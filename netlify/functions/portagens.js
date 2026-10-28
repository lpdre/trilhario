// Trilhário v21 — integração experimental com o calculador de portagens
// da Infraestruturas de Portugal. Calcula apenas Classe 1 / só ida.
// Não inventa valores: se a IP não responder, devolve erro controlado.
'use strict';
const SOURCE='https://portagens.infraestruturasdeportugal.pt/Portagens.asmx/ObterCustoPortagens';
const ORIGIN='https://portagens.infraestruturasdeportugal.pt/';
const PUBLIC_ORIGINS=new Set(['https://lpdre.github.io']);
function corsHeaders(event){
 const origin=String(event.headers?.origin||event.headers?.Origin||'');
 return PUBLIC_ORIGINS.has(origin)?{'Access-Control-Allow-Origin':origin,'Vary':'Origin'}:{};
}
const json=(status,obj,event)=>({statusCode:status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff',...corsHeaders(event)},body:JSON.stringify(obj)});
function validPair(point){return Array.isArray(point)&&point.length===2&&typeof point[0]==='number'&&typeof point[1]==='number'&&Number.isFinite(point[0])&&Number.isFinite(point[1])&&point[0]>=-11&&point[0]<=-5&&point[1]>=35&&point[1]<=44;}
function sampleRoute(route,max=1800){if(route.length<=max)return route;const step=(route.length-1)/(max-1);return Array.from({length:max},(_,i)=>route[Math.round(i*step)]);}
function decode(input){let j=input; if(typeof j==='string'){try{j=JSON.parse(j)}catch{return null}};const arr=Array.isArray(j?.d)?j.d:(Array.isArray(j)?j:null);if(!arr||arr.length<1)return null;const values=arr.map(x=>typeof x==='string'&&x.trim()?Number(x.replace(',','.')):(typeof x==='number'?x:NaN));return values.every(n=>Number.isFinite(n)&&n>=0&&n<1500)?values:null;}
exports.handler=async function handler(event){
 const origin=String(event.headers?.origin||event.headers?.Origin||'');
 if(event.httpMethod==='OPTIONS'){
  if(origin&&!PUBLIC_ORIGINS.has(origin))return json(403,{error:'Origem não autorizada'},event);
  return {statusCode:204,headers:{...corsHeaders(event),'Access-Control-Allow-Methods':'POST, GET, OPTIONS','Access-Control-Allow-Headers':'Content-Type','Cache-Control':'no-store'},body:''};
 }
 if(event.httpMethod==='GET')return json(200,{status:'ready',service:'portagens',source:'IP'},event);
 if(event.httpMethod!=='POST')return json(405,{error:'Método não permitido'},event);
 if((event.body||'').length>1900000)return json(413,{error:'Trajecto demasiado extenso'},event);
 let coords;
 try{coords=JSON.parse(event.body||'{}').coordinates}catch{return json(400,{error:'Pedido inválido'},event)}
 if(!Array.isArray(coords)||coords.length<2||coords.length>30000||!coords.every(validPair))return json(400,{error:'Coordenadas inválidas'},event);
 coords=sampleRoute(coords);
 // O projecto MobilityDataPT documenta o endpoint IP e o seu esquema.
 // A IP pode mudar a interface; tratar sempre falha como desconhecido.
 let lastErr='Sem resposta válida da IP';
 for(const asString of [false,true]){
  const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),7000);
  try{
   const res=await fetch(SOURCE,{method:'POST',headers:{'Content-Type':'application/json; charset=utf-8','Accept':'application/json','Referer':ORIGIN},body:JSON.stringify({coordenadas:asString?JSON.stringify(coords):coords}),signal:controller.signal});
   if(!res.ok){lastErr='IP HTTP '+res.status;continue}
   const vals=decode(await res.json());
   if(vals)return json(200,{source:'IP',class:1,oneWay:Math.round(vals[0]*100)/100,classes:vals.length,computedAt:new Date().toISOString()},event);
   lastErr='Resposta da IP sem tarifas reconhecíveis';
  }catch(e){lastErr=e.message||'IP indisponível'}finally{clearTimeout(timeout)}
 }
 console.error('Portagens indisponíveis:',lastErr);
 return json(503,{error:'Serviço de portagens indisponível; tentar novamente mais tarde.'},event);
};
