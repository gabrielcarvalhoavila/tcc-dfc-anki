## DFC Probe: configuração

- `enabled` (`true`/`false`): liga ou desliga o registro das revisões (e, com ele, o sorteio). Também aparece em Ferramentas > DFC Probe > Registro ativo.
- `draw_enabled` (`true`/`false`): liga ou desliga só o sorteio de variantes; o registro continua. Também em Ferramentas > DFC Probe > Sorteio ativo.
- `draw_start`, `draw_end` (`AAAA-MM-DD`): janela do estudo, inclusive. Fora dela nada é sorteado. Não altere durante a coleta; para o teste de fumaça, antecipe `draw_start` e volte para `2026-11-02` depois (eventos fora da janela não entram na análise).
- `bad_shortcut`: tecla que marca a variante em exibição como ruim (padrão `b`; vazio desliga o atalho). Também há "Variante ruim" no menu de contexto da revisão e, para a resposta anterior, em Ferramentas > DFC Probe.
- `allow_fake_bank` (`true`/`false`): um banco gerado com `--dry-run` (variantes falsas) só sorteia se isto estiver ligado. Só para o teste de fumaça; volte para `false` e importe o banco real antes de 2/11.
- `anonymize_export` (`true`/`false`): na exportação do CSV, troca `note_id`, `card_id`, `deck_id`, `deck_name` e `profile` por um hash com sal próprio desta instalação. Use `true` para dados que vão para outra pessoa.

O banco de eventos (`dfc_events.sqlite3`), o banco de variantes importado (`variant_bank.json`), o log de erros (`dfc_errors.log`) e o sal ficam em `user_files/`, que o Anki preserva ao atualizar o add-on. O banco de eventos não guarda o texto dos cartões; o de variantes guarda o texto das variantes e não deve ser compartilhado.
