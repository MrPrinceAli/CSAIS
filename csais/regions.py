"""Wilayah Indonesia dan kelompok masyarakat yang disebut berita tiap incident.

Dasar Peta Literasi di halaman Peringatan: di provinsi mana incident terjadi,
dan kelompok masyarakat mana yang disebut (pelajar SMP, ormas, perangkat
desa, ...). Hanya incident Indonesia yang dibaca: lokasinya memuat Indonesia
atau salah satu artikelnya berbahasa Indonesia.

Wilayah dikenali dari judul, ringkasan, dan awal isi artikel dengan daftar
resmi 38 provinsi dan 514 kabupaten/kota (csais/data/wilayah.json):
  - nama provinsi dan singkatannya (Jabar, Jatim, DIY, NTT, ...);
  - "Kabupaten X", "Kab. X", "Kota X", atau nama X saja. Nama yang juga kata
    umum atau nama orang (Malang, Serang, Batu, Bima, ...) hanya dihitung bila
    didahului kata penanda wilayah (di, warga, Polres, Pemkab, ...).
Kabupaten/kota disimpan bersama provinsinya; peta memakai level provinsi.

Kelompok masyarakat dikenali dengan kata kunci (COMMUNITY_PATTERNS) dan
disimpan sebagai kunci sasaran literasi di web/lib/prevention.json; alur D1
memakainya sebagai sasaran literasi yang paling spesifik.

Platform yang banyak dipakai masyarakat Indonesia (Binance, WhatsApp, Shopee,
Roblox, ...; web/lib/platforms.json) dikenali di incident negara MANA PUN:
kebocoran di luar negeri pada layanan yang juga dipakai di Indonesia tetap
menjadi sasaran literasi "pengguna <platform> di Indonesia" (kunci
``platform:<kunci>``).

Tabel: ``incident_regions`` (satu baris per incident dan wilayah),
``incident_communities`` (satu baris per incident dan kelompok), dan
``incident_platforms`` (satu baris per incident dan platform).
"""

import json
import os
import re
import sqlite3
from collections import Counter

from csais.config import PROJECT_ROOT
from csais.db import get_connection, get_timestamp
from csais.schema import record_run
from csais.text import split_publisher

WILAYAH_FILE = os.path.join(PROJECT_ROOT, "csais", "data", "wilayah.json")
PLATFORMS_FILE = os.path.join(PROJECT_ROOT, "web", "lib", "platforms.json")
CONTENT_CHARS = 4000  # awal isi artikel yang ikut dibaca

with open(WILAYAH_FILE, encoding="utf-8") as _fh:
    WILAYAH = json.load(_fh)
with open(PLATFORMS_FILE, encoding="utf-8") as _fh:
    PLATFORMS = json.load(_fh)["platforms"]
PLATFORM_RE = {key: re.compile(rf"(?<![\w-])(?:{p['pattern']})(?![\w-])") for key, p in PLATFORMS.items()}

PROVINCE_DISPLAY = {"31": "DKI Jakarta", "34": "DI Yogyakarta"}
# Singkatan dan sebutan lain provinsi (huruf besar-kecil seperti di berita)
PROVINCE_ALIASES = {
    "11": ["Aceh"], "12": ["Sumut"], "13": ["Sumbar"], "14": ["Riau"], "15": ["Jambi"],
    "16": ["Sumsel"], "17": ["Bengkulu"], "18": ["Lampung"], "19": ["Babel", "Bangka Belitung"],
    "21": ["Kepri"], "31": ["Jakarta", "DKI Jakarta", "DKI", "Metro Jaya"], "32": ["Jabar"], "33": ["Jateng"],
    "34": ["Yogyakarta", "DIY", "Jogja", "Jogjakarta", "Yogya"], "35": ["Jatim"], "36": ["Banten"],
    "51": ["Bali"], "52": ["NTB"], "53": ["NTT"], "61": ["Kalbar"], "62": ["Kalteng"], "63": ["Kalsel"],
    "64": ["Kaltim"], "65": ["Kaltara"], "71": ["Sulut"], "72": ["Sulteng"], "73": ["Sulsel"],
    "74": ["Sultra"], "75": ["Gorontalo"], "76": ["Sulbar"], "81": ["Maluku"], "82": ["Malut"],
}
# Kota yang lebih dikenal dengan nama lain
CITY_ALIASES = {"Solo": "33.72", "Surakarta": "33.72", "Makasar": "73.71"}
# Nama yang juga kata umum, nama orang, atau tempat lain: butuh kata penanda wilayah
AMBIGUOUS = {
    "Malang", "Serang", "Batang", "Buru", "Pati", "Agam", "Lebak", "Bima", "Muna", "Kaur", "Malaka", "Bone",
    "Solo", "Alor", "Belu", "Sabu", "Rote", "Paser", "Medan", "Padang", "Palu", "Sorong", "Kuningan", "Metro",
    "Batu", "Tual", "Jaya", "Kudus", "Tegal", "Karo", "Puncak", "Kapuas", "Kendal", "Lahat", "Ende", "Aru",
    "Bungo", "Tebo", "Siak", "Barru", "Sula", "Toba",
}
CONTEXT = (
    r"(?:di|ke|dari|asal|warga|wilayah|daerah|kawasan|kota|kabupaten|kab\.|provinsi|polres|polresta|"
    r"polrestabes|polda|pemkot|pemkab|pemprov|dprd|bupati|wali ?kota|walikota|gubernur|kejari|kejati|"
    r"pengadilan negeri|diskominfo|in|from)"
)

