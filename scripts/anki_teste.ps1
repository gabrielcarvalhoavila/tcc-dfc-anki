# Abre (ou verifica) um Anki ISOLADO para testar o add-on sem tocar no seu Anki de estudo.
# O Anki de teste tem pasta propria (padrao: %USERPROFILE%\AnkiTeste), um perfil "Teste" com cartoes INVENTADOS e uma chave de instancia unica
# propria do Anki (ANKI_SINGLE_INSTANCE_KEY): o seu Anki de estudo pode continuar aberto, com o add-on 0.4.0 e os dados dele intocados.
# Uso:
#   .\scripts\anki_teste.ps1                  prepara (se preciso) e abre o Anki de teste
#   .\scripts\anki_teste.ps1 -Auto            roda o roteiro automatico, sem janelas, e mostra o resultado
#   .\scripts\anki_teste.ps1 -Auto -ComLLM    idem, gerando as variantes com a IA de verdade (usa a chave do seu add-on; custa centavos)
#   .\scripts\anki_teste.ps1 -ComChave        copia a chave da IA do seu add-on para o Anki de teste (para testar a geracao a mao)
#   .\scripts\anki_teste.ps1 -Recriar         apaga o perfil de teste e cria de novo
# Requer o .venv do repositorio (python -m venv .venv; .venv\Scripts\python -m pip install anki==26.5).
param(
    [string]$Base = "$env:USERPROFILE\AnkiTeste",
    [switch]$Auto,
    [switch]$ComLLM,
    [switch]$ComChave,
    [switch]$Recriar,
    [string]$AnkiExe = "$env:LOCALAPPDATA\Programs\Anki\Anki.exe"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$study = [IO.Path]::GetFullPath("$env:APPDATA\Anki2").TrimEnd('\')
$base = [IO.Path]::GetFullPath($Base).TrimEnd('\')
if ($base -ieq $study -or $base.StartsWith($study + "\", [StringComparison]::OrdinalIgnoreCase)) {
    Write-Error "Recusado: $base e a pasta do seu Anki de estudo. Use outra pasta para o Anki de teste."
    exit 2
}
if (-not (Test-Path $AnkiExe)) {
    Write-Error "Anki nao encontrado em $AnkiExe (use -AnkiExe com o caminho do Anki.exe)."
    exit 1
}
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Crie o ambiente: python -m venv .venv; .venv\Scripts\python -m pip install anki==26.5"
    exit 1
}
if ($ComLLM) { $ComChave = $true }
if ($Auto) { $Recriar = $true }  # o roteiro responde cartoes: cada execucao parte de uma colecao nova

# 1) pasta-base, perfil e colecao de teste (cartoes inventados)
if ($Recriar) { Remove-Item (Join-Path $base "addons21\dfc_probe\user_files") -Recurse -Force -ErrorAction SilentlyContinue }  # eventos e banco do Anki de TESTE
$makeArgs = @((Join-Path $root "scripts\make_test_collection.py"), $base)
if ($Recriar) { $makeArgs += "--recriar" }
& $python @makeArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 2) add-on em desenvolvimento (so nesta pasta-base; o guarda do install_addon.ps1 protege o Anki de estudo)
& (Join-Path $PSScriptRoot "install_addon.ps1") -AnkiDir $base | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 3) chave da IA (opcional): copia so as chaves live_* da configuracao do seu add-on, sem mostrar nada
$metaPath = Join-Path $base "addons21\dfc_probe\meta.json"
if ($ComChave) {
    $studyMeta = Join-Path $study "addons21\dfc_probe\meta.json"
    if (-not (Test-Path $studyMeta)) {
        Write-Error "Nao achei a configuracao do add-on no Anki de estudo ($studyMeta)."
        exit 1
    }
    $src = (Get-Content $studyMeta -Raw -Encoding UTF8 | ConvertFrom-Json).config
    $cfg = [ordered]@{}
    foreach ($p in $src.PSObject.Properties) { if ($p.Name -like "live_*") { $cfg[$p.Name] = $p.Value } }
    $cfg["live_enabled"] = $true
    if (-not ("$($cfg['live_api_key'])".Trim())) {
        Write-Error "O add-on do Anki de estudo nao tem live_api_key preenchida."
        exit 1
    }
    $meta = if (Test-Path $metaPath) { Get-Content $metaPath -Raw -Encoding UTF8 | ConvertFrom-Json } else { [pscustomobject]@{} }
    $merged = [ordered]@{}
    if ($meta.config) { foreach ($p in $meta.config.PSObject.Properties) { $merged[$p.Name] = $p.Value } }
    foreach ($k in $cfg.Keys) { $merged[$k] = $cfg[$k] }
    $out = [ordered]@{ config = $merged }
    [IO.File]::WriteAllText($metaPath, ($out | ConvertTo-Json -Depth 6), (New-Object Text.UTF8Encoding($false)))
    Write-Output "Chave da IA copiada para o Anki de teste (live_*; nada foi exibido)."
}

# 4) roteiro automatico (so com -Auto)
$selftestDst = Join-Path $base "addons21\dfc_selftest"
$resultDir = Join-Path $base "selftest"
$result = Join-Path $resultDir "resultado.json"
if ($Auto) {
    robocopy (Join-Path $root "scripts\anki_selftest\dfc_selftest") $selftestDst /MIR /XD __pycache__ /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { Write-Error "Falha ao copiar o roteiro (robocopy $LASTEXITCODE)"; exit 1 }
    New-Item -ItemType Directory -Force -Path $resultDir | Out-Null
    Remove-Item $result -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $resultDir "telas") -Recurse -Force -ErrorAction SilentlyContinue
} elseif (Test-Path $selftestDst) {
    Remove-Item $selftestDst -Recurse -Force
}

