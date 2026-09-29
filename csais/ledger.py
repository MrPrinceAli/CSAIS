"""Ledger bukti sisi off-chain: batch Merkle dari bukti V0.6 dan catatan resmi D4.

Setiap run, bukti yang belum pernah masuk batch dikumpulkan urut evidence_id,
dipotong maksimal ``MAX_LEAVES`` per batch, lalu dihitung akar Merkle-nya.
Yang nanti dijangkarkan ke rantai hanya akar (32 byte) per batch; datanya
tetap di database. Halaman verifikasi menghitung ulang bukti Merkle dari
daun-daun batch itu, jadi ukuran batch dibatasi agar satu permintaan web
cukup membaca sekitar seribu baris.

Batch bersifat tambah-saja: bukti yang sudah masuk batch tidak dihitung
ulang walaupun barisnya di V0.6 berubah. Daun menyimpan salinan (payload)
yang di-hash, sehingga perubahan data setelah batch tetap bisa dideteksi.

Konstruksi pohon (harus sama di web/lib/merkle.ts dan di kontrak):
  daun   = SHA-256(0x00 || payload)
           payload = JSON kanonis: kunci terurut, tanpa spasi, ASCII saja
  simpul = SHA-256(0x01 || min(a, b) || max(a, b))   pasangan diurutkan
  simpul ganjil tanpa pasangan naik ke tingkat berikutnya apa adanya
SHA-256 dipakai (bukan keccak) agar dapat dihitung dengan hashlib, Web
Crypto, dan precompile sha256 di EVM tanpa pustaka tambahan; awalan 0x00/0x01
memisahkan ranah daun dan simpul (gaya RFC 6962).

Catatan resmi D4 (``flow_outputs`` alur D4) dibatch terpisah
(``batch_kind = 'official_record'``) dengan payload ``RECORD_FIELDS``;
``output_hash`` di payload mengikat seluruh isi catatan, termasuk reason
statement lembaga. ID daunnya ``record_uid`` (24 heksadesimal), disimpan di
kolom ``evidence_uid`` agar halaman verifikasi bisa mencari keduanya.
"""

import hashlib
import json

from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import ensure_column, record_run

MAX_LEAVES = 1024
PAYLOAD_FIELDS = (
    "evidence_uid", "incident_id", "article_uid", "article_url", "resolved_url",
    "content_sha256", "content_fingerprint", "publication_date",
    "content_fetched_at", "source_domain", "pipeline_version",
)


RECORD_FIELDS = (
    "kind", "record_uid", "incident_id", "output_id", "output_hash", "status",
    "tier", "source_ref", "supersedes", "recorded_at",
)
EVIDENCE = "evidence"
OFFICIAL_RECORD = "official_record"


# --- Pohon Merkle ---
def canonical_payload(record, fields=PAYLOAD_FIELDS):
    """JSON kanonis (kunci terurut, tanpa spasi, ASCII) dari kamus bukti."""
    payload = {key: record.get(key) for key in fields}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def record_uid(output_id, output_hash):
    """ID deterministik daun catatan resmi D4."""
    raw = f"D4|{output_id}|{output_hash}"
    return hashlib.sha256(raw.encode("ascii")).hexdigest()[:24]


def leaf_hash(payload):
    """Hash daun dari payload (str atau bytes)."""
    if isinstance(payload, str):
        payload = payload.encode("ascii")
    return hashlib.sha256(b"\x00" + payload).digest()


def node_hash(left, right):
    """Hash simpul dari dua anak; urutan anak tidak berpengaruh."""
    low, high = sorted((left, right))
    return hashlib.sha256(b"\x01" + low + high).digest()


def _levels(leaves):
    """Seluruh tingkat pohon, dari daun sampai akar."""
    if not leaves:
        raise ValueError("pohon Merkle tanpa daun")
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        current = levels[-1]
        upper = [node_hash(current[i], current[i + 1]) for i in range(0, len(current) - 1, 2)]
        if len(current) % 2:
            upper.append(current[-1])
        levels.append(upper)
    return levels


def merkle_root(leaves):
    """Akar Merkle (bytes) dari daftar hash daun."""
    return _levels(leaves)[-1][0]


def merkle_proof(leaves, index):
    """Daftar hash saudara (bytes) dari daun ke akar untuk daun ke-``index``."""
    if not 0 <= index < len(leaves):
        raise IndexError(index)
    proof = []
    for level in _levels(leaves)[:-1]:
        sibling = index ^ 1
        if sibling < len(level):
            proof.append(level[sibling])
        index //= 2
    return proof


