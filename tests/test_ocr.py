from app.ocr import parse_ine_text


def test_parse_fictitious_ine_text():
    text = """INSTITUTO NACIONAL ELECTORAL
NOMBRE
PRUEBA LOPEZ ANA
DOMICILIO
CALLE FICTICIA 123 COL CENTRO
CURP PULA900101MDFRPN09
CLAVE DE ELECTOR PRLBAN90010109M100
VIGENCIA 2026-2036"""
    data = parse_ine_text(text)
    assert data["name"] == "PRUEBA LOPEZ ANA"
    assert data["curp"] == "PULA900101MDFRPN09"
    assert data["voter_key"] == "PRLBAN90010109M100"
    assert data["valid_until"] == "2026-2036"


def test_empty_text_does_not_invent_data():
    assert parse_ine_text("texto ilegible") == {"name": "", "address": "", "curp": "", "voter_key": "", "valid_until": ""}

