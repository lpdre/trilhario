'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const s=fs.readFileSync(__dirname+'/../assets/js/trilhario.js','utf8');
const start=s.indexOf('let normalizedEventsCache=null;');
const end=s.indexOf('function catalogToday()',start);
assert(start>0&&end>start);
const compiled=s.slice(start,end);
// Catálogo isolado: verificar fontes oficiais, falhas e registos pessoais.
const ctx={
  remoteFeedState:'ready',remoteEvents:[{id:'recolhido',date:'2026-11-01',title:'Caminhada oficial',organizer:'X',start:'Arouca',url:'https://exemplo.pt/1'}],
  normalizedEventsCache:null, custom:[],
  catalogToday:()=> '2026-10-23',isTrilhosCaminhadasSource:()=>false,
  hasCoords:()=>false,parsePublishedGps:()=>null,legibleEventTitle:e=>e.title,displayDeparture:e=>e.start,
  localStorage:{setItem(){}}
};
vm.runInNewContext(compiled,ctx);
let items=ctx.allEvents();
assert.equal(items.length,1,'com o JSON online apenas existe o evento oficial');
assert.equal(items[0].id,'recolhido');
assert.equal(items[0].km,undefined,'META de exemplo não afecta os eventos reais');
ctx.remoteEvents=[{id:'oficial',alias_ids:['manual'],date:'2026-11-01',title:'Com alias',organizer:'X'}];
items=ctx.allEvents();
assert.equal(items.length,1,'um ID alternativo não gera um segundo evento');
ctx.remoteEvents=[];
items=ctx.allEvents();
assert.equal(items.length,0,'um catálogo online vazio não acrescenta eventos locais');
ctx.remoteFeedState='loading';ctx.remoteEvents=null;
items=ctx.allEvents();
assert.equal(items.length,0,'durante a consulta não surgem anúncios fictícios');
ctx.remoteFeedState='unavailable';
items=ctx.allEvents();
assert.equal(items.length,0,'em falha não apresentar eventos fictícios');
ctx.remoteFeedState='ready';ctx.remoteEvents=[{id:'real',date:'2026-11-01',title:'Evento',organizer:'X'}];
ctx.custom=[{id:'meu',date:'2026-11-02',title:'Evento pessoal',organizer:'Eu'}];
items=ctx.allEvents();
assert.equal(items.length,2,'eventos inseridos pelo utilizador preservados');
const html=fs.readFileSync(__dirname+'/../index.html','utf8');
const css=fs.readFileSync(__dirname+'/../assets/css/trilhario.css','utf8');
assert.equal(s.includes('const SEED='),false,'catálogo fictício não deve existir');
assert.equal(s.includes('const META='),false,'metadados de demonstração não devem existir');
assert.equal(html.includes('id="eventForm"'),false,'formulário descontinuado não deve estar no HTML');
assert.equal(css.includes('.walk-favorite'),false,'estilos de favoritos descontinuados');
console.log('OK: catálogo oficial, falhas sem anúncios fictícios, eventos antigos preservados e limpeza HTML/CSS');
