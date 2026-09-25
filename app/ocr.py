import re
from dataclasses import dataclass, asdict
from datetime import datetime
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
            result.address = "\n".join(address_lines)[:500]

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


OCR_DIGITS = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"})
OCR_LETTERS = str.maketrans({"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"})


def _curp_from_region(text: str) -> str:
    compact = re.sub(r"[^A-Z0-9]", "", text.upper()).replace("CURP", "")
    for start in range(max(1, len(compact) - 17)):
        token = compact[start:start + 18]
        if len(token) != 18:
            continue
        chars = list(token)
        for position in (0, 1, 2, 3, 10, 11, 12, 13, 14, 15):
            chars[position] = chars[position].translate(OCR_LETTERS)
        for position in (4, 5, 6, 7, 8, 9, 17):
            chars[position] = chars[position].translate(OCR_DIGITS)
        # En CURP de personas nacidas antes de 2000, la posición 17 es
        # numérica; a partir de 2000 es una letra.
        birth_year_text = "".join(chars[4:6])
        if not birth_year_text.isdigit():
            continue
        birth_year = int(birth_year_text)
        if birth_year > datetime.now().year % 100:
            chars[16] = chars[16].translate(OCR_DIGITS)
        else:
            chars[16] = chars[16].translate(OCR_LETTERS)
        candidate = "".join(chars)
        if re.fullmatch(r"[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d", candidate):
            return candidate
    return ""


def parse_front_regions(
    address_text: str,
    curp_text: str,
    birth_text: str,
    section_text: str,
    registration_text: str,
    valid_text: str,
) -> dict[str, str]:
    result = asdict(Extracted())
    address_lines = []
    for line in normalize(address_text).splitlines():
        line = re.sub(r"^D[O0]M[I1]C[I1]L[I1][O0]\s*", "", line).strip(" :-")
        if not line or re.search(r"^(?:CLAVE|CURP|FECHA|SECCI|VIGENCIA|A[ÑN]O)", line):
            continue
        if len(re.findall(r"[A-ZÁÉÍÓÚÑ]", line)) >= 3:
            address_lines.append(line)
    result["address"] = "\n".join(address_lines)[:500]
    result["curp"] = _curp_from_region(curp_text)

    birth_payload = re.sub(r"^.*(?:FECHA DE NACIMIENTO|NACIMIENTO)", "", birth_text.upper(), flags=re.DOTALL)
    birth_digits = re.sub(r"[^0-9/.-]", "", birth_payload.translate(OCR_DIGITS))
    birth = re.search(r"(\d{2})[/.-]?(\d{2})[/.-]?(19\d{2}|20\d{2})", birth_digits)
    if birth:
        result["birth_date"] = "/".join(birth.groups())

    section_payload = re.sub(r"^.*SECCI[ÓO]N", "", section_text.upper(), flags=re.DOTALL)
    section_digits = re.sub(r"\D", "", section_payload.translate(OCR_DIGITS))
    section = re.search(r"\d{3,5}", section_digits)
    if section:
        result["section"] = section.group(0)

    registration_payload = re.sub(r"^.*A[ÑN]O DE REGISTRO", "", registration_text.upper(), flags=re.DOTALL)
    registration_digits = re.sub(r"\D", "", registration_payload.translate(OCR_DIGITS))
    registration = re.search(r"(19\d{2}|20\d{2})(\d{2})?", registration_digits)
    if registration:
        result["registration_year"] = "".join(part for part in registration.groups() if part)

    valid_payload = re.sub(r"^.*VIGENCIA", "", valid_text.upper(), flags=re.DOTALL)
    valid_digits = re.sub(r"[^0-9-]", "", valid_payload.translate(OCR_DIGITS))
    valid = re.search(r"(20\d{2})-?(20\d{2})", valid_digits)
    if valid:
        result["valid_until"] = f"{valid.group(1)}-{valid.group(2)}"
    elif re.search(r"20\d{2}", valid_digits):
        result["valid_until"] = re.search(r"20\d{2}", valid_digits).group(0)
    return result


FRONT_FIELD_BOXES = {
    "name": (.29, .20, .77, .47),
    "address": (.30, .46, .76, .72),
    "curp": (.30, .71, .75, .84),
    "birth_date": (.30, .80, .57, .97),
    "section": (.52, .80, .70, .97),
    "registration_year": (.64, .67, .92, .86),
    "valid_until": (.64, .80, .93, .98),
    "sex_or_gender": (.79, .17, .99, .36),
}


def _front_field_montage(image: Image.Image) -> tuple[Image.Image, dict[str, tuple[int, int]]]:
    width, height = image.size
    montage_width = 1400
    prepared = []
    for field, box in FRONT_FIELD_BOXES.items():
        region = image.crop((
            int(width * box[0]), int(height * box[1]),
            int(width * box[2]), int(height * box[3]),
        ))
        factor = min(3.5, 1200 / max(1, region.width))
        region = region.resize(
            (int(region.width * factor), int(region.height * factor)),
            Image.Resampling.LANCZOS,
        )
        prepared.append((field, region))
    montage_height = sum(region.height for _, region in prepared) + 80 * (len(prepared) + 1)
    montage = Image.new("L", (montage_width, montage_height), 255)
    bounds = {}
    y = 80
    for field, region in prepared:
        x = (montage_width - region.width) // 2
        montage.paste(region, (x, y))
        bounds[field] = (y, y + region.height)
        y += region.height + 80
    return montage, bounds


