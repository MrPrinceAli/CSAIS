import { cache } from "react";
import type { InValue } from "@libsql/client";
import { query, queryOne } from "./db";
import { publisherOf } from "./format";
import { fromHex, leafHash, merkleProof, toHex, verifyProof } from "./merkle";
import type { StoredTrust } from "./trust";

export type IncidentRow = {
  incident_id: string;
  attack_type: string | null;
  target: string | null;
  threat_actor: string | null;
  location: string | null;
  attack_date: string | null;
  document_count: number;
  incident_confidence: number;
  anchor_article_id: number;
  anchor_published_date: string | null;
  last_published_date: string | null;
  title: string | null;
  language: string | null;
  domains: number | null;
  independence: number | null;
  domain_list: string | null; // domain sumber dipisah koma (untuk tumpukan logo)
} & StoredTrust;

/* --- Keberadaan tabel ---
 * Tabel baru (v07_trust, evidence_batches, evidence_leaves) baru ada di Turso
 * setelah pipeline versi baru menerbitkannya. Halaman tidak boleh gagal
 * sebelum itu, jadi keberadaannya dicek dulu dan diingat per instance;
 * hasil "belum ada" dicek ulang tiap lima menit. */
const tableCache = new Map<string, { exists: boolean; checkedAt: number }>();
const TABLE_TTL_MS = 5 * 60 * 1000;

/** Kolom yang ditambahkan pipeline belakangan (misalnya articles.image_url) dicek lewat definisi tabel di sqlite_master. */
const columnCache = new Map<string, { exists: boolean; checkedAt: number }>();

export async function hasColumn(table: string, column: string): Promise<boolean> {
  const key = `${table}.${column}`;
  const cached = columnCache.get(key);
  const now = Date.now();
  if (cached && (cached.exists || now - cached.checkedAt < TABLE_TTL_MS)) return cached.exists;
  const row = await queryOne<{ sql: string | null }>("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", [table]);
  const exists = new RegExp(`["\\s]${column}["\\s]`).test(row?.sql ?? "");
  columnCache.set(key, { exists, checkedAt: now });
  return exists;
}

export async function hasTable(name: string): Promise<boolean> {
  const cached = tableCache.get(name);
  const now = Date.now();
  if (cached && (cached.exists || now - cached.checkedAt < TABLE_TTL_MS)) return cached.exists;
  const row = await queryOne<{ n: number }>("SELECT COUNT(*) AS n FROM sqlite_master WHERE type = 'table' AND name = ?", [name]);
  const exists = Number(row?.n ?? 0) > 0;
  tableCache.set(name, { exists, checkedAt: now });
  return exists;
}

export type Overview = {
  artikel: number;
  incident: number;
  incident_30: number;
  multi_30: number;
  bukti: number;
  sumber: number;
  isi_ok: number;
  target_known: number;
  multi_all: number;
};

export const getLastRun = cache(async () => {
  return queryOne<{ finished_at: string; pipeline_version: string; stage: string }>(
    "SELECT finished_at, pipeline_version, stage FROM pipeline_runs WHERE finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1",
  );
});

export const getOverview = cache(async (): Promise<Overview> => {
  const row = await queryOne<Overview>(`
    SELECT
      (SELECT COUNT(*) FROM articles) AS artikel,
      (SELECT COUNT(*) FROM v05_incidents) AS incident,
      (SELECT COUNT(*) FROM v05_incidents WHERE anchor_published_date >= date('now', '-30 days')) AS incident_30,
      (SELECT COUNT(*) FROM v05_incidents WHERE anchor_published_date >= date('now', '-30 days') AND document_count >= 2) AS multi_30,
      (SELECT COUNT(*) FROM v06_evidence) AS bukti,
      (SELECT COUNT(*) FROM sources) AS sumber,
      (SELECT COUNT(*) FROM articles WHERE content_status = 'ok') AS isi_ok,
      (SELECT COUNT(*) FROM v05_incidents WHERE target IS NOT NULL AND target != '') AS target_known,
      (SELECT COUNT(*) FROM v05_incidents WHERE document_count >= 2) AS multi_all
  `);
  return row ?? { artikel: 0, incident: 0, incident_30: 0, multi_30: 0, bukti: 0, sumber: 0, isi_ok: 0, target_known: 0, multi_all: 0 };
});

const TRUST_COLUMNS = `t.score AS trust_score, t.level AS trust_level, t.corroboration AS trust_corroboration,
         t.independence AS trust_independence, t.claim AS trust_claim, t.content AS trust_content,
         t.clustering AS trust_clustering`;
