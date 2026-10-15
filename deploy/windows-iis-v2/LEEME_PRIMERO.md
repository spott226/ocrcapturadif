# Actualizacion Captura Apoyos DIF — Windows Server 2022 / IIS 10

Este directorio separa deliberadamente la actualizacion en dos paquetes. No copie la
aplicacion al servidor de SQL ni ejecute los archivos SQL en el servidor de IIS.

## Orden obligatorio

1. La versión que funcionaba en IIS ya fue recopilada y fusionada el 2026-10-15. No
   utilice una copia anterior del paquete.
2. En el **servidor de base de datos**, seguir
   `01_BASE_DATOS_SQLSERVER\LEEME_BASE_DATOS.md` y aplicar primero la migracion.
3. Confirmar que `04_VERIFICAR.sql` termina correctamente.
4. En el **servidor aplicativo**, seguir
   `02_APLICATIVO_IIS\LEEME_APLICATIVO.md`.
5. Probar con documentos ficticios antes de capturar datos personales.

La migracion conserva `people.name` y `people.address`; es aditiva y permite regresar
el codigo de IIS sin borrar las nuevas columnas. Ningun script ejecuta `iisreset`,
modifica bindings, cambia el dominio o toca el certificado HTTPS.
