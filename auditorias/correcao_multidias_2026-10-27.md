# Trilhário — correcção da agenda de programas multidiários (27-10-2026)

## Decisão funcional do responsável
Um programa que comece a 29-10 e termine a 01-11 **deixa de aparecer na agenda no dia 30-10**. A data final descreve o intervalo, não prolonga a disponibilidade de participação. No próprio dia de início, os programas permanecem visíveis até terminar esse dia. A regra de hora de início das caminhadas individuais mantém-se.

## Alterações
- `assets/js/trilhario.js`: remove a regra anterior que mantinha os programas até `endDate`; expira-os pelo dia seguinte a `date`.
- `qualidade_anuncios.py`: reconhece explicitamente `multiDay` e intervalos `endDate > date`, mesmo com título neutro.
- `recolher.py`: aproveita `endDate` de JSON-LD correspondente à própria ficha, sem inferir datas; rejeita `endDate` inválida ou anterior ao início; dados de programas já iniciados não são preservados por `endDate`; registos antigos multidiários não são erradamente rejeitados por menções à data final no título.
- `fontes_oficiais.py`: RB/Smile reconhecem os intervalos explícitos publicados em títulos/cabeçalhos, sem voltar a bloquear genericamente programas pedestres por conterem «viagem» ou «passagem de ano». Requer página individual, data verificada e indícios de caminhada.
- `normalizar_eventos.py`: valida a coerência da data final, sem a tornar critério de permanência.
- `testes/test_titulos_datas.py`: retiradas exigências permanentes de seis edições de 2026 no catálogo vivo; acrescentadas fixtures para intervalos, JSON-LD, expiração e integração RB/Smile com HTML simulado.
- `testes/test_catalogo_browser.cjs`: verifica expiração após o dia de início no navegador e preservação da regra horária das saídas individuais.
- `README.md`: regra documentada.

## Fora desta revisão
- Sem remoção global de programas de vários dias.
- Não foram inventadas datas finais para os 11 programas do inventário anterior sem essa informação.
- Não foram abordados os problemas de identidade e recuperação de campos entre edições, nem de publicação/rebase e extratores dos restantes organizadores; pertencem às próximas fases da auditoria do Codex.
- A execução completa dos testes e uma recolha real após estas alterações precisam de confirmação no GitHub Actions. Os testes foram **acrescentados**, não declarados aprovados sem execução.

## Resultado esperado
- Expedição Ordesa 29-10 a 01-11: visível até 29-10; oculta a 30-10.
- A chegada do dia 30 não provoca falha de CI por desaparecimento legítimo de Ordesa do catálogo.
- Intervalo RB/Smile «7 a 8 de Novembro» pode ser reconhecido como um programa multidiário quando publicado numa ficha oficial de caminhada, com início 7-11 e fim 8-11.
