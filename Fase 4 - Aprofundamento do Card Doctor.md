# Fase 4: Aprofundamento do Card Doctor (P1)

Data: 2026-10-14. Continua a [Fase 3](Fase%203%20-%20Propostas%20para%20Usu%C3%A1rios%20Gerais.md); contexto na [Fase 2](Fase%202%20-%20Refinamento%20do%20Tema.md) e na [Fase 1](Fase%201%20-%20An%C3%A1lise%20e%20Pesquisa%20Acad%C3%AAmica.md). Nenhum código foi escrito. Este documento **não decide o tema**: serve para entender a P1 por dentro e testar se ela se sustenta.

**Como ler.** † marca o que vem da minha memória e não foi verificado; "não encontrei" significa "não encontrei em busca rápida". A **seção 3 é uma busca deliberadamente enviesada** (fontes que sustentam a ideia, como você autorizou) e a **seção 4 é o contrapeso**. Dados de GitHub e AnkiWeb refletem as páginas em 2026-10-14. Cálculos e escores são meus.

---

## 0. Respostas diretas

| Pergunta | Resposta curta |
|---|---|
| "Ele seria um detector de cartões que não grudam e que age sobre isso?" | Quase. É um ciclo de 4 etapas: detectar, diagnosticar, propor a ação, medir se funcionou. "Não gruda" deve significar **não evolui com a prática** (não "é difícil"), e a ação é **assistida**: você aprova. |
| "É uma boa opção?" | Sim para uma prova de conceito, **desde que a tese seja sobre avaliar, não sobre construir a ferramenta** (seções 5 e 8). Riscos principais: poder estatístico baixo no piloto e um mercado que se mexe rápido. |
| "É inovador?" | **Como ferramenta, não.** Já existem detectores, scripts de IA e, descoberta desta rodada, um add-on chamado Leech Doctor, com a mesma ideia, publicado há poucos dias. **Como estudo, há espaço:** não achei avaliação comparativa de detectores nem avaliação do efeito de remediar. Para um TCC, inovação incremental com avaliação honesta basta. |
| "Como mediríamos?" | Quatro camadas (seção 6): detecção offline em dados públicos; diagnóstico por concordância humana; efeito em piloto dentro de cada usuário; custo-benefício. |
| "Qual seria a tese?" | Seção 7. Em uma frase: dá para detectar mais cedo e com menos falsos positivos que a regra de 8 lapsos, e remediar conforme a causa reduz falhas e tempo depois (esta segunda parte como estudo exploratório). |
| "Os 3 colegas ajudariam?" | Sim, em quatro coisas (seção 6.6), mas **não são necessários** para a parte offline nem para a validade do teste dentro de cada pessoa. |
| "Uma PoC autoral simples serve?" | Sim. Defina a PoC como **banco de provas** (detector + diagnóstico + registro, somente leitura) e coloque o peso na avaliação (seção 5.4). |

