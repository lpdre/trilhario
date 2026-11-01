'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../assets/js/trilhario.js','utf8');
const css=fs.readFileSync(__dirname+'/../assets/css/trilhario.css','utf8');
const start=source.indexOf('function weekendWindows(');
const end=source.indexOf('function agendaUpcomingFingerprint(',start);
assert.ok(start>=0&&end>start);
const weekendCode=source.slice(start,end);
const buttons=['this','next','following'].map(type=>({
 dataset:{quickWeekend:type},hidden:false,disabled:false,children:[],
 attributes:{},
 classList:{add(){},remove(){},toggle(){}},
 replaceChildren(...children){this.children=children},
 setAttribute(key,value){this.attributes[key]=value}
}));
let today={date:'2026-11-01',minute:11*60};
let events=[
 {id:'done',date:'2026-11-01',time:'09:30',title:'Caminhada já iniciada'},
 {id:'done-multi',date:'2026-11-01',time:'07:00',multiDay:true,title:'Programa já iniciado'},
 {id:'next',date:'2026-11-07',time:'08:30',title:'Próximo sábado'}
];
const state={weekend:'this'};
const context={
 Date,Intl,state,
 agendaClock:()=>today,
 allEvents:()=>events,
 document:{
  querySelectorAll:selector=>selector==='[data-quick-weekend]'?buttons:[],
  createElement:()=>({className:'',textContent:''})
 }
};
vm.runInNewContext(weekendCode,context);
const current=context.weekendWindows(today);
assert.equal(current.this.from,'2026-10-31');
assert.equal(current.this.to,'2026-11-01');
assert.equal(current.next.from,'2026-11-07');
context.updateWeekendQuickFilters();
assert.equal(buttons[0].hidden,true,'ocultar fim de semana já sem saídas');
assert.equal(buttons[0].disabled,true);
assert.equal(state.weekend,'all','limpar filtro que deixou de ter resultados');
assert.equal(buttons[1].hidden,false);
assert.equal(buttons[1].children[0].textContent,'7–8');
assert.equal(context.eventHasNotStarted(events[1],today),false,
 'um programa de vários dias deixa de estar disponível depois da hora de início');
assert.equal(context.eventHasNotStarted({date:'2026-11-01',time:'15:00'},today),true);
events.push({id:'late',date:'2026-11-01',time:'15:00'});
context.updateWeekendQuickFilters();
assert.equal(buttons[0].hidden,false,'não esconder fins de semana com saídas futuras');
today={date:'2026-11-01',minute:16*60};
context.updateWeekendQuickFilters();
assert.equal(buttons[0].hidden,true,'ocultar após a última saída');
assert.match(css,/\.v83-strip > button\[hidden\]\{display:none!important\}/);
console.log('OK: fim de semana termina após a última partida, incluindo programas multidiários');