const NO_TRUST_COLUMNS = `NULL AS trust_score, NULL AS trust_level, NULL AS trust_corroboration,
         NULL AS trust_independence, NULL AS trust_claim, NULL AS trust_content, NULL AS trust_clustering`;

/** SELECT incident beserta skor V0.7 bila tabel v07_trust sudah diterbitkan. */
async function incidentSelect(): Promise<string> {
  const withTrust = await hasTable("v07_trust");
  return `
  SELECT i.incident_id, i.attack_type, i.target, i.threat_actor, i.location, i.attack_date,
         i.document_count, i.incident_confidence, i.anchor_article_id, i.anchor_published_date,
         i.last_published_date, a.title, a.language,
         (SELECT COUNT(DISTINCT e.source_domain) FROM v06_evidence e WHERE e.incident_id = i.incident_id) AS domains,
         (SELECT AVG(e.evidence_independence_score) FROM v06_evidence e WHERE e.incident_id = i.incident_id) AS independence,
         (SELECT GROUP_CONCAT(DISTINCT e.source_domain) FROM v06_evidence e WHERE e.incident_id = i.incident_id AND e.source_domain != '' AND e.source_domain NOT LIKE '%google.%') AS domain_list,
         ${withTrust ? TRUST_COLUMNS : NO_TRUST_COLUMNS}
  FROM v05_incidents i
  LEFT JOIN articles a ON a.article_id = i.anchor_article_id
  ${withTrust ? "LEFT JOIN v07_trust t ON t.incident_id = i.incident_id" : ""}
`;
}

export const getLatestIncidents = cache(async (limit = 6): Promise<IncidentRow[]> => {
  return query<IncidentRow>(
    `${await incidentSelect()}
     WHERE i.anchor_published_date >= date('now', '-30 days') AND i.document_count >= 2
     ORDER BY i.document_count DESC, i.last_published_date DESC
     LIMIT ?`,
    [limit],
  );
});

/** Incident 30 hari dengan sumber terbanyak yang targetnya dikenali: bahan cerita di beranda. */
export const getFeaturedIncidentId = cache(async (): Promise<string | null> => {
  const row = await queryOne<{ incident_id: string }>(
    `SELECT incident_id FROM v05_incidents
     WHERE anchor_published_date >= date('now', '-45 days') AND target != '' AND document_count >= 3
     ORDER BY document_count DESC, last_published_date DESC LIMIT 1`,
  );
  return row?.incident_id ?? null;
});

export type ScanRow = {
  title: string | null;
  language: string | null;
  published_date: string | null;
  target: string | null;
  attack_type: string | null;
  source_domain: string | null;
  incident_id: string;
  document_count: number;
  trust_score: number | null;
};

/** Artikel terbaru yang sudah bergabung ke incident bersumber 2+, untuk panel pemindai di beranda. */
export const getScannerFeed = cache(async (limit = 8): Promise<ScanRow[]> => {
  const withTrust = await hasTable("v07_trust");
  return query<ScanRow>(
    `SELECT a.title, a.language, a.published_date, x.target, x.attack_type, e.source_domain,
            i.incident_id, i.document_count, ${withTrust ? "t.score" : "NULL"} AS trust_score
     FROM v06_evidence e
     JOIN articles a ON a.article_id = e.article_id
     JOIN v03_information_extraction x ON x.article_id = a.article_id
     JOIN v05_incidents i ON i.incident_id = e.incident_id
     ${withTrust ? "LEFT JOIN v07_trust t ON t.incident_id = i.incident_id" : ""}
     WHERE x.target != '' AND x.target != 'UNKNOWN' AND i.document_count >= 2
       AND e.source_domain != '' AND e.source_domain NOT LIKE '%google.%'
       AND a.published_date <= date('now', '+1 day')
     ORDER BY a.published_date DESC
     LIMIT ?`,
    [limit],
  );
});

export type NewsRow = {
  article_id: number;
  image_url: string | null;
  title: string | null;
  published_date: string | null;
  language: string | null;
  source_domain: string;
  attack_type: string | null;
  incident_id: string;
};

