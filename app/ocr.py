import re
from dataclasses import dataclass, asdict
from io import BytesIO
from PIL import Image, ImageEnhance, ImageOps
import pytesseract


@dataclass
class Extracted:
    name: str = ""
    address: str = ""
    curp: str = ""
    voter_key: str = ""
    birth_date: str = ""
    sex_or_gender: str = ""
    state_code: str = ""
    municipality_code: str = ""
    section: str = ""
    locality_code: str = ""
    registration_year: str = ""
    issue_year: str = ""
    cic: str = ""
    ocr_code: str = ""
    valid_until: str = ""


def normalize(text: str) -> str:
    return "\n".join(" ".join(line.upper().split()) for line in text.splitlines() if line.strip())


def parse_ine_text(text: str) -> dict[str, str]:
    text = normalize(text)
    lines = text.splitlines()
    joined = " ".join(lines)
    result = Extracted()
    curp = re.search(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b", joined)
    voter = re.search(r"(?:CLAVE DE ELECTOR|ELECTOR)\s*[:.]?\s*([A-Z0-9]{16,20})", joined)
    valid = re.search(r"(?:VIGENCIA|VÁLIDA? HASTA)\s*[:.]?\s*(\d{4}(?:\s*[-/]\s*\d{4})?|\d{2}[/.-]\d{2}[/.-]\d{4})", joined)
    birth = re.search(r"(?:FECHA DE NACIMIENTO|NACIMIENTO)\s*[:.]?\s*(\d{2}[/.-]\d{2}[/.-]\d{4})", joined)
    sex = re.search(r"(?:SEXO|G[ÉE]NERO)\s*[:.]?\s*(NB|H|M)\b", joined)
    section = re.search(r"SECCI[ÓO]N\s*[:.]?\s*(\d{3,5})", joined)
    registration = re.search(r"A[ÑN]O DE REGISTRO\s*[:.]?\s*(\d{4}(?:\s*[-/]?\s*\d{2})?)", joined)
    issue = re.search(r"EMISI[ÓO]N\s*[:.]?\s*(\d{4})", joined)
    state = re.search(r"ESTADO\s*[:.]?\s*([A-Z0-9]{1,20})", joined)
    municipality = re.search(r"MUNICIPIO\s*[:.]?\s*([A-Z0-9]{1,20})", joined)
    locality = re.search(r"LOCALIDAD\s*[:.]?\s*([A-Z0-9]{1,20})", joined)
    cic = re.search(r"\bCIC\s*[:.]?\s*([A-Z0-9]{8,20})\b", joined)
    ocr_code = re.search(r"\bOCR\s*[:.]?\s*(\d{12,13})\b", joined)
    if curp:
        result.curp = curp.group(0)
    if voter:
        result.voter_key = voter.group(1)
    if valid:
        result.valid_until = valid.group(1).replace(" ", "")
    if birth:
        result.birth_date = birth.group(1)
    if sex:
        result.sex_or_gender = sex.group(1)
    if section:
        result.section = section.group(1)
    if registration:
        result.registration_year = registration.group(1).replace(" ", "")
    if issue:
        result.issue_year = issue.group(1)
    if state:
        result.state_code = state.group(1)
    if municipality:
        result.municipality_code = municipality.group(1)
    if locality:
        result.locality_code = locality.group(1)
    if cic:
        result.cic = cic.group(1)
    if ocr_code:
        result.ocr_code = ocr_code.group(1)
    section_label = re.compile(r"^(?:NOMBRE|DOMICILIO|CURP|CLAVE(?: DE ELECTOR)?|VIGENCIA|SEXO|G[ÉE]NERO|FECHA DE NACIMIENTO|NACIMIENTO|SECCI[ÓO]N|A[ÑN]O DE REGISTRO|EMISI[ÓO]N|ESTADO|MUNICIPIO|LOCALIDAD|CIC|OCR)\b")
    for i, line in enumerate(lines):
        if line.startswith("NOMBRE"):
            candidates = []
            tail = re.sub(r"^NOMBRE\s*[:.]?\s*", "", line)
            if tail:
                candidates.append(tail)
            for candidate in lines[i + 1:i + 4]:
                if section_label.search(candidate):
                    break
                candidates.append(candidate)
            result.name = " ".join(candidates)[:180]
        if line.startswith("DOMICILIO"):
            tail = re.sub(r"^DOMICILIO\s*[:.]?\s*", "", line)
            address_lines = [tail] if tail else []
            for candidate in lines[i + 1:i + 4]:
                if section_label.search(candidate):
                    break
                address_lines.append(candidate)
            result.address = " ".join(address_lines)[:500]
    return asdict(result)


def extract_image(data: bytes) -> tuple[dict[str, str], str]:
    with Image.open(BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image).convert("L")
        if image.width < 1400:
            factor = 1400 / image.width
            image = image.resize((1400, int(image.height * factor)))
        image = ImageEnhance.Contrast(image).enhance(1.7)
        text = pytesseract.image_to_string(image, lang="spa", config="--oem 3 --psm 6")
    return parse_ine_text(text), text
