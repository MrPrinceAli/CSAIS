"""Penjangkaran akar Merkle ke blockchain lokal (prototipe) dan penerapannya.

Jaringan lokal saat ini adalah Anvil (Foundry) di komputer sendiri, dijalankan
dengan ``scripts/chain_local.sh``. Kontrak ``chain/src/CsaisAnchor.sol``
(hasil kompilasi di ``chain/CsaisAnchor.json``) sama dengan yang nanti dipakai
di jaringan permissioned Besu QBFT; hanya cara menandatangani transaksi yang
berbeda (Anvil menerima eth_sendTransaction dari akun bawaan yang tidak
terkunci).

Karena pipeline harian berjalan di GitHub Actions yang tidak bisa menjangkau
jaringan lokal, alurnya dibagi dua:
  1. di komputer lokal: ``main.py --anchor`` membaca batch yang belum
     dijangkarkan dari Turso, mengirim ``anchorRoot`` ke kontrak, lalu menulis
     bukti transaksinya ke tabel ``chain_anchors`` di database masukan
     (csais-survey, token tulis ``SURVEY_WRITE_TOKEN``);
  2. di pipeline: ``apply_anchors`` membaca ``chain_anchors`` (token baca) dan
     menandai batch yang akarnya cocok sebagai ANCHORED sebelum diterbitkan.

Variabel lingkungan (lokal):
  CHAIN_RPC_URL       default http://127.0.0.1:8545
  CHAIN_NAME          default anvil-lokal
  CHAIN_CONTRACT      alamat kontrak; bila kosong dibaca dari chain/deployment.local.json
"""

import json
import os
import time

import requests

from csais.config import PROJECT_ROOT
from csais.db import get_timestamp

ARTIFACT_FILE = os.path.join(PROJECT_ROOT, "chain", "CsaisAnchor.json")
DEPLOYMENT_FILE = os.path.join(PROJECT_ROOT, "chain", "deployment.local.json")
DEFAULT_RPC = "http://127.0.0.1:8545"
INSTITUTION_CODES = ("BSSN", "OJK", "KOMDIGI", "POLRI")
KIND = {"evidence": 0, "official_record": 1}

ANCHORS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS chain_anchors (
        merkle_root TEXT PRIMARY KEY,
        batch_id INTEGER NOT NULL,
        kind INTEGER NOT NULL,
        chain TEXT NOT NULL,
        chain_id INTEGER NOT NULL,
        contract TEXT NOT NULL,
        tx_hash TEXT NOT NULL,
        block_number INTEGER NOT NULL,
        anchored_at TEXT NOT NULL
    )
"""
ANCHORS_SQL = """
    SELECT merkle_root, batch_id, chain, chain_id, contract, tx_hash, block_number, anchored_at
    FROM chain_anchors
