<#
Script de build para criar um executável único (Windows) usando PyInstaller.
Uso: abra PowerShell na pasta do projeto e rode:
    .\build_exe.ps1

O script cria/usa o virtualenv `venv`, instala dependências e executa PyInstaller.
#>

$ErrorActionPreference = 'Stop'

Write-Host "Iniciando build do executável..."

if (-not (Test-Path -Path .\venv)) {
    Write-Host "Criando virtualenv 'venv'..."
    python -m venv venv
}

Write-Host "Ativando virtualenv..."
. .\venv\Scripts\Activate.ps1

Write-Host "Instalando dependências (pode levar alguns minutos)..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# PyInstaller command
$scriptEntry = 'gui_licenca.py'
$appName = 'CSCollectLicence'

# incluir pasta assets
$addData = "assets;assets"

# ícone opcional
$iconPath = "assets\logo.ico"
$iconArg = ''
if (Test-Path $iconPath) {
    $iconArg = "--icon=$iconPath"
} else {
    Write-Host "Aviso: ícone '.\assets\logo.ico' não encontrado. O executável será gerado sem ícone." -ForegroundColor Yellow
}

Write-Host "Executando PyInstaller..."
pyinstaller --windowed --onefile --name $appName --add-data $addData $iconArg $scriptEntry

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller falhou com código $LASTEXITCODE"
    exit $LASTEXITCODE
}

$distPath = Join-Path -Path (Get-Location) -ChildPath "dist\$appName.exe"
if (Test-Path $distPath) {
    Write-Host "Build concluído com sucesso: $distPath"
    Write-Host "Lembre-se de fornecer MASTER_KEY via variável de ambiente ou arquivo .env antes de executar o exe."
} else {
    Write-Error "Não foi possível encontrar o executável em 'dist\'"
}
