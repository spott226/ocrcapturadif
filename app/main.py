import re
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openpyxl import Workbook
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from .config import get_settings
from .database import Base, engine, get_db
from .models import Person
from .ocr import extract_image
from .security import csrf_token, password_hash, valid_csrf, verify_password

settings = get_settings()
BASE = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="DIF · Captura Apoyos", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=settings.cookie_secure, same_site="lax", max_age=28800)
if settings.cookie_secure:
    app.add_middleware(HTTPSRedirectMiddleware)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")
admin_hash = password_hash.hash(settings.admin_password)


@app.exception_handler(HTTPException)
async def friendly_http_errors(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse("/login", status_code=303)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.middleware("http")
async def privacy_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(), microphone=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'; form-action 'self'; frame-ancestors 'none'"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path != "/salud" and not request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def page(request: Request, name: str, **context):
    context.update(request=request, user=request.session.get("user"), csrf=csrf_token(request.session))
    return templates.TemplateResponse(request, name, context)


def require_user(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(401, "Inicie sesión")
    return user


def require_csrf(request: Request, token: str):
    if not valid_csrf(request.session, token):
        raise HTTPException(403, "Solicitud no válida")


@app.get("/salud")
def health():
    return {"status": "ok"}


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return page(request, "login.html")


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, email: str = Form(...), password: str = Form(...), csrf: str = Form(...)):
    require_csrf(request, csrf)
    if email.casefold() != settings.admin_email.casefold() or not verify_password(password, admin_hash):
        return page(request, "login.html", error="Correo o contraseña incorrectos" )
    request.session.clear()
    request.session["user"] = settings.admin_email
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request, csrf: str = Form(...)):
    require_csrf(request, csrf)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    require_user(request)
    people = db.scalars(select(Person).order_by(Person.created_at.desc()).limit(100)).all()
    return page(request, "index.html", people=people)


async def read_upload(upload: UploadFile) -> bytes:
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if upload.content_type not in allowed:
        raise HTTPException(400, "Use una imagen JPG, PNG o WEBP")
    data = await upload.read(settings.max_upload_mb * 1024 * 1024 + 1)
    await upload.close()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "La imagen excede el tamaño permitido")
    return data


@app.post("/ocr", response_class=HTMLResponse)
async def ocr(request: Request, front: UploadFile = File(...), back: UploadFile | None = File(None), csrf: str = Form(...)):
    require_user(request)
    require_csrf(request, csrf)
    merged = {"name": "", "address": "", "curp": "", "voter_key": "", "valid_until": ""}
    try:
        uploads = [front] + ([back] if back and back.filename else [])
        for upload in uploads:
            fields, _raw = extract_image(await read_upload(upload))
            for key, value in fields.items():
                if value and not merged[key]:
                    merged[key] = value
    except HTTPException:
        raise
    except Exception:
        return page(request, "review.html", data=merged, error="No se pudo leer la imagen. Capture los datos manualmente.")
    return page(request, "review.html", data=merged)


@app.post("/registros", response_class=HTMLResponse)
def save(request: Request, name: str = Form(...), address: str = Form(""), curp: str = Form(""), voter_key: str = Form(""), valid_until: str = Form(""), csrf: str = Form(...), db: Session = Depends(get_db)):
    user = require_user(request)
    require_csrf(request, csrf)
    name, curp, voter_key = name.strip().upper(), curp.strip().upper(), voter_key.strip().upper()
    if curp and not re.fullmatch(r"[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d", curp):
        return page(request, "review.html", data=locals(), error="La CURP no tiene un formato válido.")
    conditions = []
    if curp: conditions.append(Person.curp == curp)
    if voter_key: conditions.append(Person.voter_key == voter_key)
    duplicates = db.scalars(select(Person).where(or_(*conditions))) .all() if conditions else []
    if duplicates:
        return page(request, "review.html", data=locals(), duplicates=duplicates, error="Posible duplicado: revise antes de continuar.")
    person = Person(name=name[:180], address=address.strip().upper()[:500], curp=curp[:18], voter_key=voter_key[:24], valid_until=valid_until.strip()[:20], created_by=user)
    db.add(person)
    db.commit()
    return RedirectResponse("/?guardado=1", status_code=303)


@app.get("/exportar.xlsx")
def export(request: Request, db: Session = Depends(get_db)):
    require_user(request)
    rows = db.scalars(select(Person).order_by(Person.created_at)).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Registros DIF"
    ws.append(["ID", "Nombre", "Domicilio", "CURP", "Clave de elector", "Vigencia", "Capturó", "Fecha"])
    for row in rows:
        ws.append([row.id, row.name, row.address, row.curp, row.voter_key, row.valid_until, row.created_by, row.created_at.replace(tzinfo=None)])
    ws.freeze_panes = "A2"
    for column in ws.columns:
        ws.column_dimensions[column[0].column_letter].width = min(max(len(str(c.value or "")) for c in column) + 2, 55)
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="registros_dif.xlsx"', "Cache-Control": "no-store"}
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