/** Artikel terbaru dengan domain media asli, untuk dinding berita di beranda. */
export const getNewsFeed = cache(async (limit = 36): Promise<NewsRow[]> => {
  const withImage = await hasColumn("articles", "image_url");
  return query<NewsRow>(
    `SELECT a.article_id, ${withImage ? "a.image_url" : "NULL AS image_url"}, a.title, a.published_date, a.language, e.source_domain, x.attack_type, e.incident_id
     FROM v06_evidence e
     JOIN articles a ON a.article_id = e.article_id
     LEFT JOIN v03_information_extraction x ON x.article_id = a.article_id
     WHERE e.source_domain != '' AND e.source_domain NOT LIKE '%google.%'
       AND a.published_date <= date('now', '+1 day')
     ORDER BY a.published_date DESC
     LIMIT ?`,
    [limit],
  );
});

/** Domain sumber dengan artikel terbanyak (marquee logo). */
export const getTopSourceDomains = cache(async (limit = 28): Promise<string[]> => {
  const rows = await query<{ domain: string }>(`SELECT domain FROM sources WHERE source_type != 'BLOG' ORDER BY article_count DESC LIMIT ?`, [limit]);
  return rows.map((r) => r.domain);
});

/**
 * Incident 60 hari dengan penerbit berbeda terbanyak (korban dikenali): contoh
 * nyata di bagian "Cara kerja". Penerbit diambil dari akhiran judul Google News
 * karena source_name selalu "Google News" dan domain bukti lama masih
 * news.google.com; kandidatnya 15 incident dengan artikel terbanyak.
 */
export const getShowcaseIncidentId = cache(async (): Promise<string | null> => {
  const rows = await query<{ incident_id: string; title: string | null }>(
    `SELECT d.incident_id, a.title
     FROM v05_incident_documents d
     JOIN articles a ON a.article_id = d.article_id
     WHERE d.incident_id IN (
       SELECT incident_id FROM v05_incidents
       WHERE anchor_published_date >= date('now', '-60 days')
         AND target IS NOT NULL AND target NOT IN ('', 'UNKNOWN') AND document_count >= 3
       ORDER BY document_count DESC
       LIMIT 15
     )`,
  );
  const publishers = new Map<string, Set<string>>();
  for (const row of rows) {
    const set = publishers.get(row.incident_id) ?? new Set<string>();
    const name = publisherOf(row.title).toLowerCase();
    if (name) set.add(name);
    publishers.set(row.incident_id, set);
  }
  let best: string | null = null;
  let bestSize = 0;
  for (const [id, set] of publishers) {
    if (set.size > bestSize) {
      best = id;
      bestSize = set.size;
    }
  }
  return best;
});

export type CoverageDoc = {
  incident_id: string;
  article_id: number;
  title: string | null;
  published_date: string | null;
  resolved_url: string | null;
  image_url: string | null;
};

/** Artikel beberapa incident sekaligus (urut tanggal terbit), untuk bagian liputan terluas. */
export const getCoverageDocs = cache(async (ids: string[]): Promise<CoverageDoc[]> => {
  if (!ids.length) return [];
  const withImage = await hasColumn("articles", "image_url");
  return query<CoverageDoc>(
    `SELECT d.incident_id, a.article_id, a.title, a.published_date, a.resolved_url,
            ${withImage ? "a.image_url" : "NULL AS image_url"}
     FROM v05_incident_documents d
     JOIN articles a ON a.article_id = d.article_id
     WHERE d.incident_id IN (${ids.map(() => "?").join(", ")})
     ORDER BY a.published_date ASC, a.article_id ASC`,
    ids,
  );
});

/** Nama penerbit (huruf kecil) ke domain, dari registri sumber; untuk logo penerbit. */
export const getPublisherDomains = cache(async (): Promise<Record<string, string>> => {
  const rows = await query<{ domain: string; publisher_name: string }>(
    `SELECT domain, publisher_name FROM sources WHERE publisher_name IS NOT NULL AND publisher_name != '' ORDER BY article_count DESC`,
  );
  const map: Record<string, string> = {};
  for (const r of rows) {
    const key = r.publisher_name.toLowerCase();
    if (!(key in map)) map[key] = r.domain;
  }
  return map;
});

export type CountryCount = { location: string; n: number };

export const getCountryCounts = cache(async (days = 90): Promise<CountryCount[]> => {
  return query<CountryCount>(
    `SELECT LOWER(location) AS location, COUNT(*) AS n FROM v05_incidents
     WHERE location != '' AND anchor_published_date >= date('now', ?)
     GROUP BY location ORDER BY n DESC`,
    [`-${days} days`],
  );
});

export const getDailyArticles = cache(async (days = 60) => {
  return query<{ d: string; n: number }>(
    `SELECT substr(a.published_date, 1, 10) AS d, COUNT(*) AS n
     FROM articles a
     WHERE a.published_date >= date('now', ?) AND a.published_date <= date('now', '+1 day')
     GROUP BY d ORDER BY d`,
    [`-${days} days`],
  );
});

