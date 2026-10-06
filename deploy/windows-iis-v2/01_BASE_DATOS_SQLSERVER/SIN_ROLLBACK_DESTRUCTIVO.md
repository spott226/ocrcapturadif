# Política de regreso de base de datos

No se entrega un script que elimine las columnas o tablas agregadas. Después de que la
aplicación comience a escribir usuarios y tipos de apoyo, un `DROP` podría destruir
información y dificultar la recuperación.

La migración es compatible hacia atrás porque conserva `people.name` y
`people.address`. Si la versión nueva de IIS presenta problemas:

1. Revierta únicamente el código con `REVERTIR_ACTUALIZACION.ps1`.
2. Deje intactas las columnas y tablas nuevas.
3. Si una contingencia exige regresar toda la base, el DBA debe restaurar el respaldo
   verificado en un ambiente controlado y seguir su procedimiento institucional. No
   sobrescriba producción sin autorización y sin resguardar los registros posteriores.
