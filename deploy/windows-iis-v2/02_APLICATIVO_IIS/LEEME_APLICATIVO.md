# Paquete 02 — Aplicativo IIS

Diseñado para Windows Server 2022, IIS 10 y Windows PowerShell 5.1. Actualiza
únicamente el código de `CapturaApoyosDIF`; no ejecuta `iisreset` y no modifica sitios,
bindings, dominio, puerto ni certificado.

## Regla crítica: conservar la versión que funciona

El `main.py` del servidor fue modificado después del despliegue original. Antes de
preparar el paquete nuevo, ejecute en el servidor aplicativo:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
Set-Location "C:\ruta\de\este\paquete"
.\RECOPILAR_VERSION_ACTUAL.ps1
```

Se crea un ZIP en `C:\Users\Public\Documents`. No incluye `.env`, `.venv`, datos,
registros, imágenes, exportaciones, bases ni secretos. Lleve ese ZIP al ambiente de
desarrollo, fusione sus cambios con la versión nueva y ejecute las pruebas. No publique
una copia antigua del repositorio.

El ZIP contiene `HUELLA_APP_SHA256.txt`. Al construir el paquete final, copie solamente
esa huella hexadecimal a `VERSION_BASE_SERVIDOR.sha256`. El actualizador la compara con
el código instalado para evitar sobrescribir una versión distinta.

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
4. Ejecute:

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
  -UrlVerificacion "https://dominio-institucional/ruta-de-salud"
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
