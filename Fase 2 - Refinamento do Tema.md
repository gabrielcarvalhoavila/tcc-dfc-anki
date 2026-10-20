# Fase 2: Pesquisa ampla e refinamento do tema

Data: 2026-10-14. Continua a [Fase 1](Fase%201%20-%20An%C3%A1lise%20e%20Pesquisa%20Acad%C3%AAmica.md). Nenhum código foi escrito.

**Como ler.** Referências marcadas com † vêm da minha memória e não foram verificadas nesta sessão. Para a maioria dos papers li só o resumo; o texto completo foi lido apenas para o KARL. Fontes consultadas: arXiv, OpenAlex, Europe PMC, Crossref, GitHub, documentação e fóruns do Anki. Semantic Scholar bloqueou (erro 429), e não tive acesso a Scopus, ERIC nem Portal CAPES.

---

## 0. Resumo executivo

- **"Overfitting visual" não fecha como tese de TCC de engenharia.** Não existe dataset público que combine texto/formato de cartão com logs de revisão, e testar o efeito exige humanos. Vira **motivação de projeto** ("dependência da forma do cartão"), não a hipótese a provar.
- **O que funciona sem grupo de estudo:** artefato de software + avaliação técnica reproduzível (logs públicos, correção automática por oráculo, simulação) + piloto pequeno e exploratório.
- **Recomendação:** Candidato 1 (cartões de habilidade com variantes verificadas por testes, domínio programação/SQL) como núcleo. Alternativas: Candidato 3 (linter de cartões), escopo menor; Candidato 2 (nota implícita), mais "dados" e menor risco de implementação.
- **Descobertas que mudam o plano:**
  1. O ecossistema de apps com FSRS + IA já está saturado; "app de flashcards com IA" não é contribuição.
  2. Nota implícita por tempo já existe em add-on e em app, sem avaliação publicada.
  3. O `duration` dos logs públicos do Anki é o tempo total até a nota, não o tempo até revelar a resposta.
  4. A evidência sobre variar cartões é mista.
  5. Estudos publicados de agendadores usam de dezenas de usuários (KARL: 27) a milhares (Upadhyay et al., 2020).

---

## 1. Restrições e consequências para o desenho

