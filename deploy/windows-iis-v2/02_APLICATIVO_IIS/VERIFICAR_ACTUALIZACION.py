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
    # pydantic-settings resolves env_file=".env" from the current working
    # directory. The updater itself is launched from the extracted package,
    # so explicitly enter the deployed application directory before importing
    # app.config. Otherwise validation silently connects to the default empty
    # SQLite database beside this script instead of the preserved SQL Server
    # configuration in <root>/.env.
    os.chdir(root)
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
        required_tables = {
            "people", "support_types", "app_users",
            "structure_submissions", "support_network_submissions",
        }
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

        user_columns = {item["name"] for item in inspector.get_columns("app_users")}
        if "form_access" not in user_columns:
            raise RuntimeError("falta columna de app_users: form_access")

        network_columns = {item["name"] for item in inspector.get_columns("support_network_submissions")}
        missing_facebook = sorted(
            {f"facebook_{number}" for number in range(1, 11)}.difference(network_columns)
        )
        if missing_facebook:
            raise RuntimeError("faltan columnas separadas de Facebook: " + ", ".join(missing_facebook))

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
