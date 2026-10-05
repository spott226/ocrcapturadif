"""Checks dependencies and database connectivity without printing personal data."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, inspect, select

from app.database import SessionLocal, engine
from app.models import Person


def main() -> int:
    required_imports = ("cv2", "onnxruntime", "rapidocr", "pyodbc")
    for module_name in required_imports:
        __import__(module_name)

    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")

    if not inspect(engine).has_table("people"):
        print("ERROR: falta la tabla people; ejecute SQL/01_CREAR_BASE_Y_TABLA.sql", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        count = db.scalar(select(func.count(Person.id))) or 0

    print(f"OK: Python y OCR disponibles; base {engine.dialect.name} conectada; registros={count}")
    if shutil.which("tesseract") is None:
        print("AVISO: Tesseract no esta en PATH; RapidOCR funciona, pero no habra respaldo Tesseract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