export type DashboardFilters = {
  q?: string;
  jenis?: string;
  bahasa?: string;
  min?: number;
  hari?: number;
  negara?: string;
  page?: number;
};

const PAGE_SIZE = 40;

function buildWhere(f: DashboardFilters): { where: string; args: InValue[] } {
  const clauses: string[] = [];
  const args: InValue[] = [];
  const days = f.hari && f.hari > 0 ? f.hari : 30;
  clauses.push(`i.anchor_published_date >= date('now', ?)`);
  args.push(`-${days} days`);
  if (f.q) {
    const like = `%${f.q}%`;
    clauses.push(`(i.target LIKE ? OR i.threat_actor LIKE ? OR a.title LIKE ?)`);
    args.push(like, like, like);
  }
  if (f.jenis) {
    clauses.push(`LOWER(i.attack_type) LIKE ?`);
    args.push(`${f.jenis.toLowerCase()}%`);
  }
  if (f.bahasa) {
    clauses.push(`a.language = ?`);
    args.push(f.bahasa);
  }
  if (f.negara) {
    clauses.push(`LOWER(i.location) = ?`);
    args.push(f.negara.toLowerCase());
  }
  if (f.min && f.min > 1) {
    clauses.push(`i.document_count >= ?`);
    args.push(f.min);
  }
  return { where: clauses.length ? `WHERE ${clauses.join(" AND ")}` : "", args };
}

export async function getDashboard(f: DashboardFilters) {
  const { where, args } = buildWhere(f);
  const page = f.page && f.page > 0 ? f.page : 1;
  const base = `FROM v05_incidents i LEFT JOIN articles a ON a.article_id = i.anchor_article_id ${where}`;
  const select = await incidentSelect();
  const [rows, totalRow, daily, types, countries, kpi, allCountries, multi] = await Promise.all([
    query<IncidentRow>(
      `${select} ${where}
       ORDER BY i.document_count DESC, i.anchor_published_date DESC
       LIMIT ? OFFSET ?`,
      [...args, PAGE_SIZE, (page - 1) * PAGE_SIZE],
    ),
    queryOne<{ n: number }>(`SELECT COUNT(*) AS n ${base}`, args),
    query<{ d: string; n: number }>(`SELECT substr(i.anchor_published_date, 1, 10) AS d, COUNT(*) AS n ${base} GROUP BY d ORDER BY d`, args),
    query<{ t: string; n: number }>(
      // jenis utama = kategori pertama ("ransomware, malware" dihitung sebagai ransomware)
      `SELECT CASE WHEN instr(x, ',') > 0 THEN trim(substr(x, 1, instr(x, ',') - 1)) ELSE x END AS t, COUNT(*) AS n
       FROM (SELECT LOWER(COALESCE(NULLIF(i.attack_type, ''), 'unknown')) AS x ${base})
       GROUP BY t ORDER BY n DESC LIMIT 16`,
      args,
    ),
    query<CountryCount>(`SELECT LOWER(i.location) AS location, COUNT(*) AS n ${base} AND i.location != '' GROUP BY location ORDER BY n DESC LIMIT 8`, args),
    queryOne<{ total: number; multi: number; target_known: number; indonesia: number }>(
      `SELECT COUNT(*) AS total,
              SUM(CASE WHEN i.document_count >= 2 THEN 1 ELSE 0 END) AS multi,
              SUM(CASE WHEN i.target IS NOT NULL AND i.target != '' THEN 1 ELSE 0 END) AS target_known,
              SUM(CASE WHEN a.language = 'id' THEN 1 ELSE 0 END) AS indonesia
       ${base}`,
      args,
    ),
    query<CountryCount>(`SELECT LOWER(i.location) AS location, COUNT(*) AS n ${base} AND i.location != '' GROUP BY LOWER(i.location) ORDER BY n DESC`, args),
    query<{ location: string }>(`SELECT LOWER(i.location) AS location ${base} AND i.location LIKE '%,%' LIMIT 3000`, args),
  ]);
  const total = Number(totalRow?.n ?? 0);
  return {
    rows,
    total,
    page,
    pageSize: PAGE_SIZE,
    pages: Math.max(1, Math.ceil(total / PAGE_SIZE)),
    daily,
    types,
    countries,
    kpi: kpi ?? { total: 0, multi: 0, target_known: 0, indonesia: 0 },
    allCountries,
    pairs: countryPairs(multi.map((m) => m.location)),
  };
}

