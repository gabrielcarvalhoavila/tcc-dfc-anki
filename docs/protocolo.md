# Protocolo e plano: dependência da forma do cartão (DFC)

**Versão 1.2, 2026-10-20. Congelado** com a tag Git `protocolo-v1.2` (as `protocolo-v1` e `protocolo-v1.1` ficam como histórico; ver "Histórico de versões"). Mudanças até o primeiro sorteio (2/11) geram nova versão e nova tag; depois disso, qualquer mudança é um desvio registrado em [`desvios.md`](desvios.md) (seção 13). Contexto e evidências: [fundamentação](fundamentacao.md). Hipóteses e objetivos: [projeto](projeto.md). Piloto: [piloto-relampago](piloto-relampago.md).

**Como ler.** **(premissa)** = número meu, de calibração, não verificado em dados do estudo. † = vem da minha memória, não verifiquei. As datas da seção 11 são limites derivados da entrega (4/12) e da apresentação (18/12), não estimativas de esforço.

**Histórico de versões.**

| Versão | Data | Mudanças |
|---|---|---|
| v1 | 20/10/2026 | Versão inicial (tag `protocolo-v1`, commit `e4d5eff`) |
| v1.1 | 20/10/2026 | Antes de qualquer sorteio e de qualquer variante gerada. (1) O sorteio só ocorre se a última revisão do cartão foi em outro dia do Anki (seções 5, 6.3 e 6.3.1). (2) Esclarece que `reps` conta respostas em passos de aprendizado; o add-on registra `n_reviews` e a análise ganha uma sensibilidade com `n_reviews ≥ 5` (seções 5 e 7). (3) Resposta desfeita (sem par no histórico de revisões do Anki, ou substituída por outra do mesmo cartão e do mesmo `reps`) é erro do add-on (seções 5, 6.3 e 8). Hipóteses, desfecho e limiares não mudam. |
| v1.2 | 20/10/2026 | Antes de qualquer sorteio e de qualquer variante gerada. Adapta o desenho ao participante principal, o irmão (estudante de vestibular), cujas fichas são Cloze com várias lacunas ocultas juntas e imagem. (1) Elegibilidade: Cloze com 1 a 3 lacunas ocultas ao mesmo tempo no mesmo cartão e com imagens, que ficam fixas; áudio, vídeo, fórmula e mídia na resposta seguem fora; texto visível de pelo menos 30 caracteres; respostas todas numéricas, Image Occlusion e baralhos de inglês ficam fora (seções 4.1 e 4.2). (2) Variantes do Cloze: `pergunta` (LLM) e `sem_imagem` (determinística); o Básico mantém os quatro tipos (seção 6.1); a auditoria passa a perguntar se o texto sozinho basta (6.2). (3) O add-on registra `note_kind`, `n_blanks` e `has_image` (6.3); a análise agrupa por nota, acrescenta essas covariáveis e ganha sensibilidades para o efeito de escala (seção 7). Hipóteses, desfecho, definição de suspeito e limiares não mudam. |

---

## 1. Em uma página