def _front_fields_from_position(image: Image.Image) -> tuple[dict[str, str], str]:
    montage, bounds = _front_field_montage(image)
    try:
        data = pytesseract.image_to_data(
            montage,
            lang="spa",
            config="--oem 3 --psm 6",
            timeout=18,
            output_type=pytesseract.Output.DICT,
        )
    except (RuntimeError, pytesseract.TesseractError):
        return asdict(Extracted()), ""
    words = {field: [] for field in bounds}
    raw_words = []
    for index, text in enumerate(data.get("text", [])):
        text = str(text).strip()
        if not text:
            continue
        raw_words.append(text)
        center = int(data["top"][index]) + int(data["height"][index]) // 2
        left = int(data["left"][index])
        for field, (top, bottom) in bounds.items():
            if top <= center <= bottom:
                words[field].append((int(data["top"][index]), left, text))
                break
    texts = {}
    for field, items in words.items():
        lines = []
        for top, left, text in sorted(items):
            if not lines or abs(top - lines[-1][0]) > 28:
                lines.append([top, [(left, text)]])
            else:
                lines[-1][1].append((left, text))
        texts[field] = "\n".join(
            " ".join(text for _, text in sorted(line_words))
            for _, line_words in lines
        )
    parsed = parse_front_regions(
        texts["address"], texts["curp"], texts["birth_date"],
        texts["section"], texts["registration_year"], texts["valid_until"],
    )
    name_lines = []
    for line in normalize(texts["name"]).splitlines():
        line = re.sub(r"^N[O0]M[B8]RE\s*", "", line).strip(" :-")
        if line and len(re.findall(r"[A-ZÁÉÍÓÚÑ]", line)) >= 2:
            name_lines.append(line)
    if name_lines:
        parsed["name"] = " ".join(name_lines)[:180]
    gender_text = normalize(texts["sex_or_gender"])
    gender = re.search(r"(?:SEXO|G[ÉE]NERO)\s*[:.]?\s*(NB|H|M)\b", gender_text)
    if not gender:
        gender = re.search(r"\b(NB|H|M)\b", gender_text)
    if gender:
        parsed["sex_or_gender"] = gender.group(1)
    return parsed, " ".join(raw_words)


def parse_front_document(text: str) -> dict[str, str]:
    result = parse_ine_text(text)
    normalized = normalize(text)
    if not result["curp"]:
        result["curp"] = _curp_from_region(normalized)

    noisy_digit = r"[0-9OQDILZSBG]"
    if not result["birth_date"]:
        match = re.search(
            rf"(?:FECHA DE NACIMIENTO|NACIMIENTO)\s*[:.]?\s*({noisy_digit}{{2}}[/.-]?{noisy_digit}{{2}}[/.-]?{noisy_digit}{{4}})",
            normalized,
        )
        if match:
            digits = re.sub(r"\D", "", match.group(1).translate(OCR_DIGITS))
            if len(digits) == 8:
                result["birth_date"] = f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"
    if not result["section"]:
        match = re.search(rf"SECCI[ÓO]N\s*[:.]?\s*({noisy_digit}{{3,5}})", normalized)
        if match:
            result["section"] = match.group(1).translate(OCR_DIGITS)
    if not result["registration_year"]:
        match = re.search(
            rf"A[ÑN]O DE REGISTRO\s*[:.]?\s*({noisy_digit}{{4}})(?:\s*[-/]?\s*({noisy_digit}{{2}}))?",
            normalized,
        )
        if match:
            result["registration_year"] = "".join(
                part.translate(OCR_DIGITS) for part in match.groups() if part
            )
    if not result["valid_until"]:
        match = re.search(
            rf"VIGENCIA\s*[:.]?\s*({noisy_digit}{{4}})(?:\s*[-/]\s*({noisy_digit}{{4}}))?",
            normalized,
        )
        if match:
            years = [part.translate(OCR_DIGITS) for part in match.groups() if part]
            result["valid_until"] = "-".join(years)
    return result


def _safe_ocr(image: Image.Image, config: str, timeout: int = 15) -> str:
    try:
        return pytesseract.image_to_string(
            image, lang="spa", config=config, timeout=timeout,
        )
    except (RuntimeError, pytesseract.TesseractError):
        return ""


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
        if side == "back":
            width, height = threshold.size
            machine_lines = threshold.crop((0, int(height * .62), width, height))
            passes += ((machine_lines, "--oem 3 --psm 6"),)
        merged = asdict(Extracted())
        raw_parts = []
        for prepared, config in passes:
            text = _safe_ocr(prepared, config, timeout=15)
            raw_parts.append(text)
            fields = parse_ine_text(text)
            for key, value in fields.items():
                if value and not merged[key]:
                    merged[key] = value

        if side == "front":
            region_fields, region_text = _front_fields_from_position(clean)
            raw_parts.append(region_text)
            for key, value in region_fields.items():
                if value and (key == "name" or not merged[key]):
                    merged[key] = value

        # La versión sin normalizar conserva detalles que a veces se pierden
        # al quitar una sombra muy fuerte. Solo se usa si las dos lecturas
        # principales no encontraron ningún campo.
        if not any(merged.values()):
            text = _safe_ocr(clean, "--oem 3 --psm 11", timeout=12)
            raw_parts.append(text)
            merged.update({key: value for key, value in parse_ine_text(text).items() if value})

    return merged, "\n--- SEGUNDA LECTURA ---\n".join(raw_parts)
