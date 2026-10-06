# Actualizacion Captura Apoyos DIF — Windows Server 2022 / IIS 10

Este directorio separa deliberadamente la actualizacion en dos paquetes. No copie la
aplicacion al servidor de SQL ni ejecute los archivos SQL en el servidor de IIS.

## Orden obligatorio

1. Conservar una copia de la version que hoy funciona usando
   `02_APLICATIVO_IIS\RECOPILAR_VERSION_ACTUAL.ps1`.
2. Fusionar y probar esas modificaciones con la nueva version. No sustituir `app` con
   una copia antigua del repositorio.
3. En el **servidor de base de datos**, seguir
   `01_BASE_DATOS_SQLSERVER\LEEME_BASE_DATOS.md` y aplicar primero la migracion.
4. Confirmar que `04_VERIFICAR.sql` termina correctamente.
5. En el **servidor aplicativo**, seguir
   `02_APLICATIVO_IIS\LEEME_APLICATIVO.md`.
6. Probar con documentos ficticios antes de capturar datos personales.

La migracion conserva `people.name` y `people.address`; es aditiva y permite regresar
el codigo de IIS sin borrar las nuevas columnas. Ningun script ejecuta `iisreset`,
modifica bindings, cambia el dominio o toca el certificado HTTPS.
