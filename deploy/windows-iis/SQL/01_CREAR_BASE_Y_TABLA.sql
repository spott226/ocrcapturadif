/*
  Ejecutar en SQL Server Management Studio con una cuenta administradora.
  No crea contraseñas ni usuarios inseguros. La aplicación usa dbo.people.
*/
USE [master];
GO

IF DB_ID(N'CapturaApoyosDIF') IS NULL
BEGIN
    CREATE DATABASE [CapturaApoyosDIF];
END;
GO

USE [CapturaApoyosDIF];
GO

IF OBJECT_ID(N'dbo.people', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.people
    (
        id                  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_people PRIMARY KEY,
        name                NVARCHAR(180) NOT NULL,
        address             NVARCHAR(MAX) NOT NULL CONSTRAINT DF_people_address DEFAULT N'',
        curp                NVARCHAR(18) NOT NULL CONSTRAINT DF_people_curp DEFAULT N'',
        phone               NVARCHAR(15) NOT NULL CONSTRAINT DF_people_phone DEFAULT N'',
        leader              NVARCHAR(180) NOT NULL CONSTRAINT DF_people_leader DEFAULT N'',
        voter_key           NVARCHAR(24) NOT NULL CONSTRAINT DF_people_voter_key DEFAULT N'',
        birth_date          NVARCHAR(20) NOT NULL CONSTRAINT DF_people_birth_date DEFAULT N'',
        sex_or_gender       NVARCHAR(20) NOT NULL CONSTRAINT DF_people_sex_or_gender DEFAULT N'',
        state_code          NVARCHAR(20) NOT NULL CONSTRAINT DF_people_state_code DEFAULT N'',
        municipality_code   NVARCHAR(20) NOT NULL CONSTRAINT DF_people_municipality_code DEFAULT N'',
        section             NVARCHAR(10) NOT NULL CONSTRAINT DF_people_section DEFAULT N'',
        locality_code       NVARCHAR(20) NOT NULL CONSTRAINT DF_people_locality_code DEFAULT N'',
        registration_year   NVARCHAR(20) NOT NULL CONSTRAINT DF_people_registration_year DEFAULT N'',
        issue_year          NVARCHAR(10) NOT NULL CONSTRAINT DF_people_issue_year DEFAULT N'',
        cic                 NVARCHAR(20) NOT NULL CONSTRAINT DF_people_cic DEFAULT N'',
        ocr_code            NVARCHAR(20) NOT NULL CONSTRAINT DF_people_ocr_code DEFAULT N'',
        valid_until         NVARCHAR(20) NOT NULL CONSTRAINT DF_people_valid_until DEFAULT N'',
        created_by          NVARCHAR(254) NOT NULL,
        created_at          DATETIMEOFFSET(6) NOT NULL CONSTRAINT DF_people_created_at DEFAULT SYSDATETIMEOFFSET()
    );

    CREATE INDEX IX_people_name ON dbo.people(name);
    CREATE INDEX IX_people_curp ON dbo.people(curp);
    CREATE INDEX IX_people_phone ON dbo.people(phone);
    CREATE INDEX IX_people_voter_key ON dbo.people(voter_key);
    CREATE INDEX IX_people_cic ON dbo.people(cic);
    CREATE INDEX IX_people_ocr_code ON dbo.people(ocr_code);
END;
GO

/*
  ACCESO DE LA APLICACIÓN

  Autenticación de Windows, SQL Server en el mismo equipo que IIS:
  reemplace el nombre del pool si Sistemas usa otro y quite los comentarios.

  CREATE LOGIN [IIS APPPOOL\CapturaApoyosDIF] FROM WINDOWS;
  USE [CapturaApoyosDIF];
  CREATE USER [IIS APPPOOL\CapturaApoyosDIF]
      FOR LOGIN [IIS APPPOOL\CapturaApoyosDIF] WITH DEFAULT_SCHEMA = dbo;
  ALTER ROLE db_datareader ADD MEMBER [IIS APPPOOL\CapturaApoyosDIF];
  ALTER ROLE db_datawriter ADD MEMBER [IIS APPPOOL\CapturaApoyosDIF];

  Si SQL Server está en otro equipo, Sistemas debe ejecutar el pool con una
  cuenta de servicio de dominio y crear LOGIN/USER para esa cuenta. No conceda
  sysadmin ni db_owner a la cuenta de la aplicación.
*/
