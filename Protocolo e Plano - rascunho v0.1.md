# Protocolo e Plano (rascunho v0.2): dependência da forma do cartão (DFC)

Data: 2026-10-20. **Status: rascunho, não congelado** (v0.2: incorpora os prazos e as decisões de 20/10). Ao congelar (commit com data, antes do primeiro sorteio), qualquer mudança vira "desvio" registrado na seção 13. Base: [Fase 5](Fase%205%20-%20Retorno%20%C3%A0%20Ideia%20Original.md) e o experimento-relâmpago ([Passo 1](Relampago%20-%20Passo%201%20%28originais%29.md), [2A](Relampago%20-%20Passo%202A.md), [2B](Relampago%20-%20Passo%202B.md)).

**Como ler.** **[DECIDIR]** = precisa da sua confirmação antes de congelar. **(premissa)** = número meu, de calibração (Fase 5 §6.2 e experimento-relâmpago), não verificado em dados do estudo. † = vem da minha memória, não verifiquei. As datas da seção 11 são limites derivados da entrega (4/12) e da apresentação (18/12), não estimativas de esforço.

---

## 1. Em uma página

| Item | Definição |
|---|---|
| Pergunta | Cartões que o usuário acerta de modo consistente ("suspeitos") perdem mais acerto, quando o enunciado muda, do que os demais ("controles")? |
| Desenho | Experimento microrandomizado dentro do usuário ([Klasnja et al. 2015](https://doi.org/10.1037/hea0000305); [Qian et al. 2022](https://doi.org/10.1037/met0000283)): a cada revisão elegível, o add-on sorteia original ou variante (50/50) e registra o que foi mostrado |
| Desfecho primário | Falha = botão "Again" |
| Medida primária | Diferença de diferenças (DiD), em pontos percentuais: [falha(variante) − falha(original)] nos suspeitos, menos o mesmo nos controles |
| Confirmatórias | H1 (variantes válidas) e H2 (penalidade maior em suspeitos) |
| Exploratórias | H3 (sinais de candidato) e custo/usabilidade. Rotação (E4) fica fora (seção 3) |
| Resultado nulo | Vale como resultado: os critérios das seções 7 e 8 são fixados antes dos dados |

---

## 2. O que o experimento-relâmpago ensinou

**Passo 1 (15/10):** 41 cartões de Redes de Computadores, parados desde 2025, respondidos às cegas: 14 acertos (3 com ressalva), 8 parciais, 1 erro e 18 "não lembro". **Passo 2 (sessões A e B, cerca de 4 dias de intervalo):** 12 conceitos acertados no Passo 1, cada um em forma original numa sessão e em variante na outra: **0/12 falhas nas variantes** (IC 95% ≈ 0–26%); com correção estrita (ressalva conta como erro), original 8/12 e variante 11/12. Esses dados são piloto e **não entram** na análise confirmatória.

Lições incorporadas ao protocolo:

1. Variantes brandas (paráfrase, contexto, ordem) não derrubaram o acerto de cartões curtos "O que é X?" que a pessoa sabe. A DFC, se existe, deve estar em **suspeitos** ou em variantes mais fortes; o relâmpago não testou nenhum dos dois (cartões com no máximo 4 revisões).
2. Original e variante do mesmo cartão no mesmo arquivo deixam copiar a própria resposta. No estudo: **uma forma por exposição**, nunca as duas na mesma sessão.
3. Inversão (descrição → termo) entrega a resposta das outras formas: tipo secundário, sempre com uma forma por exposição.
4. 12 pares só excluem efeitos acima de ~26%: o estudo precisa de centenas de eventos (seção 8).
5. Um único corretor e a autoavaliação são fontes de viés: mitigar com réplica (irmão) e, se houver prazo, subamostra com resposta digitada e correção cega (6.7).

---

## 3. Escopo

| Camada | Entra? | Papel |
|---|---|---|
| E1 validade das variantes | Sim | Confirmatória (H1) |
| E2 penalidade da variante | Sim | Confirmatória (H2): núcleo do TCC |
| E3 sinais de candidato (tempo até revelar, prefixo mínimo identificador) | Sim, exploratória | Registrar desde o primeiro dia; sem limiar de decisão |
| E4 rotação de variantes | **Fora** (decidido em 20/10) | Intervenção: alternar variantes nos cartões com alta DFC e medir depois se a queda de acerto diminui. Exige semanas de seguimento; fica como trabalho futuro |
| E5 custo e usabilidade | Descritiva | Minutos e lapsos extras, % de "variante ruim"; SUS opcional |

---

## 4. Participantes e cartões

### 4.1 Fontes

| Fonte | Papel | Observação |
|---|---|---|
| Você (desktop) | Principal | Coleção nova de Engenharia de Software, AWS Skill Builder, HTTPS e subconjunto reativado da Faculdade |
| Irmão (desktop) | Fonte principal de eventos de suspeitos [DECIDIR: ainda não consultado; resposta até 22/10] | Coleção madura e ativa; consentimento; cartões de texto em português |
| Namorada | Fora da análise de E2 | Baralho novo; só usabilidade (opcional) |

**Gargalo: eventos de suspeitos.** Seus decks ativos têm poucos: no AWS Skill Builder há 21 notas com ≥ 5 revisões e 0 lapsos (61 com ≥ 4); HTTPS e Comunicação/Persuasão não têm nenhuma com ≥ 5. A Faculdade tem 263 notas sem imagem com ≥ 5 revisões e 0 lapsos (antes de filtrar LaTeX e conteúdo não conceitual), mas estão paradas há muito tempo e geram muito esquecimento. Cartões novos demoram a virar suspeitos. Sem o irmão (ou outros voluntários), o resultado provável de H2 é "inconclusivo", e o protocolo já prevê isso (seção 8.1). Contagens de 20/10, por consultas ao Anki.

### 4.2 Elegibilidade do cartão

Tipos Básico e Cloze; só texto (sem imagem, áudio ou LaTeX); conceito (não vocabulário, número, data ou lista ordenada); resposta esperada determinável pelo próprio cartão ("mundo fechado", Fase 5 §5.3); já revisado ao menos uma vez (`reps ≥ 1`), pois a primeira exposição define a forma.

### 4.3 Reativação controlada da Faculdade [DECIDIR]

Descongelar um subconjunto de cartões de texto em ritmo fixo (por exemplo, 25 por dia a partir de 2/11) para gerar eventos "devidos". Cartões parados há mais de um ano falham muito por esquecimento nos dois braços (no relâmpago, 14 de 41 foram lembrados); entram com covariável de intervalo e pesam mais nos controles e nas análises exploratórias.

---

## 5. Definições operacionais (congelar antes do primeiro sorteio)

| Termo | Definição |
|---|---|
| Evento | Uma revisão, no desktop com o add-on, de cartão elegível, com sorteio registrado e resposta registrada |
| Falha | Resposta "Again"; "Hard", "Good" e "Easy" contam como sucesso |
| Suspeito | Elegível com `reps ≥ 5`, `lapses = 0` e última resposta ≥ "Good" [DECIDIR: conferir a contagem real antes de congelar] |
| Controle | Elegível que não é suspeito |
| Variante válida | Resposta esperada preservada, sem ambiguidade, sem vazamento da resposta, redação distinta (validação da seção 6.2) |
| Evento válido | Evento cuja variante não foi marcada "variante ruim" e sem erro do add-on |
| Variante nova | A mesma variante não se repete no mesmo cartão enquanto houver outra disponível |

---

## 6. Procedimento

### 6.1 Geração offline

Para cada cartão elegível, K = 4 variantes: paráfrase, reordenação, reformatação e remoção/troca da pista inicial; inversão como tipo extra e secundário. LLM via OpenRouter, **modelo pago e fixo**; registrar modelo, versão, prompt, parâmetros e data. Nunca durante a revisão. Para notas criadas durante a coleta, o pipeline roda de novo todo dia, antes de a nota virar elegível.

### 6.2 Validação

- **Automática:** outro modelo confere a resposta esperada; checagem de ambiguidade e de vazamento; distância textual mínima.
- **Humana:** amostra de ≥ 100 variantes, estratificada por tipo, revisada por você (e ~30 pelo irmão). Critério: resposta preservada, sem ambiguidade, sem vazamento. Alimenta H1.

### 6.3 Sorteio e registro (add-on)

A cada revisão elegível: sorteio 50/50 com semente por evento; exibição nos dois lados do cartão; registro de `event_id`, `note_id`, `card_id`, braço, `variant_id`, tipo, hash do texto exibido, horário, versões do add-on e do Anki, tempo até revelar, resposta e tempo total. Botão "variante ruim" e opção de desligar.

### 6.3.1 Seleção de cartões: três camadas

1. **Elegibilidade** (4.2): decide se o cartão pode receber variante. Todo cartão elegível, suspeito ou controle, é sorteado em **toda** revisão (50/50); os não elegíveis não são alterados nem analisados.
2. **Estrato** (seção 5): suspeito ou controle, só pelo histórico (`reps`, `lapses`, última resposta). É o que entra na análise primária. O tempo até revelar não existe nas revisões antigas, por isso não define o estrato.
3. **Escore de candidato** (E3, exploratório): combina sequência de acertos, tempo até revelar relativo ao tamanho do enunciado (comparado com a distribuição da própria pessoa), prefixo mínimo identificador (PMI) e formato (Básico ou Cloze). É registrado desde o primeiro dia, mas **não** altera quem é sorteado (evita circularidade); depois se testa se prevê a falha da variante (AUC por validação cruzada, contra o baseline "só `reps`").

### 6.4 Agendamento e modo sonda

O Anki reagenda normalmente com a resposta dada [DECIDIR]. Para ampliar eventos de suspeitos fora da data devida: baralho filtrado **sem reagendamento** †, registrado como `modo = sonda`, com análise separada ou indicador no modelo.

### 6.5 Restrições

Só desktop; revisões no celular não geram eventos e não entram. Anki fixo na 26.05 durante a coleta.

### 6.6 Dados e privacidade

SQLite local no add-on, exportado em CSV; para o irmão, IDs com hash e sem texto de cartão nos dados compartilhados.

### 6.7 Subamostra com resposta digitada (fora do v1 por prazo) [DECIDIR]

Em parte dos eventos, a pessoa digita a resposta; a correção é cega ao braço (outro modelo ou outra pessoa). Serve de checagem do viés da autoavaliação (você conhece a hipótese). Só entra se sobrar prazo depois de M3; senão, o viés fica declarado como limitação e o irmão serve de réplica.

---

## 7. Análise (pré-registrada)

- **Primária (H2):** regressão logística com agrupamento: `falha ~ variante × suspeito + log(intervalo) + log(dias desde a última revisão) + tipo_de_variante`, com efeito aleatório (ou erro-padrão robusto) por cartão e por usuário. A estimativa reportada é a **DiD em pontos percentuais** (efeitos marginais), com IC 95%.
- **Secundárias:** dose-resposta (efeito da variante × `reps`); por tipo de variante; E3 (AUC de um escore de candidato prevendo a falha da variante); custo (minutos e lapsos extras).
- **Sensibilidade:** incluir eventos "variante ruim"; excluir a primeira revisão após a reativação; definição alternativa de suspeito (`reps ≥ 4`); apenas `modo ≠ sonda`; razão de chances na escala logit; subamostra digitada (se existir).
- **Multiplicidade:** um único desfecho primário; o restante é rotulado como exploratório.
- **Execução:** script versionado, rodado uma vez após o fim da coleta [DECIDIR: Python com statsmodels ou R com lme4].

---

## 8. Limiares de pré-registro

| # | Limiar | Valor proposto | Por quê |
|---|---|---|---|
| 1 | Elegibilidade | Seção 4.2 | Fixa o universo |
| 2 | Suspeito | `reps ≥ 5`, `lapses = 0`, última resposta ≥ Good | Seção 5 |
| 3 | H1 (validade) | ≥ 85% das variantes auditadas válidas; tipo abaixo de 70% sai da análise primária | Valores meus; a Fase 5 §7.2 pede limiar combinado |
| 4 | Mínimo para analisar H2 | 300 eventos válidos, ≥ 100 por estrato | Com ≈ 75 por célula só se vê DiD ≥ ≈ 20 pp (premissa) |
| 5 | Alvo e parada | ≈ 1000 eventos válidos (≈ 250 por célula) ou 22/11 (D1), o que vier primeiro; sem olhar o desfecho antes | Com ≈ 250 por célula vê-se DiD ≥ ≈ 10 pp (premissa, sem agrupamento; o poder real é menor) |
| 6 | Decisão em H2 | Seção 8.1 | |
| 7 | Custo (H5) | Falha nas variantes dos controles ≤ 5 pp acima do original; "variante ruim" ≤ 15% das exibidas | Descritivo, sem decisão confirmatória |
| 8 | Exclusões | Variante "ruim"; evento no celular; erro do add-on; versão do Anki diferente da 26.05 | |

### 8.1 Como decidir H2

| Onde está o IC 95% da DiD | Conclusão |
|---|---|
| Estimativa ≥ 10 pp e IC exclui 0 | **Apoiada**: penalidade relevante maior nos suspeitos |
| IC exclui 0, estimativa < 10 pp | **Efeito pequeno**: existe, abaixo do relevante |
| IC inclui 0 e limite superior < 10 pp | **Relevante descartado**: dependência de forma desprezível nesta amostra |
| IC inclui 0 e limite superior ≥ 10 pp | **Inconclusivo**: relatar o menor efeito detectável |

**Por que 10 pp:** uma queda extra de 10 pontos (por exemplo, de 98% para 88% de acerto) já seria perceptível ao usuário e é o que ≈ 250 eventos por célula conseguem distinguir. A Fase 5 §8 usou "menos de ~10% é pequeno; 25% ou mais é promissor" para a taxa de erro das variantes; aqui o alvo é a **diferença** em relação aos controles. [DECIDIR]

---

## 9. Ameaças e tratamento (resumo; detalhes na Fase 5 §4 e §6.5)

| Ameaça | Tratamento |
|---|---|
| Dificuldade da variante | Controles recebem as mesmas variantes; o efeito principal da variante absorve a dificuldade média |
| Esquecimento | Sorteio na revisão devida; covariáveis de intervalo e de dias desde a última revisão; reativados analisados à parte |
| Contaminação sequencial | Uma forma por exposição; variante nova a cada exposição |
| Variante ruim | Validação, auditoria e botão "variante ruim" |
| Viés do experimentador (a hipótese é sua) | Eventos do irmão como réplica; subamostra digitada com correção cega só se sobrar prazo (6.7) |
| Poucos suspeitos | Modo sonda; irmão; relatar o menor efeito detectável |
| Agrupamento (vários eventos por cartão e por pessoa) | Erros-padrão por cartão e usuário; priorizar mais cartões distintos a mais revisões por cartão |
| Generalização | Declarar o escopo: texto conceitual, poucas pessoas |

---

## 10. Ética e privacidade

- Voluntários: o professor André informou (20/10) que não exige TCLE; mesmo assim, consentimento escrito curto por mensagem (finalidade, dados coletados, retirada a qualquer momento).
- O texto dos cartões vai ao provedor de LLM na geração: só com consentimento; privacidade do provedor sem treino com os dados; alternativa local (modelo compatível com OpenAI) se alguém não aceitar.
- Dados compartilhados sem texto de cartão e com IDs anonimizados.

---

## 11. Plano de trabalho (marcos com critério de "pronto")

Datas-limite derivadas da entrega do trabalho (**sex 4/12**) e da apresentação (**sex 18/12**); hoje é ter 20/10. A coleta tem janela de 3 semanas (2/11 a 22/11), e tudo que vem antes precisa estar pronto até 30/10, senão entra o plano B (seção 12). A escrita corre em paralelo desde já; só Resultados e Discussão esperam a análise.

| Marco | Entrega | Pronto quando | Data-limite |
|---|---|---|---|
| M0 | Protocolo v1 congelado | Decisões [DECIDIR] resolvidas; arquivo comitado com a tag `protocolo-v1`; (opcional) registro no OSF † | qui 22/10 |
| M1 | Banco de variantes offline (E1) | Cartões elegíveis processados (os do irmão em lote posterior); auditoria de ≥ 100 variantes com H1 ≥ 85% | qua 28/10 (seus cartões); sex 30/10 (irmão) |
| M2 | Add-on v0 (só registro) | Registra as revisões do desktop sem quebrar o Anki; conferido contra o histórico de revisões do Anki | ter 27/10 |
| M3 | Add-on v1 (sorteio e exibição) | Teste de fumaça: a variante aparece nos dois lados, o log bate com o Anki, "variante ruim" e desligar funcionam; instalado no seu Anki e no do irmão | sex 30/10 |
| M4 | Coleta | Fim em 22/11 (D1) ou ≈ 1000 eventos; só monitoramento de qualidade e contagem | seg 2/11 a dom 22/11 |
| M5 | Análise | Script testado antes com dados do registro; rodado uma vez após D1; tabelas e figuras geradas | seg 23/11 a sex 27/11 |
| M6 | Entrega do trabalho | Metodologia = este protocolo; resultados, ameaças, limitações | sex 4/12 |
| M7 | Apresentação | Slides e ensaio | até sex 18/12 |

---

## 12. Riscos e plano B

| Risco | Gatilho | Plano B |
|---|---|---|
| Poucos eventos de suspeitos | Abaixo do mínimo na metade da janela | Modo sonda; mais voluntários; relatar o menor efeito detectável |
| Add-on atrasa | M3 não pronto em 30/10 | Sondas manuais (como no relâmpago) com registro mínimo; add-on só de registro. A data D1 (22/11) não se move: a janela encurta e o mínimo de 300 eventos continua valendo; abaixo dele, relatório descritivo |
| Variantes ruins | H1 < 85% | Ajustar prompt ou modelo; restringir tipos; repetir a auditoria |
| Anki atualiza e quebra o add-on | Nova versão instalada | Fixar a 26.05 |
| Irmão desiste | Sem dados dele | Só você; E2 descritivo com o menor efeito detectável; ênfase em E1 e em viabilidade |
| Resultado nulo ou inconclusivo | Seção 8.1 | Reportar como está; contribuição: pipeline validado, estimativa com intervalo e lições |

---

## 13. Registro e desvios

A pasta ainda não é um repositório Git (Git 2.55 está instalado). Proposta: `git init` na pasta do TCC e commit do protocolo, com data e tag `protocolo-v1`, antes do primeiro sorteio. Mudanças depois disso entram em `DESVIOS.md`, com data, o que mudou e por quê. O OSF † é opcional (registro público com data).

---

## 14. Decisões

**Decididas em 20/10:** entrega em 4/12 e apresentação em 18/12; E4 (rotação) fora; TCLE não exigido pelo professor.

**Em aberto:**
1. Irmão como fonte de eventos (resposta até 22/10).
2. Definição de suspeito (`reps ≥ 5`; alternativa `reps ≥ 4`) e limiar de 10 pp.
3. Reativação controlada da Faculdade e ritmo (25 por dia a partir de 2/11).
4. Agendamento normal do Anki com variantes (6.4).
5. Subamostra com resposta digitada (6.7): fora do v1?
6. Análise em Python (statsmodels) ou R.
7. OpenRouter: conta e créditos até 23/10, ou modelo local.
8. OK para congelar o protocolo (M0) e liberar a implementação (M1 a M3).
