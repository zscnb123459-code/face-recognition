$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root

Write-Host '== FaceVault portable build ==' -ForegroundColor Cyan
python -m pip install --disable-pip-version-check -r requirements.txt -r requirements-dev.txt
python tools\verify_install.py
python -m pytest -q

python -m PyInstaller --noconfirm --clean --distpath dist_runtime --workpath build_runtime FaceVault.spec
python -m PyInstaller --noconfirm --clean --distpath dist_launcher --workpath build_launcher FaceVaultLauncher.spec

$RuntimeSource = Join-Path $Root 'dist_runtime\FaceVault'
$LauncherExe = Join-Path $Root 'dist_launcher\FaceVaultLauncher.exe'
$ReleaseRoot = Join-Path $Root '发布版'
$Final = Join-Path $ReleaseRoot '人脸识别'
if (-not (Test-Path -LiteralPath $RuntimeSource)) { throw "Runtime output not found: $RuntimeSource" }
if (-not (Test-Path -LiteralPath $LauncherExe)) { throw "Launcher output not found: $LauncherExe" }

$ResolvedRelease = [System.IO.Path]::GetFullPath($ReleaseRoot)
$ResolvedFinal = [System.IO.Path]::GetFullPath($Final)
if (-not $ResolvedFinal.StartsWith($ResolvedRelease, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to modify path outside release directory: $ResolvedFinal"
}
if (Test-Path -LiteralPath $Final) {
    Remove-Item -LiteralPath $ResolvedFinal -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Final | Out-Null
Copy-Item -LiteralPath $RuntimeSource -Destination (Join-Path $Final 'runtime') -Recurse

$RuntimeExe = Join-Path $Final 'runtime\FaceVault.exe'
$Token = (Get-FileHash -LiteralPath $RuntimeExe -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $Final 'runtime\runtime.token') -Value $Token -Encoding ascii
Copy-Item -LiteralPath $LauncherExe -Destination (Join-Path $Final 'FaceVault.exe') -Force
Copy-Item -LiteralPath (Join-Path $Root 'README.md') -Destination (Join-Path $Final 'README.md') -Force

$FinalExe = Join-Path $Final 'FaceVault.exe'
Write-Host ('Portable application: ' + $FinalExe) -ForegroundColor Green
