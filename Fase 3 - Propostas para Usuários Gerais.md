# Fase 3: Propostas para usuários gerais de flashcards e efeito na aprendizagem

Data: 2026-10-14. Continua a [Fase 2](Fase%202%20-%20Refinamento%20do%20Tema.md); o contexto está na [Fase 1](Fase%201%20-%20An%C3%A1lise%20e%20Pesquisa%20Acad%C3%AAmica.md). Nenhum código foi escrito.

**Como ler.** Mesma convenção da Fase 2: † marca o que vem da minha memória e não foi verificado; quase todos os papers foram lidos só pelo resumo; "não encontrei" significa "não encontrei em busca rápida" (arXiv, OpenAlex, Europe PMC, GitHub, AnkiWeb, fóruns e blogs da comunidade). Escores e cálculos de tamanho de amostra são julgamento/cálculo meu, não vêm de fonte.

---

## 0. Resumo executivo

- **A objeção procede.** O oráculo só era necessário no Candidato 1, porque o sistema precisava *saber* se a variante gerada estava correta. Em flashcards gerais, a referência é o verso do cartão (escrito por quem fez o deck) e o comportamento do usuário (acerto/erro, tempo). As propostas abaixo não precisam conhecer a matéria.
- **Mais próximo na literatura** (usuários gerais, conteúdo livre, efeito em aprendizagem): o [KARL](https://arxiv.org/abs/2402.12291) (estudo online pequeno) e o ensaio randomizado de [Upadhyay et al. 2020](https://arxiv.org/abs/2010.04430) (milhares de usuários). Os dois tratam de **agendamento**, a parte mais saturada (o FSRS é aberto e já está no Anki).
- **Lacuna real para usuários gerais: cartões que "não grudam" (leeches) e a qualidade do cartão.**
  - O manual do Anki diz que leeches "take up a lot more of your time" e que reformulá-los bem exige experiência.
  - Numa amostra de 1º ano de medicina, 97,6% dos usuários de Anki usavam cartões prontos ([Nour & Harris 2025](https://doi.org/10.7759/cureus.95674)): o usuário herda cartões que não escreveu e, em geral, não sabe consertá-los.
  - Existem detectores de leech e scripts de IA que reescrevem ou explicam cartões errados. Não achei **avaliação do efeito** de nenhum, nem estudo acadêmico sobre leeches.
- **Como medir efeito na aprendizagem sem grupo de estudo:** (1) offline, em 10 mil coleções públicas (detecção); (2) microexperimento randomizado *dentro do usuário* (cada usuário é o próprio controle), exploratório, com poucos voluntários, inclusive você. Seção 4.
- **Recomendação:** **P1, "Card Doctor"**: detecção precoce, diagnóstico da causa e remediação com aprovação humana. As demais propostas entram como componentes ou planos B (seção 6).

---

## 1. Onde ficava o oráculo e onde ele não é necessário

| Ideia | Precisa saber a resposta certa? | De onde vem a "verdade" |
|---|---|---|
| Variantes verificadas (Fase 2, candidato 1) | Sim (testes executáveis) | Só existe em domínios verificáveis (código, SQL); por isso não generaliza |
| Nota implícita (candidato 2) | Não | Acerto/erro do próprio usuário e tempo |
| Linter de cartões (candidato 3) | Não | A forma do cartão (regras de formulação) |
| Diagnóstico e reparo de cartões-problema (P1) | Não | Histórico de revisão e texto do cartão; o LLM só reformula ou explica o que está no cartão; o usuário aprova |
| Variação de redação (pilar original) | Não, mas exige fidelidade ao cartão | Verso do cartão; checagem por LLM e aprovação humana (risco: alterar o sentido) |
| Correção de resposta digitada (candidato 5) | Parcial | Compara com o verso do cartão |

**Os três pilares originais sem oráculo:**

- *Latência* vira **sinal** para detectar cartões-problema (P1) ou nota implícita (P3). Cuidado: na mesma amostra de Nour & Harris, 56,6% dos usuários relatam fazer multitarefa durante as revisões, o que torna o tempo ruidoso.
- *Guardião de atomicidade* vira **diagnóstico de formulação** (um dos itens da taxonomia do P1) ou linter na importação de decks.
- *Variação de forma* vira **uma ação de remediação a ser testada**, não assumida como boa (a evidência é mista; ver Fase 2, seção 3.4).

---

## 2. Mapa de alavancas para usuários gerais

Resume onde um software poderia mudar a aprendizagem, o que já se sabe e o que falta.

| Alavanca | Evidência encontrada | Já existe | Lacuna |
|---|---|---|---|
| Quando revisar (agendamento) | Upadhyay et al. 2020 (RCT, milhares de usuários): lembram o conteúdo ~67% por mais tempo que com duas heurísticas e têm ~50% mais chance de voltar ao app em 4–7 dias. [Eglington & Pavlik 2020](https://doi.org/10.1038/s41539-020-00074-4) (experimentos): agendamento individualizado recupera mais itens (até ~40% mais, segundo o resumo). [Lindsey et al. 2014](https://doi.org/10.1177/0956797613504302): +10% sobre espaçamento genérico | FSRS aberto no Anki, simulador de carga | Ganho incremental sobre o FSRS é pequeno e difícil de medir. Saturado |
| Hábitos do usuário | [Wissman et al. 2012](https://doi.org/10.1080/09658211.2012.687052) (N = 374): estudantes tendem a não espaçar o suficiente. Nour & Harris 2025: 56,6% fazem multitarefa nas revisões | Agendamento automático | Contexto, não alvo de intervenção |
| Qualidade do cartão | Manual do Anki e [Bjornstad](https://controlaltbackspace.org/leech/): cartões mal formulados viram leeches; consertar exige experiência. 97,6% usam cartões prontos. Não achei estudo controlado do efeito da formulação em flashcards (há literatura de avaliação sobre falhas de redação em questões de múltipla escolha †, não verificada) | Regra de leech, add-ons, reformulação por IA | Detecção tardia, diagnóstico por causa e remediação **sem avaliação** |
| Feedback após o erro | [Wisniewski et al. 2020](https://doi.org/10.3389/fpsyg.2019.03087) (435 estudos, N > 61.000): d = 0,48, mas depende do conteúdo informacional do feedback. [Dunlosky et al. 2013](https://doi.org/10.1177/1529100612453266): interrogação elaborativa e autoexplicação = utilidade moderada | AnkiAIUtils (explicações, mnemônicos, ilustrações por LLM) | Nenhum ensaio randomizado em flashcards |
| Forma da pergunta | [Pan & Rickard 2018](https://doi.org/10.1037/bul0000151): transferência d = 0,40, fraca para pares estímulo-resposta rearranjados. Cowan 2024, Serrano & Pellicer-Sánchez 2026, Brunmair & Richter 2019: evidência mista (Fase 2) | [Memdora](https://arxiv.org/abs/2607.25096) (17 tipos de interação, sem resultado de aprendizagem no resumo) | Variar a forma sem medir aprendizagem |
| Sinais e nota (latência) | Benchmark: LSTM com tempo vs. GRU sem tempo, log loss 0,3332 vs. 0,3328 (Fase 2). Objeções no fórum (tópico 41037) | Pass/Fail Review (add-on), Gnoseed | Sem avaliação publicada de não inferioridade |
| Interferência entre cartões | Manual do Anki (esperar um cartão até aprender o outro). Vocabulário L2: agrupamento semântico tende a prejudicar a aprendizagem inicial (Tinkham 1993; Waring 1997; direção do efeito de memória †); estudo sobre massificação/espaçamento em palavras relacionadas ou não (SSLA 2018). Resumos não lidos | Interference Recorder, AnkiFuzzy, ankiR | Nenhuma intervenção avaliada |
| Carga e adesão | [Reddy et al. 2016](https://arxiv.org/abs/1602.07032): transição de fase na taxa de itens novos. [Gilbert et al. 2023](https://doi.org/10.1007/s40670-023-01826-8) (observacional, N = 130): usuários de Anki pontuaram mais (6,2% a 7,0% nos três cursos; 12,9% na prova abrangente, conforme o resumo), com ressalva de autosseleção | Simulador, Easy Days | Orçamento de tempo (issue #737, "not planned") |

Leitura: **agendamento** é onde há mais evidência de efeito e menos espaço; **qualidade e diagnóstico de cartões** é onde há mais dor relatada e menos avaliação.

---

## 3. O que está mais próximo

### 3.1 Pesquisa com usuários gerais

| Trabalho | Desenho | O que aproveitar |
|---|---|---|
| [KARL](https://arxiv.org/abs/2402.12291) (EMNLP 2024) | 543 usuários nos logs; avaliação online com 27 usuários em 32 sessões de 6 dias; comitê de ética | **Modelo de estudo pequeno e viável**: teste dentro do sujeito, acerto verificado pelo sistema |
| [Upadhyay et al. 2020](https://arxiv.org/abs/2010.04430) | RCT com milhares de usuários de um app de aprendizagem (área de mobilidade) | Mostra a escala de um efeito de agendamento; ensaio desse porte exige empresa ou laboratório |
| Eglington & Pavlik 2020; Lindsey et al. 2014 | Experimentos com agendamento individualizado | Efeitos de agendamento; fora do seu escopo |
| Gilbert et al. 2023 | Coorte observacional; 78 usuários de Anki e 52 não usuários | Associação, não causa. Os autores relatam pouca correlação entre as estatísticas do Anki e o desempenho, o que sugere (inferência minha) que métricas de uso sozinhas não capturam o que importa |

### 3.2 Plataformas e métodos para experimentar

| Recurso | O que é | Observação |
|---|---|---|
| [MoFaCTS](https://github.com/memphis-iis/MoFaCTS) | Sistema web de prática adaptativa e pesquisa (AGPL-3.0; TypeScript/Meteor/Svelte); respostas digitadas, múltipla escolha e voz; exporta dados de interação | Pré-1.0 (alpha), um único mantenedor; usa lições próprias (TDF), não decks do Anki |
| [UpGrade](https://github.com/CarnegieLearningWeb/UpGrade) | Teste A/B e feature flags para EdTech (BSD-3); SDKs JS, Python e Java; amostragem estratificada e fatorial | Dá para reusar, ou imitar com uma tabela local de randomização |
| Ensaios microrandomizados ([Klasnja et al. 2015](https://doi.org/10.1037/hea0000305); [Qian et al. 2022](https://doi.org/10.1037/met0000283)) | Randomização repetida, dentro do usuário, a cada momento de decisão; estima o efeito *proximal* de um componente da intervenção | É o desenho que sustenta o piloto (seção 4.3) |

### 3.3 Produtos e ferramentas da comunidade Anki

| Ferramenta | O que faz | Avaliação do efeito |
|---|---|---|
| Regra padrão de leech | Ao atingir 8 lapsos, marca a nota como leech e suspende o cartão ([manual](https://docs.ankiweb.net/leeches.html)). Um usuário reclama no [fórum](https://forums.ankiweb.net/t/identify-leeches-by-the-total-times-of-pressing-again/42926) que a identificação demora porque o contador sobe no máximo 1 por dia | Nenhuma |
| [Leech Detector](https://ankiweb.net/shared/info/1406469667) (add-on; [post de abr/2026](https://jschoreels.substack.com/p/anki-leech-detection-based-on-actual)) | Detecta leech por desempenho real (ciclos e quedas de desempenho), independente do agendador; status ativo/recuperando/recuperado. Argumento: sob FSRS, com retenção-alvo de 90%, ~10% das revisões falham por construção | Nenhuma |
| [leechkit](https://github.com/rbrownwsws/leechkit) (experimental, MIT) | Marca cartões cuja taxa de falha seria improvável dado o esperado pelo FSRS (cauda binomial); limiar dinâmico; checagem incremental | Nenhuma |
| [Leech Toolkit (kar)](https://ankiweb.net/shared/info/568675395), [Anki-Leech-Manager](https://github.com/SagaSkoyer/Anki-Leech-Manager) | Razão lapsos/revisões; colunas de taxa de falha (LifetimeIFR, RecentIFR) | Nenhuma |
| [anki-leech-doctor](https://github.com/alexanderjfink/anki-leech-doctor) (add-on, achado na Fase 4) | Ranking por lapsos, diagnóstico heurístico, proposta de edição por LLM (modo de falha, justificativa, edições), aplicação com log de reversão | Nenhuma |
| [AnkiAIUtils](https://github.com/thiswillbeyourgithub/AnkiAIUtils) (AGPL; 887 estrelas) | A cada cartão errado, gera com LLM explicações, mnemônicos, ilustrações e reformulações; altera as notas no lugar (funciona em todos os clientes via sincronização, segundo o README); log para reverter | Relato do autor ("testado na faculdade de medicina"); sem avaliação controlada |
| [Interference Recorder](https://ankiweb.net/shared/info/1812738345), [AnkiFuzzy](https://ankiweb.net/shared/info/1665515487), [ankiR](https://www.rdocumentation.org/packages/ankiR/versions/0.6.0/topics/anki_interference_analysis) | Pares confundíveis por falhas próximas no tempo (grafo com decaimento) e/ou similaridade de texto | Nenhuma |

### 3.4 O que não encontrei

- Estudo controlado do efeito de remediar leeches (por humano ou por LLM).
- Comparação de regras de detecção de leech pelo custo futuro em muitas coleções. No OpenAlex, "leech" com "spaced repetition" retorna só biologia, e "leeches" com "flashcards" retorna zero (o termo é jargão da comunidade; a literatura pode usar "itens difíceis").
- Ensaio randomizado de explicações ou mnemônicos de LLM em flashcards.
- Ferramenta de experimentos pessoais (poucos usuários) para repetição espaçada.

A área está ativa (Leech Detector é de abr/2026), então a contribuição não está em "mais uma regra de detecção", e sim em **avaliação comparativa** e em **diagnóstico com remediação avaliada**.

---

## 4. Como medir efeito na aprendizagem sem grupo de estudo

### 4.1 O que "aprendizagem" quer dizer aqui

Definir antes de coletar:

- **Proximal:** acerto (0/1) na próxima revisão; lapsos por 100 revisões.
- **Eficiência:** minutos de revisão por cartão que chega a um intervalo-alvo; carga diária.
- **Retenção tardia (opcional):** teste digitado, em amostra de cartões, depois de N dias.
- **Fora do alcance:** desempenho em provas, compreensão, transferência.

### 4.2 Escada de evidência

| Nível | O que mostra | Dá para fazer? |
|---|---|---|
| 1. Previsão offline em logs públicos | A regra detecta o que se propõe a detectar; economia potencial de revisões | Sim |
| 2. Microexperimento intra-usuário | Efeito proximal da intervenção, com intervalo de confiança | Sim, exploratório |
| 3. Teste tardio controlado | Retenção depois de dias | Só em amostra pequena, opcional |
| 4. RCT com centenas de usuários | Efeito sobre aprendizagem | Não (escala de Upadhyay et al.) |

### 4.3 Desenho do microexperimento (intra-usuário)

- **Randomizar por nota**, não por cartão, para evitar contaminação entre cartões irmãos; estratificar por número de lapsos e dificuldade.
- **Controle por lista de espera:** o cartão do braço controle recebe a remediação depois, não nunca. Ético e útil ao usuário.
- **Desfecho ajustado:** acerto na próxima revisão, ajustado por intervalo decorrido e retrievability prevista pelo FSRS (senão o efeito se confunde com intervalos diferentes entre braços). Regressão logística mista (efeitos aleatórios por usuário e por nota) com intervalos de confiança.
- **Pré-registro** das hipóteses, desfechos e análise antes de olhar os dados (OSF †).
- **Tamanho (cálculo meu; α = 0,05; poder 80%; sem agrupamento):** cerca de 140 cartões por braço para detectar queda de 35% para 20% na taxa de falha; cerca de 1.100 eventos por braço para detectar +5 pontos percentuais (75% para 80%) no acerto pós-lapso. Efeitos pequenos exigem muito mais dados, então o piloto é **exploratório**: estima o efeito e a incerteza, não confirma.
- **Ameaças:** autorrelato do acerto; contaminação por cartões semelhantes; efeito de novidade; multitarefa; LLM errando; privacidade (o texto do cartão vai ao provedor do LLM; usar modelo local ou consentimento explícito).

### 4.4 O que dá para afirmar

| Pode | Não pode |
|---|---|
| "A regra X sinaliza cartões-problema N revisões antes da regra padrão, com taxa de falsos positivos Y" (offline) | "Melhora o desempenho em provas" |
| "Em K usuários, a remediação teve efeito estimado Z (IC ...) sobre a taxa de falha dos cartões" (exploratório) | "Vale para qualquer usuário ou matéria" |
| "O diagnóstico concorda com humanos em κ = ..." | "Melhora a retenção de longo prazo" |

---

## 5. Propostas

Como cada uma afetaria a aprendizagem:

| Proposta | Mecanismo | Efeito esperado | Como medir |
|---|---|---|---|
| P1 Card Doctor | Menos tempo em cartões que não evoluem; cartões corrigidos passam a ser aprendidos | Menos lapsos e minutos por cartão-problema; mais tempo para material novo | Offline (RQ1) e intra-usuário (RQ2) |
| P2 Explicação pós-erro | Feedback elaborado depois do erro | Maior acerto na próxima revisão | Microrandomização por lapso |
| P3 Nota implícita | Menos fricção e sinal de esforço | Previsão igual ou melhor com menos esforço; efeito em aprendizagem só indireto | Não inferioridade offline |
| P4 Laboratório pessoal | Testar qualquer intervenção no próprio uso | Depende da intervenção testada | Randomização intra-usuário |
| P5 Interferência | Menos confusão entre itens parecidos | Menos lapsos em pares confundíveis | Offline (co-lapsos) e piloto |

### P1. Card Doctor: detecção precoce e remediação de cartões-problema (recomendada)

- **Problema.** Em coleções reais, uma minoria de cartões não evolui e consome tempo desproporcional. A regra padrão dispara tarde (8 lapsos; quando dispara, o usuário já passou por várias dezenas de revisões "em círculos", segundo Bjornstad) e, sob FSRS, lapsos ocasionais são esperados. Quem usa decks prontos não escreveu os cartões e não sabe diagnosticar. Na fonte primária do SuperMemo ([Wozniak](https://super-memory.com/articles/theory.htm), verificada na Fase 4): uma tabela de medições reais (sem detalhes de amostra) mostra itens com 3 ou mais lapsos como 13% dos itens e 27% da carga; o "até 300%" de ganho ao eliminar os 10% mais difíceis é **simulação**, e o "50% das repetições para 2,5% do material" refere-se ao material de intervalo curto, não a leeches. **Medir esse custo em 10 mil coleções públicas seria, por si só, uma contribuição descritiva.**
- **Ideia (três etapas, sem oráculo).**
  1. **Detectar cedo** com o histórico (acertos/erros, intervalos, retrievability prevista, tempo).
  2. **Diagnosticar a causa provável** com a taxonomia abaixo (texto do cartão, cartões semelhantes por embeddings e estatísticas).
  3. **Aplicar com aprovação humana:** mostrar a mudança como diff, aplicar só depois de aceita, permitir desfazer. Alinha com o achado do SmartFlash (usuários querem saídas editáveis).

| Causa provável | Sinais | Ação sugerida | Base |
|---|---|---|---|
| Formulação ruim (ambígua, várias informações, enumeração) | Texto do cartão; falhas desde cedo | Reescrever ou dividir | Manual do Anki; Bjornstad (passos 1 e 3) |
| Falta de contexto ou compreensão | Termos não explicados; falhas desde a primeira revisão | Cartão de contexto antes do original | Bjornstad (passo 2); regra 1 de Wozniak ("não aprenda o que não entende", [20 regras](https://super-memory.com/articles/20rules.htm)) |
| Interferência com cartão semelhante | Cartão parecido com falhas próximas no tempo | Cartão de contraste; escalonar a introdução | Manual do Anki ("disappoint"/"disappear"); Bjornstad (passo 2) |
| Associação arbitrária | Cartão claro e atômico que mesmo assim falha | Mnemônico, como último recurso | Bjornstad (passo 6); Dunlosky 2013 (mnemônico de palavra-chave: utilidade baixa, limitado a certos materiais e a prazos curtos) |
| Pouco importante | Usuário indica; fora do objetivo de estudo | Adiar ou apagar | Bjornstad (passos 4 e 5); manual do Anki |

- **Perguntas de pesquisa e hipóteses.**
  - **RQ1 (offline, anki-revlogs-10k):** um detector que usa só os k primeiros eventos antecipa e identifica melhor os cartões que depois consomem mais tempo do que a regra padrão?
    - Detectores comparados: (a) regra do Anki com limiares 8 e menores; (b) razão lapsos/revisões; (c) excesso de falhas sobre o esperado (cauda binomial, como no leechkit); (d) ciclos e quedas de desempenho (Leech Detector); (e) classificador treinado nos k primeiros eventos.
    - Métricas: AUC e precisão-recall; antecedência (revisões e minutos antes da regra padrão); falsos positivos (cartões que "se curam").
    - Rótulo de "problemático" fixado **antes**, com análise de sensibilidade (o post do Leech Detector lista quatro definições possíveis de leech).
    - **Ameaça central: censura.** O usuário age sobre leeches (suspende, edita, apaga), então o futuro do cartão é truncado. Tratar com análise de sobrevivência ou rótulos só até a censura; reportar a economia como **limite superior potencial**, não como efeito.
  - **RQ2 (piloto intra-usuário, exploratório):** entre cartões sinalizados, a remediação sugerida e aceita "agora" reduz lapsos e tempo nas revisões seguintes em relação a remediar "depois" (lista de espera)? Desenho da seção 4.3; desfechos: lapsos por 10 revisões, minutos, fração que chega a um intervalo-alvo sem novo lapso.
  - **RQ3 (qualidade):** o diagnóstico e a ação sugerida concordam com 2 avaliadores humanos (κ de Cohen) acima de um baseline de prompt único? Reportar também a taxa de sugestões aceitas, editadas e rejeitadas e a taxa de sugestões com erro factual.
  - *Extensão opcional:* aplicar o linter do candidato 3 a decks prontos na importação e testar se o escore prediz virar leech (exige coleções com texto e histórico).
- **Efeito esperado na aprendizagem.** Menos tempo em cartões que não evoluem (eficiência); mais chance de aprender de fato esses itens (se a remediação funcionar); mais tempo para material novo. **Riscos:** reescrever errado, apagar algo importante, "terceirizar o esforço" ([Bastani et al. 2025](https://doi.org/10.1073/pnas.2422633122)). Mitigação: aprovação humana, ancorar o LLM no texto do cartão, log e reversão.
- **Contribuição de engenharia de software.** Requisitos e taxonomia; arquitetura com aprovação humana e reversão; harness de reprodução offline com split temporal; testes do pipeline; privacidade por projeto (modo local); avaliação reprodutível. Metodologia: Design Science Research (Fase 2).
- **Reuso.** py-fsrs ou fsrs-rs para o estado FSRS; srs-benchmark para dados, split e métricas; leechkit e Leech Detector como *baselines* de detecção (conferir licenças); API de add-ons do Anki † e AnkiConnect † para integração.
- **Escopo mínimo.** (1) Pipeline do RQ1 em Python, sem interface. (2) Módulo de diagnóstico: taxonomia, prompt, saída estruturada com justificativa. (3) Ferramenta (CLI primeiro, add-on mínimo depois) que lista cartões-problema, mostra a sugestão em diff e aplica após aprovação. (4) Registro de randomização e notebook de análise do piloto.
- **Prior art e novidade.** Ver seção 3.3. Detecção, reformulação por IA e interferência existem como ferramentas **sem avaliação**; diagnóstico por causa com remediação avaliada não encontrei. **Atualização (Fase 4):** existe o add-on [anki-leech-doctor](https://github.com/alexanderjfink/anki-leech-doctor), com a mesma ideia e sem avaliação. Novidade: média, concentrada na avaliação (não na ferramenta); risco: médio.
- **Riscos.** Definição de "problemático" arbitrária (mitigar com várias definições); poucos leeches no piloto (limiar de sinalização mais baixo, voluntários com coleções grandes, incluir a sua); LLM errando; privacidade; o dataset público não tem texto, então RQ2 e RQ3 dependem de coleções reais (a sua e a de voluntários); contaminação por cartões semelhantes.

### P2. Explicação pós-erro por LLM, avaliada por microrandomização

- **Problema.** Ao errar, o Anki mostra só o verso. Feedback elaborado ajuda em média (d = 0,48, dependente do conteúdo, Wisniewski et al. 2020), e o AnkiAIUtils já gera explicações, sem avaliação controlada.
- **Ideia.** A cada lapso, com probabilidade 0,5 (por nota), mostrar uma explicação curta gerada a partir do texto do cartão (sem informação externa, com "não sei" permitido); no outro braço, nada. A explicação vem **depois** da tentativa de recordação e nunca a substitui (cautela de Bastani et al. 2025).
- **Tese (exploratória).** O efeito proximal da explicação sobre o acerto na próxima revisão é positivo e compensa o tempo extra.
- **Evidência e lacuna.** Não achei RCT de explicações de LLM em flashcards. Relacionado: ["Effects of elaborate feedback during practice tests: Costs and benefits of retrieval prompts"](https://doi.org/10.1037/xap0000212) (2019; resumo não lido, o título já sugere custos e benefícios).
- **Poder.** Cerca de 1.100 eventos por braço para detectar +5 pontos percentuais (seção 4.3). Viável só com usuários pesados ou vários usuários; caso contrário, intervalo de confiança largo.
- **Riscos.** Alucinação; efeito pequeno; tempo extra; efeito de novidade.
- **Escopo.** Pequeno. É um caso particular da remediação do P1 e pode ser o primeiro braço do piloto.

### P3. Nota implícita (correção + latência), avaliação offline

- **Problema.** Autoavaliação é subjetiva e pesada; "Hard misuse" está documentado; já há add-on e app que derivam a nota do tempo, sem avaliação publicada.
- **Tese.** Uma nota inferida de acerto/erro e latência normalizada por usuário e cartão é **não inferior** às 4 notas manuais na previsão da próxima recordação (detalhes na Fase 2, candidato 2).
- **Para usuários gerais.** Remove fricção e erro de uso dos botões. Ameaças: `duration` mistura recordação, leitura e pausas (teto de 60 s); 56,6% de multitarefa relatada (Nour & Harris); no benchmark, o tempo de resposta quase não muda o log loss.
- **Efeito na aprendizagem.** Só indireto (se a previsão melhorar). Novidade: média. Risco: baixo para implementar, resultado pode ser nulo.

### P4. Laboratório pessoal de microexperimentos (plataforma)

- **Ideia.** Em vez de provar *uma* intervenção, entregar método e infraestrutura para o usuário testar intervenções no próprio uso: randomização por nota ou por evento, registro e análise com intervalo de confiança. Intervenções plugáveis: explicação pós-erro (P2), reformulação, digitar vs. só virar, entre outras. Validação por simulação de poder e por um controle positivo (intervenção de efeito conhecido).
- **Prior art.** UpGrade e MoFaCTS (infraestrutura), ensaios microrandomizados (método). Não achei ferramenta de experimento pessoal para repetição espaçada.
- **Riscos.** Vira infraestrutura sem tese; usuários gerais raramente querem "rodar experimentos"; poucos usuários não detectam efeitos pequenos.
- **Sugestão.** Tratar como **componente** do P1/P2 (randomização e log), não como tese isolada.

### P5. Interferência: pares confundíveis

- **Ideia.** Detectar pares de cartões semelhantes (embeddings do texto) com falhas próximas no tempo e aplicar as ações do manual do Anki: cartão de contraste ou escalonar a introdução. Bjornstad relata que adicionar um cartão que distingue os dois pode facilitar os três.
- **Avaliação.** Offline no dataset do KARL (tem texto e acerto verificado; domínio de trivia): a similaridade entre cartões prediz falhas conjuntas? O KARL usa similaridade para *melhorar* a previsão, então o sinal (facilita ou interfere) é uma pergunta empírica, não uma premissa.
- **Riscos.** Texto + logs só no KARL (trivia) ou em coleções reais; difícil isolar causa; ferramentas heurísticas já existem.
- **Sugestão.** Entra como **um dos diagnósticos** do P1.

### Outras ideias, não priorizadas

| Ideia | Por que não |
|---|---|
| Fadiga de sessão e efeito de ordem em logs | Análise descritiva interessante, sem artefato de software claro |
| Governança de carga/backlog | Reddy et al. 2016 e a issue #737 mostram a dor, mas o Anki já tem simulador e Easy Days |
| Correção digitada com abstenção (candidato 5) | Útil, mas é componente; já descrito na Fase 2 |
| Geração de cartões por IA | Saturado; e, com 97,6% usando cartões prontos, o gargalo é a qualidade dos cartões existentes |
| Atributos extras no agendador (irmãos, hierarquia, texto) | O RWKV-Instant do benchmark mostra espaço (log loss 0,277 vs. 0,346 do FSRS-6), mas é projeto de ML pesado |

---

## 6. Comparação e recomendação

Escalas de 1 a 5, julgamento meu. Risco: menor é melhor. Escopo: menor = mais enxuto.

| Proposta | Usuários gerais | Efeito mensurável | Avaliável sem grupo grande | Novidade | Risco | Escopo |
|---|---|---|---|---|---|---|
| P1 Card Doctor | 5 | 4 | 4 | 4 | 3 | 3 |
| P2 Explicação pós-erro | 5 | 4 | 3 | 3 | 2 | 2 |
| P3 Nota implícita | 4 | 2 | 5 | 3 | 2 | 3 |
| P4 Laboratório pessoal | 4 | 3 | 3 | 4 | 4 | 4 |
| P5 Interferência | 4 | 3 | 3 | 3 | 3 | 3 |

**Recomendação.**

- **Núcleo: P1.** É geral (qualquer deck, qualquer matéria), não precisa de oráculo, tem uma camada avaliável sem ninguém (RQ1), uma camada exploratória com poucos voluntários (RQ2) e uma dor documentada pelo próprio manual do Anki.
- **Corte agressivo para não repetir o erro de empilhar hipóteses:** a tese é uma só ("detectar cedo e remediar cartões-problema reduz o custo de revisão"). As ações de remediação são opções, não hipóteses separadas; o RQ2 compara "remediar agora" com "remediar depois", não a ação A com a B (isso fica como trabalho futuro).
- **Como as outras entram:** P2 é uma das ações de remediação (e pode ser o primeiro braço do piloto); P3 fornece a latência como *feature* do detector (testada no RQ1, não assumida); P5 é um dos diagnósticos; P4 se reduz ao mínimo (randomização e log).
- **Plano B, sem voluntários:** RQ1 (offline) + RQ3 (rótulos humanos sobre a sua coleção ou sobre decks públicos) + RQ2 como estudo de caso na sua própria coleção (N de 1), apresentado como viabilidade.
- **Plano C, sem Anki próprio nem voluntários:** P3, só com dados públicos.

---

## 7. Decisões em aberto

Como escolher:

| Se... | Então |
|---|---|
| Você (ou colegas) usa Anki com milhares de cartões e tolera ceder o texto dos cartões | P1 completo (RQ1 + RQ2 + RQ3) |
| Prefere nada com pessoas | P1 só com RQ1 (+ RQ3 em decks públicos) ou P3 |
| Quer o menor escopo de implementação | P2, com o piloto em poucos usuários |

Perguntas:

1. Você usa Anki hoje? Quantos cartões e quantos leeches (ou cartões com muitos lapsos) tem na coleção?
2. Há 3 a 10 colegas que usem Anki e aceitariam participar, com consentimento?
3. Integração: começar por uma ferramenta externa que lê a coleção (CLI) e só depois um add-on mínimo, ou direto add-on?
4. LLM local (GPU/RAM disponível) ou API paga? Há orçamento? (privacidade: o texto dos cartões iria ao provedor)
5. Stack: Python (alinha com FSRS, benchmark e add-ons do Anki) ou TypeScript?
6. A instituição exige número mínimo de usuários ou comitê de ética?

---

## 8. Referências

**Verificadas nesta sessão (existência e resumo ou página):**

- Pesquisa: [KARL](https://arxiv.org/abs/2402.12291); [Upadhyay et al. 2020](https://arxiv.org/abs/2010.04430); [Eglington & Pavlik 2020](https://doi.org/10.1038/s41539-020-00074-4); [Lindsey et al. 2014](https://doi.org/10.1177/0956797613504302); [Wissman, Rawson & Pyc 2012](https://doi.org/10.1080/09658211.2012.687052); [Nour & Harris 2025](https://doi.org/10.7759/cureus.95674); [Gilbert et al. 2023](https://doi.org/10.1007/s40670-023-01826-8); [Wisniewski, Zierer & Hattie 2020](https://doi.org/10.3389/fpsyg.2019.03087); [Dunlosky et al. 2013](https://doi.org/10.1177/1529100612453266); [Klasnja et al. 2015](https://doi.org/10.1037/hea0000305); [Qian et al. 2022](https://doi.org/10.1037/met0000283); [Bastani et al. 2025](https://doi.org/10.1073/pnas.2422633122); [Reddy et al. 2016](https://arxiv.org/abs/1602.07032); [Pan & Rickard 2018](https://doi.org/10.1037/bul0000151); [Memdora](https://arxiv.org/abs/2607.25096); [SmartFlash](https://arxiv.org/abs/2602.14431); [Effects of elaborate feedback during practice tests (2019)](https://doi.org/10.1037/xap0000212) (só título e DOI).
- Vocabulário L2 e interferência (existência no OpenAlex; resumos não lidos): Tinkham 1993, "The effect of semantic clustering on the learning of second language vocabulary" ([doi](https://doi.org/10.1016/0346-251x(93)90027-e)); Waring 1997, "The effects of semantic and thematic clustering on the learning of second language vocabulary" ([doi](https://doi.org/10.1191/026765897672376469)); "Effects of massing and spacing on the learning of semantically related and unrelated words", SSLA 2018 ([doi](https://doi.org/10.1017/s0272263118000219)).
- Comunidade e ferramentas: [manual do Anki: Leeches](https://docs.ankiweb.net/leeches.html); [Bjornstad, "Dealing with Leeches"](https://controlaltbackspace.org/leech/); [Schoreels, "Leech Detection based on Actual Performance"](https://jschoreels.substack.com/p/anki-leech-detection-based-on-actual); [fórum 42926](https://forums.ankiweb.net/t/identify-leeches-by-the-total-times-of-pressing-again/42926); [Leech Detector](https://ankiweb.net/shared/info/1406469667); [leechkit](https://github.com/rbrownwsws/leechkit); [Leech Toolkit (kar)](https://ankiweb.net/shared/info/568675395); [Anki-Leech-Manager](https://github.com/SagaSkoyer/Anki-Leech-Manager); [AnkiAIUtils](https://github.com/thiswillbeyourgithub/AnkiAIUtils); [Interference Recorder](https://ankiweb.net/shared/info/1812738345); [AnkiFuzzy](https://github.com/cjdduarte/AnkiFuzzy); [ankiR](https://www.rdocumentation.org/packages/ankiR/versions/0.6.0/topics/anki_interference_analysis); [MoFaCTS](https://github.com/memphis-iis/MoFaCTS); [UpGrade](https://github.com/CarnegieLearningWeb/UpGrade); [20 regras de Wozniak](https://super-memory.com/articles/20rules.htm).
- Já verificadas na Fase 2 e reutilizadas aqui: Cowan et al. 2024; Brunmair & Richter 2019; Serrano & Pellicer-Sánchez 2026; benchmark e números do FSRS-6 e RWKV-Instant; tópicos 41037 e 67575 do fórum; issue #737.

**Marcadas †, de memória, não verificadas:** pré-registro no OSF; API de add-ons do Anki e AnkiConnect; literatura de avaliação sobre falhas de redação de questões de múltipla escolha; direção do efeito do agrupamento semântico em Tinkham 1993 e Waring 1997.

---

## 9. Limitações desta pesquisa

- Busca ampla, mas não sistemática; sem bases pagas; Semantic Scholar bloqueou.
- Quase tudo foi lido só pelo resumo ou por trechos de página. Ferramentas da comunidade foram descritas a partir de páginas de listagem e READMEs; o comportamento exato não foi testado e as licenças dos add-ons não foram conferidas.
- Os números do SuperMemo (tabela por número de lapsos, 300%, 50% em 2,5%) foram conferidos na fonte primária na Fase 4: vêm de medições sem detalhes de amostra e de simulação. Eu não medi a prevalência de leeches nos logs públicos.
- Os cálculos de tamanho de amostra são aproximações simples (normal, sem agrupamento); com medidas repetidas por usuário e covariáveis, o poder real muda.
- Os escores da seção 6 são julgamento meu.
- "Não encontrei" significa "não encontrei em busca rápida", não "não existe". A ausência de literatura sobre leeches pode ser efeito do jargão.
