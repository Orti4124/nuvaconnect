# build.ps1 — Genera el instalador de Windows de NuvaConnect con un comando.
#
# Requisitos en la máquina Windows:
#   - Python 3.10+ (https://python.org)
#   - Inno Setup 6 (https://jrsoftware.org/isinfo.php)  -> aporta 'iscc'
#
# Uso (PowerShell, desde la raíz del proyecto):
#   .\installer\windows\build.ps1
#
# Resultado: dist_installer\NuvaConnect-Setup.exe

$ErrorActionPreference = "Stop"

# Ir a la raíz del proyecto (dos niveles arriba de este script)
$root = Resolve-Path "$PSScriptRoot\..\.."
Set-Location $root
Write-Host "== Compilando NuvaConnect para Windows ==" -ForegroundColor Cyan
Write-Host "Raíz del proyecto: $root"

# 1) Entorno virtual + dependencias
if (-not (Test-Path ".venv")) {
    Write-Host "-> Creando entorno virtual..."
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller

# 2) Empaquetar los ejecutables con PyInstaller
Write-Host "-> Empaquetando ejecutables con PyInstaller..."
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean installer\windows\nuvaconnect.spec

# 3) Construir el instalador con Inno Setup
Write-Host "-> Construyendo el instalador con Inno Setup..."
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "iscc" }  # si está en el PATH
& $iscc installer\windows\NuvaConnect.iss

Write-Host ""
Write-Host "✔ Listo: dist_installer\NuvaConnect-Setup.exe" -ForegroundColor Green
Write-Host "  (Para producción, firma el .exe con signtool antes de distribuir.)"
