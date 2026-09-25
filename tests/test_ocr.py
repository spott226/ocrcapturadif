from app.ocr import parse_ine_text


def test_parse_fictitious_ine_text():
    text = """INSTITUTO NACIONAL ELECTORAL
NOMBRE
PRUEBA LOPEZ ANA
DOMICILIO
CALLE FICTICIA 123 COL CENTRO
CURP PULA900101MDFRPN09
CLAVE DE ELECTOR PRLBAN90010109M100
FECHA DE NACIMIENTO 01/01/1990
SEXO M
ESTADO 09
MUNICIPIO 010
SECCIÓN 1234
LOCALIDAD 0001
AÑO DE REGISTRO 2010 00
EMISIÓN 2026
CIC 123456789
OCR 1234567890123
VIGENCIA 2026-2036"""
    data = parse_ine_text(text)
    assert data["name"] == "PRUEBA LOPEZ ANA"
    assert data["curp"] == "PULA900101MDFRPN09"
    assert data["voter_key"] == "PRLBAN90010109M100"
    assert data["birth_date"] == "01/01/1990"
    assert data["sex_or_gender"] == "M"
    assert data["state_code"] == "09"
    assert data["municipality_code"] == "010"
    assert data["section"] == "1234"
    assert data["locality_code"] == "0001"
    assert data["registration_year"] == "201000"
    assert data["issue_year"] == "2026"
    assert data["cic"] == "123456789"
    assert data["ocr_code"] == "1234567890123"
    assert data["valid_until"] == "2026-2036"


def test_empty_text_does_not_invent_data():
    assert parse_ine_text("texto ilegible") == {
        "name": "", "address": "", "curp": "", "voter_key": "",
        "birth_date": "", "sex_or_gender": "", "state_code": "",
        "municipality_code": "", "section": "", "locality_code": "",
        "registration_year": "", "issue_year": "", "cic": "",
        "ocr_code": "", "valid_until": "",
    }
