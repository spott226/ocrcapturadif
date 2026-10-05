[CmdletBinding()]
param(
    [ValidateSet('SqlServer', 'SQLite')]
    [string]$BaseDatos = 'SqlServer',
    [string]$ServidorSql = '',
    [string]$NombreBase = 'CapturaApoyosDIF',
    [ValidateSet('Windows', 'Sql')]
    [string]$AutenticacionSql = 'Windows',
    [switch]$ConfiarCertificadoSql,
    [string]$NombreSitio = 'Captura Apoyos DIF',
    [string]$NombrePool = 'CapturaApoyosDIF',
    [int]$PuertoPrueba = 8095,
    [switch]$NoConfigurarIIS
)

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Raiz

function Convertir-SeguroAPlano([Security.SecureString]$Valor) {
    $Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Valor)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr) }
}

function Valor-Env([string]$Valor) {
    if ($Valor -match "[`r`n]") { throw 'Los valores de configuración no pueden contener saltos de línea.' }
    return '"' + $Valor.Replace('\', '\\').Replace('"', '\"') + '"'
}

function Nueva-ClaveSecreta {
    $Bytes = New-Object byte[] 48
    $Rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $Rng.GetBytes($Bytes) } finally { $Rng.Dispose() }
    return [Convert]::ToBase64String($Bytes)
}

Write-Host '1/5 Creando el entorno privado de Python...' -ForegroundColor Cyan
$Py = Get-Command py.exe -ErrorAction SilentlyContinue
if (-not $Py) { throw 'Instale Python 3.11 o 3.12 x64 desde python.org y vuelva a ejecutar este instalador.' }

if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    & $Py.Source -3.12 -m venv '.venv'
    if ($LASTEXITCODE -ne 0) {
        & $Py.Source -3.11 -m venv '.venv'
    }
    if ($LASTEXITCODE -ne 0) { throw 'No fue posible crear .venv con Python 3.12 ni 3.11.' }
}

& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'No se pudo actualizar pip.' }
& '.\.venv\Scripts\python.exe' -m pip install -r 'requirements.txt'
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias. Revise Internet/proxy del servidor.' }

foreach ($Carpeta in @('data', 'logs', 'backups')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Raiz $Carpeta) | Out-Null
}

Write-Host '2/5 Preparando configuración segura...' -ForegroundColor Cyan
$CorreoAdmin = Read-Host 'Correo institucional para iniciar sesión'
if ($CorreoAdmin -notmatch '^[^@\s]+@[^@\s]+$') { throw 'El correo administrativo no tiene un formato válido.' }
$ContrasenaAdmin = Convertir-SeguroAPlano (Read-Host 'Contraseña inicial (mínimo 12 caracteres)' -AsSecureString)
if ($ContrasenaAdmin.Length -lt 12) { throw 'La contraseña administrativa debe tener al menos 12 caracteres.' }

$Lineas = [Collections.Generic.List[string]]::new()
if ($BaseDatos -eq 'SqlServer') {
    if (-not $ServidorSql) { $ServidorSql = Read-Host 'Servidor SQL (ejemplo SERVIDOR o SERVIDOR\INSTANCIA)' }
    if (-not $ServidorSql) { throw 'Debe indicar el servidor SQL.' }
    $Lineas.Add('DATABASE_BACKEND=sqlserver')
    $Lineas.Add('SQLSERVER_SERVER=' + (Valor-Env $ServidorSql))
    $Lineas.Add('SQLSERVER_DATABASE=' + (Valor-Env $NombreBase))
    $Lineas.Add('SQLSERVER_AUTH=' + $AutenticacionSql.ToLowerInvariant())
    if ($AutenticacionSql -eq 'Sql') {
        $UsuarioSql = Read-Host 'Usuario SQL de la aplicación'
        $ContrasenaSql = Convertir-SeguroAPlano (Read-Host 'Contraseña SQL de la aplicación' -AsSecureString)
        if (-not $UsuarioSql -or -not $ContrasenaSql) { throw 'Faltan las credenciales SQL.' }
        $Lineas.Add('SQLSERVER_USERNAME=' + (Valor-Env $UsuarioSql))
        $Lineas.Add('SQLSERVER_PASSWORD=' + (Valor-Env $ContrasenaSql))
    }
    else {
        $Lineas.Add('SQLSERVER_USERNAME=')
        $Lineas.Add('SQLSERVER_PASSWORD=')
    }
    $Lineas.Add('SQLSERVER_DRIVER="ODBC Driver 18 for SQL Server"')
    $Lineas.Add('SQLSERVER_ENCRYPT=true')
    $Lineas.Add('SQLSERVER_TRUST_CERTIFICATE=' + $ConfiarCertificadoSql.IsPresent.ToString().ToLowerInvariant())
}
else {
    $Lineas.Add('DATABASE_BACKEND=url')
    $Lineas.Add('DATABASE_URL=sqlite:///./data/captura_apoyos.sqlite3')
    $Lineas.Add('ALLOW_SQLITE_IN_IIS=true')
    Write-Warning 'SQLite queda habilitado solo para prueba temporal; no es la opción recomendada para varias capturistas.'
}

