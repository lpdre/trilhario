# Trilhário — Auditoria 5.2: partidas e coordenadas GPS
Data: 26-10-2026.

## Estado verificado
Catálogo observado: 199 anúncios de 17 organizadores (actualizado em 26-10 às 12:52 UTC).
- 26 anúncios mostram o local de partida como «Por confirmar». Não se deduz uma morada pelo nome da caminhada.
- Muitos anúncios, sobretudo GreenTrekker, têm uma partida textual legítima mas `town` vazio. O campo `town` vazio não implica que falte o ponto de encontro: não é necessário preencher o campo com localidades presumidas.
- 32 anúncios têm coordenadas. A existência de um GPS publicado não prova que esse seja o início físico do trilho: pode ser o ponto de encontro ou de transporte da organização.

## Erros inequívocos corrigidos
1. `googleMapsDeparture` acrescentava a expressão literal «Por confirmar» à pesquisa Google Maps de anúncios cuja partida estava correctamente preenchida mas `town` era desconhecido. Foi substituída por uma condição que só acrescenta localidades efectivamente utilizáveis e ainda não presentes na partida.
2. Algumas extracções conservavam finais sem sentido como «, R», «, n», «Hora de» ou «Coo», apesar de existir no mesmo campo uma referência de partida aproveitável. Limpeza conservadora e idêntica em Python e navegador, com testes de regressão.

## Atenção — GPS partilhados por eventos de locais diferentes
A auditoria detectou coordenadas repetidas em anúncios com localidades diferentes, por exemplo na Trekking Roots. A própria página «Rota das Faias e o Melhor do Outono de Manteigas» publica o ponto 41.162813, -8.592803, embora descreva uma caminhada na Serra da Estrela. Isso pode representar um ponto de encontro para transporte a partir do Porto, não uma coordenada falsa. **Não alterar nem substituir essas coordenadas sem conferir os detalhes de transporte e o ponto exacto de encontro**.
- Ficha do organizador: https://trekkingroots.pt/caminhada/rota-das-faias-e-o-melhor-do-outono-de-manteigas/
- Revisão futura: distinguir documentalmente ponto de encontro/logística de transporte de início do percurso.

## Restrições respeitadas
Sem geocodificar automaticamente localidades presumidas, criar GPS artificial, alterar títulos/datas/IDs, filtros, dificuldade ou cálculo de portagens. O JSON persistido só reflectirá a limpeza textual Python no próximo ciclo de normalização; o navegador passa a limpar e construir as ligações imediatamente.
