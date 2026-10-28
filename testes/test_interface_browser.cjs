'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const s=fs.readFileSync(__dirname+'/../assets/js/trilhario.js','utf8');
const html=fs.readFileSync(__dirname+'/../index.html','utf8');
const css=fs.readFileSync(__dirname+'/../assets/css/trilhario.css','utf8');
const section=(a,b)=>{const start=s.indexOf(a),end=s.indexOf(b,start);assert.ok(start>=0&&end>start,'Secção ausente '+a);return s.slice(start,end);};
const obsolete=/\bcompared\b|\bcomparison\b|\bcompareTray\b|\bTRAVEL_COMPARE_KEY\b|\bCOMPARE_PAGE_MODE\b|\bcomparação\b|\bcomparar\b/i;
for(const file of [s,html,css])assert.equal(obsolete.test(file),false,'comparação removida integralmente');
assert.equal(s.includes('onclick='),false,'eventos continuam delegados');
const card={displayDeparture:e=>e.start,eventPhotoUrl:()=>'',organizerHomepage:()=>'',isPlacePlaceholder:()=>false,googleMapsDeparture:()=>'',esc:x=>String(x??''),legibleEventTitle:e=>e.title,safeExternalUrl:()=>'',eventFreshnessNote:()=>'',fmtN:x=>String(x),dur:e=>String(e.duration),fmtP:x=>String(x),travelRow:()=>'',names:['','Fácil','Moderada','Exigente','Difícil','Muito difícil']};
vm.runInNewContext(section('function eventRow(x){','function chips(){'),card);
const row=card.eventRow({id:'t',date:'2026-11-01',title:'Trilho das Faias',organizer:'X',start:'Arouca',time:'09:00',duration:4,km:15,gain:450,price:18,difficulty:4});
assert.ok(row.includes('Trilho das Faias'));
assert.ok(row.includes('Dificuldade:'));
const e=[{id:'a',date:'2026-11-01',time:'09:00',title:'A',organizer:'X',km:18,gain:500},{id:'b',date:'2026-11-02',time:'09:00',title:'B',organizer:'Y',km:10,gain:200},{id:'c',date:'2026-11-03',time:'09:00',title:'C',organizer:'X',km:26,gain:900}];
const filt={KM_CAP:50,GAIN_CAP:2500,state:{weekend:'all',day:'all',organizer:'X',kmMin:15,kmMax:50,gainMin:400,gainMax:2500},agendaClock:()=>({}),weekendWindows:()=>({}),eventHasNotStarted:()=>true,allEvents:()=>e};
vm.runInNewContext(section('function selected({ignoreDay=false}={})','function dateShort('),filt);
assert.deepEqual([...filt.selected()].map(x=>x.id),['a','c']);
filt.state.day='2026-11-03';
assert.deepEqual([...filt.selected()].map(x=>x.id),['c']);
const trip={travelPrefs:{origin:'Aveiro',consumption:5,fuel:2},ambiguousDeparture:()=>false,routeFresh:()=>true,tollFresh:r=>r.tollChecked>0,travelData:()=>({kmOne:75,kmBack:84,minutesOne:70,minutesBack:90,tollOut:3,tollBack:4,tollChecked:123})};
vm.runInNewContext(section('function tripCalc(e){','function timeStr('),trip);
const calc=trip.tripCalc({price:30});
assert.equal(calc.km,159);assert.equal(calc.minutes,160);assert.equal(calc.fuel,15.9);assert.equal(calc.toll,7);assert.equal(calc.total,22.9);
// As portagens devem ser calculadas sem botões nos cartões.
const tripCard={
  tollApiEndpoint:'/.netlify/functions/portagens',
  travelPrefs:{origin:'Aveiro'},tripCalc:()=>({km:145.5,minutes:120,fuel:15,toll:null,total:null}),
  travelData:()=>({precomputed:true}),routeCacheKey:()=> 'aveiro|evento',
  tripProblems:new Map(),departureCandidates:()=>['Arouca'],
  ambiguousDeparture:()=>false,tripOriginProblem:'',
  fmtN:x=>String(x),timeStr:()=> '2h 00min',travelMoney:()=> '15,00 €',
  esc:x=>String(x??'')
};
vm.runInNewContext(section('function travelRow(e){','// Delegação:'),tripCard);
const withoutTolls=tripCard.travelRow({id:'evento'});
assert.ok(withoutTolls.includes('Portagens <strong>—</strong>'),'portagens em falta sem inventar zero');
assert.ok(withoutTolls.includes('Combustível'),'combustível continua disponível');
assert.ok(!withoutTolls.includes('Calcular portagens'),'botão manual eliminado');
assert.ok(!withoutTolls.includes('Repetir portagens'),'botão de repetição eliminado');
assert.ok(!withoutTolls.includes('data-event-action="calculateOneRoute"'),'cálculo automático, sem botão na viagem válida');

const auto={
  travelData:()=>({precomputed:true}),routeCacheKey:()=> 'aveiro|evento',
  tripRetryAfter:new Map(),tripProblems:new Map(),
  routeFresh:()=>true,tollsDue:()=>true,getRouteGeometry:()=>null
};
vm.runInNewContext(section('function tripNeedsRoute(e,force=false){','function scheduleCachedTolls('),auto);
assert.equal(auto.tripNeedsRoute({id:'evento'}),true,'rota pré-calculada necessita de traçado para portagens');
auto.getRouteGeometry=()=>({out:[[0,0],[1,1]],back:[[1,1],[0,0]]});
assert.equal(auto.tripNeedsRoute({id:'evento'}),false,'não repetir cálculo com traçado disponível');
auto.getRouteGeometry=()=>null;auto.tollsDue=()=>false;
assert.equal(auto.tripNeedsRoute({id:'evento'}),false,'respeitar validade e espera das portagens');
console.log('OK: comparação removida, cartões, filtros, dificuldade, viagens e portagens automáticas');
