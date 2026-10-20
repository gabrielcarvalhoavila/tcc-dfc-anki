# Instala o add-on na pasta de add-ons do Anki. Feche o Anki antes, ou reinicie-o depois.
# Uso: .\scripts\install_addon.ps1 [-AnkiDir "$env:APPDATA\Anki2"]
param([string]$AnkiDir = "$env:APPDATA\Anki2")
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "addon\dfc_probe"
$dst = Join-Path $AnkiDir "addons21\dfc_probe"
if (-not (Test-Path (Join-Path $AnkiDir "addons21"))) {
    Write-Error "Pasta de add-ons nao encontrada em $AnkiDir"
    exit 1
}
# Sem /PURGE: user_files (banco de eventos) e meta.json do Anki ficam intactos.
robocopy $src $dst /E /XD __pycache__ user_files /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Error "Falha ao copiar (robocopy $LASTEXITCODE)"
    exit 1
}
Write-Output "Add-on copiado para $dst"
Write-Output "Reinicie o Anki e confira em Ferramentas > DFC Probe > Status."
exit 0
