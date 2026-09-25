import re
from dataclasses import dataclass, asdict
from io import BytesIO
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, ImageStat
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
    normalized = "\n".join(" ".join(line.upper().split()) for line in text.splitlines() if line.strip())
    # Corrige únicamente etiquetas conocidas que Tesseract suele confundir.
    label_fixes = {
        r"\bN[O0]M[B8]RE\b": "NOMBRE",
        r"\bD[O0]M[I1Í]C[I1Í]L[I1Í][O0]\b": "DOMICILIO",
        r"\bSECC[I1Í][O0Ó]N\b": "SECCIÓN",
        r"\bV[I1Í]GENC[I1Í]A\b": "VIGENCIA",
        r"\bEM[I1Í]S[I1Í][O0Ó]N\b": "EMISIÓN",
    }
    for pattern, replacement in label_fixes.items():
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


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

    # En las INE nuevas, el reverso concentra CIC/OCR y el nombre en tres
    # renglones legibles por máquina, sin imprimir las etiquetas "CIC" u "OCR".
    mrz_top = re.search(r"\bIDMEX\s*([A-Z0-9]{8,15})<{1,3}(\d{12,14})\b", joined)
    if mrz_top:
        if not result.cic:
            result.cic = mrz_top.group(1)
        if not result.ocr_code:
            result.ocr_code = mrz_top.group(2)
    if not result.name:
        for line in lines:
            compact = line.replace(" ", "")
            if (
                "<<" in compact
                and not compact.startswith("IDMEX")
                and re.fullmatch(r"[A-Z<]{8,}", compact)
            ):
                surnames, given_names = compact.split("<<", 1)
                candidate = " ".join(
                    part for part in (surnames.replace("<", " "), given_names.replace("<", " "))
                    if part.strip()
                )
                result.name = " ".join(candidate.split())[:180]
                break
    return asdict(result)


def prepare_ocr_images(image: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image]:
    image = ImageOps.exif_transpose(image).convert("L")
    longest_side = max(image.size)
    if longest_side < 1800:
        factor = 1800 / longest_side
        image = image.resize(
            (int(image.width * factor), int(image.height * factor)),
            Image.Resampling.LANCZOS,
        )
    elif longest_side > 3200:
        factor = 3200 / longest_side
        image = image.resize(
            (int(image.width * factor), int(image.height * factor)),
            Image.Resampling.LANCZOS,
        )

    clean = ImageOps.autocontrast(image, cutoff=1)
    clean = ImageEnhance.Contrast(clean).enhance(1.25)
    clean = clean.filter(ImageFilter.UnsharpMask(radius=1.3, percent=160, threshold=3))

    # Estima la iluminación de fondo y la resta de la imagen. Esto empareja
    # zonas claras y oscuras sin guardar ni enviar una copia procesada.
    blur_radius = max(18, min(clean.size) // 34)
    illumination = clean.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    shadowless = ImageOps.invert(ImageChops.difference(clean, illumination))
    shadowless = ImageOps.autocontrast(shadowless, cutoff=1)
    shadowless = shadowless.filter(ImageFilter.UnsharpMask(radius=1.0, percent=150, threshold=2))

    average = ImageStat.Stat(shadowless).mean[0]
    threshold_level = max(145, min(215, int(average * 0.91)))
    threshold = shadowless.point(lambda pixel: 255 if pixel > threshold_level else 0)
    return clean, shadowless, threshold


def extract_image(data: bytes, side: str | None = None) -> tuple[dict[str, str], str]:
    with Image.open(BytesIO(data)) as image:
        clean, shadowless, threshold = prepare_ocr_images(image)
        passes = (
            (shadowless, "--oem 3 --psm 11"),
            (threshold, "--oem 3 --psm 6"),
        )
        if side == "front":
            width, height = shadowless.size
            detail = shadowless.crop((int(width * .27), int(height * .15), width, int(height * .98)))
            passes += ((detail, "--oem 3 --psm 11"),)
        elif side == "back":
            width, height = threshold.size
            machine_lines = threshold.crop((0, int(height * .62), width, height))
            passes += ((machine_lines, "--oem 3 --psm 6"),)
        merged = asdict(Extracted())
        raw_parts = []
        for prepared, config in passes:
            text = pytesseract.image_to_string(
                prepared, lang="spa", config=config, timeout=25,
            )
            raw_parts.append(text)
            fields = parse_ine_text(text)
            for key, value in fields.items():
                if value and not merged[key]:
                    merged[key] = value

        # La versión sin normalizar conserva detalles que a veces se pierden
        # al quitar una sombra muy fuerte. Solo se usa si las dos lecturas
        # principales no encontraron ningún campo.
        if not any(merged.values()):
            text = pytesseract.image_to_string(
                clean, lang="spa", config="--oem 3 --psm 11", timeout=25,
            )
            raw_parts.append(text)
            merged.update({key: value for key, value in parse_ine_text(text).items() if value})

    return merged, "\n--- SEGUNDA LECTURA ---\n".join(raw_parts)
