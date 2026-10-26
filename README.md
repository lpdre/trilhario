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