"""


# --- ABI (hanya tipe statis: cukup kata 32 byte) ---
def _artifact():
    with open(ARTIFACT_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def selector(signature):
    """4 byte pemilih fungsi dari artefak kompilasi (tanpa pustaka keccak)."""
    return _artifact()["methodIdentifiers"][signature]


def word(value):
    """Satu argumen statis sebagai 32 byte heksadesimal."""
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        return f"{value:064x}"
    text = str(value).lower().removeprefix("0x")
    if len(text) == 40:  # alamat
        return text.rjust(64, "0")
    if len(text) != 64:
        raise ValueError(f"bukan bytes32/alamat: {value}")
    return text


def encode_call(signature, *args):
    return "0x" + selector(signature) + "".join(word(a) for a in args)


def decode_words(data):
    text = (data or "0x")[2:]
    return [text[i : i + 64] for i in range(0, len(text), 64)]


def code_bytes32(code):
    """Kode lembaga (ASCII) sebagai bytes32 rata kiri, seperti bytes32("BSSN") di Solidity."""
    raw = code.encode("ascii").hex()
    return raw.ljust(64, "0")


# --- JSON-RPC ---
class ChainClient:
    """Klien JSON-RPC kecil untuk Anvil (akun bawaan tidak terkunci)."""

    def __init__(self, rpc_url=None, session=None):
        self.rpc_url = rpc_url or os.environ.get("CHAIN_RPC_URL") or DEFAULT_RPC
        self.session = session or requests.Session()
        self._id = 0

    def call(self, method, params=None):
        self._id += 1
        response = self.session.post(
            self.rpc_url,
            json={"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or []},
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise RuntimeError(f"RPC {method}: {body['error'].get('message')}")
        return body["result"]

    def chain_id(self):
        return int(self.call("eth_chainId"), 16)

    def accounts(self):
        return self.call("eth_accounts")

    def send(self, sender, to, data):
        """Kirim transaksi dan tunggu tanda terimanya; kembalikan receipt."""
        tx = {"from": sender, "data": data}
        if to:
            tx["to"] = to
        tx_hash = self.call("eth_sendTransaction", [tx])
        for _ in range(120):
            receipt = self.call("eth_getTransactionReceipt", [tx_hash])
            if receipt:
                if int(receipt.get("status", "0x1"), 16) != 1:
                    raise RuntimeError(f"transaksi gagal: {tx_hash}")
                return receipt
            time.sleep(0.5)
        raise TimeoutError(f"tanda terima tidak muncul: {tx_hash}")

    def eth_call(self, to, data):
        return self.call("eth_call", [{"to": to, "data": data}, "latest"])


# --- Kontrak ---
def load_deployment():
    address = os.environ.get("CHAIN_CONTRACT")
    if address:
        return {"contract": address}
    try:
        with open(DEPLOYMENT_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        return None


def deploy(client=None):
    """Pasang kontrak dari akun pertama; akun 2-5 didaftarkan sebagai lembaga."""
    client = client or ChainClient()
    accounts = client.accounts()
    receipt = client.send(accounts[0], None, "0x" + _artifact()["bytecode"].removeprefix("0x"))
    contract = receipt["contractAddress"]
    institutions = {}
    for code, account in zip(INSTITUTION_CODES, accounts[1:5]):
        client.send(accounts[0], contract, encode_call("setInstitution(bytes32,address)", code_bytes32(code), account))
        institutions[code] = account
    deployment = {
        "contract": contract,
        "chain_id": client.chain_id(),
        "relayer": accounts[0],
        "institutions": institutions,
        "block": int(receipt["blockNumber"], 16),
        "deployed_at": get_timestamp(),
    }
    with open(DEPLOYMENT_FILE, "w", encoding="utf-8") as fh:
        json.dump(deployment, fh, indent=2)
    return deployment


def get_anchor(client, contract, root_hex):
    """(batch_id, kind, previous_root, block, timestamp) atau None bila belum dijangkarkan."""
    words = decode_words(client.eth_call(contract, encode_call("getAnchor(bytes32)", root_hex)))
    block = int(words[3], 16)
    if block == 0:
        return None
    return int(words[0], 16), int(words[1], 16), words[2], block, int(words[4], 16)


def anchor_batches(batches, client, contract, chain_name):
    """Jangkarkan daftar batch (dict merkle_root, previous_root, batch_id, batch_kind).

    Akar yang sudah ada di kontrak tidak dikirim ulang; data jangkarnya dibaca
    dari kontrak agar tetap tercatat. Kembalikan daftar baris chain_anchors.
    """
    chain_id = client.chain_id()
    sender = client.accounts()[0]
    rows = []
    for batch in batches:
        root = batch["merkle_root"]
        kind = KIND.get(batch.get("batch_kind") or "evidence", 0)
        existing = get_anchor(client, contract, root)
        if existing:
            tx_hash, block = "", existing[3]
        else:
            data = encode_call(
                "anchorRoot(uint64,bytes32,bytes32,uint8)",
                int(batch["batch_id"]), root, batch.get("previous_root") or "0" * 64, kind,
            )
            receipt = client.send(sender, contract, data)
            tx_hash, block = receipt["transactionHash"], int(receipt["blockNumber"], 16)
        rows.append({
            "merkle_root": root, "batch_id": int(batch["batch_id"]), "kind": kind,
            "chain": chain_name, "chain_id": chain_id, "contract": contract.lower(),
            "tx_hash": tx_hash, "block_number": block, "anchored_at": get_timestamp(),
        })
    return rows


# --- Penerapan di pipeline ---
def apply_anchors(conn, rows):
    """Tandai batch yang akarnya cocok sebagai ANCHORED; kembalikan jumlah yang berubah."""
    changed = 0
    for root, batch_id, chain, chain_id, contract, tx_hash, block, anchored_at in rows:
        cursor = conn.execute(
            """
            UPDATE evidence_batches
            SET anchor_status = 'ANCHORED', anchor_chain = ?, anchor_tx = ?,
                anchor_block = ?, anchored_at = ?
            WHERE merkle_root = ? AND batch_id = ? AND anchor_status != 'ANCHORED'
            """,
            (f"{chain}:{chain_id}@{contract}", tx_hash or None, block, anchored_at, root, batch_id),
        )
        changed += cursor.rowcount
    conn.commit()
    return changed


# --- Perintah lokal ---
PENDING_SQL = """
    SELECT batch_id, merkle_root, previous_root, batch_kind
    FROM evidence_batches WHERE anchor_status = 'PENDING' ORDER BY batch_id
