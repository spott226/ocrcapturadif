# Paquete 01 — Base de datos SQL Server

Compatible con SQL Server administrado desde SQL Server Management Studio (SSMS).
Debe ejecutarlo una persona autorizada sobre la base `CapturaApoyosDIF`.

## Antes de empezar

- Cierre o pause las capturas durante estos minutos.
- Confirme que está conectado a la instancia correcta.
- No use una copia de producción para ensayar; pruebe primero en respaldo/restauración
  si el área de Sistemas dispone de ese ambiente.
- Los scripts no contienen usuarios ni contraseñas.

## Orden exacto en SSMS

1. Abra `00_PREVERIFICAR.sql`, revise que la instancia y la base sean correctas y
   ejecútelo. No debe mostrar errores.
2. Edite solamente la ruta autorizada de `01_RESPALDO_ANTES.sql` y ejecútelo. La cuenta
   del servicio SQL Server debe poder escribir en esa carpeta del **servidor SQL**.
   Si no existe una ruta autorizada o el DBA ya usa otro mecanismo institucional, **no
   ejecute este archivo con la ruta de ejemplo**: deténgase y pida al DBA un respaldo
   verificado antes de continuar.
3. Ejecute `02_MIGRAR_ESQUEMA.sql`. Puede ejecutarse nuevamente: comprueba cada objeto
   antes de crearlo.
4. Cuando se reciba el catálogo definitivo, copie sus filas en
   `03_CARGAR_CATALOGO_PLANTILLA.sql`, conservando códigos únicos, y ejecútelo.
5. Ejecute `04_VERIFICAR.sql`. Debe finalizar con el mensaje `VERIFICACION SQL OK`.
6. Entregue al responsable de IIS únicamente la confirmación de que la migración quedó
   aplicada. No comparta credenciales ni fotografías que muestren contraseñas.

## Cambios realizados

- En `dbo.people` agrega `given_names`, `paternal_surname`, `maternal_surname`,
  `municipality` y `support_type_id`.
- Crea `dbo.support_types` para el catálogo de tipos de apoyo.
- Crea `dbo.app_users` con roles `superadmin` y `capturista`.
- Crea la llave foránea e índice del tipo de apoyo.
- Conserva `name`, `address` y todos los registros anteriores.

La migración no intenta separar automáticamente los nombres existentes: hacerlo sin
revisión humana puede intercambiar nombres y apellidos compuestos.

## Regreso ante una falla

No elimine columnas ni tablas nuevas. Consulte `SIN_ROLLBACK_DESTRUCTIVO.md`. Como el
cambio es aditivo, el código anterior puede seguir usando `name` y `address` mientras
Sistemas revisa la actualización.
