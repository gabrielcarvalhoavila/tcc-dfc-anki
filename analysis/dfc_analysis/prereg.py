"""Constantes pré-registradas da análise (protocolo v1.7, seções 5, 7 e 8).

Cada valor vem do protocolo; mudar qualquer um depois do primeiro sorteio (28/10/2026) é um desvio e entra em docs/desvios.md.
"""
from __future__ import annotations

import datetime

VERSAO_ANALISE = "1.0"

# Seção 5 e 8: janela, banco e versão do Anki dos eventos que entram
JANELA_INICIO = datetime.date(2026, 10, 28)
JANELA_FIM = datetime.date(2026, 11, 22)
FUSO = "America/Sao_Paulo"  # "data local do computador do autor"
BANCO_HASH = "e1284dee5eac"
ANKI_VERSAO = "26.05"
PERFIL_ENV = "DFC_PERFIL_ESTUDO"  # nome do perfil de estudo: argumento da linha de comando ou esta variável; nunca no código

# Seção 5: suspeito = reps >= 5, lapses = 0 e última resposta >= Good (3)
SUSPEITO_REPS = 5
SUSPEITO_ULTIMA_RESPOSTA = 3
SUSPEITO_REPS_SENS = 4  # sensibilidade (seção 7)
SUSPEITO_NREV_SENS = 5  # sensibilidade com `n_reviews` (seção 7)

# Seção 8: limiares
ALVO_EVENTOS = 1000  # parada: ≈ 1000 eventos válidos ou 22/11, o que vier primeiro
MIN_EVENTOS = 300  # mínimo para analisar H2
MIN_POR_ESTRATO = 100
LIMIAR_PP = 10.0  # 8.1: efeito relevante
H1_LIMIAR = 0.85
H5_FALHA_CONTROLE_PP = 5.0  # 8, linha 7: falha nas variantes dos controles <= 5 pp acima do original
H5_VARIANTE_RUIM = 0.15  # 8, linha 7: "variante ruim" <= 15% das exibidas
NIVEL_IC = 0.95
PODER = 0.80  # só para o "menor efeito detectável" que a seção 8.1 manda relatar

# Seção 7: dimensões da forma (cada tipo de variante muda uma)
DIMENSAO = {
    "paraphrase": "palavras",
    "reorder": "ordem",
    "cue_swap": "palavras iniciais",
    "pergunta": "formato",
    "reformat": "formato",
    "sem_imagem": "imagem",
}

# Decisões de análise que o protocolo deixa em aberto, fixadas no código antes do fim da coleta
DOSE_FAIXAS = 3  # dose-resposta: `reps` em terços dos eventos da análise (`reps` é muito assimétrico: no 1º dia, mediana 15 e máximo 38)
MIN_CELULA = 10  # subgrupo com célula (estrato x braço) menor que isso não é estimado
TEMPO_PERCENTIL = 99  # tempo total truncado neste percentil (cartão esquecido aberto distorce)
E3_RIDGE = 1.0  # penalidade L2 do escore de candidato (sinais padronizados): poucas falhas, então um pouco de regularização
E3_BLOCOS = 5  # blocos da validação cruzada agrupada por nota

# Eventos que a seção "desvios" manda excluir numa sensibilidade (prefixo do `event_id`; ver docs/desvios.md)
EVENTOS_SENSIBILIDADE = {
    "3ceb41c0": "nota editada no meio da exposição (desvios.md, entrada 4)",
}
