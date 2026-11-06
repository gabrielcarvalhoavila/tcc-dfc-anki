# Instala o add-on na pasta de add-ons do Anki. Feche o Anki antes, ou reinicie-o depois.
# Uso: .\scripts\install_addon.ps1 [-AnkiDir "$env:APPDATA\Anki2"] [-ColetaEncerrada]
# Guarda do estudo: no Anki de estudo (a pasta padrao) a instalacao e recusada enquanto a coleta pode estar em andamento (ate draw_end),
# porque trocar o add-on no meio da coleta mistura versoes nos eventos (protocolo 6.5 e 6.8). Para testar sem afetar o estudo use
# .\scripts\anki_teste.ps1. Depois que a coleta terminar (alvo de eventos validos ou draw_end) e o CSV final estiver exportado, use -ColetaEncerrada.
param([string]$AnkiDir = "$env:APPDATA\Anki2", [switch]$ColetaEncerrada)
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root "addon\dfc_probe"
$dst = Join-Path $AnkiDir "addons21\dfc_probe"
if (-not (Test-Path (Join-Path $AnkiDir "addons21"))) {
    Write-Error "Pasta de add-ons nao encontrada em $AnkiDir"
    exit 1
}
$studyDir = [IO.Path]::GetFullPath("$env:APPDATA\Anki2").TrimEnd('\')
$target = [IO.Path]::GetFullPath($AnkiDir).TrimEnd('\')
if ($target -ieq $studyDir -and -not $ColetaEncerrada) {
    $cfg = Get-Content (Join-Path $src "config.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    if ((Get-Date).Date -le [datetime]::Parse($cfg.draw_end).Date) {
        Write-Error ("Recusado: este e o Anki de estudo e a coleta pode estar em andamento (janela ate $($cfg.draw_end); o alvo e ~1000 eventos validos). " +
            "Instalar agora trocaria o add-on no meio da coleta. Para testar a versao nova sem afetar o estudo: .\scripts\anki_teste.ps1. " +
            "Se a coleta ja terminou e o CSV final foi exportado, rode de novo com -ColetaEncerrada.")
        exit 3
    }
}
# Sem /PURGE: user_files (banco de eventos) e meta.json do Anki ficam intactos.
robocopy $src $dst /E /XD __pycache__ user_files /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Error "Falha ao copiar (robocopy $LASTEXITCODE)"
    exit 1
}
. (Join-Path $PSScriptRoot "vendor_pipeline.ps1")
Copy-PipelineInto -Root $root -AddonDir $dst
Write-Output "Add-on copiado para $dst"
Write-Output "Reinicie o Anki e confira em Ferramentas > DFC Probe > Status."
exit 0
