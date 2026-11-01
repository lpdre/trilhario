'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {handler}=require('../netlify/functions/portagens.js');
(async()=>{
 const origin='https://lpdre.github.io';
 const options=await handler({httpMethod:'OPTIONS',headers:{origin}});
 assert.equal(options.statusCode,204);
 assert.equal(options.headers['Access-Control-Allow-Origin'],origin);
 assert.match(options.headers['Access-Control-Allow-Headers'],/Content-Type/);
 const health=await handler({httpMethod:'GET',headers:{origin}});
 assert.equal(health.statusCode,200);
 assert.equal(health.headers['Access-Control-Allow-Origin'],origin);
 assert.equal(JSON.parse(health.body).status,'ready');
 const invalid=await handler({httpMethod:'POST',headers:{origin},body:'{}'});
 assert.equal(invalid.statusCode,400);
 assert.equal(invalid.headers['Access-Control-Allow-Origin'],origin);
 const blocked=await handler({httpMethod:'OPTIONS',headers:{origin:'https://untrusted.example'}});
 assert.equal(blocked.statusCode,403);
 assert.equal(blocked.headers['Access-Control-Allow-Origin'],undefined);
 const site=fs.readFileSync(path.join(__dirname,'..','assets/js/trilhario.js'),'utf8');
 assert.ok(site.includes('fetchTimedJson(tollApiEndpoint,'));
 assert.ok(site.includes('loadTollApiEndpoint()'));
 assert.ok(site.includes('if(!tollApiEndpoint||!r||'));
 const cfg=JSON.parse(fs.readFileSync(path.join(__dirname,'..','portagens-config.json'),'utf8'));
 assert.equal(typeof cfg.endpoint,'string');

 // A fila de portagens confirma os dois sentidos, sem repetir a rota.
 const section=(a,b)=>{
  const i=site.indexOf(a),j=site.indexOf(b,i);
  assert.ok(i>=0&&j>i,'secção ausente: '+a);
  return site.slice(i,j);
 };
 assert.ok(site.includes('TOLL_UNKNOWN_MS=15*60*1000'),'resposta desconhecida não bloqueia 12 horas');
 const migration=section('const tollStartupNow=Date.now();','let travelBusy=');
 const oldWait=Date.now()+8*60*60*1000,shortWait=Date.now()+10*60*1000;
 const stale={tollStatus:'unknown',tollNextRetry:oldWait,tollRequestId:42};
 const recent={tollStatus:'unknown',tollNextRetry:shortWait};
 vm.runInNewContext(migration,{travelRoutes:{stale,recent}});
 assert.equal(stale.tollRequestId,undefined,'pedidos de outra sessão não ficam bloqueados');
 assert.ok(stale.tollNextRetry<=Date.now(),'desbloquear esperas de 12 horas antigas');
 assert.equal(recent.tollNextRetry,shortWait,'preservar espera curta legítima');

 const queueSource=section('function runTollQueue(){','// Assinatura reduzida da geometria');
 const once=async(getResponse)=>{
  const row={tollRequestId:9};
  const ctx={
   tollWorking:false,tollActiveKey:'',
   tollJobs:[{key:'aveiro|evento',id:'evento',requestId:9,
              outGeometry:[[0,0],[1,1]],backGeometry:[[1,1],[0,0]]}],
   travelRoutes:{'aveiro|evento':row},TOLL_RETRY_MS:180000,TOLL_UNKNOWN_MS:900000,
   autoTollsForGeometry:getResponse,renderTravelProgress:()=>{},
   refreshTravelCard:()=>{},persistTravel:()=>{},
   console:{info:()=>{}}
  };
  vm.runInNewContext(queueSource,ctx);
  ctx.runTollQueue();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ctx.tollWorking,false);
  assert.equal(ctx.tollActiveKey,'');
  assert.equal(ctx.tollJobs.length,0);
  assert.equal(row.tollRequestId,undefined,'um pedido não pode ficar permanentemente ocupado');
  return row;
 };
 const success=await once(async()=>({status:'ok',amount:2.75}));
 assert.equal(success.tollReturn,5.5);
 assert.equal(success.tollSource,'IP');
 assert.equal(success.tollStatus,undefined);
 const unknown=await once(async()=>({status:'unknown'}));
 assert.equal(unknown.tollStatus,'unknown');
 assert.ok(unknown.tollNextRetry-Date.now()<=900000);
 assert.ok(unknown.tollNextRetry>Date.now()+850000);
 const failed=await once(async()=>{throw new Error('interrupção simulada')});
 assert.equal(failed.tollStatus,'retry');
 assert.ok(failed.tollNextRetry-Date.now()<=180000);
 // Se o traçado ainda estiver guardado, pedir só tarifas: nem um job rodoviário.
 const tripSource=section('function queueTrips(events,manual=false){','// v38 — actualização incremental:');
 let scheduled=0;
 const autoCtx={
  travelPrefs:{origin:'Aveiro'},tripOriginProblem:'',
  routeCacheKey:()=> 'aveiro|evento',travelData:()=>({}),
  routeFresh:()=>true,tollsDue:()=>true,
  getRouteGeometry:()=>({out:[[0,0],[1,1]],back:[[1,1],[0,0]]}),
  scheduleCachedTolls:()=>{scheduled++},
  refreshTravelCard:()=>{},tripNeedsRoute:()=>false,
  departureCandidates:()=>['Lisboa'],tripActiveKey:'',
  tripJobsSet:new Set(),tripJobs:[],requestAnimationFrame:()=>{}
 };
 vm.runInNewContext(tripSource,autoCtx);
 autoCtx.queueTrips([{id:'evento'}],false);
 assert.equal(scheduled,1);
 assert.equal(autoCtx.tripJobs.length,0,'traçado em cache evita recalcular distância');

 console.log('OK: Netlify POST/OPTIONS CORS, URL configurável e GitHub Pages sem pedidos inválidos');
})().catch(e=>{console.error(e);process.exitCode=1;});
