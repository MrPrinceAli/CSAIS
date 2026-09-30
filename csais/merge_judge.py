"""#21: gabungkan incident yang sebenarnya satu kejadian, dinilai LLM per pasangan.

Kandidat datang dari ``incident_links`` (csais/related.py) yang ditandai
``same_event``: kemiripan makna tinggi dan waktunya berdekatan, termasuk lintas
bahasa. Kemiripan saja tidak cukup (penipuan serupa di dua kota berbeda juga
mirip), jadi setiap pasangan dinilai LLM lokal:

  lokal:    ``main.py --judge-merges`` membaca pasangan dan teks kedua incident
            dari Turso, meminta LLM memutuskan (sama / tidak, keyakinan, alasan),
            lalu menulis ``merge_decisions`` ke database masukan;
  pipeline: V0.5 memanggil ``apply_judged_merges`` setelah chaining: pasangan
            yang dinyatakan sama dengan keyakinan >= MIN_CONFIDENCE digabung
            (union-find, incident paling awal menjadi induk), memakai
            ``merge_incident`` yang sama dengan chaining.
"""

import json
import os
import time

from csais import llm
from csais.db import get_timestamp

PROMPT_VERSION = "merge-judge-v1"
MIN_CONFIDENCE = 0.7
METHOD = "LLM_MERGED"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["same_event", "confidence", "reason"],
    "properties": {
        "same_event": {"type": "boolean"},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
}

SYSTEM_PROMPT = """Anda menilai apakah dua kelompok berita melaporkan KEJADIAN siber yang sama.
Sama: korban atau sasaran yang sama DAN serangan, kebocoran, penipuan, atau penindakan yang sama; termasuk berita lanjutan, bahasa berbeda, atau sudut pandang berbeda atas kejadian itu.
Berbeda: korban berbeda walaupun jenis serangannya sama (penipuan serupa di kota lain, ransomware kelompok yang sama ke korban lain); laporan berkala atau statistik umum (laporan bulanan, tren); imbauan umum yang tidak menyebut kejadian tertentu.
Bila ragu, jawab false dengan keyakinan rendah.
confidence: 0 sampai 1. reason: satu kalimat pendek dalam bahasa Indonesia.
Jawab hanya dengan JSON sesuai skema."""

DECISIONS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS merge_decisions (
        incident_a TEXT NOT NULL,
        incident_b TEXT NOT NULL,
        same_event INTEGER NOT NULL,
        confidence REAL NOT NULL,
        reason TEXT,
        similarity REAL,
        model TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (incident_a, incident_b, model, prompt_version)
    )
