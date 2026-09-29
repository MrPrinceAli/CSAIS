"""Uji incident terkait: teks incident, tetangga dalam jendela waktu, aturan kejadian sama."""

import pytest

np = pytest.importorskip("numpy")

from csais import related  # noqa: E402


def test_incident_texts_uses_anchor_and_other_headlines():
    incidents = [("I1", 2, "2026-09-01", "id")]
    docs = [("I1", 1, "Judul lain - A", "x"), ("I1", 2, "Judul jangkar - Kompas", "Ringkasan jangkar Kompas"), ("I1", 3, "Judul jangkar - Detik", "")]
    item = related.incident_texts(incidents, docs)["I1"]
    assert item["text"].startswith("Judul jangkar. Judul lain")
    assert "Ringkasan jangkar" in item["text"]


def test_neighbors_window_and_same_event():
    items = {
        "A": {"published": "2026-09-01", "language": "en"},
        "B": {"published": "2026-09-02", "language": "id"},  # lintas bahasa, dekat
        "C": {"published": "2026-12-30", "language": "en"},  # di luar jendela 60 hari
        "D": {"published": "2026-09-01", "language": "en"},
    }
    vectors = np.array([[1, 0, 0], [0.93, 0.37, 0], [1, 0, 0], [0.5, 0.87, 0]], dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    links = related.neighbors(list(items), vectors, items, top_k=2)
    pairs = {(a, b) for a, b, _, _ in links}
    assert ("A", "B") in pairs and ("A", "C") not in pairs and ("A", "D") not in pairs
    rows = related.link_rows(links, items, "m", "t")
    ab = next(r for r in rows if r[:2] == ("A", "B"))
    assert ab[3] == 1 and ab[4] == 1  # kemungkinan kejadian sama, lintas bahasa


def test_embeddings_cache_skips_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(related, "CACHE_FILE", str(tmp_path / "emb.db"))
    monkeypatch.setattr(related, "DATABASE_DIR", str(tmp_path))
    calls = []

    def fake(texts, model, base_url):
        calls.append(len(texts))
        return [[float(len(t)), 1.0] for t in texts]

    items = {"A": {"text": "satu"}, "B": {"text": "dua"}}
    related.embeddings(items, "m", "u", log=lambda *_: None, embed=fake)
    related.embeddings(items, "m", "u", log=lambda *_: None, embed=fake)
    items["B"]["text"] = "dua berubah"
    ids, matrix = related.embeddings(items, "m", "u", log=lambda *_: None, embed=fake)
    assert calls == [2, 1] and matrix.shape == (2, 2)
