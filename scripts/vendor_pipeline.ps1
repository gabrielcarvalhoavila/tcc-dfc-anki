# Copia para dentro do add-on os modulos do pipeline que a variante sob demanda usa: uma fonte so (pipeline/dfc_pipeline).
# A lista precisa conter tudo o que esses modulos importam (tests/test_live.py confere).
$PipelineModules = @("__init__.py", "cards.py", "generate.py", "llm.py", "prompts.py", "util.py", "validate.py")

function Copy-PipelineInto {
    param([string]$Root, [string]$AddonDir)
    $dest = Join-Path $AddonDir "dfc_pipeline"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    foreach ($f in $PipelineModules) {
        Copy-Item (Join-Path $Root "pipeline\dfc_pipeline\$f") (Join-Path $dest $f) -Force -ErrorAction Stop
    }
}