"""
DECISION_COLUMNS = ("incident_a", "incident_b", "same_event", "confidence", "reason", "similarity", "model", "prompt_version", "created_at")


def user_prompt(a, b):
    return f"Kelompok A ({a['published'] or '-'}):\n{a['text']}\n\nKelompok B ({b['published'] or '-'}):\n{b['text']}"


def judge(client, a, b):
    """(same_event, keyakinan, alasan) untuk satu pasangan."""
    raw, _ = client.chat_json(SYSTEM_PROMPT, user_prompt(a, b), SCHEMA, name="merge_judge", max_tokens=300)
    try:
        confidence = min(1.0, max(0.0, float(raw.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    return bool(raw.get("same_event")), round(confidence, 3), str(raw.get("reason") or "")[:300]


# --- Lokal ---
def candidate_pairs():
    """Pasangan unik (a < b) berlabel same_event dari database masukan, dengan kemiripannya."""
    from csais.related import LINKS_SQL
    from csais.survey import fetch_rows

    pairs = {}
    for incident_id, related_id, similarity, same_event, *_ in fetch_rows(LINKS_SQL) or []:
        if not int(same_event or 0):  # Turso mengirim angka sebagai teks ("0")
            continue
        key = tuple(sorted((incident_id, related_id)))
        pairs[key] = max(pairs.get(key, 0.0), float(similarity))
    return pairs


def judged_pairs(model):
    from csais.survey import fetch_rows

    safe = model.replace("'", "")
    rows = fetch_rows(
        f"SELECT incident_a, incident_b FROM merge_decisions WHERE model = '{safe}' AND prompt_version = '{PROMPT_VERSION}'"
    )
    return {(a, b) for a, b in rows or []}


def store_decisions(rows):
    from csais.publish import TursoClient

    url = (os.environ.get("SURVEY_DATABASE_URL") or "").strip()
    insert = f"INSERT OR REPLACE INTO merge_decisions ({', '.join(DECISION_COLUMNS)}) VALUES ({', '.join('?' for _ in DECISION_COLUMNS)})"
    if url.startswith("file:"):
        import sqlite3

        conn = sqlite3.connect(url[len("file:"):])
        conn.execute(DECISIONS_SCHEMA)
        conn.executemany(insert, rows)
        conn.commit()
        conn.close()
        return
    token = os.environ.get("SURVEY_WRITE_TOKEN")
    if not url or not token:
        raise SystemExit("SURVEY_DATABASE_URL dan SURVEY_WRITE_TOKEN harus diisi")
    statements = [(DECISIONS_SCHEMA, [])] + [(insert, list(r)) for r in rows]
    for attempt in range(3):
        try:
            TursoClient(url, token).execute(statements)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))


def run_local(limit=0, client=None, log=print):
    """Nilai pasangan yang belum dinilai model dan versi prompt ini; kembalikan jumlah keputusan."""
    from csais import related

    client = client or llm.LLMClient()
    model = client.config["model"]
    pairs = candidate_pairs()
    done = judged_pairs(model)
    pending = sorted((p for p in pairs if p not in done), key=lambda p: -pairs[p])
    if limit:
        pending = pending[:limit]
    log(f"Pasangan kejadian sama: {len(pairs)}, sudah dinilai: {len(done)}, akan dinilai: {len(pending)}")
    if not pending:
        return 0
    needed = {i for pair in pending for i in pair}
    items = related.incident_texts(related._paged(related.INCIDENTS_SQL), related._paged(related.DOCS_SQL))
    items = {k: v for k, v in items.items() if k in needed}
    batch, saved, same = [], 0, 0
    for index, (a, b) in enumerate(pending, start=1):
        if a not in items or b not in items:
            continue  # incident sudah tidak ada (tergabung atau dikelompokkan ulang)
        try:
            verdict, confidence, reason = judge(client, items[a], items[b])
        except (llm.LLMError, OSError) as error:
            log(f"   ⚠️ {a} / {b}: {error}")
            continue
        same += verdict
        batch.append((a, b, int(verdict), confidence, reason, round(pairs[(a, b)], 4), model, PROMPT_VERSION, get_timestamp()))
        if len(batch) >= 25 or index == len(pending):
            try:
                store_decisions(batch)
            except Exception as error:
                log(f"   ⚠️ gagal menyimpan {len(batch)} keputusan, dicoba lagi nanti: {error}")
                continue
            saved += len(batch)
            batch = []
            log(f"   {index}/{len(pending)} dinilai, {same} dinyatakan sama")
    if batch:
        store_decisions(batch)
        saved += len(batch)
    log(f"Keputusan tersimpan: {saved} ({same} sama). Digabung pada run pipeline berikutnya.")
    return saved


# --- Pipeline (dipanggil V0.5) ---
DECISIONS_SQL = f"""
    SELECT incident_a, incident_b, confidence FROM merge_decisions
    WHERE same_event = 1 AND confidence >= {MIN_CONFIDENCE}
"""


def merge_groups(pairs):
    """Union-find: kelompok incident yang saling terhubung lewat keputusan 'sama'."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a
    groups = {}
    for x in list(parent):
        groups.setdefault(find(x), set()).add(x)
    return [g for g in groups.values() if len(g) > 1]


def apply_judged_merges(conn, rows=None, log=print):
    """Gabungkan incident yang dinyatakan sama oleh LLM; kembalikan jumlah incident yang diserap."""
    from csais import v05_incident_clustering as v05

    if rows is None:
        from csais.survey import fetch_rows

        try:
            rows = fetch_rows(DECISIONS_SQL)
        except Exception as error:  # jaringan: jangan gagalkan V0.5
            log(f"   ⚠️ merge_decisions tidak terbaca: {error}")
            return 0
    if not rows:
        return 0
    cursor = conn.execute(v05._INCIDENT_SELECT)
    incidents = {row[0]: dict(zip(v05.INCIDENT_COLUMNS, row)) for row in cursor.fetchall()}
    pairs = [(a, b) for a, b, _ in rows if a in incidents and b in incidents]
    absorbed = 0
    for group in merge_groups(pairs):
        members = sorted(group, key=lambda i: (incidents[i]["anchor_published_date"] or "9999", i))
        head = incidents[members[0]]
        for other_id in members[1:]:
            v05.merge_incident(conn, head, incidents[other_id], method=METHOD)
            absorbed += 1
    conn.commit()
    return absorbed


def summarize(rows):
    """Ringkasan keputusan untuk log: (sama, beda)."""
    same = sum(1 for r in rows if r[2])
    return same, len(rows) - same


if __name__ == "__main__":
    print(json.dumps({"prompt": PROMPT_VERSION, "min_confidence": MIN_CONFIDENCE}))
