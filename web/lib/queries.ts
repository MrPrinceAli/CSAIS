import { cache } from "react";
import type { InValue } from "@libsql/client";
import { query, queryOne } from "./db";

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
};

export type Overview = {
  artikel: number;
  incident: number;
  incident_30: number;
  multi_30: number;
  bukti: number;
  sumber: number;
  atestasi: number;
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
      0 AS atestasi
  `);
  return row ?? { artikel: 0, incident: 0, incident_30: 0, multi_30: 0, bukti: 0, sumber: 0, atestasi: 0 };
});

const INCIDENT_SELECT = `
  SELECT i.incident_id, i.attack_type, i.target, i.threat_actor, i.location, i.attack_date,
         i.document_count, i.incident_confidence, i.anchor_article_id, i.anchor_published_date,
         i.last_published_date, a.title, a.language
  FROM v05_incidents i
  LEFT JOIN articles a ON a.article_id = i.anchor_article_id
`;

export const getLatestIncidents = cache(async (limit = 6): Promise<IncidentRow[]> => {
  return query<IncidentRow>(
    `${INCIDENT_SELECT}
     WHERE i.anchor_published_date >= date('now', '-30 days') AND i.document_count >= 2
     ORDER BY i.document_count DESC, i.last_published_date DESC
     LIMIT ?`,
    [limit],
  );
});

export type DashboardFilters = {
  q?: string;
  jenis?: string;
  bahasa?: string;
  min?: number;
  hari?: number;
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
  if (f.min && f.min > 1) {
    clauses.push(`i.document_count >= ?`);
    args.push(f.min);
  }
  return { where: clauses.length ? `WHERE ${clauses.join(" AND ")}` : "", args };
}

export async function getDashboard(f: DashboardFilters) {
  const { where, args } = buildWhere(f);
  const page = f.page && f.page > 0 ? f.page : 1;
  const [rows, totalRow, daily, types, kpi] = await Promise.all([
    query<IncidentRow>(
      `${INCIDENT_SELECT} ${where}
       ORDER BY i.document_count DESC, i.anchor_published_date DESC
       LIMIT ? OFFSET ?`,
      [...args, PAGE_SIZE, (page - 1) * PAGE_SIZE],
    ),
    queryOne<{ n: number }>(
      `SELECT COUNT(*) AS n FROM v05_incidents i LEFT JOIN articles a ON a.article_id = i.anchor_article_id ${where}`,
      args,
    ),
    query<{ d: string; n: number }>(
      `SELECT substr(i.anchor_published_date, 1, 10) AS d, COUNT(*) AS n
       FROM v05_incidents i LEFT JOIN articles a ON a.article_id = i.anchor_article_id ${where}
       GROUP BY d ORDER BY d`,
      args,
    ),
    query<{ t: string; n: number }>(
      `SELECT LOWER(COALESCE(NULLIF(i.attack_type, ''), 'unknown')) AS t, COUNT(*) AS n
       FROM v05_incidents i LEFT JOIN articles a ON a.article_id = i.anchor_article_id ${where}
       GROUP BY t ORDER BY n DESC LIMIT 8`,
      args,
    ),
    queryOne<{ total: number; multi: number; target_known: number; indonesia: number }>(
      `SELECT COUNT(*) AS total,
              SUM(CASE WHEN i.document_count >= 2 THEN 1 ELSE 0 END) AS multi,
              SUM(CASE WHEN i.target IS NOT NULL AND i.target != '' THEN 1 ELSE 0 END) AS target_known,
              SUM(CASE WHEN a.language = 'id' THEN 1 ELSE 0 END) AS indonesia
       FROM v05_incidents i LEFT JOIN articles a ON a.article_id = i.anchor_article_id ${where}`,
      args,
    ),
  ]);
  return {
    rows,
    total: Number(totalRow?.n ?? 0),
    page,
    pageSize: PAGE_SIZE,
    daily,
    types,
    kpi: kpi ?? { total: 0, multi: 0, target_known: 0, indonesia: 0 },
  };
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

export async function getIncident(id: string) {
  const incident = await queryOne<IncidentRow>(`${INCIDENT_SELECT} WHERE i.incident_id = ?`, [id]);
  if (!incident) return null;
  const [docs, relations, related] = await Promise.all([
    query<DocumentRow>(
      `SELECT a.article_id, a.title, a.published_date, a.resolved_url, a.article_url, a.source_name,
              a.syndicated_of, a.language, a.content_status, a.content_sha256,
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
          `${INCIDENT_SELECT}
           WHERE i.target = ? AND i.incident_id != ?
           ORDER BY i.anchor_published_date DESC LIMIT 6`,
          [incident.target, id],
        )
      : Promise.resolve([] as IncidentRow[]),
  ]);
  return { incident, docs, relations, related };
}

export type GroupStat = {
  group: string;
  now: number;
  prev: number;
  types: { t: string; n: number }[];
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
  const cutoff = new Date(Date.now() - 30 * 86400 * 1000).toISOString();
  const stats = new Map<string, { now: Set<string>; prev: Set<string>; types: Map<string, number>; samples: Map<string, GroupStat["samples"][number]> }>();
  for (const row of rows) {
    for (const raw of row.target_group.split(",")) {
      const group = raw.trim();
      if (!group) continue;
      let s = stats.get(group);
      if (!s) {
        s = { now: new Set(), prev: new Set(), types: new Map(), samples: new Map() };
        stats.set(group, s);
      }
      const recent = row.anchor_published_date >= cutoff;
      (recent ? s.now : s.prev).add(row.incident_id);
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
      types: [...s.types.entries()].map(([t, n]) => ({ t, n })).sort((a, b) => b.n - a.n).slice(0, 3),
      samples: [...s.samples.values()].sort((a, b) => b.document_count - a.document_count).slice(0, 3),
    }))
    .sort((a, b) => b.now - a.now);
});

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
  evidence: { evidence_uid: string; incident_id: string; content_fingerprint: string | null; evidence_type: string | null }[];
};

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
      const ev = await queryOne<{ article_id: number }>(
        `SELECT article_id FROM v06_evidence WHERE content_fingerprint = ? LIMIT 1`,
        [value.toLowerCase()],
      );
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
    const ev = await queryOne<{ article_id: number }>(
      `SELECT article_id FROM v06_evidence WHERE evidence_uid = ? LIMIT 1`,
      [value.toLowerCase()],
    );
    if (ev) {
      article = await queryOne(`SELECT ${articleCols} FROM articles WHERE article_id = ?`, [ev.article_id]);
    } else {
      article = await queryOne(`SELECT ${articleCols} FROM articles WHERE article_uid = ? LIMIT 1`, [value.toLowerCase()]);
    }
  }
  const evidence = article
    ? await query<VerifyResult["evidence"][number]>(
        `SELECT evidence_uid, incident_id, content_fingerprint, evidence_type FROM v06_evidence WHERE article_id = ?`,
        [article.article_id],
      )
    : [];
  return { kind, article, evidence };
}

export const getSources = cache(async () => {
  return query<{
    domain: string;
    source_type: string;
    country: string;
    publisher_name: string | null;
    article_count: number;
    first_seen: string | null;
    last_seen: string | null;
  }>(`SELECT domain, source_type, country, publisher_name, article_count, first_seen, last_seen
      FROM sources ORDER BY article_count DESC, domain ASC LIMIT 300`);
});