# 5) abre o Anki de teste com a chave de instancia propria (o de estudo, se aberto, nao e afetado)
$old = @{ key = $env:ANKI_SINGLE_INSTANCE_KEY; qpa = $env:QT_QPA_PLATFORM; out = $env:DFC_SELFTEST_OUT; live = $env:DFC_SELFTEST_LIVE; gl = $env:ANKI_SOFTWAREOPENGL; fonts = $env:QT_QPA_FONTDIR }
$env:ANKI_SINGLE_INSTANCE_KEY = "anki-dfc-teste"
if ($Auto) {
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:QT_QPA_FONTDIR = "$env:WINDIR\Fonts"
    $env:ANKI_SOFTWAREOPENGL = "1"
    $env:DFC_SELFTEST_OUT = $result
    $env:DFC_SELFTEST_LIVE = $(if ($ComLLM) { "1" } else { "0" })
}
try {
    $proc = Start-Process -FilePath $AnkiExe -ArgumentList "-b `"$base`" -p Teste" -PassThru
} finally {
    $env:ANKI_SINGLE_INSTANCE_KEY = $old.key; $env:QT_QPA_PLATFORM = $old.qpa; $env:DFC_SELFTEST_OUT = $old.out; $env:DFC_SELFTEST_LIVE = $old.live; $env:ANKI_SOFTWAREOPENGL = $old.gl; $env:QT_QPA_FONTDIR = $old.fonts
}
if (-not $Auto) {
    Write-Output "Anki de teste aberto (PID $($proc.Id)) em $base, perfil Teste. O Anki de estudo nao foi tocado."
    Write-Output "Ferramentas > DFC Probe > Variantes nos meus cartoes (uso livre). Para fechar: feche a janela do Anki de teste."
    exit 0
}

# 6) espera o roteiro terminar (ate 6 min; so este processo e encerrado, nunca o Anki de estudo)
$limit = if ($ComLLM) { 360 } else { 150 }
if (-not $proc.WaitForExit($limit * 1000)) {
    Write-Warning "O roteiro nao terminou em $limit s; encerrando o Anki de teste (PID $($proc.Id))."
    Stop-Process -Id $proc.Id -Force
}
if (-not (Test-Path $result)) {
    Write-Error "O roteiro nao gravou resultado (veja $base\logs)."
    exit 1
}
$r = Get-Content $result -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Output "Resultado completo: $result"
Write-Output "Telas (imagens): $(Join-Path $resultDir 'telas')"
$r | ConvertTo-Json -Depth 8
if ($r.terminou -ne $true) { exit 1 }
exit 0
