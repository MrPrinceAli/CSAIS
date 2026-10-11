"""Uji pengenal wilayah Indonesia dan kelompok masyarakat (Peta Literasi)."""

import pytest

from csais import flows, regions


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Polres Malang ungkap penipuan online", {("35", "35.73")}),
        ("Nasib Malang Korban Pinjol", set()),  # kata umum tanpa penanda wilayah
        ("Serangan siber di Jabar dan DIY", {("32", None), ("34", None)}),
        ("Warga Jakarta Selatan tertipu", {("31", "31.74")}),
        ("Polda Metro Jaya tutup aplikasi", {("31", None)}),
        ("Papua Nugini diserang hacker", set()),
        ("Satreskrim Polres Kulonprogo bongkar penipuan", {("34", "34.01")}),
        ("Situs Pemkab Banjarnegara diretas", {("33", "33.04")}),
    ],
)
def test_find_regions(text, expected):
    assert set(regions.find_regions(text)) == expected


def test_find_communities():
    found = regions.find_communities("Siswa SMP dan pengurus ormas di desa jadi korban; kepala desa melapor")
    assert {"pelajar_smp", "pengurus_ormas", "perangkat_desa"} <= set(found)
    assert "pelajar_sma" not in regions.find_communities("Smp")  # singkatan harus huruf besar


def test_gazetteer_has_all_provinces():
    assert len(regions.WILAYAH["provinsi"]) == 38 and len(regions.WILAYAH["kabkota"]) == 514
    assert regions.province_name("31") == "DKI Jakarta"


def _tables(conn):
    conn.execute("CREATE TABLE v05_incidents (incident_id TEXT, location TEXT)")
    conn.execute("CREATE TABLE v05_incident_documents (incident_id TEXT, article_id INTEGER)")
    conn.execute("CREATE TABLE articles (article_id INTEGER, title TEXT, summary TEXT, content TEXT, language TEXT)")
    conn.executemany("INSERT INTO v05_incidents VALUES (?, ?)", [("A", None), ("B", None), ("C", "india")])
    docs = [
        ("A", 1, "Penipuan online di Surabaya - Koran Jakarta", "Ringkasan - Koran Jakarta", None, "id"),
        ("A", 2, "Polisi tangkap pelaku", "Berita lain: banjir di Lampung", "Korban siswa SMP di Surabaya", "id"),
        ("B", 3, "Data bocor", "Lampung dan Bali", None, "id"),
        ("B", 4, "Data bocor lagi", "Lampung", None, "id"),
        ("C", 5, "Bank in Bali hacked", "", None, "en"),  # bukan incident Indonesia
    ]
    for incident_id, article_id, title, summary, content, language in docs:
        conn.execute("INSERT INTO v05_incident_documents VALUES (?, ?)", (incident_id, article_id))
        conn.execute("INSERT INTO articles VALUES (?, ?, ?, ?, ?)", (article_id, title, summary, content, language))
    conn.commit()


def test_incident_context_and_store(temp_conn):
    _tables(temp_conn)
    context = regions.incident_context(temp_conn)
    assert set(context) == {"A", "B"}
    a_regions, a_communities = context["A"]
    # nama media (Koran Jakarta) dan wilayah yang hanya di satu ringkasan (Lampung) tidak dihitung
    assert set(a_regions) == {("35", "35.78")} and a_regions[("35", "35.78")] == 2
    assert "pelajar_smp" in a_communities
    # B: Lampung disebut ringkasan dua artikel, Bali hanya satu
    assert set(context["B"][0]) == {("18", None)}
    assert regions.store(temp_conn, context) == (2, 1)
    assert regions.communities_by_incident(temp_conn) == {"A": ["pelajar_smp"]}
    rows = temp_conn.execute("SELECT province, kabkota FROM incident_regions WHERE incident_id = 'A'").fetchall()
    assert rows == [("Jawa Timur", "Kota Surabaya")]


def test_communities_lead_literacy_audience():
    plan = flows.literacy_for("STUDENTS", ["phishing"], communities=["pelajar_smp", "bukan_kunci"])
    assert plan["audience"] == ["pelajar_smp", "pelajar_sma", "mahasiswa"]
