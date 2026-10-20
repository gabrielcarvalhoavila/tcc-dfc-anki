# Roda todos os testes (pipeline e add-on com Anki simulado). Uso: .\scripts\run_tests.ps1 [-Real]
# -Real inclui os testes com o motor real do Anki; antes: python -m venv .venv; .venv\Scripts\python -m pip install anki==26.5
param([switch]$Real)
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$root\pipeline;$root\addon"
Set-Location $root
$python = "python"
if ($Real) {
    $python = Join-Path $root ".venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        Write-Error "Crie o ambiente: python -m venv .venv; .venv\Scripts\python -m pip install anki==26.5"
        exit 1
    }
}
& $python -m unittest discover -s tests -v
exit $LASTEXITCODE
