"""Importa una exportación de Captura Apoyos sin mostrar datos personales."""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from openpyxl import load_workbook
from sqlalchemy import or_, select

from app.database import Base, SessionLocal, engine
from app.main import migrate_existing_database
from app.models import Person


def normalized_header(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()


HEADERS = {
    "ID": "source_id",
    "NOMBRE COMPLETO": "name",
    "CURP": "curp",
    "DIRECCION": "address",
    "NUMERO DE TELEFONO": "phone",
    "TELEFONO": "phone",
    "LIDER": "leader",
    "CAPTURO": "created_by",
    "FECHA DE CAPTURA": "created_at",
}


def as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_date(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = as_text(value)
    for pattern in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def import_workbook(path: Path, simulate: bool = False) -> tuple[int, int, int]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    try:
        raw_headers = next(rows)
    except StopIteration as exc:
        raise ValueError("El Excel está vacío") from exc

    columns = {index: HEADERS.get(normalized_header(value)) for index, value in enumerate(raw_headers)}
    if "name" not in columns.values():
        raise ValueError("No se encontró la columna 'Nombre completo'")

    inserted = duplicates = invalid = 0
    seen_curps: set[str] = set()
    seen_phones: set[str] = set()
    Base.metadata.create_all(engine)
    migrate_existing_database()
    with SessionLocal() as db:
        for row in rows:
            values = {
                field: row[index]
                for index, field in columns.items()
                if field and index < len(row)
            }
            name = as_text(values.get("name")).upper()[:180]
            curp = as_text(values.get("curp")).upper()[:18]
            phone = re.sub(r"\D", "", as_text(values.get("phone")))[:15]
            if not name:
                invalid += 1
                continue

            if (curp and curp in seen_curps) or (phone and phone in seen_phones):
                duplicates += 1
                continue

            conditions = []
            if curp:
                conditions.append(Person.curp == curp)
            if phone:
                conditions.append(Person.phone == phone)
            if conditions and db.scalar(select(Person.id).where(or_(*conditions)).limit(1)):
                duplicates += 1
                continue

            db.add(Person(
                name=name,
                curp=curp,
                address=as_text(values.get("address")).upper()[:500],
                phone=phone,
                leader=as_text(values.get("leader")).upper()[:180],
                created_by=as_text(values.get("created_by"))[:254] or "IMPORTACION",
                created_at=parse_date(values.get("created_at")),
            ))
            if curp:
                seen_curps.add(curp)
            if phone:
                seen_phones.add(phone)
            inserted += 1

        if simulate:
            db.rollback()
        else:
            db.commit()
    workbook.close()
    return inserted, duplicates, invalid


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa una exportación .xlsx de Captura Apoyos")
    parser.add_argument("archivo", type=Path)
    parser.add_argument("--simular", action="store_true", help="valida todo sin guardar")
    args = parser.parse_args()
    if not args.archivo.is_file() or args.archivo.suffix.casefold() != ".xlsx":
        parser.error("indique un archivo .xlsx existente")
    inserted, duplicates, invalid = import_workbook(args.archivo, args.simular)
    mode = "SIMULACION" if args.simular else "IMPORTACION"
    print(f"{mode} TERMINADA: nuevos={inserted}, duplicados={duplicates}, inválidos={invalid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
