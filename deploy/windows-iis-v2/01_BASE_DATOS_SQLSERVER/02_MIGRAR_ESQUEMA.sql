/* Migración aditiva e idempotente. No borra ni renombra datos existentes. */
USE [CapturaApoyosDIF];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.people', N'U') IS NULL
    THROW 51020, N'No existe dbo.people. No se realizó ningún cambio.', 1;

BEGIN TRY
    BEGIN TRANSACTION;

    IF OBJECT_ID(N'dbo.support_types', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.support_types
        (
            id int IDENTITY(1,1) NOT NULL
                CONSTRAINT PK_support_types PRIMARY KEY,
            code nvarchar(50) NOT NULL,
            name nvarchar(180) NOT NULL,
            is_active bit NOT NULL
                CONSTRAINT DF_support_types_is_active DEFAULT (1),
            sort_order int NOT NULL
                CONSTRAINT DF_support_types_sort_order DEFAULT (0),
            CONSTRAINT UQ_support_types_code UNIQUE (code)
        );
    END;

    IF OBJECT_ID(N'dbo.app_users', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.app_users
        (
            id int IDENTITY(1,1) NOT NULL
                CONSTRAINT PK_app_users PRIMARY KEY,
            email nvarchar(254) NOT NULL,
            password_hash nvarchar(512) NOT NULL,
            role nvarchar(32) NOT NULL,
            is_active bit NOT NULL
                CONSTRAINT DF_app_users_is_active DEFAULT (1),
            created_by nvarchar(254) NOT NULL,
            created_at datetimeoffset(6) NOT NULL
                CONSTRAINT DF_app_users_created_at DEFAULT (SYSDATETIMEOFFSET()),
            last_login_at datetimeoffset(6) NULL,
            CONSTRAINT UQ_app_users_email UNIQUE (email),
            CONSTRAINT CK_app_users_role
                CHECK (role IN (N'superadmin', N'capturista'))
        );
    END;

    IF COL_LENGTH(N'dbo.people', N'given_names') IS NULL
        ALTER TABLE dbo.people ADD given_names nvarchar(120) NOT NULL
            CONSTRAINT DF_people_given_names DEFAULT (N'') WITH VALUES;

    IF COL_LENGTH(N'dbo.people', N'paternal_surname') IS NULL
        ALTER TABLE dbo.people ADD paternal_surname nvarchar(80) NOT NULL
            CONSTRAINT DF_people_paternal_surname DEFAULT (N'') WITH VALUES;

    IF COL_LENGTH(N'dbo.people', N'maternal_surname') IS NULL
        ALTER TABLE dbo.people ADD maternal_surname nvarchar(80) NOT NULL
            CONSTRAINT DF_people_maternal_surname DEFAULT (N'') WITH VALUES;

    IF COL_LENGTH(N'dbo.people', N'municipality') IS NULL
        ALTER TABLE dbo.people ADD municipality nvarchar(120) NOT NULL
            CONSTRAINT DF_people_municipality DEFAULT (N'') WITH VALUES;

    IF COL_LENGTH(N'dbo.people', N'support_type_id') IS NULL
        ALTER TABLE dbo.people ADD support_type_id int NULL;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.foreign_keys
        WHERE parent_object_id = OBJECT_ID(N'dbo.people')
          AND name = N'FK_people_support_types'
    )
    BEGIN
        ALTER TABLE dbo.people WITH CHECK
            ADD CONSTRAINT FK_people_support_types
            FOREIGN KEY (support_type_id) REFERENCES dbo.support_types(id)
            ON UPDATE NO ACTION ON DELETE NO ACTION;
        ALTER TABLE dbo.people CHECK CONSTRAINT FK_people_support_types;
    END;

    IF NOT EXISTS
    (
        SELECT 1
        FROM sys.indexes
        WHERE object_id = OBJECT_ID(N'dbo.people')
          AND name = N'IX_people_support_type_id'
    )
        CREATE INDEX IX_people_support_type_id ON dbo.people(support_type_id);

    COMMIT TRANSACTION;
    PRINT N'MIGRACION TERMINADA CORRECTAMENTE.';
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO
