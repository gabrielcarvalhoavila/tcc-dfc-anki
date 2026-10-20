# Fase 5: Retorno à ideia original (variantes de cartões como sonda de memorização do formato)

Data: 2026-10-14. Retoma a ideia inicial (ver [Fase 1](Fase%201%20-%20An%C3%A1lise%20e%20Pesquisa%20Acad%C3%AAmica.md)) com o que as Fases [2](Fase%202%20-%20Refinamento%20do%20Tema.md), [3](Fase%203%20-%20Propostas%20para%20Usu%C3%A1rios%20Gerais.md) e [4](Fase%204%20-%20Aprofundamento%20do%20Card%20Doctor.md) mostraram. Nenhum código foi escrito. Os candidatos das fases anteriores ficam de lado.

**Como ler.** † marca o que vem da minha memória e não foi verificado; "não encontrei" significa "não encontrei em busca rápida". Para vários clássicos da psicologia (Tulving & Thomson 1973, Morris et al. 1977, Chi et al. 1981, Reyna & Brainerd 1995, Paas & van Merriënboer 1994, Kahana 2002, Rohrer et al. 2010) verifiquei só a existência e o título; o conteúdo vem de conhecimento geral †. Escores e cálculos são meus.

---

## 0. Respostas diretas

| Pergunta | Resposta curta |
|---|---|
| A ideia é boa? | Sim, **como sonda de diagnóstico e experimento**, com três ajustes: (1) acertar uma variante é **evidência** de generalização, não prova de que "aprendeu o conteúdo"; (2) a novidade não é variar cartões (isso já existe), e sim **escolher candidatos, medir a diferença e avaliar**; (3) começar só com variantes que não exigem conhecimento externo ("mundo fechado"). |
| Faz sentido para TCC? | Sim. Junta um problema que você mesmo observa, **muitos eventos por usuário** (dá para medir com pouca gente), um artefato de software (add-on com LLM e validação) e uma hipótese falseável. |
| Já existe? | A **rotação** de variantes, sim: add-on Dynamic Cards (LLM), tipos de nota randomizados do Expertium, Reformulator do AnkiAIUtils. **Não encontrei:** escolha de candidatos por comportamento, registro de qual variante foi mostrada, nem medição da diferença entre original e variante. |
| Qual seria a tese? | Seção 7. |
| Como mediríamos? | Seção 6: sortear, no horário devido, original ou variante, e comparar o acerto entre cartões suspeitos e de controle. |
| O que fazer antes de programar? | Um experimento-relâmpago manual (seção 8). |

---

## 1. A ideia em termos precisos

### 1.1 O fenômeno e seus nomes

