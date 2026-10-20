# Fase 1: Análise e Pesquisa Acadêmica

Data: 2026-10-14

Escopo: avaliar se a ideia de um SRS (tipo Anki) focado em "overfitting visual" faz sentido, com base em pesquisa acadêmica e na pesquisa anterior feita com o Gemini ([TCC em Aprendizagem Adaptativa.md](TCC%20em%20Aprendizagem%20Adaptativa.md)). Nenhum código foi escrito.

**Metodologia e limites.** Busca em arXiv, OpenAlex, Europe PMC, fóruns do Anki e GitHub do FSRS. Para LECTOR, KARL e Memdora li apenas o resumo, não o texto completo. Referências marcadas com † vêm de memória e não foram verificadas. Semantic Scholar bloqueou com erro 429, e não tive acesso a Scopus, ERIC nem Portal CAPES. A busca não é exaustiva.

---

## 1. Veredito

**Faz sentido, com três ressalvas.**

1. **"Overfitting visual" não é termo acadêmico.** O fenômeno existe na literatura com outros nomes (seção 2), mas precisa de definição operacional antes de virar hipótese.
2. **Não achei estudo controlado sobre esse problema em flashcards.** A evidência direta é prática (Matuschak, fóruns do Anki). A evidência experimental é indireta e mista. Isso é uma lacuna, e dá espaço para contribuição.
3. **Variar o cartão pode piorar a retenção.** Pelo estudo de Cowan et al. (2024), a variabilidade ajuda memória de itens, mas pode atrapalhar memória associativa, que é o caso típico de pergunta→resposta.

---

## 2. Mapeamento teórico

