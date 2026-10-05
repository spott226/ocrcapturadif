from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dif_ine.sqlite3"
    database_backend: str = "url"
    sqlserver_server: str = ""
    sqlserver_database: str = "CapturaApoyosDIF"
    sqlserver_auth: str = "windows"
    sqlserver_username: str = ""
    sqlserver_password: str = ""
    sqlserver_driver: str = "ODBC Driver 18 for SQL Server"
    sqlserver_encrypt: bool = True
    sqlserver_trust_certificate: bool = False
    secret_key: str = "solo-desarrollo-cambie-esta-clave-insegura"
    admin_email: str = "admin@dif.local"
    admin_password: str = "cambie-esta-contrasena"
    cookie_secure: bool = False
    force_https: bool = False
    allow_sqlite_in_iis: bool = False
    max_upload_mb: int = 8
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

