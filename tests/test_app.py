import os
os.environ["DATABASE_URL"] = "sqlite:///./test.sqlite3"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"
os.environ["ADMIN_EMAIL"] = "admin@example.test"
os.environ["ADMIN_PASSWORD"] = "a-secure-test-password"

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Person
from sqlalchemy import delete


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
            "curp": "PULA900101MDFRPN09", "voter_key": "PRLBAN90010109M100",
            "birth_date": "01/01/1990", "section": "1234", "cic": "123456789",
            "ocr_code": "1234567890123", "valid_until": "2036", "csrf": csrf,
        })
        assert saved.status_code == 200
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
