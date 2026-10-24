'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const s=fs.readFileSync(__dirname+'/../assets/js/trilhario.js','utf8');
const start=s.indexOf('function migrateComparedAliases(');
const end=s.indexOf('// Num alojamento web',start);
assert(start>0&&end>start);
const compiled=s.slice(start,end);
// A partir da v47A, a migração dos IDs usa o auxiliar de persistência.
// Este teste isola o catálogo: fornecer um substituto e verificar a chamada.
const writes=[];
const ctx={
  remoteFeedState:'ready',remoteEvents:[{id:'recolhido',date:'2026-11-01',title:'Caminhada oficial',organizer:'X',start:'Arouca',url:'https://exemplo.pt/1'}],
  normalizedEventsCache:null, custom:[], SEED:[{id:'demo',date:'2026-11-01',title:'Demo',organizer:'Y',start:'Aveiro'}],META:{demo:{km:4}},
  catalogToday:()=> '2026-10-23',excludedOrganizer:()=>false,isTrilhosCaminhadasSource:()=>false,
  hasCoords:()=>false,parsePublishedGps:()=>null,legibleEventTitle:e=>e.title,displayDeparture:e=>e.start,
  compared:new Set(['manual','desconhecido']),TRAVEL_COMPARE_KEY:'comparacoes',
  persistValue:(key,value,quiet)=>{writes.push({key,value,quiet});return true;},localStorage:{setItem(){}}
};
vm.runInNewContext(compiled,ctx);
let items=ctx.allEvents();
assert.equal(items.length,1,'com o JSON online apenas existe o evento oficial');
assert.equal(items[0].id,'recolhido');
assert.equal(items[0].km,undefined,'META de exemplo não afecta os eventos reais');
ctx.remoteEvents=[{id:'oficial',alias_ids:['manual'],date:'2026-11-01',title:'Com alias',organizer:'X'}];
items=ctx.allEvents();
assert.equal(ctx.compared.has('oficial'),true,'comparação migrada para ID oficial');
assert.equal(ctx.compared.has('manual'),false);
assert.equal(ctx.compared.has('desconhecido'),true,'ID temporariamente ausente é conservado');
assert.equal(writes.length,1,'migração guardada uma única vez');
assert.equal(writes[0].key,'comparacoes');
assert.deepEqual([...writes[0].value].sort(),['desconhecido','oficial']);
ctx.remoteEvents=[];
items=ctx.allEvents();
assert.equal(items.length,0,'um catálogo online vazio não acrescenta eventos locais');
ctx.remoteFeedState='loading';ctx.remoteEvents=null;
items=ctx.allEvents();
assert.equal(items.length,0,'durante a consulta não surgem anúncios fictícios');
ctx.remoteFeedState='unavailable';
items=ctx.allEvents();
assert.equal(items.length,1,'em falha pode mostrar demo claramente identificada');
assert.equal(items[0].id,'demo');
assert.equal(items[0].km,4);
ctx.remoteFeedState='ready';ctx.remoteEvents=[{id:'real',date:'2026-11-01',title:'Evento',organizer:'X'}];
ctx.custom=[{id:'meu',date:'2026-11-02',title:'Evento pessoal',organizer:'Eu'}];
items=ctx.allEvents();
assert.equal(items.length,2,'eventos inseridos pelo utilizador preservados');
console.log('OK: JSON único, vazio, carregamento, demonstração, eventos pessoais');
