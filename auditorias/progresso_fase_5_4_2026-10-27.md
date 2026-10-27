# Trilhário — Auditoria fase 5.4 (checkpoint de 27-10-2026)

## Estado do trabalho
- 5.1 Títulos e datas: revistos nas versões anteriores.
- 5.2 Locais e GPS: revistos nas versões anteriores.
- 5.3 Programas de vários dias: v96 mantém os programas e apresenta a data final. NÃO voltar a excluí-los.
- 5.4 Qualidade dos campos: dividida em 5.4a–5.4d.

## 5.4a — Distâncias sem proveniência e preços Hike Land — código corrigido
1. O anúncio «Caminhando nas Maravilhas da Arrábida» (31-10-2026) tinha 35 km retirados do texto geográfico sobre a extensão da cordilheira, não do percurso. A página oficial não indica uma quilometragem positiva (campo «0 km's Distância»). Valor do evento publicado corrigido para desconhecido (null), sem inventar quilómetros.
2. No colector de Caminhando.pt, só aceitar quilómetros quando associados explicitamente ao rótulo «Distância»/«Distância do percurso». Não aplicar a regra às outras fontes.
3. A correcção documentada no registo excepcoes_catalogo.json prevalece sobre os dados antigos, incluindo uma correcção explícita para null; impedir que o valor falso regresse pela recuperação do catálogo anterior.
4. O normalizador já pode reconhecer «PREÇO: 15€ | Participante» nas fichas da Hike Land, em vez de depender apenas da recolha inicial.
5. Adicionados testes offline em testes/test_qualidade_campos.py; execução integral da suite ainda por confirmar.

Fonte para a distância indevida: https://caminhando.pt/eventos/caminhando-nas-maravilhas-da-arrabida/
Formato de preço Hike Land: https://www.hikeland.pt/eventos/caminhada-no-bosque-dos-druidas-sintra-2/

## Inventário inicial (27-10-2026, antes das correcções)
- 217 eventos no eventos.json.
- 127 sem preço; 29 sem quilometragem; 139 sem URL de imagem.
- GreenTrekker: 74/76 sem preço. Hike Land: 39/41 sem preço.
- Fotografia em falta não implica ausência de imagem na página oficial; o hotlink pode estar bloqueado.

## Próximos blocos (por concluir)
- [ ] 5.4b — Preços: verificar por fonte os erros de obtenção de páginas, reforçar leitura do preço de inscrição e testar páginas reais; prioritários GreenTrekker e Hike Land. Não preencher por estimativa.
- [ ] 5.4c — Distâncias, desníveis, duração e horas: detecção de contexto errado, incoerências e sobreposição com programas multidiários.
- [ ] 5.4d — Imagens: rever fontes sem URL, taxa de cobertura dos dois fins de semana seguintes e limites de pedidos sem sobrecarregar o workflow.
- [ ] Confirmar execução completa dos testes offline e resultado após a próxima recolha programada.

## Regras a preservar
- Não excluir programas de vários dias (incluindo Monfragüe, Courel, Faias, Aracena e passagem de ano).
- Não confundir distâncias acumuladas de programas de vários dias com um só percurso.
- Não reintroduzir comparação de trilhos nem filtros já removidos; manter dificuldade nos cartões.
- Preservar IDs, datas, custos de viagem e localização quando não relacionados com a correcção.