"""


def _rows(url, token, sql):
    from csais.survey import fetch_file, fetch_remote

    if url.startswith("file:"):
        return fetch_file(url[len("file:"):], sql)
    return fetch_remote(url, token, sql)


def pending_batches():
    """Batch PENDING dari database terbit (Turso) sebagai daftar dict."""
    url = os.environ.get("TURSO_DATABASE_URL") or ""
    if not url:
        raise ValueError("TURSO_DATABASE_URL belum diisi")
    rows = _rows(url, os.environ.get("TURSO_AUTH_TOKEN"), PENDING_SQL)
    keys = ("batch_id", "merkle_root", "previous_root", "batch_kind")
    return [dict(zip(keys, row)) for row in rows]


def store_anchor_rows(rows):
    """Tulis baris chain_anchors ke database masukan (token tulis)."""
    url = (os.environ.get("SURVEY_DATABASE_URL") or "").strip()
    if not url:
        raise ValueError("SURVEY_DATABASE_URL belum diisi")
    columns = ("merkle_root", "batch_id", "kind", "chain", "chain_id", "contract", "tx_hash", "block_number", "anchored_at")
    values = f"({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"
    # Akar yang sudah ada di kontrak (tx_hash kosong) tidak boleh menimpa catatan lengkap
    statements = [
        (f"INSERT {'OR REPLACE' if r['tx_hash'] else 'OR IGNORE'} INTO chain_anchors {values}", [r[c] for c in columns])
        for r in rows
    ]
    if url.startswith("file:"):
        import sqlite3

        conn = sqlite3.connect(url[len("file:"):])
        conn.execute(ANCHORS_SCHEMA)
        for sql, args in statements:
            conn.execute(sql, args)
        conn.commit()
        conn.close()
        return
    from csais.publish import TursoClient

    token = os.environ.get("SURVEY_WRITE_TOKEN")
    if not token:
        raise ValueError("SURVEY_WRITE_TOKEN (token tulis database masukan) belum diisi")
    client = TursoClient(url, token)
    client.execute([(ANCHORS_SCHEMA, [])] + statements)


def run_deploy():
    deployment = deploy()
    print(f"Kontrak dipasang di {deployment['contract']} (chain {deployment['chain_id']}, blok {deployment['block']}).")
    for code, account in deployment["institutions"].items():
        print(f"   {code:8s} {account}")
    print(f"Disimpan ke {DEPLOYMENT_FILE}")


def run_anchor():
    """Jangkarkan semua batch PENDING ke jaringan lokal dan catat buktinya."""
    deployment = load_deployment()
    if not deployment:
        raise SystemExit("Kontrak belum dipasang: jalankan python main.py --chain-deploy")
    client = ChainClient()
    chain_name = os.environ.get("CHAIN_NAME") or "anvil-lokal"
    batches = pending_batches()
    print(f"Batch menunggu penjangkaran: {len(batches)}")
    rows = anchor_batches(batches, client, deployment["contract"], chain_name)
    if rows:
        store_anchor_rows(rows)
    sent = sum(1 for r in rows if r["tx_hash"])
    print(f"Dijangkarkan sekarang: {sent}; sudah ada di kontrak: {len(rows) - sent}")
    print("Status ANCHORED terbit ke web setelah run pipeline harian berikutnya.")


def run_status(root_hex):
    deployment = load_deployment()
    if not deployment:
        raise SystemExit("Kontrak belum dipasang.")
    found = get_anchor(ChainClient(), deployment["contract"], root_hex.lower().removeprefix("0x"))
    if not found:
        print("Akar ini belum dijangkarkan.")
        return
    batch_id, kind, previous, block, timestamp = found
    print(json.dumps({"batch_id": batch_id, "kind": kind, "previous_root": previous, "block": block, "timestamp": timestamp}, indent=2))


INSTITUTION_KEYS_FILE = os.path.join(PROJECT_ROOT, "web", "lib", "institution-keys.json")


def register_institutions(client=None, path=INSTITUTION_KEYS_FILE):
    """Daftarkan alamat kunci tanda tangan portal (institution-keys.json) ke kontrak."""
    deployment = load_deployment()
    if not deployment:
        raise SystemExit("Kontrak belum dipasang: jalankan python main.py --chain-deploy")
    client = client or ChainClient()
    with open(path, encoding="utf-8") as fh:
        addresses = json.load(fh)["addresses"]
    admin = client.accounts()[0]
    for code, address in addresses.items():
        client.send(admin, deployment["contract"], encode_call("setInstitution(bytes32,address)", code_bytes32(code), address))
        words = decode_words(client.eth_call(deployment["contract"], encode_call("institutions(bytes32)", code_bytes32(code))))
        print(f"   {code:8s} {address}  (terbaca di kontrak: 0x{words[0][24:]})")
    deployment["institutions"] = addresses
    if not os.environ.get("CHAIN_CONTRACT"):
        with open(DEPLOYMENT_FILE, "w", encoding="utf-8") as fh:
            json.dump(deployment, fh, indent=2)
