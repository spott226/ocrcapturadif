import os
from types import SimpleNamespace
os.environ["DATABASE_URL"] = "sqlite:///./test.sqlite3"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"
os.environ["ADMIN_EMAIL"] = "admin@example.test"
os.environ["ADMIN_PASSWORD"] = "a-secure-test-password"

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, build_database_url
from app.models import Person
from sqlalchemy import delete
from openpyxl import Workbook
from tools.importar_excel import import_workbook


def test_builds_sql_server_windows_auth_url_without_manual_password_encoding():
    sql_settings = SimpleNamespace(
        database_backend="sqlserver",
        database_url="",
        sqlserver_server=r"SERVIDOR\INSTANCIA",
        sqlserver_database="CapturaApoyosDIF",
        sqlserver_auth="windows",
        sqlserver_username="",
        sqlserver_password="",
        sqlserver_driver="ODBC Driver 18 for SQL Server",
        sqlserver_encrypt=True,
        sqlserver_trust_certificate=False,
    )
    url = build_database_url(sql_settings)
    assert url.drivername == "mssql+pyodbc"
    assert url.host == r"SERVIDOR\INSTANCIA"
    assert url.database == "CapturaApoyosDIF"
    assert url.query["Trusted_Connection"] == "yes"
    assert url.query["Encrypt"] == "yes"
    assert url.query["TrustServerCertificate"] == "no"


def test_builds_sql_server_login_url_without_exposing_password_by_default():
    sql_settings = SimpleNamespace(
        database_backend="sqlserver",
        database_url="",
        sqlserver_server="sql.dif.local",
        sqlserver_database="CapturaApoyosDIF",
        sqlserver_auth="sql",
        sqlserver_username="captura_app",
        sqlserver_password="Prueba! con espacios",
        sqlserver_driver="ODBC Driver 18 for SQL Server",
        sqlserver_encrypt=True,
        sqlserver_trust_certificate=True,
    )
    url = build_database_url(sql_settings)
    assert "Prueba" not in str(url)
    assert url.password == "Prueba! con espacios"
    assert "Trusted_Connection" not in url.query


def test_health():
    with TestClient(app) as client:
        response = client.get("/salud")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_home_requires_authentication():
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_login_save_and_export_fictitious_record():
    with SessionLocal() as db:
        db.execute(delete(Person))
        db.commit()
    with TestClient(app) as client:
        login_page = client.get("/login")
        csrf = login_page.text.split('name="csrf" value="', 1)[1].split('"', 1)[0]
        response = client.post("/login", data={"email": "admin@example.test", "password": "a-secure-test-password", "csrf": csrf})
        assert response.status_code == 200
        csrf = response.text.split('name="csrf" value="', 1)[1].split('"', 1)[0]
        saved = client.post("/registros", data={
            "name": "PERSONA FICTICIA PRUEBA", "address": "DOMICILIO FICTICIO",
            "curp": "PULA900101MDFRPN09", "phone": "4491234567",
            "leader": "LIDER FICTICIO", "csrf": csrf,
        })
        assert saved.status_code == 200
        assert "Número de teléfono" in saved.text
        assert "Dirección" in saved.text
        assert "Líder" in saved.text
        assert "OCR del reverso" not in saved.text
        assert "PERSONA FICTICIA PRUEBA" in saved.text
        assert "4491234567" in saved.text
        assert "LIDER FICTICIO" in saved.text
        exported = client.get("/exportar.xlsx")
        assert exported.status_code == 200
        assert exported.content[:2] == b"PK"
        with SessionLocal() as db:
            person_id = db.query(Person.id).filter(Person.curp == "PULA900101MDFRPN09").scalar()
        deleted = client.post(
            f"/registros/{person_id}/eliminar", data={"csrf": csrf},
            follow_redirects=False,
        )
        assert deleted.status_code == 303
        with SessionLocal() as db:
            assert db.get(Person, person_id) is None


def test_rejects_invalid_phone_length():
    with TestClient(app) as client:
        login_page = client.get("/login")
        csrf = login_page.text.split('name="csrf" value="', 1)[1].split('"', 1)[0]
        response = client.post("/login", data={
            "email": "admin@example.test", "password": "a-secure-test-password", "csrf": csrf,
        })
        csrf = response.text.split('name="csrf" value="', 1)[1].split('"', 1)[0]
        rejected = client.post("/registros", data={
            "name": "PERSONA FICTICIA", "phone": "449123", "csrf": csrf,
        })
        assert rejected.status_code == 200
        assert "El teléfono debe tener 10 dígitos" in rejected.text


def test_records_are_paginated_ten_per_page():
    with SessionLocal() as db:
        db.execute(delete(Person))
        db.add_all([
            Person(
                name=f"PERSONA FICTICIA {number:02d}",
                curp=f"FICTICIO{number:010d}",
                created_by="admin@example.test",
            )
            for number in range(1, 12)
        ])
        db.commit()

    with TestClient(app) as client:
        login_page = client.get("/login")
        csrf = login_page.text.split('name="csrf" value="', 1)[1].split('"', 1)[0]
        client.post("/login", data={
            "email": "admin@example.test",
            "password": "a-secure-test-password",
            "csrf": csrf,
        })

        first_page = client.get("/")
        assert "11 en total · Página 1 de 2" in first_page.text
        assert first_page.text.count('class="record-card"') == 10
        assert "Siguiente" in first_page.text

        second_page = client.get("/?pagina=2")
        assert "11 en total · Página 2 de 2" in second_page.text
        assert second_page.text.count('class="record-card"') == 1
        assert "Anterior" in second_page.text

    with SessionLocal() as db:
        db.execute(delete(Person))
        db.commit()


def test_excel_import_can_simulate_and_avoids_fictitious_duplicates(tmp_path):
    with SessionLocal() as db:
        db.execute(delete(Person))
        db.commit()

    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "ID", "Nombre completo", "CURP", "Dirección", "Número de teléfono",
        "Líder", "Capturó", "Fecha de captura",
    ])
    sheet.append([
        1, "PERSONA FICTICIA EXCEL", "PULA900101MDFRPN09", "DOMICILIO FICTICIO",
        "4491234567", "LIDER FICTICIO", "captura@example.test", "2026-10-05 10:30:00",
    ])
    sheet.append([
        2, "DUPLICADO FICTICIO", "PULA900101MDFRPN09", "OTRO DOMICILIO FICTICIO",
        "", "LIDER FICTICIO", "captura@example.test", "2026-10-05 10:31:00",
    ])
    path = tmp_path / "registros_ficticios.xlsx"
    workbook.save(path)

    assert import_workbook(path, simulate=True) == (1, 1, 0)
    with SessionLocal() as db:
        assert db.query(Person).count() == 0

    assert import_workbook(path) == (1, 1, 0)
    with SessionLocal() as db:
        saved = db.query(Person).one()
        assert saved.name == "PERSONA FICTICIA EXCEL"
        assert saved.address == "DOMICILIO FICTICIO"

    with SessionLocal() as db:
        db.execute(delete(Person))
        db.commit()