/** Pasangan negara yang disebut bersama dalam satu incident, terbanyak dulu (bahan busur globe). */
function countryPairs(locations: string[]): { a: string; b: string; n: number }[] {
  const counts = new Map<string, number>();
  for (const value of locations) {
    const names = [...new Set(value.split(",").map((x) => x.trim()).filter(Boolean))].sort();
    for (let i = 0; i < names.length; i++) {
      for (let j = i + 1; j < names.length; j++) {
        const key = `${names[i]}|${names[j]}`;
        counts.set(key, (counts.get(key) ?? 0) + 1);
      }
    }
  }
  return [...counts.entries()]
    .map(([key, n]) => {
      const [a, b] = key.split("|");
      return { a, b, n };
    })
    .sort((x, y) => y.n - x.n)
    .slice(0, 24);
}

export const getAttackTypeOptions = cache(async () => {
  return query<{ t: string; n: number }>(
    `SELECT LOWER(attack_type) AS t, COUNT(*) AS n FROM v05_incidents
     WHERE attack_type != '' AND attack_type NOT LIKE '%,%'
     GROUP BY t ORDER BY n DESC LIMIT 20`,
  );
});

export type DocumentRow = {
  article_id: number;
  title: string | null;
  published_date: string | null;
  resolved_url: string | null;
  article_url: string | null;
  source_name: string | null;
  syndicated_of: number | null;
  language: string | null;
  content_status: string | null;
  content_sha256: string | null;
  content_fetched_at: string | null;
  similarity_score: number | null;
  evidence_type: string | null;
  evidence_uid: string | null;
  source_domain: string | null;
  evidence_independence_score: number | null;
  content_fingerprint: string | null;
  target: string | null;
  threat_actor: string | null;
  attack_type: string | null;
  attack_date: string | null;
  field_confidence: string | null;
};

export const getIncident = cache(async (id: string) => {
  const select = await incidentSelect();
  const incident = await queryOne<IncidentRow>(`${select} WHERE i.incident_id = ?`, [id]);
  if (!incident) return null;
  const [docs, relations, related, ledgerCount] = await Promise.all([
    query<DocumentRow>(
      `SELECT a.article_id, a.title, a.published_date, a.resolved_url, a.article_url, a.source_name,
              a.syndicated_of, a.language, a.content_status, a.content_sha256, a.content_fetched_at,
              d.similarity_score,
              e.evidence_type, e.evidence_uid, e.source_domain, e.evidence_independence_score, e.content_fingerprint,
              x.target, x.threat_actor, x.attack_type, x.attack_date, x.field_confidence
       FROM v05_incident_documents d
       JOIN articles a ON a.article_id = d.article_id
       LEFT JOIN v06_evidence e ON e.article_id = d.article_id AND e.incident_id = d.incident_id
       LEFT JOIN v03_information_extraction x ON x.article_id = d.article_id
       WHERE d.incident_id = ?
       ORDER BY a.published_date ASC
       LIMIT 200`,
      [id],
    ),
    query<{ relation_type: string; n: number }>(
      `SELECT relation_type, COUNT(*) AS n FROM v06_source_relations WHERE incident_id = ? GROUP BY relation_type ORDER BY n DESC`,
      [id],
    ),
    incident.target
      ? query<IncidentRow>(
          `${select}
           WHERE i.target = ? AND i.incident_id != ?
           ORDER BY i.anchor_published_date DESC LIMIT 6`,
          [incident.target, id],
        )
      : Promise.resolve([] as IncidentRow[]),
    // jumlah bukti incident ini yang sudah masuk batch Merkle (ledger off-chain)
    hasTable("evidence_leaves").then((ok) =>
      ok
        ? queryOne<{ n: number }>(
            `SELECT COUNT(*) AS n FROM evidence_leaves l JOIN v06_evidence e ON e.evidence_uid = l.evidence_uid WHERE e.incident_id = ?`,
            [id],
          ).then((r) => Number(r?.n ?? 0))
        : 0,
    ),
  ]);
  return { incident, docs, relations, related, ledgerCount };
});

export type GroupStat = {
  group: string;
  now: number;
  prev: number;
  weeks: number[]; // 8 pekan terakhir, dari yang paling lama
  types: { t: string; n: number }[];
  typesAll: Record<string, number>;
  samples: { incident_id: string; title: string | null; attack_type: string | null; document_count: number }[];
};

