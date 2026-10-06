import os
import re
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import select

os.environ["DATABASE_URL"] = "sqlite:///./test.sqlite3"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"
os.environ["ADMIN_EMAIL"] = "admin@example.test"
os.environ["ADMIN_PASSWORD"] = "a-secure-test-password"

from app.database import Base, SessionLocal, build_database_url, engine
from app.main import app
from app.models import AppUser, Person, SupportType
from tools.importar_excel import import_workbook


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def csrf_from(response) -> str:
    match = re.search(r'name="csrf" value="([^"]+)"', response.text)
    assert match, response.text[:500]
    return match.group(1)


def login(client: TestClient, email="admin@example.test", password="a-secure-test-password"):
    login_page = client.get("/login")
    response = client.post(
        "/login",
        data={"email": email, "password": password, "csrf": csrf_from(login_page)},
    )
    assert response.status_code == 200
    return response


def create_support(client: TestClient, code="DESPENSA", name="Apoyo alimentario") -> int:
    home = client.get("/")
    response = client.post(
        "/admin/tipos-apoyo",
        data={
            "code": code,
            "name": name,
            "sort_order": 10,
            "csrf": csrf_from(home),
        },
    )
    assert response.status_code == 200
    with SessionLocal() as db:
        return db.scalar(select(SupportType.id).where(SupportType.code == code))


def valid_record(csrf: str, support_type_id: int, **overrides):
    data = {
        "given_names": "PERSONA",
        "paternal_surname": "FICTICIA",
        "maternal_surname": "PRUEBA",
        "municipality": "Aguascalientes",
        "support_type_id": str(support_type_id),
        "curp": "PULA900101MDFRPN09",
        "phone": "4491234567",
        "leader": "LIDER FICTICIO",
        "csrf": csrf,
    }
    data.update(overrides)
    return data


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


def test_health_and_home_authentication():
    with TestClient(app) as client:
        health = client.get("/salud")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_superadmin_can_save_export_and_delete_fictitious_record():
    with TestClient(app) as client:
        login(client)
        support_id = create_support(client)
        saved = client.post(
            "/registros",
            data=valid_record(csrf_from(client.get("/")), support_id),
        )
        assert saved.status_code == 200
        assert "PERSONA FICTICIA PRUEBA" in saved.text
        assert "Aguascalientes" in saved.text
        assert "Apoyo alimentario" in saved.text

        with SessionLocal() as db:
            person = db.scalar(select(Person).where(Person.curp == "PULA900101MDFRPN09"))
            assert person is not None
            assert person.name == "PERSONA FICTICIA PRUEBA"
            assert person.address == ""
            assert person.given_names == "PERSONA"
            assert person.paternal_surname == "FICTICIA"
            assert person.maternal_surname == "PRUEBA"
            assert person.municipality == "Aguascalientes"
            assert person.support_type_id == support_id
            person_id = person.id

        exported = client.get("/exportar.xlsx")
        assert exported.status_code == 200
        workbook = load_workbook(BytesIO(exported.content), read_only=True)
        rows = list(workbook.active.iter_rows(values_only=True))
        assert rows[0][:9] == (
            "ID", "Nombre(s)", "Apellido paterno", "Apellido materno",
            "Nombre completo", "CURP", "Municipio", "Código de apoyo", "Tipo de apoyo",
        )
        assert rows[1][1:9] == (
            "PERSONA", "FICTICIA", "PRUEBA", "PERSONA FICTICIA PRUEBA",
            "PULA900101MDFRPN09", "Aguascalientes", "DESPENSA", "Apoyo alimentario",
        )
        workbook.close()

        deleted = client.post(
            f"/registros/{person_id}/eliminar",
            data={"csrf": csrf_from(client.get("/"))},
            follow_redirects=False,
        )
        assert deleted.status_code == 303
        with SessionLocal() as db:
            assert db.get(Person, person_id) is None


def test_rejects_invalid_phone_length():
    with TestClient(app) as client:
        login(client)
        support_id = create_support(client)
        response = client.post(
            "/registros",
            data=valid_record(csrf_from(client.get("/")), support_id, phone="449123"),
        )
        assert response.status_code == 200
        assert "El teléfono debe tener 10 dígitos" in response.text


