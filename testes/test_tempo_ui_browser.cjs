'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.join(__dirname,'..');
const page=fs.readFileSync(path.join(root,'index.html'),'utf8');
const main=fs.readFileSync(path.join(root,'assets/js/trilhario.js'),'utf8');
const addon=fs.readFileSync(path.join(root,'assets/js/trilhario-weather-ui.js'),'utf8');
assert.ok(page.indexOf('trilhario.js?v=')<page.indexOf('trilhario-weather.js?v='),
 'a aplicação deve arrancar antes de carregar a previsão');
assert.ok(page.indexOf('trilhario-weather.js?v=')<page.indexOf('trilhario-weather-ui.js?v='));
assert.equal(main.includes('TRILHARIO_WEATHER'),false,
 'a agenda nunca deve depender da existência da previsão');

// A meteorologia pode não estar acessível ou falhar ao inicializar.
// Não pode provocar uma exceção não tratada nem impedir o núcleo.
const empty={getElementById:()=>null};
assert.doesNotThrow(()=>vm.runInNewContext(addon,{window:{},document:empty,console:{info(){}},Promise}));
assert.doesNotThrow(()=>vm.runInNewContext(addon,{
 window:{TrilharioWeather:{create(){throw Error('falha de previsão simulada')}}},
 document:{getElementById:()=>({})},allEvents:()=>[],
 console:{info(){}}
}));

let installed=null,mounts=0,changed=null;
const row={
 dataset:{eid:'trilho-7'},
 slot:null,
 querySelector(selector){
  if(selector==='.v86-weather')return this.slot;
  if(selector==='.v74-trip-route')return {
   appendChild:node=>{this.slot=node;mounts++;}
  };
  return null;
 }
};
const list={
 querySelectorAll(selector){
  if(selector==='.walk-row[data-eid]')return [row];
  if(selector==='[data-weather-id]')return row.slot?[row.slot]:[];
  return [];
 }
};
const weather={
 create:()=>({observe:slots=>{installed=[...slots]}}),
 weekendDates:()=>new Set(['2026-11-07','2026-11-08','2026-11-14','2026-11-15']),
 locationPlan:()=>({kind:'gps',lat:40.5,lon:-8.1})
};
const context={
 window:{TrilharioWeather:weather},
 document:{getElementById:id=>id==='listView'?list:null,
           createElement:()=>({dataset:{},setAttribute(k,v){this[k]=v}})},
 allEvents:()=>[{id:'trilho-7',date:'2026-11-07',lat:40.5,lon:-8.1}],
 agendaClock:()=>({date:'2026-11-01'}),
 MutationObserver:class{constructor(callback){changed=callback}observe(){}},
 requestAnimationFrame:fn=>fn(),
 Promise,
 console:{info(){}}
};
vm.runInNewContext(addon,context);
assert.equal(mounts,1,'apenas um espaço meteorológico na viagem');
assert.equal(row.slot.className,'v86-weather');
assert.equal(row.slot.dataset.weatherId,'trilho-7');
assert.equal(row.slot.textContent,'…','mostrar consulta enquanto carrega a temperatura');
assert.equal(installed.length,1);
changed([{addedNodes:[{nodeType:1,matches:selector=>selector.includes('.walk-row')}]}]);
assert.equal(mounts,1,'mutações repetidas não duplicam indicadores');

// Mesmo existindo uma viagem na lista, não criar indicadores para outras datas.
row.dataset.eid='trilho-21';row.slot=null;
context.allEvents=()=>[{id:'trilho-21',date:'2026-11-21'}];
changed([{addedNodes:[{nodeType:1,matches:selector=>selector.includes('.walk-row')}]}]);
assert.equal(mounts,1,'fora dos dois fins de semana não consultar meteorologia');

// Teste integrado: a camada opcional tem de obter dados e escrever a temperatura
// no nó real do cartão; um teste que apenas cria o <span> não chega.
(async()=>{
 const RealWeather=require('../assets/js/trilhario-weather.js');
 const event={id:'live-7',date:'2026-11-07',title:'Levada da Víbora',
  verified:true,lat:41.561,lon:-7.982,town:'Cabeceiras de Basto'};
 let slot=null,networkCalls=0;
 const realList={
  querySelectorAll(selector){
   if(selector==='.walk-row[data-eid]')return [realRow];
   if(selector==='[data-weather-id]')return slot?[slot]:[];
   return [];
  }
 };
 const realRow={
  dataset:{eid:event.id},
  querySelector(selector){
   if(selector==='.v86-weather')return slot;
   if(selector==='.v74-trip-route')return {appendChild:n=>{slot=n}};
   return null;
  }
 };
 const getForecast=async url=>{
  networkCalls++;
  assert.match(url,/^https:\/\/api.open-meteo.com\/v1\/ecmwf\?/);
  return {ok:true,json:async()=>({hourly:{
   time:['2026-11-07T12:00'],temperature_2m:[11.4],weather_code:[2]
  }})};
 };
 const realContext={
  window:{TrilharioWeather:{...RealWeather,
   create:opts=>RealWeather.create({...opts,fetchImpl:getForecast})}},
  document:{
   getElementById:id=>id==='listView'?realList:null,
   createElement:()=>({dataset:{},isConnected:true,textContent:'',
    setAttribute(k,v){this[k]=v},removeAttribute(k){delete this[k]}}),
   addEventListener(){}
  },
  allEvents:()=>[event],
  agendaClock:()=>({date:'2026-11-01'}),
  requestAnimationFrame:fn=>fn(),
  Promise,
  console:{info(){}}
 };
 vm.runInNewContext(addon,realContext);
 assert.equal(slot.textContent,'…','o indicador é visível enquanto consulta');
 // Dar oportunidade às promessas internas de recolher e apresentar a previsão.
 for(let i=0;i<25;i++)await Promise.resolve();
 assert.equal(slot.textContent,'⛅ 11°C');
 assert.match(slot.title,/ECMWF IFS via Open-Meteo/);
 assert.equal(networkCalls,1);
 console.log('OK: módulos separados, indicadores e temperatura real simulada no cartão');
})().catch(error=>{console.error(error);process.exitCode=1});

