/*
  Plantilla idempotente. Sustituya las filas de ejemplo comentadas por el catálogo
  autorizado. code es una clave estable y única: no reutilice un código para otro apoyo.
*/
USE [CapturaApoyosDIF];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.support_types', N'U') IS NULL
    THROW 51030, N'Falta dbo.support_types. Ejecute primero 02_MIGRAR_ESQUEMA.sql.', 1;

DECLARE @Catalogo TABLE
(
    code nvarchar(50) NOT NULL PRIMARY KEY,
    name nvarchar(180) NOT NULL,
    is_active bit NOT NULL,
    sort_order int NOT NULL
);

/* EJEMPLO: quite el comentario y reemplace con el catálogo real.
INSERT INTO @Catalogo (code, name, is_active, sort_order)
VALUES
    (N'APOYO-001', N'Nombre oficial del apoyo', 1, 10),
    (N'APOYO-002', N'Otro apoyo autorizado', 1, 20);
*/

IF NOT EXISTS (SELECT 1 FROM @Catalogo)
    THROW 51031, N'La plantilla no contiene filas. Cargue el catálogo autorizado.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    UPDATE destino
       SET destino.name = origen.name,
           destino.is_active = origen.is_active,
           destino.sort_order = origen.sort_order
    FROM dbo.support_types AS destino
    INNER JOIN @Catalogo AS origen ON origen.code = destino.code;

    INSERT INTO dbo.support_types (code, name, is_active, sort_order)
    SELECT origen.code, origen.name, origen.is_active, origen.sort_order
    FROM @Catalogo AS origen
    WHERE NOT EXISTS
    (
        SELECT 1 FROM dbo.support_types AS destino WHERE destino.code = origen.code
    );

    COMMIT TRANSACTION;
    PRINT N'CATALOGO ACTUALIZADO CORRECTAMENTE.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT code, name, is_active, sort_order
FROM dbo.support_types
ORDER BY sort_order, name;
GO