export const getRiskGroups = cache(async (): Promise<GroupStat[]> => {
  const rows = await query<{
    target_group: string;
    incident_id: string;
    anchor_published_date: string;
    attack_type: string | null;
    document_count: number;
    title: string | null;
  }>(`
    SELECT x.target_group, d.incident_id, i.anchor_published_date, i.attack_type, i.document_count, a.title
    FROM v03_information_extraction x
    JOIN v05_incident_documents d ON d.article_id = x.article_id
    JOIN v05_incidents i ON i.incident_id = d.incident_id
    LEFT JOIN articles a ON a.article_id = i.anchor_article_id
    WHERE x.target_group != 'UNKNOWN' AND i.anchor_published_date >= date('now', '-60 days')
  `);
  const now = Date.now();
  const cutoff = new Date(now - 30 * 86400 * 1000).toISOString();
  type Acc = {
    now: Set<string>;
    prev: Set<string>;
    weeks: Set<string>[];
    types: Map<string, number>;
    samples: Map<string, GroupStat["samples"][number]>;
  };
  const stats = new Map<string, Acc>();
  for (const row of rows) {
    const ts = new Date(row.anchor_published_date).getTime();
    const weekIndex = 7 - Math.min(7, Math.floor((now - ts) / (7 * 86400 * 1000)));
    for (const raw of row.target_group.split(",")) {
      const group = raw.trim();
      if (!group) continue;
      let s = stats.get(group);
      if (!s) {
        s = { now: new Set(), prev: new Set(), weeks: Array.from({ length: 8 }, () => new Set<string>()), types: new Map(), samples: new Map() };
        stats.set(group, s);
      }
      const recent = row.anchor_published_date >= cutoff;
      (recent ? s.now : s.prev).add(row.incident_id);
      if (weekIndex >= 0 && weekIndex < 8) s.weeks[weekIndex].add(row.incident_id);
      if (recent) {
        const type = (row.attack_type ?? "").toLowerCase().split(",")[0].trim() || "unknown";
        s.types.set(type, (s.types.get(type) ?? 0) + 1);
        if (!s.samples.has(row.incident_id)) {
          s.samples.set(row.incident_id, {
            incident_id: row.incident_id,
            title: row.title,
            attack_type: row.attack_type,
            document_count: Number(row.document_count),
          });
        }
      }
    }
  }
  return [...stats.entries()]
    .map(([group, s]) => ({
      group,
      now: s.now.size,
      prev: s.prev.size,
      weeks: s.weeks.map((w) => w.size),
      types: [...s.types.entries()].map(([t, n]) => ({ t, n })).sort((a, b) => b.n - a.n).slice(0, 3),
      typesAll: Object.fromEntries(s.types),
      samples: [...s.samples.values()].sort((a, b) => b.document_count - a.document_count).slice(0, 3),
    }))
    .sort((a, b) => b.now - a.now);
});

/** Posisi satu bukti dalam batch Merkle beserta bukti (proof) yang dihitung ulang dari daun batch. */
export type LedgerProof = {
  batch_id: number;
  leaf_index: number;
  leaf_count: number;
  leaf_hash: string;
  merkle_root: string;
  created_at: string;
  anchor_status: string;
  anchor_chain: string | null;
  anchor_tx: string | null;
  proof: string[];
  valid: boolean; // daun + proof menghasilkan akar batch
  leaf_matches: boolean; // hash daun tersimpan = SHA-256(0x00 || payload)
  snapshot_sha256: string | null; // content_sha256 saat batch dibuat
  snapshot_changed: boolean; // teks artikel diambil/berubah setelah batch
};

export type VerifyEvidence = {
  evidence_uid: string;
  incident_id: string;
  content_fingerprint: string | null;
  evidence_type: string | null;
  ledger: LedgerProof | null;
};

export type VerifyResult = {
  kind: "hash" | "url" | "uid" | "kosong";
  article: {
    article_id: number;
    article_uid: string | null;
    title: string | null;
    resolved_url: string | null;
    article_url: string | null;
    content_status: string | null;
    content_sha256: string | null;
    content_fetched_at: string | null;
    published_date: string | null;
  } | null;
  evidence: VerifyEvidence[];
};

type LeafRow = {
  batch_id: number;
  leaf_index: number;
  leaf_hash: string;
  payload: string;
  merkle_root: string;
  leaf_count: number;
  created_at: string;
  anchor_status: string;
  anchor_chain: string | null;
  anchor_tx: string | null;
};