**Atualização da Fase 3.** Lá listei detectores e scripts de IA, mas não conhecia o add-on que junta as duas coisas, com o mesmo nome que eu dei à proposta: [anki-leech-doctor](https://github.com/alexanderjfink/anki-leech-doctor). Isso reduz a novidade que atribuí à P1 (de "média-alta" para "média, concentrada na avaliação"). A falta de **avaliação** continua valendo. Detalhes e as demais correções na seção 5.3.

---

## 1. O que o Card Doctor é e o que não é

### 1.1 "Não gruda" como definição operacional

- A regra do Anki chama de leech o cartão que atinge 8 lapsos ([manual](https://docs.ankiweb.net/leeches.html)). Mas lapsos acontecem por construção: com retenção-alvo de 90%, cerca de 10% das revisões falham ([Schoreels 2026](https://jschoreels.substack.com/p/anki-leech-detection-based-on-actual)).
- Definição proposta: **cartão que não evolui**, isto é, apesar de revisões repetidas a taxa de acerto fica abaixo do esperado e o intervalo (ou a estabilidade) não cresce.
- Conceito acadêmico análogo: ***wheel spinning***, o aluno que não domina uma habilidade apesar de muita prática ([Beck & Gong 2013](https://doi.org/10.1007/978-3-642-39112-5_44)). Aqui, a unidade é o par usuário-cartão.
- **Dificuldade não é o problema.** Dificuldades podem ser desejáveis (Bjork & Bjork 2011, capítulo sem DOI), e tentativas de recordação que falham, seguidas de feedback, aumentam a aprendizagem posterior ([Kornell et al. 2009](https://doi.org/10.1037/a0015729)). O alvo é a dificuldade **improdutiva** (formulação minha): a que não produz progresso.

### 1.2 O ciclo

1. **Detectar** o cartão que não evolui, de preferência cedo.
2. **Diagnosticar** a causa provável (formulação, falta de contexto, interferência, associação arbitrária, pouco importante).
3. **Agir** com aprovação humana (reescrever, dividir, acrescentar cartão de contexto ou de contraste, mnemônico, adiar, apagar).
4. **Medir** se funcionou (o cartão voltou a evoluir? o custo caiu?).

A etapa 4 é a que falta nas ferramentas existentes (seção 5).

### 1.3 O que não é

Não é agendador (usa o FSRS como está), não gera cartões do zero, não decide sozinho e não é tutor.

### 1.4 "Quando" versus "o quê"

O FSRS adapta **quando** revisar. O Card Doctor adapta **o quê** é revisado. E o FSRS também não funciona como detector de cartões-problema: segundo o autor do algoritmo, a dificuldade do FSRS é um valor relativo (em alguns usuários quase todos os cartões têm dificuldade 100%) e ele recomendava, naquele momento, manter a detecção por lapsos ([fórum, tópico 40740](https://forums.ankiweb.net/t/using-fsrs-parameters-to-identify-leech-cards/40740)).

---

## 2. Como funcionaria na prática

### 2.1 Fluxo do usuário

1. Você estuda normalmente no Anki.
2. Ao abrir a ferramenta, ela lista **cartões sob suspeita**, ordenados por evidência, com um motivo curto (por exemplo, "5 falhas em 6 revisões; esperado: menos de 1").
3. Para cada cartão ela mostra um dossiê: texto, estatísticas, cartões parecidos com falhas próximas no tempo, diagnóstico (causa e confiança) e ações sugeridas com rascunho.
4. Você aceita, edita ou rejeita. Só então algo é alterado, com cópia de segurança e reversão.
5. Ela acompanha o cartão depois ("curou?") e registra tudo. Esse registro é o dado da avaliação.

### 2.2 Pipeline técnico

| Etapa | Entrada | Saída | Observação |
|---|---|---|---|
| Ingestão | Cópia somente leitura da coleção | Tabelas de cartões, notas e revisões | Começar sem escrever na coleção |
| Detecção | Histórico de revisão por cartão | Escore e evidência por cartão | Vários detectores em paralelo (seção 6.2) |
| Diagnóstico | Texto do cartão, estatísticas, vizinhos por similaridade | Causa, justificativa, confiança, ação, rascunho (saída estruturada) | Heurísticas + LLM; com **abstenção** ("não sei") |
| Aprovação | Rascunho | Decisão (aceitar, editar, rejeitar) | Humano decide |
| Aplicação | Decisão | Diff aplicado, log, reversão | Fase opcional da PoC |
| Acompanhamento | Revisões posteriores | "Evoluiu?", custo depois | Alimenta a avaliação |

### 2.3 Exemplos ilustrativos (inventados, não são dados reais)

| Cartão | Sinais | Diagnóstico provável | Ação sugerida |
|---|---|---|---|
| "Quais são os 7 princípios do manifesto X?" | 6 falhas em 9 revisões; resposta com 7 itens | Enumeração (várias informações num cartão) | Dividir ou converter em cloze por item |
| "Qual a diferença entre TCP e UDP?" e "O que é UDP?" | Falhas em dias próximos nos dois | Interferência, falta de contraste | Cartão de contraste ("qual dos dois garante entrega?"); escalonar a introdução |
| "Qual o código HTTP de redirecionamento permanente?" (301) | Cartão claro e atômico que falha sempre | Associação arbitrária | Âncora ou mnemônico; adiar ou apagar se for pouco importante |

### 2.4 Onde estão os dados no Anki (verificado nesta rodada)

| Dado | Onde | Fonte |
|---|---|---|
| Lapsos e revisões por cartão | `card.lapses`, `card.reps`; busca `prop:lapses>3` | [`cards.py`](https://github.com/ankitects/anki/blob/main/pylib/anki/cards.py), [busca](https://docs.ankiweb.net/searching.html) |
| Estado FSRS (estabilidade, dificuldade), retenção-alvo | `card.memory_state`, `card.desired_retention`; buscas `prop:s`, `prop:d`, `prop:r` (Anki 23.10+ com FSRS) | idem |
| Texto | `card.note()` (campos), `card.question()` e `card.answer()` | `cards.py` |
| Histórico de revisões | Tabela `revlog` do banco † | Não verifiquei o esquema nesta rodada |
| Integração | Add-on em Python †, AnkiConnect † ou leitura da cópia de `collection.anki2` (o [leechkit](https://github.com/rbrownwsws/leechkit) faz isto e avisa para fechar o Anki e fazer backup) | README do leechkit |

Notas: o [anki-for-claude](https://github.com/MichaelPrutkow/anki-for-claude) lê a dificuldade FSRS do histórico porque o AnkiConnect não expõe o estado FSRS. O código do Anki é AGPL-3 (cabeçalho de `cards.py`); se a PoC importar a biblioteca, conferir as implicações †.

---

## 3. Fontes de apoio (busca enviesada, por afirmação)

Cada linha é uma afirmação que a justificativa do TCC precisaria sustentar, com as fontes que a corroboram e o limite de cada uma.

| Afirmação | Fontes que corroboram | Força e limite |
|---|---|---|
| **A1.** Uma minoria de cartões consome parcela desproporcional do tempo | Wozniak, [teoria da repetição espaçada](https://super-memory.com/articles/theory.htm) (fonte primária): numa tabela de "medições reais" por número de lapsos, itens com 5 ou mais lapsos eram 5% dos itens e 12% da carga; com 3 ou mais lapsos, 13% dos itens e 27% da carga. Manual do Anki: leeches "take up a lot more of your time" | Média. O texto não dá detalhes da amostra (parece um único processo de aprendizagem) e é do SuperMemo, não do Anki. O "300%" do mesmo texto é **simulação** (eliminar os 10% mais difíceis); o "50% das repetições para 2,5% do material" refere-se ao material de intervalo curto, não a leeches |
| **A2.** A regra de 8 lapsos é tardia e ruidosa sob FSRS | [Schoreels 2026](https://jschoreels.substack.com/p/anki-leech-detection-based-on-actual); [Expertium, tópico 56887](https://forums.ankiweb.net/t/automated-leech-detection/56887) (teste estatístico com a recordação prevista pelo FSRS permitiria detectar com 2 ou 3 revisões); [Bjornstad](https://controlaltbackspace.org/leech/) (ao atingir 8 lapsos, já foram dezenas de revisões "em círculos") | Média a alta como argumento técnico. Mas o próprio Expertium diz que não saberão o quão bem funciona "até tentar" |
| **A3.** As causas são distintas e pedem ações distintas | Manual do Anki (editar, apagar, esperar); Bjornstad (decisão em 6 passos); [20 regras de Wozniak](https://super-memory.com/articles/20rules.htm); Tinkham 1993 e Waring 1997 (interferência em vocabulário L2, Fase 3) | Média: consenso de prática, sem validação da taxonomia |
| **A4.** Há conceito análogo e método estabelecido em pesquisa educacional | *Wheel spinning* (Beck & Gong 2013); qualidade de itens em avaliação ([Haladyna et al. 2002](https://doi.org/10.1207/s15324818ame1503_5): diretrizes de redação; [Tarrant & Ware 2008](https://doi.org/10.1111/j.1365-2923.2007.02957.x): impacto de falhas de redação no desempenho em testes de múltipla escolha, pelo título); refinamento de modelos a partir de dados ([Cen et al. 2006](https://doi.org/10.1007/11774303_17)); **"fechar o ciclo"**: dados apontam o defeito, a instrução é refeita, um experimento mede o ganho ([Liu & Koedinger 2017](https://doi.org/10.5281/zenodo.3554625)) | Forte como **fundamentação conceitual**. Não prova que o Card Doctor funciona em flashcards |
| **A5.** Feedback elaborado ajuda, se bem desenhado | [Wisniewski et al. 2020](https://doi.org/10.3389/fpsyg.2019.03087) (d = 0,48; depende do conteúdo); Kornell et al. 2009; [Dunlosky et al. 2013](https://doi.org/10.1177/1529100612453266) (interrogação elaborativa e autoexplicação: utilidade moderada; mnemônico de palavra-chave: baixa) | Média. Transferência para flashcards não demonstrada |
| **A6.** Há demanda real | Fóruns do Anki (tópicos [67575](https://forums.ankiweb.net/t/67575), [42926](https://forums.ankiweb.net/t/identify-leeches-by-the-total-times-of-pressing-again/42926), 40740, 56887 com ~1,4 mil visualizações); add-ons e scripts de detecção; [AnkiAIUtils](https://github.com/thiswillbeyourgithub/AnkiAIUtils) (887 estrelas) | Demanda indicada, não medida |
| **A7.** Dá para avaliar com poucos participantes | Ensaios microrandomizados ([Klasnja et al. 2015](https://doi.org/10.1037/hea0000305); [Qian et al. 2022](https://doi.org/10.1037/met0000283)); desenhos de caso único com padrões de qualidade ([Kratochwill et al. 2013](https://doi.org/10.1177/0741932512452794), [atualização 2021](https://doi.org/10.1016/j.jsp.2021.10.006)); testes de randomização para experimentos de caso único ([2013](https://doi.org/10.1016/j.jcbs.2013.10.002); [pacote R](https://doi.org/10.3758/brm.40.2.467)) | Forte como método. Limita a generalização |
| **A8.** O usuário médio depende de cartões que não escreveu | [Nour & Harris 2025](https://doi.org/10.7759/cureus.95674): 97,6% usavam cartões prontos | Uma escola de medicina; autorrelato |
| **A9.** LLMs conseguem avaliar e reformular perguntas com qualidade razoável | Moore et al. 2022, 2023 e 2024; An et al. 2025 (Fase 2, seção 3.3) | Média e heterogênea; ver O4 abaixo |

**Como usar fontes que corroboram, sem se enganar:**

- Elas sustentam a **relevância e a fundamentação** (por que o problema importa, por que o método é razoável). Quem demonstra que a tese vale são os **seus resultados**.
- Cada afirmação da justificativa precisa de fonte, mas a avaliação deve ser capaz de **refutar** a tese. Um TCC com resultado nulo e bem conduzido é aceitável; um com fontes escolhidas a dedo e avaliação incapaz de falhar, não.
- Apresente as fontes contrárias (seção 4) na discussão e nas limitações.

---

## 4. Fontes contra e limites (advogado do diabo)

| Objeção | Evidência | Como o projeto lida |
|---|---|---|
| **O1.** Dificuldade é desejável; falhar também ensina | Bjork & Bjork 2011; Kornell et al. 2009 | Detectar **ausência de progresso**, não dificuldade; "nenhuma ação" é uma decisão válida; medir se o cartão "se cura" sozinho |
| **O2.** O FSRS já se adapta aos cartões difíceis | Tópico 40740: a dificuldade é relativa | O FSRS só muda o **quando**; o custo que sobra é medido no E1 |
| **O3.** Suspender ou apagar é barato e suficiente | Bjornstad (passos 4 e 5: "apague e não olhe para trás") | Apagar e adiar fazem parte do espaço de ações; compara-se custo-benefício (E4). Risco: perder conhecimento crítico |
| **O4.** LLMs erram, alucinam e não prevêem dificuldade | [An et al. 2026](https://arxiv.org/abs/2609.27063): dificuldade rotulada por LLM quase não correlaciona com a empírica (ρ ≈ 0,06) | O diagnóstico usa o histórico, não só o texto; abstenção; aprovação humana; taxa de erro factual reportada |
| **O5.** IA pode prejudicar a aprendizagem | [Bastani et al. 2025](https://doi.org/10.1073/pnas.2422633122) | A IA propõe edições de cartão; não responde pelo aluno; a recordação continua sendo do usuário |
| **O6.** Poder estatístico baixo | Cálculos da seção 6.4 | Estudo exploratório, estimativa com intervalo, réplica entre pessoas; não alegar eficácia |
| **O7.** "Leech" não tem verdade absoluta para treinar ou avaliar | Expertium: um detector aprendido exigiria milhares (talvez centenas de milhares) de cartões rotulados à mão, "e isso não vai acontecer"; Schoreels lista quatro definições possíveis | Usar **custo futuro** como critério objetivo (sem rótulo manual), com análise de sensibilidade às definições; rótulos humanos só para a **causa** (E2), em amostra pequena |
| **O8.** Alguns cartões são difíceis por natureza e não têm conserto | Bjornstad (passo 6: mnemônico como último recurso; se nada funcionar, o cartão provavelmente continuará falhando) | A taxonomia inclui "associação arbitrária" e "pouco importante"; o sistema não promete cura |
| **O9.** O usuário já faz isso à mão | Bjornstad descreve uma rotina semanal manual | O custo de triagem e de edição entra no custo-benefício; a ferramenta só vale se reduzir esse custo |
| **O10.** O mercado se mexe rápido | Leech Detector (abr/2026), leechkit, Leech Doctor (poucos dias) | Posicionar a contribuição como **avaliação e protocolo**, difícil de copiar por quem só lança ferramentas |

---

## 5. Inovação: o que já existe e onde está o espaço

### 5.1 Estado da arte por componente

| Componente | O que já existe | Avaliação publicada? |
|---|---|---|
| Detecção por contagem de lapsos | Regra padrão do Anki (8 lapsos, marca e suspende) | Não |
| Detecção por razão ou desempenho | Leech Toolkit, Anki-Leech-Manager; [Leech Detector](https://ankiweb.net/shared/info/1406469667) (ciclos e quedas de desempenho; status ativo, recuperando, recuperado) | Não |
| Detecção por excesso de falhas sobre o esperado | Proposta de Expertium (tópico 56887, mar/2025: cauda da distribuição Poisson-binomial com a recordação prevista pelo FSRS; limiar de 1%); implementação no leechkit (experimental) | Não: "não saberemos o quão bem funciona até tentar" |
| Diagnóstico + reescrita por LLM + aplicar/reverter | **[anki-leech-doctor](https://github.com/alexanderjfink/anki-leech-doctor)** (add-on; ranking por lapsos; diagnóstico heurístico; LLM devolve modo de falha, justificativa e edições em JSON; log de reversão; licença Peer Production; 0 estrelas; commits de "há 2 dias" na página); [AnkiAIUtils](https://github.com/thiswillbeyourgithub/AnkiAIUtils) (explicações, mnemônicos, reformulação); anki-for-claude (`improve-cards`) | Não |
| Interferência entre cartões | Interference Recorder, AnkiFuzzy, ankiR | Não |
| **Medir o efeito da remediação (intra-usuário, randomizado)** | **Não encontrei** | **Não** |
| Conceitos acadêmicos análogos | *Wheel spinning*, análise de itens, refinamento de modelos, "fechar o ciclo" (outros domínios) | Sim, fora de flashcards |

### 5.2 Veredito de novidade

- **Ferramenta:** não é novidade. Quase tudo que a P1 faria como produto existe, e o espaço está lotando.
- **Onde ainda há espaço (todas as afirmações com "não encontrei"):**
  1. Avaliação **comparativa** de detectores pelo custo futuro em muitas coleções.
  2. Avaliação do **efeito** de remediar cartões, com desenho randomizado dentro do usuário.
  3. Taxonomia de causas **validada** (concordância entre avaliadores) e com abstenção.
  4. **Transferência** de conceitos de pesquisa educacional (*wheel spinning*, análise de itens, fechar o ciclo) para repetição espaçada de consumo.
- **Para um TCC:** não se exige ineditismo mundial. Exige problema bem posto, método coerente, avaliação honesta e discussão de limites. Inovação incremental com avaliação rigorosa é um bom TCC.
- **Vale o mesmo para as outras propostas da Fase 3:** a explicação pós-erro (P2) já existe no AnkiAIUtils e a nota implícita (P3) em add-ons. Neste ecossistema, qualquer ideia de ferramenta já tem concorrente; o que falta em todas é avaliação.

### 5.3 Correções à Fase 3 após esta rodada

| Item da Fase 3 | Correção |
|---|---|
| Novidade "média-alta" da P1 | Alta demais: existe o add-on anki-leech-doctor (e scripts de IA). Passa a "média, concentrada na avaliação". Continua valendo: **sem avaliação** publicada |
| Cifras do SuperMemo "não verificadas na fonte" | Verificadas na [página primária](https://super-memory.com/articles/theory.htm): o 300% é simulação; "50% das repetições para 2,5%" refere-se a material de intervalo curto, não a leeches; há tabela de medição real por número de lapsos, sem detalhes da amostra (A1) |
| Detecção estatística como baseline | Já proposta e implementada pela comunidade (Expertium, leechkit); entra como baseline, não como contribuição |

### 5.4 PoC autoral: três formas, e a recomendada

| Forma | O que é | Vantagem | Risco |
|---|---|---|---|
| **A. Construir** | Reimplementar o ciclo completo como produto | Entrega visível | Sem novidade; compete com ferramentas prontas |
| **B. Banco de provas (recomendada)** | PoC mínima **somente leitura** (detectores comparáveis + diagnóstico + registro) e a **avaliação** como contribuição | Novidade na avaliação; escopo controlável; mostra o conceito | Menos "produto" |
| **C. Avaliar ferramenta alheia** | Usar o anki-leech-doctor como intervenção e só montar o experimento | Menor esforço de engenharia | Ferramenta nova e instável; licença Peer Production (não comercial, compartilhar igual) limita reuso |

**Escopo da forma B:**

1. **Auditoria** da sua coleção (seção 6.0), sem código.
2. **Detectores**: leitura da coleção e relatório (CSV ou HTML) com os escores de vários detectores lado a lado, na sua coleção e, depois, no conjunto público.
3. **Diagnóstico**: para cada cartão sinalizado, saída estruturada (causa, justificativa, confiança, rascunho), em arquivo para você aprovar à mão; você aplica as edições (sem escrever na coleção).
4. **Registro** de decisões e acompanhamento (planilha ou CSV) para o piloto.
5. *Opcional*: aplicar edições via API, com backup e reversão.

Uma implementação própria também evita amarras de licença (AGPL do Anki e do AnkiAIUtils, Peer Production do Leech Doctor). Contribuição de engenharia: requisitos e taxonomia, arquitetura com aprovação humana e reversão, testes com coleções sintéticas, reprodutibilidade (sementes fixas, versão de prompt e de modelo registradas) e privacidade por projeto.

---

## 6. Como mediríamos

### 6.0 Auditoria inicial na sua coleção (sem código)

No **Navegador** do Anki, digite cada busca e leia quantos cartões aparecem:

| Busca | Mede | Para que serve |
|---|---|---|
| (todos os cartões) | Total de cartões | Denominador |
| `prop:lapses>=3` | Cartões com 3 ou mais lapsos | Base de candidatos do detector e do piloto |
| `prop:lapses>=5` | Idem, 5 ou mais | Casos claros |
| `tag:leech` | Leeches pela regra padrão | O que o Anki já marcou |
| `tag:leech is:suspended` | Leeches já suspensos | Cartões "abandonados" |
| `rated:30:1` | Cartões com "Again" no último mês | Atividade recente de falhas |
| `prop:reps>=8 prop:s<10` (só com FSRS) | Muitas revisões e estabilidade baixa | Candidatos a "não evolui" |

Sintaxe conforme o [manual de busca](https://docs.ankiweb.net/searching.html). Anote também **se o FSRS está ativado** (nas opções do baralho): os detectores estatísticos dependem dele.

**Regra prática minha** para decidir o desenho: com menos de ~40 cartões elegíveis (você e colegas somados) o piloto é só descritivo; com mais de ~100 já há material para uma estimativa com intervalo de confiança.

### 6.1 Visão geral das camadas

| Camada | Pergunta | Dados | Medida | O que se pode alegar |
|---|---|---|---|---|
| **E1** Detecção | O detector proposto antecipa e identifica melhor os cartões que não evoluem? | anki-revlogs-10k (público) e sua coleção | PR-AUC, precisão nos K primeiros, antecedência, falsos positivos | "Detecta N revisões antes da regra padrão, com taxa de falsos positivos Y" |
| **E2** Diagnóstico | A causa e a ação sugeridas concordam com humanos e são úteis? | Cartões sinalizados em coleções reais | κ de Cohen, aceitação, utilidade (1 a 5), erro factual | "Concordância de κ = ...; X% das sugestões aceitas" |
| **E3** Efeito | Remediar agora reduz falhas e tempo depois, comparado a remediar mais tarde? | Piloto intra-usuário | Lapsos por 10 revisões, minutos, fração que evolui | "Em K usuários, efeito estimado Z (IC ...)", sem generalizar |
| **E4** Custo-benefício | Compensa o tempo gasto na triagem e na edição? | Registro do piloto | Minutos economizados menos minutos gastos | "Economia líquida de ... por cartão remediado" |

### 6.2 E1: detecção offline

- **Unidade:** cartão em um ponto de decisão (depois da k-ésima revisão, k = 3 a 10), usando só o histórico até ali. Ignorar as primeiras revisões, em que o estado do FSRS ainda se estabiliza, como faz o leechkit (`--skip-reviews`).
- **Detectores comparados:**
  - D0: regra do Anki (lapsos ≥ L, com L = 3, 4, 5 e 8).
  - D1: razão lapsos por revisão.
  - D2: dificuldade FSRS alta (baseline fraco, segundo o fórum).
  - D3: excesso de falhas sobre o esperado (cauda Poisson-binomial, limiares de 1% e 5%).
  - D4: ciclos e quedas de desempenho (Leech Detector).
  - D5: modelo aprendido nos k primeiros eventos (regressão logística ou árvores).
- **Desfecho (fixado antes):** custo futuro do cartão (lapsos e minutos nas próximas H revisões); "problemático" = custo acima de um percentil entre cartões com histórico comparável. Análise de sensibilidade com definições alternativas (Schoreels lista quatro).
- **Métricas:** PR-AUC e AUROC; precisão nos K primeiros por coleção (K = 20 e 50, que é o que um usuário consegue triar); **antecedência** (revisões e minutos antes de a regra de 8 lapsos disparar); falsos positivos (cartões que "se curam"); economia potencial (limite superior).
- **Estatística:** reamostragem (bootstrap) por usuário; comparação pareada entre detectores; intervalos de 95%.
- **Dados:** [anki-revlogs-10k](https://huggingface.co/datasets/open-spaced-repetition/anki-revlogs-10k) (Fase 2: 10 mil coleções, sem texto, exige aceitar as condições no Hugging Face). Não depende de voluntários.
- **Ameaças:**
  - **Censura:** o usuário age sobre leeches (suspende, edita, apaga), truncando o futuro do cartão; tratar com análise de sobrevivência ou rótulos só até a censura.
  - `duration` não é o tempo até revelar a resposta.
  - O histórico não registra as edições nem as suspensões.
  - A recordação prevista exige parâmetros do FSRS por usuário (usar parâmetros padrão como aproximação é uma simplificação a declarar).

### 6.3 E2: diagnóstico

- **Amostra:** algumas dezenas a poucas centenas de cartões sinalizados em 3 a 4 coleções.
- **Rubrica:** livro de códigos com definição e exemplos de cada causa (formulação, falta de contexto, interferência, arbitrária, pouco importante, "outro/incerto").
- **Avaliadores:** o **dono do cartão** (melhor informante sobre por que falha) e você; κ de Cohen entre eles e contra o sistema.
- **Comparações:** (a) regras simples; (b) LLM com prompt único, sem taxonomia; (c) a proposta (LLM + taxonomia + estatísticas + abstenção); (d) opcional, o campo "modo de falha" do anki-leech-doctor nos mesmos cartões.
- **Métricas:** κ, concordância por classe, taxa de aceitação (aceita, editada, rejeitada), utilidade percebida (1 a 5), **taxa de sugestões com erro factual** (revisão humana), cobertura (quanto o sistema se abstém).
- **Ameaças:** rótulos subjetivos; amostra pequena; limiar de κ a fixar antes (convenções como as de Landis e Koch †).

### 6.4 E3: efeito (piloto intra-usuário)

- **Elegibilidade:** cartões sinalizados abaixo do limiar de 8 lapsos. Desativar a suspensão automática dos cartões do piloto, para que o braço de espera não seja suspenso durante a janela.
- **Desenho:** randomização **por nota** (blocos por pessoa e por baralho) entre **remediar agora** e **lista de espera** (remediar só depois de uma janela fixa de revisões ou dias, definida antes). Todos os cartões acabam remediados.
- **Regra única de reagendamento** após a edição (por exemplo, manter o agendamento), definida antes, para não confundir o efeito.
- **Desfechos:** primário, lapsos por 10 revisões na janela; secundários, minutos por revisão, fração que atinge um intervalo-alvo sem novo lapso, recorrência da marcação, aceitação, tempo de triagem.
- **Análise:**
  - **Por pessoa:** teste de randomização (p-valor exato, sem supor amostragem aleatória nem normalidade; a validade vem do sorteio).
  - **Global:** modelo misto (contagem de lapsos com exposição em revisões; efeitos aleatórios por usuário e por nota), com intervalos de confiança.
  - **Pré-registro** (OSF †).
- **Réplica:** desenhos de caso único pedem demonstração do efeito em **pelo menos três momentos ou casos** ([padrões do WWC](https://ies.ed.gov/ncee/wwc/Docs/ReferenceResources/wwc_scd.pdf), lido apenas em trechos de busca). Você mais cerca de 3 colegas atende a isso.

**Poder (cálculo meu; α = 0,05; poder 80%; sem agrupamento):**

| Efeito a detectar | Cartões por braço |
|---|---|
| Taxa de falha de 35% para 20% | ≈ 140 |
| Taxa de falha de 35% para 10% | ≈ 43 |

Com 20 a 30 cartões por braço por pessoa, só efeitos enormes seriam detectáveis. Usar desfechos no nível da revisão, com efeitos aleatórios, e somar as pessoas ajuda, mas o piloto continua **exploratório**: o resultado é uma estimativa com intervalo, não uma confirmação.

**Ameaça específica:** "remediar agora" mistura a sugestão do LLM com a **atenção** dada ao cartão. Separar exigiria um terceiro braço (o usuário remedia sem LLM), possível só se houver cartões suficientes.

### 6.5 E4: custo-benefício

- Economia líquida por cartão = (revisões evitadas × segundos por revisão) − (tempo de triagem + tempo de edição).
- Ponto de equilíbrio: a ação compensa quando a probabilidade de sucesso, multiplicada pelo custo evitado no horizonte, supera o tempo gasto na intervenção.
- Reportar também quanto do custo vem de **apagar ou adiar** (O3). Se apagar custa menos e basta, o resultado diz isso.

### 6.6 O que os colegas agregam

| Cenário | Dá para fazer | Não dá |
|---|---|---|
| Só você | E1 completo (dados públicos); E2 com você como avaliador (viés); E3 como estudo de caso sobre a sua coleção, com randomização por nota e teste de randomização (válido para você) | Generalizar; medir concordância entre pessoas; replicar entre usuários |
| Você e cerca de 3 colegas | E3 com **réplica entre participantes** (o padrão mínimo de três demonstrações); coleções e áreas diferentes (versões do Anki, idiomas, FSRS ligado ou não); mais cartões para o piloto; **cada colega rotula a causa dos próprios cartões** (melhor informante), o que viabiliza o κ; retorno de usabilidade | Estimativas para a população geral |
| Dez ou mais | Estimativas mais estáveis | Não é necessário para o TCC |

**Pedido mínimo a cada colega:** rodar a ferramenta localmente, rotular uns 15 a 20 cartões sinalizados (causa percebida e utilidade da sugestão) e devolver uma planilha anonimizada, **sem compartilhar o texto dos cartões**. Mesmo sem exigência da instituição, recomendo um termo de consentimento simples e anonimização.

### 6.7 Ameaças à validade

| Tipo | Ameaça | Mitigação |
|---|---|---|
| Construto | "Leech" e "evolui" são operacionalizações | Definições fixadas antes; sensibilidade; custo futuro objetivo |
| Interna | Atenção ao cartão, regressão à média, cartões irmãos ou parecidos, censura por ações do usuário | Lista de espera, randomização por nota, regra de reagendamento, análise de sobrevivência |
| Externa | Poucas pessoas, áreas e decks diferentes | Réplica entre pessoas; declarar o escopo; não generalizar |
| Conclusão | Baixo poder, múltiplas comparações | Estimativa com IC; desfecho primário único; pré-registro |

As categorias seguem a convenção de estudos empíricos em engenharia de software (Wohlin et al. †).

---

## 7. A tese

### 7.1 Termos

Em TCC costuma-se escrever **problema de pesquisa**, **hipótese**, **objetivo geral** e **objetivos específicos**. A "tese" aqui é a hipótese central que a avaliação tenta sustentar ou refutar.

### 7.2 Formulações possíveis

| Versão | Enunciado | Quando usar |
|---|---|---|
| **Viabilidade (PoC)** | É viável fechar o ciclo detectar, diagnosticar, corrigir e medir em coleções reais do Anki, com diagnósticos que os usuários consideram corretos e úteis e com uma estimativa preliminar do efeito | Escopo mínimo, foco em demonstrar o conceito |
| **Detecção** | Um teste estatístico sobre o histórico de revisão identifica cartões que não evoluem **mais cedo e com menos falsos positivos** que a regra padrão de 8 lapsos | Se o peso for dados e avaliação offline |
| **Efeito** | Remediar cartões que não evoluem, conforme a causa provável e com aprovação do usuário, reduz as falhas e o tempo de revisão subsequentes em relação a adiar a remediação | Se houver voluntários e cartões suficientes |

**Recomendada (combinando as três, com pesos diferentes):**

> Cartões que não evoluem com a prática podem ser identificados mais cedo, e com menos falsos positivos, por um teste estatístico sobre o histórico de revisão do que pela regra padrão de lapsos; e remediar esses cartões conforme a causa provável, com aprovação do usuário, reduz as falhas e o tempo de revisão subsequentes em relação a adiar a remediação. A prova de conceito testa a primeira parte offline e explora a segunda em poucos usuários.

### 7.3 Hipóteses e critérios de refutação

| Hipótese | Refutada se |
|---|---|
| **H1 (detecção).** O detector D3 tem PR-AUC maior que o da regra de 8 lapsos e antecipa a sinalização, sem aumentar os falsos positivos | O IC de 95% (por usuário) da diferença inclui zero ou a antecedência mediana não é positiva |
| **H2 (diagnóstico).** A causa sugerida concorda com os donos dos cartões acima de um κ definido antes, e a maioria das sugestões é aceita ou editada | O κ ou a aceitação ficam abaixo do limiar combinado |
| **H3 (efeito, exploratória).** Remediar agora reduz lapsos por 10 revisões em relação à espera | A estimativa tem o sinal oposto ou o IC é largo demais para excluir efeito nulo (reportar assim, sem "provar" nada) |
| **H4 (custo).** A economia líquida por cartão é positiva | O tempo de triagem e edição supera o custo evitado |

Os limiares numéricos devem ser fixados **antes** de olhar os dados (pré-registro).

### 7.4 Objetivos (rascunho para o texto do TCC)

**Objetivo geral:** desenvolver e avaliar uma prova de conceito que detecta cartões de repetição espaçada que não evoluem com a prática e propõe, com aprovação do usuário, intervenções direcionadas à causa provável.

**Objetivos específicos:**

1. Levantar a literatura e as ferramentas existentes sobre leeches, qualidade de cartões e detecção de itens improdutivos.
2. Definir operacionalmente "cartão que não evolui" e uma taxonomia de causas com rubrica.
3. Implementar a PoC (detectores, diagnóstico, registro; aplicação assistida opcional).
4. Avaliar os detectores offline em conjunto público de coleções.
5. Avaliar o diagnóstico por concordância entre avaliadores e utilidade percebida.
6. Conduzir um estudo exploratório intra-usuário do efeito da remediação.
7. Analisar custo-benefício, ameaças à validade e limitações.

**Metodologia:** Design Science Research ([Hevner et al. 2004](https://doi.org/10.2307/25148625); [Peffers et al. 2007](https://doi.org/10.2753/mis0742-1222240302)): problema, objetivos, projeto e desenvolvimento, demonstração, avaliação, comunicação.

### 7.5 Critérios de sucesso da PoC

- Roda de ponta a ponta em coleções reais sem alterar nada sem aprovação.
- O detector antecipa a sinalização e a comparação com a regra padrão é reportada com intervalo.
- Diagnóstico com concordância e aceitação reportadas.
- Estimativa de efeito com IC e limites declarados.
- Resultado nulo ou negativo é aceitável se bem conduzido e discutido.

---

## 8. É uma boa opção? Veredito, riscos e critérios

**A favor:** problema real e documentado; geral (qualquer matéria); sem oráculo; parte offline sem pessoas; dá para testar na sua própria coleção desde o início; encaixa em DSR e em engenharia de software; metodologia de avaliação com poucos participantes já estabelecida.

**Contra:** a ferramenta em si não é novidade; o piloto tem baixo poder; depende de haver cartões suficientes; a definição de "problemático" é discutível; o mercado se mexe rápido; o dataset público não tem texto, então diagnóstico e efeito dependem de coleções reais.

**Boa opção se:** você aceitar que a contribuição é a **avaliação e o protocolo**, e declarar o piloto como exploratório.

**Má opção se:** o objetivo for "um produto novo que ninguém tem", ou se você quiser alegar "melhora a aprendizagem".

**Critérios de decisão depois da auditoria (6.0):**

| Situação | Caminho |
|---|---|
| Cartões suficientes (você + colegas) e acesso ao conjunto público | P1 completo (E1 a E4) |
| Sem colegas | E1 + E2 (você como avaliador) + E3 como estudo de caso, apresentado como viabilidade |
| Quase nenhum cartão elegível e sem acesso ao conjunto público | Mudar para a P3 (nota implícita, só com dados públicos) ou outra proposta |

---

## 9. Próximos passos (sem código)

1. Rodar a **auditoria** da seção 6.0 e anotar os números (e se o FSRS está ativo).
2. Decidir entre PoC **forma B** (recomendada) e as outras formas (seção 5.4).
3. Escolher a formulação da tese (seção 7.2).
4. Esboçar a **taxonomia e a rubrica** e rotular à mão uns 20 cartões seus, para testar se as categorias se distinguem.
5. Só depois: liberar a implementação.

Perguntas que ficam:

- Quanto deu na auditoria (total, ≥ 3 lapsos, `tag:leech`)? FSRS ativado?
- Algum colega topa o pedido mínimo da seção 6.6?
- A banca valoriza mais artefato ou evidência? (Define o peso entre construir e avaliar.)

---

## 10. Referências

**Verificadas nesta rodada (existência, resumo ou página):**

- Pesquisa e métodos: [Beck & Gong 2013](https://doi.org/10.1007/978-3-642-39112-5_44) (*wheel spinning*); [Liu & Koedinger 2017](https://doi.org/10.5281/zenodo.3554625) (fechar o ciclo); [Cen et al. 2006](https://doi.org/10.1007/11774303_17) (LFA); [Kornell et al. 2009](https://doi.org/10.1037/a0015729); Bjork & Bjork 2011, "Making things hard on yourself, but in a good way" (capítulo, sem DOI); [Haladyna et al. 2002](https://doi.org/10.1207/s15324818ame1503_5); [Tarrant & Ware 2008](https://doi.org/10.1111/j.1365-2923.2007.02957.x) (autores de memória †); [Kratochwill et al. 2013](https://doi.org/10.1177/0741932512452794) e [2021](https://doi.org/10.1016/j.jsp.2021.10.006); testes de randomização em experimentos de caso único ([2013](https://doi.org/10.1016/j.jcbs.2013.10.002); [pacote R, 2008](https://doi.org/10.3758/brm.40.2.467)); [WWC, documentação técnica de desenhos de caso único](https://ies.ed.gov/ncee/wwc/Docs/ReferenceResources/wwc_scd.pdf) (só trechos de busca).
- Reaproveitadas da Fase 3: Wisniewski et al. 2020; Dunlosky et al. 2013; Klasnja et al. 2015; Qian et al. 2022; Nour & Harris 2025; Bastani et al. 2025; An et al. 2026; Hevner et al. 2004; Peffers et al. 2007.
- Fonte primária do SuperMemo: [Wozniak, "Theoretical aspects of spaced repetition in learning"](https://super-memory.com/articles/theory.htm).
- Documentação e código do Anki: [busca](https://docs.ankiweb.net/searching.html); [`pylib/anki/cards.py`](https://github.com/ankitects/anki/blob/main/pylib/anki/cards.py); [manual: Leeches](https://docs.ankiweb.net/leeches.html).
- Comunidade e ferramentas: fórum do Anki [56887](https://forums.ankiweb.net/t/automated-leech-detection/56887) (Expertium) e [40740](https://forums.ankiweb.net/t/using-fsrs-parameters-to-identify-leech-cards/40740); [Schoreels 2026](https://jschoreels.substack.com/p/anki-leech-detection-based-on-actual); [Bjornstad](https://controlaltbackspace.org/leech/); [anki-leech-doctor](https://github.com/alexanderjfink/anki-leech-doctor) (AnkiWeb 2142317474); [anki-for-claude](https://github.com/MichaelPrutkow/anki-for-claude); [leechkit](https://github.com/rbrownwsws/leechkit); [Leech Detector](https://ankiweb.net/shared/info/1406469667); [AnkiAIUtils](https://github.com/thiswillbeyourgithub/AnkiAIUtils); [artigo da Flica sobre leeches](https://flica.app/article/anki-leech-cards) (conteúdo comercial, usado só para ver a taxonomia popular de causas; não é evidência).

**Marcadas †, de memória, não verificadas:** esquema da tabela `revlog`; API de add-ons do Anki e AnkiConnect; implicações da licença AGPL ao importar a biblioteca do Anki; pré-registro no OSF; Gong & Beck 2015 sobre detecção precoce de *wheel spinning*; Wohlin et al. sobre ameaças à validade; limiares de κ de Landis e Koch; autores de Tarrant & Ware 2008.

---

## 11. Limitações desta pesquisa

- Busca ampla, mas não sistemática; sem bases pagas; Semantic Scholar indisponível.
- A maior parte foi lida só por resumo ou trechos de página. O documento do WWC foi visto só em trechos de busca. Os detalhes do anki-leech-doctor vêm do README; não instalei nem testei nenhuma ferramenta.
- O anki-leech-doctor é muito recente (versões 0.1 e 0.2, commits de poucos dias): pode mudar, e o que digo sobre ele pode estar desatualizado em pouco tempo.
- Os números do SuperMemo vêm de medições sem detalhes de amostra (aparentemente um único processo de aprendizagem) e de simulação; não representam coleções do Anki.
- Os cálculos de poder são aproximações simples; com medidas repetidas e covariáveis, o poder real muda.
- Não medi a prevalência de leeches em dados públicos: isso seria o primeiro resultado do E1.
- "Não encontrei" significa busca rápida, não inexistência.
