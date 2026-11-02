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
assert.deepEqual(Weather.locationPlan(e),
 {kind:'gps',lat:41.561,lon:-7.982,name:'Cabeceiras de Basto',approximate:true},
 'GPS próximo do percurso continua a ser melhor que o centro da cidade');
const precise={...e,weatherLat:41.52,weatherLon:-8.02,weatherLocation:'Ponto central do trilho'};
assert.deepEqual(Weather.locationPlan(precise),
 {kind:'gps',lat:41.52,lon:-8.02,name:'Ponto central do trilho',approximate:false});
const multi={id:'m',title:'Rota das Faias de Manteigas',date:'2026-11-07',
 multiDay:true,town:'Manteigas',start:'Porto (ponto de encontro)',
 verified:true,lat:41.1628,lon:-8.5928};
assert.deepEqual(Weather.locationPlan(multi),
 {kind:'place',name:'Manteigas',approximate:true});
assert.deepEqual(Weather.locationPlan({
 title:'Fim de semana na Serra da Estrela',date:'2026-11-07',
 multiDay:true,town:'Lisboa',
 start:'Terminal Rodoviário do Oriente, Lisboa',
 lat:38.77,lon:-9.10,verified:true
}),{kind:'place',name:'Serra da Estrela',approximate:true},
 'uma caminhada na Estrela não deve usar a previsão de Lisboa');
assert.equal(Weather.locationPlan({id:'x',date:'2026-11-07',
 multiDay:true,town:'Por confirmar',start:'Porto',verified:true,lat:41.15,lon:-8.61}),null);
assert.equal(Weather.locationPlan({id:'u',date:'2026-11-07',
 town:'Por confirmar',start:'Por confirmar'}),null);
assert.deepEqual(Weather.locationPlan({title:'Caminhada na Serra da Estrela',date:'2026-11-07',
 town:'Lisboa',start:'Terminal Rodoviário do Oriente, Lisboa',
 verified:true,lat:38.77,lon:-9.10}),
 {kind:'place',name:'Serra da Estrela',approximate:true},
 'uma viagem de autocarro não deve gerar previsão da partida');
assert.deepEqual(Weather.placeOptions('Túmio, Freguesia de Bico – Paredes de Coura')[0],'Paredes de Coura');

assert.equal(Weather.startLocality('Junto à Câmara Municipal,Rua 1º de Maio, Manteigas'),'Manteigas');
assert.equal(Weather.startLocality('Parque Desportivo Municipal de Mafra'),'Mafra');
assert.equal(Weather.startLocality('Em Loriga junto ao Restaurante Vicente'),'Loriga');
assert.equal(Weather.startLocality('Terminal Rodoviário do Oriente'),'');
const catalog=JSON.parse(fs.readFileSync(path.join(__dirname,'../eventos.json'),'utf8')).events;
const valinhas=catalog.find(x=>x.id==='web-5b4218700508ce0')||{
 id:'web-5b4218700508ce0',date:'2026-11-14',title:'Além do Trilho',
 url:'https://maistrilhos.pt/caminhadas/alem-do-trilho',
 start:'Parque de lazer de Valinhas',town:'Por confirmar'};
assert.deepEqual(Weather.locationPlan(valinhas),
 {kind:'gps',lat:41.305067,lon:-8.449997,
 name:'Parque de Lazer de Valinhas, Santo Tirso',approximate:true},
 'Além do Trilho localiza-se em Santo Tirso, não numa Valinhas desconhecida');
assert.equal(Weather.locationPlan({...valinhas,url:'https://example.org/walk'}),null,
 'não atribuir coordenadas de Valinhas a outros eventos com nome semelhante');

assert.deepEqual(Weather.locationPlan({
 id:'carvao',title:'Pelos trilhos do carvão',date:'2026-11-07',
 town:'Por confirmar',start:'Junto à Câmara Municipal,Rua 1º de Maio, Manteigas'
}),{kind:'place',name:'Manteigas',approximate:true},
 'a descrição do ponto de encontro contém uma localidade utilizável');