| Item | Definição |
|---|---|
| Pergunta | Cartões que o usuário acerta de modo consistente ("suspeitos") perdem mais acerto, quando o enunciado muda, do que os demais ("controles")? |
| Desenho | Experimento microrandomizado dentro do usuário ([Klasnja et al. 2015](https://doi.org/10.1037/hea0000305); [Qian et al. 2022](https://doi.org/10.1037/met0000283)): a cada revisão elegível de outro dia do Anki, o add-on sorteia original ou variante (50/50) e registra o que foi mostrado |
| Desfecho primário | Falha = botão "Again" |
| Medida primária | Diferença de diferenças (DiD), em pontos percentuais: [falha(variante) − falha(original)] nos suspeitos, menos o mesmo nos controles |
| Confirmatórias | H1 (variantes válidas) e H2 (penalidade maior em suspeitos) |
| Exploratórias | H3 (sinais de candidato) e custo/usabilidade. Rotação (H4/E4) fica fora (seção 3) |
| Resultado nulo | Vale como resultado: os critérios das seções 7 e 8 são fixados antes dos dados |

---

## 2. Calibração pelo piloto

No [experimento-relâmpago](piloto-relampago.md), 12 conceitos que a pessoa sabia foram testados como original e como variante em sessões separadas: **0/12 falhas nas variantes** (IC 95% ≈ 0–26%). Lições incorporadas:

1. Variantes brandas não derrubaram o acerto de cartões curtos "O que é X?". A DFC, se existe, deve estar em **suspeitos** ou em variantes mais fortes; o piloto não testou nenhum dos dois.
2. Original e variante do mesmo cartão no mesmo arquivo deixam copiar a própria resposta. No estudo: **uma forma por exposição**, nunca as duas na mesma sessão.
3. Inversão (descrição → termo) entrega a resposta das outras formas: tipo secundário, sempre com uma forma por exposição.
4. 12 pares só excluem efeitos acima de ~26%: o estudo precisa de centenas de eventos (seção 8).
5. Um único corretor e a autoavaliação são fontes de viés: mitigar com réplica (irmão) e, se houver prazo, resposta digitada com correção cega (6.7).
6. Quando todos os cartões de uma coleção seguem o mesmo molde (como as fichas do irmão: título, imagem e linhas "rótulo: lacuna"), uma variante branda quase não muda o que a pessoa já viu, e um resultado nulo seria pouco informativo. Por isso o Cloze passa a ter variantes que mudam o estilo (`pergunta`) ou tiram a imagem (`sem_imagem`) (v1.2, seção 6.1).

---

## 3. Escopo

| Camada | Entra? | Papel |
|---|---|---|
| E1 validade das variantes | Sim | Confirmatória (H1) |
| E2 penalidade da variante | Sim | Confirmatória (H2): núcleo do TCC |
| E3 sinais de candidato (tempo até revelar, prefixo mínimo identificador) | Sim, exploratória | Registrar desde o primeiro dia; sem limiar de decisão |
| E4 rotação de variantes | **Fora** | Intervenção: alternar variantes nos cartões com alta DFC e medir depois se a queda de acerto diminui. Exige semanas de seguimento; fica como trabalho futuro |
| E5 custo e usabilidade | Descritiva | Minutos e lapsos extras, % de "variante ruim" |

---

## 4. Participantes e cartões

### 4.1 Fontes

| Fonte | Papel | Observação |
|---|---|---|
| Irmão (desktop) | **Participante principal**: fonte da maior parte dos eventos de suspeitos; sem ele não há estudo (plano B na seção 12) | Estudante de vestibular; coleção madura e ativa (≈ 28.900 notas, ≈ 150 respostas por dia estudado, retenção ≈ 92%, levantamento de 20/10, só agregados). O autor confirmou em 20/10 o consentimento, o calendário das provas e o uso do Anki no desktop |
| Autor (desktop) | Secundário: ensaio do add-on e dados adicionais | Coleção nova de Engenharia de Software, AWS Skill Builder, HTTPS e subconjunto reativado da Faculdade |

**Gargalo: eventos de suspeitos.** Contagens de 20/10, por consultas ao Anki do autor: no AWS Skill Builder há 21 notas com ≥ 5 revisões e 0 lapsos (61 com ≥ 4); HTTPS e Comunicação/Persuasão não têm nenhuma com ≥ 5. A Faculdade tem 263 notas sem imagem com ≥ 5 revisões e 0 lapsos (antes de filtrar LaTeX e conteúdo não conceitual), mas estão paradas há muito tempo e geram muito esquecimento. Cartões novos demoram a virar suspeitos. Por isso o irmão é o participante principal. O levantamento de 20/10 na coleção dele (comando `survey`, só agregados, sem texto de cartão) mostra 2.755 respostas nos 28 dias anteriores, 58% delas em cartões que o add-on sortearia pelas regras desta versão: ≈ 1.320 eventos, ≈ 730 de suspeitos pelo histórico. Se a rotina continuar igual, a janela de 21 dias renderia ≈ 990 eventos (≈ 550 de suspeitos), perto do alvo da seção 8; com as regras da v1.1 (só texto, uma lacuna) seriam ≈ 50 (≈ 16 de suspeitos), e foi isso que motivou a v1.2. É projeção, não garantia: depende de ele manter o ritmo de estudo (o calendário das provas pode mudá-lo) e de o banco cobrir os cartões que vencerem; vale o número observado. Sem o irmão (ou outros voluntários), o resultado provável de H2 é "inconclusivo", e o protocolo já prevê isso (seção 8.1).

### 4.2 Elegibilidade do cartão

Tipos Básico e Cloze; conceito (não vocabulário, número, data ou lista ordenada); resposta esperada determinável pelo próprio cartão ("mundo fechado", seção 6.1); já revisado ao menos uma vez (`reps ≥ 1`), pois a primeira exposição define a forma. Restrições por tipo (v1.2):

- **Básico:** só texto (sem imagem, áudio, vídeo ou LaTeX).
- **Cloze:** de 1 a 3 lacunas ocultas ao mesmo tempo no mesmo cartão, todas com o mesmo número `cN` (nota com vários números gera vários cartões e fica fora, assim como a nota com mais de 3 lacunas). O campo da lacuna pode ter **imagens**, que ficam fixas nas duas formas, exceto na variante `sem_imagem`. Continuam fora áudio, vídeo, fórmula ou LaTeX e qualquer mídia dentro de uma resposta. O texto visível (sem as lacunas e sem as imagens) precisa ter ≥ 30 caracteres, para haver contexto para uma pergunta, e as respostas não podem ser todas numéricas.
- **Fora em qualquer tipo:** Image Occlusion e tipos com resposta digitada; baralhos de inglês (vocabulário e frases de mineração; decisão de 20/10: não é o que o estudo quer testar); subbaralhos em que a imagem é o enunciado (a regra dos 30 caracteres já tira a maior parte deles); respostas vazias. Os baralhos excluídos são definidos na consulta de exportação, antes da geração.

A elegibilidade estrutural é checada pelo pipeline; "conceitual" e "o texto sozinho permite perguntar" são julgados pelo LLM na geração (sinal `conceptual` do registro) e conferidos na auditoria.

### 4.3 Reativação controlada da Faculdade

Descongelar um subconjunto de cartões de texto elegíveis em ritmo fixo de 25 por dia a partir de 2/11 (o ritmo real é registrado) para gerar eventos "devidos". Cartões parados há mais de um ano falham muito por esquecimento nos dois braços (no piloto, 14 de 41 foram lembrados); entram com covariáveis de intervalo e de dias desde a última revisão e pesam mais nos controles e nas análises exploratórias.

---

## 5. Definições operacionais

| Termo | Definição |
|---|---|
| Janela | Revisões de 2/11 a 22/11/2026 (inclusive). Antes de 2/11 o add-on só registra; o sorteio é ligado em 2/11 |
| Evento | Uma revisão, no desktop com o add-on, de cartão elegível cuja revisão anterior foi em outro dia do Anki, com sorteio registrado e resposta registrada, dentro da janela |
| Exposição do mesmo dia | Revisão no mesmo dia do Anki da revisão anterior do cartão (passos de aprendizado do primeiro dia, cartão que reaparece depois de um Again). Mostra o original, é registrada com `same_day = 1`, não é sorteada e não é evento |
| Falha | Resposta "Again"; "Hard", "Good" e "Easy" contam como sucesso |
| Suspeito | Elegível com `reps ≥ 5`, `lapses = 0` e última resposta ≥ "Good" |
| Controle | Elegível que não é suspeito |
| Variante válida | Resposta esperada preservada (em Cloze, a de cada lacuna), sem ambiguidade, sem vazamento da resposta, redação distinta (validação da seção 6.2); na `sem_imagem`, o texto sozinho basta para responder |
| Evento válido | Evento cuja variante não foi marcada "variante ruim" e sem erro do add-on (inclui resposta desfeita: sem par no histórico de revisões do Anki, ou substituída por outra do mesmo cartão e do mesmo `reps`) |
| Variante nova | A mesma variante não se repete no mesmo cartão enquanto houver outra disponível |

**Esclarecimentos (v1.1).** "Dia do Anki" segue a virada de dia configurada no próprio Anki. `reps` é o contador do Anki e inclui respostas em passos de aprendizado, então `reps ≥ 5` equivale, em geral, a 3 ou 4 revisões em estado de revisão: nas notas do autor (consulta de 20/10), 193 dos 276 suspeitos por esta definição têm 3 ou 4 dessas revisões e 83 têm 5 ou mais (todos da Faculdade). A definição de suspeito não muda, para não perder poder; o add-on registra `n_reviews` (entradas do tipo revisão no histórico do Anki, `type = 1`) para a sensibilidade da seção 7.

**Esclarecimentos (v1.2).** No Cloze com várias lacunas, elas ficam ocultas juntas e a pessoa responde o cartão inteiro com um botão: a **falha é "Again" no cartão**, o que pressupõe que ela dê "Again" se errou alguma lacuna (autoavaliação, como no resto do protocolo). A unidade de análise é o evento e o agrupamento é por **nota**: no Cloze do irmão cada nota tem um único cartão (um só `cN`), e as variantes e as covariáveis `n_blanks` e `has_image` pertencem à nota.

---

## 6. Procedimento

### 6.1 Geração offline

**Básico.** Para cada cartão elegível, K = 4 variantes, uma de cada tipo:

| Tipo | O que muda |
|---|---|
| `paraphrase` | Palavras e estrutura do enunciado |
| `reorder` | Ordem de itens ou de orações |
| `reformat` | Formato (por exemplo, afirmação com lacuna no lugar da resposta, ou pergunta aberta) |
| `cue_swap` | Remoção ou troca das palavras iniciais e das pistas superficiais |

**Cloze (v1.2).** Dois tipos, e cada um muda uma dimensão:

| Tipo | Quem gera | O que muda |
|---|---|---|
| `pergunta` | LLM | O texto vira perguntas diretas, uma por linha, com título, subtítulo e rótulos como contexto; cada lacuna continua oculta (`{{cN::resposta}}`) no lugar da resposta da pergunta correspondente; as imagens ficam no topo |
| `sem_imagem` | Determinística: o add-on tira as imagens do campo na hora de mostrar | Só a imagem; o resto do cartão fica idêntico |

A `pergunta` muda o estilo (de rótulo seco para pergunta); a `sem_imagem` muda a presença da imagem, a dependência visual que originou a ideia do projeto. A `sem_imagem` só existe para a nota que tem imagem, para a qual o LLM gerou uma `pergunta` válida (sinal de que o texto sozinho basta, isto é, de que a imagem é ilustrativa) e que a auditoria não rejeitou. Paráfrase e reordenação ficam fora do Cloze: nas fichas do irmão, todas do mesmo molde, mudariam pouco o que ele já viu (lição 6 da seção 2). Como os cartões são maduros (intervalo médio ≈ 240 dias), cada cartão aparece, em geral, uma só vez na janela (no levantamento de 20/10, 1.321 eventos em 1.251 cartões) e uma `pergunta` por nota basta; havendo `pergunta` e `sem_imagem`, o add-on escolhe ao acaso entre as ainda não mostradas daquele cartão.

Inversão (a resposta vira a pergunta) é tipo extra e secundário, desligado por padrão. **Regra de "mundo fechado":** a resposta esperada da variante é exatamente a do cartão e está contida no texto do próprio cartão; o LLM só reorganiza o que o cartão diz, sem conhecimento externo, e a variante não pode conter a resposta. No Cloze, cada lacuna aparece uma vez, na ordem do original, com a resposta do cartão, e o título e os rótulos viram o contexto das perguntas. Fora: instâncias ou aplicações novas, múltipla escolha com distratores.

*Exemplos (inventados):* "O que o TCP garante que o UDP não garante?" → "Que propriedade distingue a transmissão do TCP da do UDP?" (paráfrase); "Heme é formado por protoporfirina e {{c1::ferro}}" → "{{c1::Protoporfirina}} e ferro formam o heme" (reordenação). Ficha de Cloze com duas lacunas (título "Mitose", imagem de uma célula): "Fase em que os cromossomos se alinham no equador: {{c1::metáfase}}" e "Fase em que as cromátides-irmãs se separam: {{c1::anáfase}}" → `pergunta`: "Em que fase da mitose os cromossomos se alinham no equador da célula? {{c1::metáfase}}" e "E em que fase as cromátides-irmãs se separam? {{c1::anáfase}}" (a imagem continua no topo); `sem_imagem`: a mesma ficha, sem a imagem.

LLM via OpenRouter, **modelo pago e fixo**; registrar modelo, versão, prompt (`gen-v2` e `judge-v2`, com instruções próprias para o Cloze), parâmetros e data. Nunca durante a revisão. O banco cobre os cartões elegíveis que vencem até 22/11 (consulta por vencimento na exportação): o add-on só sorteia notas que estão no banco. Para notas criadas durante a coleta, o pipeline roda de novo todo dia, antes de a nota virar elegível.

### 6.2 Validação

- **Automática:** outro modelo (o juiz) confere se a resposta esperada responde à variante (em Cloze, a de cada lacuna), se há resposta alternativa plausível, se a variante entrega a resposta, se pergunta o mesmo que o original e o idioma; checagem lexical de distância mínima do original e de vazamento (em Cloze, sem contar os marcadores das lacunas) e de marcadores: cada lacuna aparece uma vez, na ordem do original e sem marcas de template, e a `pergunta` tem ao menos uma interrogação.
- **Humana:** amostra de ≥ 100 variantes aprovadas na validação automática, estratificada por tipo, revisada pelo autor (e ~30 pelo irmão). Critério: resposta preservada, sem ambiguidade, sem vazamento. A `sem_imagem` não passa pelo LLM e entra na amostra com a pergunta "só com o texto, ainda dá para responder o cartão?"; se não, a imagem não era ilustrativa e a variante é inválida. Alimenta H1. A taxa de aprovação automática é reportada à parte.

### 6.3 Sorteio e registro (add-on)

A cada revisão elegível de outro dia do Anki: sorteio 50/50 com semente por evento; exibição nos dois lados do cartão; registro de `event_id`, `note_id`, `card_id`, braço, `variant_id`, tipo, covariáveis da nota (`note_kind`, `n_blanks`, `has_image`, também no braço original), hash do texto exibido, horário, versões do add-on e do Anki, tempo até revelar, resposta e tempo total, além do estado do cartão antes da resposta (`reps`, `lapses`, intervalo, dias desde a última revisão, `same_day`, `n_reviews`, últimas respostas, agendador e retenção desejada). Nas exposições do mesmo dia o original aparece sem sorteio e o evento é registrado com `same_day = 1`. Botão "variante ruim" e opção de desligar. Na exportação, o add-on concilia cada evento com o histórico de revisões do Anki (`revlog_match`) e marca os substituídos (`superseded`), o que detecta respostas desfeitas (Ctrl+Z). No Cloze, a `pergunta` aparece como texto simples e centralizado (perde a formatação do campo original), com as imagens no topo, e a `sem_imagem` é o campo original sem as imagens; a diferença entre a `pergunta` e o original inclui, portanto, a formatação (seção 9).

#### 6.3.1 Seleção de cartões: três camadas

1. **Elegibilidade** (4.2): decide se o cartão pode receber variante. Todo cartão elegível, suspeito ou controle, é sorteado em **toda** revisão de outro dia do Anki (50/50); nas exposições do mesmo dia o original aparece sem sorteio; os não elegíveis não são alterados nem analisados.
2. **Estrato** (seção 5): suspeito ou controle, só pelo histórico (`reps`, `lapses`, última resposta). É o que entra na análise primária. O tempo até revelar não existe nas revisões antigas, por isso não define o estrato.
3. **Escore de candidato** (E3, exploratório): combina sequência de acertos, tempo até revelar relativo ao tamanho do enunciado (comparado com a distribuição da própria pessoa), prefixo mínimo identificador (PMI) e formato (Básico ou Cloze). É registrado desde o primeiro dia, mas **não** altera quem é sorteado (evita circularidade); depois se testa se prevê a falha da variante (AUC por validação cruzada, contra o baseline "só `reps`").

### 6.4 Agendamento e modo sonda

O Anki reagenda normalmente com a resposta dada. Para ampliar eventos de suspeitos fora da data devida: baralho filtrado **sem reagendamento** †, registrado como `mode` próprio, com análise separada ou indicador no modelo.

### 6.5 Restrições

Só desktop; revisões no celular não geram eventos e não entram. Anki fixo na 26.05 durante a coleta.

### 6.6 Dados e privacidade

SQLite local no add-on, exportado em CSV; para o irmão, IDs com hash e sem texto de cartão nos dados compartilhados.

### 6.7 Subamostra com resposta digitada

Fora do v1 por prazo. Só entra se sobrar prazo depois de M3: a pessoa digita a resposta em parte dos eventos e a correção é cega ao braço (outro modelo ou outra pessoa). Se não entrar, o viés da autoavaliação fica declarado como limitação e o irmão serve de réplica.

---

## 7. Análise (pré-registrada)

- **Primária (H2):** regressão logística com agrupamento: `falha ~ variante × suspeito + log(intervalo) + log(dias desde a última revisão) + tipo_de_variante + n_blanks + has_image`, com efeito aleatório (ou erro-padrão robusto) por **nota** e por usuário (`n_blanks` vale 0 no Básico). A estimativa reportada é a **DiD em pontos percentuais** (efeitos marginais), com IC 95%.
- **Secundárias:** dose-resposta (efeito da variante × `reps`); por tipo de variante (`pergunta`, `sem_imagem` e os do Básico); por número de lacunas e por presença de imagem; E3 (AUC de um escore de candidato prevendo a falha da variante); custo (minutos e lapsos extras).
- **Sensibilidade:** incluir eventos "variante ruim"; excluir a primeira revisão após a reativação; definição alternativa de suspeito (`reps ≥ 4`; e `n_reviews ≥ 5`); apenas eventos sem filtro de modo sonda; razão de chances na escala logit; subamostra digitada (se existir).
- **Efeito de escala (v1.2):** se a variante for mais fácil (ou mais difícil) do que o original para todos, por exemplo a `pergunta` em relação ao rótulo seco, a DiD em pontos percentuais deixa de ser zero só porque os controles têm mais falha a perder (ou a ganhar), sem nenhuma dependência da forma. Por isso a interação é repetida nas escalas de razão de chances e de razão de risco e com a falha anterior do cartão (`last_ease`, `prev_eases`) como covariável, e o relatório diz se a conclusão de H2 muda de uma escala para outra.
- **Multiplicidade:** um único desfecho primário; o restante é rotulado como exploratório.
- **Execução:** script em Python (statsmodels) versionado, testado antes com dados do registro e rodado uma vez após o fim da coleta.

---

## 8. Limiares de pré-registro

| # | Limiar | Valor | Por quê |
|---|---|---|---|
| 1 | Elegibilidade | Seção 4.2 | Fixa o universo |
| 2 | Suspeito | `reps ≥ 5`, `lapses = 0`, última resposta ≥ Good | Seção 5 |
| 3 | H1 (validade) | ≥ 85% das variantes auditadas válidas (a `sem_imagem` conta como um tipo); tipo abaixo de 70% sai da análise primária | Valores combinados antes dos dados |
| 4 | Mínimo para analisar H2 | 300 eventos válidos, ≥ 100 por estrato | Com ≈ 75 por célula só se vê DiD ≥ ≈ 20 pp (premissa) |
| 5 | Alvo e parada | ≈ 1000 eventos válidos (≈ 250 por célula) ou 22/11 (D1), o que vier primeiro; sem olhar o desfecho antes | Com ≈ 250 por célula vê-se DiD ≥ ≈ 10 pp (premissa, sem agrupamento; o poder real é menor) |
| 6 | Decisão em H2 | Seção 8.1 | |
| 7 | Custo (H5) | Falha nas variantes dos controles ≤ 5 pp acima do original; "variante ruim" ≤ 15% das exibidas | Descritivo, sem decisão confirmatória |
| 8 | Exclusões | Variante "ruim"; evento no celular; erro do add-on (inclui resposta desfeita: sem par no histórico de revisões do Anki, ou substituída por outra do mesmo cartão e do mesmo `reps`); versão do Anki diferente da 26.05; evento fora da janela; exposição do mesmo dia (não sorteada) | |

*Premissas do cálculo de poder (α = 0,05, poder 80%, sem agrupamento):* penalidade moderada, suspeitos 98% → 83% e controles 90% → 87% (DiD de 12 pp), ≈ 200 revisões por célula; penalidade grande, suspeitos 98% → 73% e controles 90% → 87% (22 pp), ≈ 70 por célula; DiD de 10 pp com suspeitos 98% → 88% e controles inalterados, ≈ 240 por célula.

### 8.1 Como decidir H2

| Onde está o IC 95% da DiD | Conclusão |
|---|---|
| Estimativa ≥ 10 pp e IC exclui 0 | **Apoiada**: penalidade relevante maior nos suspeitos |
| IC exclui 0, estimativa < 10 pp | **Efeito pequeno**: existe, abaixo do relevante |
| IC inclui 0 e limite superior < 10 pp | **Relevante descartado**: dependência de forma desprezível nesta amostra |
| IC inclui 0 e limite superior ≥ 10 pp | **Inconclusivo**: relatar o menor efeito detectável |

**Por que 10 pp:** uma queda extra de 10 pontos (por exemplo, de 98% para 88% de acerto) já seria perceptível ao usuário e é o que ≈ 250 eventos por célula conseguem distinguir. O piloto usou "menos de ~10% é pequeno; 25% ou mais é promissor" para a taxa de erro das variantes; aqui o alvo é a **diferença** em relação aos controles.

---

## 9. Ameaças e tratamento (resumo; tabela completa na [fundamentação](fundamentacao.md), seção 6)

| Ameaça | Tratamento |
|---|---|
| Dificuldade da variante | Controles recebem as mesmas variantes; o efeito principal da variante absorve a dificuldade média |
| Esquecimento | Sorteio na revisão devida; covariáveis de intervalo e de dias desde a última revisão; reativados analisados à parte |
| Contaminação sequencial | Uma forma por exposição; variante nova a cada exposição |
| Variante ruim | Validação, auditoria e botão "variante ruim" |
| Efeito de escala (variante mais fácil ou mais difícil para todos) | Sensibilidade em razão de chances e de risco, com a falha anterior do cartão como covariável (seção 7) |
| A `pergunta` muda também a formatação (texto simples e centralizado) | Declarada como parte do tratamento; a `sem_imagem` mantém a formatação original, e a análise por tipo mostra se o efeito vem de um só |
| Imagem essencial para responder | Regra dos 30 caracteres, auditoria da `sem_imagem` e exclusão de subbaralhos em que a imagem é o enunciado |
| Viés do experimentador (a hipótese é do autor) | Eventos do irmão como réplica; subamostra digitada com correção cega só se sobrar prazo (6.7) |
| Poucos suspeitos | Modo sonda; irmão; relatar o menor efeito detectável |
| Agrupamento (vários eventos por nota e por pessoa) | Erros-padrão por nota e usuário; priorizar mais notas distintas a mais revisões por nota |
| Generalização | Declarar o escopo: texto conceitual, poucas pessoas (um participante principal) |

---

## 10. Ética e privacidade

- Voluntários: o professor André informou (20/10) que não exige TCLE; mesmo assim, consentimento escrito curto por mensagem (finalidade, dados coletados, retirada a qualquer momento).
- O texto dos cartões vai ao provedor de LLM na geração: só com consentimento; privacidade do provedor sem treino com os dados; alternativa local (modelo compatível com OpenAI) se alguém não aceitar.
- Dados compartilhados sem texto de cartão e com IDs anonimizados.

---

## 11. Plano de trabalho (marcos com critério de "pronto")

Datas-limite derivadas da entrega do trabalho (**sex 4/12**) e da apresentação (**sex 18/12**). A coleta tem janela de 3 semanas (2/11 a 22/11), e tudo que vem antes precisa estar pronto até 30/10, senão entra o plano B (seção 12). A escrita corre em paralelo desde já; só Resultados e Discussão esperam a análise.

| Marco | Entrega | Pronto quando | Data-limite |
|---|---|---|---|
| M0 | Protocolo congelado (v1, v1.1 e v1.2) | Arquivo comitado com a tag da versão (a vigente é `protocolo-v1.2`); (opcional) registro no OSF † | **feito em 20/10** |
| M1 | Banco de variantes offline (E1) | Cartões elegíveis do irmão e do autor processados, depois de um piloto com 20 a 30 cartões reais do irmão; auditoria de ≥ 100 variantes com H1 ≥ 85% | qua 28/10 |
| M2 | Add-on v0 (só registro) | Registra as revisões do desktop sem quebrar o Anki; conferido contra o histórico de revisões do Anki | ter 27/10 |
| M3 | Add-on v1 (sorteio e exibição) | Teste de fumaça: a variante aparece nos dois lados, o log bate com o Anki, "variante ruim" e desligar funcionam; instalado no Anki do autor e no do irmão | sex 30/10 |
| M4 | Coleta | Fim em 22/11 (D1) ou ≈ 1000 eventos; só monitoramento de qualidade e contagem | seg 2/11 a dom 22/11 |
| M5 | Análise | Script testado antes com dados do registro; rodado uma vez após D1; tabelas e figuras geradas | seg 23/11 a sex 27/11 |
| M6 | Entrega do trabalho | Metodologia = este protocolo; resultados, ameaças, limitações | sex 4/12 |
| M7 | Apresentação | Slides e ensaio | até sex 18/12 |

---

## 12. Riscos e plano B

| Risco | Gatilho | Plano B |
|---|---|---|
| Poucos eventos de suspeitos | Abaixo do mínimo na metade da janela | Modo sonda; mais voluntários; relatar o menor efeito detectável |
| Add-on atrasa | M3 não pronto em 30/10 | Sondas manuais (como no piloto) com registro mínimo; add-on só de registro. A data D1 (22/11) não se move: a janela encurta e o mínimo de 300 eventos continua valendo; abaixo dele, relatório descritivo |
| Variantes ruins | H1 < 85% | Ajustar prompt ou modelo; restringir tipos; repetir a auditoria |
| Anki atualiza e quebra o add-on | Nova versão instalada | Fixar a 26.05 |
| Irmão desiste ou estuda bem menos (provas) | Sem dados dele, ou abaixo do mínimo na metade da janela | Mais voluntários; só o autor; E2 descritivo com o menor efeito detectável; ênfase em E1 e em viabilidade |
| Imagem essencial em parte das fichas | `sem_imagem` abaixo de 70% na auditoria | A `sem_imagem` sai da análise primária e o banco segue só com a `pergunta` |
| Resultado nulo ou inconclusivo | Seção 8.1 | Reportar como está; contribuição: pipeline validado, estimativa com intervalo e lições |

---

## 13. Registro e desvios

Repositório Git criado em 20/10; o protocolo foi comitado e marcado com `protocolo-v1` antes de qualquer sorteio e revisado como `protocolo-v1.1` e `protocolo-v1.2` (ver "Histórico de versões"), também antes do primeiro sorteio. Mudanças depois do primeiro sorteio entram em [`desvios.md`](desvios.md), com data, o que mudou e por quê. O OSF † é opcional (registro público com data).

---

## 14. Decisões tomadas

- **20/10:** entrega em 4/12 e apresentação em 18/12; E4 (rotação) fora; TCLE não exigido pelo professor.
- **Ao liberar a implementação (20/10):** suspeito `reps ≥ 5` (sensibilidade `≥ 4`); limiar de 10 pp; reativação de 25 por dia a partir de 2/11; agendamento normal do Anki; resposta digitada fora do v1; análise em Python.
- **Antes do primeiro sorteio (20/10, v1.1):** sorteio só em exposições de outro dia do Anki; `reps ≥ 5` mantido, com `n_reviews` registrado e sensibilidade `n_reviews ≥ 5`; resposta desfeita conta como erro do add-on.
- **Antes do primeiro sorteio (20/10, v1.2):** o irmão é o participante principal; entram Cloze com 1 a 3 lacunas e imagens fixas, e ficam fora Image Occlusion e os baralhos de inglês; variantes do Cloze: `pergunta` e `sem_imagem`; análise agrupada por nota, com `n_blanks` e `has_image` e sensibilidades para o efeito de escala.
- **Pendências fora do protocolo:** conta e créditos no OpenRouter (até 23/10) e piloto da geração com 20 a 30 cartões reais do irmão, para o autor e o irmão julgarem se o conteúdo se mantém e se a forma parece diferente.
