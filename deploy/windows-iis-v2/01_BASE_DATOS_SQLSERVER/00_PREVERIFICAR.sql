/* Solo lectura. Ejecutar conectado a la instancia que aloja CapturaApoyosDIF. */
SET NOCOUNT ON;

SELECT
    CAST(SERVERPROPERTY(N'MachineName') AS nvarchar(128)) AS Servidor,
    COALESCE(CAST(SERVERPROPERTY(N'InstanceName') AS nvarchar(128)), N'(predeterminada)') AS Instancia,
    CAST(SERVERPROPERTY(N'ProductVersion') AS nvarchar(128)) AS VersionSql,
    ORIGINAL_LOGIN() AS InicioSesion;

IF DB_ID(N'CapturaApoyosDIF') IS NULL
    THROW 51000, N'No existe la base CapturaApoyosDIF en esta instancia. Deténgase.', 1;

IF OBJECT_ID(N'CapturaApoyosDIF.dbo.people', N'U') IS NULL
    THROW 51001, N'No existe CapturaApoyosDIF.dbo.people. Deténgase.', 1;

SELECT
    d.name AS BaseDatos,
    d.state_desc AS Estado,
    d.recovery_model_desc AS Recuperacion,
    d.user_access_desc AS Acceso
FROM sys.databases AS d
WHERE d.name = N'CapturaApoyosDIF';

SELECT
    c.name AS ColumnaExistente,
    TYPE_NAME(c.user_type_id) AS Tipo,
    c.max_length AS LongitudBytes,
    c.is_nullable AS PermiteNulos
FROM CapturaApoyosDIF.sys.columns AS c
WHERE c.object_id = OBJECT_ID(N'CapturaApoyosDIF.dbo.people')
  AND c.name IN
      (N'name', N'address', N'curp', N'leader', N'given_names', N'paternal_surname',
       N'maternal_surname', N'municipality', N'support_type_id')
ORDER BY c.column_id;

PRINT N'PREVERIFICACION OK. Revise servidor, instancia y base antes de continuar.';
