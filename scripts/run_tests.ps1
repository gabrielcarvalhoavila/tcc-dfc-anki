# Roda todos os testes (pipeline e add-on com Anki simulado). Uso: .\scripts\run_tests.ps1
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = "$root\pipeline;$root\addon"
Set-Location $root
python -m unittest discover -s tests -v
exit $LASTEXITCODE
