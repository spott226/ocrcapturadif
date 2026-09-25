from io import BytesIO

from PIL import Image, ImageDraw, ImageStat

from app.ocr import extract_image, parse_front_regions, parse_ine_text, prepare_ocr_images


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


def test_common_ocr_label_confusions_are_tolerated():
    data = parse_ine_text("""N0MBRE
PERSONA FICTICIA
D0M1C1L10
CALLE DE PRUEBA 10
SECC10N 4321
V1GENC1A 2034""")
    assert data["name"] == "PERSONA FICTICIA"
    assert data["address"] == "CALLE DE PRUEBA 10"
    assert data["section"] == "4321"
    assert data["valid_until"] == "2034"


def test_two_ocr_passes_merge_fictitious_results(monkeypatch):
    readings = iter([
        "NOMBRE\nPERSONA FICTICIA\nCURP PULA900101MDFRPN09",
        "CLAVE DE ELECTOR PRLBAN90010109M100\nVIGENCIA 2036",
    ])
    monkeypatch.setattr(
        "app.ocr.pytesseract.image_to_string",
        lambda *_args, **_kwargs: next(readings),
    )
    image = Image.new("RGB", (900, 600), "white")
    stream = BytesIO()
    image.save(stream, format="JPEG")

    data, raw = extract_image(stream.getvalue())

    assert data["name"] == "PERSONA FICTICIA"
    assert data["curp"] == "PULA900101MDFRPN09"
    assert data["voter_key"] == "PRLBAN90010109M100"
    assert data["valid_until"] == "2036"
    assert "SEGUNDA LECTURA" in raw


def test_new_ine_front_sections_and_back_machine_readable_lines():
    front = """INSTITUTO NACIONAL ELECTORAL
NOMBRE
GOMEZ
VELAZQUEZ
MARGARITA
DOMICILIO
VIAL TLALPAN 100
COL ARENAL TEPEPAN 14610
TLALPAN, CDMX
CLAVE DE ELECTOR GMMMR80070501M100
CURP GOVM800705MCLMLR01
AÑO DE REGISTRO 2019 03
FECHA DE NACIMIENTO 05/07/1980
SECCIÓN 4094
VIGENCIA 2026-2036
GÉNERO NB"""
    back = """IDMEX1382528441<<3904033366874
701204M3512311MEX<<01<<12345<1
GOMEZ<VELAZQUEZ<<MARGARITA<<<<"""

    front_data = parse_ine_text(front)
    back_data = parse_ine_text(back)

    assert front_data["name"] == "GOMEZ VELAZQUEZ MARGARITA"
    assert front_data["voter_key"] == "GMMMR80070501M100"
    assert front_data["curp"] == "GOVM800705MCLMLR01"
    assert front_data["birth_date"] == "05/07/1980"
    assert front_data["section"] == "4094"
    assert front_data["registration_year"] == "201903"
    assert front_data["valid_until"] == "2026-2036"
    assert front_data["sex_or_gender"] == "NB"
    assert back_data["cic"] == "1382528441"
    assert back_data["ocr_code"] == "3904033366874"
    assert back_data["name"] == "GOMEZ VELAZQUEZ MARGARITA"


def test_shadow_correction_balances_uneven_illumination():
    image = Image.new("L", (1800, 1000), 220)
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((0, 0, 899, 999), fill=90)

    _clean, shadowless, _threshold = prepare_ocr_images(image)
    dark_side = ImageStat.Stat(shadowless.crop((150, 150, 700, 850))).mean[0]
    light_side = ImageStat.Stat(shadowless.crop((1100, 150, 1650, 850))).mean[0]

    assert abs(dark_side - light_side) < 15


def test_front_detail_region_can_recover_section(monkeypatch):
    readings = iter(["", "", "SECCIÓN 4094"] + [""] * 6)
    monkeypatch.setattr(
        "app.ocr.pytesseract.image_to_string",
        lambda *_args, **_kwargs: next(readings),
    )
    image = Image.new("RGB", (1600, 1000), "white")
    stream = BytesIO()
    image.save(stream, format="JPEG")

    data, _raw = extract_image(stream.getvalue(), side="front")

    assert data["section"] == "4094"


def test_front_regions_recover_noisy_small_fields():
    data = parse_front_regions(
        "DOM1C1L10\nVIAL TLALPAN 100\nCOL ARENAL TEPEPAN 14610\nTLALPAN CDMX",
        "CURP G0VM8OO7O5MCLMLRO1",
        "O5/O7/198O",
        "4O94",
        "2O19 O3",
        "2O26-2O36",
    )

    assert data["address"] == "VIAL TLALPAN 100 COL ARENAL TEPEPAN 14610 TLALPAN CDMX"
    assert data["curp"] == "GOVM800705MCLMLR01"
    assert data["birth_date"] == "05/07/1980"
    assert data["section"] == "4094"
    assert data["registration_year"] == "201903"
    assert data["valid_until"] == "2026-2036"