/** Bukti Merkle satu evidence_uid, dihitung dari daun batch (maksimal 1.024 baris). */
async function ledgerProof(evidenceUid: string, currentSha256: string | null): Promise<LedgerProof | null> {
  const leaf = await queryOne<LeafRow>(
    `SELECT l.batch_id, l.leaf_index, l.leaf_hash, l.payload, b.merkle_root, b.leaf_count, b.created_at,
            b.anchor_status, b.anchor_chain, b.anchor_tx
     FROM evidence_leaves l JOIN evidence_batches b ON b.batch_id = l.batch_id
     WHERE l.evidence_uid = ?`,
    [evidenceUid],
  );
  if (!leaf) return null;
  const rows = await query<{ leaf_hash: string }>(`SELECT leaf_hash FROM evidence_leaves WHERE batch_id = ? ORDER BY leaf_index`, [leaf.batch_id]);
  const leaves = rows.map((r) => fromHex(r.leaf_hash));
  const index = Number(leaf.leaf_index);
  const proof = index < leaves.length ? merkleProof(leaves, index) : [];
  let snapshotSha: string | null = null;
  try {
    snapshotSha = (JSON.parse(leaf.payload) as { content_sha256?: string | null }).content_sha256 ?? null;
  } catch {
    snapshotSha = null;
  }
  return {
    batch_id: Number(leaf.batch_id),
    leaf_index: index,
    leaf_count: Number(leaf.leaf_count),
    leaf_hash: leaf.leaf_hash,
    merkle_root: leaf.merkle_root,
    created_at: leaf.created_at,
    anchor_status: leaf.anchor_status,
    anchor_chain: leaf.anchor_chain,
    anchor_tx: leaf.anchor_tx,
    proof: proof.map(toHex),
    valid: index < leaves.length && verifyProof(fromHex(leaf.leaf_hash), proof, fromHex(leaf.merkle_root)),
    leaf_matches: toHex(leafHash(leaf.payload)) === leaf.leaf_hash,
    snapshot_sha256: snapshotSha,
    snapshot_changed: (snapshotSha ?? null) !== (currentSha256 ?? null),
  };
}

/** Posisi satu bukti di batch Merkle; null bila tabel ledger belum terbit atau bukti belum masuk batch. */
export async function getEvidenceLeaf(evidenceUid: string | null, currentSha256: string | null): Promise<LedgerProof | null> {
  if (!evidenceUid || !(await hasTable("evidence_leaves"))) return null;
  return ledgerProof(evidenceUid, currentSha256);
}

export type LedgerStats = { batches: number; leaves: number; pending: number; latest: string | null };

/** Ringkasan ledger off-chain untuk halaman verifikasi; null bila tabel belum diterbitkan. */
export const getLedgerStats = cache(async (): Promise<LedgerStats | null> => {
  if (!(await hasTable("evidence_batches"))) return null;
  const row = await queryOne<{ batches: number; leaves: number; pending: number; latest: string | null }>(
    `SELECT COUNT(*) AS batches, COALESCE(SUM(leaf_count), 0) AS leaves,
            SUM(CASE WHEN anchor_status = 'PENDING' THEN 1 ELSE 0 END) AS pending,
            MAX(created_at) AS latest
     FROM evidence_batches`,
  );
  return row ? { batches: Number(row.batches), leaves: Number(row.leaves), pending: Number(row.pending), latest: row.latest } : null;
});

