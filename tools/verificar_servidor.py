"""Checks dependencies and database connectivity without printing personal data."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect

from app.database import engine


def main() -> int:
    required_imports = ("cv2", "onnxruntime", "rapidocr", "pyodbc")
    for module_name in required_imports:
        try:
            __import__(module_name)
        except (ImportError, OSError) as exc:
            if module_name == "onnxruntime":
                print(
                    "ERROR: Windows no pudo cargar ONNX Runtime. Instale o repare "
                    "Microsoft Visual C++ Redistributable v14 x64 (2015-2022) y "
                    "vuelva a ejecutar VERIFICAR_SERVIDOR.ps1. Descarga oficial: "
                    "https://aka.ms/vs/17/release/vc_redist.x64.exe",
                    file=sys.stderr,
                )
            else:
                print(f"ERROR: no se pudo cargar la dependencia {module_name}.", file=sys.stderr)
            print(f"Detalle tecnico: {exc}", file=sys.stderr)
            return 3

    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")

    inspector = inspect(engine)
    required_tables = {"people", "support_types", "app_users"}
    available_tables = set(inspector.get_table_names())
    missing_tables = sorted(required_tables - available_tables)
    if missing_tables:
        print(
            "ERROR: faltan tablas de la versión 2: " + ", ".join(missing_tables),
            file=sys.stderr,
        )
        return 2

    required_columns = {
        "people": {
            "name", "address", "given_names", "paternal_surname",
            "maternal_surname", "municipality", "support_type_id", "curp",
            "phone", "leader", "created_by", "created_at",
        },
        "support_types": {"id", "code", "name", "is_active", "sort_order"},
        "app_users": {
            "id", "email", "password_hash", "role", "is_active",
            "created_by", "created_at", "last_login_at",
        },
    }
    for table_name, expected in required_columns.items():
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        missing = sorted(expected - actual)
        if missing:
            print(
                f"ERROR: faltan columnas en {table_name}: " + ", ".join(missing),
                file=sys.stderr,
            )
            return 2

    print(f"OK: Python, OCR y esquema v2 disponibles; base {engine.dialect.name} conectada")
    if shutil.which("tesseract") is None:
        print("AVISO: Tesseract no esta en PATH; RapidOCR funciona, pero no habra respaldo Tesseract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
