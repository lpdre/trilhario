# Trilhário
Agenda de caminhadas organizadas em Portugal.

## Componentes
- `index.html`, `assets/js/trilhario.js` e `assets/css/trilhario.css`: interface, filtros, calendário, mapa e custos de deslocação.
- `eventos.json`: catálogo oficial; falhas de carregamento não apresentam eventos fictícios.
- `recolher.py`, `monitorizacao_fontes.py`, `normalizar_eventos.py`, `consolidar_catalogo.py`, `fontes_oficiais.py` e `localizacoes.py`: recolha diária, monitorização e validação.
- `excepcoes_catalogo.json`: correcções documentadas e eventos confirmados manualmente.
- `precalcular_rotas.py`, `rotas_precalculadas.json` e `netlify/functions/portagens.js`: cálculos de deslocação.
- `.github/workflows/actualizar.yml`: actualização diária; `.github/workflows/validar.yml`: testes de regressão sem recolha de dados.

## Compatibilidade
A criação manual de caminhadas no navegador foi descontinuada. Os eventos já guardados em `trilhario_custom_v1` continuam visíveis e podem ser eliminados individualmente; a limpeza não apaga dados pessoais do navegador.

A dificuldade mantém-se nos cartões, mas não existe filtro por dificuldade. Os favoritos e os dados de demonstração foram descontinuados.

## Testes locais
```bash
python -m pip install 'requests>=2.31,<3' 'beautifulsoup4>=4.12,<5'
python -m unittest discover -s testes -p 'test_*.py' -v
node --check assets/js/trilhario.js
node testes/test_catalogo_browser.cjs
node testes/test_localizacoes_browser.cjs
```

## Arquitectura v87
- `assets/js/trilhario-routes.js` separa operações puras de geometria, amostragem e validade de rotas; não altera as consultas aos serviços externos.
- Código obsoleto (exportação ICS sem botão, helpers e ícones sem utilização) retirado. Mantêm-se as caminhadas pessoais antigas, a exportação KML e a dificuldade.

- O directório distingue fontes configuradas daquelas apenas listadas, com base nos metadados `sources_health` efectivamente publicados.
- Comandos gerados por JavaScript deixam de usar atributos `onclick` e passam a delegação central.

## Revisão v88
- Retirada por completo a funcionalidade de comparação, incluindo página, botões, estilos, armazenamento, chamadas e testes dedicados.
- Preservados os filtros, a indicação de dificuldade, as estimativas de viagem, o mapa e o calendário.
- O histórico local de eventos pessoais e as preferências de deslocação não são alterados.

## Auditoria Python v89
- Removido o extractor do agregador desactivado e as referências ao respectivo despacho/monitorização.
- Retirada a função de exclusão de organizadores que devolvia sempre `False`.
- Programas PDF sem eventos individuais confirmados não provocam pedidos HTTP desnecessários.
- Mantida a protecção que rejeita registos antigos do agregador e a validação de fontes oficiais.

## Auditoria v90 — Normalização
- Eliminada uma excepção antiga para um anúncio do agregador e referências a favoritos já inexistentes.
- Retirado o domínio do agregador das origens elegíveis para fotografias.
- Deduplicação de eventos renomeada e simplificada, preservando IDs alternativos.
- GPS parcial, mal formatado ou infinito é rejeitado com erro controlado, sem interromper a execução abruptamente.
- Removida a correcção específica de 25-10-2026, mantendo a protecção genérica contra horas fictícias `00:00`.

## Auditoria v91 — Fontes e validação
- Listagens alternativas documentadas são consultadas mesmo quando a página principal contém links sem eventos válidos. Ligações relativas usam a página onde foram encontradas.
- URLs mal formados são descartados sem interromper a consulta da fonte.
- GPS é validado com os mesmos limites usados pelo mapa (continente, Madeira e Açores).
- Registos manuais sem validade ou com datas inválidas devolvem erros explícitos.
- A execução diária aplica a mesma bateria offline de testes Python e JavaScript da validação de código.

## Auditoria v92 — Sessões, IDs e interface compacta
- `identidade_eventos.py` protege contra a fusão de sessões do mesmo dia/título com horários, pontos de partida ou fichas oficiais individuais diferentes.
- A deduplicação do colector e do normalizador preserva preferencialmente o ID já publicado, mantendo aliases e GPS posteriormente confirmado.
- Registos incompletos não desaparecem silenciosamente: prosseguem até à validação do catálogo.
- Uma falha isolada de fonte continua a conservar anúncios futuros anteriormente confirmados, sem actualizar falsamente `last_confirmed_at`.
- Botões rápidos de distância e fim de semana e barra Filtros/Ordenar/Vistas ficaram menos altos, mantendo as opções e setas.
- Testes offline adicionais em `test_identidade_eventos.py` e `test_layout_compacto.cjs`.

## Auditoria v93 — Títulos e datas (fase 5.1)
- Análise do catálogo de 201 anúncios e relatório em `auditorias/fase_5_1_titulos_datas_2026-10-26.md`.
- Título oficial da caminhada **Montemuro: O Vale do Bestança | Cinfães** recuperado a partir do H1 verificado; correcção com proveniência registada.
- Retirados dois programas multidiários indevidos: expedição aos Pirinéus da Trekking Roots e passagem de ano da Mais Trilhos.
- `qualidade_anuncios.py` centraliza critérios de anúncios multidiários, títulos de cartão genéricos e datas explícitas contraditórias.
- O colector, a recuperação do catálogo e a normalização impedem a reentrada destes anúncios.
- Testes unitários acrescentados; restantes eventos, IDs, filtros, viagens e dificuldade preservados.

## Auditoria v94 — Locais e GPS (fase 5.2)
- Limpeza consistente em Python e JavaScript de finais de moradas interrompidos (por exemplo, `R`, `Av`, `n`, `Hora de`, `Coo`). Conservar o topónimo inteligível, sem inventar um endereço.
- Nas ligações para o Google Maps, nunca juntar `Por confirmar` à morada; acrescentar apenas localidade efectiva e ainda não presente no ponto de encontro.
- Testes de regressão para partidas e pesquisas do Google Maps; coordenadas GPS já publicadas não são substituídas automaticamente.
- Relatório: `auditorias/fase_5_2_locais_gps_2026-10-26.md`.

## Auditoria v95 — Programas multidiários disfarçados de caminhadas
- Quatro pacotes de 2 a 4 dias detectados com títulos que não mencionavam a duração; 3 fichas oficiais acessíveis e calendário detalhado do quarto.
- URL oficial individual documentado em `VERIFIED_MULTIDAY_URLS`. A validação actua tanto nos anúncios novos como nos anúncios históricos e antes da publicação final.
- Não excluir actividades apenas pelo preço elevado: o critério é a evidência do programa multidiário.
- Catálogo reduzido de 199 para 195 eventos, com IDs e campos restantes preservados.
- Relatório: `auditorias/fase_5_3_programas_multidiarios_2026-10-26.md`.
