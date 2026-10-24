'use strict';
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/../assets/js/trilhario.js','utf8');
const start=source.indexOf('function localPartidaLegivel(');
const end=source.indexOf('// Fonte desactivada:',start);
assert(start>=0&&end>start,'A função de limpeza deve existir no browser');
const scope={};
vm.runInNewContext(source.slice(start,end),scope);
const examples=new Map([
 ['Palácio Nacional de Sintra ( Palácio da Vila) Hora de Fim 23:00 (31-Out-2026) A hora de fim é a','Palácio Nacional de Sintra ( Palácio da Vila)'],
 ['Cabril (Pastelaria e Padaria de Cabril) 08h15 – Início da Etapa 16','Cabril (Pastelaria e Padaria de Cabril)'],
 ['Horário INÍCIO: 10:00H FINAL: 16:00H Em frente ao café','Por confirmar'],
 ['Horário INÍCIO: 10:00H FINAL: 16:00H Estacionamento jun','Por confirmar'],
 ['Tourém (Localização','Tourém'],
 ['Cruz da Jogadas (junto à Rota das Faias - início do per','Cruz da Jogadas'],
 ['Parque de Merendas','Por confirmar'],
 ['Posto de Turismo de Manteigas Coordenadas GPS Lat: N 40','Posto de Turismo de Manteigas'],
 ['Ponto de encontro: Padaria Pitões, R. Outeiro 24, 5470-370 Pitões das Junias, Portugal','Padaria Pitões, R. Outeiro 24, 5470-370 Pitões das Junias, Portugal']
]);
for(const [raw,expected] of examples){
 assert.equal(scope.localPartidaLegivel(raw),expected,'Local incorrecto: '+raw);
}
console.log('OK: locais de partida limpos antes de geocodificação ('+examples.size+' casos)');
