# Trilhário — Auditoria 5.3: programas com vários dias omitidos do título
Data: 26-10-2026.

## Problema
A auditoria encontrou quatro programas de vários dias entre os 199 anúncios, apesar de o Trilhário ser uma agenda de caminhadas individuais. Um título descritivo (sem a palavra «viagem» ou «fim de semana») passava pelas regras existentes. As distâncias publicadas correspondiam à soma de percursos ou só a parte do programa.

## Anúncios excluídos, com confirmação
1. Trekking Roots, 07-11-2026 — «Rota das Faias e o Melhor do Outono de Manteigas» (159 €): anúncio descreve duas caminhadas e uma noite de alojamento. Fonte https://trekkingroots.pt/caminhada/rota-das-faias-e-o-melhor-do-outono-de-manteigas/
2. Trekking Roots, 21-11-2026 — «Bosques Mágicos do Courel» (169 €): 21 e 22 de Novembro, uma noite, dois percursos. Fonte https://trekkingroots.pt/caminhada/bosques-magicos-do-courel/
3. Mais Trilhos, 28-11-2026 — «Parque Nacional de Monfragüe» (400 €): três noites de hotel e vários percursos em dias sucessivos. Fonte https://maistrilhos.pt/caminhadas/parque-nacional-de-monfrague
4. Caminhando.pt, 28-11-2026 — «Caminhando em Aracena, Gruta das Maravilhas e Parque Mineiro de Rio Tinto»: programa 28 de Novembro a 1 de Dezembro. A página original não respondeu a consulta externa; programação detalhada reproduzida com atribuição à Caminhando.pt em https://stayhappening.com/e/caminhando-em-aracena-gruta-das-maravilhas-e-parque-mineiro-de-rio-tinto-E2ISYRNDMG2

## Correcções
- Nova função `is_multiday_program` usa a detecção genérica por título e uma lista restrita de URLs individuais documentados.
- Aplicada no colector de novos eventos, na conservação de eventos antigos e na normalização.
- Testes para os quatro casos e para garantir que uma caminhada individual semelhante não é excluída.
- Estes anúncios foram retirados de `eventos.json`; todos os restantes IDs e dados foram conservados.
- Nenhuma alteração de preços ou coordenadas por dedução.

## Resultado
195 anúncios publicados na revisão do catálogo. As datas e os preços elevados não bastam, por si só, para classificar uma caminhada como programa multidiário.
