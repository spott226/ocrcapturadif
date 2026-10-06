[CmdletBinding()]
param(
    [string]$DestinoApp = 'C:\inetpub\CapturaApoyosDIF',
    [string]$NombrePool = 'CapturaApoyosDIF',
    [string]$UrlVerificacion = '',
    [switch]$ConfirmarCodigoFusionado,
    [switch]$AceptarBaseDistinta
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$RaizPaquete = Split-Path -Parent $MyInvocation.MyCommand.Path
$Payload = Join-Path $RaizPaquete 'payload'
$NombresProtegidos = @('.env', '.venv', 'data', 'logs', 'backups', 'web.config')
$BackupActual = $null
$CodigoReemplazado = $false
$EstadoInicial = $null
$Bloqueo = $null
$HuellaWebConfigAntes = $null
$EnvAntes = $null

function Ruta-Completa([string]$Ruta) {
    return [IO.Path]::GetFullPath($Ruta).TrimEnd('\')
}

function Confirmar-RaizAplicacion([string]$Ruta) {
    if (-not (Test-Path -LiteralPath $Ruta -PathType Container)) {
        throw "No existe la carpeta de la aplicación: $Ruta"
    }
    $RaizUnidad = [IO.Path]::GetPathRoot($Ruta).TrimEnd('\')
    if ($Ruta.TrimEnd('\') -eq $RaizUnidad) {
        throw 'Por seguridad no se permite usar la raíz de una unidad como destino.'
    }
    foreach ($Requerido in @('.env', '.venv\Scripts\python.exe', 'web.config', 'app\main.py')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Ruta $Requerido))) {
            throw "La ruta no parece ser la aplicación instalada; falta $Requerido"
        }
    }
}

function Confirmar-Administrador {
    $Principal = New-Object Security.Principal.WindowsPrincipal(
        [Security.Principal.WindowsIdentity]::GetCurrent()
    )
    if (-not $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Abra Windows PowerShell como administrador.'
    }
    if (-not [Environment]::Is64BitProcess) {
        throw 'Use Windows PowerShell de 64 bits.'
    }
}

function Es-Prohibido([string]$Nombre) {
    foreach ($Protegido in $NombresProtegidos) {
        if ($Nombre.Equals($Protegido, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

function Confirmar-Payload([string]$Ruta) {
    if (-not (Test-Path -LiteralPath $Ruta -PathType Container)) {
        throw 'Falta la carpeta payload. Construya el paquete en desarrollo antes de copiarlo al servidor.'
    }
    foreach ($Requerido in @('app\main.py', 'requirements.txt', 'run_iis.py', 'tools\verificar_servidor.py')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Ruta $Requerido) -PathType Leaf)) {
            throw "El payload está incompleto; falta $Requerido"
        }
    }
    foreach ($Item in Get-ChildItem -LiteralPath $Ruta -Force) {
        if (Es-Prohibido $Item.Name) {
            throw "El payload contiene un elemento protegido y no se publicará: $($Item.Name)"
        }
    }
    foreach ($Item in Get-ChildItem -LiteralPath $Ruta -Recurse -Force) {
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "El payload contiene un enlace/reparse point no permitido: $($Item.FullName)"
        }
        if (-not $Item.PSIsContainer) {
            $Nombre = $Item.Name.ToLowerInvariant()
            $Extension = $Item.Extension.ToLowerInvariant()
            if ($Nombre -eq '.env' -or $Nombre.StartsWith('.env.')) {
                throw "El payload contiene un archivo de entorno no permitido: $($Item.FullName)"
            }
            if ($Nombre -match '(secret|secreto|credential|credencial|password|contrasena)') {
                throw "El payload parece contener un archivo secreto: $($Item.FullName)"
            }
            if (@('.sqlite', '.sqlite3', '.db', '.bak', '.mdf', '.ndf', '.ldf',
                  '.xlsx', '.xls', '.csv', '.pem', '.pfx', '.p12', '.key') -contains $Extension) {
                throw "El payload contiene datos, exportaciones o material secreto no permitido: $($Item.FullName)"
            }
            if (@('.jpg', '.jpeg', '.png', '.gif', '.webp', '.tif', '.tiff', '.bmp', '.heic') -contains $Extension) {
                $Estaticos = (Ruta-Completa (Join-Path $Ruta 'app\static')) + '\'
                $ArchivoCompleto = Ruta-Completa $Item.FullName
                if (-not $ArchivoCompleto.StartsWith($Estaticos, [StringComparison]::OrdinalIgnoreCase)) {
                    throw "El payload contiene una imagen fuera de app\static: $($Item.FullName)"
                }
            }
        }
    }
}

function Obtener-HuellaApp([string]$RaizApp) {
    $App = Join-Path $RaizApp 'app'
    $Lineas = New-Object Collections.Generic.List[string]
    $ExtensionesExcluidas = @(
        '.sqlite', '.sqlite3', '.db', '.bak', '.mdf', '.ndf', '.ldf',
        '.xlsx', '.xls', '.csv', '.jpg', '.jpeg', '.png', '.gif', '.webp',
        '.tif', '.tiff', '.bmp', '.heic', '.pdf', '.zip', '.7z', '.pyc'
    )
    $Archivos = Get-ChildItem -LiteralPath $App -Recurse -Force -File |
        Where-Object {
            $_.FullName -notmatch '[\\/](__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache)[\\/]' -and
            -not ($ExtensionesExcluidas -contains $_.Extension.ToLowerInvariant())
        } |
        Sort-Object FullName
    foreach ($Archivo in $Archivos) {
        $RelativaApp = $Archivo.FullName.Substring($App.Length).TrimStart('\').Replace('\', '/')
        $Relativa = 'app/' + $RelativaApp
        $Hash = (Get-FileHash -LiteralPath $Archivo.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        $Lineas.Add(('{0}|{1}|{2}' -f $Relativa, $Hash, $Archivo.Length))
    }
    if ($Lineas.Count -eq 0) { throw 'No fue posible calcular la huella del código app.' }
    $Texto = [string]::Join("`n", $Lineas.ToArray())
    $Sha = [Security.Cryptography.SHA256]::Create()
    try {
        $Bytes = [Text.Encoding]::UTF8.GetBytes($Texto)
        return ([BitConverter]::ToString($Sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally { $Sha.Dispose() }
}

function Obtener-ItemsCodigo([string]$Raiz) {
    return @(Get-ChildItem -LiteralPath $Raiz -Force | Where-Object { -not (Es-Prohibido $_.Name) })
}

function Confirmar-Hijo([string]$Ruta, [string]$Raiz) {
    $Completa = Ruta-Completa $Ruta
    $Prefijo = (Ruta-Completa $Raiz) + '\'
    if (-not $Completa.StartsWith($Prefijo, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Ruta fuera del destino autorizado: $Completa"
    }
}

function Copiar-Codigo([string]$Origen, [string]$Destino) {
    foreach ($Item in Get-ChildItem -LiteralPath $Origen -Force) {
        if (Es-Prohibido $Item.Name) {
            throw "Se intentó copiar un elemento protegido: $($Item.Name)"
        }
        Copy-Item -LiteralPath $Item.FullName -Destination (Join-Path $Destino $Item.Name) -Recurse -Force
    }
}

function Limpiar-Codigo([string]$Raiz) {
    foreach ($Item in Obtener-ItemsCodigo $Raiz) {
        Confirmar-Hijo $Item.FullName $Raiz
        Remove-Item -LiteralPath $Item.FullName -Recurse -Force
    }
}

function Esperar-Pool([string]$Nombre, [string]$EstadoEsperado, [int]$Segundos = 90) {
    $Limite = (Get-Date).AddSeconds($Segundos)
    do {
        $Estado = (Get-WebAppPoolState -Name $Nombre).Value
        if ($Estado -eq $EstadoEsperado) { return }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $Limite)
    throw "El pool $Nombre no alcanzó el estado $EstadoEsperado. Estado actual: $Estado"
}

function Detener-PoolSiNecesario([string]$Nombre) {
    $Estado = (Get-WebAppPoolState -Name $Nombre).Value
    if ($Estado -ne 'Stopped') {
        Stop-WebAppPool -Name $Nombre
        Esperar-Pool $Nombre 'Stopped'
    }
}

function Iniciar-Pool([string]$Nombre) {
    $Estado = (Get-WebAppPoolState -Name $Nombre).Value
    if ($Estado -ne 'Started') {
        Start-WebAppPool -Name $Nombre
        Esperar-Pool $Nombre 'Started'
    }
}

function Instalar-Requisitos([string]$Python, [string]$Archivo, [string]$RaizPaqueteLocal) {
    $Argumentos = @('-m', 'pip', 'install', '--disable-pip-version-check', '-r', $Archivo)
    $Wheelhouse = Join-Path $RaizPaqueteLocal 'wheelhouse'
    if ((Test-Path -LiteralPath $Wheelhouse -PathType Container) -and
        @(Get-ChildItem -LiteralPath $Wheelhouse -Filter '*.whl' -File).Count -gt 0) {
        $Argumentos += @('--no-index', '--find-links', $Wheelhouse)
        Write-Host 'Instalando dependencias desde wheelhouse local...' -ForegroundColor Cyan
    }
    else {
        Write-Host 'Validando/instalando dependencias con pip...' -ForegroundColor Cyan
    }
    & $Python @Argumentos
    if ($LASTEXITCODE -ne 0) { throw 'pip no pudo instalar las dependencias.' }
}

function Verificar-Codigo([string]$Raiz, [string]$ScriptVerificacion) {
    $Python = Join-Path $Raiz '.venv\Scripts\python.exe'
    & $Python -m compileall -q (Join-Path $Raiz 'app') (Join-Path $Raiz 'tools') (Join-Path $Raiz 'run_iis.py')
    if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación de Python.' }

    $Anterior = [Environment]::GetEnvironmentVariable('CAPTURA_APOYOS_ROOT', 'Process')
    try {
        [Environment]::SetEnvironmentVariable('CAPTURA_APOYOS_ROOT', $Raiz, 'Process')
        & $Python $ScriptVerificacion
        if ($LASTEXITCODE -ne 0) { throw 'Falló la verificación de aplicación o esquema SQL.' }
    }
    finally {
        [Environment]::SetEnvironmentVariable('CAPTURA_APOYOS_ROOT', $Anterior, 'Process')
    }
}

function Restaurar-DesdeRespaldo([string]$Raiz, [string]$Respaldo, [string]$Pool, [bool]$IniciarDespues) {
    Write-Warning "Restaurando código desde $Respaldo"
    Detener-PoolSiNecesario $Pool
    Limpiar-Codigo $Raiz
    Copiar-Codigo (Join-Path $Respaldo 'codigo') $Raiz

    $Python = Join-Path $Raiz '.venv\Scripts\python.exe'
    $Freeze = Join-Path $Respaldo 'requirements.freeze.txt'
    if (Test-Path -LiteralPath $Freeze -PathType Leaf) {
        & $Python -m pip install --disable-pip-version-check -r $Freeze
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'El código fue restaurado, pero pip no pudo restaurar completamente el entorno.'
        }
    }
    if ($IniciarDespues) { Iniciar-Pool $Pool }
}

try {
    if (-not $ConfirmarCodigoFusionado) {
        throw 'Actualización cancelada: use -ConfirmarCodigoFusionado únicamente después de fusionar la versión del servidor.'
    }
    Confirmar-Administrador
    $Destino = Ruta-Completa $DestinoApp
    Confirmar-RaizAplicacion $Destino
    Confirmar-Payload $Payload

    $RaizPaqueteCompleta = Ruta-Completa $RaizPaquete
    if ($RaizPaqueteCompleta.StartsWith(($Destino + '\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Copie el paquete fuera de la carpeta de producción antes de ejecutarlo.'
    }

    Import-Module WebAdministration -ErrorAction Stop
    if (-not (Test-Path -LiteralPath ('IIS:\AppPools\' + $NombrePool))) {
        throw "No existe el pool IIS $NombrePool. No se modificó IIS."
    }

    $HuellaActual = Obtener-HuellaApp $Destino
    $ArchivoHuella = Join-Path $RaizPaquete 'VERSION_BASE_SERVIDOR.sha256'
    $HuellaEsperada = if (Test-Path -LiteralPath $ArchivoHuella -PathType Leaf) {
        (Get-Content -LiteralPath $ArchivoHuella -Raw).Trim().ToLowerInvariant()
    } else { '' }
    $HuellaValida = $HuellaEsperada -match '^[0-9a-f]{64}$'
    if (-not $HuellaValida -and -not $AceptarBaseDistinta) {
        throw 'Falta una VERSION_BASE_SERVIDOR.sha256 válida. Recopile y fusione el código; para una excepción revisada use -AceptarBaseDistinta.'
    }
    if ($HuellaValida -and $HuellaEsperada -ne $HuellaActual -and -not $AceptarBaseDistinta) {
        throw "El código instalado cambió después de recopilarlo. Esperado=$HuellaEsperada Actual=$HuellaActual. No se reemplazó nada."
    }
    if (-not $HuellaValida -or $HuellaEsperada -ne $HuellaActual) {
        Write-Warning 'Sistemas aceptó explícitamente una base distinta; el respaldo seguirá siendo obligatorio.'
    }

    $Marca = Join-Path $Destino '.VERSION_SERVIDOR_NO_FUSIONADA'
    if ((Test-Path -LiteralPath $Marca) -and -not $AceptarBaseDistinta) {
        throw 'Existe .VERSION_SERVIDOR_NO_FUSIONADA. Fusione la versión o use la excepción revisada -AceptarBaseDistinta.'
    }

    $CarpetaBackups = Join-Path $Destino 'backups\actualizaciones'
    New-Item -ItemType Directory -Path $CarpetaBackups -Force | Out-Null
    $Bloqueo = Join-Path $CarpetaBackups '.actualizando.lock'
    if (Test-Path -LiteralPath $Bloqueo) {
        throw 'Ya existe un bloqueo de actualización. Confirme que no haya otro proceso antes de retirarlo.'
    }
    New-Item -ItemType File -Path $Bloqueo -Force | Out-Null

    $EstadoInicial = (Get-WebAppPoolState -Name $NombrePool).Value
    $DebeIniciar = $EstadoInicial -eq 'Started'
    $HuellaWebConfigAntes = (Get-FileHash -LiteralPath (Join-Path $Destino 'web.config') -Algorithm SHA256).Hash
    $ArchivoEnv = Get-Item -LiteralPath (Join-Path $Destino '.env')
    $EnvAntes = '{0}|{1}' -f $ArchivoEnv.Length, $ArchivoEnv.LastWriteTimeUtc.Ticks

    $Sello = Get-Date -Format 'yyyyMMdd-HHmmss'
    $BackupActual = Join-Path $CarpetaBackups $Sello
    $CodigoBackup = Join-Path $BackupActual 'codigo'
    New-Item -ItemType Directory -Path $CodigoBackup -Force | Out-Null
    foreach ($Item in Obtener-ItemsCodigo $Destino) {
        if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "No se respaldará un enlace/reparse point: $($Item.FullName)"
        }
        Copy-Item -LiteralPath $Item.FullName -Destination (Join-Path $CodigoBackup $Item.Name) -Recurse -Force
    }

    $Python = Join-Path $Destino '.venv\Scripts\python.exe'
    $PaquetesInstalados = @(& $Python -m pip freeze)
    if ($LASTEXITCODE -ne 0) { throw 'No fue posible inventariar las dependencias antes de actualizar.' }
    $Utf8SinBom = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllLines(
        (Join-Path $BackupActual 'requirements.freeze.txt'),
        [string[]]$PaquetesInstalados,
        $Utf8SinBom
    )
    $Info = [ordered]@{
        fecha_utc = [DateTime]::UtcNow.ToString('o')
        servidor = $env:COMPUTERNAME
        destino = $Destino
        pool = $NombrePool
        estado_pool_antes = $EstadoInicial
        huella_app_antes = $HuellaActual
        web_config_preservado = $true
        env_preservado_sin_leer = $true
    }
    [IO.File]::WriteAllText(
        (Join-Path $BackupActual 'MANIFIESTO_RESPALDO.json'),
        (($Info | ConvertTo-Json) + "`r`n"),
        $Utf8SinBom
    )
    Write-Host "Respaldo creado: $BackupActual" -ForegroundColor Green

    Detener-PoolSiNecesario $NombrePool
    $CodigoReemplazado = $true
    Limpiar-Codigo $Destino
    Copiar-Codigo $Payload $Destino

    $HuellaWebConfigDespues = (Get-FileHash -LiteralPath (Join-Path $Destino 'web.config') -Algorithm SHA256).Hash
    if ($HuellaWebConfigDespues -ne $HuellaWebConfigAntes) {
        throw 'web.config cambió inesperadamente; se activará la restauración.'
    }
    $ArchivoEnvDespues = Get-Item -LiteralPath (Join-Path $Destino '.env')
    $EnvDespues = '{0}|{1}' -f $ArchivoEnvDespues.Length, $ArchivoEnvDespues.LastWriteTimeUtc.Ticks
    if ($EnvDespues -ne $EnvAntes) {
        throw '.env cambió inesperadamente; se activará la restauración.'
    }

    Instalar-Requisitos $Python (Join-Path $Destino 'requirements.txt') $RaizPaquete
    Verificar-Codigo $Destino (Join-Path $RaizPaquete 'VERIFICAR_ACTUALIZACION.py')

    if ($DebeIniciar) {
        Iniciar-Pool $NombrePool
    }
    else {
        Write-Warning 'El pool estaba detenido antes de actualizar y se dejó detenido.'
    }

    if ($UrlVerificacion) {
        if (-not $DebeIniciar) { throw 'No puede verificarse la URL porque el pool estaba detenido.' }
        $Correcta = $false
        for ($Intento = 1; $Intento -le 3; $Intento++) {
            try {
                $Respuesta = Invoke-WebRequest -Uri $UrlVerificacion -UseBasicParsing -TimeoutSec 45
                if ($Respuesta.StatusCode -ge 200 -and $Respuesta.StatusCode -lt 400) {
                    $Correcta = $true
                    break
                }
            }
            catch {
                if ($Intento -lt 3) { Start-Sleep -Seconds 5 }
            }
        }
        if (-not $Correcta) { throw 'La URL de verificación no respondió correctamente.' }
    }

    Write-Host 'ACTUALIZACIÓN IIS TERMINADA CORRECTAMENTE.' -ForegroundColor Green
    Write-Host "Respaldo para reversión: $BackupActual"
    Write-Host 'No se modificaron .env, .venv, data, logs, backups, web.config, bindings ni certificado.'
}
catch {
    $ErrorPrincipal = $_
    Write-Warning ("Falló la actualización: " + $ErrorPrincipal.Exception.Message)
    if ($CodigoReemplazado -and $BackupActual -and (Test-Path -LiteralPath (Join-Path $BackupActual 'codigo'))) {
        try {
            Restaurar-DesdeRespaldo $Destino $BackupActual $NombrePool ($EstadoInicial -eq 'Started')
            Write-Warning 'El código anterior fue restaurado automáticamente.'
        }
        catch {
            Write-Warning ("También falló la restauración automática: " + $_.Exception.Message)
        }
    }
    throw $ErrorPrincipal
}
finally {
    if ($Bloqueo -and (Test-Path -LiteralPath $Bloqueo)) {
        Remove-Item -LiteralPath $Bloqueo -Force -ErrorAction SilentlyContinue
    }
}
