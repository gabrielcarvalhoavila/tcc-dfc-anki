# Gera dist\dfc_probe.ankiaddon (para instalar em outro computador: Ferramentas > Complementos > Instalar de arquivo).
# Uso: .\scripts\package_addon.ps1
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "addon\dfc_probe"
$dist = Join-Path $root "dist"
$tmp = Join-Path $env:TEMP "dfc_probe_pkg"
$zip = Join-Path $dist "dfc_probe.zip"
$out = Join-Path $dist "dfc_probe.ankiaddon"
New-Item -ItemType Directory -Force -Path $dist | Out-Null
Remove-Item $zip, $out -ErrorAction SilentlyContinue
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
robocopy $src $tmp /E /XD __pycache__ user_files /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Error "Falha ao copiar (robocopy $LASTEXITCODE)"
    exit 1
}
Compress-Archive -Path "$tmp\*" -DestinationPath $zip
Move-Item $zip $out
Remove-Item $tmp -Recurse -Force
Write-Output "Gerado: $out"
exit 0
