

def test_media_is_not_threat_actor():
    from csais import v03_information_extraction as v

    text = "Kelompok peretas ShinyHunters mengklaim membobol FBI. Seorang reporter BBC News mengaku telah melihat sampel data."
    assert v.extract_threat_actor(text) == "ShinyHunters"
    assert v.extract_threat_actor("Kompas TV mengaku telah menerima pesan.") == "UNKNOWN"
    assert v.extract_threat_actor("Bjorka Mengaku Bertanggung Jawab atas kebocoran data") == "Bjorka"


def test_publisher_suffix_is_not_location():
    from csais import v03_information_extraction as v

    result = v.extract_information(1, "Kelompok peretas mengklaim membobol FBI - vietnam.vn", "Kelompok peretas mengklaim membobol FBI vietnam.vn", "")
    assert "vietnam" not in result["location"].lower()
