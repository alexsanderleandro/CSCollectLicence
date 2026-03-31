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
$iconPath = "assets\logo.ico"
$iconArg = ''
if (Test-Path $iconPath) {
    $iconArg = "--icon=$iconPath"
} else {
    Write-Host "Aviso: ícone '.\assets\logo.ico' não encontrado. O executável será gerado sem ícone." -ForegroundColor Yellow
}

# Gerar version_build.txt usando Python (menos propenso a problemas de escape)
$pyScript = @'
import re
from pathlib import Path
vp = Path('version.py').read_text(encoding='utf-8')
m = re.search(r"VERSION\s*=\s*'([^']*)'", vp)
ver_full = m.group(1).strip() if m else '0.0.0'
ver_core = ver_full.split()[0]
parts = ver_core.split('.')
while len(parts) < 4:
    parts.append('0')
parts = parts[:4]
filevers = ','.join(str(int(p)) if p.isdigit() else '0' for p in parts)
vt = Path('version.txt').read_text(encoding='utf-8') if Path('version.txt').exists() else ''
if vt:
    vt = re.sub(r'filevers=\([^)]*\)', f'filevers=({filevers})', vt)
    vt = re.sub(r'prodvers=\([^)]*\)', f'prodvers=({filevers})', vt)
    vt = re.sub(r"FileVersion', '.*?'", f"FileVersion', '{ver_full}'", vt)
    vt = re.sub(r"ProductVersion', '.*?'", f"ProductVersion', '{ver_full}'", vt)
    Path('version_build.txt').write_text(vt, encoding='utf-8')
    print('WROTE version_build.txt')
else:
    print('version.txt not found; skipping version embed')
'@

$pyFile = '._gen_version_tmp.py'
Set-Content -Path $pyFile -Value $pyScript -Encoding UTF8
python $pyFile
Remove-Item $pyFile -ErrorAction SilentlyContinue

$versionArg = ''
if (Test-Path 'version_build.txt') { $versionArg = "--version-file=version_build.txt" }

Write-Host "Executando PyInstaller..."
pyinstaller --windowed --onefile --name $appName --add-data $addData --add-data $addEnv $versionArg $iconArg $scriptEntry

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller falhou com código $LASTEXITCODE"
    exit $LASTEXITCODE
}

$distPath = Join-Path -Path (Get-Location) -ChildPath "dist\$appName.exe"
if (Test-Path $distPath) {
    Write-Host "Build concluído com sucesso: $distPath"
    Write-Host "Lembre-se de fornecer MASTER_KEY via variável de ambiente ou arquivo .env antes de executar o exe."
} else {
    Write-Error "Não foi possível encontrar o executável em dist"
}
