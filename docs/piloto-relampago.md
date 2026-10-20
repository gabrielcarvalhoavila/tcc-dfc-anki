# Piloto: experimento-relâmpago (15 a 20/10/2026)

Teste manual, sem código, para ver antes de programar se variantes de cartões **que a pessoa sabe** falham e se as variantes geradas fazem sentido. É piloto e **não entra** na análise confirmatória. Dados em [`pilot/relampago/`](../pilot/relampago/): as folhas de resposta (`passo1-originais.md`, `passo2a.md`, `passo2b.md`) e as notas por item (`notas.csv`).

## Desenho

- **Pool:** 41 cartões de Redes de Computadores (Básico, só texto, criados em 2025), movidos para o deck `TCC::Relampago` do Anki (continuam suspensos, com a tag `tcc_relampago`). Ficaram de fora 4 cartões: um duplicado, dois de sim/não e um genérico demais.
- **Por que folha de resposta e não o Anki:** o Anki mostra a resposta ao virar o cartão, e esse feedback contamina as tentativas seguintes. As respostas foram digitadas sem consultar nada e corrigidas só no fim.
- **Passo 1 (15/10):** os 41 originais, às cegas. Correção feita pelo assistente (GitHub Copilot) pela ideia central: correto, correto com ressalva, parcial, errado ou "não lembro".
- **Passo 2:** os 12 conceitos acertados no Passo 1 (2 de 14 acertos foram descartados porque outras perguntas da mesma folha serviam de dica). **Crossover AB:** cada conceito aparece uma vez por sessão, como original numa sessão e como variante na outra, com ordem sorteada (sementes fixas). As sessões A e B foram respondidas com cerca de 4 dias de intervalo.
- **Variantes:** uma por conceito, de "mundo fechado": paráfrase, ordem trocada, contexto sem o termo e finalidade. Inversão (descrição para o termo) ficou de fora porque entrega a resposta das outras formas na mesma folha.

## Resultados

**Passo 1:** 14 acertos (3 com ressalva), 8 parciais, 1 erro e 18 "não lembro" em 41 cartões. Os cartões estavam parados havia cerca de 17 meses.

**Passo 2** (✓ correto; ~ correto com ressalva, por hesitação ou imprecisão):

| Conceito | Original | Variante (tipo) |
|---|---|---|
| longest prefix match | ~ | ✓ (contexto, sem o termo) |
| queueing | ✓ | ✓ (paráfrase) |
| packet sniffing | ✓ | ✓ (paráfrase) |
| ISP | ~ | ✓ (paráfrase) |
| HTTP persistente | ✓ | ✓ ("por que") |
| TCP x UDP | ✓ | ✓ (ordem trocada) |
| DNS | ✓ | ✓ (contexto) |
| NAT | ~ | ~ (finalidade) |
| DDoS | ✓ | ✓ (contexto, sem o termo) |
| protocolo de rede | ✓ | ✓ (paráfrase) |
| HTTP x FTP | ~ | ✓ (ordem trocada) |
| aplicação sensível à perda | ✓ | ✓ (paráfrase) |

- Ressalvas contadas como acerto: original 12/12 e variante 12/12. Ressalvas contadas como erro: original 8/12 e variante 11/12.
- **0 falhas em 12 variantes:** IC 95% de Clopper-Pearson para o erro da variante de 0% a cerca de 26%.
- As duas variantes sem o termo (longest prefix match e DDoS) foram respondidas nomeando o termo.

## Leitura

- Variantes brandas (paráfrase, contexto, ordem) não derrubaram o acerto de cartões curtos "O que é X?" que a pessoa sabe. Na régua combinada antes (menos de ~10% de erro = dependência pequena), isso é "pequena" para esse tipo de cartão.
- O piloto **não testa** a hipótese principal: os cartões têm no máximo 4 revisões (não são "suspeitos"), as variantes eram brandas e inversão e cloze ficaram de fora.
- 12 pares só excluem efeitos acima de ~26%.

## Limitações

Amostra de 12 pares; um único corretor (o assistente); autoavaliação e hipótese conhecidas pelo participante, que é também o autor do estudo; respostas quase idênticas entre as exposições, o que pode refletir lembrar a própria resposta.

## Lições incorporadas ao protocolo

1. **Uma forma por exposição:** original e variante do mesmo cartão no mesmo arquivo deixam copiar a própria resposta.
2. **Inversão** é tipo secundário e nunca na mesma sessão que as outras formas.
3. **Centenas de eventos**, não dezenas, e eventos de **suspeitos** (cartões com muitas revisões e sem lapsos).
4. **Viés do experimentador:** réplica com outra pessoa; resposta digitada com correção cega como extensão.
