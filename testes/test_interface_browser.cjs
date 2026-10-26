'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const js=fs.readFileSync(__dirname+'/../assets/js/trilhario.js','utf8');
const html=fs.readFileSync(__dirname+'/../index.html','utf8');
const css=fs.readFileSync(__dirname+'/../assets/css/trilhario.css','utf8');
const segment=(a,b)=>{const start=js.indexOf(a),end=js.indexOf(b,start);assert.ok(start>=0&&end>start,'intervalo não encontrado: '+a);return js.slice(start,end)};

// Regressões de estrutura, acções e preservação da dificuldade.
assert.ok(js.includes('data-event-action="toggleCompare"'),'o cartão permite comparar');
assert.ok(js.includes('aria-pressed="${compared.has(x.id)}"'),'selecção acessível');
assert.ok(js.includes('button[data-event-action="toggleCompare"]'),'actualização do botão');
assert.ok(css.includes('.walk-title-row'),'comparação compacta na linha do título');
assert.ok(!js.includes('onclick='),'sem atributos onclick');
assert.ok(html.includes('id="compareTray"'),'barra de comparação presente');
assert.ok(html.includes('trilhario-routes.js?v=87'),'módulo de rotas antes do frontend');
assert.ok(js.includes("case 'difficulty'"),'dificuldade na comparação');

// Comparar sem redesenhar toda a lista; não contar IDs de eventos já ausentes.
const active=[{id:'a',title:'Arouca'},{id:'b',title:'Gerês'},{id:'c',title:'Lousã'}];
const dom={
 compareTray:{hidden:true},compareQty:{textContent:''},compareNames:{textContent:''},
 compareOpen:{classList:{toggle(name,yes){this[name]=yes;}},setAttribute(name,v){this[name]=v;}}
};
const buttons=active.map(e=>({
 dataset:{eventId:e.id,eventTitle:e.title},textContent:'',
 classList:{toggle(name,yes){this[name]=yes;}},setAttribute(name,v){this[name]=v;}
}));
const body={classList:{toggle(name,yes){this[name]=yes;}}};
let saved=0,redraws=0;
const cmp={
 compared:new Set(['antigo']),COMPARE_PAGE_MODE:false,ORGANIZERS_PAGE_MODE:false,
 document:{body,querySelectorAll:()=>buttons},$:id=>dom[id],
 allEvents:()=>active,persistTravel:()=>{saved++;return true;},
 renderComparison:()=>{redraws++;},toast:()=>{}
};
vm.runInNewContext(segment('function availableCompared(){','function travelSortVal('),cmp);
cmp.renderCompareTray();
assert.equal(dom.compareTray.hidden,true,'IDs antigos sem correspondência não devem apresentar barra');
cmp.toggleCompare('a');
assert.equal(dom.compareQty.textContent,'1 seleccionada');
assert.equal(dom.compareOpen['aria-disabled'],'true');
assert.equal(buttons[0]['aria-pressed'],'true');
assert.equal(buttons[0].textContent,'✓ Seleccionado');
cmp.toggleCompare('b');
assert.equal(dom.compareQty.textContent,'2 seleccionadas');
assert.equal(dom.compareOpen['aria-disabled'],'false');
assert.equal(redraws,0,'a selecção não reconstrói a lista inteira');
cmp.clearCompare();
assert.equal(cmp.compared.size,0);
assert.equal(dom.compareTray.hidden,true);
assert.equal(buttons[0]['aria-pressed'],'false');
assert.equal(saved,3);

// Testar o cartão renderizado nas duas situações.
const cardEnv={
 displayDeparture:e=>e.start,eventPhotoUrl:()=>'',organizerHomepage:()=>'',isPlacePlaceholder:()=>false,
 googleMapsDeparture:()=>'',esc:s=>String(s??''),legibleEventTitle:e=>e.title,
 safeExternalUrl:()=>'',eventFreshnessNote:()=>'',fmtN:n=>String(n),
 dur:e=>String(e.duration),fmtP:n=>String(n),travelRow:()=>'',compared:new Set(),
 names:['','Fácil','Moderada','Exigente','Difícil','Muito difícil']
};
vm.runInNewContext(segment('function eventRow(x){','function chips(){'),cardEnv);
const evt={id:'a',date:'2026-11-01',title:'Trilho das Faias',organizer:'X',
 start:'Arouca',time:'09:00',duration:4,km:15,gain:450,price:18,difficulty:4};
const before=cardEnv.eventRow(evt);
assert.ok(before.includes('>Comparar</button>'));
assert.ok(before.includes('aria-pressed="false"'));
assert.ok(before.includes('Dificuldade:'));
cardEnv.compared.add('a');
const after=cardEnv.eventRow(evt);
assert.ok(after.includes('>✓ Seleccionado</button>'));
assert.ok(after.includes('aria-pressed="true"'));

// A selecção dos filtros não pode depender da dificuldade.
const walk=[
 {id:'a',date:'2026-11-01',time:'09:00',title:'A',organizer:'X',km:18,gain:500,difficulty:5},
 {id:'b',date:'2026-11-02',time:'09:00',title:'B',organizer:'Y',km:10,gain:200,difficulty:1},
 {id:'c',date:'2026-11-03',time:'09:00',title:'C',organizer:'X',km:26,gain:900,difficulty:2}
];
const filters={
 KM_CAP:50,GAIN_CAP:2500,state:{weekend:'all',day:'all',organizer:'X',kmMin:15,kmMax:50,gainMin:400,gainMax:2500},
 agendaClock:()=>({}),weekendWindows:()=>({}),eventHasNotStarted:()=>true,allEvents:()=>walk
};
vm.runInNewContext(segment('function selected({ignoreDay=false}={})','function dateShort('),filters);
assert.deepEqual([...filters.selected()].map(e=>e.id),['a','c']);
filters.state.day='2026-11-03';
assert.deepEqual([...filters.selected()].map(e=>e.id),['c']);
assert.deepEqual([...filters.selected({ignoreDay:true})].map(e=>e.id),['a','c']);

// Duração, km, combustível e portagens calculados por ida + volta distintas.
const tripCtx={
 travelPrefs:{origin:'Aveiro',consumption:5,fuel:2},ambiguousDeparture:()=>false,
 routeFresh:()=>true,tollFresh:r=>r.tollChecked>0,
 travelData:()=>({kmOne:75,kmBack:84,minutesOne:70,minutesBack:90,tollOut:3,tollBack:4,tollChecked:123})
};
vm.runInNewContext(segment('function tripCalc(e){','function timeStr('),tripCtx);
const cost=tripCtx.tripCalc({price:30});
assert.equal(cost.km,159);
assert.equal(cost.minutes,160);
assert.equal(cost.fuel,15.9);
assert.equal(cost.toll,7);
assert.equal(cost.total,22.9,'a inscrição não integra o custo da deslocação');
console.log('OK: comparação, cartão, filtros e cálculos separados de ida e volta');