assert.deepEqual(Weather.locationPlan({
 id:'mafra',title:'De Mafra ao Atlântico',date:'2026-11-07',
 town:'Por confirmar',start:'Parque Desportivo Municipal de Mafra'
}),{kind:'place',name:'Mafra',approximate:true},
 'o centro de Mafra é referência aproximada, não localização do percurso inteiro');
assert.deepEqual(Weather.locationPlan({
 id:'faias-lisboa',title:'Caminhando na Rota das Faias - Serra da Estrela',
 date:'2026-11-07',town:'Lisboa',start:'Terminal Rodoviário do Oriente',
 multiDay:true,lat:38.7675,lon:-9.1019,verified:true
}),{kind:'place',name:'Manteigas',approximate:true},
 'não mostrar tempo de Lisboa numa viagem às Faias');
assert.deepEqual(Weather.locationPlan({
 id:'faias-porto',title:'Rota das Faias e o Melhor do Outono de Manteigas',
 date:'2026-11-07',town:'Porto',start:'Porto (ponto de encontro)',
 multiDay:true,lat:41.1628,lon:-8.5928,verified:true
}),{kind:'place',name:'Manteigas',approximate:true},
 'um ponto de recolha no Porto nunca prevalece sobre o destino do título');
assert.equal(Weather.locationPlan({
 title:'Fim de semana nas montanhas',date:'2026-11-07',
 town:'Porto',start:'Porto',multiDay:true
}),null,'não inventar tempo do Porto quando não se conhece o destino');
assert.deepEqual(Weather.locationPlan({
 id:'loriga',title:'KM Vertical/Serra da Estrela',date:'2026-11-14',
 town:'Por confirmar',start:'Em Loriga junto ao Restaurante Vicente'
}),{kind:'place',name:'Loriga',approximate:true},
 'em regiões amplas preferir a aldeia explícita à localização genérica da serra');

