"""Ekstraksi informasi dengan LLM lokal (LM Studio) sebagai pelengkap V0.3.

Alurnya dibagi dua, karena LLM berjalan di komputer lokal sedangkan pipeline
harian berjalan di GitHub Actions:

  1. lokal: ``main.py --llm-extract`` mengambil artikel incident dari Turso
     (judul dan ringkasan), meminta LLM mengisi kartu inti dengan skema JSON
     ketat, lalu menulis hasilnya ke tabel ``llm_extractions`` di database
     masukan (csais-survey, token tulis ``SURVEY_WRITE_TOKEN``);
  2. pipeline: tahap ``run()`` (setelah V0.3) menyalin hasil itu ke tabel
     lokal ``v03_llm_extraction``. Bila ``LLM_MERGE=fill_unknown``, kolom
     V0.3 yang kosong (UNKNOWN) diisi dari LLM dan extraction_method menjadi
     ``RULE_BASED+LLM``; nilai hasil aturan tidak pernah ditimpa. Kolom yang
     diisi diatur ``LLM_MERGE_FIELDS`` (default tanpa pelaku). Default
     ``off``: hasil hanya disimpan untuk dibandingkan (eval/score_llm.py).

Setiap hasil diberi ``model`` dan ``prompt_version`` agar hasil model atau
prompt yang berbeda tidak tercampur.
"""

import json
import os
import re

from csais import llm
from csais.config import PROJECT_ROOT
from csais.db import get_connection, get_timestamp
from csais.schema import record_run

PROMPT_VERSION = "llm-extract-v2"
FILL_CONFIDENCE = 0.7  # keyakinan kolom yang diisi LLM (aturan: 0.5 - 1.0)

with open(os.path.join(PROJECT_ROOT, "csais", "data", "extraction_keywords.json"), encoding="utf-8") as _fh:
    _KEYWORDS = json.load(_fh)
ATTACK_TYPES = sorted(set(_KEYWORDS["attack_type_keywords"]) | {"CYBER_ATTACK"})
TARGET_GROUPS = sorted(_KEYWORDS["target_group_keywords"])
_DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["is_incident", "attack_types", "target", "threat_actor", "attack_date", "location", "target_groups", "confidence"],
    "properties": {
        "is_incident": {"type": "boolean"},
        "attack_types": {"type": "array", "items": {"type": "string", "enum": ATTACK_TYPES}, "maxItems": 3},
        "target": {"type": ["string", "null"]},
        "threat_actor": {"type": ["string", "null"]},
        "attack_date": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
        "target_groups": {"type": "array", "items": {"type": "string", "enum": TARGET_GROUPS}, "maxItems": 3},
        "confidence": {"type": "number"},
    },
}

SYSTEM_PROMPT = f"""Anda analis intelijen serangan siber. Dari judul dan ringkasan berita, isi kartu inti incident.
Aturan:
- Isi hanya dari teks yang diberikan. Jangan menebak; pakai null atau [] bila tidak disebut.
- is_incident: true hanya bila berita melaporkan kejadian konkret: serangan, kebocoran, atau penipuan siber yang sudah terjadi pada korban atau pihak tertentu, atau penangkapan/penindakan pelakunya. false untuk imbauan dan peringatan umum ("waspada link video viral berisi phishing", "jangan klik tautan ..."), statistik atau tren ("ratusan ribu malware incar ..."), tips keamanan, opini, ulasan produk, dan berita kebijakan tanpa kejadian tertentu.
- attack_types: 1-3 kategori paling tepat dari daftar: {", ".join(ATTACK_TYPES)}. Pakai CYBER_ATTACK hanya bila jenisnya tidak jelas.
- target: nama organisasi atau pihak yang menjadi korban, seperti tertulis (misalnya "Bank Syariah Indonesia"). null bila korban umum atau tidak disebut.
- threat_actor: nama kelompok atau pelaku yang disebut (misalnya "LockBit"). null bila tidak disebut; jangan isi dengan kata umum seperti "hacker".
- attack_date: tanggal kejadian YYYY-MM-DD (atau YYYY-MM / YYYY) hanya bila disebut jelas; bukan tanggal terbit.
- location: negara korban dalam bahasa Inggris huruf kecil (misalnya "indonesia"), null bila tidak jelas.
- target_groups: 0-3 kelompok sasaran dari daftar: {", ".join(TARGET_GROUPS)}.
- confidence: 0 sampai 1, keyakinan Anda terhadap kartu ini.
Jawab hanya dengan JSON sesuai skema."""


