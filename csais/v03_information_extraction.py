"""CSAIS V0.3 - Information Extraction.

Ekstraksi informasi berbasis aturan (kata kunci dan regex) dari artikel yang
dinilai RELEVANT atau UNCERTAIN oleh V0.2: jenis serangan, metode serangan,
sektor dan organisasi target, kelompok target, lokasi, tanggal serangan,
pelaku ancaman, dampak, serta indikator (CVE dan hash). Hasil disimpan ke
tabel ``v03_information_extraction`` beserta skor kepercayaan ekstraksi.
"""

import json
import os
import re
from datetime import datetime

from csais.config import DATABASE_FILE
from csais.db import get_connection, get_timestamp
from csais.provenance import pipeline_stamp
from csais.schema import ensure_column, ensure_content_columns, record_run
from csais.text import (
    contains_keyword,
    drop_overlapping_keywords,
    find_keywords,
    normalize_text,
    remove_publisher,
    split_publisher,
)


# --- Konfigurasi ---
BATCH_SIZE = 500


# --- Kata kunci ekstraksi ---
# Daftar kata kunci disimpan di file JSON pada folder csais/data agar dapat
# diubah tanpa menyentuh kode. Penjelasan setiap kunci ada di csais/data/README.md.
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load_keywords(name):
    """Baca satu file data kata kunci JSON dari folder csais/data."""
    with open(os.path.join(_DATA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


_EXTRACTION = _load_keywords("extraction_keywords.json")

# Kata kunci jenis serangan
ATTACK_TYPE_KEYWORDS = _EXTRACTION["attack_type_keywords"]

# Kata kunci metode serangan
ATTACK_METHOD_KEYWORDS = _EXTRACTION["attack_method_keywords"]

# Kata kunci sektor target
TARGET_SECTOR_KEYWORDS = _EXTRACTION["target_sector_keywords"]

# Kata kunci kelompok target
TARGET_GROUP_KEYWORDS = _EXTRACTION["target_group_keywords"]

# Kata kunci dampak
IMPACT_KEYWORDS = _EXTRACTION["impact_keywords"]

# Kata kunci negara / lokasi
COUNTRY_NAMES = _EXTRACTION["country_names"]


# --- Ekstraksi berbasis kata kunci ---
def find_keyword_matches(text, keyword_dictionary):
    """Kategori yang salah satu kata kuncinya muncul sebagai kata utuh di teks."""
    matches = []
    for category, keywords in keyword_dictionary.items():
        for keyword in keywords:
            if contains_keyword(text, keyword):
                matches.append(category)
                break
    return matches


def extract_attack_type(text):
    """Ekstrak jenis serangan dari teks."""
    matches = find_keyword_matches(text, ATTACK_TYPE_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_attack_method(text):
    """Ekstrak metode serangan dari teks."""
    matches = find_keyword_matches(text, ATTACK_METHOD_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_target_sector(text):
    """Ekstrak sektor target dari teks."""
    matches = find_keyword_matches(text, TARGET_SECTOR_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_target_group(text):
    """Ekstrak kelompok target dari teks."""
    matches = find_keyword_matches(text, TARGET_GROUP_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_impact(text):
    """Ekstrak dampak serangan dari teks."""
    matches = find_keyword_matches(text, IMPACT_KEYWORDS)
    if not matches:
        return "UNKNOWN"
    return ", ".join(matches)


def extract_location(text):
    """Ekstrak nama negara yang disebut di dalam teks."""
    locations = []
    for country, keywords in COUNTRY_NAMES.items():
        for keyword in keywords:
            if contains_keyword(text, keyword):
                locations.append(country)
                break
    if not locations:
        return "UNKNOWN"
    return ", ".join(locations)


# --- Pelaku ancaman yang sudah dikenal ---
# Nama grup yang cukup khas untuk dicari langsung di teks. Nama umum seperti
# "Play", "Royal", atau "Hive" hanya dicari bersama kata "ransomware".
KNOWN_THREAT_ACTORS = _EXTRACTION["known_threat_actors"]

# Kata sandang di awal nama dibuang.
_ARTICLES = {"a", "an", "the"}

# Bila kata PERTAMA hasil tangkapan regex termasuk di sini, tangkapan itu bukan
# nama (kata kerja judul berita, kata penunjuk, kata benda serangan, dll.).
_REJECT_FIRST_WORDS = {
    "this", "that", "these", "those", "it", "its", "their", "our", "his", "her",
    "several", "many", "some", "two", "three", "four", "five", "new", "another",
    "latest", "second", "third", "exclusive", "update", "breaking", "cyber",
    "cyberattack", "cyberattacks", "ransomware", "hackers", "hacker", "attack",
    "attacks", "attackers", "data", "breach", "after", "following", "amid", "why",
    "how", "what", "when", "who", "notorious", "infamous", "prolific", "suspected",
    "alleged", "takes", "take", "claims", "claim", "targets", "target", "exploits",
    "exploit", "exploited", "hits", "hit", "uses", "use", "abuses", "abuse", "deploys",
    "deploy", "leaks", "leak", "strikes", "strike", "steals", "steal", "targeting",
    "exploiting", "using", "behind", "linked", "tied", "says", "said", "warns", "warn",
    "reports", "report", "emerges", "returns", "expands", "shifts", "adds", "adopts",
    "now", "activity", "operations", "operation", "members", "leader", "affiliate",
    "affiliates", "victims", "victim", "list", "lists", "site", "sites", "website",
    "infrastructure", "threat", "tactics", "techniques", "tools", "malware", "group",
    "groups", "gang", "gangs", "name", "names", "police", "officials", "over", "more",
    "than", "most", "top", "worst", "massive", "huge", "emerging",
    # Kata fungsi yang kapital hanya karena berada di awal kalimat isi artikel
    "if", "while", "although", "though", "as", "but", "and", "or", "so", "because",
    "since", "once", "until", "unless", "before", "during", "however", "meanwhile",
    "according", "in", "on", "at", "by", "for", "from", "with", "to", "of", "there",
    "here", "they", "we", "you", "he", "she", "one", "no", "not", "yes", "also",
    "still", "even", "just", "only", "then", "today", "yesterday", "last", "first",
    "earlier", "later", "recently", "additionally", "further", "furthermore",
    "moreover", "instead", "despite", "among", "both", "each", "every", "such",
    "like", "unlike", "per", "via", "read", "learn", "see", "get", "watch", "follow",
    "sign", "subscribe", "share", "related", "sources", "source", "image", "photo",
    # Keterangan yang mendahului kata kerja ("Threat Actor Allegedly Claims ...")
    "allegedly", "reportedly", "purportedly", "apparently", "officially",
    # Judul seksi dan boilerplate halaman yang ikut terbawa di isi artikel
    "overview", "summary", "analysis", "timeline", "background", "introduction",
    "conclusion", "campaign", "detection", "mitigation", "mitigations",
    "recommendations", "references", "attribution", "indicators", "advertisement",
    "sponsored", "trending", "recommended", "popular", "newsletter", "podcast",
    "video", "editorial", "opinion", "click", "download", "print", "email",
    "copyright", "tags", "topics", "comments", "verify", "verifying", "please",
    "checking", "javascript", "cookies", "enable", "tbps", "gbps", "mbps",
    # Nama dan singkatan bulan ("Dec 28 was breached")
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    # Indonesia: kata kerja judul (tanpa awalan me-), keterangan, kata tunjuk,
    # dan kata benda pelaku/serangan; judul berita Indonesia memakai Title Case
    # sehingga kata-kata ini ikut berhuruf besar
    "hacker", "peretas", "pelaku", "penjahat", "kelompok", "geng", "grup", "sindikat",
    "serangan", "peretasan", "pembobolan", "kebocoran", "penipuan", "penipu",
    "diduga", "dikabarkan", "disebut", "dilaporkan", "berhasil", "sempat", "kembali",
    "resmi", "ini", "itu", "tersebut", "yang", "asal", "asing", "internasional",
    "global", "lokal", "misterius", "begini", "beginilah", "inilah", "ternyata",
    "waspada", "awas", "hati-hati", "jangan", "cara", "tips", "daftar", "deretan",
    "siapa", "apa", "mengapa", "kenapa", "bagaimana", "kok", "bisa", "usai",
    "setelah", "pasca", "imbas", "akibat", "karena", "gara-gara", "soal", "terkait",
    "hingga", "sampai", "saat", "ketika", "kini", "lagi", "makin", "semakin",
    "kian", "paling", "isu", "kasus", "dugaan", "heboh", "viral", "gawat",
    "serang", "bobol", "retas", "jebol", "curi", "jual", "sebar", "kuasai",
    "lumpuhkan", "sadap", "bajak", "susupi", "peras", "klaim", "mengaku", "ancam",
    "incar", "akui", "bantah", "sebut", "ungkap", "bongkar", "tangkap", "usut",
    "selidiki", "dalami", "jamin", "tolak", "cegah", "gagalkan", "tangkal", "rebut",
    "imbau", "minta", "desak", "pastikan", "benarkan", "tegaskan", "pulih", "rugi",
    "merugi", "kehilangan", "raib", "lenyap", "hilang", "rugikan", "terancam",
    "ancaman", "jutaan", "ribuan", "puluhan", "ratusan", "juta", "ribu", "miliar",
    "triliun", "sejumlah", "beberapa", "banyak", "para", "terjadi", "penjual",
    "pembeli", "selain", "selama", "seperti", "sehingga", "namun", "tetapi", "meski",
    "meskipun", "walau", "bahkan", "juga", "yakni", "yaitu", "adalah", "ialah",
    "hanya", "sudah", "telah", "masih", "akan", "bakal", "harus", "perlu", "dapat",
    "mulai", "sejak", "menurut", "kata", "ujar", "tutur",
}

# Kata umum yang tidak boleh menjadi satu-satunya isi sebuah nama. Kata benda
# lembaga boleh mengawali nama ("Bank of PNG", "University of X"), tetapi
# "Hospital" atau "Dutch" sendirian bukan nama.
_GENERIC_NAME_WORDS = _REJECT_FIRST_WORDS | {
    "company", "companies", "government", "hospital", "hospitals", "school",
    "schools", "university", "bank", "banks", "city", "county", "state", "council",
    "systems", "services", "ministry", "department", "agency", "firm", "journalists",
    "us", "u.s.", "uk", "u.k.", "european", "american", "british", "australian",
    "indian", "indonesian", "russian", "chinese", "iranian", "korean", "japanese",
    "german", "french", "dutch", "canadian", "african", "asian", "global", "local",
    "national", "international", "major", "windows", "linux", "android",
    # Arah mata angin: "North Korean", "South Asian" bukan nama organisasi
    "north", "south", "east", "west", "northern", "southern", "eastern", "western",
}

# Spasi di dalam nama: bukan baris baru, agar judul seksi di isi artikel
# ("Campaign Overview") tidak menyambung dengan kalimat di bawahnya.
_SP = r"[ \t\u00a0]+"
_NAME_TOKEN = r"[A-Z][\w&.'’-]*"
_NAME_CONNECTOR = r"(?:of|and|&|de|for|the|del|di)"
_ORG_NAME = rf"({_NAME_TOKEN}(?:{_SP}(?:{_NAME_CONNECTOR}{_SP})?{_NAME_TOKEN}){{0,5}})"
_PASSIVE_VERBS = (
    r"(?:(?:was|were|has been|have been|had been|is|are|gets|got)\s+)?"
    r"(?:reportedly\s+|recently\s+|allegedly\s+)?"
    r"(?:hit|attacked|breached|hacked|compromised|targeted|struck|disrupted|"
    r"crippled|paralyzed|paralysed|forced)\b"
)
_SUFFERED_VERBS = (
    r"(?:suffered|suffers|experienced|experiences|confirmed|confirms|disclosed|"
    r"discloses|reported|reports|faced|faces|investigating|investigates|"
    r"responding to|responds to)\s+"
    r"(?:a\s+|an\s+)?(?:[A-Za-z][\w-]*\s+){0,3}?"
    r"(?:cyber|cyber-attack|cyberattack|ransomware|data|security|hack|zero-day|"
    r"zero day|vulnerability|exploitation|breach|attack|incident|intrusion|outage|"
    r"malware|phishing|ddos)\b"
)
_ATTACK_NOUNS = (
    r"(?:cyberattack|cyber attack|cyber-attack|ransomware attack|ransomware|hack|"
    r"data breach|breach|attack|hackers|cybercriminals)"
)
_ACTIVE_VERBS = (
    r"(?:hits|hit|targets|targeted|breaches|breached|attacks|attacked|strikes|"
    r"struck|cripples|crippled|disrupts|disrupted|paralyzes|paralyses|"
    r"compromises|compromised)"
)
_ORGANIZATION_PATTERNS = [
    re.compile(rf"{_ORG_NAME}\s+{_PASSIVE_VERBS}"),
    re.compile(rf"{_ORG_NAME}\s+{_SUFFERED_VERBS}"),
    re.compile(
        rf"{_ATTACK_NOUNS}\s+(?:on\s+|at\s+|against\s+|{_ACTIVE_VERBS}\s+)"
        rf"(?:the\s+)?{_ORG_NAME}"
    ),
]

# Kata pemicu tidak peka huruf besar (?i:...), tetapi nama pelaku harus diawali
# huruf besar agar kata biasa di tengah kalimat tidak ikut tertangkap.
_ACTOR_TERMS = (
    r"(?i:threat actors?|threat groups?|hacking groups?|hacker groups?|"
    r"ransomware groups?|ransomware gangs?|cybercrime groups?|cybercriminal groups?|"
    r"apt groups?|hacktivist groups?|extortion groups?|ransomware operations?)"
)
_ACTOR_NAME = rf"([A-Z][\w-]*(?:{_SP}[A-Z0-9][\w-]*){{0,2}})"
_ACTOR_PATTERNS = [
    re.compile(
        rf"{_ACTOR_TERMS}{_SP}(?i:known as{_SP}|called{_SP}|named{_SP}|dubbed{_SP}|tracked as{_SP})?"
        rf"[\"“']?{_ACTOR_NAME}"
    ),
    re.compile(rf"{_ACTOR_NAME}{_SP}{_ACTOR_TERMS}"),
    # Nama dengan huruf besar di tengah atau angka (LockBit, Cl0p, RansomHub)
    re.compile(rf"([A-Z][a-z]*[A-Z0-9][\w-]*){_SP}(?i:ransomware)\b"),
]


_ADJECTIVE_COMPOUND = re.compile(
    r"-(?:powered|based|linked|backed|sponsored|affiliated|related|driven|aligned|"
    r"nexus|speaking|born|led|owned|made)\b",
    re.I,
)


# --- Pola bahasa Indonesia ---
#
# Judul berita Indonesia memakai Title Case, jadi setiap kata berhuruf besar dan
# batas nama tidak bisa ditebak dari huruf besar saja. Dua penangkal: token nama
# tidak boleh berupa kata kerja/keterangan judul (``_ID_STOP_WORDS``, dicek
# dengan lookahead), dan kata aset atau kelompok di depan nama ("Situs Resmi",
# "Data Nasabah", "Akun Instagram") dibuang setelah tangkapan.
_ID_STOP_WORDS = (
    r"diduga|dikabarkan|disebut|dilaporkan|berhasil|sempat|kembali|resmi|ini|itu|"
    r"tersebut|yang|usai|setelah|pasca|imbas|akibat|karena|gara-gara|soal|terkait|"
    r"hingga|sampai|saat|ketika|kini|lagi|makin|semakin|kian|paling|ternyata|kok|"
    r"bisa|begini|inilah|jadi|menjadi|serang|bobol|retas|jebol|curi|jual|sebar|"
    r"kuasai|lumpuhkan|sadap|bajak|susupi|peras|klaim|mengaku|ancam|incar|akui|"
    r"bantah|sebut|ungkap|bongkar|tangkap|usut|selidiki|dalami|jamin|tolak|cegah|"
    r"gagalkan|tangkal|rebut|imbau|minta|desak|pastikan|benarkan|tegaskan|pulih|"
    r"rugi|merugi|kehilangan|raib|lenyap|hilang|rugikan|terancam|ancam|jutaan|"
    r"ribuan|puluhan|ratusan|juta|ribu|miliar|triliun|sejumlah|beberapa|banyak|"
    r"para|diretas|dibobol|dijebol|diserang|disusupi|dibajak|diperas|dilumpuhkan|"
    r"disadap|dicuri|bocor|kena|terkena|alami|mengalami|korban|sasaran|hacker|"
    r"peretas|pelaku|kelompok|geng|grup|sindikat|serangan|peretasan|pembobolan|"
    r"kebocoran|penipuan|penipu|waspada|awas|hati-hati|jangan|cara|tips|daftar|"
    r"deretan|siapa|apa|mengapa|kenapa|bagaimana|isu|kasus|dugaan|heboh|viral|"
    r"gawat|terjadi|verify|penjual|pembeli|selain|selama|seperti|sehingga|namun|"
    r"tetapi|meski|meskipun|walau|bahkan|juga|yakni|yaitu|adalah|ialah|hanya|"
    r"sudah|telah|masih|akan|bakal|harus|perlu|dapat|mulai|sejak|menurut|kata|"
    r"ujar|tutur|m|t|rp\d+[\w,.]*|"
    # kata kerja berawalan me- yang lazim di judul dan isi berita
    r"membenarkan|membantah|mengakui|menyebut|mengungkap|mengungkapkan|membongkar|"
    r"menangkap|mengusut|menyelidiki|mendalami|menjamin|menolak|mencegah|"
    r"menggagalkan|menangkal|merebut|mengimbau|meminta|mendesak|memastikan|"
    r"menegaskan|mengklaim|menguasai|mencuri|menjual|menyebar|menyerang|membobol|"
    r"meretas|menjebol|menyusupi|membajak|memeras|melumpuhkan|menyadap|mengancam|"
    r"mengincar|merugikan|menghadapi|mendeteksi|melaporkan|mengonfirmasi|"
    r"menemukan|menyatakan|mengatakan|menilai|menduga|memperingatkan|memburu|"
    r"meringkus|membekuk|menetapkan|memblokir|menutup|menghapus|memulihkan|"
    r"mengembalikan|menggunakan|memakai|memanfaatkan|menawarkan|mengirim|menerima|"
    r"membuka|membuat|mengetahui|mengecek|memeriksa|mengamankan|melindungi|"
    r"menyerukan|mengumumkan|menjelaskan|menyampaikan|mengaku"
)
_ID_NAME_TOKEN = rf"(?!(?i:{_ID_STOP_WORDS})\b)[A-Z][\w&.'’-]*"
_ID_CONNECTOR = r"(?:dan|dari|untuk|di|of|and|&)"
_ID_ORG_NAME = rf"({_ID_NAME_TOKEN}(?:{_SP}(?:{_ID_CONNECTOR}{_SP})?{_ID_NAME_TOKEN}){{0,5}})"
_ID_ORG_NAME_SHORT = rf"({_ID_NAME_TOKEN}(?:{_SP}(?:{_ID_CONNECTOR}{_SP})?{_ID_NAME_TOKEN}){{0,3}})"
# Kata aset, kelompok orang, gelar, dan bilangan di depan nama yang dibuang
_ID_STRIP_WORDS = {
    "situs", "web", "website", "laman", "portal", "resmi", "akun", "instagram", "ig",
    "twitter", "x", "facebook", "tiktok", "whatsapp", "wa", "telegram", "email",
    "server", "sistem", "aplikasi", "layanan", "jaringan", "database", "basis",
    "data", "rekening", "nomor", "kamera", "ponsel", "hp", "laptop", "komputer",
    "perangkat", "dokumen", "rahasia", "pribadi", "medis", "akademik", "milik",
    "nasabah", "pelanggan", "konsumen", "pengguna", "pasien", "karyawan", "pegawai",
    "mahasiswa", "siswa", "alumni", "warga", "penduduk", "wajib", "pajak", "wp", "peserta",
    "anggota", "personel", "asn", "pns", "pppk", "jutaan", "ribuan", "puluhan",
    "ratusan", "juta", "ribu", "miliar", "triliun", "sejumlah", "beberapa", "banyak",
    "para", "wakil", "ketua", "kepala", "direktur", "dirut", "ceo", "bos", "menteri",
    "gubernur", "bupati", "walikota", "wali", "kota", "isu", "kasus", "dugaan", "soal",
    "informasi", "info", "kabar", "berita", "insiden", "dana", "uang", "saldo",
    "aset", "kripto", "koin", "token", "dompet", "wallet", "malware", "virus",
    "trojan", "spyware", "ransomware", "android", "aplikasi",
}
# Kata umum Indonesia yang tidak boleh menjadi satu-satunya isi nama
_ID_GENERIC_WORDS = _ID_STRIP_WORDS | {
    "bank", "perusahaan", "pemerintah", "instansi", "lembaga", "kementerian",
    "rumah", "sakit", "kampus", "universitas", "sekolah", "kantor", "dinas",
    "pemkot", "pemkab", "pemprov", "pemda", "kripto", "ip", "internet", "online",
    "digital", "siber", "nasional", "indonesia", "negara", "publik", "swasta",
    "bumn", "startup", "fintech", "e-commerce", "marketplace", "platform", "media",
    "sosial", "game", "mod", "android", "ios", "windows", "iphone", "samsung",
    "asuransi", "koperasi", "fintech", "e-wallet", "dompet", "exchange",
}
# Nama tempat dan wilayah: lokasi, bukan organisasi korban. "Bank Jambi" atau
# "Pemkab Bandung" tetap sah karena ada kata lembaga di depannya; nama yang
# seluruhnya tempat ("Jawa Barat", "Texas") ditolak.
_ID_PLACE_WORDS = {
    "jakarta", "bandung", "surabaya", "medan", "semarang", "makassar", "yogyakarta",
    "jogja", "palembang", "denpasar", "bali", "batam", "malang", "bogor", "depok",
    "tangerang", "bekasi", "jawa", "barat", "tengah", "timur", "utara", "selatan",
    "pusat", "sumatera", "sumatra", "kalimantan", "sulawesi", "papua", "maluku",
    "nusa", "tenggara", "aceh", "riau", "lampung", "banten", "jambi", "bengkulu",
    "jabar", "jateng", "jatim", "sumut", "sumsel", "sulsel", "kaltim", "asia",
    "eropa", "amerika", "afrika", "australia", "dunia", "global", "texas",
    "california", "florida", "new", "york", "london", "moskow", "moscow", "beijing",
    "tokyo", "seoul", "sydney", "washington", "paris", "berlin", "delhi", "mumbai",
    "dubai", "hong", "kong", "silicon", "valley",
}
# Awalan aset/bilangan/kelompok yang dilewati sebelum nama pada pola berkata
# kerja aktif dan kata benda serangan ("Jebol Server Telkomsel",
# "Pembobolan Data Pribadi 341 Ribu Personel Polri")
_ID_ASSET_PREFIX = (
    r"(?:(?i:data|akun|situs|website|server|sistem|jaringan|database|rekening|"
    r"dokumen|dana|aset|layanan|aplikasi)\s+(?:(?i:pribadi|medis|milik|resmi|"
    r"internal|rahasia)\s+)?)?"
    r"(?:\d[\d.,]*\s+(?:(?i:juta|ribu|miliar|triliun)\s+)?)?"
    r"(?:(?i:warga|nasabah|pelanggan|konsumen|pengguna|pasien|karyawan|pegawai|"
    r"mahasiswa|siswa|personel|anggota|penduduk|peserta|wajib\s+pajak)\s+)?"
    r"(?:(?i:di|milik|dari)\s+)?"
)
_ID_PASSIVE = (
    r"(?i:(?:diduga|dikabarkan|disebut|dilaporkan|sempat|kembali|resmi)\s+)?"
    r"(?i:diretas|dibobol|dijebol|diserang|disusupi|dibajak|diperas|dilumpuhkan|"
    r"disadap|dicuri|diacak-acak|bocor|jebol|kena\s+hack|kena\s+retas|"
    r"kena\s+serangan|terkena\s+serangan|(?:jadi|menjadi)\s+(?:korban|sasaran)|"
    r"(?:alami|mengalami)\s+(?:serangan|peretasan|kebocoran|pembobolan|gangguan|"
    r"insiden))\b"
)
_ID_ATTACK_NOUNS = (
    r"(?i:(?:dugaan\s+|upaya\s+)?(?:peretasan|pembobolan|kebocoran|serangan\s+siber|"
    r"serangan\s+ransomware|serangan\s+ddos|serangan\s+phishing|insiden\s+siber))"
)
_ID_ACTIVE_VERBS = (
    r"(?i:(?:diduga|dikabarkan|berhasil|sempat|kembali|klaim|mengklaim|mengaku)\s+)?"
    r"(?i:jebol|bobol|retas|serang|susupi|bajak|curi|kuasai|lumpuhkan|sadap|"
    r"menjebol|membobol|meretas|menyerang|menyusupi|membajak|mencuri|menguasai|"
    r"melumpuhkan|menyadap)\s+"
)
_ID_STATEMENT_VERBS = (
    r"(?i:bantah|membantah|akui|mengakui|sebut|menyebut|konfirmasi|mengonfirmasi|"
    r"pastikan|memastikan|benarkan|membenarkan|ungkap|mengungkap|laporkan|"
    r"melaporkan|cegah|mencegah|gagalkan|menggagalkan|tangkal|menangkal|hadapi|"
    r"menghadapi|deteksi|mendeteksi|alami|mengalami|tegaskan|menegaskan)\s+"
)
_ID_INCIDENT_WORDS = (
    r"(?i:peretasan|pembobolan|kebocoran|serangan|diretas|dibobol|bocor|jebol|"
    r"dijebol|dibajak|disusupi|ransomware|phishing|insiden\s+siber|upaya\s+peretasan)"
)
_ORGANIZATION_PATTERNS_ID = [
    # "Bank Jambi Dibobol Hacker", "Situs PeduliLindungi Diretas", "Bybit Kena Hack"
    re.compile(rf"{_ID_ORG_NAME}\s+{_ID_PASSIVE}"),
    # "Hacker Diduga Jebol Server Telkomsel", "Hacker Klaim Kuasai Data ... Jawa Barat"
    re.compile(
        rf"(?i:hacker|peretas|pelaku|penjahat\s+siber|kelompok\s+\w+|geng\s+\w+)\s+"
        rf"{_ID_ACTIVE_VERBS}{_ID_ASSET_PREFIX}{_ID_ORG_NAME}"
    ),
    # "Kebocoran Data dan Penerbitan Kartu Kredit Fiktif ... di Bank UOB Indonesia"
    re.compile(
        rf"{_ID_ATTACK_NOUNS}\s+(?:[^\s.]+\s+){{0,8}}?(?i:di|pada|terhadap|menimpa)\s+"
        rf"{_ID_ASSET_PREFIX}{_ID_ORG_NAME_SHORT}"
    ),
    # "Peretasan Jaguar Land Rover Rugikan ...", "Pembobolan Data Pribadi 341 Ribu Personel Polri"
    re.compile(
        rf"{_ID_ATTACK_NOUNS}\s+(?:(?i:terhadap|pada|di|ke|menimpa|yang\s+menimpa|"
        rf"dialami)\s+)?{_ID_ASSET_PREFIX}{_ID_ORG_NAME_SHORT}"
    ),
    # "ITB Sebut Data Mahasiswa Bocor", "Starbucks Akui Kebocoran Data",
    # "Ecopetrol cegah serangan ransomware"
    re.compile(
        rf"{_ID_ORG_NAME}\s+{_ID_STATEMENT_VERBS}(?:[^\s.]+\s+){{0,6}}?{_ID_INCIDENT_WORDS}"
    ),
    # "Venus Protocol Pulih Rp205 M Setelah Serangan Phishing"
    re.compile(
        rf"{_ID_ORG_NAME}\s+(?:[^\s.]+\s+){{0,4}}?(?i:setelah|usai|akibat|imbas|pasca|"
        rf"pascaserangan|karena)\s+{_ID_INCIDENT_WORDS}"
    ),
]
# Subjek pola pernyataan yang lazimnya penyidik atau pengamat, bukan korban
_ID_REPORTER_WORDS = {
    "polda", "polres", "polsek", "polri", "polisi", "bareskrim", "ditressiber",
    "ditreskrimsus", "satgas", "bssn", "komdigi", "kominfo", "kemkomdigi", "ojk",
    "kpk", "ppatk", "fbi", "interpol", "europol", "pakar", "praktisi", "pengamat",
    "peneliti", "analis", "menteri", "menkeu", "menkominfo", "wamen", "presiden",
    "gubernur", "walikota", "bupati", "dpr", "dprd", "mpr", "komisi", "anggota",
    "ketua", "kapolri", "kapolda", "kapolres", "kabid", "kadis", "kadiskominfo",
    "kepala", "dirjen", "kejari", "kejati", "kejaksaan", "pengadilan", "hakim",
    "jaksa", "bpk", "bpkp", "ombudsman", "kaspersky", "eset", "microsoft", "google",
    "cisa",
}
_ID_STATEMENT_PATTERN_INDEX = 4

_ACTOR_TERMS_ID = (
    r"(?i:kelompok\s+(?:hacker|peretas|ransomware|hacktivis|siber|apt)|"
    r"geng\s+(?:ransomware|hacker)|grup\s+(?:hacker|ransomware)|"
    r"sindikat\s+(?:hacker|ransomware|siber)|kolektif\s+(?:hacker|peretas))"
)
_ACTOR_PATTERNS_ID = [
    # "kelompok hacker Bjorka", "geng ransomware asal Rusia bernama Qilin"
    re.compile(
        rf"{_ACTOR_TERMS_ID}{_SP}(?:(?i:asal|dari){_SP}\w+{_SP})?"
        rf"(?:(?i:bernama|berjuluk|dijuluki|berinisial|yang{_SP}menamakan{_SP}diri){_SP})?"
        rf"[\"“']?{_ACTOR_NAME}"
    ),
    # "hacker bernama Zyaire", "peretas yang mengaku sebagai DigitalGhostt"
    re.compile(
        rf"(?i:hacker|peretas|pelaku){_SP}(?i:bernama|berjuluk|dijuluki|berinisial|"
        rf"beridentitas|dengan{_SP}nama|yang{_SP}menamakan{_SP}diri|"
        rf"yang{_SP}mengaku{_SP}sebagai){_SP}[\"“']?{_ACTOR_NAME}"
    ),
    # "Hacker 'Gajah Misterius'", 'dengan nama akun "DigitalGhostt"': julukan dalam tanda kutip
    re.compile(
        rf"(?i:hacker|peretas|akun|nama{_SP}akun|dengan{_SP}nama|julukan|alias){_SP}"
        rf"[\"“']{_ACTOR_NAME}[\"”']"
    ),
    # "Bjorka Mengaku Bertanggung Jawab", "DigitalGhostt klaim menguasai data"
    re.compile(
        rf"{_ACTOR_NAME}{_SP}(?i:mengaku|mengklaim|klaim){_SP}(?i:bertanggung{_SP}jawab|"
        rf"meretas|membobol|menguasai|mencuri|memiliki|telah|sudah)"
    ),
]


_ID_LEADING_CONNECTORS = {"dan", "dari", "untuk", "di", "&", "and", "of"}


def _strip_leading_id(words):
    """Buang kata aset/kelompok/gelar Indonesia di awal nama (termasuk bentuk -nya).

    Kata sambung yang tersisa di depan ("Data ASN dan PPPK" -> "dan PPPK") ikut
    dibuang, lalu penyaringan diulang.
    """
    while words:
        word = words[0].lower().strip("?!,:;'\"“”’")
        if word in _ID_LEADING_CONNECTORS or word in _ID_STRIP_WORDS:
            words.pop(0)
        elif word.endswith("nya") and word[:-3] in _ID_STRIP_WORDS:
            words.pop(0)
        else:
            break
    return words


def _clean_name_id(name):
    """Rapikan nama hasil pola Indonesia; None bila tinggal kata umum saja."""
    words = _strip_leading_id(re.sub(r"\s+", " ", name).strip(" .,;:'\"“”’-").split())
    if not words:
        return None
    cleaned = _clean_name(" ".join(words))
    if cleaned is None:
        return None
    lowered = [word.lower() for word in cleaned.split()]
    if all(word in _ID_GENERIC_WORDS or word in _ID_LEADING_CONNECTORS for word in lowered):
        return None
    if all(word in _ID_PLACE_WORDS or word in _ID_LEADING_CONNECTORS for word in lowered):
        return None
    return cleaned


def _clean_name(name):
    """Rapikan nama hasil regex; None bila bukan nama (kata umum saja)."""
    name = re.sub(r"\s+", " ", name).strip(" .,;:'\"“”’-")
    words = name.split()
    while words and words[0].lower() in _ARTICLES:
        words.pop(0)
    # Kata sandang di akhir berasal dari kalimat berikutnya ("for Sale A threat actor")
    while words and words[-1].lower() in _ARTICLES:
        words.pop()
    if not words or words[0].lower() in _REJECT_FIRST_WORDS:
        return None
    if all(word.lower() in _GENERIC_NAME_WORDS for word in words):
        return None
    # "AI-powered", "China-based", "North Korea-linked", "Russian-aligned": kata
    # sifat majemuk di mana pun posisinya berarti ini keterangan, bukan nama
    if any(_ADJECTIVE_COMPOUND.search(word) for word in words):
        return None
    return " ".join(words)


# --- Ekstraksi berbasis regex ---
def extract_threat_actor(raw_text):
    """Ekstrak nama pelaku ancaman dari teks asli (huruf besar dipertahankan)."""
    actors = []
    known = drop_overlapping_keywords(find_keywords(raw_text, KNOWN_THREAT_ACTORS))
    for name in known:
        actors.append(re.sub(r"\s+ransomware$", "", name))

    for pattern in _ACTOR_PATTERNS + _ACTOR_PATTERNS_ID:
        for match in pattern.finditer(raw_text):
            name = _clean_name(match.group(1))
            if name and name.lower() in _COUNTRY_WORDS:
                name = None  # "kelompok hacker Indonesia": kebangsaan, bukan nama
            if name and name.lower() not in {a.lower() for a in actors}:
                actors.append(name[:100])
            if len(actors) >= 3:
                break

    if not actors:
        return "UNKNOWN"
    return ", ".join(actors[:3])


_COUNTRY_WORDS = {name.lower() for name in COUNTRY_NAMES} | {
    keyword.lower() for keywords in COUNTRY_NAMES.values() for keyword in keywords
}


def _first_organization(text):
    """Nama organisasi pertama yang cocok pola serangan di satu teks; None bila tidak ada.

    Pola Inggris dicoba dulu, lalu pola Indonesia. Kata kerja tiap bahasa tidak
    muncul di bahasa lain, jadi keduanya aman dijalankan pada semua artikel.
    """
    for pattern in _ORGANIZATION_PATTERNS:
        for match in pattern.finditer(text):
            name = _clean_name(match.group(1))
            if name and name.lower() not in _COUNTRY_WORDS:
                return name[:150]
    for index, pattern in enumerate(_ORGANIZATION_PATTERNS_ID):
        for match in pattern.finditer(text):
            name = _clean_name_id(match.group(1))
            if not name or name.lower() in _COUNTRY_WORDS:
                continue
            first_word = re.split(r"[-/]", name.split()[0].lower())[0]
            if index == _ID_STATEMENT_PATTERN_INDEX and first_word in _ID_REPORTER_WORDS:
                continue  # "Polda Jambi Sebut ...": penyidik, bukan korban
            return name[:150]
    return None


def extract_target_organization(headline, summary, content=""):
    """Ekstrak nama organisasi target dari judul, lalu ringkasan, lalu isi artikel.

    Nama negara tidak dihitung sebagai organisasi; itu urusan extract_location.
    """
    return extract_target_organization_tiered(headline, summary, content)[0]


# Keyakinan berdasarkan tempat nama ditemukan: judul paling dapat dipercaya,
# isi artikel paling rendah karena bisa menyebut organisasi lain yang dikutip.
TIER_CONFIDENCE = {"headline": 0.9, "summary": 0.8, "content": 0.6}
CONTENT_SCAN_CHARS = 3000  # bagian awal isi artikel yang dipindai regex


def extract_target_organization_tiered(headline, summary, content=""):
    """(nama organisasi, keyakinan) dari judul, ringkasan, lalu isi artikel."""
    tiers = (
        ("headline", headline or ""),
        ("summary", summary or ""),
        ("content", (content or "")[:CONTENT_SCAN_CHARS]),
    )
    for tier, text in tiers:
        if text:
            name = _first_organization(text)
            if name:
                return name, TIER_CONFIDENCE[tier]
    return "UNKNOWN", 0.0


def extract_threat_actor_tiered(headline, summary, content=""):
    """(pelaku, keyakinan): dicari di judul dulu, lalu ringkasan, lalu isi artikel."""
    tiers = (
        ("headline", headline or ""),
        ("summary", f"{headline or ''}. {summary or ''}"),
        ("content", f"{headline or ''}. {summary or ''} {(content or '')[:CONTENT_SCAN_CHARS]}"),
    )
    for tier, text in tiers:
        actor = extract_threat_actor(text)
        if actor != "UNKNOWN":
            return actor, TIER_CONFIDENCE[tier]
    return "UNKNOWN", 0.0


def _valid_date(year, month, day):
    """'YYYY-MM-DD' bila tanggal valid, selain itu None."""
    try:
        return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
    except ValueError:
        return None


def extract_attack_date(text):
    """Ekstrak tanggal serangan yang valid, dinormalisasi ke YYYY-MM-DD."""
    for match in re.finditer(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text):
        date = _valid_date(match.group(1), match.group(2), match.group(3))
        if date:
            return date
    for match in re.finditer(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", text):
        first, second, year = match.group(1), match.group(2), match.group(3)
        # Diasumsikan d/m/Y (lazim di Indonesia); m/d/Y bila d/m/Y tidak valid.
        date = _valid_date(year, second, first) or _valid_date(year, first, second)
        if date:
            return date
    return "UNKNOWN"


def extract_indicators(text):
    """Ekstrak indikator (CVE dan hash MD5/SHA1/SHA256) tanpa duplikat."""
    indicators = []
    for match in re.findall(r"\bCVE-\d{4}-\d{4,7}\b", text, re.IGNORECASE):
        indicators.append(match.upper())
    for pattern in (r"\b[A-Fa-f0-9]{32}\b", r"\b[A-Fa-f0-9]{40}\b", r"\b[A-Fa-f0-9]{64}\b"):
        indicators.extend(match.lower() for match in re.findall(pattern, text))
    indicators = list(dict.fromkeys(indicators))
    if not indicators:
        return "UNKNOWN"
    return ", ".join(indicators)


def calculate_extraction_confidence(
    attack_type, attack_method, target_sector, location, impact
):
    """Hitung proporsi field utama yang berhasil diekstrak (bukan UNKNOWN)."""
    fields = [attack_type, attack_method, target_sector, location, impact]
    known_fields = 0
    for field in fields:
        if field != "UNKNOWN":
            known_fields += 1
    confidence = known_fields / len(fields)
    return round(confidence, 4)


def _keyword_confidence(value, title_value):
    """Keyakinan field kata kunci: 0.9 bila juga cocok di judul, 0.7 bila hanya di teks lain."""
    if value == "UNKNOWN":
        return 0.0
    return 0.9 if title_value != "UNKNOWN" else 0.7


def extract_information(article_id, title, summary, content):
    """Ekstrak seluruh field informasi dari satu artikel beserta keyakinan per field.

    Isi artikel penuh (bila sudah diambil content_fetcher) ikut dipindai;
    tanpa isi, ekstraksi bekerja pada judul dan ringkasan saja.
    """
    title_text = normalize_text(title)
    summary_text = normalize_text(summary)
    content_text = normalize_text(content)
    combined_text = f"{title_text} {summary_text} {content_text}".strip()

    attack_type = extract_attack_type(combined_text)
    attack_method = extract_attack_method(combined_text)
    target_sector = extract_target_sector(combined_text)
    target_group = extract_target_group(combined_text)
    location = extract_location(combined_text)
    impact = extract_impact(combined_text)
    attack_date = extract_attack_date(combined_text)
    indicators = extract_indicators(combined_text)

    # Teks asli (huruf besar dipertahankan) tanpa nama media Google News
    headline, publisher = split_publisher(title)
    raw_summary = remove_publisher(summary, publisher)
    threat_actor, actor_confidence = extract_threat_actor_tiered(
        headline, raw_summary, content
    )
    target_organization, target_confidence = extract_target_organization_tiered(
        headline, raw_summary, content
    )

    extraction_confidence = calculate_extraction_confidence(
        attack_type, attack_method, target_sector, location, impact
    )
    field_confidence = {
        "attack_type": _keyword_confidence(attack_type, extract_attack_type(title_text)),
        "attack_method": _keyword_confidence(
            attack_method, extract_attack_method(title_text)
        ),
        "target": target_confidence,
        "target_sector": _keyword_confidence(
            target_sector, extract_target_sector(title_text)
        ),
        "target_group": _keyword_confidence(target_group, extract_target_group(title_text)),
        "location": _keyword_confidence(location, extract_location(title_text)),
        "attack_date": 0.5 if attack_date != "UNKNOWN" else 0.0,
        "threat_actor": actor_confidence,
        "impact": _keyword_confidence(impact, extract_impact(title_text)),
        "indicator": 0.9 if indicators != "UNKNOWN" else 0.0,
    }

    return {
        "article_id": article_id,
        "attack_type": attack_type,
        "attack_method": attack_method,
        "target": target_organization,
        "target_organization": target_organization,
        "target_sector": target_sector,
        "target_group": target_group,
        "location": location,
        "attack_date": attack_date,
        "threat_actor": threat_actor,
        "impact": impact,
        "indicator": indicators,
        "extraction_confidence": extraction_confidence,
        "field_confidence": field_confidence,
        "extraction_method": "RULE_BASED",
    }


# --- Database ---
def initialize_v03_database():
    """Buat tabel dan indeks V0.3 bila belum ada."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS v03_information_extraction (
            article_id INTEGER PRIMARY KEY,
            attack_type TEXT,
            attack_method TEXT,
            target TEXT,
            target_organization TEXT,
            target_sector TEXT,
            target_group TEXT,
            location TEXT,
            attack_date TEXT,
            threat_actor TEXT,
            impact TEXT,
            indicator TEXT,
            extraction_confidence REAL,
            extraction_method TEXT,
            extracted_at TEXT
        )
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_v03_attack_type
        ON v03_information_extraction(attack_type)
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_v03_location
        ON v03_information_extraction(location)
        """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_v03_target_sector
        ON v03_information_extraction(target_sector)
        """)
    connection.commit()
    ensure_column(connection, "v03_information_extraction", "pipeline_version", "TEXT")
    ensure_column(connection, "v03_information_extraction", "field_confidence", "TEXT")
    connection.close()


def get_total_candidates():
    """Hitung jumlah artikel kandidat V0.2 (RELEVANT atau UNCERTAIN)."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM articles a
        INNER JOIN v02_relevance v
            ON a.article_id = v.article_id
        WHERE v.relevance_label IN ('RELEVANT', 'UNCERTAIN')
        """)
    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_analyzed_articles():
    """Hitung jumlah artikel yang sudah diekstrak oleh V0.3."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM v03_information_extraction")
    total = cursor.fetchone()[0]
    connection.close()
    return total


def get_remaining_candidates():
    """Hitung kandidat V0.2 yang belum diekstrak oleh V0.3."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(f"""
        SELECT COUNT(*)
        FROM v02_relevance v
        JOIN articles a ON a.article_id = v.article_id
        LEFT JOIN v03_information_extraction x ON v.article_id = x.article_id
        WHERE v.relevance_label IN ('RELEVANT', 'UNCERTAIN')
            AND ({_NEEDS_EXTRACTION})
        """)
    total = cursor.fetchone()[0]
    connection.close()
    return total


# Artikel perlu (di)ekstrak bila belum pernah, atau isi penuhnya baru diambil
# setelah ekstraksi terakhir (INSERT OR REPLACE memperbarui barisnya).
_NEEDS_EXTRACTION = (
    "x.article_id IS NULL OR (a.content_status = 'ok' "
    "AND a.content_fetched_at > x.extracted_at)"
)


def get_next_batch():
    """Ambil batch artikel kandidat V0.2 yang belum (atau perlu ulang) diekstrak."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        f"""
        SELECT
            a.article_id,
            a.title,
            a.summary,
            a.content,
            a.language,
            v.relevance_label,
            v.relevance_score
        FROM articles a
        INNER JOIN v02_relevance v
            ON a.article_id = v.article_id
        LEFT JOIN v03_information_extraction x
            ON a.article_id = x.article_id
        WHERE v.relevance_label IN ('RELEVANT', 'UNCERTAIN')
            AND ({_NEEDS_EXTRACTION})
        ORDER BY a.article_id
        LIMIT ?
        """,
        (BATCH_SIZE,),
    )
    rows = cursor.fetchall()
    connection.close()
    return rows


def save_extraction(cursor, result):
    """Simpan hasil ekstraksi satu artikel lewat cursor batch (tanpa commit)."""
    extracted_at = get_timestamp()
    cursor.execute(
        """
        INSERT OR REPLACE INTO v03_information_extraction (
            article_id,
            attack_type,
            attack_method,
            target,
            target_organization,
            target_sector,
            target_group,
            location,
            attack_date,
            threat_actor,
            impact,
            indicator,
            extraction_confidence,
            extraction_method,
            extracted_at,
            pipeline_version,
            field_confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result["article_id"],
            result["attack_type"],
            result["attack_method"],
            result["target"],
            result["target_organization"],
            result["target_sector"],
            result["target_group"],
            result["location"],
            result["attack_date"],
            result["threat_actor"],
            result["impact"],
            result["indicator"],
            result["extraction_confidence"],
            result["extraction_method"],
            extracted_at,
            pipeline_stamp(),
            json.dumps(result["field_confidence"]),
        ),
    )


def process_batch(rows):
    """Ekstrak dan simpan informasi satu batch artikel dalam satu transaksi."""
    processed = 0
    connection = get_connection()
    cursor = connection.cursor()
    for row in rows:
        article_id = row[0]
        title = row[1] or ""
        summary = row[2] or ""
        content = row[3] or ""
        language = row[4] or "unknown"
        relevance_label = row[5] or "UNKNOWN"
        relevance_score = row[6] or 0.0

        result = extract_information(article_id, title, summary, content)
        save_extraction(cursor, result)
        processed += 1

        # Tampilkan contoh hasil untuk 10 artikel pertama
        if processed <= 10:
            print(f"\n[{processed}] Article ID : {article_id}")
            print(f"    Language       : {language}")
            print(f"    V0.2 Relevance : {relevance_label}")
            print(f"    V0.2 Score     : {relevance_score:.2f}")
            print(f"    Title          : {title[:120]}")
            print(f"    Attack Type    : {result['attack_type']}")
            print(f"    Attack Method  : {result['attack_method']}")
            print(f"    Target         : {result['target']}")
            print(f"    Sector         : {result['target_sector']}")
            print(f"    Location       : {result['location']}")
            print(f"    Impact         : {result['impact']}")
            print(f"    Confidence     : {result['extraction_confidence']:.2f}")

    connection.commit()
    connection.close()
    return processed


def get_v03_summary():
    """Ambil 15 jenis serangan dan 15 sektor target terbanyak."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT attack_type, COUNT(*)
        FROM v03_information_extraction
        GROUP BY attack_type
        ORDER BY COUNT(*) DESC
        LIMIT 15
        """)
    attack_rows = cursor.fetchall()
    cursor.execute("""
        SELECT target_sector, COUNT(*)
        FROM v03_information_extraction
        GROUP BY target_sector
        ORDER BY COUNT(*) DESC
        LIMIT 15
        """)
    sector_rows = cursor.fetchall()
    connection.close()
    return attack_rows, sector_rows


# --- Program utama ---
def run():
    """Jalankan V0.3: ekstraksi informasi untuk semua kandidat V0.2."""
    print("\n==================================================")
    print("   CSAIS V0.3 - INFORMATION EXTRACTION")
    print("==================================================")

    # Cek database
    if not os.path.exists(DATABASE_FILE):
        print("\n❌ Database tidak ditemukan:")
        print(f"   {DATABASE_FILE}")
        return

    started_at = get_timestamp()
    initialize_v03_database()
    connection = get_connection()
    ensure_content_columns(connection)  # kolom content_status dipakai kueri batch
    connection.close()

    # Ringkasan database
    total_candidates = get_total_candidates()
    analyzed_articles = get_analyzed_articles()
    print(f"\nTotal V0.2 candidates : {total_candidates}")
    print(f"Sudah dianalisis     : {analyzed_articles}")
    print(f"Belum dianalisis     : {get_remaining_candidates()}")

    # Proses artikel per batch
    total_processed = 0
    while True:
        rows = get_next_batch()
        if not rows:
            break
        processed = process_batch(rows)
        total_processed += processed
        print(f"\nBatch processed : {processed}")
        print(f"Total processed : {total_processed}")

    # Ringkasan akhir
    attack_rows, sector_rows = get_v03_summary()
    final_total = get_analyzed_articles()

    print("\n==================================================")
    print("   V0.3 ANALYSIS SUMMARY")
    print("==================================================")
    print(f"\nTotal candidates : {total_candidates}")
    print(f"Total extracted  : {final_total}")

    print("\nTOP ATTACK TYPES")
    print("--------------------------------------------------")
    for attack_type, count in attack_rows:
        print(f"{attack_type:<35} {count}")

    print("\nTOP TARGET SECTORS")
    print("--------------------------------------------------")
    for sector, count in sector_rows:
        print(f"{sector:<35} {count}")

    connection = get_connection()
    record_run(connection, "v03_information_extraction", started_at, total_processed)
    connection.close()

    print("\n==================================================")
    print("   ✅ V0.3 INFORMATION EXTRACTION SELESAI")
    print("==================================================")


if __name__ == "__main__":
    run()
