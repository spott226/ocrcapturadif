/*
  Ajuste la carpeta. Debe existir en el servidor de SQL y la cuenta del servicio
  SQL Server necesita permiso para escribir ahí. Pruebe también RESTORE VERIFYONLY.
*/
BACKUP DATABASE [CapturaApoyosDIF]
TO DISK = N'D:\RespaldosSQL\CapturaApoyosDIF.bak'
WITH COPY_ONLY, COMPRESSION, CHECKSUM, INIT, STATS = 10;
GO

RESTORE VERIFYONLY
FROM DISK = N'D:\RespaldosSQL\CapturaApoyosDIF.bak'
WITH CHECKSUM;
GO