def test_records_are_paginated_ten_per_page():
    with TestClient(app) as client:
        login(client)
        with SessionLocal() as db:
            db.add_all([
                Person(
                    name=f"PERSONA FICTICIA {number:02d}",
                    given_names="PERSONA",
                    paternal_surname=f"FICTICIA {number:02d}",
                    municipality="Aguascalientes",
                    curp=f"FICTICIO{number:010d}"[:18],
                    created_by="admin@example.test",
                )
                for number in range(1, 12)
            ])
            db.commit()

        first_page = client.get("/")
        assert "11 en total · Página 1 de 2" in first_page.text
        assert first_page.text.count('class="record-card"') == 10
        second_page = client.get("/?pagina=2")
        assert "11 en total · Página 2 de 2" in second_page.text
        assert second_page.text.count('class="record-card"') == 1


def test_capturista_can_capture_but_cannot_view_export_delete_or_administer():
    with TestClient(app) as admin:
        login(admin)
        support_id = create_support(admin)
        response = admin.post(
            "/admin/usuarios",
            data={
                "email": "captura@example.test",
                "password": "captura-segura-123",
                "role": "capturista",
                "csrf": csrf_from(admin.get("/")),
            },
        )
        assert response.status_code == 200

        with TestClient(app) as capturista:
            home = login(capturista, "captura@example.test", "captura-segura-123")
            assert "Registros</h2>" not in home.text
            assert "Exportar Excel" not in home.text
            assert capturista.get("/exportar.xlsx").status_code == 403
            assert capturista.get("/admin/usuarios").status_code == 403
            assert capturista.get("/admin/tipos-apoyo").status_code == 403

            saved = capturista.post(
                "/registros",
                data=valid_record(csrf_from(capturista.get("/")), support_id),
            )
            assert saved.status_code == 200
            assert "Registro guardado correctamente" in saved.text
            assert "PERSONA FICTICIA PRUEBA" not in saved.text

            with SessionLocal() as db:
                person_id = db.scalar(select(Person.id))
            forbidden = capturista.post(
                f"/registros/{person_id}/eliminar",
                data={"csrf": csrf_from(capturista.get("/"))},
                follow_redirects=False,
            )
            assert forbidden.status_code == 403


def test_superadmin_cannot_disable_or_demote_self():
    with TestClient(app) as client:
        login(client)
        with SessionLocal() as db:
            admin_id = db.scalar(select(AppUser.id).where(AppUser.email == "admin@example.test"))
        csrf = csrf_from(client.get("/"))
        assert client.post(
            f"/admin/usuarios/{admin_id}/estado",
            data={"active": "0", "csrf": csrf},
        ).status_code == 400
        assert client.post(
            f"/admin/usuarios/{admin_id}/rol",
            data={"role": "capturista", "csrf": csrf},
        ).status_code == 400


def test_excel_import_supports_legacy_and_v2_without_writing_in_simulation(tmp_path):
    with TestClient(app):
        with SessionLocal() as db:
            db.add(SupportType(code="DESPENSA", name="Apoyo alimentario", active=True))
            db.commit()

        legacy = Workbook()
        sheet = legacy.active
        sheet.append(["Nombre completo", "CURP", "Dirección", "Número de teléfono"])
        sheet.append([
            "PERSONA LEGADA FICTICIA", "LEGA900101MDFRPN09",
            "DOMICILIO FICTICIO", "4491111111",
        ])
        legacy_path = tmp_path / "legacy.xlsx"
        legacy.save(legacy_path)
        assert import_workbook(legacy_path, simulate=True) == (1, 0, 0)
        with SessionLocal() as db:
            assert db.scalar(select(Person.id)) is None
        assert import_workbook(legacy_path) == (1, 0, 0)

        modern = Workbook()
        sheet = modern.active
        sheet.append([
            "Nombre(s)", "Apellido paterno", "Apellido materno", "CURP",
            "Municipio", "Código de apoyo", "Número de teléfono",
        ])
        sheet.append([
            "OTRA", "PERSONA", "FICTICIA", "OTRA900101MDFRPN09",
            "Aguascalientes", "DESPENSA", "4492222222",
        ])
        sheet.append([
            "TIPO", "DESCONOCIDO", "FICTICIO", "TIPO900101MDFRPN09",
            "Aguascalientes", "NO-EXISTE", "4493333333",
        ])
        modern_path = tmp_path / "v2.xlsx"
        modern.save(modern_path)
        assert import_workbook(modern_path) == (1, 0, 1)

        with SessionLocal() as db:
            rows = list(db.scalars(select(Person).order_by(Person.id)).all())
            assert len(rows) == 2
            assert rows[0].name == "PERSONA LEGADA FICTICIA"
            assert rows[0].address == "DOMICILIO FICTICIO"
            assert rows[0].support_type_id is None
            assert rows[1].name == "OTRA PERSONA FICTICIA"
            assert rows[1].address == ""
            assert rows[1].support_type.code == "DESPENSA"
