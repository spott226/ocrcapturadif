[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Archivo,
    [switch]$Simular
)

$ErrorActionPreference = 'Stop'
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Raiz

if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe')) {
    throw 'No existe .venv. Ejecute primero INSTALAR_IIS.ps1.'
}
if (-not (Test-Path -LiteralPath $Archivo -PathType Leaf)) {
    throw "No se encontró el Excel: $Archivo"
}

$Argumentos = @('tools\importar_excel.py', $Archivo)
if ($Simular) { $Argumentos += '--simular' }
& '.\.venv\Scripts\python.exe' @Argumentos
if ($LASTEXITCODE -ne 0) { throw 'La importación no terminó correctamente.' }
