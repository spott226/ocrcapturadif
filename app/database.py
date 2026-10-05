from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import get_settings


class Base(DeclarativeBase):
    pass


def build_database_url(settings):
    """Build a driver URL without requiring passwords to be URL-escaped."""
    backend = settings.database_backend.strip().casefold()
    if backend in {"sqlserver", "mssql"}:
        server = settings.sqlserver_server.strip()
        database = settings.sqlserver_database.strip()
        if not server or not database:
            raise RuntimeError("SQLSERVER_SERVER y SQLSERVER_DATABASE son obligatorios")

        query = {
            "driver": settings.sqlserver_driver.strip(),
            "Encrypt": "yes" if settings.sqlserver_encrypt else "no",
            "TrustServerCertificate": "yes" if settings.sqlserver_trust_certificate else "no",
        }
        auth = settings.sqlserver_auth.strip().casefold()
        if auth == "windows":
            query["Trusted_Connection"] = "yes"
            username = password = None
        elif auth == "sql":
            username = settings.sqlserver_username.strip()
            password = settings.sqlserver_password
            if not username or not password:
                raise RuntimeError("Usuario y contraseña de SQL Server son obligatorios para autenticación SQL")
        else:
            raise RuntimeError("SQLSERVER_AUTH debe ser 'windows' o 'sql'")

        return URL.create(
            "mssql+pyodbc",
            username=username,
            password=password,
            host=server,
            database=database,
            query=query,
        )

    database_url = settings.database_url.strip()
    # Railway exposes PostgreSQL as postgresql://. Pin the SQLAlchemy dialect to
    # psycopg 3, which is the driver installed by this project.
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


settings = get_settings()
database_url = build_database_url(settings)
is_sqlite = str(database_url).startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)


if is_sqlite:
    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