# Kelompok masyarakat -> kunci sasaran literasi (web/lib/prevention.json "audiences")
COMMUNITY_PATTERNS = {
    "pelajar_smp": r"\b(?:SMP|MTs|siswa SMP|pelajar SMP)\b",
    "pelajar_sma": r"\b(?:SMA|SMK|siswa SMA|pelajar SMA)\b",
    "mahasiswa": r"\b(?:mahasiswa|mahasiswi|kampus|universitas)\b",
    "guru": r"\b(?:guru|tenaga pendidik|kepala sekolah)\b",
    "anak": r"\b(?:anak-anak|anak di bawah umur|siswa SD|remaja)\b",
    "pengurus_ormas": r"\b(?:ormas|organisasi kemasyarakatan|yayasan|LSM|komunitas)\b",
    "tokoh_agama": r"\b(?:masjid|gereja|pesantren|ponpes|ustaz|ustadz|kiai|kyai|pendeta|jemaah|jamaah|majelis taklim)\b",
    "perangkat_desa": r"\b(?:kepala desa|kades|perangkat desa|dana desa|pemerintah desa|lurah)\b",
    "pekerja_migran": r"\b(?:pekerja migran|PMI|TKI|TKW|buruh migran)\b",
    "petani_nelayan": r"\b(?:petani|nelayan|peternak)\b",
    "pengemudi_ojol": r"\b(?:ojol|ojek online|ojek daring|driver online|pengemudi online|mitra pengemudi)\b",
    "ibu_rumah_tangga": r"\b(?:ibu rumah tangga|IRT|emak-emak|ibu-ibu)\b",
    "lansia": r"\b(?:lansia|lanjut usia|pensiunan)\b",
    "pelaku_umkm": r"\b(?:UMKM|pedagang|pelapak|penjual online|toko online|warung)\b",
    "asn_layanan": r"\b(?:ASN|PNS|aparatur sipil negara|pegawai negeri)\b",
    "nasabah_bank": r"\b(?:nasabah|rekening bank|m-banking|mobile banking)\b",
    "investor_ritel": r"\b(?:investasi bodong|investor|aset kripto|robot trading)\b",
    "pencari_kerja": r"\b(?:lowongan kerja|loker|pencari kerja|calon pekerja)\b",
}
COMMUNITY_RE = {key: re.compile(pattern, re.I if key not in ("pelajar_smp", "pelajar_sma", "pekerja_migran", "asn_layanan", "ibu_rumah_tangga") else 0)
                for key, pattern in COMMUNITY_PATTERNS.items()}


# --- Daftar nama ---
def _base(name):
    return re.sub(r"^(?:Kabupaten Administrasi|Kota Administrasi|Kabupaten|Kota) ", "", name.strip())


