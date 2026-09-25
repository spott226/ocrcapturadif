# DIF · Captura INE (MVP)

Aplicación web móvil/escritorio para capturar frente y reverso de una INE, proponer datos con Tesseract OCR, revisarlos manualmente, detectar coincidencias y exportar registros a Excel.

## Alcance y decisiones de privacidad

- Las imágenes se leen en memoria y **no se guardan** en disco ni en la base de datos.
- El texto OCR crudo tampoco se persiste. Solo se guardan los campos confirmados por el operador.
- CURP y clave de elector activan la alerta de posible duplicado.
- Las imágenes admitidas son JPG, PNG y WEBP, con límite configurable (8 MB por defecto).
- Las cookies de sesión son `HttpOnly` y `SameSite=Lax`; en Railway debe activarse `COOKIE_SECURE=true`.
- La exportación requiere una sesión autenticada y se entrega con `Cache-Control: no-store`.
- Es un MVP con una cuenta administrativa configurada por variables. Para producción ampliada conviene integrar identidad institucional, roles, bitácora de accesos, cifrado a nivel de campo y política de retención.

Antes de usar datos reales, publique el aviso de privacidad correspondiente, documente finalidad/base legal, limite accesos, capacite operadores y defina retención y eliminación conforme a las obligaciones aplicables. No coloque documentos reales en pruebas ni repositorios.

## Ejecución local con Docker

1. Instale Docker Desktop.
2. Copie `.env.example` a `.env` y cambie `SECRET_KEY`, `ADMIN_EMAIL` y `ADMIN_PASSWORD`.
3. Cree una red y una base PostgreSQL, o use este ejemplo:

```bash
docker network create dif-red
docker run -d --name dif-postgres --network dif-red -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=dif_ine postgres:16
docker build -t dif-ine .
docker run --rm --network dif-red -p 8000:8000 --env-file .env -e DATABASE_URL=postgresql+psycopg://postgres:postgres@dif-postgres:5432/dif_ine dif-ine
```

Abra `http://localhost:8000`.

## Despliegue en Railway

1. Suba esta carpeta a un repositorio privado. No suba `.env`, imágenes o exportaciones reales.
2. En Railway cree un proyecto desde el repositorio y agregue un servicio **PostgreSQL**.
3. Configure las variables del servicio web:

   - `DATABASE_URL=${{Postgres.DATABASE_URL}}` (la aplicación normaliza automáticamente la URL de Railway para usar psycopg 3).
   - `SECRET_KEY`: cadena aleatoria de 32 bytes o más.
   - `ADMIN_EMAIL`: cuenta institucional.
   - `ADMIN_PASSWORD`: contraseña larga y única.
   - `COOKIE_SECURE=true`.

4. Railway detectará el `Dockerfile`; el chequeo de salud usa `/salud`.
5. Genere un dominio en **Settings → Networking**. Railway termina TLS y publica la app por HTTPS. No desactive la redirección HTTPS del dominio.
6. Inicie sesión, capture únicamente un documento ficticio, verifique la descarga `.xlsx` y elimine el registro/base de ensayo antes de operar.

Las tablas se crean en el arranque para simplificar el MVP. Antes de evolucionar el esquema en producción, incorpore Alembic y copias de seguridad administradas.

## Desarrollo y pruebas

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/pytest -q
```

Las pruebas incluidas validan el analizador con **texto completamente ficticio**, el estado de salud y la protección de la pantalla principal. No se reportan resultados de OCR sobre imágenes reales: la precisión depende de iluminación, enfoque, versión de credencial y cámara. La revisión humana es obligatoria.

## Prueba manual segura

Cree una imagen ficticia que diga claramente `DOCUMENTO DE PRUEBA — SIN VALIDEZ` y contenga datos inventados con formato válido. Fotografíela desde móvil, revise cada campo sugerido, corrija errores, guarde y exporte. No use credenciales de personas reales durante la aceptación.