export async function verify(input: string): Promise<VerifyResult> {
  const value = input.trim();
  if (!value) return { kind: "kosong", article: null, evidence: [] };
  const articleCols =
    "article_id, article_uid, title, resolved_url, article_url, content_status, content_sha256, content_fetched_at, published_date";
  let kind: VerifyResult["kind"] = "uid";
  let article: VerifyResult["article"] = null;
  if (/^[0-9a-f]{64}$/i.test(value)) {
    kind = "hash";
    article = await queryOne(`SELECT ${articleCols} FROM articles WHERE content_sha256 = ? LIMIT 1`, [value.toLowerCase()]);
    if (!article) {
      const ev = await queryOne<{ article_id: number }>(`SELECT article_id FROM v06_evidence WHERE content_fingerprint = ? LIMIT 1`, [value.toLowerCase()]);
      if (ev) article = await queryOne(`SELECT ${articleCols} FROM articles WHERE article_id = ?`, [ev.article_id]);
    }
  } else if (/^https?:\/\//i.test(value)) {
    kind = "url";
    const bare = value.replace(/[?#].*$/, "").replace(/\/$/, "");
    article = await queryOne(
      `SELECT ${articleCols} FROM articles
       WHERE resolved_url = ? OR resolved_url LIKE ? OR article_url = ? OR article_url LIKE ?
       LIMIT 1`,
      [value, `${bare}%`, value, `${bare}%`],
    );
  } else {
    const ev = await queryOne<{ article_id: number }>(`SELECT article_id FROM v06_evidence WHERE evidence_uid = ? LIMIT 1`, [value.toLowerCase()]);
    if (ev) {
      article = await queryOne(`SELECT ${articleCols} FROM articles WHERE article_id = ?`, [ev.article_id]);
    } else {
      article = await queryOne(`SELECT ${articleCols} FROM articles WHERE article_uid = ? LIMIT 1`, [value.toLowerCase()]);
    }
  }
  const rows = article
    ? await query<Omit<VerifyEvidence, "ledger">>(
        `SELECT evidence_uid, incident_id, content_fingerprint, evidence_type FROM v06_evidence WHERE article_id = ?`,
        [article.article_id],
      )
    : [];
  const withLedger = rows.length > 0 && (await hasTable("evidence_leaves"));
  const evidence: VerifyEvidence[] = await Promise.all(
    rows.map(async (row) => ({
      ...row,
      ledger: withLedger ? await ledgerProof(row.evidence_uid, article?.content_sha256 ?? null) : null,
    })),
  );
  return { kind, article, evidence };
}

/** Contoh bukti terbaru untuk ditampilkan di halaman verifikasi saat kosong. */
export const getSampleEvidence = cache(async () => {
  return query<{ evidence_uid: string; content_sha256: string | null; title: string | null; incident_id: string }>(
    `SELECT e.evidence_uid, a.content_sha256, a.title, e.incident_id
     FROM v06_evidence e JOIN articles a ON a.article_id = e.article_id
     WHERE a.content_sha256 IS NOT NULL
     ORDER BY e.publication_date DESC LIMIT 3`,
  );
});

export type SourceRow = {
  domain: string;
  source_type: string;
  country: string;
  publisher_name: string | null;
  article_count: number;
  first_seen: string | null;
  last_seen: string | null;
};

export type SourceFilters = { q?: string; tipe?: string; negara?: string; urut?: string; page?: number };
const SOURCE_PAGE = 48;

export async function getSources(f: SourceFilters) {
  const clauses: string[] = [];
  const args: InValue[] = [];
  if (f.q) {
    clauses.push(`(domain LIKE ? OR publisher_name LIKE ?)`);
    args.push(`%${f.q}%`, `%${f.q}%`);
  }
  if (f.tipe) {
    clauses.push(`source_type = ?`);
    args.push(f.tipe.toUpperCase());
  }
  if (f.negara) {
    clauses.push(`country = ?`);
    args.push(f.negara);
  }
  const where = clauses.length ? `WHERE ${clauses.join(" AND ")}` : "";
  const order = f.urut === "terbaru" ? "last_seen DESC" : f.urut === "nama" ? "domain ASC" : "article_count DESC, domain ASC";
  const page = f.page && f.page > 0 ? f.page : 1;
  const [rows, totalRow, byType, byCountry, maxRow] = await Promise.all([
    query<SourceRow>(
      `SELECT domain, source_type, country, publisher_name, article_count, first_seen, last_seen
       FROM sources ${where} ORDER BY ${order} LIMIT ? OFFSET ?`,
      [...args, SOURCE_PAGE, (page - 1) * SOURCE_PAGE],
    ),
    queryOne<{ n: number }>(`SELECT COUNT(*) AS n FROM sources ${where}`, args),
    query<{ source_type: string; n: number; artikel: number }>(`SELECT source_type, COUNT(*) AS n, SUM(article_count) AS artikel FROM sources GROUP BY source_type ORDER BY n DESC`),
    query<{ country: string; n: number }>(`SELECT country, COUNT(*) AS n FROM sources GROUP BY country ORDER BY n DESC LIMIT 10`),
    queryOne<{ m: number }>(`SELECT MAX(article_count) AS m FROM sources`),
  ]);
  const total = Number(totalRow?.n ?? 0);
  return {
    rows,
    total,
    page,
    pageSize: SOURCE_PAGE,
    pages: Math.max(1, Math.ceil(total / SOURCE_PAGE)),
    byType,
    byCountry,
    max: Number(maxRow?.m ?? 1),
  };
}

export const getLanguageCounts = cache(async () => {
  return query<{ language: string; n: number }>(
    `SELECT COALESCE(NULLIF(language, ''), 'unknown') AS language, COUNT(*) AS n FROM articles GROUP BY language ORDER BY n DESC LIMIT 6`,
  );
});