$Lineas.Add('SECRET_KEY=' + (Valor-Env (Nueva-ClaveSecreta)))
$Lineas.Add('ADMIN_EMAIL=' + (Valor-Env $CorreoAdmin))
$Lineas.Add('ADMIN_PASSWORD=' + (Valor-Env $ContrasenaAdmin))
$Lineas.Add('COOKIE_SECURE=true')
$Lineas.Add('FORCE_HTTPS=false')
$Lineas.Add('MAX_UPLOAD_MB=8')
$Utf8SinBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllLines((Join-Path $Raiz '.env'), $Lineas, $Utf8SinBom)

Write-Host '3/5 Comprobando el controlador de SQL Server...' -ForegroundColor Cyan
if ($BaseDatos -eq 'SqlServer') {
    $Controladores = & '.\.venv\Scripts\python.exe' -c "import pyodbc; print('|'.join(pyodbc.drivers()))"
    if ($Controladores -notmatch 'ODBC Driver 18 for SQL Server') {
        throw 'Falta Microsoft ODBC Driver 18 for SQL Server x64. Instálelo y ejecute de nuevo.'
    }
}

if ($NoConfigurarIIS) {
    Write-Host '4/5 IIS omitido por solicitud.' -ForegroundColor Yellow
}
else {
    Write-Host '4/5 Configurando IIS...' -ForegroundColor Cyan
    $EsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    if (-not $EsAdmin) { throw 'Abra PowerShell como administrador para configurar IIS.' }
    Import-Module WebAdministration -ErrorAction Stop
    if (-not (Get-WebGlobalModule | Where-Object Name -eq 'httpPlatformHandler')) {
        throw 'IIS no tiene HttpPlatformHandler. Instale el módulo x64 y ejecute de nuevo.'
    }
    if (-not (Test-Path -LiteralPath ('IIS:\AppPools\' + $NombrePool))) {
        New-WebAppPool -Name $NombrePool | Out-Null
    }
    Set-ItemProperty -LiteralPath ('IIS:\AppPools\' + $NombrePool) -Name managedRuntimeVersion -Value ''
    Set-ItemProperty -LiteralPath ('IIS:\AppPools\' + $NombrePool) -Name startMode -Value 'AlwaysRunning'
    Set-ItemProperty -LiteralPath ('IIS:\AppPools\' + $NombrePool) -Name processModel.loadUserProfile -Value $true

    $Sitio = Get-Website -Name $NombreSitio -ErrorAction SilentlyContinue
    if ($Sitio) {
        throw "Ya existe un sitio llamado '$NombreSitio'. Sistemas debe revisarlo para evitar sobrescribirlo."
    }
    New-Website -Name $NombreSitio -PhysicalPath $Raiz -Port $PuertoPrueba -ApplicationPool $NombrePool | Out-Null

    $Identidad = 'IIS AppPool\' + $NombrePool
    & icacls.exe $Raiz /grant ($Identidad + ':(OI)(CI)(RX)') /T | Out-Null
    foreach ($Carpeta in @('data', 'logs', 'backups')) {
        & icacls.exe (Join-Path $Raiz $Carpeta) /grant ($Identidad + ':(OI)(CI)(M)') /T | Out-Null
    }
    Start-Website -Name $NombreSitio
}

Write-Host '5/5 Preparación terminada.' -ForegroundColor Green
Write-Host 'Siguiente: ejecute VERIFICAR_SERVIDOR.ps1 y configure en IIS el certificado HTTPS institucional.'
if ($BaseDatos -eq 'SqlServer' -and $AutenticacionSql -eq 'Windows') {
    Write-Host "Importante: autorice en SQL Server la identidad del pool '$NombrePool' o una cuenta de servicio de dominio."
}