- **Comunidade do Anki:** "pattern matching". Segundo o [Expertium](https://expertium.github.io/Avoid_Pattern_Matching.html), é "memorizar como a resposta se parece em vez da informação", o que leva a "recordar" no Anki mas não na vida real. [Matuschak](https://andymatuschak.org/prompts/) inclui "desencorajar pattern matching" nos testes de qualidade de um cartão e diz que clozes copiados de textos são particularmente suscetíveis.
- **Psicologia:** dependência de pista, especificidade de codificação, processamento adequado à transferência (seção 2).
- **Analogia de ML (só analogia):** sobreajuste a exemplos específicos; a **diferença de acerto entre o cartão original e uma variante** seria um "gap de generalização", e as variantes seriam "aumento de dados" para a memória.
- **Nome sugerido:** **dependência da forma do cartão** (DFC). A medida: **penalidade da variante** (queda de acerto quando a forma muda). "Visual" continua sem uso: não é termo acadêmico (Fase 1).

### 1.2 O que a lógica "acertou, aprendeu; errou, decorou" acerta e erra

| Original | Variante | Leitura mais provável | Outras explicações |
|---|---|---|---|
| Acertou | Acertou | Recordação robusta à forma | Memorizou também a variante (se repetida); variante fácil |
| Acertou | **Errou** | **Dependência da forma** (a hipótese) | Variante mais difícil; variante ambígua ou errada; direção invertida; lapso aleatório |
| Errou | Acertou | Rara | Original ambíguo; acaso |
| Errou | Errou | Esqueceu de fato | Não diz nada sobre a forma |

**Consequência:** "errou a variante" é um sinal **probabilístico**, e só significa algo **em comparação** com cartões de controle (seção 4). "Aprendeu o conteúdo" também é forte demais: o que a variante mostra é **robustez da recordação a mudanças de forma**, um tipo de transferência próxima.

### 1.3 Dois usos da mesma ideia

| Uso | O que faz | Evidência e situação |
|---|---|---|
| **Sonda** (diagnóstico) | Mede a penalidade da variante em cartões suspeitos | Não depende de a variação ser benéfica; é o núcleo proposto |
| **Rotação** (intervenção) | Alterna variantes no cartão ou cria cartões-irmãos com variantes | Evidência de benefício mista (seção 2) e ferramentas já existentes (seção 3); entra como estudo exploratório |

---

## 2. O fenômeno é real? Fundamentação (busca enviesada) e contraponto

### 2.1 Fontes de apoio

| # | Afirmação | Fontes | Força e limite |
|---|---|---|---|
| A1 | Usuários e autores descrevem o problema | Expertium; Matuschak (cloze copiado de texto; "false positives: como você poderia acertar sem saber?"); manual do Anki: a ordem "Deck, then due date" facilita adivinhar pelo contexto (Fase 2); fórum [55947](https://forums.ankiweb.net/t/image-occlusion-and-the-problem-of-excess-context-in-flashcards/55947) e [issue 3626](https://github.com/ankitects/anki/issues/3626) (Fase 2); threads do Reddit em [r/Anki](https://www.reddit.com/r/Anki/comments/1cy11e1/how_do_you_ensure_that_youre_recalling_the_cards/) e [r/medicalschoolanki](https://www.reddit.com/r/medicalschoolanki/comments/kab906/does_anyone_else_have_this_memory_issue/) (só trechos de busca; um usuário relata saber a resposta ao vê-la, mas o enunciado "não traduzir") | Média: prática e relatos, sem medição |
| A2 | A teoria prevê dependência de pista | [Tulving & Thomson 1973](https://doi.org/10.1037/h0020071) (especificidade de codificação); [Morris et al. 1977](https://doi.org/10.1016/s0022-5371(77)80016-9) (processamento adequado à transferência); [Reyna & Brainerd 1995](https://doi.org/10.1016/1041-6080(95)90031-4) (traços literais e de essência); [Chi et al. 1981](https://doi.org/10.1207/s15516709cog0502_2) (novatos e especialistas representam problemas de modo diferente) | Forte como teoria; a magnitude em flashcards é desconhecida |
| A3 | Estudar com a mesma pista do teste gera ilusão de saber | [Koriat & Bjork 2005](https://doi.org/10.1037/0278-7393.31.2.187) | Média a forte (laboratório) |
| A4 | Prática de recuperação tende a transferir | [Butler 2010](https://doi.org/10.1037/a0019902); [Rohrer et al. 2010](https://doi.org/10.1037/a0017678); [Carpenter 2012](https://doi.org/10.1177/0963721412452728); [Butler et al. 2017](https://doi.org/10.1037/xap0000142); [Pan & Rickard 2018](https://doi.org/10.1037/bul0000151) (d = 0,40; mais fraco para pares estímulo-resposta rearranjados) | Forte. Implica que **parte** da generalização vem "de graça" e que a DFC será **heterogênea** entre cartões, o que torna a medição interessante |
| A5 | Variar a prática melhora a transferência ao custo do desempenho na aquisição | [Paas & van Merriënboer 1994](https://doi.org/10.1037//0022-0663.86.1.122) (exemplos trabalhados variados) | Média; outro domínio |
| A6 | Gerar variantes isomórficas com IA e validá-las é viável | [Liu et al. 2026](https://arxiv.org/abs/2602.05114) (física: 73% dos bancos com dificuldade estatisticamente homogênea; modelos de linguagem ajudam a achar variantes problemáticas, como textos ambíguos); [Chen et al. 2023](https://arxiv.org/abs/2310.14498) (acesso aberto a bancos de problemas isomórficos teve impacto pequeno no desempenho em exames; as diferenças ficaram na faixa de 5 a 10 pontos percentuais, comparáveis às entre versões isomórficas do mesmo problema); [Gierl & Haladyna 2012](https://doi.org/10.4324/9780203803912) (geração automática de itens) | Média; domínio diferente (problemas de física, não flashcards) |
| A7 | Analogia com aprendizado de máquina | [Geirhos et al. 2020](https://doi.org/10.1038/s42256-020-00257-z) (aprendizado por atalhos); [Hoel 2021](https://doi.org/10.1016/j.patter.2021.100244) (hipótese de que o cérebro sofre sobreajuste e sonhos ajudam a generalizar; só o título foi lido) | Só analogia; não é evidência sobre pessoas |
| A8 | Há demanda e experimentação | Dynamic Cards, tipos de nota randomizados, Reformulator (seção 3) | Demanda, não eficácia |

### 2.2 Contraponto

| # | Objeção | Fontes | Como o projeto lida |
|---|---|---|---|
| C1 | Para associações arbitrárias, a especificidade pode ser o objetivo e variar não ajuda | [Cowan et al. 2024](https://doi.org/10.1073/pnas.2311077121) (variabilidade ajuda memória de item, não a associativa); Serrano & Pellicer-Sánchez 2026 (variação de contexto não facilitou recordação); Brunmair & Richter 2019 (intercalar prejudica com palavras) | Limitar o escopo a cartões **conceituais**; classificar "vale variar?" antes de gerar; excluir vocabulário, números e datas |
| C2 | Prompts devem produzir respostas consistentes | Matuschak (interferência, "retrieval-induced forgetting") | Variantes mudam o enunciado, **nunca a resposta esperada** |
| C3 | Errar a variante não prova que decorou | Versões isomórficas diferem em dificuldade da ordem de 5 a 10 pontos percentuais (Chen et al. 2023) e 27% dos bancos não tiveram dificuldade homogênea (Liu et al. 2026); a direção inversa de uma associação tem dificuldade própria (o Anki trata "Basic and reversed" como cartões separados; [Kahana 2002](https://doi.org/10.3758/bf03195769) discute a simetria associativa, resumo não lido) | Seção 4 |
| C4 | Variantes aumentam lapsos e carga | Paas & van Merriënboer 1994 (pior aquisição com variação) | Medir o custo (E5); limitar a fração de revisões com variante |
| C5 | Variação imprevisível pode irritar | Matuschak: "o mais importante a otimizar é a conexão emocional com as sessões de revisão" | Controle do usuário (desligar, marcar "variante ruim"); avaliação de usabilidade |
| C6 | LLMs erram e custam; privacidade | [An et al. 2026](https://arxiv.org/abs/2609.27063) (dificuldade rotulada por LLM quase não prevê a empírica); o Dynamic Cards avisa que "os cartões podem nem sempre ficar certos" | Validação em camadas, modo local, abstenção |
| C7 | Autoavaliação é subjetiva | Fase 2 | Resposta digitada opcional; análise de sensibilidade |

---

## 3. O que já existe e onde está o espaço

| Componente | O que existe | Avaliação publicada? |
|---|---|---|
| Variar o cartão por LLM a cada revisão | [Dynamic Cards](https://ankiweb.net/shared/info/1902186394) (add-on; Mistral ou Gemini; na primeira vez mostra o original, depois um reescrito; até 3 versões por padrão; atualizado em 2026-08-13; avisa que o LLM pode errar) | Nenhuma encontrada |
| Variantes escritas à mão e sorteadas | Tipos de nota do [Expertium e Vilhelm Ian](https://expertium.github.io/Avoid_Pattern_Matching.html) ([deck](https://ankiweb.net/shared/info/171015247)): Randomized Cloze e Basic (versões separadas por `|`, sorteadas a cada revisão), Shuffled Cloze (ordem das lacunas), Match Pairs (ordem aleatória). Sugerem usar LLM para gerar as 2 ou 3 versões | Nenhuma |
| Reescrita por IA | [AnkiAIUtils](https://github.com/thiswillbeyourgithub/AnkiAIUtils) (Reformulator: "varie a redação para fortalecer a recordação") | Nenhuma |
| Direção inversa, ordem aleatória | Recursos nativos do Anki ("Basic and reversed"; ordenação de revisão) | Não aplicável |
| **Escolher candidatos por comportamento** (acerta sempre, tempo até revelar curto, início do enunciado basta) | **Não encontrei** | Não |
| **Registrar qual variante foi mostrada e o resultado** | **Não encontrei.** O histórico nativo de revisões do Anki não registra qual versão foi exibida, e não vi registro de resultados por versão na página do Dynamic Cards | Não |
| **Medir a penalidade da variante e avaliar a rotação** | **Não encontrei.** No OpenAlex, "paraphrase" no título com "flashcards" no resumo retorna 0; no arXiv, "question paraphrase" com flashcard, repetição espaçada ou prática de recuperação retorna 0 | Não |

**Veredito de novidade:** variar cartões **não é novidade**. Os três espaços abertos são: **(a)** escolher quais cartões variar, **(b)** **medir** a diferença entre original e variante (diagnóstico), **(c)** **avaliar** se a rotação ajuda e a que custo. A sua frase "se acertou a variante, aprendeu; se não, decorou" é justamente (b), e é o que as ferramentas atuais, até onde vi, não fazem.

---

## 4. Como não se enganar: o problema de inferência

| Ameaça | Por que atrapalha | Mitigação |
|---|---|---|
| Dificuldade intrínseca da variante | Variante mais difícil faz parecer dependência de forma | **Grupo de controle** (cartões não suspeitos recebem as mesmas variantes); o efeito principal da variante mede a dificuldade média; duas variantes por cartão; pré-triagem por modelos de linguagem (como em Liu et al. 2026) |
| Direção inversa | Responder da resposta para a pergunta é naturalmente diferente | Inversão fica fora do índice principal (secundária) |
| Esquecimento verdadeiro | Errar por ter esquecido, não por depender da forma | Sorteio **no horário devido** e ajuste pela recordação prevista pelo FSRS |
| Contaminação sequencial | Ver a resposta do original e logo depois a variante infla o acerto | Nunca mostrar original e variante na mesma sessão; sorteio **por revisão** |
| Variante ambígua ou errada | Falha que não é do aluno | Validação automática, amostra revisada por humano, botão "variante ruim" que descarta o evento |
| Regressão à média e seleção | Cartões "sempre acertados" tendem a ter acertos futuros menores por acaso | Definir suspeitos **antes** do sorteio; controles emparelhados por número de revisões e intervalo |
| Treinar a variante | Se a mesma variante se repete, vira nova forma decorada | Variante **nova** a cada exposição na medição |
| Autoavaliação | Quem decorou pode achar que sabe | Resposta digitada opcional; análise de sensibilidade |
| Atenção e novidade | Qualquer mudança desperta atenção | Variantes também nos controles; o efeito principal absorve a novidade |

**A medida:** a **interação** entre "variante" e "suspeito" no acerto. Se cartões suspeitos perdem **mais** acerto com a variante do que os controles, há dependência de forma **além** do que a dificuldade das variantes explica.

---

## 5. Como seria o sistema (prova de conceito)

### 5.1 Fluxo do usuário

1. Você estuda como sempre. O add-on registra tempo até revelar, acerto e tipo de nota.
2. Ele calcula um **escore de candidato** por cartão (seção 5.2).
3. Para candidatos e controles, um LLM gera variantes de mundo fechado; a validação filtra (seção 5.4); você pode aprovar ou descartar.
4. No horário devido, o add-on **sorteia original ou variante** e registra qual foi mostrada.
5. Um relatório mostra a penalidade por cartão e por grupo e lista os cartões com dependência de forma.
6. *Ação (opcional):* rotacionar variantes no próprio cartão, criar **cartões-irmãos** com as variantes (o que você descreveu) ou sugerir reformulação.

### 5.2 Sinais de candidato

| Sinal | Como medir | Observação |
|---|---|---|
| Sequência de acertos e intervalo longo | Histórico de revisões | É o "ela acerta sempre" |
| Tempo até revelar curto para o tamanho do enunciado | Ganchos de revisão do add-on (seção 5.5); comparar com o tempo mínimo de leitura (adultos leem na casa das centenas de palavras por minuto; cerca de 238 em não ficção †, [Brysbaert 2019](https://doi.org/10.1016/j.jml.2019.104047)) e com a distribuição do próprio usuário | Ruído (multitarefa, leitura dinâmica): usar como **feature**, nunca como verdade. Já existe add-on que mede do exibir ao revelar (Pass/Fail Review, Fase 2) |
| **Prefixo mínimo identificador (PMI)** | Número mínimo de palavras iniciais do enunciado que distinguem o cartão de todos os outros do baralho | Formulação minha. Não depende de LLM nem de comportamento. Mede o quanto "as palavras iniciais" bastam para identificar o cartão |
| Formato do cartão | Cloze copiado de texto, ordem fixa de lacunas, oclusão de imagem | Apontados por Matuschak e Expertium como suscetíveis |

*Exemplo de PMI (inventado):* num baralho em que muitos enunciados começam com "Qual é o protocolo...", o PMI é alto (o início não distingue); num enunciado que começa com "Heme é formado por...", só a segunda palavra já o torna único (PMI = 2). Um cartão longo com PMI baixo é **estruturalmente** vulnerável a ser respondido sem ler o resto.

### 5.3 Tipos de variante

| Tipo | O que muda | Precisa de conhecimento externo? | Risco | No PoC? |
|---|---|---|---|---|
| Paráfrase | Palavras e estrutura do enunciado | **Não** (só reescreve) | Mudar o sentido | Sim |
| Reordenação | Ordem de itens, lacunas ou cláusulas | Não | Ordem que é parte do conhecimento (listas ordenadas) | Sim |
| Reformatação | Básico, cloze ou pergunta aberta | Não | Muda a dificuldade (completar versus produzir) | Sim, com o tipo registrado |
| Remoção ou troca da pista superficial | Corta ou substitui as palavras iniciais | Não | Pode tornar ambíguo | Sim |
| Inversão | Resposta vira pergunta | Só vale para fatos bijetivos | Dificuldade própria da direção | Secundária |
| Instância ou aplicação novas | Exemplo ou contexto diferente | **Sim** | Erro factual | **Fora**: é o "oráculo" que você rejeitou |
| Múltipla escolha com distratores | Reconhecimento no lugar de recordação | Sim (distratores plausíveis) | Muda a tarefa | Fora |

**Regra de "mundo fechado":** a resposta esperada da variante precisa estar **contida no texto do próprio cartão**. Assim o LLM só reorganiza o que o cartão já diz, sem precisar saber a matéria, e a validação consegue checar a variante contra o cartão.

*Exemplos ilustrativos (inventados):*

| Original | Variante | Tipo |
|---|---|---|
| "O que o TCP garante que o UDP não garante?" (entrega ordenada e confiável) | "Que propriedade distingue a transmissão do TCP da do UDP?" | Paráfrase |
| "Heme é formado por protoporfirina e {{c1::ferro}}" | "{{c1::Protoporfirina}} e ferro formam o heme" | Reordenação |
| "O que significa a sigla CRUD?" | "Que sigla designa Create, Read, Update e Delete?" | Inversão (secundária) |

### 5.4 Validação das variantes

1. Gerar K candidatas por cartão, com instrução ancorada no texto do cartão.
2. **Preservação da resposta:** outro modelo, ou um verificador de inferência textual, confere se a resposta esperada da variante equivale à do original.
3. **Ambiguidade e vazamento:** há outra resposta correta plausível? A variante contém a resposta?
4. **Distância:** superfície suficientemente diferente do original, com similaridade semântica alta.
5. **Pré-triagem de dificuldade** por modelos de linguagem (a abordagem de Liu et al. 2026) e, depois, pela taxa de falha por variante.
6. **Amostra revisada por humano** e botão "variante ruim" no add-on.

### 5.5 Entrega e registro no Anki (ganchos verificados nesta rodada)

| Necessidade | Gancho do Anki |
|---|---|
| Tempo até revelar | `reviewer_did_show_question` e `reviewer_did_show_answer` |
| Mostrar a variante | `card_will_show` ("pode modificar o texto do cartão antes da revisão"). O lado da resposta costuma reexibir a frente: é preciso trocar nos dois lados |
| Registrar o resultado | `reviewer_did_answer_card` |
| Não reagendar (modo sonda) | `reviewer_will_answer_card` permite "contornar a avaliação" do cartão |
| Comunicação com a interface web | `webview_did_receive_js_message` |

Fonte: [`genhooks_gui.py`](https://github.com/ankitects/anki/blob/main/qt/tools/genhooks_gui.py) do Anki. O código do Anki é AGPL-3; conferir implicações de licença †. Alternativa: um app próprio com ts-fsrs ou py-fsrs, com mais controle e sem usuários prontos.

### 5.6 Escopo mínimo

- Notas de texto (Básico e Cloze), em português e inglês.
- Três ou quatro tipos de variante de mundo fechado.
- Pipeline de geração e validação, **agnóstico quanto ao LLM** (local ou API).
- Add-on: registro (tempo até revelar, acerto, variante exibida), sorteio no horário devido, relatório.
- **Fora do escopo:** agendador próprio, variantes de mundo aberto, imagens e áudio, aplicação automática da rotação.

---

## 6. Como mediríamos

### 6.1 Camadas

| Camada | Pergunta | Dados | Medida |
|---|---|---|---|
| **E1** Validade das variantes | O pipeline gera variantes válidas sem conhecimento externo? | Variantes de cartões reais | Porcentagem válida por tipo (revisão humana), erros típicos, custo e latência |
| **E2** Penalidade da variante | Cartões suspeitos sofrem queda maior que os controles quando o enunciado muda? | Microrrandomização no horário devido | Interação suspeito × variante no acerto, com intervalo de confiança |
| **E3** Validade dos sinais | Os sinais de candidato preveem a penalidade? | Mesmos dados e histórico | AUC ou correlação; comparação com sorteio aleatório |
| **E4** Efeito da rotação (exploratório) | Rotacionar variantes reduz a penalidade depois? | Piloto dentro de cada usuário | Penalidade em sondas futuras; lapsos e minutos extras |
| **E5** Custo e usabilidade | Compensa o esforço? | Registro e questionário | Minutos e lapsos extras; aceitação; SUS |

### 6.2 E2: o núcleo do estudo

- **Unidade:** uma revisão de um cartão no horário devido.
- **Estratos:** suspeito (definido **antes** do sorteio) e controle (emparelhado por número de revisões e intervalo).
- **Sorteio por revisão:** original ou variante (50% cada), com variante **nova** a cada exposição.
- **Desfecho:** acerto (0/1) pela autoavaliação, ou resposta digitada se o usuário optar.
- **Modelo:** regressão logística mista: acerto ~ variante × suspeito + recordação prevista (FSRS) + tipo de variante + efeitos aleatórios por usuário e por cartão. A **interação** mede a dependência de forma; o efeito principal da variante mede a dificuldade média das variantes.
- **Reforços:** duas variantes diferentes do mesmo cartão (se as duas falham, a evidência é maior); dose-resposta (paráfrase < reordenação < reformatação).
- **Tamanho (cálculo meu, aproximação sem agrupamento, α = 0,05, poder 80%; as premissas de acerto são minhas):**

| Cenário | Premissas | Revisões por braço, por grupo |
|---|---|---|
| Penalidade moderada | Suspeitos: 98% no original e 83% na variante; controles: 90% e 87% (diferença de diferenças de 12 pp) | ≈ 200 (≈ 800 no total) |
| Penalidade grande | Suspeitos: 98% e 73%; controles: 90% e 87% (22 pp) | ≈ 70 (≈ 280 no total) |

- **Viabilidade:** cartões suspeitos são maduros, com intervalos longos, e geram poucas revisões por cartão. O fator limitante é o **tamanho da coleção** (milhares de cartões maduros) ou o número de usuários. Alternativa: antecipar revisões em um baralho filtrado, com ajuste pela recordação prevista.

### 6.3 E1, E3, E4, E5

- **E1:** taxa de variantes válidas por tipo (juiz humano sobre amostra; critério: resposta preservada, sem ambiguidade, sem vazamento), comparando modelos locais e de nuvem; custo e latência por variante.
- **E3:** o escore de candidato (sequência, tempo até revelar, PMI, formato) contra a penalidade observada; baseline: sorteio aleatório de cartões.
- **E4 (exploratório):** sortear por nota, entre cartões suspeitos, **rotação** versus **estático**; desfecho: penalidade em sondas posteriores; custo: lapsos e minutos. Poder baixo; reportar estimativa com intervalo e replicar entre pessoas.
- **E5:** minutos e lapsos extras por semana de uso, fração de variantes descartadas como ruins, questionário SUS.

### 6.4 O que os colegas agregam

| Cenário | Dá para fazer | Não dá |
|---|---|---|
| Só você | E1 e E2 com o seu volume de cartões (muitos eventos por usuário); E3 e E5 | Generalizar para outras pessoas e áreas |
| Você e cerca de 3 colegas | Replicação entre pessoas; baralhos e áreas diferentes; mais cartões suspeitos; E4 com réplica | Estimativas para a população geral |

Diferente de propostas anteriores, aqui os colegas **não são indispensáveis**: a unidade de análise é a revisão, e o seu uso já pode gerar centenas de eventos.

### 6.5 Ameaças à validade

| Tipo | Ameaça | Mitigação |
|---|---|---|
| Construto | "Suspeito" e "dependência de forma" são operacionalizações | Definições fixadas antes; sensibilidade; vários sinais |
| Interna | Dificuldade da variante, esquecimento, sequência, regressão à média | Controles, sorteio por revisão, ajuste pela recordação prevista |
| Externa | Poucos usuários e baralhos de texto conceitual | Declarar o escopo; réplica entre pessoas |
| Conclusão | Autoavaliação; múltiplas comparações | Resposta digitada opcional; desfecho primário único; pré-registro (OSF †) |

---

## 7. A tese

### 7.1 Formulações

| Versão | Enunciado |
|---|---|
| **Núcleo (diagnóstico)** | Cartões que o usuário responde de modo consistente e rápido, ou cujo enunciado é identificável pelas palavras iniciais, sofrem queda de acerto **maior que cartões de controle** quando o enunciado é substituído por variantes semanticamente equivalentes. Essa dependência da forma do cartão é mensurável e pode ser prevista por sinais baratos |
| **Habilitadora (pipeline)** | Um pipeline com LLM e verificação gera, **só a partir do texto do cartão**, variantes válidas em proporção aceitável, sem conhecimento externo da matéria |
| **Exploratória (intervenção)** | Alternar variantes nos cartões com alta dependência reduz a queda de acerto em sondas posteriores, a um custo de revisões aceitável |

**Recomendada (as três, com pesos diferentes):**

> A memorização do formato do cartão (dependência da forma) pode ser medida em usuários reais de repetição espaçada por meio de variantes de mundo fechado geradas por LLM e validadas automaticamente; cartões respondidos de modo consistente e rápido apresentam penalidade de variante maior que cartões de controle; e a rotação de variantes é estudada de forma exploratória.

### 7.2 Hipóteses e critérios de refutação

| Hipótese | Refutada se |
|---|---|
| **H1 (pipeline).** Uma proporção definida antes de variantes é válida por revisão humana, por tipo | A proporção fica abaixo do limiar combinado ou os erros exigem conhecimento externo |
| **H2 (penalidade).** A interação suspeito × variante é positiva (suspeitos perdem mais acerto) | O intervalo de confiança da interação inclui zero |
| **H3 (sinais).** Os sinais de candidato preveem a penalidade melhor que o acaso | A AUC não supera o baseline aleatório |
| **H4 (rotação, exploratória).** A rotação reduz a penalidade em sondas posteriores | A estimativa tem o sinal oposto ou o intervalo não exclui efeito nulo (reportar assim) |
| **H5 (custo).** O custo extra em minutos e lapsos é aceitável | O custo supera o limiar combinado |

Limiares numéricos devem ser fixados **antes** de olhar os dados. **Resultado nulo é informativo:** se não há penalidade, a dependência de forma é pequena nos baralhos testados, o que também é uma contribuição.

### 7.3 Objetivos (rascunho)

**Objetivo geral:** desenvolver e avaliar uma prova de conceito que mede a dependência da forma do cartão em repetição espaçada, comparando o acerto em cartões originais e em variantes equivalentes geradas por LLM.

**Objetivos específicos:**

1. Levantar a literatura e as ferramentas sobre variação de cartões e "pattern matching".
2. Definir operacionalmente "dependência da forma", "cartão suspeito" e "variante de mundo fechado".
3. Implementar o pipeline de geração e validação e o add-on de registro e sorteio.
4. Avaliar a validade das variantes (E1).
5. Estimar a penalidade da variante em suspeitos e controles (E2) e a validade dos sinais (E3).
6. Explorar o efeito da rotação (E4) e o custo (E5).
7. Discutir ameaças à validade e limitações.

**Metodologia:** Design Science Research ([Hevner et al. 2004](https://doi.org/10.2307/25148625); [Peffers et al. 2007](https://doi.org/10.2753/mis0742-1222240302)); a avaliação em E2 segue o desenho microrrandomizado ([Klasnja et al. 2015](https://doi.org/10.1037/hea0000305); [Qian et al. 2022](https://doi.org/10.1037/met0000283)).

### 7.4 Delimitações

Só texto; só variantes de mundo fechado; sem alegar melhora de aprendizagem de longo prazo; "aprendeu o conteúdo" é substituído por "recordação robusta a mudanças de forma".

---

## 8. Experimento-relâmpago (sem código)

Objetivo: ver, antes de programar, se variantes de cartões "sempre acertados" falham com frequência e se as variantes geradas fazem sentido. **Não é conclusivo** (não há controle), mas informa o tamanho do efeito e a qualidade das variantes.

1. **Seleção.** No Navegador do Anki, busque `prop:reps>=8 prop:lapses=0` (sintaxe conforme o [manual de busca](https://docs.ankiweb.net/searching.html)) e escolha 30 cartões de texto (Básico ou Cloze), espaçados na lista para não escolher só os do começo.
2. **Variantes.** Em qualquer LLM, para cada cartão, peça duas variantes (uma paráfrase e uma reordenação ou reformatação) com a regra: "a resposta esperada deve estar contida no cartão; não use informação externa". **Não leia as variantes com atenção**: cole-as numa planilha e embaralhe as 60 linhas.
3. **Teste cego.** Responda cada variante **digitando** a resposta antes de olhar o cartão original. Depois classifique: certo, parcial, errado, ou "variante ruim" (ambígua ou com resposta diferente).
4. **Análise.** Calcule a taxa de erro entre as variantes válidas, por tipo. Leia os erros e classifique: dependência de forma, variante ambígua, esquecimento.
5. **Leitura (julgamento meu):** poucos erros (menos de ~10%) sugerem DFC pequena nesses cartões; 25% ou mais é promissor e já ajuda a dimensionar o E2. Se muitas variantes forem "ruins", o gargalo é o pipeline, não a hipótese.

---

## 9. É uma boa ideia? Veredito

**A favor:**
- O problema é reconhecido pela comunidade ("pattern matching") e previsto pela teoria (especificidade de codificação, ilusão de saber).
- É **testável de forma limpa**: sorteio por revisão no horário devido, com controles. Cada revisão é um evento, então um usuário com muitos cartões gera dados suficientes.
- É sua ideia e preserva a motivação original; o artefato (add-on com LLM e validação) é rico em engenharia de software.
- Mesmo um resultado nulo é informativo.

**Contra:**
- A rotação de variantes não é novidade, e o benefício da variação é incerto (Cowan; Serrano; Brunmair).
- Variantes podem ser mais difíceis por motivos alheios à memorização do formato (por isso o controle).
- LLM erra; a validação é parte do trabalho.
- Cartões suspeitos são maduros: poucas revisões por cartão, então a coleção precisa ser grande.
- Pode aumentar lapsos e carga.

**É boa se** a tese for centrada em medir (diagnóstico) e o escopo ficar em variantes de mundo fechado. **É má se** o objetivo for "um produto novo" ou se você quiser alegar "melhora a aprendizagem".

**Critérios para seguir depois do experimento-relâmpago (julgamento meu):** (a) uma fração relevante das variantes válidas falha (cerca de 20% ou mais); (b) a maioria das variantes é válida; (c) o seu volume de cartões maduros permite acumular algumas centenas de revisões de suspeitos.

---

## 10. Próximos passos e perguntas

1. Rodar o **experimento-relâmpago** da seção 8 e anotar: variantes válidas, taxa de erro por tipo, exemplos de falhas.
2. Decidir o escopo: núcleo e habilitadora (recomendado), rotação como exploratória.
3. Host: add-on do Anki (recomendado, porque os ganchos existem) ou app próprio.
4. LLM: manter o pipeline agnóstico (local ou API), como você sugeriu.
5. Só depois, liberar a implementação.

Perguntas:

- Quantos cartões maduros você tem (`prop:ivl>=60`) e o FSRS está ativado?
- Você aceita que o resultado possa mostrar que o problema é pequeno?
- Prefere o produto criar **cartões-irmãos** com as variantes (como você descreveu) ou **rotacionar** no próprio cartão? (Para medir, a rotação com sorteio é melhor; para o produto, os irmãos são mais simples.)

---

## 11. Referências

**Verificadas nesta rodada (título e DOI no OpenAlex; autores e conteúdo de memória quando indicado †):** [Tulving & Thomson 1973](https://doi.org/10.1037/h0020071); [Morris et al. 1977](https://doi.org/10.1016/s0022-5371(77)80016-9); [Reyna & Brainerd 1995](https://doi.org/10.1016/1041-6080(95)90031-4); [Chi et al. 1981](https://doi.org/10.1207/s15516709cog0502_2); [Koriat & Bjork 2005](https://doi.org/10.1037/0278-7393.31.2.187); [Butler 2010](https://doi.org/10.1037/a0019902); [Rohrer et al. 2010](https://doi.org/10.1037/a0017678) (autores †); [Carpenter 2012](https://doi.org/10.1177/0963721412452728); [Butler et al. 2017](https://doi.org/10.1037/xap0000142); [Paas & van Merriënboer 1994](https://doi.org/10.1037//0022-0663.86.1.122); [Kahana 2002](https://doi.org/10.3758/bf03195769); [Gierl & Haladyna 2012](https://doi.org/10.4324/9780203803912); [Brysbaert 2019](https://doi.org/10.1016/j.jml.2019.104047); [Geirhos et al. 2020](https://doi.org/10.1038/s42256-020-00257-z); [Hoel 2021](https://doi.org/10.1016/j.patter.2021.100244); [Liu et al. 2026](https://arxiv.org/abs/2602.05114) e [Chen et al. 2023](https://arxiv.org/abs/2310.14498) (resumos lidos).

**Comunidade e ferramentas (páginas lidas):** [Expertium, "Note Types to Avoid Pattern Matching"](https://expertium.github.io/Avoid_Pattern_Matching.html); [Matuschak, "How to write good prompts"](https://andymatuschak.org/prompts/); [Dynamic Cards](https://ankiweb.net/shared/info/1902186394) ([GitHub](https://github.com/Petronian/dynamic-cards), não aberto); [AnkiAIUtils](https://github.com/thiswillbeyourgithub/AnkiAIUtils); [ganchos do Anki](https://github.com/ankitects/anki/blob/main/qt/tools/genhooks_gui.py); [busca do Anki](https://docs.ankiweb.net/searching.html); threads do Reddit citados (só trechos de busca).

**Reaproveitadas das fases anteriores:** Pan & Rickard 2018; Cowan et al. 2024; Serrano & Pellicer-Sánchez 2026; Brunmair & Richter 2019; An et al. 2026; Klasnja et al. 2015; Qian et al. 2022; Hevner et al. 2004; Peffers et al. 2007; manual do Anki (ordem das revisões); fórum 55947 e issue 3626; Pass/Fail Review.

**Marcadas †:** autores de itens sem informação no OpenAlex; conteúdo dos clássicos listados em "Como ler"; taxa de leitura de 238 palavras por minuto; implicações da licença AGPL; pré-registro no OSF.

---

## 12. Limitações desta pesquisa

- Busca ampla, mas não sistemática; sem bases pagas; Semantic Scholar indisponível.
- Quase tudo foi lido por resumo, título ou trecho de página. Os clássicos de psicologia foram verificados só quanto à existência e ao título.
- O Dynamic Cards foi avaliado pela página do AnkiWeb; não testei nenhuma ferramenta. Os threads do Reddit foram vistos só em trechos de busca.
- A evidência de que **variar** melhora o aprendizado em flashcards é mista e indireta; a de que a DFC **existe e é grande** em usuários reais é, até onde vi, de relatos e teoria, sem medição. Medi-la é exatamente a proposta.
- Os cálculos de poder usam premissas minhas e ignoram o agrupamento por cartão e por usuário.
- "Não encontrei" significa busca rápida, não inexistência.
