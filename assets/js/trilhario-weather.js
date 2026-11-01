/* Trilhário — previsão meteorológica nos dois próximos fins de semana.
 * ECMWF IFS via Open-Meteo, sem API Windy (a API de produção exige licença).
 * Apenas símbolos e temperatura ao meio-dia; a previsão é aproximada.
 */
(function(root, factory){
 'use strict';
 const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 if(root)root.TrilharioWeather=api;
})(typeof window==='object'?window:null,function(){
 'use strict';
 const FORECAST_API='https://api.open-meteo.com/v1/ecmwf';
 const GEO_API='https://geocoding-api.open-meteo.com/v1/search';
 const CACHE_MS=3*60*60*1000, FAILURE_MS=10*60*1000;
 const PLACEHOLDERS=new Set(['','por confirmar','a confirmar','desconhecido','por definir','local a definir']);
 const validDate=s=>typeof s==='string'&&/^\d{4}-\d\d-\d\d$/.test(s);
 const folded=s=>String(s??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
 const usable=s=>{const v=String(s||'').trim();return v.length>=3&&!PLACEHOLDERS.has(folded(v));};
 function weekendDates(today){
  if(!validDate(today))return new Set();
  const saturday=new Date(today+'T12:00:00Z');
  if(!Number.isFinite(saturday.getTime()))return new Set();
  const weekday=(saturday.getUTCDay()+6)%7;
  saturday.setUTCDate(saturday.getUTCDate()+5-weekday);
  if(saturday.toISOString().slice(0,10)<today)saturday.setUTCDate(saturday.getUTCDate()+7);
  const dates=new Set();
  for(const offset of [0,1,7,8]){
   const day=new Date(saturday);
   day.setUTCDate(day.getUTCDate()+offset);
   dates.add(day.toISOString().slice(0,10));
  }
  return dates;
 }
 function condition(code){
  const n=Number(code);
  if(!Number.isInteger(n))return null;
  if(n===0)return {symbol:'☀️',label:'Céu limpo'};
  if(n===1)return {symbol:'🌤️',label:'Pouco nublado'};
  if(n===2)return {symbol:'⛅',label:'Parcialmente nublado'};
  if(n===3)return {symbol:'☁️',label:'Nublado'};
  if(n===45||n===48)return {symbol:'🌫️',label:'Nevoeiro'};
  if([51,53,55,56,57,80].includes(n))return {symbol:'🌦️',label:'Aguaceiros ou chuviscos'};
  if([61,63,65,66,67,81,82].includes(n))return {symbol:'🌧️',label:'Chuva'};
  if([71,73,75,77,85,86].includes(n))return {symbol:'🌨️',label:'Neve'};
  if([95,96,99].includes(n))return {symbol:'⛈️',label:'Trovoada'};
  return null;
 }
 function noonForecast(data,day){
  const hourly=data?.hourly;
  if(!Array.isArray(hourly?.time)||!Array.isArray(hourly.temperature_2m)||
     !Array.isArray(hourly.weather_code))return null;
  const index=hourly.time.indexOf(day+'T12:00');
  if(index<0)return null; // Não misturar dias nem inventar previsões.
  const temp=hourly.temperature_2m[index],wx=condition(hourly.weather_code[index]);
  if(typeof temp!=='number'||!Number.isFinite(temp)||temp< -60||temp>55||!wx)return null;
  return {symbol:wx.symbol,label:wx.label,temp:Math.round(temp)};
 }
 function locationPlan(event){
  if(!event||!validDate(event.date))return null;
  const multi=event.multiDay===true||validDate(event.endDate)&&event.endDate>event.date;
  const town=usable(event.town)?String(event.town).trim():'';
  const start=usable(event.start)?String(event.start).trim():'';
  const title=folded(event.title);
  if(multi){
   // Nunca usar GPS de recolha de passageiros (Porto/Lisboa) como clima da serra.
   if(!town)return null;
   // Se a 'localidade' é o mesmo ponto de recolha mas não figura no título,
   // não há prova de que seja o destino do trilho.
   const names=folded(town).split(/[,\u2013\u2014]/).map(s=>s.trim()).filter(s=>s.length>=4);
   if(start&&names.some(part=>folded(start).includes(part))&&!names.some(part=>title.includes(part)))
    return null;
   return {kind:'place',name:town};
  }
  // Se a morada é uma recolha rodoviária, as coordenadas descrevem o
  // transporte e não necessariamente a zona onde se caminha.
  if(/terminal rodovi[aá]rio|terminal fluvial|esta[cç][aã]o do oriente|ponto de recolha|autocarro/i.test(start)){
   if(town&&(!folded(start).includes(folded(town))||title.includes(folded(town))))
    return {kind:'place',name:town};
   return null;
  }
  const lat=Number(event.lat),lon=Number(event.lon);
  if(event.verified===true&&event.lat!=null&&event.lon!=null&&
     Number.isFinite(lat)&&Number.isFinite(lon)&&
     lat>=36&&lat<=43&&lon>=-10&&lon<=-6)
    return {kind:'gps',lat,lon,name:town||start||'zona do trilho'};
  if(town)return {kind:'place',name:town};
  // Na ausência de GPS, só usar nomes geográficos, não ruas ou pontos de encontro.
  if(start&&!/^(?:rua|r\.|av\.|avenida|parque|estacionamento|terminal|junto|em frente)/i.test(start)
      &&start.length<=65)return {kind:'place',name:start};
  return null;
 }
 function placeOptions(name){
  const value=String(name).trim().replace(/\s+/g,' ');
  const segments=value.split(/\s*[,–—]\s*/).map(x=>x.trim()).filter(x=>x.length>=3);
  // Procurar primeiro a localidade/município, não a rua ou referência logística.
  const choices=[...segments.slice().reverse(),value];
  return [...new Set(choices)].filter(x=>x.length>=3&&x.length<=80).slice(0,3);
 }
 function create(options={}){
  const fetchImpl=options.fetchImpl||(typeof fetch==='function'?fetch.bind(root):null);
  const getToday=options.today||(()=>new Date().toLocaleDateString('sv-SE',{timeZone:'Europe/Lisbon'}));
  const getEvent=options.getEvent||(()=>null);
  const weatherCache=new Map(),geoCache=new Map();
  const active=new Set(),queue=[],results=new Map();
  let observer=null,working=0;
  async function fetchJson(url){
   if(!fetchImpl)return null;
   const controller=typeof AbortController==='function'?new AbortController():null;
   const timer=controller?setTimeout(()=>controller.abort(),11000):null;
   try{
    const response=await fetchImpl(url,controller?{signal:controller.signal}:{});
    if(!response.ok)return null;
    return await response.json();
   }catch{return null;}
   finally{if(timer!=null)clearTimeout(timer);}
  }
  function cached(cache,key,task){
   const hit=cache.get(key);
   if(hit&&hit.exp>Date.now())return hit.promise;
   const promise=Promise.resolve().then(task).catch(()=>null);
   const entry={promise,exp:Date.now()+CACHE_MS};
   cache.set(key,entry);
   promise.then(v=>{entry.exp=Date.now()+(v?CACHE_MS:FAILURE_MS);});
   return promise;
  }
  async function resolvePlace(name){
   const key=folded(name);
   return cached(geoCache,key,async()=>{
    for(const candidate of placeOptions(name)){
     const q=new URLSearchParams({name:candidate,count:'5',countryCode:'PT',language:'pt',format:'json'});
     const response=await fetchJson(GEO_API+'?'+q);
     const items=response?.results;
     const found=Array.isArray(items)?items.find(x=>
      x.country_code==='PT'&&Number.isFinite(x.latitude)&&Number.isFinite(x.longitude)&&
      x.latitude>=36&&x.latitude<=43&&x.longitude>=-10&&x.longitude<=-6):null;
     if(found)return {lat:found.latitude,lon:found.longitude,name:found.name||candidate};
    }
    return null;
   });
  }
  async function getHours(lat,lon){
   const key=lat.toFixed(2)+','+lon.toFixed(2);
   return cached(weatherCache,key,async()=>{
    const args=new URLSearchParams({
     latitude:lat.toFixed(4),longitude:lon.toFixed(4),
     hourly:'temperature_2m,weather_code',timezone:'Europe/Lisbon',forecast_days:'15'
    });
    const response=await fetchJson(FORECAST_API+'?'+args);
    return Array.isArray(response?.hourly?.time)?response:null;
   });
  }
  async function forecast(event){
   if(!weekendDates(getToday()).has(event?.date))return null;
   const plan=locationPlan(event);
   if(!plan)return null;
   const point=plan.kind==='gps'?plan:await resolvePlace(plan.name);
   if(!point)return null;
   const data=await getHours(point.lat,point.lon);
   const value=noonForecast(data,event.date);
   return value?{...value,name:point.name||plan.name}:null;
  }
  function display(node,event,result){
   if(!node||!node.isConnected||node.dataset.weatherId!==String(event.id))return;
   if(!result){node.textContent='';node.removeAttribute('title');node.removeAttribute('aria-label');return;}
   node.textContent=result.symbol+' '+result.temp+'°C';
   const location=result.name||'zona da caminhada';
   const description=result.label+', '+result.temp+'°C, às 12h de '+event.date+
    ', em '+location+'. Previsão ECMWF via Open-Meteo (aproximada).';
   node.title=description;
   node.setAttribute('aria-label',description);
  }
  function eventKey(e){
   return [e.id,e.date,e.town||'',e.start||'',e.lat??'',e.lon??''].join('|');
  }
  function paintAll(event,value){
   const slots=typeof document==='object'?document.querySelectorAll('[data-weather-id]'):[];
   for(const node of slots)if(node.dataset.weatherId===String(event.id))display(node,event,value);
  }
  function pump(){
   while(working<3&&queue.length){
    const node=queue.shift();
    if(!node?.isConnected)continue;
    const event=getEvent(node.dataset.weatherId);
    if(!event||!weekendDates(getToday()).has(event.date))continue;
    const key=eventKey(event);
    const previous=results.get(key);
    if(previous&&previous.exp>Date.now()){
     display(node,event,previous.value);
     continue;
    }
    if(active.has(key))continue;
    active.add(key);working++;
    forecast(event).then(value=>{
     results.set(key,{value,exp:Date.now()+(value?CACHE_MS:FAILURE_MS)});
     paintAll(event,value);
     display(node,event,value);
    }).catch(()=>display(node,event,null)).finally(()=>{
     active.delete(key);working--;pump();
    });
   }
  }
  function observe(elements){
   if(observer)observer.disconnect();
   const slots=Array.from(elements||[]).filter(node=>{
    const event=getEvent(node.dataset.weatherId);
    if(!event)return false;
    const cached=results.get(eventKey(event));
    if(cached&&cached.exp>Date.now()){
     display(node,event,cached.value);
     return false;
    }
    return true;
   });
   if(typeof IntersectionObserver!=='function'){
    queue.push(...slots.slice(0,8));pump();return;
   }
   const current=new IntersectionObserver(entries=>{
    for(const entry of entries){
     if(!entry.isIntersecting)continue;
     current.unobserve(entry.target);
     queue.push(entry.target);
    }
    pump();
   },{rootMargin:'500px 0px',threshold:0});
   observer=current;
   slots.forEach(node=>current.observe(node));
  }
  return {forecast,observe};
 }
 return {weekendDates,condition,noonForecast,locationPlan,placeOptions,create};
});
