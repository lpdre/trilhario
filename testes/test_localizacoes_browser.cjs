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
 ['Parque Desportivo Municipal de Mafra, R','Parque Desportivo Municipal de Mafra'],
 ['Entrada principal da Mesquita de Lisboa - Rua da Mesquita, n','Entrada principal da Mesquita de Lisboa - Rua da Mesquita'],
 ['Salinas do Samouco, Alcochete Hora de','Salinas do Samouco, Alcochete'],
 ['Largo do Chafariz de Dentro, Lisboa Coo','Largo do Chafariz de Dentro, Lisboa'],
 ['Junto à Igreja Matriz, Av','Junto à Igreja Matriz'],
 ['Ponto de encontro: Padaria Pitões, R. Outeiro 24, 5470-370 Pitões das Junias, Portugal','Padaria Pitões, R. Outeiro 24, 5470-370 Pitões das Junias, Portugal']
]);
for(const [raw,expected] of examples){
 assert.equal(scope.localPartidaLegivel(raw),expected,'Local incorrecto: '+raw);
}
// Garantia: o Google Maps não recebe «Por confirmar» como parte da morada.
const queryStart=source.indexOf('function googleMapsDeparture(');
const queryEnd=source.indexOf('const TRILHARIO_DELETE_ICON',queryStart);
assert(queryStart>=0 && queryEnd>queryStart,'Google Maps deve ter uma função de partida');
scope.fold=v=>String(v||'').toLocaleLowerCase('pt-PT');
scope.isPlacePlaceholder=v=>!v||['por confirmar','a confirmar','desconhecido','por definir'].includes(scope.fold(v));
scope.hasCoords=x=>Number.isFinite(Number(x.lat))&&Number.isFinite(Number(x.lon));
vm.runInNewContext(source.slice(queryStart,queryEnd),scope);
const query=(e,spot)=>new URL(scope.googleMapsDeparture(e,spot)).searchParams.get('query');
assert.equal(query({town:'Por confirmar',verified:false},'Posto de Turismo de Manteigas'),'Posto de Turismo de Manteigas, Portugal');
assert.equal(query({town:'Arouca',verified:false},'Parque de Campismo do Merujal'),'Parque de Campismo do Merujal, Arouca, Portugal');
assert.equal(query({town:'Arouca',verified:false},'Merujal, Arouca'),'Merujal, Arouca, Portugal');
assert.equal(query({town:'Por confirmar',verified:true,lat:40.8,lon:-8.2},'Merujal'),'40.8,-8.2');
console.log('OK: locais de partida e pesquisas Maps sem localidades fictícias ('+examples.size+' casos)');
