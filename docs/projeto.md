# Projeto: dependência da forma do cartão (DFC) em repetição espaçada

## Tema e problema

Quem usa o Anki por muito tempo passa a acertar alguns cartões **pela forma**: o formato, as palavras iniciais, a ordem das lacunas. A recordação vira reflexo à aparência do cartão e não ao conceito. A ideia do projeto é usar **variantes** dos cartões "sempre acertados" (mesmo assunto, com outras palavras, ordem ou formato) como **sonda**: se a pessoa acerta a variante, a recordação é robusta à forma; se erra, há sinal de que decorou o cartão.

"Acertou a variante" não prova "aprendeu o conteúdo", e "errou" não prova "decorou": o sinal só significa algo em comparação com cartões de controle (ver [fundamentação](fundamentacao.md), seção 6).

## Pergunta de pesquisa

Cartões que o usuário acerta de modo consistente ("suspeitos") perdem **mais** acerto, quando o enunciado muda, do que os demais cartões ("controles")?

## Tese

> A dependência da forma do cartão pode ser medida em usuários reais de repetição espaçada por meio de variantes de "mundo fechado" (a resposta esperada está contida no próprio cartão) geradas por LLM e validadas; cartões suspeitos apresentam penalidade de variante maior que cartões de controle. Um resultado nulo ou inconclusivo também é resultado.

Duas partes: **núcleo (diagnóstico)**, a penalidade da variante em suspeitos × controles; e **habilitadora (pipeline)**, um fluxo com LLM e verificação que gera variantes válidas só a partir do texto do cartão.

## Hipóteses e critérios de refutação

Os limiares numéricos estão no [protocolo](protocolo.md), seção 8, e foram fixados antes dos dados.

| Hipótese | Papel | Refutada se |
|---|---|---|
| **H1** (pipeline): a maioria das variantes é válida | Confirmatória | Menos de 85% das variantes auditadas são válidas, ou os erros exigem conhecimento externo |
| **H2** (penalidade): a queda de acerto da variante é maior nos suspeitos que nos controles | Confirmatória | O IC 95% da diferença de diferenças inclui 0 (classes em protocolo 8.1) |
| **H3** (sinais): tempo até revelar, prefixo mínimo identificador e sequência de acertos preveem a falha da variante | Exploratória | A AUC não supera o baseline "só número de revisões" |
| **H4** (rotação): alternar variantes reduz a penalidade depois | Fora do escopo | Trabalho futuro |
| **H5** (custo): o custo extra em lapsos e minutos é aceitável | Descritiva | Falha extra nas variantes dos controles acima de 5 pontos percentuais ou mais de 15% de "variante ruim" |

## Objetivos

**Geral:** desenvolver e avaliar uma prova de conceito que mede a DFC em repetição espaçada, comparando o acerto em cartões originais e em variantes equivalentes geradas por LLM.

**Específicos:**
1. Levantar a literatura e as ferramentas sobre variação de cartões e "pattern matching".
2. Definir operacionalmente DFC, cartão suspeito e variante de mundo fechado.
3. Implementar o pipeline de geração e validação de variantes e o add-on do Anki que registra e sorteia.
4. Avaliar a validade das variantes (E1).
5. Estimar a penalidade da variante em suspeitos e controles (E2) e explorar a validade dos sinais de candidato (E3).
6. Descrever o custo para o usuário (E5).
7. Discutir ameaças à validade e limitações, e apontar a rotação (E4) como trabalho futuro.

## Metodologia

**Design Science Research** ([Hevner et al. 2004](https://doi.org/10.2307/25148625); [Peffers et al. 2007](https://doi.org/10.2753/mis0742-1222240302)): problema, objetivos, projeto e desenvolvimento, demonstração, avaliação, comunicação. A avaliação de E2 segue o desenho **microrandomizado** ([Klasnja et al. 2015](https://doi.org/10.1037/hea0000305); [Qian et al. 2022](https://doi.org/10.1037/met0000283)): a cada revisão elegível de outro dia do Anki, o add-on sorteia original ou variante e registra o que foi mostrado.

## Delimitações

- Texto conceitual (Básico e Cloze com até 3 lacunas; no Cloze, as imagens ilustrativas ficam fixas), em português; só desktop.
- Só variantes de mundo fechado; sem alegar melhora de aprendizagem de longo prazo.
- "Aprendeu o conteúdo" é substituído por "recordação robusta a mudanças de forma".
- Poucas pessoas (o irmão do autor é o participante principal, que estuda em sessões dedicadas numa cópia da coleção dele): o resultado não se generaliza para a população de usuários nem para a rotina natural de estudo.

## Contribuições esperadas

1. Definição operacional e medida da DFC.
2. Pipeline de geração e validação de variantes de mundo fechado, com a taxa de variantes válidas por tipo.
3. Add-on do Anki que sorteia, exibe e registra (código aberto, sujeito à licença AGPL do Anki †).
4. Estimativa, com intervalo de confiança, da penalidade da variante em suspeitos e controles; ou, se o resultado for nulo, o limite superior do efeito.
5. Lições de viabilidade: quantos eventos de suspeitos uma coleção real rende e o custo do pipeline.
