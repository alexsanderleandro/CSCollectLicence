# Build script v2: usa um helper Python para gerar o version_build.txt e executa PyInstaller
$ErrorActionPreference = 'Stop'
Write-Host "Iniciando build (v2) do executável..."

if (-not (Test-Path -Path .\venv)) {
    Write-Host "Criando virtualenv 'venv'..."
    python -m venv venv
}

Write-Host "Ativando virtualenv..."
. .\venv\Scripts\Activate.ps1

Write-Host "Instalando dependências (pode levar alguns minutos)..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Parâmetros
$scriptEntry = 'gui_licenca.py'
$appName = 'CSCollectLicence'
$addData = "assets;assets"
$addEnv = ".env;."
Write-Host "Gerando assets (version_build.txt e logo.ico) via tools/gen_build_assets.py"
python tools\gen_build_assets.py

$iconIco = "assets\logo.ico"
$iconArg = ''
if (Test-Path $iconIco) {
    $iconArg = "--icon=$iconIco"
} else {
    Write-Host "Aviso: nenhum ícone .ico encontrado; o executável será gerado sem ícone." -ForegroundColor Yellow
}

$versionArg = ''
if (Test-Path 'version_build.txt') { $versionArg = "--version-file=version_build.txt" }

Write-Host "Executando PyInstaller..."
# --onedir: extração acontece no build (não a cada abertura, como no --onefile),
# eliminando os vários segundos de descompactação + scan do antivírus no startup.
pyinstaller --windowed --onedir --contents-directory _internal --name $appName --add-data $addData --add-data $addEnv $versionArg $iconArg $scriptEntry

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller falhou com código $LASTEXITCODE"
    exit $LASTEXITCODE
}

$distDir = Join-Path -Path (Get-Location) -ChildPath "dist\$appName"
$distPath = Join-Path -Path $distDir -ChildPath "$appName.exe"
if (Test-Path $distPath) {
    Write-Host "Gerando pacote zip para distribuição..."
    $zipPath = Join-Path -Path (Get-Location) -ChildPath "dist\$appName.zip"
    Compress-Archive -Path $distDir -DestinationPath $zipPath -Force
    Write-Host "Build concluído com sucesso:"
    Write-Host "  Pasta do app: $distDir"
    Write-Host "  Executável:   $distPath"
    Write-Host "  Zip p/ envio: $zipPath"
    Write-Host "Lembre-se de fornecer MASTER_KEY via variável de ambiente ou arquivo .env antes de executar o exe."
} else {
    Write-Error "Não foi possível encontrar o executável em dist\$appName"
}
