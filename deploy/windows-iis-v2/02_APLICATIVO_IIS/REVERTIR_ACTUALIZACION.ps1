[CmdletBinding()]
param(
    [string]$DestinoApp = 'C:\inetpub\CapturaApoyosDIF',
    [string]$NombrePool = 'CapturaApoyosDIF',
    [string]$Respaldo = '',
    [string]$UrlVerificacion = '',
    [switch]$ConfirmarReversion
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$RaizPaquete = Split-Path -Parent $MyInvocation.MyCommand.Path
$NombresProtegidos = @('.env', '.venv', 'data', 'logs', 'backups', 'web.config')

function Ruta-Completa([string]$Ruta) {
    return [IO.Path]::GetFullPath($Ruta).TrimEnd('\')
}

function Es-Prohibido([string]$Nombre) {
    foreach ($Protegido in $NombresProtegidos) {
        if ($Nombre.Equals($Protegido, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Confirmar-Raiz([string]$Ruta) {
    if (-not (Test-Path -LiteralPath $Ruta -PathType Container)) { throw "No existe $Ruta" }
    $RaizUnidad = [IO.Path]::GetPathRoot($Ruta).TrimEnd('\')
    if ($Ruta.TrimEnd('\') -eq $RaizUnidad) { throw 'No se permite operar sobre la raíz de una unidad.' }
    foreach ($Requerido in @('.env', '.venv\Scripts\python.exe', 'web.config')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Ruta $Requerido))) {
            throw "La ruta no parece ser CapturaApoyosDIF; falta $Requerido"
        }
    }
}

function Confirmar-Hijo([string]$Ruta, [string]$Raiz) {
    $Completa = Ruta-Completa $Ruta
    $Prefijo = (Ruta-Completa $Raiz) + '\'
    if (-not $Completa.StartsWith($Prefijo, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Ruta fuera del destino autorizado: $Completa"
    }
}

function Obtener-ItemsCodigo([string]$Raiz) {
    return @(Get-ChildItem -LiteralPath $Raiz -Force | Where-Object { -not (Es-Prohibido $_.Name) })
}

function Limpiar-Codigo([string]$Raiz) {
    foreach ($Item in Obtener-ItemsCodigo $Raiz) {
        Confirmar-Hijo $Item.FullName $Raiz
        Remove-Item -LiteralPath $Item.FullName -Recurse -Force
    }
}

function Copiar-Codigo([string]$Origen, [string]$Destino) {
    foreach ($Item in Get-ChildItem -LiteralPath $Origen -Force) {
        if (Es-Prohibido $Item.Name) { throw "El respaldo contiene un elemento protegido: $($Item.Name)" }
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "El respaldo contiene un enlace/reparse point: $($Item.FullName)"
        }
        Copy-Item -LiteralPath $Item.FullName -Destination (Join-Path $Destino $Item.Name) -Recurse -Force
    }
}

function Esperar-Pool([string]$Nombre, [string]$Esperado, [int]$Segundos = 90) {
    $Limite = (Get-Date).AddSeconds($Segundos)
    do {
        $Estado = (Get-WebAppPoolState -Name $Nombre).Value
        if ($Estado -eq $Esperado) { return }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $Limite)
    throw "El pool $Nombre no alcanzó $Esperado. Estado: $Estado"
}

function Detener-Pool([string]$Nombre) {
    if ((Get-WebAppPoolState -Name $Nombre).Value -ne 'Stopped') {
        Stop-WebAppPool -Name $Nombre
        Esperar-Pool $Nombre 'Stopped'
    }
}

function Iniciar-Pool([string]$Nombre) {
    if ((Get-WebAppPoolState -Name $Nombre).Value -ne 'Started') {
        Start-WebAppPool -Name $Nombre
        Esperar-Pool $Nombre 'Started'
    }
}

if (-not $ConfirmarReversion) {
    throw 'Reversión cancelada. Revise el respaldo y vuelva a ejecutar con -ConfirmarReversion.'
}

$Principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Abra Windows PowerShell como administrador.'
}

$Destino = Ruta-Completa $DestinoApp
Confirmar-Raiz $Destino
Import-Module WebAdministration -ErrorAction Stop
if (-not (Test-Path -LiteralPath ('IIS:\AppPools\' + $NombrePool))) {
    throw "No existe el pool IIS $NombrePool."
}

$RaizRespaldos = Ruta-Completa (Join-Path $Destino 'backups\actualizaciones')
if (-not (Test-Path -LiteralPath $RaizRespaldos -PathType Container)) {
    throw 'No existe la carpeta de respaldos de actualizaciones.'
}

if (-not $Respaldo) {
    $Candidato = Get-ChildItem -LiteralPath $RaizRespaldos -Directory |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'codigo') -PathType Container } |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
    if (-not $Candidato) { throw 'No se encontró un respaldo válido.' }
    $Respaldo = $Candidato.FullName
}

$RespaldoCompleto = Ruta-Completa $Respaldo
if (-not $RespaldoCompleto.StartsWith(($RaizRespaldos + '\'), [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Por seguridad el respaldo debe estar dentro de backups\actualizaciones.'
}
$CodigoRespaldo = Join-Path $RespaldoCompleto 'codigo'
if (-not (Test-Path -LiteralPath $CodigoRespaldo -PathType Container)) {
    throw 'El respaldo seleccionado no contiene la carpeta codigo.'
}

$EstadoInicial = (Get-WebAppPoolState -Name $NombrePool).Value
$DebeIniciar = $EstadoInicial -eq 'Started'
$WebConfigAntes = (Get-FileHash -LiteralPath (Join-Path $Destino 'web.config') -Algorithm SHA256).Hash
$EnvItem = Get-Item -LiteralPath (Join-Path $Destino '.env')
$EnvAntes = '{0}|{1}' -f $EnvItem.Length, $EnvItem.LastWriteTimeUtc.Ticks

$Emergencia = Join-Path $Destino ('backups\antes_reversion\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$CodigoEmergencia = Join-Path $Emergencia 'codigo'
New-Item -ItemType Directory -Path $CodigoEmergencia -Force | Out-Null
foreach ($Item in Obtener-ItemsCodigo $Destino) {
    if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "No se respaldará un enlace/reparse point: $($Item.FullName)"
    }
    Copy-Item -LiteralPath $Item.FullName -Destination (Join-Path $CodigoEmergencia $Item.Name) -Recurse -Force
}

try {
    Write-Host "Revirtiendo desde: $RespaldoCompleto" -ForegroundColor Cyan
    Write-Host "Copia de emergencia de la versión actual: $Emergencia"
    Detener-Pool $NombrePool
    Limpiar-Codigo $Destino
    Copiar-Codigo $CodigoRespaldo $Destino

    $Python = Join-Path $Destino '.venv\Scripts\python.exe'
    $Freeze = Join-Path $RespaldoCompleto 'requirements.freeze.txt'
    if (Test-Path -LiteralPath $Freeze -PathType Leaf) {
        & $Python -m pip install --disable-pip-version-check -r $Freeze
        if ($LASTEXITCODE -ne 0) { throw 'No fue posible restaurar las dependencias del respaldo.' }
    }

    & $Python -m compileall -q (Join-Path $Destino 'app') (Join-Path $Destino 'tools') (Join-Path $Destino 'run_iis.py')
    if ($LASTEXITCODE -ne 0) { throw 'El código restaurado no compila.' }

    $WebConfigDespues = (Get-FileHash -LiteralPath (Join-Path $Destino 'web.config') -Algorithm SHA256).Hash
    if ($WebConfigDespues -ne $WebConfigAntes) { throw 'web.config cambió inesperadamente.' }
    $EnvItemDespues = Get-Item -LiteralPath (Join-Path $Destino '.env')
    $EnvDespues = '{0}|{1}' -f $EnvItemDespues.Length, $EnvItemDespues.LastWriteTimeUtc.Ticks
    if ($EnvDespues -ne $EnvAntes) { throw '.env cambió inesperadamente.' }

    if ($DebeIniciar) { Iniciar-Pool $NombrePool }
    else { Write-Warning 'El pool estaba detenido y se dejó detenido.' }

    if ($UrlVerificacion) {
        if (-not $DebeIniciar) { throw 'No puede verificarse la URL con el pool detenido.' }
        $Respuesta = Invoke-WebRequest -Uri $UrlVerificacion -UseBasicParsing -TimeoutSec 45
        if ($Respuesta.StatusCode -lt 200 -or $Respuesta.StatusCode -ge 400) {
            throw "La URL devolvió HTTP $($Respuesta.StatusCode)."
        }
    }

    Write-Host 'REVERSIÓN DE CÓDIGO TERMINADA CORRECTAMENTE.' -ForegroundColor Green
    Write-Host 'La base SQL, .env, .venv, web.config, bindings y certificado no fueron modificados.'
}
catch {
    $ErrorReversion = $_
    Write-Warning ("Falló la reversión: " + $ErrorReversion.Exception.Message)
    try {
        Detener-Pool $NombrePool
        Limpiar-Codigo $Destino
        Copiar-Codigo $CodigoEmergencia $Destino
        if ($DebeIniciar) { Iniciar-Pool $NombrePool }
        Write-Warning 'Se recuperó la versión que existía justo antes de intentar la reversión.'
    }
    catch {
        Write-Warning ("También falló la recuperación de emergencia: " + $_.Exception.Message)
    }
    throw $ErrorReversion
}