def verify_proof(leaf, proof, root):
    """True bila daun dan bukti saudaranya menghasilkan akar yang diberikan."""
    current = leaf
    for sibling in proof:
        current = node_hash(current, sibling)
    return current == root


# --- Database ---
def create_tables(conn):
    """Buat tabel batch dan daun bila belum ada."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evidence_batches (
            batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            merkle_root TEXT NOT NULL UNIQUE,
            previous_root TEXT,
            leaf_count INTEGER NOT NULL,
            first_evidence_id INTEGER,
            last_evidence_id INTEGER,
            created_at TEXT NOT NULL,
            pipeline_version TEXT NOT NULL,
            anchor_status TEXT NOT NULL DEFAULT 'PENDING',
            anchor_chain TEXT,
            anchor_tx TEXT,
            anchor_block INTEGER,
            anchored_at TEXT
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evidence_leaves (
            batch_id INTEGER NOT NULL,
            leaf_index INTEGER NOT NULL,
            evidence_uid TEXT NOT NULL UNIQUE,
            leaf_hash TEXT NOT NULL,
            payload TEXT NOT NULL,
            PRIMARY KEY (batch_id, leaf_index)
        )
        """)
    conn.commit()
    # jenis batch: bukti artikel V0.6 atau catatan resmi D4
    ensure_column(conn, "evidence_batches", "batch_kind", f"TEXT NOT NULL DEFAULT '{EVIDENCE}'")


_PENDING_SQL = """
    SELECT e.evidence_id, e.evidence_uid, e.incident_id, a.article_uid,
           a.article_url, a.resolved_url, a.content_sha256, e.content_fingerprint,
           e.publication_date, a.content_fetched_at, e.source_domain,
           e.pipeline_version
    FROM v06_evidence e
    JOIN articles a ON a.article_id = e.article_id
    LEFT JOIN evidence_leaves l ON l.evidence_uid = e.evidence_uid
    WHERE l.evidence_uid IS NULL AND e.evidence_uid IS NOT NULL
    ORDER BY e.evidence_id
"""
_PENDING_KEYS = (
    "evidence_id", "evidence_uid", "incident_id", "article_uid", "article_url",
    "resolved_url", "content_sha256", "content_fingerprint", "publication_date",
    "content_fetched_at", "source_domain", "pipeline_version",
)


def pending_evidence(conn):
    """Bukti V0.6 yang belum masuk batch, sebagai daftar kamus urut evidence_id."""
    cursor = conn.cursor()
    cursor.execute(_PENDING_SQL)
    return [dict(zip(_PENDING_KEYS, row)) for row in cursor.fetchall()]


def latest_root(conn):
    """Akar batch terakhir (heksadesimal) atau None."""
    cursor = conn.cursor()
    cursor.execute("SELECT merkle_root FROM evidence_batches ORDER BY batch_id DESC LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None


_PENDING_RECORDS_SQL = """
    SELECT o.output_id, o.incident_id, o.output_hash, o.status, o.tier, o.source_ref,
           o.supersedes, o.recorded_at
    FROM flow_outputs o
    WHERE o.flow = 'D4'
    ORDER BY o.output_id
"""


def pending_records(conn):
    """Catatan resmi D4 yang belum masuk batch, urut output_id; [] bila tabel belum ada."""
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'flow_outputs'")
    if cursor.fetchone() is None:
        return []
    cursor.execute("SELECT evidence_uid FROM evidence_leaves")
    done = {row[0] for row in cursor.fetchall()}
    records = []
    for output_id, incident_id, digest, status, tier, source_ref, supersedes, recorded_at in cursor.execute(_PENDING_RECORDS_SQL).fetchall():
        uid = record_uid(output_id, digest)
        if uid in done:
            continue
        records.append({
            "kind": OFFICIAL_RECORD, "record_uid": uid, "evidence_uid": uid,
            "incident_id": incident_id, "output_id": output_id, "output_hash": digest,
            "status": status, "tier": tier, "source_ref": source_ref,
            "supersedes": supersedes, "recorded_at": recorded_at,
        })
    return records


def create_batch(conn, records, kind=EVIDENCE):
    """Simpan satu batch dari daftar kamus bukti; kembalikan (batch_id, akar heksadesimal)."""
    fields = RECORD_FIELDS if kind == OFFICIAL_RECORD else PAYLOAD_FIELDS
    id_key = "output_id" if kind == OFFICIAL_RECORD else "evidence_id"
    payloads = [canonical_payload(record, fields) for record in records]
    leaves = [leaf_hash(payload) for payload in payloads]
    root = merkle_root(leaves).hex()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO evidence_batches (
            merkle_root, previous_root, leaf_count, first_evidence_id,
            last_evidence_id, created_at, pipeline_version, batch_kind
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            root, latest_root(conn), len(records), records[0][id_key],
            records[-1][id_key], get_timestamp(), pipeline_stamp(), kind,
        ),
    )
    batch_id = cursor.lastrowid
    cursor.executemany(
        "INSERT INTO evidence_leaves (batch_id, leaf_index, evidence_uid, leaf_hash, payload) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (batch_id, index, record["evidence_uid"], leaf.hex(), payload)
            for index, (record, leaf, payload) in enumerate(zip(records, leaves, payloads))
        ],
    )
    conn.commit()
    return batch_id, root