def build_gazetteer():
    """(nama -> (kode provinsi, kode kabkota/None)) untuk nama tegas dan nama yang butuh penanda."""
    plain, contextual = {}, {}
    for code, name in WILAYAH["provinsi"].items():
        for alias in [name.strip(), PROVINCE_DISPLAY.get(code, "")] + PROVINCE_ALIASES.get(code, []):
            if alias:
                plain[alias] = (code, None)
    bases = {}
    for code, name in WILAYAH["kabkota"].items():
        name = name.strip()
        base = _base(name)
        prefix_kab = name.startswith("Kabupaten")
        plain[name] = (code[:2], code)
        if prefix_kab:
            plain[f"Kab. {base}"] = (code[:2], code)
        bases.setdefault(base, []).append((code, name.startswith("Kota")))
        if len(base.split()) == 2:  # "Kulon Progo" juga ditulis Kulonprogo atau KulonProgo
            first, second = base.split()
            for joined in {first + second, first + second.lower()}:
                bases.setdefault(joined, []).append((code, name.startswith("Kota")))
    for base, entries in bases.items():
        provinces = {code[:2] for code, _ in entries}
        if len(provinces) > 1 or base in plain:
            continue  # nama sama di dua provinsi (Banjar) atau sama dengan nama provinsi
        # nama saja: utamakan kota bila ada kota dan kabupaten bernama sama
        code = sorted(entries, key=lambda e: not e[1])[0][0]
        (contextual if base in AMBIGUOUS else plain)[base] = (code[:2], code)
    for alias, code in CITY_ALIASES.items():
        (contextual if alias in AMBIGUOUS else plain)[alias] = (code[:2], code)
    return plain, contextual


def _alternation(names):
    return "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))


PLAIN, CONTEXTUAL = build_gazetteer()
PLAIN_RE = re.compile(rf"(?<![\w-])({_alternation(PLAIN)})(?![\w-])")
# "Polda Metro Jaya" adalah Jakarta, bukan Kota Metro di Lampung
CONTEXT_RE = re.compile(rf"(?i:\b{CONTEXT})\s+({_alternation(CONTEXTUAL)})(?![\w-])(?!\s+Jaya)")


_NOT_INDONESIA = re.compile(r"\bPapua (?:Nugini|New Guinea)\b")


def find_regions(text):
    """Counter (kode provinsi, kode kabkota/None) -> jumlah sebutan dalam satu teks."""
    text = _NOT_INDONESIA.sub("PNG", text)
    found = Counter()
    for match in PLAIN_RE.finditer(text):
        found[PLAIN[match.group(1)]] += 1
    for match in CONTEXT_RE.finditer(text):
        found[CONTEXTUAL[match.group(1)]] += 1
    return found


def find_communities(text):
    return Counter({key: len(regex.findall(text)) for key, regex in COMMUNITY_RE.items() if regex.search(text)})


def find_platforms(text):
    return Counter({key: len(regex.findall(text)) for key, regex in PLATFORM_RE.items() if regex.search(text)})


def province_name(code):
    return PROVINCE_DISPLAY.get(code) or WILAYAH["provinsi"][code].strip()


# --- Tahap pipeline ---
_DOCS_SQL = """
    SELECT d.incident_id, a.title, a.summary, {content}, a.language, i.location
    FROM v05_incident_documents d
    JOIN articles a ON a.article_id = d.article_id
    JOIN v05_incidents i ON i.incident_id = d.incident_id
"""


