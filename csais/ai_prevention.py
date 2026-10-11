"""Saran preventif dan literasi oleh model AI (API berbayar) untuk alur D1 - D4.

Satu model yang sama menulis saran untuk setiap alur, tetapi masukannya
berbeda sesuai alurnya, sehingga keluarannya bisa dibandingkan:

  D1  kartu mesin + berita (judul, ringkasan), kelompok masyarakat, platform,
      dan wilayah yang disebut;
  D2  kartu yang sama + hasil survei publik (penilaian per kolom, koreksi,
      dan jawaban "benar terjadi?");
  D3  kartu yang sama + keputusan lembaga (status, alasan, koreksi, langkah
      dan sasaran yang dipilih, imbauan);
  D4  catatan resmi (dikonfirmasi atau dibantah, beserta alasannya).

Biaya dibatasi: hanya incident TOP_N terbesar (artikel + 2 x sumber dalam
TOP_DAYS hari terakhir data) yang diproses, dan saran hanya ditulis ulang bila
masukannya berubah (``input_hash``). Selain itu setiap provinsi di Peta
Literasi mendapat saran wilayah dari profilnya, kasus lokal, dan incident
terbesar; ditulis ulang bila kasus lokal berubah atau sudah REGION_MAX_AGE_DAYS.

Pengaturan (.env / rahasia GitHub Actions), API apa pun yang kompatibel OpenAI:
  AI_BASE_URL   mis. https://api.openai.com/v1, https://api.anthropic.com/v1,
                https://generativelanguage.googleapis.com/v1beta/openai,
                https://openrouter.ai/api/v1, https://api.deepseek.com/v1
  AI_API_KEY    kunci API (rahasia)
  AI_MODEL      nama model di penyedia itu
  AI_MAX_CALLS  batas permintaan per run (default 100)
Tanpa AI_API_KEY/AI_MODEL tahap ini dilewati.

Tabel: ``ai_top`` (peringkat incident terbesar saat ini), ``ai_prevention``
(saran per incident dan alur), ``ai_region_literacy`` (saran per provinsi).
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from csais import flows
from csais.config import PROJECT_ROOT
from csais.db import get_connection, get_timestamp
from csais.llm import LLMClient, LLMError
from csais.schema import record_run

PROMPT_VERSION = "ai-prevention-v1"
TOP_N = 10
TOP_DAYS = 14
REGION_MAX_AGE_DAYS = 7
DEFAULT_MAX_CALLS = 100
FLOWS = ("D1", "D2", "D3", "D4")

# Fakta yang boleh dipakai model untuk rentang usia; selain ini usia dikosongkan
KNOWN_FACTS = [
    "Bappebti (data per September 2024): 26,9% investor kripto Indonesia berusia 18-24 tahun dan 35,1% berusia 25-30 tahun.",
    "APJII 2024: Gen Z (12-27 tahun) adalah 34,4% pengguna internet Indonesia, milenial (28-43 tahun) 30,62%.",
]
CHANNELS = [
    "aduankonten.id (Komdigi, konten dan tautan berbahaya)",
    "patrolisiber.id (Siber Polri, laporan kejahatan siber)",
    "cekrekening.id (cek dan laporkan rekening penipu)",
    "Kontak OJK 157 / kontak157.ojk.go.id (investasi dan pinjaman ilegal)",
    "BSSN, bssn.go.id (insiden keamanan siber organisasi)",
]

SYSTEM = f"""Anda analis literasi keamanan siber untuk masyarakat Indonesia.
Tugas: dari satu incident siber dan sudut pandang alur yang diberikan, tulis saran preventif dan literasi yang SPESIFIK untuk masyarakat Indonesia.

Aturan:
- Bahasa Indonesia yang jelas untuk orang awam. Ringkas.
- Sasaran literasi harus spesifik: sebut kelompok, platform, dan konteksnya (mis. "pelajar SMA pengguna TikTok", "pengguna Binance yang menyimpan aset di exchange", "staf keuangan perusahaan menengah"), bukan "masyarakat umum".
- Incident di luar negeri tetap relevan bila layanan, modus, atau jenis korbannya juga ada di Indonesia; jelaskan kaitannya.
- Rentang usia HANYA boleh diisi bila didukung fakta berikut; selain itu kosongkan (""):
  {" ".join(KNOWN_FACTS)}
