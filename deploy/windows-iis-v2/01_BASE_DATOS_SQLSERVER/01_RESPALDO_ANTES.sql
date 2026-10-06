/*
  CAMBIE únicamente la ruta. Debe ser una ruta local del servidor SQL y el servicio
  SQL Server debe tener permiso de escritura. No use una carpeta del servidor IIS.
  Si no tiene una ruta autorizada, NO ejecute este archivo; solicite el respaldo al DBA.
*/
USE [master];
GO
SET NOCOUNT ON;

IF DB_ID(N'CapturaApoyosDIF') IS NULL
    THROW 51010, N'No existe la base CapturaApoyosDIF. No se creó respaldo.', 1;

DECLARE @Ruta nvarchar(4000) = N''; -- PEGAR AQUÍ LA RUTA AUTORIZADA DEL SERVIDOR SQL

IF NULLIF(LTRIM(RTRIM(@Ruta)), N'') IS NULL
    THROW 51011, N'Edite y confirme la ruta autorizada antes de ejecutar el respaldo.', 1;

BACKUP DATABASE [CapturaApoyosDIF]
TO DISK = @Ruta
WITH COPY_ONLY, INIT, CHECKSUM, STATS = 10;

RESTORE VERIFYONLY FROM DISK = @Ruta WITH CHECKSUM;
PRINT N'RESPALDO Y VERIFYONLY TERMINADOS.';
GO
