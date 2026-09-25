import re
from dataclasses import dataclass, asdict
from datetime import datetime
from io import BytesIO
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
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


def sanitize_extracted(fields: dict[str, str]) -> dict[str, str]:
    """Elimina ruido OCR y descarta valores que no cumplen el formato del campo."""
    clean = {key: str(value or "").strip() for key, value in fields.items()}

    name = normalize(clean.get("name", "")).replace("\n", " ")
    name = re.split(
        r"\b(?:DOMICILIO|CURP|CLAVE DE ELECTOR|FECHA DE NACIMIENTO|SECCI[ÓO]N|VIGENCIA)\b",
        name,
    )[0]
    name = re.sub(r"[/|]+", " ", name)
    name = re.sub(r"[^A-ZÁÉÍÓÚÜÑ' -]", "", name)
    name = " ".join(word for word in name.split() if word != "NOMBRE")
    clean["name"] = name[:180] if len(name.replace(" ", "")) >= 4 else ""

    address_lines = []
    for line in normalize(clean.get("address", "")).splitlines()[:3]:
        line = re.sub(r"[^A-ZÁÉÍÓÚÜÑ0-9 .,#/'-]", " ", line)
        line = " ".join(line.split()).strip(" ,.-")
        if len(line) >= 3 and line != "DOMICILIO":
            address_lines.append(line)
    clean["address"] = "\n".join(address_lines)[:500]

    compact_rules = {
        "curp": r"[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d",
        "voter_key": r"[A-Z0-9]{16,20}",
        "section": r"\d{3,5}",
        "registration_year": r"(?:19|20)\d{2}(?:\d{2})?",
        "cic": r"\d{8,15}",
        "ocr_code": r"\d{12,14}",
    }
    for field, pattern in compact_rules.items():
        value = re.sub(r"[^A-Z0-9]", "", clean.get(field, "").upper())
        clean[field] = value if re.fullmatch(pattern, value) else ""

    birth = clean.get("birth_date", "").replace("-", "/").replace(".", "/")
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", birth):
        try:
            datetime.strptime(birth, "%d/%m/%Y")
            clean["birth_date"] = birth
        except ValueError:
            clean["birth_date"] = ""
    else:
        clean["birth_date"] = ""

    gender = clean.get("sex_or_gender", "").upper()
    clean["sex_or_gender"] = gender if gender in {"H", "M", "NB"} else ""
    validity = re.sub(r"\s", "", clean.get("valid_until", ""))
    clean["valid_until"] = validity if re.fullmatch(
        r"(?:20\d{2})(?:-(?:20\d{2}))?|\d{2}/\d{2}/20\d{2}", validity,
    ) else ""
    return clean


def normalize(text: str) -> str:
    normalized = "\n".join(" ".join(line.upper().split()) for line in text.splitlines() if line.strip())
    # Corrige únicamente etiquetas conocidas que Tesseract suele confundir.
    label_fixes = {
        r"\bN[O0]M[B8]RE\b": "NOMBRE",
        r"\bD[O0]M[I1Í]C[I1Í]L[I1Í][O0]\b": "DOMICILIO",
        r"\bCLAVE\s*DE\s*ELECT[O0]R\b": "CLAVE DE ELECTOR",
        r"\bSECC[I1ÍL][O0Ó]N\b": "SECCIÓN",
        r"\bV[I1Í]GENC[I1ÍL]A\b": "VIGENCIA",
        r"\bA[ÑN]O\s*DE\s*REG[I1ÍL]STRO\b": "AÑO DE REGISTRO",
        r"\bFECHA\s*DE\s*NAC[I1ÍL]M[I1ÍL]ENTO\b": "FECHA DE NACIMIENTO",
        r"\bG[ÉE]NER[O0]\b": "GÉNERO",
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
    voter_value = ""
    for line in lines:
        voter_line = re.search(r"(?:CLAVE DE ELECTOR|ELECTOR)\s*[:.]?\s*([A-Z0-9 ]+)$", line)
        if not voter_line:
            continue
        candidate = re.sub(r"\s", "", voter_line.group(1))
        if 16 <= len(candidate) <= 20:
            voter_value = candidate
            break
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
    if voter_value:
        result.voter_key = voter_value
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
    "name": (.29, .20, .77, .46),
    "address": (.29, .45, .78, .69),
    "voter_key": (.29, .66, .78, .78),
    "curp": (.29, .73, .69, .86),
    "registration_year": (.64, .70, .94, .86),
    "birth_date": (.29, .82, .57, .98),
    "section": (.52, .82, .72, .98),
    "valid_until": (.67, .81, .95, .98),
    "sex_or_gender": (.79, .16, .99, .36),
}


