# Paquete 02 — Aplicativo IIS

Diseñado para Windows Server 2022, IIS 10 y Windows PowerShell 5.1. Actualiza
únicamente el código de `CapturaApoyosDIF`; no ejecuta `iisreset` y no modifica sitios,
bindings, dominio, puerto ni certificado.

## Versión del servidor ya conservada

El `main.py` del servidor fue modificado después del despliegue original. Esa versión
ya fue recopilada el 2026-10-15, comparada y fusionada con este paquete. Su huella es:

```text
712b2f34721ee17bdda671da92ef5a669d696841e3a35fab60259665a83e0db9
```

`VERSION_BASE_SERVIDOR.sha256` contiene esa misma huella. El actualizador la compara
con el código instalado para evitar sobrescribir una versión distinta. No necesita
ejecutar nuevamente `RECOPILAR_VERSION_ACTUAL.ps1` salvo que alguien modifique el código
del servidor después de esta recopilación.

## Contenido que debe tener `payload`

La carpeta `payload` se arma en desarrollo y debe contener, como mínimo:

- `app\` con el código, plantillas y estáticos actualizados;
- `tools\verificar_servidor.py`;
- `run_iis.py`;
- `requirements.txt`;
- los demás archivos de código necesarios para ejecutar la aplicación.

No coloque en `payload`: `.env`, `.venv`, `data`, `logs`, `backups` ni `web.config`.
El script rechaza el paquete si encuentra alguno. Nunca incluya credenciales, fotos de
INE, archivos Excel exportados o una base local.

## Orden de instalación

1. Aplique y verifique primero el paquete `01_BASE_DATOS_SQLSERVER`.
2. Copie esta carpeta completa a una ubicación temporal del servidor aplicativo, por
   ejemplo `C:\Actualizaciones\CapturaApoyosDIF_2026-10` (fuera de
   `C:\inetpub\CapturaApoyosDIF`).
3. Abra **Windows PowerShell como administrador**.
4. Abra la configuración existente sin compartir su contenido:

```powershell
notepad "C:\inetpub\CapturaApoyosDIF\.env"
```

Confirme que la conexión `SQLSERVER_*` apunte a la base nueva y agregue esta línea,
porque el IIS actual publica la aplicación bajo esa ruta:

```dotenv
PUBLIC_PREFIX=/CapturaApoyosDIF
```

Guarde el archivo. No cambie `SECRET_KEY`, `ADMIN_EMAIL` ni contraseñas durante esta
actualización.

5. Ejecute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
Set-Location "C:\Actualizaciones\CapturaApoyosDIF_2026-10"
.\ACTUALIZAR_IIS.ps1 -ConfirmarCodigoFusionado
```

Si la huella no coincide, el script se detiene antes de tocar IIS. Investigue primero.
Use `-AceptarBaseDistinta` únicamente cuando Sistemas haya comprobado y fusionado las
diferencias de forma deliberada:

```powershell
.\ACTUALIZAR_IIS.ps1 -ConfirmarCodigoFusionado -AceptarBaseDistinta
```

El proceso:

- guarda una copia en `C:\inetpub\CapturaApoyosDIF\backups\actualizaciones`;
- preserva `.env`, `.venv`, `data`, `logs`, `backups` y `web.config`;
- detiene e inicia solamente el pool `CapturaApoyosDIF`;
- instala requisitos solamente si es necesario;
- verifica importaciones, esquema SQL y estado del pool;
- restaura automáticamente el código anterior si falla.

Puede agregar la URL ya configurada para una verificación HTTP final:

```powershell
.\ACTUALIZAR_IIS.ps1 -ConfirmarCodigoFusionado `
  -UrlVerificacion "https://dominio-institucional/CapturaApoyosDIF/salud"
```

## Reversión manual

El script de actualización muestra la ruta exacta del respaldo. Para regresar el
código, sin tocar base de datos, dominio ni certificado:

```powershell
.\REVERTIR_ACTUALIZACION.ps1 -ConfirmarReversion
```

Por omisión utiliza el respaldo más reciente. También acepta `-Respaldo` con una ruta
ubicada dentro de `backups\actualizaciones`. Las columnas nuevas de SQL se conservan.

## Recomendación operativa

Realice primero una captura ficticia y valide ambos perfiles:

- `capturista`: puede capturar y guardar, pero no listar, exportar, eliminar ni
  administrar usuarios;
- `superadmin`: puede consultar, exportar y administrar usuarios y roles.

No cargue documentos reales hasta confirmar HTTPS, autenticación, permisos y respaldo.
