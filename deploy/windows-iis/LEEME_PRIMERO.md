# Captura Apoyos DIF — entrega para IIS y SQL Server

Esta carpeta contiene la aplicación y los instaladores. **No contiene los registros que estaban en Railway**, contraseñas reales ni fotografías de INE.

## Lo que debe tener el servidor

1. Windows Server con IIS 8 o posterior.
2. Python 3.11 o 3.12 x64.
3. IIS HttpPlatformHandler x64.
4. Microsoft ODBC Driver 18 for SQL Server x64.
5. SQL Server Database Engine accesible. SQL Server Management Studio (SSMS) sirve para administrarlo, pero SSMS por sí solo no es la base de datos.
6. Certificado HTTPS institucional. La cámara del celular requiere un sitio seguro.
7. Recomendado: Microsoft Visual C++ Redistributable x64. Tesseract 5 con idioma español es opcional como respaldo; RapidOCR es el lector principal.

## Instalación corta

1. Copie toda la carpeta a una ubicación definitiva, por ejemplo `C:\inetpub\CapturaApoyosDIF`. No la ejecute desde Descargas ni desde una carpeta temporal.
2. En SSMS, un administrador ejecuta `SQL\01_CREAR_BASE_Y_TABLA.sql`.
3. Defina la cuenta que usará el Application Pool y concédale solamente lectura/escritura en `CapturaApoyosDIF`. El final del script SQL contiene el ejemplo para SQL Server e IIS en el mismo equipo. Si SQL está en otro servidor, use una cuenta de servicio de dominio.
4. Abra PowerShell **como administrador** en esta carpeta y ejecute:

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\INSTALAR_IIS.ps1 -BaseDatos SqlServer -ServidorSql "SERVIDOR\INSTANCIA"
   ```

   El instalador pedirá el correo y las contraseñas sin incluirlas en esta entrega. También puede usar `-AutenticacionSql Sql` si Sistemas exige una cuenta SQL.

   La conexión valida el certificado de SQL Server de forma predeterminada. Use `-ConfiarCertificadoSql` únicamente si el DBA confirma que el servidor interno usa un certificado propio que ya fue verificado por otra vía.

5. Ejecute `./VERIFICAR_SERVIDOR.ps1`.
6. En IIS agregue al sitio un enlace HTTPS con el certificado del DIF y configure la redirección de HTTP a HTTPS. Publique la aplicación como sitio raíz con un nombre propio, no como subcarpeta `/dif`.
7. Desde una PC pruebe `https://NOMBRE-DEL-SITIO/salud`; debe responder `{"status":"ok"}`. Luego pruebe inicio de sesión, alta, Excel, eliminación y reinicio del Application Pool.
8. Desde un teléfono conectado a la red autorizada abra la misma dirección HTTPS y haga la aceptación únicamente con un documento ficticio.

## Prueba temporal con SQLite

Si todavía no está lista la base SQL, puede preparar una demostración en un solo servidor:

```powershell
.\INSTALAR_IIS.ps1 -BaseDatos SQLite
```

No se recomienda SQLite para varias capturistas ni como destino definitivo. Los datos quedan en `data\captura_apoyos.sqlite3` y se deben respaldar junto con los archivos `-wal` y `-shm` mientras el sitio esté detenido.

## Recuperar registros anteriores

- Si descargó `registros_dif.xlsx` desde Railway, primero simule y luego importe:

  ```powershell
  .\IMPORTAR_EXCEL.ps1 -Archivo "D:\Respaldo\registros_dif.xlsx" -Simular
  .\IMPORTAR_EXCEL.ps1 -Archivo "D:\Respaldo\registros_dif.xlsx"
  ```

- El importador evita duplicados por CURP o teléfono y solo muestra conteos, no datos personales.
- El Excel anterior contiene los campos visibles exportados, no todas las columnas históricas. Si Railway aún permite un respaldo PostgreSQL, consérvelo cifrado y entregue la migración a Sistemas; un `pg_dump` no se restaura directamente en SSMS.
- Si no existe Excel ni respaldo de la base anterior, esta carpeta no puede reconstruir esos registros.

## Seguridad y operación

- Proteja `.env`: contiene secretos. Nunca lo envíe por correo, WhatsApp o Git.
- No guarde fotos de INE. La aplicación las procesa en memoria y solo guarda los datos confirmados.
- Restrinja el sitio a la red/VPN del DIF y cambie la contraseña cuando cambie el personal autorizado.
- Configure respaldos automáticos de SQL Server y pruebe una restauración. `SQL\02_RESPALDO_EJEMPLO.sql` es una guía para el DBA.
- Use una sola instancia de la aplicación al inicio. Para más concurrencia, Sistemas debe hacer pruebas de carga porque el OCR consume memoria y CPU.
- Revise `logs\httpplatform*.log` si IIS devuelve error 500. Detenga el sitio antes de compartir esos logs y verifique que no contengan información sensible.
