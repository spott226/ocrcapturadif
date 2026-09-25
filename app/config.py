from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./dif_ine.sqlite3"
    secret_key: str = "solo-desarrollo-cambie-esta-clave-insegura"
    admin_email: str = "admin@dif.local"
    admin_password: str = "cambie-esta-contrasena"
    cookie_secure: bool = False
    max_upload_mb: int = 8
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