| Restrição | Consequência |
|---|---|
| TCC de Engenharia de Software | A contribuição é um artefato (requisitos, arquitetura, testes, reprodutibilidade) mais uma avaliação. Metodologia natural: Design Science Research ([Hevner et al. 2004](https://doi.org/10.2307/25148625); [Peffers et al. 2007](https://doi.org/10.2753/mis0742-1222240302); [Wieringa 2014](https://doi.org/10.1007/978-3-662-43839-8), voltado a ES). |
| Sem grupo de estudo | Evitar experimentos confirmatórios sobre aprendizagem. Usar logs públicos, oráculos automáticos, simulação e um piloto exploratório. |
| Estudo-piloto/proposta pequena | Uma pergunta de pesquisa, escopo mínimo, sem alegar "melhora a aprendizagem". |
| Tese interessante | Hipótese falseável por métrica objetiva. |

---

## 2. Respostas às suas dúvidas

### 2.1 Como medir memória sem ser subjetivo

Memória não é medida diretamente. O que se mede é **desempenho de recordação**: depois de um intervalo, o aluno acerta ou erra (0/1). Os agendadores estimam a **probabilidade de acerto** e são avaliados comparando a previsão com o resultado observado.

- **Métricas padrão** do [benchmark aberto](https://github.com/open-spaced-repetition/srs-benchmark) (9.999 usuários, ~350 milhões de revisões avaliadas): *log loss* (qualidade das probabilidades), *AUC* (separação entre acerto e erro) e *RMSE (bins)* (calibração: quando prevê 90%, acerta ~90%?). A divisão é temporal: treina no passado, testa no futuro.
- **Onde há subjetividade:**
  1. No Anki, o usuário decide se "lembrou" (Again vs. o resto) e escolhe Hard/Good/Easy.
  2. Fatores de contexto (cansaço, distração).
- **Onde não há:** quando o sistema verifica a resposta (texto digitado comparado, teste de código, resultado de consulta SQL), o acerto/erro é objetivo.
- **O que isso não mede:** aprendizagem de longo prazo causada pelo software. Isso exige experimento (KARL: 27 usuários em sessões de 6 dias; [Upadhyay et al. 2020](https://arxiv.org/abs/2010.04430): milhares de usuários em ensaio randomizado).

### 2.2 "Visual" e "domínio"

**"Visual".** O termo não tem definição acadêmica. O que a literatura e a prática descrevem são variantes de dependência da forma do cartão:

| Significado possível | Fonte |
|---|---|
| Ordem fixa de revisão permite adivinhar pelo contexto | Docs do Anki: a ordem "Deck, then due date" "makes it easier to guess the answer based on context, and leads to weaker memories" ([deck options](https://docs.ankiweb.net/deck-options.html)) |
| Decorar a redação/pista da pergunta | [Matuschak 2020](https://andymatuschak.org/prompts/) ("discourage pattern matching"; cloze copiado de texto é suscetível) |
| Decorar a ordem das lacunas / excesso de contexto | [Fórum do Anki, tópico 55947](https://forums.ankiweb.net/t/image-occlusion-and-the-problem-of-excess-context-in-flashcards/55947) |
| Decorar a posição em oclusão de imagem | [Anki issue #3626](https://github.com/ankitects/anki/issues/3626) ("hide all, guess one") |
| Transferência fraca quando o par estímulo-resposta é rearranjado | [Pan & Rickard 2018](https://doi.org/10.1037/bul0000151) |

Sugestão: abandonar "visual", chamar de **dependência da forma do cartão** e tratá-la como motivação.

**"Domínio".** Era o *assunto* que o aluno estuda (vocabulário, medicina, programação). Importa porque define o que dá para verificar automaticamente e qual literatura se aplica. Sugestão: **programação/SQL** como domínio de demonstração. É o seu meio, permite correção objetiva por testes, e a evidência publicada é mais forte em idiomas e medicina.

### 2.3 O que dá para afirmar num TCC sem grupo de estudo

| Pode afirmar | Como sustentar |
|---|---|
| "A previsão de recordação é tão boa quanto a do método X" | Replay offline em logs públicos, com split temporal |
| "O pipeline gera variantes válidas em Y%" | Testes automáticos, mutantes e amostra rotulada por humanos |
| "O sistema é utilizável" | Piloto pequeno (SUS), apresentado como descritivo |
| **Não afirmar:** "melhora a retenção" | Exige experimento controlado. O próprio KARL ressalva que o desempenho offline não equivale a ganho de aprendizagem |

---

## 3. Panorama: o que já existe

### 3.1 Algoritmos e benchmark

- **FSRS** (Ye et al., KDD 2022 / TKDE 2023). Versões: 4.5 (17 parâmetros), FSRS-6 (21, curva de esquecimento ajustável), FSRS-7 (34, intervalos fracionários). Segundo o blog do Expertium, FSRS-6 está no Anki desde a 25.07.
- **Números do benchmark** (sem revisões do mesmo dia): FSRS-6 tem log loss 0,346 e AUC 0,703. O RWKV-Instant, treinado com atributos extras (duração, informação de cartões irmãos, hierarquia de decks, dia da semana), chega a 0,277 e 0,833. Modelos paramétricos interpretáveis estão longe do teto.
- **Tempo de resposta:** o LSTM do benchmark usa tempo de resposta (AT) e o GRU não. Os log loss são praticamente iguais (0,3332 vs. 0,3328), com arquiteturas diferentes. Não permite concluir, mas sugere que o ganho do tempo é pequeno.
- **Outros:** HLR ([Settles & Meeder 2016](https://doi.org/10.18653/v1/p16-1174)), ACT-R, DASH, [DAS3H](https://arxiv.org/abs/1905.06873), [MEMORIZE (Tabibian et al. 2019)](https://doi.org/10.1073/pnas.1815156116), [Reddy et al. 2016](https://arxiv.org/abs/1602.07032) (transição de fase na taxa de novos itens).
- **Anki** já oferece simulador de carga ("Help Me Decide"), Easy Days, Auto Advance e ordenação por retrievability. O cálculo de retenção mínima recomendada foi removido na 25.07.

### 3.2 Ecossistema de apps (lista [awesome-fsrs](https://github.com/open-spaced-repetition/awesome-fsrs), 2026)

| App/projeto | O que faz | O que implica |
|---|---|---|
| Gnoseed | Múltipla escolha para engenheiros. Errou = Again; acertou = Easy/Good/Hard **por tempo de resposta** (limiares padrão 4 s e 10 s) | Nota implícita já existe em produto |
| MemPro | Exercícios de código com sandbox e testes, mas o usuário **autoavalia**; MCP para Claude Code/Cursor | Correção objetiva existe, nota ainda é manual |
| LeetFlash, LeetSRS | Capturam submissões do LeetCode e agendam | SRS para programação já tem produtos |
| HSRS (satchelspencer) | Cartões gramaticais parametrizados; reagenda subcartões por estatística bayesiana | Conceito com várias realizações já existe em idiomas |
| Word2Sentence | Avalia recordação sem botões, com frases geradas por IA | Correção automática sem autoavaliação |
| Loudwalk, MySummaries, Quanta, Avorio, Discito, Flipnem, spacedrep | Voz, perguntas erradas viram cartões, geração com fontes, IA local, servidores MCP | "Flashcards + IA + FSRS" genérico está saturado |

Bibliotecas maduras para reuso: ts-fsrs, py-fsrs, fsrs-rs (inclui fsrs-browser).

### 3.3 Pesquisa com LLM + repetição espaçada

- [KARL](https://arxiv.org/abs/2402.12291) (EMNLP 2024): agendador sensível ao texto do cartão (BERT + DKT + recuperação). 123.143 logs de 543 usuários; avaliação online com **27 usuários em 32 sessões de 6 dias**; aprovado por comitê de ética.
- [LECTOR](https://arxiv.org/abs/2508.03275): preprint de um autor, avaliado em aprendizes **simulados** (ver Fase 1).
- [Memdora](https://arxiv.org/abs/2607.25096) (preprint 2026): 17 tipos de interação sobre FSRS-6. Sem resultado de aprendizagem no resumo.
- [SRS-Stories](https://arxiv.org/abs/2512.18362) (EMNLP 2025, trilha industrial): histórias geradas só com vocabulário conhecido, revisando palavras em contextos variados. Avaliação de qualidade textual, não de aprendizagem.
- [SMART](https://arxiv.org/abs/2406.15352) (EMNLP 2024): preferência *expressa* e *observada* dos alunos divergem ("o que parece útil nem sempre é útil").
- [SmartFlash](https://arxiv.org/abs/2602.14431) (ISLS 2026, 6 alunos): querem saídas de IA editáveis e transparentes.
- Correção de respostas curtas com LLM: [Kortemeyer 2023](https://arxiv.org/abs/2309.09338) (GPT-4 comparável a modelos artesanais, pior que modelos especializados), [Walsh et al. 2025](https://arxiv.org/abs/2508.04063), [Cong et al. 2026](https://arxiv.org/abs/2605.00200) (a confiança do LLM sozinha não basta).
- Qualidade de questões por LLM: [Moore et al. 2022](https://doi.org/10.1007/978-3-031-16290-9_18), [2023](https://doi.org/10.1007/978-3-031-42682-7_16), [IEEE TLT 2024](https://doi.org/10.1109/tlt.2024.3394807). Mas [An et al. 2026](https://arxiv.org/abs/2609.27063) mostra que a dificuldade rotulada por LLM não prediz a empírica (ρ ≈ 0,06). Questões de recuperação geradas por LLM: [An et al. 2025](https://arxiv.org/abs/2507.05629) (cerca de 60 alunos; acerto 89% vs. 73%).
- Risco de terceirizar o esforço: [Bastani et al. 2025, PNAS](https://doi.org/10.1073/pnas.2422633122) (IA sem salvaguardas pode prejudicar a aprendizagem).

### 3.4 Repetição espaçada na educação

- **Visão geral:** [Kang 2016](https://doi.org/10.1177/2372732215624708); [Lindsey et al. 2014](https://doi.org/10.1177/0956797613504302) (revisão personalizada: +16,5% sobre estudo em bloco, +10% sobre espaçamento genérico).
- **Medicina (Anki):** [Deng et al. 2015](https://doi.org/10.1007/s40037-015-0220-x), [Lu et al. 2021](https://doi.org/10.1007/s40670-021-01386-9), [BMC Med Educ 2022](https://doi.org/10.1186/s12909-022-03324-8), [revisão narrativa 2025](https://doi.org/10.1007/s40670-025-02487-5).
- **Programação/computação:** [FIE 2024](https://doi.org/10.1109/fie61694.2024.10893444) (IFPB, Brasil; cita eventos brasileiros WEI e SBIE, vale consultar como literatura nacional); [ICER 2019](https://doi.org/10.1145/3291279.3339411) (Univ. de Michigan, ferramenta de prática espaçada e intercalada). Resultados não lidos.
- **Tutor de IA com prática de recuperação:** [Baillifard et al. 2023](https://arxiv.org/abs/2309.13060) (N=51, semestre).
- **Variação:**
  - [Cowan et al. 2024](https://doi.org/10.1073/pnas.2311077121): variabilidade ajuda memória de item; para memória associativa, a repetição foi melhor e o benefício do espaçamento só apareceu sem variabilidade.
  - [Serrano & Pellicer-Sánchez 2026](https://discovery.ucl.ac.uk/id/eprint/10216384/) (92 aprendizes de inglês): espaçamento e variação de contexto aumentaram o esforço de processamento e **não** facilitaram recordação.
  - [Brunmair & Richter 2019](https://doi.org/10.1037/bul0000209) (59 estudos): intercalar ajuda mais em material visual (pinturas g = 0,67), ajuda pouco em matemática (g = 0,34) e **prejudica com palavras** (g = −0,39).
  - [Pan & Rickard 2018](https://doi.org/10.1037/bul0000151): transferência do teste d = 0,40, fraca para pares estímulo-resposta rearranjados.

### 3.5 Dores recorrentes em comunidades

| Dor | Evidência |
|---|---|
| Nota automática por tempo | Add-on [Pass/Fail Review](https://forums.ankiweb.net/t/53872) (mede do exibir pergunta ao revelar; padrão 1 s / 7 s; o autor diz que com FSRS pode ser redundante e não o usa mais); [tópico 41037](https://forums.ankiweb.net/t/41037) (objeções: tempo "não significa nada" para aprendizes recreativos, TDAH, pausas) |
| Diagnóstico de cartões ruins | [Tópico 67575](https://forums.ankiweb.net/t/67575): leech do Anki é "blunt"; ideia de add-on para marcar cartões ruins por dificuldade, lapsos e tempo |
| Dependência de contexto/ordem em cloze e oclusão | Tópico 55947 e issue #3626 (acima) |
| Orçamento de tempo em vez de número de cartões | [Issue #737](https://github.com/open-spaced-repetition/fsrs4anki/issues/737) (encerrada como "not planned") |
| Atomicidade vs. recordação integrada | Tópicos [66733](https://forums.ankiweb.net/t/66733), [67642](https://forums.ankiweb.net/t/67642), [69505](https://forums.ankiweb.net/t/69505) (só títulos e trechos vistos) |
| Correção de resposta digitada | O Anki compara texto mas não nota sozinho; usuários usam scripts (`pycmd('ease1')`…) e templates |

### 3.6 Lacunas candidatas

1. Habilidades (código/SQL) com correção objetiva e variação anti-memorização integradas ao SRS: não encontrei trabalho acadêmico.
2. Avaliação rigorosa de nota implícita: existem add-on e app, sem avaliação publicada.
3. Qualidade de cartões como verificação automática: usuários pedem; LLM para qualidade de questões existe, mas não para flashcards.
4. Especificidade de superfície medida em logs reais (cartões irmãos): não achei análise formal.
5. Correção de respostas digitadas com abstenção por confiança: a literatura de correção automática recomenda confiança, mas não há aplicação a flashcards.

---

## 4. Dados e ferramentas disponíveis sem recrutar ninguém

| Recurso | Conteúdo | Observações |
|---|---|---|
| [anki-revlogs-10k](https://huggingface.co/datasets/open-spaced-repetition/anki-revlogs-10k) | 10 mil coleções; `card_id`, `day_offset`, `rating` (1–4), `state`, `duration` (ms, 0–60000), `elapsed_days/seconds`; tabelas `cards` (`card_id`, `note_id`, `deck_id`) e `decks` | 15,7 GB, parquet. Exige aceitar condições no Hugging Face. **Sem texto.** `duration` = tempo total até a nota (o timer interno do Anki vai da exibição da pergunta até o botão, com teto de 60 s) |
| FSRS-Anki-20k | 20 mil coleções, ~99 GB | Marcado como obsoleto (substituído pelo 10k) |
| [Duolingo HLR](https://github.com/duolingo/halflife-regression) | 13 milhões de traços; 361 MB; `p_recall`, `delta`, `lexeme_string`, histórico | Sem tempo de resposta |
| Dataset do KARL | 123.143 logs; 543 usuários; 23.918 cartões (trivia); `card_text`, acerto/erro **verificado pelo sistema**, `elapsed_milliseconds` (tempo até enviar) | Liberado pelos autores; URL não confirmada. Domínio de trivia |
| [srs-benchmark](https://github.com/open-spaced-repetition/srs-benchmark) | Código, métricas e split temporal prontos | Python (uv) |
| Bibliotecas FSRS | ts-fsrs, py-fsrs, fsrs-rs, fsrs-browser | Reuso direto |
| Correção de respostas curtas | SciEntsBank e Beetle (usados por Kortemeyer 2023) | Mohler (CS) †, não verificado |
| MaiMemo (Dataverse) | Citado no awesome-fsrs | Não consegui abrir a página para checar campos |

---

## 5. Candidatos

### Candidato 1: Cartões de habilidade com variantes verificadas por testes (programação/SQL)

- **Problema.** Em habilidades, repetir o mesmo exercício favorece decorar a resposta ou a forma; a autoavaliação é subjetiva; criar variantes à mão é caro.
- **Ideia.** "Cartão = conceito + gerador de variantes + oráculo de correção". Um LLM instancia tarefas-modelo (escrever função, prever saída, corrigir bug, consulta SQL), variando nomes, enunciado e dados. Gera também a solução de referência e os testes. Um pipeline valida antes de publicar. O aluno responde digitando; a correção é automática; o FSRS agenda no nível do conceito.
- **Tese e hipóteses (engenharia).**
  - H1: a maioria das variantes passa na verificação (taxa de validade comparada entre modelos locais e de nuvem).
  - H2: as variantes diferem do original na superfície (distância de tokens/AST) e preservam a semântica (testes, mutantes, revisão humana de amostra).
  - H3: custo e latência por variante são viáveis em hardware comum.
  - H4 (exploratória, piloto): descrever como a taxa de acerto das variantes se compara à do enunciado original.
- **Verificação (oráculo).** Executar a referência nos testes; checar que mutantes (versões erradas) são detectados; descartar quase-duplicatas; opcionalmente uma segunda solução independente.
- **Avaliação sem grupo.** Métricas do pipeline, testes do próprio sistema, segurança da execução (timeouts, limites; navegador com WebAssembly, como Pyodide/sql.js †), simulação de carga de revisões com parâmetros reais do dataset. Piloto de 5 a 10 voluntários só para usabilidade (SUS) e logs, descritivo.
- **Prior art e novidade.** Geração de exercícios com LLM ([Sarsa et al. 2022](https://doi.org/10.1145/3501385.3543957), 475 citações; [exercícios contextualizados 2024](https://doi.org/10.1145/3632620.3671103)); SRS em programação (FIE 2024, ICER 2019); produtos MemPro, LeetFlash, LeetSRS; Math Academy usa bancos de problemas por tópico, proprietário e sem estudos acadêmicos. Não achei trabalho que una geração de variantes, verificação por testes e SRS. Novidade: média-alta.
- **Riscos.** Testes fracos gerados por LLM; equivalência semântica difícil de provar (mitigar com mutantes e amostra humana); segurança do sandbox; escopo de interface.
- **Escopo mínimo.** Python + SQL, 10–20 conceitos, interface simples, ts-fsrs, relatório de avaliação do pipeline.

### Candidato 2: Nota implícita (correção + latência) com avaliação offline

- **Problema.** Autoavaliação é subjetiva e pesada; "Hard misuse" está documentado nos próprios manuais do Anki; já há add-on e app que derivam nota do tempo, sem avaliação.
- **Tese.** Uma nota inferida de correção + latência normalizada por usuário/cartão é **não inferior** às 4 notas manuais na previsão da próxima recordação.
- **Avaliação.** Subamostra de 200 a 500 usuários do anki-revlogs-10k; split temporal; FSRS-6; condições: (a) 4 notas, (b) 2 notas (pass/fail), (c) limiares fixos (1 s/7 s do add-on; 4 s/10 s do Gnoseed), (d) limiares relativos (z-score por usuário e por cartão), (e) modelo ordinal aprendido. Métricas: log loss, AUC, RMSE (bins); comparação pareada por usuário; margem de não inferioridade definida antes.
- **Ameaças.** `duration` mistura tempo de recordação, leitura da resposta e pausas, com teto de 60 s; o pass/fail é autorrelatado; o resultado pode ser nulo (o benchmark já tem opção `--two_buttons` e o LSTM com tempo não se destaca). Replicação parcial com o dataset do KARL (latência limpa, sem as 4 notas).
- **Entregáveis.** Biblioteca de nota implícita, pipeline reprodutível e protótipo de revisão.
- **Novidade.** Média: o conceito existe; a avaliação sistemática em larga escala não achei.

### Candidato 3: Linter de cartões

- **Problema.** Cartões ruins (regras de Wozniak, "litmus tests" de Matuschak); usuários pedem diagnóstico (tópico 67575).
- **Tese.** As regras de formulação podem ser operacionalizadas como verificações automáticas (regras + LLM), com concordância substancial com avaliadores humanos (κ de Cohen / α de Krippendorff).
- **Artefato.** Catálogo de 10–15 verificações (atomicidade, ambiguidade, pergunta binária, lista não decomposta, cloze com contexto excessivo, pista que entrega a resposta…); CLI e integração com decks em Markdown ou Obsidian.
- **Avaliação.** 150 a 300 cartões rotulados por você e 1–2 colegas; baseline (um único prompt) vs. regras + LLM; opcionalmente, correlação do escore com lapsos em coleções exportadas voluntariamente.
- **Prior art.** LLM para qualidade de questões existe (seção 3.3); busca rápida no GitHub achou 4 repositórios triviais de "linter de flashcards". Novidade: média.
- **Risco.** LLM fraco em prever dificuldade (An et al. 2026), então restringir-se a falhas estruturais verificáveis. Rótulos humanos são subjetivos: medir concordância.

### Candidato 4: Especificidade de superfície em logs reais (cartões irmãos)

- **Problema (liga ao tema original).** Quanto da memória é específica do cartão e quanto é do conceito? O Anki agrupa cartões em notas (reverso, cloze adjacentes); o FSRS trata cada cartão como independente; o Math Academy propaga crédito implícito em hierarquias (sem estudo acadêmico).
- **Tese.** Uma revisão bem-sucedida de um cartão irmão melhora a previsão do outro além do histórico do próprio cartão; um agendador com crédito parcial entre irmãos reduz revisões sem perda de retenção prevista.
- **Avaliação.** Offline no anki-revlogs-10k, usando `note_id`: FSRS-6 + atributos de irmãos; ΔlogLoss; simulação de carga com crédito parcial.
- **Riscos.** Confundidores (o bury de irmãos os espaça; irmãos costumam ser aprendidos juntos); o dataset não informa o tipo do cartão; resultado pode ser nulo.
- **Novidade.** Média-alta, com risco maior.

### Candidato 5: Correção de respostas digitadas com LLM e abstenção

- **Problema.** Recordação digitada exige corretor; o Anki não nota sozinho.
- **Tese.** Um corretor com LLM local e abstenção por confiança concorda com humanos nos casos em que decide e encaminha o resto para autoavaliação, com custo e latência viáveis.
- **Avaliação.** SciEntsBank/Beetle e conjunto próprio de pares (pergunta, resposta de referência, resposta do aluno) de ES; curva cobertura × precisão; latência e custo (local vs. nuvem).
- **Prior art.** Correção automática de respostas curtas (seção 3.3). Novidade: média.

### Outros considerados e não priorizados

| Ideia | Por que não |
|---|---|
| Inicialização por conteúdo (KARL + FSRS) | Muito ML, pouco ES; dataset de trivia |
| Planejamento com prazo/orçamento de tempo | O Anki já tem simulador, Easy Days e ordenação por retrievability |
| Harness de benchmark/simulação | Infraestrutura útil como componente, sem tese própria |
| Variação de contexto em vocabulário | Evidência mista (Serrano & Pellicer-Sánchez 2026; Brunmair & Richter 2019) e exige humanos |

---

## 6. Comparação e recomendação

Escalas de 1 a 5, julgamento meu. Risco: menor é melhor.

| Candidato | Aderência ao tema | Fit com ES | Avaliável sem grupo | Novidade | Risco | Escopo (menor = mais enxuto) |
|---|---|---|---|---|---|---|
| 1. Habilidades com variantes verificadas | 5 | 5 | 4 | 4 | 3 | 3 |
| 2. Nota implícita (offline) | 4 | 3 | 5 | 3 | 2 | 4 |
| 3. Linter de cartões | 4 | 4 | 3 | 3 | 2 | 4 |
| 4. Irmãos / superfície em logs | 5 | 3 | 5 | 4 | 4 | 3 |
| 5. Correção com abstenção | 5 | 4 | 4 | 3 | 3 | 3 |

**Recomendação.**

- **Núcleo: Candidato 1.** Combina o seu interesse original (variar a superfície para evitar decorar), elimina a autoavaliação por usar oráculo de testes, é nativo de ES e se avalia por métricas objetivas. O escopo deve ser cortado de forma agressiva (Python + SQL, poucos conceitos).
- **Plano B, escopo enxuto:** Candidato 3.
- **Plano B, mais "dados" e menos implementação:** Candidato 2.
- **Combinação** 1 + 2 (nota derivada de teste + latência) só se sobrar escopo; o documento do Gemini errou justamente por empilhar hipóteses.

**O que aproveitar do documento do Gemini:** FSRS como baseline, latência como telemetria, LLM como assistente (não como porteiro que bloqueia, conforme o SmartFlash). **O que descartar:** bloqueio por pré-requisito, remoção de todas as notas sem avaliação, tom de "comprovado".

---

## 7. Próximos passos e decisões em aberto

Fase 3 (após a escolha): definir pergunta de pesquisa e objetivos, escopo mínimo, protocolo de avaliação, arquitetura, registro de riscos. Perguntas para decidir:

1. Prefere artefato (Candidato 1), dados (Candidato 2) ou ferramenta enxuta (Candidato 3)?
2. Stack preferida (TypeScript ou Python)?
3. Pode rodar LLM local (GPU/RAM) ou usaria API paga? Há orçamento?
4. A sua instituição exige avaliação com usuários (nº mínimo) ou comitê de ética?
5. Há 5 a 10 colegas disponíveis para um piloto leve?

---

## 8. Referências

**Verificadas nesta sessão (existência/resumo):** [Pan & Rickard 2018](https://doi.org/10.1037/bul0000151); [Cowan et al. 2024](https://doi.org/10.1073/pnas.2311077121); [Brunmair & Richter 2019](https://doi.org/10.1037/bul0000209); [Serrano & Pellicer-Sánchez 2026](https://discovery.ucl.ac.uk/id/eprint/10216384/); [Lindsey et al. 2014](https://doi.org/10.1177/0956797613504302); [Upadhyay et al. 2020](https://arxiv.org/abs/2010.04430); [KARL](https://arxiv.org/abs/2402.12291) (texto completo); [LECTOR](https://arxiv.org/abs/2508.03275); [Memdora](https://arxiv.org/abs/2607.25096); [SmartFlash](https://arxiv.org/abs/2602.14431); [SMART](https://arxiv.org/abs/2406.15352); [SRS-Stories](https://arxiv.org/abs/2512.18362); [Reddy et al. 2016](https://arxiv.org/abs/1602.07032); [DAS3H](https://arxiv.org/abs/1905.06873); [Baillifard et al. 2023](https://arxiv.org/abs/2309.13060); [An et al. 2025](https://arxiv.org/abs/2507.05629) e [2026](https://arxiv.org/abs/2609.27063); [Kortemeyer 2023](https://arxiv.org/abs/2309.09338); [Walsh et al. 2025](https://arxiv.org/abs/2508.04063); [Cong et al. 2026](https://arxiv.org/abs/2605.00200); [Bastani et al. 2025](https://doi.org/10.1073/pnas.2422633122); [Hevner et al. 2004](https://doi.org/10.2307/25148625); [Peffers et al. 2007](https://doi.org/10.2753/mis0742-1222240302); [Wieringa 2014](https://doi.org/10.1007/978-3-662-43839-8); [Sarsa et al. 2022](https://doi.org/10.1145/3501385.3543957); [FIE 2024](https://doi.org/10.1109/fie61694.2024.10893444); [ICER 2019](https://doi.org/10.1145/3291279.3339411); [Matuschak 2020](https://andymatuschak.org/prompts/); [Math Academy / FIRe](https://www.justinmath.com/individualized-spaced-repetition-in-hierarchical-knowledge-structures/); documentação do [Anki](https://docs.ankiweb.net/deck-options.html); [srs-benchmark](https://github.com/open-spaced-repetition/srs-benchmark); [awesome-fsrs](https://github.com/open-spaced-repetition/awesome-fsrs).

**Marcadas †, de memória, não verificadas:** Pyodide e sql.js como execução em WebAssembly; estágios do método DSRM de Peffers; conjunto Mohler de respostas curtas de ciência da computação.

---

## 9. Limitações desta pesquisa

- Busca ampla, mas não sistemática: sem protocolo de revisão sistemática, sem bases pagas e sem Semantic Scholar.
- Quase todos os papers foram lidos só pelo resumo; números citados vêm de resumos, tabelas do benchmark e do texto do KARL.
- Os escores da seção 6 são julgamento meu, não medida.
- "Não encontrei" significa "não encontrei em busca rápida", não "não existe".
