"""Production launcher used only by IIS HttpPlatformHandler."""
from __future__ import annotations

import os
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)


def fail(message: str) -> None:
    raise SystemExit(f"CONFIGURACION INVALIDA: {message}")


if not (ROOT / ".env").is_file():
    fail("falta el archivo .env en la raiz del sitio")

from app.config import get_settings  # noqa: E402

settings = get_settings()
port = os.getenv("HTTP_PLATFORM_PORT", "").strip()
if not port.isdigit():
    fail("IIS no proporciono HTTP_PLATFORM_PORT; inicie mediante HttpPlatformHandler")
if settings.secret_key.startswith("solo-desarrollo") or len(settings.secret_key) < 32:
    fail("SECRET_KEY debe ser aleatoria y tener al menos 32 caracteres")
if settings.admin_password == "cambie-esta-contrasena" or len(settings.admin_password) < 12:
    fail("ADMIN_PASSWORD debe ser unica y tener al menos 12 caracteres")
if not settings.cookie_secure:
    fail("COOKIE_SECURE debe ser true cuando IIS publica por HTTPS")

is_sqlite = (
    settings.database_backend.casefold() not in {"sqlserver", "mssql"}
    and settings.database_url.casefold().startswith("sqlite")
)
if is_sqlite and not settings.allow_sqlite_in_iis:
    fail("SQLite esta bloqueado en IIS; configure SQL Server o autorice solo una prueba temporal")

uvicorn.run(
    "app.main:app",
    host="127.0.0.1",
    port=int(port),
    proxy_headers=True,
    forwarded_allow_ips="127.0.0.1",
    workers=1,
    access_log=False,
)