| Ideia | Construto acadêmico | Fonte |
|---|---|---|
| Decorar a forma da pergunta, não o conceito | Especificidade de codificação; processamento apropriado à transferência | Tulving & Thomson 1973†; Morris, Bransford & Franks 1977† |
| Benefício do teste não se generaliza | Transferência do efeito de teste | [Pan & Rickard 2018](https://doi.org/10.1037/bul0000151) |
| Variar a apresentação ajuda | Variabilidade de codificação × espaçamento | Glenberg 1979†; [Appleton-Knapp, Bjork & Wickens 2005](https://doi.org/10.1086/432236) |
| Pistas fáceis reduzem o esforço | Hipótese do esforço de recuperação; suporte de pistas empobrecido | Pyc & Rawson 2009 (citado por Matuschak); [Carpenter & DeLosh 2006](https://doi.org/10.3758/bf03193405) |
| Novato usa pistas superficiais | Características superficiais vs. estrutura profunda | Chi, Feltovich & Glaser 1981† |
| Acerto rápido que não prova aprendizado | Fluência enganosa na recuperação | Benjamin, Bjork & Schwartz 1998† |

---

## 3. Evidência a favor e contra

### A favor

- **Meta-análise de Pan & Rickard (2018):** 192 tamanhos de efeito, 122 experimentos, N = 10.382. A transferência do efeito de teste é d = 0,40 [0,31; 0,50]. É **mais fraca para itens estímulo-resposta rearranjados e para materiais não testados**. Após correção de viés de publicação, muitas vezes não resta transferência quando faltam moderadores como congruência de resposta e recuperação elaborada. Em outras palavras, o ganho tende a ficar preso ao formato praticado.
- **Matuschak (2020), ["How to write good prompts"](https://andymatuschak.org/prompts/):** recomenda "discourage pattern matching". Diz que o aluno pode memorizar o formato da pergunta e a resposta sem pensar no conteúdo, e que cloze copiado de texto é especialmente suscetível. Ele também ressalva que a evidência científica "stops well short of exact guidance".
- **Fórum do Anki, [tópico 55947](https://forums.ankiweb.net/t/image-occlusion-and-the-problem-of-excess-context-in-flashcards/55947) (2025):** usuários relatam decorar a ordem das lacunas. Um autor de deck implementou randomização de textos alternativos, e há um pedido de "hide all, guess one" ([issue #3626](https://github.com/ankitects/anki/issues/3626)). Os relatos são anedóticos, e o próprio autor do deck argumenta que o efeito é pequeno e que o RMSE do FSRS já o absorveria.
- **[Memdora](https://arxiv.org/abs/2607.25096) (preprint de 2026, submetido ao IUI 2027):** propõe 17 tipos de interação sobre FSRS-6, ou seja, variar o formato do cartão. Pelo resumo, não há ainda resultado de aprendizagem.

### Contra ou complicadores

- **[Cowan et al. 2024, PNAS](https://doi.org/10.1073/pnas.2311077121):** para memória de item, variabilidade e espaçamento ajudam, e a variabilidade pesa mais em intervalos curtos. Para memória associativa, a repetição foi melhor que a variabilidade, e o benefício do espaçamento só apareceu sem variabilidade.
- **Appleton-Knapp et al. 2005:** mostra interação entre variabilidade e espaçamento. Pelo que lembro, a direção do efeito parece oposta à de Cowan (†, precisa verificar). Se confirmado, a literatura é inconsistente e é preciso testar os dois cenários.
- **Matuschak, propriedade de consistência:** o cartão deve evocar a mesma resposta sempre, senão há interferência. Ele também observa que manter a lista na mesma ordem faz o aluno aprender o "formato visual", e isso ajuda a recordar. A pista visual pode ser muleta ou ajuda, dependendo do caso.

---

## 4. Avaliação da pesquisa do Gemini

O documento tem base útil: o modelo DSR do FSRS, a teoria de Bjork, latência como sinal e LLM como filtro de qualidade. Mas há problemas sérios.

1. **Não menciona overfitting visual.** Ele trata outro problema, então a tese precisa ser reescrita.
2. **Seções 6.2, 6.3 e 7 são texto degenerado** (sinônimos repetidos) e inutilizáveis. Os "[cite: …]" não apontam para nada, e a lista de referências está vazia, só com imagens de fórmulas. Todas as fontes precisam ser refeitas.
3. **LECTOR é evidência fraca.** É um [preprint de um único autor](https://arxiv.org/abs/2508.03275), avaliado em 100 aprendizes simulados por 100 dias. O 90,2% vs. 88,4% é melhoria relativa de 2,0% na taxa de sucesso, e o melhor baseline foi SSP-MMC, não FSRS. O resumo diz que o método trata confusão semântica entre conceitos parecidos. O Gemini descreve o inverso (sobreposição alongaria o intervalo). Isso precisa ser conferido no texto completo.
4. **Fatos do FSRS desatualizados.** O [benchmark aberto](https://github.com/open-spaced-repetition/srs-benchmark) (cerca de 10 mil usuários e 350 milhões de revisões) mostra FSRS-6 com 21 parâmetros, não 17. Já existe FSRS-7, com 34 parâmetros e intervalos fracionários. FSRS-6 tem log loss de 0,346 e AUC de 0,703, contra 0,277 e 0,833 do RWKV-Instant. Modelos neurais com mais atributos, incluindo duração da revisão, superam o FSRS. Isso sustenta o interesse em latência, mas mostra que não é território virgem.
5. **Contradição interna sobre latência.** A seção 3 trata latência alta como "esforço, logo mais ganho de armazenamento". A seção 6.2 usa a mesma latência alta ("right but slow") para **encurtar** o intervalo. É preciso separar latência como proxy da recuperabilidade atual e latência como preditora de ganho. Há também resultados cautelosos: Benjamin et al.† mostram que fluência na prática pode enganar sobre retenção futura, e [Maddox et al. 2018](https://doi.org/10.3758/s13421-018-0843-3) não encontraram que a latência de detecção de repetição modulasse o teste final.
6. **Latência é confundida por outros fatores:** velocidade de digitação, tamanho da resposta, tempo de leitura e distração. Usar tempo até a primeira tecla e normalizar por usuário e por cartão seria o mínimo.
7. **Remover os botões de nota e exigir resposta digitada** cria um corretor de respostas (match exato ou LLM) como nova fonte de erro. E descarta a informação de Hard/Easy que o FSRS usa. O benchmark tem ablação `--two_buttons`, o que sugere que dá para replicar.
8. **Escopo grande demais** para um TCC: latência, filtro de atomicidade por LLM, onboarding por afinidade e bloqueio por pré-requisito. Não dá para atribuir efeitos a nenhum deles. O bloqueio por pré-requisito não tem evidência citada.
9. **Tom:** "comprovado", "incontestável" etc. não cabem em texto acadêmico.

---

## 5. Trabalhos relacionados

| Trabalho | Contribuição | Relevância |
|---|---|---|
| FSRS (Ye et al., KDD 2022 / TKDE 2023) | Modelo DSR e agendador treinável por usuário | Baseline obrigatório; a fórmula de D é heurística ([issue #352](https://github.com/open-spaced-repetition/fsrs4anki/issues/352)) |
| [KARL](https://arxiv.org/abs/2402.12291) (EMNLP 2024) | Agendador que usa o texto do cartão (BERT + DKT); 123 mil logs; avaliação online com 27 usuários | Referência real de agendamento sensível ao conteúdo; avaliação online pequena |
| [DAS3H](https://arxiv.org/abs/1905.06873) (EDM 2019) | Esquecimento com várias habilidades por item | Relaciona item e habilidade |
| [Reddy et al. 2016](https://arxiv.org/abs/1602.07032) (KDD) | Modelo de filas para o sistema Leitner | Fundamento de dinâmica do SRS |
| [Lindsey et al. 2014](https://doi.org/10.1177/0956797613504302) | Revisão personalizada: +16,5% sobre estudo em bloco e +10% sobre espaçamento genérico; semestre em escola | Prova de conceito de personalização |
| [Mettler, Massey & Kellman 2016](https://doi.org/10.1037/xge0000170) | Agendamento adaptativo baseado em tempo de resposta (ARTS) | Antecedente direto do uso de latência (números não conferidos) |
| Pavlik & Anderson 2008†; Settles & Meeder 2016† | ACT-R e HLR | Modelos clássicos |
| [An et al. 2025](https://arxiv.org/abs/2507.05629) | Questões de recuperação geradas por LLM: acerto de 89% vs. 73%, cerca de 60 alunos | Mostra viabilidade, com qualidade variável |
| [An et al. 2026](https://arxiv.org/abs/2609.27063) | Dificuldade rotulada pelo LLM não prediz a dificuldade empírica (ρ ≈ 0,06) | Cuidado ao usar LLM para julgar atomicidade ou dificuldade |
| [SmartFlash](https://arxiv.org/abs/2602.14431) (ISLS 2026) | Alunos querem saídas de IA editáveis e transparentes | Sugere "sugerir", não "bloquear", no filtro por LLM |

---

## 6. Proposta de refinamento

### Definição operacional (rascunho)

Há overfitting visual quando P(acerto) depende da forma de superfície *s* do cartão (layout, posição da lacuna, redação, direção) e não do conceito *c*.

Métrica candidata: **Lacuna de Transferência de Superfície** = acerto no formato original − acerto numa variante do mesmo conceito, com atraso igualado.

Assinatura comportamental a testar: acerto muito rápido no formato original e queda de acerto ou aumento de latência na variante.

### Hipóteses

- **H1:** rotacionar variantes (mesmo agendamento FSRS) reduz a Lacuna de Transferência de Superfície em relação ao cartão fixo, sem perder retenção no formato original.
- **H2:** latência e padrões de erro detectam o overfitting antes do teste de transferência.
- **H3:** um LLM gera variantes que preservam o conceito (validade verificada por humanos).

### Desenho sugerido

- Experimento intra-sujeito, com itens contrabalançados entre cartão fixo e variado.
- Duas a quatro semanas de estudo, seguidas de teste final com formulações inéditas.
- Análise com regressão logística de efeitos mistos e registro de latência.
- Testar memória associativa e memória de item separadamente, por causa de Cowan.

### Restrições

- Os datasets públicos de revlog (o README do benchmark indica registros de revisão, sem texto do cartão) não permitem testar a hipótese. Será preciso coletar dados próprios, mais simulação de aprendiz com componentes específico-da-pista e conceitual.
- Provavelmente é necessária aprovação de comitê de ética para participantes humanos; confirmar na instituição.

### Implicação de arquitetura (alto nível)

Um conceito com várias "realizações de superfície"; um agendador FSRS como baseline (há implementação aberta em Rust, [fsrs-rs](https://github.com/open-spaced-repetition/fsrs-rs)); telemetria de latência; e um harness de simulação e avaliação. O detalhamento fica para a Fase 2.

---

## 7. Decisões em aberto

1. **"Visual"** é layout e posição na tela, redação da pergunta, posição da lacuna em cloze ou imagem? Isso define a variante a gerar.
2. **Domínio:** vocabulário, conceitos de computação, medicina? A literatura é mais forte em verbal.
3. **Escopo:** concentrar em variação de superfície (recomendado) e tratar latência como análise secundária, ou manter o pacote do Gemini?
4. **Coleta com humanos** é viável no prazo, ou o TCC fica em simulação mais estudo-piloto pequeno?
