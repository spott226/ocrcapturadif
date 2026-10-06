"""Verificación de despliegue sin leer ni imprimir datos personales."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    root = Path(os.environ.get("CAPTURA_APOYOS_ROOT", "")).resolve()
    if not root.is_dir():
        print("ERROR: CAPTURA_APOYOS_ROOT no apunta a la aplicación.", file=sys.stderr)
        return 2
    sys.path.insert(0, str(root))

    for module_name in ("fastapi", "cv2", "onnxruntime", "rapidocr", "pyodbc"):
        try:
            __import__(module_name)
        except (ImportError, OSError) as exc:
            print(f"ERROR: no se pudo cargar {module_name}: {exc}", file=sys.stderr)
            return 3

    try:
        from sqlalchemy import inspect

        from app.database import engine
        from app.main import app

        inspector = inspect(engine)
        required_tables = {"people", "support_types", "app_users"}
        missing_tables = sorted(required_tables.difference(inspector.get_table_names()))
        if missing_tables:
            raise RuntimeError("faltan tablas: " + ", ".join(missing_tables))

        people_columns = {item["name"] for item in inspector.get_columns("people")}
        required_columns = {
            "given_names",
            "paternal_surname",
            "maternal_surname",
            "municipality",
            "support_type_id",
        }
        missing_columns = sorted(required_columns.difference(people_columns))
        if missing_columns:
            raise RuntimeError("faltan columnas de people: " + ", ".join(missing_columns))

        if not getattr(app, "routes", None):
            raise RuntimeError("FastAPI no registró rutas")
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except Exception as exc:  # El detalle técnico no incluye consultas de personas.
        print(f"ERROR DE VERIFICACIÓN: {exc}", file=sys.stderr)
        return 4

    print("VERIFICACIÓN DE APLICACIÓN Y ESQUEMA OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
