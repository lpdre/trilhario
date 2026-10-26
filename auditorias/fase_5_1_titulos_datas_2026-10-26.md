# Trilhário — Auditoria 5.1: títulos e datas
Data da análise: 26-10-2026.

## Âmbito
Catálogo publicado com **201 anúncios** de 17 organizadores; validação offline de datas escritas expressamente nos títulos e inspecção dos títulos com sinais de anúncios multidiários ou metadados usados como nome. A análise automática não prova que os restantes títulos e datas coincidam com as páginas oficiais.

## Correcções verificadas
- **Hike Land, 21-11-2026:** substituir o rótulo `muito-dificil 21/11/2026 21 km NOVIDADE` por **Montemuro: O Vale do Bestança | Cinfães**. Título e data conferidos na ficha: https://www.hikeland.pt/eventos/montemuro-o-vale-do-bestanca-cinfaes
- **Trekking Roots, 29-10-2026:** excluir **Expedição Outonal a Ordesa e Monte Perdido**. Ficha oficial confirma quatro dias (29-10 a início de Novembro) e deslocação a Espanha: https://trekkingroots.pt/caminhada/expedicao-outonal-a-ordesa-e-monte-perdido
- **Mais Trilhos, 31-12-2026:** excluir **Fim de Semana Passagem de Ano - Douro Internacional** como anúncio multidiário explícito. O detalhe está protegido contra acesso automático; não inferir datas alternativas: https://maistrilhos.pt/caminhadas/passagem-de-ano-douro-internacional

## Verificação de datas
Foram detectados nove anúncios com datas explícitas nos títulos; as datas coincidiram com a data do catálogo. Não inferimos datas pelos slugs de URLs, que podem ser reutilizados pelas organizações.

## Regras acrescentadas
- Importar o H1 do anúncio oficial quando o cartão só dá dificuldade/data/quilómetros.
- Rejeitar programas de vários dias também quando já estavam guardados no JSON, para não reaparecerem em execuções seguintes.
- Bloquear títulos que contradizem explicitamente a data; conservar IDs de anúncios válidos.
- Testes determinísticos, sem rede, para títulos genéricos, vários formatos de datas e retenção do catálogo.

**Resultado imediato:** 199 anúncios; uma correcção de título e duas exclusões documentadas.