def incident_context(conn):
    """{incident_id: (Counter wilayah, Counter kelompok)} untuk incident Indonesia."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(articles)")}
    content = f"substr(a.content, 1, {CONTENT_CHARS})" if "content" in columns else "NULL"
    texts, indonesian, platforms = {}, set(), {}
    for incident_id, title, summary, body, language, location in conn.execute(_DOCS_SQL.format(content=content)):
        if language == "id" or "indonesia" in (location or "").lower():
            indonesian.add(incident_id)
        # nama media di akhir judul dan ringkasan ("... - Koran Jakarta") bukan lokasi kejadian
        headline, publisher = split_publisher(title)
        if publisher and summary:
            summary = summary.replace(publisher, " ")
        texts.setdefault(incident_id, []).append((" ".join(p for p in (headline, body) if p), summary or ""))
        found = set(find_platforms(f"{headline} {summary or ''} {body or ''}"))
        if found:
            platforms.setdefault(incident_id, Counter()).update(found)
    result = {}
    for incident_id in indonesian:
        strong, weak, communities = Counter(), Counter(), Counter()
        for main, summary in texts[incident_id]:
            # satu artikel dihitung sekali per wilayah/kelompok: jumlah = artikel yang menyebut
            in_main = set(find_regions(main))
            strong.update(in_main)
            weak.update(set(find_regions(summary)) - in_main)
            communities.update(set(find_communities(f"{main} {summary}")))
        # ringkasan Google News sering memuat judul berita lain: wilayah yang hanya
        # muncul di ringkasan baru dihitung bila disebut dua artikel atau lebih
        regions = Counter({key: n + weak[key] for key, n in strong.items()})
        regions.update({key: n for key, n in weak.items() if key not in strong and n >= 2})
        if regions or communities:
            result[incident_id] = (regions, communities)
    return result, platforms


def store(conn, context, platforms=None):
    conn.execute("DROP TABLE IF EXISTS incident_regions")
    conn.execute("""
        CREATE TABLE incident_regions (
            incident_id TEXT NOT NULL, province_code TEXT NOT NULL, province TEXT NOT NULL,
            kabkota_code TEXT, kabkota TEXT, mentions INTEGER NOT NULL
        )""")
    conn.execute("DROP TABLE IF EXISTS incident_communities")
    conn.execute("CREATE TABLE incident_communities (incident_id TEXT NOT NULL, audience TEXT NOT NULL, mentions INTEGER NOT NULL)")
    region_rows, community_rows = [], []
    for incident_id, (regions, communities) in context.items():
        for (province, kabkota), mentions in regions.items():
            name = WILAYAH["kabkota"][kabkota].strip() if kabkota else None
            region_rows.append((incident_id, province, province_name(province), kabkota, name, mentions))
        community_rows.extend((incident_id, key, n) for key, n in communities.items())
    conn.executemany("INSERT INTO incident_regions VALUES (?, ?, ?, ?, ?, ?)", region_rows)
    conn.executemany("INSERT INTO incident_communities VALUES (?, ?, ?)", community_rows)
    conn.execute("DROP TABLE IF EXISTS incident_platforms")
    conn.execute("CREATE TABLE incident_platforms (incident_id TEXT NOT NULL, platform TEXT NOT NULL, mentions INTEGER NOT NULL)")
    conn.executemany(
        "INSERT INTO incident_platforms VALUES (?, ?, ?)",
        [(incident_id, key, n) for incident_id, found in (platforms or {}).items() for key, n in found.items()],
    )
    conn.execute("CREATE INDEX idx_incident_regions_province ON incident_regions(province_code)")
    conn.execute("CREATE INDEX idx_incident_communities_incident ON incident_communities(incident_id)")
    conn.commit()
    return len({row[0] for row in region_rows}), len({row[0] for row in community_rows})


def communities_by_incident(conn):
    """incident_id -> kunci sasaran dari berita: kelompok masyarakat dulu, lalu
    platform (``platform:<kunci>``), masing-masing paling banyak disebut dulu;
    {} bila tabel belum ada."""
    grouped = {}
    for sql, prefix, rank in (
        ("SELECT incident_id, audience, mentions FROM incident_communities", "", 0),
        ("SELECT incident_id, platform, mentions FROM incident_platforms", "platform:", 1),
    ):
        try:
            rows = conn.execute(sql).fetchall()
        except sqlite3.OperationalError:
            continue
        for incident_id, key, mentions in rows:
            grouped.setdefault(incident_id, []).append((rank, -mentions, f"{prefix}{key}"))
    return {k: [key for *_, key in sorted(v)] for k, v in grouped.items()}


def run():
    print("\n==================================================")
    print("   WILAYAH DAN KELOMPOK MASYARAKAT")
    print("==================================================")
    started_at = get_timestamp()
    conn = get_connection()
    try:
        context, platforms = incident_context(conn)
        with_region, with_community = store(conn, context, platforms)
        record_run(conn, "incident_regions", started_at, with_region)
        provinces = Counter(
            row[0] for row in conn.execute("SELECT province FROM incident_regions GROUP BY incident_id, province")
        )
    finally:
        conn.close()
    print(f"Incident dengan wilayah  : {with_region}")
    print(f"Incident dengan kelompok : {with_community}")
    print(f"Incident dengan platform : {len(platforms)} (semua negara)")
    print("Provinsi teratas         : " + ", ".join(f"{name} {n}" for name, n in provinces.most_common(6)))
    print("==================================================")


if __name__ == "__main__":
    run()