def user_prompt(title, summary):
    return f"Judul: {title or '-'}\nRingkasan: {summary or '-'}"


def _text(value, limit=120):
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text or text.lower() in ("null", "none", "unknown", "-", "n/a"):
        return None
    return text[:limit]


def normalize(result):
    """Rapikan jawaban model: kategori yang dikenal saja, tanggal dan negara yang wajar."""
    types = [str(t).upper() for t in (result.get("attack_types") or []) if str(t).upper() in ATTACK_TYPES]
    groups = [str(g).upper() for g in (result.get("target_groups") or []) if str(g).upper() in TARGET_GROUPS]
    date = _text(result.get("attack_date"), 10)
    location = _text(result.get("location"), 60)
    try:
        confidence = min(1.0, max(0.0, float(result.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "is_incident": bool(result.get("is_incident")),
        "attack_type": ", ".join(dict.fromkeys(types[:3])) or None,
        "target": _text(result.get("target")),
        "threat_actor": _text(result.get("threat_actor"), 80),
        "attack_date": date if date and _DATE.match(date) else None,
        "location": location.lower() if location else None,
        "target_group": ", ".join(dict.fromkeys(groups[:3])) or None,
        "confidence": round(confidence, 3),
    }


def extract(client, title, summary):
    """Kartu inti dari satu artikel: (hasil ternormalisasi, JSON mentah)."""
    raw, _ = client.chat_json(SYSTEM_PROMPT, user_prompt(title, summary), SCHEMA)
    return normalize(raw), raw


# --- Database masukan ---
LLM_SCHEMA = """
    CREATE TABLE IF NOT EXISTS llm_extractions (
        article_uid TEXT NOT NULL,
        model TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        is_incident INTEGER,
        attack_type TEXT,
        target TEXT,
        threat_actor TEXT,
        attack_date TEXT,
        location TEXT,
        target_group TEXT,
        confidence REAL,
        raw TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (article_uid, model, prompt_version)
    )
"""
LLM_COLUMNS = (
    "article_uid", "model", "prompt_version", "is_incident", "attack_type", "target", "threat_actor",
    "attack_date", "location", "target_group", "confidence", "raw", "created_at",
)
LLM_SQL = f"SELECT {', '.join(LLM_COLUMNS)} FROM llm_extractions"
CANDIDATES_SQL = """
    SELECT a.article_uid, a.title, a.summary
    FROM articles a JOIN v05_incident_documents d ON d.article_id = a.article_id
    WHERE a.article_uid IS NOT NULL
    ORDER BY (a.language = 'id') DESC, a.published_date DESC
    LIMIT ?
"""


def _input_url():
    url = (os.environ.get("SURVEY_DATABASE_URL") or "").strip()
    if not url:
        raise ValueError("SURVEY_DATABASE_URL belum diisi")
    return url


def done_uids(model):
    """article_uid yang sudah diekstrak model dan versi prompt ini."""
    from csais.survey import fetch_rows

    safe = model.replace("'", "")  # fetch_rows tanpa parameter; nama model dari .env sendiri
    rows = fetch_rows(f"SELECT article_uid FROM llm_extractions WHERE model = '{safe}' AND prompt_version = '{PROMPT_VERSION}'")
    return {row[0] for row in rows or []}


def candidates(limit):
    """Artikel incident dari database terbit (Turso), Indonesia dan terbaru lebih dulu."""
    from csais.publish import TursoClient
    from csais.survey import _hrana_value

    url = os.environ.get("TURSO_DATABASE_URL") or ""
    if url.startswith("file:"):
        import sqlite3

        conn = sqlite3.connect(url[len("file:"):])
        try:
            return conn.execute(CANDIDATES_SQL, (limit,)).fetchall()
        finally:
            conn.close()
    client = TursoClient(url, os.environ.get("TURSO_AUTH_TOKEN"))
    result = client.execute([(CANDIDATES_SQL, [limit])])[0]["response"]["result"]
    return [tuple(_hrana_value(cell) for cell in row) for row in result["rows"]]


def store_rows(rows):
    """Tulis hasil ekstraksi ke database masukan."""
    url = _input_url()
    insert = f"INSERT OR REPLACE INTO llm_extractions ({', '.join(LLM_COLUMNS)}) VALUES ({', '.join('?' for _ in LLM_COLUMNS)})"
    values = [[row[c] for c in LLM_COLUMNS] for row in rows]
    if url.startswith("file:"):
        import sqlite3

        conn = sqlite3.connect(url[len("file:"):])
        conn.execute(LLM_SCHEMA)
        conn.executemany(insert, values)
        conn.commit()
        conn.close()
        return
    from csais.publish import TursoClient

    token = os.environ.get("SURVEY_WRITE_TOKEN")
    if not token:
        raise ValueError("SURVEY_WRITE_TOKEN (token tulis database masukan) belum diisi")
    TursoClient(url, token).execute([(LLM_SCHEMA, [])] + [(insert, v) for v in values])


def run_local(limit=100, client=None, log=print):
    """Ekstrak sampai ``limit`` artikel baru dengan LLM lokal; kembalikan jumlah yang tersimpan."""
    client = client or llm.LLMClient()
    model = client.config["model"]
    done = done_uids(model)
    pending = [row for row in candidates(limit * 4) if row[0] not in done][:limit]
    log(f"Model {model}, prompt {PROMPT_VERSION}: {len(pending)} artikel akan diekstrak ({len(done)} sudah ada).")
    batch, saved, failed = [], 0, 0
    for index, (uid, title, summary) in enumerate(pending, start=1):
        try:
            result, raw = extract(client, title, summary)
        except (llm.LLMError, OSError) as error:
            failed += 1
            log(f"   ⚠️ {uid}: {error}")
            continue
        batch.append({
            "article_uid": uid, "model": model, "prompt_version": PROMPT_VERSION, **result,
            "is_incident": int(result["is_incident"]), "raw": json.dumps(raw, ensure_ascii=False)[:4000],
            "created_at": get_timestamp(),
        })
        if len(batch) >= 20 or index == len(pending):
            store_rows(batch)
            saved += len(batch)
            batch = []
            log(f"   {index}/{len(pending)} diproses")
    if batch:
        store_rows(batch)
        saved += len(batch)
    log(f"Tersimpan {saved}, gagal {failed}. Hasil dipakai pipeline pada run harian berikutnya.")
    return saved


def run_check(client=None, log=print):
    """Periksa koneksi LM Studio dan coba satu ekstraksi contoh."""
    client = client or llm.LLMClient()
    log(f"Server : {client.config['base_url']}")
    log(f"Model  : {client.config['model']}")
    models = client.models()
    log(f"Model dimuat server: {', '.join(models) or '(tidak ada)'}")
    if client.config["model"] not in models:
        log("   ⚠️ LLM_MODEL tidak ada di daftar; periksa nama model di LM Studio.")
    title = "Bank Syariah Indonesia Diserang Ransomware LockBit, Layanan Sempat Lumpuh - Kompas.com"
    summary = "Kelompok LockBit mengklaim mencuri 1,5 TB data nasabah BSI pada 8 Mei 2023."
    result, raw = extract(client, title, summary)
    log("Contoh ekstraksi:")
    log(json.dumps(result, ensure_ascii=False, indent=2))
    return result


# --- Tahap pipeline ---
def create_tables(conn):
    conn.execute(LLM_SCHEMA.replace("llm_extractions", "v03_llm_extraction"))
    conn.commit()


def store_local(conn, rows):
    """Ganti isi v03_llm_extraction dengan hasil dari database masukan."""
    create_tables(conn)
    conn.execute("DELETE FROM v03_llm_extraction")
    conn.executemany(
        f"INSERT OR REPLACE INTO v03_llm_extraction ({', '.join(LLM_COLUMNS)}) VALUES ({', '.join('?' for _ in LLM_COLUMNS)})",
        rows,
    )
    conn.commit()


_FILL_FIELDS = ("attack_type", "target", "threat_actor", "attack_date", "location", "target_group")
# Kolom yang diisi LLM_MERGE=fill_unknown. Pelaku tidak termasuk secara default:
# pada uji penuh (eval/SCORES.md, 29 Sep 2026) aturan lebih tepat untuk pelaku
# (F1 0,61 vs 0,40 en), sedangkan LLM jauh lebih baik untuk korban (0,32 vs 0,73 en).
DEFAULT_MERGE_FIELDS = ("attack_type", "target", "attack_date", "location", "target_group")


def merge_fields():
    raw = os.environ.get("LLM_MERGE_FIELDS")
    if not raw:
        return DEFAULT_MERGE_FIELDS
    return tuple(f.strip() for f in raw.split(",") if f.strip() in _FILL_FIELDS)


def _unknown(value, field):
    if value is None or str(value).strip() in ("", "UNKNOWN"):
        return True
    return field == "attack_type" and str(value).strip().upper() == "CYBER_ATTACK"


def fill_unknown(conn, fields=None):
    """Isi kolom V0.3 yang kosong dari hasil LLM terbaru per artikel; kembalikan jumlah artikel yang berubah."""
    fields = fields or merge_fields()
    rows = conn.execute(
        f"""
        SELECT x.article_id, {", ".join(f"x.{f}" for f in _FILL_FIELDS)}, x.field_confidence, x.extraction_method,
               {", ".join(f"l.{f}" for f in _FILL_FIELDS)}
        FROM v03_information_extraction x
        JOIN articles a ON a.article_id = x.article_id
        JOIN (SELECT article_uid, MAX(created_at) AS latest FROM v03_llm_extraction GROUP BY article_uid) m
          ON m.article_uid = a.article_uid
        JOIN v03_llm_extraction l ON l.article_uid = m.article_uid AND l.created_at = m.latest
        WHERE l.is_incident = 1
        """
    ).fetchall()
    changed = 0
    n = len(_FILL_FIELDS)
    for row in rows:
        article_id, rule, confidence_json, method, model_values = row[0], row[1 : 1 + n], row[1 + n], row[2 + n], row[3 + n :]
        try:
            confidence = json.loads(confidence_json or "{}")
        except ValueError:
            confidence = {}
        updates = {}
        for field, current, proposed in zip(_FILL_FIELDS, rule, model_values):
            if field in fields and proposed and _unknown(current, field) and proposed != current:
                updates[field] = proposed
                confidence[field] = FILL_CONFIDENCE
        if not updates:
            continue
        sets = ", ".join(f"{field} = ?" for field in updates)
        new_method = method if method and "LLM" in method else f"{method or 'RULE_BASED'}+LLM"
        conn.execute(
            f"UPDATE v03_information_extraction SET {sets}, field_confidence = ?, extraction_method = ? WHERE article_id = ?",
            [*updates.values(), json.dumps(confidence), new_method, article_id],
        )
        changed += 1
    conn.commit()
    return changed


def run():
    """Tahap pipeline: ambil hasil LLM dari database masukan; isi kolom kosong bila diaktifkan."""
    from csais.survey import fetch_rows

    print("\n==================================================")
    print("   V0.3 LLM - HASIL EKSTRAKSI LLM LOKAL")
    print("==================================================")
    rows = fetch_rows(LLM_SQL)
    if rows is None:
        print("SURVEY_DATABASE_URL belum diisi; tahap dilewati.")
        return
    mode = (os.environ.get("LLM_MERGE") or "off").strip().lower()
    started_at = get_timestamp()
    conn = get_connection()
    try:
        store_local(conn, rows)
        filled = fill_unknown(conn) if mode == "fill_unknown" else 0
        record_run(conn, "v03_llm", started_at, filled)
    finally:
        conn.close()
    print(f"Hasil LLM dibaca     : {len(rows)}")
    print(f"Mode penggabungan    : {mode}")
    print(f"Artikel diisi LLM    : {filled}")
    print("==================================================")


if __name__ == "__main__":
    run()
