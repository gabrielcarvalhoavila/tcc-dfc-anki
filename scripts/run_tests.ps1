# Roda todos os testes (pipeline, add-on com Anki simulado e análise). Uso: .\scripts\run_tests.ps1 [-Real]
# -Real inclui os testes que precisam de pacotes extras: o motor real do Anki e numpy, pandas e statsmodels da análise (sem eles, são pulados).
# Antes: python -m venv .venv; .venv\Scripts\python -m pip install anki==26.5 -r analysis\requirements.txt
param([switch]$Real)
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$root\pipeline;$root\addon;$root\analysis"
Set-Location $root
$python = "python"
if ($Real) {
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        Write-Error "Crie o ambiente: python -m venv .venv; .venv\Scripts\python -m pip install anki==26.5 -r analysis\requirements.txt"
        exit 1
    }
}
& $python -m unittest discover -s tests -v
exit $LASTEXITCODE