def batch_pending(conn, max_leaves=MAX_LEAVES):
    """Masukkan bukti dan catatan D4 tertunda ke batch baru; kembalikan (batch_id, akar, jumlah)."""
    create_tables(conn)
    created = []
    for kind, records in ((EVIDENCE, pending_evidence(conn)), (OFFICIAL_RECORD, pending_records(conn))):
        for start in range(0, len(records), max_leaves):
            chunk = records[start : start + max_leaves]
            batch_id, root = create_batch(conn, chunk, kind)
            created.append((batch_id, root, len(chunk)))
    return created


def proof_for(conn, evidence_uid):
    """Bukti Merkle satu evidence sebagai kamus siap JSON; None bila belum masuk batch."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT l.batch_id, l.leaf_index, l.leaf_hash, l.payload, b.merkle_root,
               b.leaf_count, b.created_at, b.anchor_status, b.anchor_chain, b.anchor_tx
        FROM evidence_leaves l JOIN evidence_batches b USING (batch_id)
        WHERE l.evidence_uid = ?
        """,
        (evidence_uid,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    batch_id, index, leaf_hex, payload, root, count, created_at, status, chain, tx = row
    cursor.execute(
        "SELECT leaf_hash FROM evidence_leaves WHERE batch_id = ? ORDER BY leaf_index",
        (batch_id,),
    )
    leaves = [bytes.fromhex(value[0]) for value in cursor.fetchall()]
    proof = merkle_proof(leaves, index)
    return {
        "evidence_uid": evidence_uid,
        "batch_id": batch_id,
        "leaf_index": index,
        "leaf_count": count,
        "leaf_hash": leaf_hex,
        "payload": payload,
        "proof": [item.hex() for item in proof],
        "merkle_root": root,
        "valid": verify_proof(bytes.fromhex(leaf_hex), proof, bytes.fromhex(root)),
        "created_at": created_at,
        "anchor_status": status,
        "anchor_chain": chain,
        "anchor_tx": tx,
    }


def ledger_summary(conn):
    """(jumlah batch, jumlah daun, batch belum dijangkarkan)."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(leaf_count), 0) FROM evidence_batches")
    batches, leaves = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM evidence_batches WHERE anchor_status = 'PENDING'")
    pending = cursor.fetchone()[0]
    return batches, leaves, pending


def run():
    """Jalankan tahap ledger: batch Merkle untuk bukti dan catatan D4 yang belum masuk batch."""
    print("\n==================================================")
    print("   LEDGER - BATCH MERKLE BUKTI")
    print("==================================================")
    started_at = get_timestamp()
    conn = get_connection()
    try:
        created = batch_pending(conn)
        batches, leaves, pending = ledger_summary(conn)
        total_leaves = sum(count for _, _, count in created)
        record_run(conn, "ledger_batch", started_at, total_leaves)
    finally:
        conn.close()
    if created:
        for batch_id, root, count in created:
            print(f"   batch #{batch_id}: {count} daun, akar {root[:16]}…")
    else:
        print("   Tidak ada bukti baru; tidak ada batch dibuat.")
    print(f"\nTotal batch        : {batches}")
    print(f"Total daun         : {leaves}")
    print(f"Belum dijangkarkan : {pending}")
    print("==================================================")
    print("   ✅ LEDGER SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
