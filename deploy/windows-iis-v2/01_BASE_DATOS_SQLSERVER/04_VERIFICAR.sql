/* Verificación sin mostrar datos personales. */
USE [CapturaApoyosDIF];
GO
SET NOCOUNT ON;

IF OBJECT_ID(N'dbo.people', N'U') IS NULL THROW 51040, N'Falta dbo.people.', 1;
IF OBJECT_ID(N'dbo.support_types', N'U') IS NULL THROW 51041, N'Falta dbo.support_types.', 1;
IF OBJECT_ID(N'dbo.app_users', N'U') IS NULL THROW 51042, N'Falta dbo.app_users.', 1;

IF COL_LENGTH(N'dbo.people', N'given_names') IS NULL THROW 51043, N'Falta people.given_names.', 1;
IF COL_LENGTH(N'dbo.people', N'paternal_surname') IS NULL THROW 51044, N'Falta people.paternal_surname.', 1;
IF COL_LENGTH(N'dbo.people', N'maternal_surname') IS NULL THROW 51045, N'Falta people.maternal_surname.', 1;
IF COL_LENGTH(N'dbo.people', N'municipality') IS NULL THROW 51046, N'Falta people.municipality.', 1;
IF COL_LENGTH(N'dbo.people', N'support_type_id') IS NULL THROW 51047, N'Falta people.support_type_id.', 1;

IF COL_LENGTH(N'dbo.support_types', N'id') IS NULL THROW 51051, N'Falta support_types.id.', 1;
IF COL_LENGTH(N'dbo.support_types', N'code') IS NULL THROW 51052, N'Falta support_types.code.', 1;
IF COL_LENGTH(N'dbo.support_types', N'name') IS NULL THROW 51053, N'Falta support_types.name.', 1;
IF COL_LENGTH(N'dbo.support_types', N'is_active') IS NULL THROW 51054, N'Falta support_types.is_active.', 1;
IF COL_LENGTH(N'dbo.support_types', N'sort_order') IS NULL THROW 51055, N'Falta support_types.sort_order.', 1;

IF COL_LENGTH(N'dbo.app_users', N'id') IS NULL THROW 51056, N'Falta app_users.id.', 1;
IF COL_LENGTH(N'dbo.app_users', N'email') IS NULL THROW 51057, N'Falta app_users.email.', 1;
IF COL_LENGTH(N'dbo.app_users', N'password_hash') IS NULL THROW 51058, N'Falta app_users.password_hash.', 1;
IF COL_LENGTH(N'dbo.app_users', N'role') IS NULL THROW 51059, N'Falta app_users.role.', 1;
IF COL_LENGTH(N'dbo.app_users', N'is_active') IS NULL THROW 51060, N'Falta app_users.is_active.', 1;
IF COL_LENGTH(N'dbo.app_users', N'created_by') IS NULL THROW 51061, N'Falta app_users.created_by.', 1;
IF COL_LENGTH(N'dbo.app_users', N'created_at') IS NULL THROW 51062, N'Falta app_users.created_at.', 1;
IF COL_LENGTH(N'dbo.app_users', N'last_login_at') IS NULL THROW 51063, N'Falta app_users.last_login_at.', 1;

IF NOT EXISTS
(
    SELECT 1 FROM sys.key_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.support_types')
      AND name = N'UQ_support_types_code'
      AND type = N'UQ'
)
    THROW 51064, N'Falta la unicidad de support_types.code.', 1;

IF NOT EXISTS
(
    SELECT 1 FROM sys.key_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.app_users')
      AND name = N'UQ_app_users_email'
      AND type = N'UQ'
)
    THROW 51065, N'Falta la unicidad de app_users.email.', 1;

IF NOT EXISTS
(
    SELECT 1 FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.app_users')
      AND name = N'CK_app_users_role'
      AND is_disabled = 0
      AND is_not_trusted = 0
)
    THROW 51066, N'Falta o no es confiable CK_app_users_role.', 1;

IF NOT EXISTS
(
    SELECT 1 FROM sys.foreign_keys
    WHERE parent_object_id = OBJECT_ID(N'dbo.people')
      AND name = N'FK_people_support_types'
      AND is_disabled = 0
      AND is_not_trusted = 0
      AND delete_referential_action = 0
      AND update_referential_action = 0
)
    THROW 51048, N'Falta o no es confiable FK_people_support_types.', 1;

IF NOT EXISTS
(
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.people')
      AND name = N'IX_people_support_type_id'
)
    THROW 51049, N'Falta IX_people_support_type_id.', 1;

IF EXISTS
(
    SELECT 1
    FROM dbo.people AS p
    LEFT JOIN dbo.support_types AS s ON s.id = p.support_type_id
    WHERE p.support_type_id IS NOT NULL AND s.id IS NULL
)
    THROW 51050, N'Existen tipos de apoyo huérfanos.', 1;

SELECT N'dbo.people' AS Objeto, COUNT_BIG(*) AS Filas FROM dbo.people
UNION ALL
SELECT N'dbo.support_types', COUNT_BIG(*) FROM dbo.support_types
UNION ALL
SELECT N'dbo.app_users', COUNT_BIG(*) FROM dbo.app_users;

PRINT N'VERIFICACION SQL OK.';
GO