- Jangan mengarang angka, statistik, nama orang, atau kejadian yang tidak ada di masukan.
- Kanal pelaporan hanya dari daftar ini: {"; ".join(CHANNELS)}.
- Ikuti sudut pandang alur: D1 = hasil mesin dari berita; D2 = pendapat publik dari survei; D3 = keputusan lembaga; D4 = catatan resmi lembaga.
  Bila publik atau lembaga menyatakan informasinya tidak benar (hoaks), fokuskan saran pada cek fakta dan jangan menyebarkan.
Jawab hanya dengan JSON sesuai skema."""

_STRINGS = {"type": "array", "items": {"type": "string"}}
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ringkasan", "sasaran", "materi", "langkah", "kanal", "pesan_kunci"],
    "properties": {
        "ringkasan": {"type": "string"},
        "sasaran": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kelompok", "usia", "wilayah", "alasan"],
                "properties": {
                    "kelompok": {"type": "string"},
                    "usia": {"type": "string"},
                    "wilayah": {"type": "string"},
                    "alasan": {"type": "string"},
                },
            },
        },
        "materi": _STRINGS,
        "langkah": _STRINGS,
        "kanal": _STRINGS,
        "pesan_kunci": {"type": "string"},
    },
}
LIMITS = {"sasaran": 3, "materi": 4, "langkah": 5, "kanal": 3}

FLOW_VIEW = {
    "D1": "D1 (mesin): saran berdasarkan isi berita dan hasil ekstraksi mesin saja.",
    "D2": "D2 (publik): saran yang memperhitungkan penilaian publik di survei, termasuk koreksi dan pendapat apakah kejadian ini benar.",
    "D3": "D3 (lembaga): saran yang memperhitungkan keputusan lembaga resmi, alasan, koreksi, dan imbauannya.",
    "D4": "D4 (catatan resmi): saran resmi berdasarkan catatan lembaga yang sudah dikonfirmasi atau dibantah.",
}


# --- Pengaturan ---
def settings():
    return {
        "base_url": (os.environ.get("AI_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
        "api_key": os.environ.get("AI_API_KEY") or "",
        "model": os.environ.get("AI_MODEL") or "",
        "max_calls": int(os.environ.get("AI_MAX_CALLS") or DEFAULT_MAX_CALLS),
    }


def configured():
    config = settings()
    return bool(config["api_key"] and config["model"])


def make_client():
    config = settings()
    return LLMClient(base_url=config["base_url"], api_key=config["api_key"], model=config["model"], no_think=False, timeout=180)


# --- Tabel ---
def create_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_prevention (
            incident_id TEXT NOT NULL, flow TEXT NOT NULL, input_hash TEXT NOT NULL,
            model TEXT NOT NULL, prompt_version TEXT NOT NULL, output TEXT NOT NULL,
            created_at TEXT NOT NULL, PRIMARY KEY (incident_id, flow)
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_region_literacy (
            province_code TEXT PRIMARY KEY, province TEXT NOT NULL, input_hash TEXT NOT NULL,
            model TEXT NOT NULL, prompt_version TEXT NOT NULL, output TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_top (
            rank INTEGER PRIMARY KEY, incident_id TEXT NOT NULL, score REAL NOT NULL, computed_at TEXT NOT NULL
        )""")
    conn.commit()


def _has(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None


def _hash(payload):
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()[:24]


def _loads(value):
    try:
        parsed = json.loads(value) if value else {}
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


# --- Incident terbesar ---
def top_incidents(conn, n=TOP_N, days=TOP_DAYS):
    """[(incident_id, skor)] terbesar dalam ``days`` hari terakhir data (bukan jam dinding)."""
    latest = conn.execute("SELECT MAX(last_published_date) FROM v05_incidents").fetchone()[0]
    if not latest:
        return []
    since = (datetime.fromisoformat(latest[:10]) - timedelta(days=days)).date().isoformat()
    domains = "COALESCE(t.domain_count, 0)" if _has(conn, "v07_trust") else "0"
    join = "LEFT JOIN v07_trust t ON t.incident_id = i.incident_id" if _has(conn, "v07_trust") else ""
    rows = conn.execute(
        f"""SELECT i.incident_id, i.document_count + 2 * {domains} AS score
            FROM v05_incidents i {join}
            WHERE i.last_published_date >= ? AND i.document_count >= 2
            ORDER BY score DESC, i.incident_id LIMIT ?""",
        (since, n),
    ).fetchall()
    return [(incident_id, float(score)) for incident_id, score in rows]


# --- Masukan per alur ---
def _article(conn, column):
    """``a.<kolom>`` bila kolom ada di tabel articles, selain itu NULL (database uji ringkas)."""
    have = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
    return f"a.{column}" if column in have else "NULL"


def _news(conn, incident_id, limit=5):
    cols = ", ".join(_article(conn, c) for c in ("title", "summary", "published_date", "source_name"))
    order = "a.published_date" if _article(conn, "published_date") != "NULL" else "a.article_id"
    rows = conn.execute(
        f"""SELECT {cols} FROM v05_incident_documents d JOIN articles a ON a.article_id = d.article_id
            WHERE d.incident_id = ? ORDER BY {order} LIMIT ?""",
        (incident_id, limit),
    ).fetchall()
    return [{"judul": t, "ringkasan": (s or "")[:400], "tanggal": (p or "")[:10], "sumber": src} for t, s, p, src in rows]


def _context(conn, incident_id):
    context = {}
    for table, column, key in (
        ("incident_regions", "province", "wilayah_indonesia"),
        ("incident_communities", "audience", "kelompok_disebut"),
        ("incident_platforms", "platform", "platform_disebut"),
    ):
        if _has(conn, table):
            values = [row[0] for row in conn.execute(f"SELECT DISTINCT {column} FROM {table} WHERE incident_id = ?", (incident_id,))]
            if values:
                context[key] = values
    return context


CARD_FIELDS = ("attack_type", "target", "threat_actor", "attack_date", "location", "target_group")


def flow_inputs(conn, incident_id, latest):
    """{alur: masukan} untuk alur yang punya keluaran pada incident ini."""
    d1 = latest["D1"].get(incident_id)
    if d1 is None:
        return {}
    card = {field: d1.get(field) for field in CARD_FIELDS}
    base = {
        "incident": {
            "kartu": card,
            "trust_mesin": d1.get("status"),
            "berita": _news(conn, incident_id),
            **_context(conn, incident_id),
        }
    }
    inputs = {"D1": base}
    d2 = latest["D2"].get(incident_id)
    if d2:
        basis = _loads(d2.get("basis"))
        inputs["D2"] = {
            **base,
            "survei_publik": {
                "status": d2.get("status"),
                "penilaian_per_kolom": _loads(d2.get("field_status")),
                "koreksi_publik": basis.get("corrections") or {},
                "pendapat_benar_terjadi": basis.get("verdict") or "belum_pasti",
                "jumlah_jawaban": basis.get("responses"),
                "jumlah_responden": basis.get("respondents"),
            },
        }
    for flow in ("D3", "D4"):
        row = latest[flow].get(incident_id)
        if not row:
            continue
        basis = _loads(row.get("basis"))
        plan = _loads(row.get("prevention"))
        inputs[flow] = {
            **base,
            "keputusan_lembaga": {
                "lembaga": basis.get("institution"),
                "status": row.get("status"),
                "alasan": row.get("reason"),
                "penilaian_per_kolom": _loads(row.get("field_status")),
                "nilai_menurut_lembaga": {field: row.get(field) for field in CARD_FIELDS if row.get(field) != card.get(field)},
                "imbauan_lembaga": plan.get("text"),
                "sasaran_dipilih_lembaga": plan.get("audience") or [],
                "materi_dipilih_lembaga": plan.get("topics") or [],
                "catatan_resmi": flow == "D4",
            },
        }
    return inputs


def _latest_outputs(conn):
    latest = {flow: {} for flow in FLOWS}
    if not _has(conn, "flow_outputs"):
        return latest
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT o.* FROM flow_outputs o
               JOIN (SELECT incident_id, flow, MAX(output_id) AS last_id FROM flow_outputs GROUP BY incident_id, flow) m
                 ON m.last_id = o.output_id"""
        ).fetchall()
    finally:
        conn.row_factory = None
    for row in rows:
        if row["status"] == flows.REMOVED:
            continue
        # D2 "belum" (kolom belum diputuskan) tetap berguna bila publik sudah menjawab "benar terjadi?"
        if row["status"] == flows.PENDING and row["flow"] != "D2":
            continue
        latest[row["flow"]][row["incident_id"]] = dict(row)
    return latest


# --- Panggilan model ---
def clean_output(raw):
    """Rapikan jawaban model ke skema tetap (tipe dan batas jumlah item)."""
    out = {"ringkasan": str(raw.get("ringkasan") or "").strip(), "pesan_kunci": str(raw.get("pesan_kunci") or "").strip()}
    targets = []
    for item in raw.get("sasaran") or []:
        if isinstance(item, dict) and str(item.get("kelompok") or "").strip():
            targets.append({key: str(item.get(key) or "").strip() for key in ("kelompok", "usia", "wilayah", "alasan")})
    out["sasaran"] = targets[: LIMITS["sasaran"]]
    for key in ("materi", "langkah", "kanal"):
        out[key] = [str(v).strip() for v in raw.get(key) or [] if str(v).strip()][: LIMITS[key]]
    return out


def generate(client, task, payload, max_tokens=1200):
    user = f"{task}\n\nMasukan (JSON):\n{json.dumps(payload, ensure_ascii=False, indent=1)}"
    raw, _usage = client.chat_json(SYSTEM, user, OUTPUT_SCHEMA, name="saran_literasi", temperature=0.2, max_tokens=max_tokens)
    return clean_output(raw)


def _province_inputs(conn, top_titles):
    """{kode provinsi: (masukan, hash)} dari profil wilayah, kasus lokal 90 hari, dan incident terbesar."""
    from csais.regions import WILAYAH, province_name

    with open(os.path.join(PROJECT_ROOT, "web", "lib", "region-profiles.json"), encoding="utf-8") as fh:
        profiles = json.load(fh)
    local = {}
    if _has(conn, "incident_regions"):
        latest = conn.execute("SELECT MAX(last_published_date) FROM v05_incidents").fetchone()[0] or "0000"
        since = (datetime.fromisoformat(latest[:10]) - timedelta(days=90)).date().isoformat() if latest != "0000" else "0000"
        for code, incident_id, title, attack_type, docs in conn.execute(
            f"""SELECT DISTINCT r.province_code, r.incident_id, {_article(conn, 'title')}, i.attack_type, i.document_count
               FROM incident_regions r JOIN v05_incidents i ON i.incident_id = r.incident_id
               LEFT JOIN articles a ON a.article_id = i.anchor_article_id
               WHERE i.last_published_date >= ? ORDER BY i.document_count DESC""",
            (since,),
        ):
            local.setdefault(code, []).append((incident_id, {"judul": title, "jenis": attack_type, "artikel": docs}))
    result = {}
    for code in WILAYAH["provinsi"]:
        traits = [
            {"ciri": profiles["traits"][t]["label"]["id"], "alasan": profiles["traits"][t]["reason"]["id"]}
            for t in profiles["provinces"].get(code, [])
        ]
        cases = local.get(code, [])[:6]
        payload = {
            "provinsi": province_name(code),
            "profil_wilayah": traits,
            "kasus_lokal_90_hari": [case for _, case in cases],
            "incident_terbesar_nasional_dan_global": top_titles,
        }
        result[code] = (payload, _hash({"v": PROMPT_VERSION, "traits": traits, "local": [i for i, _ in cases]}))
    return result


def store_top(conn, now=None):
    """Simpan peringkat incident terbesar saat ini ke ai_top (tanpa AI); kembalikan daftarnya."""
    create_tables(conn)
    top = top_incidents(conn, TOP_N)
    conn.execute("DELETE FROM ai_top")
    conn.executemany("INSERT INTO ai_top VALUES (?, ?, ?, ?)", [(i + 1, iid, score, now or get_timestamp()) for i, (iid, score) in enumerate(top)])
    conn.commit()
    return top


def run_ai(conn, client, model, max_calls=DEFAULT_MAX_CALLS, now=None, log=print):
    """Perbarui peringkat dan saran AI; kembalikan (permintaan dibuat, gagal)."""
    now = now or get_timestamp()
    top = store_top(conn, now)
    latest = _latest_outputs(conn)
    known = {(r[0], r[1]): r[2] for r in conn.execute("SELECT incident_id, flow, input_hash FROM ai_prevention")}
    calls = failed = 0

    def call(task, payload):
        nonlocal calls, failed
        calls += 1
        try:
            return generate(client, task, payload)
        except (LLMError, ValueError, KeyError) as error:
            failed += 1
            log(f"   ⚠️ AI gagal: {str(error)[:160]}")
            return None

    for incident_id, _score in top:
        for flow, payload in flow_inputs(conn, incident_id, latest).items():
            digest = _hash({"v": PROMPT_VERSION, "model": model, "flow": flow, "input": payload})
            if known.get((incident_id, flow)) == digest:
                continue
            if calls >= max_calls:
                log(f"   batas {max_calls} permintaan tercapai; sisanya run berikutnya")
                return calls, failed
            output = call(f"Sudut pandang alur: {FLOW_VIEW[flow]}", payload)
            if output is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO ai_prevention VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (incident_id, flow, digest, model, PROMPT_VERSION, json.dumps(output, ensure_ascii=False), now),
                )
                conn.commit()

    titles = [r[0] for r in conn.execute(
        f"SELECT {_article(conn, 'title')} FROM ai_top t JOIN v05_incidents i ON i.incident_id = t.incident_id "
        f"LEFT JOIN articles a ON a.article_id = i.anchor_article_id ORDER BY t.rank LIMIT {TOP_N}"
    )]
    stored = {r[0]: (r[1], r[2]) for r in conn.execute("SELECT province_code, input_hash, created_at FROM ai_region_literacy")}
    stale_before = (datetime.fromisoformat(now.replace("Z", "+00:00")) - timedelta(days=REGION_MAX_AGE_DAYS)).isoformat()
    for code, (payload, digest) in _province_inputs(conn, titles).items():
        previous = stored.get(code)
        if previous and previous[0] == digest and previous[1] >= stale_before:
            continue
        if calls >= max_calls:
            log(f"   batas {max_calls} permintaan tercapai; provinsi lain run berikutnya")
            break
        task = (
            "Tulis rekomendasi literasi untuk satu PROVINSI di Indonesia: siapa yang paling perlu diedukasi di provinsi ini "
            "(spesifik kelompok dan konteks lokalnya), materi, langkah, dan pesan kunci. Gunakan profil wilayah, kasus lokal, "
            "dan incident terbesar yang modusnya bisa terjadi di provinsi ini. Isi 'wilayah' dengan kabupaten/kota bila relevan."
        )
        output = call(task, payload)
        if output is not None:
            conn.execute(
                "INSERT OR REPLACE INTO ai_region_literacy VALUES (?, ?, ?, ?, ?, ?, ?)",
                (code, payload["provinsi"], digest, model, PROMPT_VERSION, json.dumps(output, ensure_ascii=False), now),
            )
            conn.commit()
    return calls, failed


def run():
    print("\n==================================================")
    print("   SARAN PREVENTIF AI (D1 - D4 DAN PETA LITERASI)")
    print("==================================================")
    if not configured():
        # peringkat tetap diperbarui: daftar 10 terbesar dan prioritas survei/portal tidak butuh AI
        conn = get_connection()
        try:
            top = store_top(conn)
        finally:
            conn.close()
        print(f"Incident terbesar    : {len(top)}")
        print("AI_API_KEY dan AI_MODEL belum diisi; saran AI dilewati.")
        return
    config = settings()
    started_at = get_timestamp()
    conn = get_connection()
    try:
        calls, failed = run_ai(conn, make_client(), config["model"], config["max_calls"])
        record_run(conn, "ai_prevention", started_at, calls - failed, notes=f"model={config['model']}")
        top = conn.execute("SELECT COUNT(*) FROM ai_top").fetchone()[0]
        flows_done = conn.execute("SELECT COUNT(*) FROM ai_prevention WHERE incident_id IN (SELECT incident_id FROM ai_top)").fetchone()[0]
        regions = conn.execute("SELECT COUNT(*) FROM ai_region_literacy").fetchone()[0]
    finally:
        conn.close()
    print(f"Model                : {config['model']}")
    print(f"Permintaan / gagal   : {calls} / {failed}")
    print(f"Incident terbesar    : {top} (saran alur tersedia: {flows_done})")
    print(f"Provinsi bersaran AI : {regions} / 38")
    print("==================================================")


if __name__ == "__main__":
    run()
