'use strict';
const assert=require('node:assert/strict');
const Weather=require('../assets/js/trilhario-weather.js');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');

const days=[...Weather.weekendDates('2026-11-01')].sort();
assert.deepEqual(days,['2026-11-07','2026-11-08','2026-11-14','2026-11-15']);
assert.deepEqual([...Weather.weekendDates('2026-11-07')].sort(),days);
assert.deepEqual([...Weather.weekendDates('2026-11-08')].sort(),[
 '2026-11-14','2026-11-15','2026-11-21','2026-11-22'
]);
assert.equal(Weather.condition(0).symbol,'☀️');
assert.equal(Weather.condition(3).symbol,'☁️');
assert.equal(Weather.condition(63).symbol,'🌧️');
assert.equal(Weather.condition(73).symbol,'🌨️');
assert.equal(Weather.condition(95).symbol,'⛈️');
assert.equal(Weather.condition(97).symbol,'⛈️');
assert.equal(Weather.condition(999),null);
assert.deepEqual(Weather.noonForecast({hourly:{
 time:['2026-11-07T09:00','2026-11-07T12:00'],
 temperature_2m:[4,11.2],weather_code:[0,63]
}},'2026-11-07'),{symbol:'🌧️',label:'Chuva',temp:11});
assert.equal(Weather.noonForecast({hourly:{
 time:['2026-11-08T12:00'],temperature_2m:[10],weather_code:[1]
}},'2026-11-07'),null,'não inventar previsão de outro dia');
const e={id:'g',title:'Levada da Víbora',date:'2026-11-07',
 verified:true,lat:41.561,lon:-7.982, town:'Cabeceiras de Basto'};
assert.equal(Weather.locationPlan(e).kind,'gps');
const multi={id:'m',title:'Rota das Faias de Manteigas',date:'2026-11-07',
 multiDay:true,town:'Manteigas',start:'Porto (ponto de encontro)',
 verified:true,lat:41.1628,lon:-8.5928};
assert.deepEqual(Weather.locationPlan(multi),{kind:'place',name:'Manteigas'});
assert.equal(Weather.locationPlan({
 title:'Fim de semana na Serra da Estrela',date:'2026-11-07',
 multiDay:true,town:'Lisboa',
 start:'Terminal Rodoviário do Oriente, Lisboa',
 lat:38.77,lon:-9.10,verified:true
}),null,'não apresentar tempo de Lisboa numa caminhada na Serra da Estrela');
assert.equal(Weather.locationPlan({id:'x',date:'2026-11-07',
 multiDay:true,town:'Por confirmar',start:'Porto',verified:true,lat:41.15,lon:-8.61}),null);
assert.equal(Weather.locationPlan({id:'u',date:'2026-11-07',
 town:'Por confirmar',start:'Por confirmar'}),null);
assert.equal(Weather.locationPlan({title:'Caminhada na Serra da Estrela',date:'2026-11-07',
 town:'Lisboa',start:'Terminal Rodoviário do Oriente, Lisboa',
 verified:true,lat:38.77,lon:-9.10}),null,
 'uma viagem de autocarro não é a previsão do trilho');
assert.deepEqual(Weather.placeOptions('Túmio, Freguesia de Bico – Paredes de Coura')[0],'Paredes de Coura');
(async()=>{
 let calls=0,geoCalls=0;
 const forecastJson={hourly:{time:['2026-11-07T12:00'],
  temperature_2m:[12.6],weather_code:[2]}};
 const fetchImpl=async url=>{
  calls++;
  if(url.startsWith('https://geocoding-api.open-meteo.com/')){
   geoCalls++;
   return {ok:true,json:async()=>({results:[{
    name:'Manteigas',country_code:'PT',latitude:40.402,longitude:-7.539
   }]})};
  }
  assert.match(url,/^https:\/\/api.open-meteo.com\/v1\/ecmwf\?/);
  const parsed=new URL(url);
  assert.equal(parsed.searchParams.get('forecast_days'),'15');
  assert.equal(parsed.searchParams.get('timezone'),'Europe/Lisbon');
  return {ok:true,json:async()=>forecastJson};
 };
 const controller=Weather.create({fetchImpl,today:()=> '2026-11-01',getEvent:()=>multi});
 const value=await controller.forecast(multi);
 assert.equal(value.temp,13);
 assert.equal(value.symbol,'⛅');
 assert.equal(value.name,'Manteigas');
 const again=await controller.forecast(multi);
 assert.deepEqual(again,value);
 assert.equal(calls,2,'mesma localidade e modelo devem usar cache');
 assert.equal(geoCalls,1);
 // Simular o carregamento real no navegador, sem injectar fetchImpl.
 // A função fetch nativa existe globalmente, não no âmbito lexical de factory().
 const browser={
  window:{},
  fetch:async url=>({ok:true,json:async()=>forecastJson}),
  URLSearchParams
 };
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../assets/js/trilhario-weather.js'),'utf8'),browser);
 const browserEngine=browser.window.TrilharioWeather.create({today:()=> '2026-11-01'});
 const browserForecast=await browserEngine.forecast(e);
 assert.equal(browserForecast.temp,13,'fetch global do navegador deve alimentar a previsão');
 assert.equal(browserForecast.symbol,'⛅','o cartão deve receber o símbolo do tempo');
 const other=await controller.forecast({...multi,date:'2026-11-28'});
 assert.equal(other,null,'nunca consultar datas fora dos dois fins de semana');
 assert.equal(calls,2);
 const node={dataset:{weatherId:'m'},isConnected:true,textContent:'',
  title:'',setAttribute(k,v){this[k]=v},removeAttribute(k){delete this[k]}};
 controller.observe([node]);
 for(let i=0;i<30;i++)await Promise.resolve();
 assert.equal(node.textContent,'⛅ 13°C');
 assert.match(node.title,/ECMWF IFS via Open-Meteo/);
 const noLocation=await controller.forecast({...multi,town:'Por confirmar'});
 assert.equal(noLocation,null);
 // Quando o endpoint ECMWF falha, usar a previsão genérica e identificar a origem.
 const urls=[];
 const fallback=Weather.create({
  today:()=> '2026-11-01',
  getEvent:()=>multi,
  fetchImpl:async url=>{
   urls.push(url);
   if(url.includes('geocoding-api'))return {ok:true,json:async()=>({results:[{
    name:'Manteigas',country_code:'PT',latitude:40.402,longitude:-7.539
   }]})};
   if(url.includes('/v1/ecmwf?'))return {ok:false};
   return {ok:true,json:async()=>forecastJson};
  }
 });
 const fromFallback=await fallback.forecast(multi);
 assert.equal(fromFallback.source,'Open-Meteo');
 assert.equal(fromFallback.temp,13);
 assert.ok(urls.some(url=>url.includes('/v1/forecast?')));
 // Depois de duas respostas inválidas a temperatura é desconhecida: nunca 0°C.
 const none=Weather.create({
  today:()=> '2026-11-01',
  getEvent:()=>multi,
  fetchImpl:async url=>url.includes('geocoding-api')?
   {ok:true,json:async()=>({results:[{name:'Manteigas',country_code:'PT',
    latitude:40.402,longitude:-7.539}]})}:{ok:false}
 });
 const missing=await none.forecast(multi);
 assert.equal(missing,null);
 console.log('OK: calendário, símbolos ECMWF, temperatura, localização, cache e apresentação');
})().catch(error=>{console.error(error);process.exitCode=1});