def _front_field_montage(image: Image.Image) -> tuple[Image.Image, dict[str, tuple[int, int]]]:
    width, height = image.size
    montage_width = 1500
    prepared = []
    for field, box in FRONT_FIELD_BOXES.items():
        region = image.crop((
            int(width * box[0]), int(height * box[1]),
            int(width * box[2]), int(height * box[3]),
        ))
        scale = min(4.0, 1250 / max(1, region.width))
        region = region.resize(
            (int(region.width * scale), int(region.height * scale)),
            Image.Resampling.LANCZOS,
        )
        prepared.append((field, region))
    montage_height = sum(region.height for _, region in prepared) + 70 * (len(prepared) + 1)
    montage = Image.new("L", (montage_width, montage_height), 255)
    bounds = {}
    top = 70
    for field, region in prepared:
        left = (montage_width - region.width) // 2
        montage.paste(region, (left, top))
        bounds[field] = (top, top + region.height)
        top += region.height + 70
    return montage, bounds


def _lines_from_words(words: list[tuple[int, int, int, str]]) -> str:
    lines = []
    for top, height, left, text in sorted(words):
        tolerance = max(16, height)
        if not lines or abs(top - lines[-1][0]) > tolerance:
            lines.append([top, [(left, text)]])
        else:
            lines[-1][1].append((left, text))
    return "\n".join(
        " ".join(text for _, text in sorted(line_words))
        for _, line_words in lines
    )


def _front_fields_from_regions(image: Image.Image) -> tuple[dict[str, str], str]:
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
    for index, text in enumerate(data.get("text", [])):
        text = str(text).strip()
        if not text:
            continue
        top = int(data["top"][index])
        left = int(data["left"][index])
        height = int(data["height"][index])
        center = top + height // 2
        for field, (start, end) in bounds.items():
            if start <= center <= end:
                words[field].append((top, height, left, text))
                break
    texts = {field: _lines_from_words(items) for field, items in words.items()}
    document_order = (
        "name", "address", "voter_key", "curp", "registration_year",
        "birth_date", "section", "valid_until", "sex_or_gender",
    )
    reconstructed = "\n".join(texts[field] for field in document_order if texts[field])
    parsed = parse_front_document(reconstructed)
    # Las zonas pequeñas toleran etiquetas débiles usando el formato del dato.
    if not parsed["curp"]:
        parsed["curp"] = _curp_from_region(texts["curp"])
    detail = parse_front_regions(
        texts["address"], texts["curp"], texts["birth_date"],
        texts["section"], texts["registration_year"], texts["valid_until"],
    )
    for key, value in detail.items():
        if value and not parsed[key]:
            parsed[key] = value
    gender = re.search(r"\b(NB|H|M)\b", normalize(texts["sex_or_gender"]))
    if gender and not parsed["sex_or_gender"]:
        parsed["sex_or_gender"] = gender.group(1)
    return parsed, reconstructed


def parse_back_mrz(text: str) -> dict[str, str]:
    result = parse_ine_text(text)
    for line in normalize(text).splitlines():
        compact = re.sub(r"[^A-Z0-9<]", "", line)
        match = re.search(r"I[DO0]MEX([A-Z0-9]{8,15})<{1,3}([A-Z0-9]{12,14})", compact)
        if not match:
            continue
        cic = match.group(1).translate(OCR_DIGITS)
        ocr_code = match.group(2).translate(OCR_DIGITS)
        if cic.isdigit():
            result["cic"] = cic
        if ocr_code.isdigit():
            result["ocr_code"] = ocr_code
        break
    return result


def _back_fields_from_mrz(image: Image.Image) -> tuple[dict[str, str], str]:
    width, height = image.size
    region = image.crop((0, int(height * .62), width, height))
    if region.width < 2400:
        scale = 2400 / region.width
        region = region.resize(
            (2400, int(region.height * scale)), Image.Resampling.LANCZOS,
        )
    text = _safe_ocr(
        region,
        "--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<",
        timeout=18,
    )
    return parse_back_mrz(text), text


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


def _ordered_corners(points: np.ndarray) -> np.ndarray:
    points = points.reshape(4, 2).astype("float32")
    ordered = np.zeros((4, 2), dtype="float32")
    totals = points.sum(axis=1)
    differences = np.diff(points, axis=1).ravel()
    ordered[0] = points[np.argmin(totals)]
    ordered[2] = points[np.argmax(totals)]
    ordered[1] = points[np.argmin(differences)]
    ordered[3] = points[np.argmax(differences)]
    return ordered


