[CmdletBinding()]
param(
    [string]$RaizApp = 'C:\inetpub\CapturaApoyosDIF',
    [string]$DirectorioSalida = 'C:\Users\Public\Documents'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Ruta-Completa([string]$Ruta) {
    return [IO.Path]::GetFullPath($Ruta).TrimEnd('\')
}

function Es-ArchivoPermitido([IO.FileInfo]$Archivo, [string]$Raiz) {
    $Relativa = $Archivo.FullName.Substring($Raiz.Length).TrimStart('\')
    $Partes = $Relativa -split '[\\/]'
    $DirectoriosExcluidos = @(
        '.git', '.venv', 'data', 'logs', 'backups', '__pycache__', '.pytest_cache',
        '.mypy_cache', '.ruff_cache', 'exports', 'exportaciones', 'uploads',
        'imagenes', 'images', 'temp', 'tmp'
    )
    foreach ($Parte in $Partes) {
        if ($DirectoriosExcluidos -contains $Parte.ToLowerInvariant()) { return $false }
    }

    $Nombre = $Archivo.Name.ToLowerInvariant()
    if ($Nombre -eq '.env' -or $Nombre.StartsWith('.env.')) { return $false }
    if ($Nombre -match '(secret|secreto|credential|credencial|password|contrasena|contraseña)') {
        return $false
    }
    if ($Nombre -eq 'web.config') { return $false }

    $ExtensionesExcluidas = @(
        '.sqlite', '.sqlite3', '.db', '.bak', '.mdf', '.ndf', '.ldf',
        '.xlsx', '.xls', '.csv', '.jpg', '.jpeg', '.png', '.gif', '.webp',
        '.tif', '.tiff', '.bmp', '.heic', '.pdf', '.zip', '.7z',
        '.pem', '.pfx', '.p12', '.key', '.cer'
    )
    if ($ExtensionesExcluidas -contains $Archivo.Extension.ToLowerInvariant()) { return $false }
    return $true
}

$Raiz = Ruta-Completa $RaizApp
if (-not (Test-Path -LiteralPath $Raiz -PathType Container)) {
    throw "No existe la aplicación: $Raiz"
}
if (-not (Test-Path -LiteralPath (Join-Path $Raiz 'app\main.py') -PathType Leaf)) {
    throw 'La ruta no parece ser CapturaApoyosDIF: falta app\main.py.'
}
if (-not (Test-Path -LiteralPath $DirectorioSalida -PathType Container)) {
    New-Item -ItemType Directory -Path $DirectorioSalida -Force | Out-Null
}

$MarcaTiempo = Get-Date -Format 'yyyyMMdd-HHmmss'
$NombreBase = "CapturaApoyosDIF_VERSION_ACTUAL_$MarcaTiempo"
$Temporal = Join-Path ([IO.Path]::GetTempPath()) ($NombreBase + '_' + [Guid]::NewGuid().ToString('N'))
$Contenido = Join-Path $Temporal 'VERSION_ACTUAL'
$Codigo = Join-Path $Contenido 'codigo'
$Zip = Join-Path (Ruta-Completa $DirectorioSalida) ($NombreBase + '.zip')
$Utf8SinBom = New-Object Text.UTF8Encoding($false)

try {
    New-Item -ItemType Directory -Path $Codigo -Force | Out-Null

    $Manifiesto = New-Object Collections.Generic.List[string]
    $ManifiestoApp = New-Object Collections.Generic.List[string]
    $Archivos = Get-ChildItem -LiteralPath $Raiz -Recurse -Force -File |
        Sort-Object FullName

    foreach ($Archivo in $Archivos) {
        if (-not (Es-ArchivoPermitido $Archivo $Raiz)) { continue }
        if (($Archivo.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "No se recopilará un enlace o reparse point: $($Archivo.FullName)"
        }

        $Relativa = $Archivo.FullName.Substring($Raiz.Length).TrimStart('\')
        $Destino = Join-Path $Codigo $Relativa
        $CarpetaDestino = Split-Path -Parent $Destino
        if (-not (Test-Path -LiteralPath $CarpetaDestino)) {
            New-Item -ItemType Directory -Path $CarpetaDestino -Force | Out-Null
        }
        Copy-Item -LiteralPath $Archivo.FullName -Destination $Destino -Force

        $Hash = (Get-FileHash -LiteralPath $Archivo.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $Linea = '{0}|{1}|{2}' -f $Relativa.Replace('\', '/'), $Hash, $Archivo.Length
        $Manifiesto.Add($Linea)
        if ($Relativa.StartsWith('app\', [StringComparison]::OrdinalIgnoreCase)) {
            $ManifiestoApp.Add($Linea)
        }
    }

    if ($ManifiestoApp.Count -eq 0) { throw 'No se encontraron archivos fuente dentro de app.' }

    [IO.File]::WriteAllLines((Join-Path $Contenido 'MANIFIESTO_SHA256.txt'), $Manifiesto, $Utf8SinBom)
    $TextoHuella = [string]::Join("`n", $ManifiestoApp.ToArray())
    $Sha = [Security.Cryptography.SHA256]::Create()
    try {
        $Bytes = [Text.Encoding]::UTF8.GetBytes($TextoHuella)
        $HuellaApp = ([BitConverter]::ToString($Sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally { $Sha.Dispose() }
    [IO.File]::WriteAllText((Join-Path $Contenido 'HUELLA_APP_SHA256.txt'), $HuellaApp + "`r`n", $Utf8SinBom)

    $Resumen = @(
        'Copia segura de código para fusión; no es un respaldo de datos.',
        ('Fecha UTC: ' + [DateTime]::UtcNow.ToString('o')),
        ('Servidor: ' + $env:COMPUTERNAME),
        ('Raíz: ' + $Raiz),
        ('Archivos incluidos: ' + $Manifiesto.Count),
        'Excluidos: .env, .venv, datos, logs, respaldos, cachés, imágenes, exportaciones y bases.',
        'web.config no se copia; el actualizador lo preserva en el servidor.'
    )
    [IO.File]::WriteAllLines((Join-Path $Contenido 'RESUMEN.txt'), $Resumen, $Utf8SinBom)
    [IO.File]::WriteAllText(
        (Join-Path $Contenido 'VERSION_SERVIDOR_NO_FUSIONADA.marker'),
        "Fusione y pruebe este código antes de actualizar IIS.`r`n",
        $Utf8SinBom
    )

    if (Test-Path -LiteralPath $Zip) { throw "Ya existe el ZIP de salida: $Zip" }
    Compress-Archive -LiteralPath $Contenido -DestinationPath $Zip -CompressionLevel Optimal
    $HashZip = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText(($Zip + '.sha256.txt'), $HashZip + "  " + [IO.Path]::GetFileName($Zip) + "`r`n", $Utf8SinBom)

    Write-Host 'VERSIÓN ACTUAL RECOPILADA SIN DATOS NI SECRETOS.' -ForegroundColor Green
    Write-Host "ZIP: $Zip"
    Write-Host "SHA256: $HashZip"
    Write-Host 'Entregue este ZIP al desarrollador para fusionar los cambios antes de publicar.'
}
finally {
    if (Test-Path -LiteralPath $Temporal) {
        Remove-Item -LiteralPath $Temporal -Recurse -Force -ErrorAction SilentlyContinue
    }
}
