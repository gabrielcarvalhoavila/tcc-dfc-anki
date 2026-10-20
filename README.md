# TCC: dependência da forma do cartão (DFC) em repetição espaçada

Um add-on do Anki e um pipeline com LLM para medir se cartões que a pessoa "sempre acerta" dependem da **forma** do enunciado. A cada revisão elegível de outro dia do Anki, o add-on sorteia o cartão original ou uma variante (mesma resposta, outras palavras, ordem ou formato) e registra o resultado; a análise compara a queda de acerto da variante em cartões suspeitos e em controles. Resultado nulo também é resultado.

**Prazos:** entrega do trabalho em 4/12/2026; apresentação até 18/12/2026. Protocolo v1.1 congelado em 20/10/2026 (tag `protocolo-v1.1`; a `protocolo-v1` fica como histórico).

## Estado

| Marco | O quê | Data-limite | Estado |
|---|---|---|---|
| M0 | Protocolo v1.1 congelado | 20/10 | Feito (v1 e v1.1 em 20/10, antes de qualquer sorteio) |
| M2 | Add-on v0 (só registro) | 27/10 | Feito em 20/10: 12 revisões no Anki 26.05 real conferidas contra o histórico do Anki, 0 divergências em nota, horário, tempo, intervalo anterior e tipo; a resposta desfeita (Ctrl+Z) fica sem par e é marcada na exportação |
| M1 | Banco de variantes e auditoria de 100 | 28/10 (irmão: 30/10) | Código pronto e testado com LLM falso; falta conta no OpenRouter, modelo fixo, geração e auditoria |
| M3 | Add-on v1 (sorteio e exibição) | 30/10 | Código pronto (0.2.2); testado com o motor real do Anki 26.5 sem interface e, na interface (20/10), exibição das variantes, tecla `x` e Ctrl+Z; falta o banco real (roteiro em [arquitetura](docs/arquitetura.md)) |
| M4 | Coleta | 2/11 a 22/11 | |
| M5 | Análise | 23/11 a 27/11 | Não iniciado |
| M6 | Entrega do trabalho | 4/12 | |
| M7 | Apresentação | até 18/12 | |

## Mapa do repositório

| Pasta | Conteúdo |
|---|---|
| `docs/` | [projeto](docs/projeto.md), [fundamentação](docs/fundamentacao.md), [protocolo](docs/protocolo.md) (congelado), [piloto](docs/piloto-relampago.md), [arquitetura](docs/arquitetura.md), [desvios](docs/desvios.md) |
| `addon/dfc_probe/` | Add-on do Anki (registra revisões, sorteia e exibe variantes) |
| `pipeline/dfc_pipeline/` | Exportar notas, gerar, validar, auditar e empacotar variantes |
| `tests/` | 106 testes, sem rede; 11 usam o motor real do Anki (`run_tests.ps1 -Real`) e os demais, um Anki simulado |
| `scripts/` | Instalar e empacotar o add-on, rodar os testes, conferir a exibição de um banco numa cópia da coleção |
| `pilot/relampago/` | Dados do piloto manual |
| `data/` | Local, ignorado pelo Git: texto de cartões, variantes e logs |

## Começar

1. **Testes:** `.\scripts\run_tests.ps1`
2. **Add-on:** feche o Anki, rode `.\scripts\install_addon.ps1`, abra o Anki e confira em Ferramentas > DFC Probe > Status.
3. **Pipeline:** copie `.env.example` para `.env` e preencha (a chave nunca vai para o Git nem para chats). Depois, na raiz:

```powershell
$env:PYTHONPATH = "pipeline"
python -m dfc_pipeline export --query "deck:HTTPS"
python -m dfc_pipeline generate --limit 5 --dry-run   # testa o fluxo sem LLM
python -m dfc_pipeline stats --generation data/generation.jsonl
```

Detalhes e esquemas em [arquitetura](docs/arquitetura.md).

## Universo de cartões do autor (consulta de 20/10)

De 1332 notas lidas (AWS Skill Builder, HTTPS e Faculdade não nova), **697 passam na elegibilidade estrutural** (só texto, sem LaTeX, Cloze com uma lacuna, resposta não numérica) e **276 delas são suspeitas pelo histórico** (`reps ≥ 5` e `lapses = 0`, pelo primeiro cartão da nota): AWS 21 e Faculdade 255 (Grafos 54, Otimização combinatória 48, Cálculo II 46, Álgebra Linear 27, Algoritmos e Programação 18, Probabilidade 16, Fundamentos de Algoritmos 14, Introdução à arquitetura 11, Complexidade 11, Org B 6, outras 4). Redes e Sisop II têm cartões elegíveis, mas nenhum suspeito (no máximo 4 revisões). É contagem estrutural: o sinal "conceitual" do LLM ainda vai reduzi-la. O `reps` do Anki inclui passos de aprendizado: dos 276, 193 têm só 3 ou 4 revisões em estado de revisão e 83 (todas da Faculdade) têm 5 ou mais (protocolo v1.1).