def correct_document_perspective(image: Image.Image) -> Image.Image:
    """Endereza una credencial completa; si no hay borde confiable conserva la foto."""
    source = ImageOps.exif_transpose(image).convert("RGB")
    rgb = np.asarray(source)
    height, width = rgb.shape[:2]
    detection_scale = min(1.0, 1400 / max(width, height))
    detection = cv2.resize(
        rgb, None, fx=detection_scale, fy=detection_scale,
        interpolation=cv2.INTER_AREA,
    )
    gray = cv2.cvtColor(detection, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 45, 135)
    edges = cv2.morphologyEx(
        edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=2,
    )
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = detection.shape[0] * detection.shape[1]
    card = None
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
        area = cv2.contourArea(contour)
        if area < image_area * .38:
            break
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, .025 * perimeter, True)
        if len(polygon) == 4 and cv2.isContourConvex(polygon):
            card = polygon.reshape(4, 2) / detection_scale
            break
    if card is None:
        return source

    corners = _ordered_corners(card)
    top_left, top_right, bottom_right, bottom_left = corners
    measured_width = max(
        np.linalg.norm(bottom_right - bottom_left),
        np.linalg.norm(top_right - top_left),
    )
    measured_height = max(
        np.linalg.norm(top_right - bottom_right),
        np.linalg.norm(top_left - bottom_left),
    )
    ratio = max(measured_width, measured_height) / max(1, min(measured_width, measured_height))
    if not 1.30 <= ratio <= 1.90:
        return source
    if measured_height > measured_width:
        corners = np.roll(corners, -1, axis=0)

    output_width = min(2400, max(1600, int(max(measured_width, measured_height))))
    output_height = round(output_width / 1.586)
    destination = np.array([
        [0, 0], [output_width - 1, 0],
        [output_width - 1, output_height - 1], [0, output_height - 1],
    ], dtype="float32")
    transform = cv2.getPerspectiveTransform(corners, destination)
    warped = cv2.warpPerspective(rgb, transform, (output_width, output_height))
    return Image.fromarray(warped)


def prepare_ocr_images(image: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image]:
    image = correct_document_perspective(image).convert("L")
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

    # Divide cada píxel entre una estimación suave de la iluminación. OpenCV
    # compensa sombras y CLAHE recupera letras sin quemar todo el plástico.
    gray = np.asarray(image)
    sigma = max(18, min(clean.size) // 34)
    illumination = cv2.GaussianBlur(gray, (0, 0), sigmaX=sigma, sigmaY=sigma)
    normalized = cv2.divide(gray, illumination, scale=245)
    normalized = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(10, 10)).apply(normalized)
    normalized = cv2.GaussianBlur(normalized, (3, 3), 0)
    shadowless = Image.fromarray(normalized).filter(
        ImageFilter.UnsharpMask(radius=1.0, percent=140, threshold=2),
    )
    threshold_array = cv2.adaptiveThreshold(
        normalized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 41, 13,
    )
    threshold = Image.fromarray(threshold_array)
    return clean, shadowless, threshold


def extract_image(data: bytes, side: str | None = None) -> tuple[dict[str, str], str]:
    with Image.open(BytesIO(data)) as image:
        clean, shadowless, threshold = prepare_ocr_images(image)
        passes = (
            (shadowless, "--oem 3 --psm 11"),
            (threshold, "--oem 3 --psm 6"),
        )
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
            region_fields, region_text = _front_fields_from_regions(shadowless)
            region_fields = sanitize_extracted(region_fields)
            raw_parts.append(region_text)
            for key, value in region_fields.items():
                if not value:
                    continue
                if key in {"name", "address"}:
                    if len(re.sub(r"\W", "", value)) >= len(re.sub(r"\W", "", merged[key])):
                        merged[key] = value
                elif not merged[key]:
                    merged[key] = value

        if side == "back":
            back_fields, back_text = _back_fields_from_mrz(shadowless)
            raw_parts.append(back_text)
            for key, value in back_fields.items():
                if value and (key in {"cic", "ocr_code"} or not merged[key]):
                    merged[key] = value

        # La versión sin normalizar conserva detalles que a veces se pierden
        # al quitar una sombra muy fuerte. Solo se usa si las dos lecturas
        # principales no encontraron ningún campo.
        if not any(merged.values()):
            text = _safe_ocr(clean, "--oem 3 --psm 11", timeout=12)
            raw_parts.append(text)
            merged.update({key: value for key, value in parse_ine_text(text).items() if value})

    return sanitize_extracted(merged), "\n--- SEGUNDA LECTURA ---\n".join(raw_parts)
