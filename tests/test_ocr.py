from io import BytesIO

from PIL import Image, ImageDraw, ImageStat

from app.ocr import (
    correct_document_perspective,
    extract_image,
    parse_back_mrz,
    parse_front_document,
    parse_front_regions,
    parse_ine_text,
    prepare_ocr_images,
    sanitize_extracted,
)


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


def test_sanitizer_removes_symbols_and_rejects_malformed_fields():
    fields = {
        "name": "MONT@OYA++ SALOMON / CHRISTOPHER LENIEL ###",
        "address": "CALLE # 10@@\nCOL. CENTRO ++\nAGUASCALIENTES, AGS",
        "curp": "NO-ES-UNA-CURP",
        "voter_key": "ABC+123",
        "birth_date": "39/19/2020",
        "sex_or_gender": "?",
        "section": "40+94",
        "registration_year": "2019 03",
        "cic": "123?456",
        "ocr_code": "3904033366874",
        "valid_until": "2026 - 2036",
    }

    clean = sanitize_extracted(fields)

    assert clean["name"] == "MONTOYA SALOMON CHRISTOPHER LENIEL"
    assert clean["address"] == "CALLE # 10\nCOL. CENTRO\nAGUASCALIENTES, AGS"
    assert clean["curp"] == ""
    assert clean["voter_key"] == ""
    assert clean["birth_date"] == ""
    assert clean["sex_or_gender"] == ""
    assert clean["section"] == "4094"
    assert clean["registration_year"] == "201903"
    assert clean["cic"] == ""
    assert clean["ocr_code"] == "3904033366874"
    assert clean["valid_until"] == "2026-2036"


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


def test_noisy_back_mrz_recovers_cic_and_ocr():
    data = parse_back_mrz("""IDMEXI38252844I<<39O4O33366874
GOMEZ<VELAZQUEZ<<MARGARITA<<<<""")

    assert data["cic"] == "1382528441"
    assert data["ocr_code"] == "3904033366874"


def test_shadow_correction_balances_uneven_illumination():
    image = Image.new("L", (1800, 1000), 220)
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((0, 0, 899, 999), fill=90)

    _clean, shadowless, _threshold = prepare_ocr_images(image)
    dark_side = ImageStat.Stat(shadowless.crop((150, 150, 700, 850))).mean[0]
    light_side = ImageStat.Stat(shadowless.crop((1100, 150, 1650, 850))).mean[0]

    assert abs(dark_side - light_side) < 15


def test_perspective_correction_rectifies_a_complete_card():
    image = Image.new("RGB", (1800, 1300), "#222222")
    drawing = ImageDraw.Draw(image)
    drawing.polygon(
        [(180, 250), (1610, 120), (1680, 1050), (260, 1160)],
        fill="white", outline="black", width=12,
    )
    drawing.line((450, 500, 1400, 420), fill="black", width=20)

    corrected = correct_document_perspective(image)

    assert corrected.width >= 1600
    assert abs(corrected.width / corrected.height - 1.586) < .01


def test_front_detail_region_can_recover_section(monkeypatch):
    readings = iter(["", ""])
    monkeypatch.setattr(
        "app.ocr.pytesseract.image_to_string",
        lambda *_args, **_kwargs: next(readings),
    )
    monkeypatch.setattr(
        "app.ocr.pytesseract.image_to_data",
        lambda *_args, **_kwargs: {
            "text": ["NOMBRE", "MONTOYA", "SALMON", "CHRISTOPHER", "LENIEL", "DOMICILIO", "CALLE", "UNO", "COLONIA", "CENTRO", "AGUASCALIENTES", "AGS", "SECCIÓN", "4094"],
            "top": [100, 150, 190, 230, 230, 600, 650, 650, 700, 700, 750, 750, 2700, 2780],
            "height": [30] * 14,
            "left": [100, 100, 100, 100, 430, 100, 100, 250, 100, 280, 100, 390, 100, 220],
            "block_num": [1] * 14,
            "par_num": [1] * 14,
            "line_num": [1, 2, 3, 4, 4, 5, 6, 6, 7, 7, 8, 8, 9, 10],
        },
    )
    image = Image.new("RGB", (1600, 1000), "white")
    stream = BytesIO()
    image.save(stream, format="JPEG")

    data, _raw = extract_image(stream.getvalue(), side="front")

    assert data["name"] == "MONTOYA SALMON CHRISTOPHER LENIEL"
    assert data["address"] == "CALLE UNO\nCOLONIA CENTRO\nAGUASCALIENTES AGS"
    assert data["section"] == "4094"


def test_front_document_corrects_noisy_labels_and_digits():
    data = parse_front_document("""DOMICILIO
VIAL TLALPAN 100 COL ARENAL
CURP G0VM8OO7O5MCLMLRO1
FECHA DE NACIMIENTO O5/O7/198O
SECCIÓN 4O94
AÑO DE REGISTRO 2O19 O3
VIGENCIA 2O26-2O36""")

    assert data["curp"] == "GOVM800705MCLMLR01"
    assert data["birth_date"] == "05/07/1980"
    assert data["section"] == "4094"
    assert data["registration_year"] == "201903"
    assert data["valid_until"] == "2026-2036"


def test_front_regions_recover_noisy_small_fields():
    data = parse_front_regions(
        "DOM1C1L10\nVIAL TLALPAN 100\nCOL ARENAL TEPEPAN 14610\nTLALPAN CDMX",
        "CURP G0VM8OO7O5MCLMLRO1",
        "O5/O7/198O",
        "4O94",
        "2O19 O3",
        "2O26-2O36",
    )

    assert data["address"] == "VIAL TLALPAN 100\nCOL ARENAL TEPEPAN 14610\nTLALPAN CDMX"
    assert data["curp"] == "GOVM800705MCLMLR01"
    assert data["birth_date"] == "05/07/1980"
    assert data["section"] == "4094"
    assert data["registration_year"] == "201903"
    assert data["valid_until"] == "2026-2036"