(async()=>{
 const valinhasForecast=Weather.create({today:()=> '2026-11-02',
  fetchImpl:async url=>{
   if(url.includes('/v1/ecmwf'))return {ok:true,json:async()=>({hourly:{
    time:['2026-11-09T12:00'],temperature_2m:[12],weather_code:[1]}})};
   assert.match(url,/^https:\/\/api\.open-meteo\.com\/v1\/forecast\?/);
   return {ok:true,json:async()=>({hourly:{
    time:['2026-11-14T12:00'],temperature_2m:[14.1],weather_code:[2]}})};
  }});
 const valinhasResult=await valinhasForecast.forecast(valinhas);
 assert.equal(valinhasResult.temp,14);
 assert.equal(valinhasResult.url,
  'https://www.windy.com/41.3051/-8.4500?ecmwf,temp,2026-11-14-12,41.3051,-8.4500,10,d:picker',
  'Windy deve abrir em Valinhas (Santo Tirso), dia 14 de Novembro');
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
  assert.equal(parsed.searchParams.get('forecast_days'),'10');
  assert.equal(parsed.searchParams.get('timezone'),'Europe/Lisbon');
  return {ok:true,json:async()=>forecastJson};
 };
 const controller=Weather.create({fetchImpl,today:()=> '2026-11-01',getEvent:()=>multi});
 const value=await controller.forecast(multi);
 assert.equal(value.temp,13);
 assert.equal(value.symbol,'⛅');
 assert.equal(value.name,'Manteigas');
 assert.equal(value.url,
  'https://www.windy.com/40.4020/-7.5390?ecmwf,temp,2026-11-07-12,40.4020,-7.5390,10,d:picker');
 const again=await controller.forecast(multi);
 assert.deepEqual(again,value);
 assert.equal(calls,2,'mesma localidade e modelo devem usar cache');
 assert.equal(geoCalls,1);
 // Dados reais do catálogo de 7 de Novembro: dois organizadores
 // recolhem passageiros em Lisboa ou no Porto para a Rota das Faias.
 // Verificar endereço final, não apenas a localidade escolhida.
 const catalogue=JSON.parse(fs.readFileSync(path.join(__dirname,'../eventos.json'),'utf8')).events;
 const actualIds=['web-6af928d82a9819f','web-e4ed9df2552123a'];
 const examples=[
  {id:actualIds[0],title:'Caminhando na Rota das Faias - Serra da Estrela',
   date:'2026-11-07',multiDay:true,town:'Lisboa',
   start:'Terminal Rodoviário Junto à Estação do Oriente (PERTO DO AKI)',
   lat:38.76750556,lon:-9.10195278,verified:true},
  {id:actualIds[1],title:'Rota das Faias e o Melhor do Outono de Manteigas',
   date:'2026-11-07',multiDay:true,town:'Manteigas',
   start:'Porto (ponto de encontro)',lat:41.162813,lon:-8.592803,verified:true}
 ];
 for(const fallbackRecord of examples){
  const actual=catalogue.find(item=>item.id===fallbackRecord.id)||fallbackRecord;
  assert.deepEqual(Weather.locationPlan(actual),
   {kind:'place',name:'Manteigas',approximate:true},
   'o ponto de recolha do anúncio '+fallbackRecord.id+' não pode ser destino meteorológico');
  const isolated=Weather.create({fetchImpl,today:()=> '2026-11-01'});
  const result=await isolated.forecast(actual);
  assert.equal(result.url,value.url,
   'o link Windy do anúncio '+fallbackRecord.id+' tem de centrar o mapa em Manteigas');
  assert.ok(!result.url.includes('41.1628,-8.5928')&&!result.url.includes('38.7675,-9.1019'),
   'não utilizar o GPS do transporte para o mapa de previsão');
 }
 const fuelHike={id:'carvao',title:'Pelos trilhos do carvão',
  date:'2026-11-07',town:'Por confirmar',
  start:'Junto à Câmara Municipal,Rua 1º de Maio, Manteigas'};
 const fuelForecast=await controller.forecast(fuelHike);
 assert.equal(fuelForecast.url,value.url,
  'a caminhada do carvão consulta a previsão de Manteigas, não a morada inteira');
 const mislocated={...multi,multiDay:false,endDate:null,
  start:'Praça da Liberdade, Porto',lat:41.1628,lon:-8.5928,verified:true};
 assert.equal(Weather.locationPlan(mislocated).kind,'gps');
 const fixed=await controller.forecast(mislocated);
 assert.equal(fixed.url,value.url,
  'quando o GPS de encontro está longe do destino explícito, prever na zona do trilho');
 assert.equal(fixed.name,'Manteigas');
 // Simular o carregamento real no navegador, sem injectar fetchImpl.
 // A função fetch nativa existe globalmente, não no âmbito lexical de factory().
 const browser={
  window:{},
  fetch:async url=>({ok:true,json:async()=>forecastJson}),
  URLSearchParams
 };
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../assets/js/trilhario-weather.js'),'utf8'),browser);
 const browserEngine=browser.window.TrilharioWeather.create({today:()=> '2026-11-01'});
 const browserForecast=await browserEngine.forecast(precise);
 assert.equal(browserForecast.temp,13,'fetch global do navegador deve alimentar a previsão');
 assert.equal(browserForecast.symbol,'⛅','o cartão deve receber o símbolo do tempo');
 const callsBeforeOutOfRange=calls;
 const other=await controller.forecast({...multi,date:'2026-11-28'});
 assert.equal(other,null,'nunca consultar datas fora dos dois fins de semana');
 assert.equal(calls,callsBeforeOutOfRange,'datas fora dos fins de semana não consultam a API');
 const node={dataset:{weatherId:'m'},isConnected:true,textContent:'',
  title:'',setAttribute(k,v){this[k]=v},removeAttribute(k){delete this[k]}};
 controller.observe([node]);
 for(let i=0;i<30;i++)await Promise.resolve();
 assert.equal(node.textContent,'13°C');
 assert.equal(node['data-weather-icon'],'⛅');
 assert.equal(node.target,'_blank');
 assert.equal(node.rel,'noopener noreferrer');
 assert.equal(node.href,value.url,'clicar na temperatura abre o Windy no dia e zona do trilho');
 assert.match(node.title,/ECMWF IFS via Open-Meteo/);
 const noLocation=await controller.forecast({...multi,title:'Passeio genérico',
  town:'Por confirmar',start:'Terminal Rodoviário do Oriente'});
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
 assert.equal(fromFallback.url,value.url,
  'o link Windy usa dia e local mesmo quando o Open-Meteo recorre ao modelo alternativo');
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
