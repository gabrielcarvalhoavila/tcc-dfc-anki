# Fundamentação: dependência da forma do cartão (DFC)

Síntese do que sustenta o projeto, extraída das cinco fases de pesquisa de 14 a 20/10/2026. Os textos originais foram removidos na limpeza de 20/10 e estão no histórico do Git (commit "Snapshot antes da limpeza"). **† = vem da minha memória e não foi verificado.** "Não encontrei" significa busca rápida, não inexistência. Quase tudo foi lido por resumo, título ou trecho de página.

---

## 1. O fenômeno e a definição

- **Comunidade do Anki:** "pattern matching", ou memorizar como a resposta se parece em vez da informação ([Expertium](https://expertium.github.io/Avoid_Pattern_Matching.html)). [Matuschak](https://andymatuschak.org/prompts/) inclui "desencorajar pattern matching" entre os testes de qualidade de um cartão e diz que clozes copiados de textos são particularmente suscetíveis.
- **Psicologia:** especificidade de codificação, processamento adequado à transferência e dependência de pista (seção 3).
- **Analogia de aprendizado de máquina (só analogia):** sobreajuste a exemplos específicos. A diferença de acerto entre o cartão original e uma variante seria um "gap de generalização".
- **Nome adotado:** **dependência da forma do cartão (DFC)**. Medida: **penalidade da variante**, a queda de acerto quando a forma do enunciado muda. "Overfitting visual" não é termo acadêmico e foi abandonado.

---

## 2. O que "acertou, aprendeu; errou, decorou" permite concluir

| Original | Variante | Leitura mais provável | Outras explicações |
|---|---|---|---|
| Acertou | Acertou | Recordação robusta à forma | Memorizou também a variante (se repetida); variante fácil |
| Acertou | **Errou** | **Dependência da forma** (a hipótese) | Variante mais difícil; ambígua ou errada; direção invertida; lapso aleatório |
| Errou | Acertou | Rara | Original ambíguo; acaso |
| Errou | Errou | Esqueceu de fato | Não diz nada sobre a forma |

"Errou a variante" é um sinal **probabilístico** e só significa algo **em comparação** com cartões de controle (seção 6). "Aprendeu o conteúdo" também é forte demais: o que a variante mostra é **robustez da recordação a mudanças de forma**, um tipo de transferência próxima.

---

## 3. Evidência a favor

| # | Afirmação | Fontes | Força e limite |
|---|---|---|---|
| A1 | Usuários e autores descrevem o problema | Expertium; Matuschak (cloze copiado de texto; "false positives: como você poderia acertar sem saber?"); manual do Anki (a ordem "Deck, then due date" facilita adivinhar pelo contexto); [fórum 55947](https://forums.ankiweb.net/t/image-occlusion-and-the-problem-of-excess-context-in-flashcards/55947) (decorar a ordem das lacunas) e [issue 3626](https://github.com/ankitects/anki/issues/3626); threads do [r/Anki](https://www.reddit.com/r/Anki/comments/1cy11e1/how_do_you_ensure_that_youre_recalling_the_cards/) e do [r/medicalschoolanki](https://www.reddit.com/r/medicalschoolanki/comments/kab906/does_anyone_else_have_this_memory_issue/) (só trechos de busca) | Média: prática e relatos, sem medição. O autor do deck no fórum argumenta que o efeito é pequeno e que o RMSE do FSRS já o absorveria |
| A2 | A teoria prevê dependência de pista | [Tulving & Thomson 1973](https://doi.org/10.1037/h0020071) (especificidade de codificação); [Morris et al. 1977](https://doi.org/10.1016/s0022-5371(77)80016-9) (processamento adequado à transferência); [Reyna & Brainerd 1995](https://doi.org/10.1016/1041-6080(95)90031-4); [Chi et al. 1981](https://doi.org/10.1207/s15516709cog0502_2) (novatos usam pistas superficiais); [Appleton-Knapp et al. 2005](https://doi.org/10.1086/432236) (variabilidade × espaçamento); [Carpenter & DeLosh 2006](https://doi.org/10.3758/bf03193405) | Forte como teoria; a magnitude em flashcards é desconhecida |
| A3 | Estudar com a mesma pista do teste gera ilusão de saber | [Koriat & Bjork 2005](https://doi.org/10.1037/0278-7393.31.2.187); Benjamin, Bjork & Schwartz 1998 † | Média a forte (laboratório) |
| A4 | Prática de recuperação tende a transferir, menos para pares estímulo-resposta rearranjados | [Butler 2010](https://doi.org/10.1037/a0019902); [Rohrer et al. 2010](https://doi.org/10.1037/a0017678); [Carpenter 2012](https://doi.org/10.1177/0963721412452728); [Butler et al. 2017](https://doi.org/10.1037/xap0000142); [Pan & Rickard 2018](https://doi.org/10.1037/bul0000151) (192 tamanhos de efeito, 122 experimentos, N = 10.382; d = 0,40 [0,31; 0,50]; mais fraco para itens rearranjados e materiais não testados) | Forte. Implica que parte da generalização vem "de graça" e que a DFC será **heterogênea** entre cartões, o que torna a medição interessante |
| A5 | Variar a prática melhora a transferência ao custo da aquisição | [Paas & van Merriënboer 1994](https://doi.org/10.1037//0022-0663.86.1.122) (exemplos trabalhados variados) | Média; outro domínio |
| A6 | Gerar variantes isomórficas com IA e validá-las é viável | [Liu et al. 2026](https://arxiv.org/abs/2602.05114) (física: 73% dos bancos com dificuldade homogênea; modelos de linguagem ajudam a achar variantes problemáticas); [Chen et al. 2023](https://arxiv.org/abs/2310.14498) (diferenças de 5 a 10 pontos percentuais, comparáveis às entre versões isomórficas); [Gierl & Haladyna 2012](https://doi.org/10.4324/9780203803912); [An et al. 2025](https://arxiv.org/abs/2507.05629) (questões de recuperação por LLM: 89% vs. 73% de acerto, cerca de 60 alunos) | Média; domínio diferente (problemas de física, não flashcards) |
| A7 | Analogia com aprendizado de máquina | [Geirhos et al. 2020](https://doi.org/10.1038/s42256-020-00257-z) (atalhos); [Hoel 2021](https://doi.org/10.1016/j.patter.2021.100244) (só o título foi lido) | Só analogia; não é evidência sobre pessoas |
| A8 | Há demanda e experimentação | Dynamic Cards, tipos de nota randomizados, Reformulator (seção 5); [Memdora](https://arxiv.org/abs/2607.25096) (preprint de 2026; 17 tipos de interação sobre FSRS-6; sem resultado de aprendizagem no resumo) | Demanda, não eficácia |

---

## 4. Contraponto

| # | Objeção | Fontes | Como o projeto lida |
|---|---|---|---|
| C1 | Para associações arbitrárias, a especificidade pode ser o objetivo e variar não ajuda | [Cowan et al. 2024](https://doi.org/10.1073/pnas.2311077121) (variabilidade ajuda memória de item, não a associativa); [Serrano & Pellicer-Sánchez 2026](https://discovery.ucl.ac.uk/id/eprint/10216384/) (92 aprendizes de inglês: variação de contexto aumentou o esforço e não facilitou a recordação); [Brunmair & Richter 2019](https://doi.org/10.1037/bul0000209) (intercalar prejudica com palavras, g = −0,39) | Escopo: cartões **conceituais**; excluir vocabulário, números e datas |
| C2 | Prompts devem produzir respostas consistentes | Matuschak (interferência; "retrieval-induced forgetting") | Variantes mudam o enunciado, **nunca a resposta esperada** |
| C3 | Errar a variante não prova que decorou | Versões isomórficas diferem em dificuldade da ordem de 5 a 10 pontos percentuais (Chen et al. 2023) e 27% dos bancos não tiveram dificuldade homogênea (Liu et al. 2026); a direção inversa de uma associação tem dificuldade própria ([Kahana 2002](https://doi.org/10.3758/bf03195769), resumo não lido) | Seção 6 |
| C4 | Variantes aumentam lapsos e carga | Paas & van Merriënboer 1994 | Medir o custo (E5); metade das revisões elegíveis fica no original |
| C5 | Variação imprevisível pode irritar | Matuschak: "o mais importante a otimizar é a conexão emocional com as sessões de revisão" | Botão "variante ruim" e opção de desligar |
| C6 | LLMs erram e custam; privacidade | [An et al. 2026](https://arxiv.org/abs/2609.27063) (dificuldade rotulada por LLM quase não prevê a empírica, ρ ≈ 0,06); o Dynamic Cards avisa que "os cartões podem nem sempre ficar certos"; [Bastani et al. 2025](https://doi.org/10.1073/pnas.2422633122) (IA sem salvaguardas pode prejudicar a aprendizagem) | Validação em camadas, auditoria humana, modo local opcional |
| C7 | Autoavaliação é subjetiva | Fase 2 (removida) | Réplica com outra pessoa; resposta digitada fica como extensão |

---

## 5. O que já existe

| Componente | O que existe | Avaliação publicada? |
|---|---|---|
| Variar o cartão por LLM a cada revisão | [Dynamic Cards](https://ankiweb.net/shared/info/1902186394) (add-on; Mistral ou Gemini; mostra o original na primeira vez e depois um reescrito; até 3 versões por padrão; atualizado em 2026-08-13; avisa que o LLM pode errar) | Nenhuma encontrada |
| Variantes escritas à mão e sorteadas | Tipos de nota do [Expertium e Vilhelm Ian](https://expertium.github.io/Avoid_Pattern_Matching.html) ([deck](https://ankiweb.net/shared/info/171015247)): Randomized Cloze e Basic (versões separadas por barra vertical, sorteadas a cada revisão), Shuffled Cloze, Match Pairs | Nenhuma |
| Reescrita por IA | [AnkiAIUtils](https://github.com/thiswillbeyourgithub/AnkiAIUtils) (Reformulator) | Nenhuma |
| Escolher candidatos por comportamento | Não encontrei | Não |
| Registrar qual variante foi mostrada e o resultado | Não encontrei; o histórico nativo do Anki não registra qual versão foi exibida | Não |
| Medir a penalidade da variante | Não encontrei. No OpenAlex, "paraphrase" no título com "flashcards" no resumo retorna 0; no arXiv, "question paraphrase" com flashcard, repetição espaçada ou prática de recuperação retorna 0 | Não |

**Veredito de novidade:** variar cartões **não é novidade**. Os espaços abertos são: **(a)** escolher quais cartões variar, **(b)** **medir** a diferença entre original e variante (diagnóstico), **(c)** avaliar se a rotação ajuda e a que custo. Este projeto cobre (a) e (b); (c) fica como trabalho futuro.

**Pesquisa com LLM e repetição espaçada (contexto):**
- [KARL](https://arxiv.org/abs/2402.12291) (EMNLP 2024): agendador sensível ao texto do cartão (BERT + DKT); 123 mil logs; avaliação online com 27 usuários.
- [LECTOR](https://arxiv.org/abs/2508.03275): preprint de um autor, avaliado em aprendizes **simulados**; evidência fraca.
- [SmartFlash](https://arxiv.org/abs/2602.14431) (ISLS 2026, 6 alunos): querem saídas de IA editáveis e transparentes.
- [Kortemeyer 2023](https://arxiv.org/abs/2309.09338): correção de respostas curtas por GPT-4 comparável a modelos artesanais e pior que modelos especializados.

**FSRS (contexto):** modelo DSR e agendador treinável por usuário (Ye et al., KDD 2022 e TKDE 2023; DOI não conferido). FSRS-6 tem 21 parâmetros e está no Anki desde a 25.07; existe FSRS-7 (34 parâmetros, intervalos fracionários). No [benchmark aberto](https://github.com/open-spaced-repetition/srs-benchmark) (cerca de 10 mil usuários, 350 milhões de revisões), FSRS-6 tem log loss 0,346 e AUC 0,703, contra 0,277 e 0,833 do RWKV-Instant, que usa atributos extras, entre eles a duração da revisão.

---

## 6. Por que errar a variante não prova (ameaças à inferência)

| Ameaça | Por que atrapalha | Mitigação no protocolo |
|---|---|---|
| Dificuldade intrínseca da variante | Variante mais difícil parece dependência de forma | **Controles** recebem as mesmas variantes; o efeito principal da variante mede a dificuldade média; auditoria das variantes |
| Direção inversa | Responder da resposta para a pergunta é naturalmente diferente | Inversão fica fora do índice principal |
| Esquecimento verdadeiro | Errar por ter esquecido, não por depender da forma | Sorteio **na revisão devida**; covariáveis de intervalo e de dias desde a última revisão |
| Contaminação sequencial | Ver a resposta do original e logo depois a variante infla o acerto | Uma forma por exposição; nunca original e variante na mesma sessão |
| Variante ambígua ou errada | Falha que não é do aluno | Validação automática, auditoria humana, botão "variante ruim" |
| Regressão à média e seleção | Cartões "sempre acertados" tendem a ter acertos futuros menores por acaso | Suspeitos definidos **antes** do sorteio; controles recebem o mesmo tratamento |
| Treinar a variante | Se a mesma variante se repete, vira nova forma decorada | Variante **nova** a cada exposição |
| Autoavaliação | Quem decorou pode achar que sabe | Réplica com outra pessoa; resposta digitada como extensão |
| Atenção e novidade | Qualquer mudança desperta atenção | Variantes também nos controles |

---

## 7. Dados públicos não bastam

- Os datasets públicos de revlog (por exemplo, [anki-revlogs-10k](https://huggingface.co/datasets/open-spaced-repetition/anki-revlogs-10k)) não têm o texto do cartão nem registram qual versão foi exibida; não permitem testar a hipótese. É preciso coletar dados próprios.
- Neles, `duration` é o tempo total até a nota (o timer do Anki vai da exibição da pergunta até o botão, com teto de 60 s). O tempo **até revelar** não existe nesses dados, por isso o add-on o mede.

---

## 8. Referências

**Verificadas (título e DOI no OpenAlex; conteúdo dos clássicos de memória †):** Tulving & Thomson 1973; Morris et al. 1977; Reyna & Brainerd 1995; Chi et al. 1981; Appleton-Knapp et al. 2005; Carpenter & DeLosh 2006; Koriat & Bjork 2005; Butler 2010; Rohrer et al. 2010 (autores †); Carpenter 2012; Butler et al. 2017; Pan & Rickard 2018; Paas & van Merriënboer 1994; Cowan et al. 2024; Brunmair & Richter 2019; Kahana 2002; Gierl & Haladyna 2012; Geirhos et al. 2020; Hoel 2021; Bastani et al. 2025; [Klasnja et al. 2015](https://doi.org/10.1037/hea0000305); [Qian et al. 2022](https://doi.org/10.1037/met0000283); [Hevner et al. 2004](https://doi.org/10.2307/25148625); [Peffers et al. 2007](https://doi.org/10.2753/mis0742-1222240302); [Brysbaert 2019](https://doi.org/10.1016/j.jml.2019.104047); [Lindsey et al. 2014](https://doi.org/10.1177/0956797613504302); [Kang 2016](https://doi.org/10.1177/2372732215624708). Preprints e arXiv (resumos lidos): Liu et al. 2026; Chen et al. 2023; An et al. 2025 e 2026; Kortemeyer 2023; KARL; LECTOR; Memdora; SmartFlash.

**Comunidade e ferramentas (páginas lidas):** Expertium, "Note Types to Avoid Pattern Matching"; Matuschak, "How to write good prompts"; Dynamic Cards; AnkiAIUtils; [ganchos do Anki](https://github.com/ankitects/anki/blob/main/qt/tools/genhooks_gui.py); [busca do Anki](https://docs.ankiweb.net/searching.html); [Pass/Fail Review](https://forums.ankiweb.net/t/53872) (add-on que mede do exibir a pergunta ao revelar); [srs-benchmark](https://github.com/open-spaced-repetition/srs-benchmark).

**Marcadas †:** conteúdo dos clássicos de psicologia; Benjamin, Bjork & Schwartz 1998; taxa de leitura de 238 palavras por minuto (Brysbaert 2019); implicações da licença AGPL do Anki; pré-registro no OSF; DOI de Ye et al.

---

## 9. Limitações

- Busca ampla, mas não sistemática; sem bases pagas; Semantic Scholar indisponível.
- O Dynamic Cards foi avaliado pela página do AnkiWeb; nenhuma ferramenta foi testada.
- A evidência de que **variar** melhora o aprendizado em flashcards é mista e indireta; a de que a DFC **existe e é grande** em usuários reais é, até onde vi, de relatos e teoria, sem medição. Medi-la é a proposta do projeto.
