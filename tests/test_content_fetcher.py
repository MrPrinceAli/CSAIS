"""Pengujian csais/content_fetcher.py: ekstraksi gambar utama artikel (tanpa jaringan)."""

from csais import content_fetcher as cf


def test_extract_image_url_prefers_open_graph_and_makes_absolute():
    html = """
    <html><head>
      <meta name="twitter:image" content="/img/tw.jpg">
      <meta property="og:image" content="//cdn.example.com/hero.jpg?w=1200">
    </head></html>
    """
    assert cf.extract_image_url(html, "https://www.example.com/berita/1") == "https://cdn.example.com/hero.jpg?w=1200"


def test_extract_image_url_falls_back_to_twitter_and_relative_paths():
    html = '<meta content="/foto/utama.png" name="twitter:image:src" />'
    assert cf.extract_image_url(html, "https://media.id/artikel/x") == "https://media.id/foto/utama.png"


def test_extract_image_url_rejects_missing_or_non_http():
    assert cf.extract_image_url("<meta property='og:title' content='x'>", "https://a.id/") is None
    assert cf.extract_image_url("<meta property='og:image' content='data:image/png;base64,xx'>", "https://a.id/") is None
    assert cf.extract_image_url("", "https://a.id/") is None
