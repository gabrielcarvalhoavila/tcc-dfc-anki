## DFC Probe: configuração

- `enabled` (`true`/`false`): liga ou desliga o registro das revisões. Também aparece em Ferramentas > DFC Probe > Registro ativo.
- `anonymize_export` (`true`/`false`): na exportação do CSV, troca `note_id`, `card_id`, `deck_id` e `deck_name` por um hash com sal próprio desta instalação. Use `true` para dados que vão para outra pessoa.

O banco (`dfc_events.sqlite3`), o log de erros (`dfc_errors.log`) e o sal ficam em `user_files/`, que o Anki preserva ao atualizar o add-on. O banco não guarda o texto dos cartões.
