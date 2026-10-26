
'use strict';
const {timeValid,encodeRouteGeometry,decodeRouteGeometry,compactRouteGeometry,routeShapeFingerprint}=window.TrilharioRoutes;
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const fmtN=n=>n===null||n===undefined||n===''?'—':Number(n).toLocaleString('pt-PT',{maximumFractionDigits:1});
const fmtP=n=>n==null?'—':n===0?'Grátis':fmtN(n)+' €';
const names=['','Fácil','Moderada','Exigente','Difícil','Muito difícil'];
// v47A — leitura tolerante: validar dados antigos sem reescrever nem apagar o original.
// Eventos pessoais e preferências são duradouros; rotas, GPS e preços são caches.
const isStoredRecord=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const numericBetween=(v,min,max)=>v!==null&&v!==''&&Number.isFinite(Number(v))&&Number(v)>=min&&Number(v)<=max;
const storedDate=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&
 !Number.isNaN(Date.parse(v+'T12:00:00Z'))&&new Date(v+'T12:00:00Z').toISOString().slice(0,10)===v;
function sanitizeStored(key,value,fallback){
 if(key==='trilhario_custom_v1'){
  if(!Array.isArray(value))return [];
  // Não eliminar nem reparar registos no armazenamento: usar uma cópia válida em memória.
  return value.filter(e=>isStoredRecord(e)&&typeof e.id==='string'&&e.id.length>0&&e.id.length<=240&&
    typeof e.title==='string'&&e.title.trim().length>0&&typeof e.organizer==='string'&&
    e.organizer.trim().length>0&&storedDate(e.date)).map(e=>({...e,userAdded:true}));
 }
 if(key==='trilhario_travel_prefs_v19'){
  if(!isStoredRecord(value))return {...fallback};
  const p={...fallback};
  if(typeof value.origin==='string')p.origin=value.origin.slice(0,200);
  if(numericBetween(value.consumption,0.1,35))p.consumption=Number(value.consumption);
  if(value.kind==='gasoleo'||value.kind==='gasolina')p.kind=value.kind;
  if(numericBetween(value.fuel,0.3,5))p.fuel=Number(value.fuel);
  if(value.fuelOverride===null)p.fuelOverride=null;
  else if(numericBetween(value.fuelOverride,0.3,5))p.fuelOverride=Number(value.fuelOverride);
  return p;
 }
 if(key==='trilhario_dgeg_medianas_v20'){
  if(!isStoredRecord(value))return {};
  const good={};
  for(const kind of ['gasoleo','gasolina']){
   const row=value[kind];
   if(isStoredRecord(row)&&numericBetween(row.value,0.3,5)&&storedDate(row.date)){
    good[kind]={value:Number(row.value),date:row.date,source:typeof row.source==='string'?row.source.slice(0,80):'DGEG'};
   }
  }
  return good;
 }
 if(key==='trilhario_routes_v19'||key==='trilhario_geocode_v19'||key==='trilhario_toll_geometry_v43'){
  if(!isStoredRecord(value))return {};
  const max=key==='trilhario_routes_v19'?1500:key==='trilhario_geocode_v19'?650:40;
  let entries=Object.entries(value).filter(([k,row])=>k.length>0&&k.length<=350&&
   k!=='__proto__'&&isStoredRecord(row));
  if(entries.length>max){
   // Só para caches: manter os registos mais recentes.
   entries.sort((a,b)=>(Number(b[1].updated||b[1].checkedAt||b[1].accessed)||0)-
     (Number(a[1].updated||a[1].checkedAt||a[1].accessed)||0));
   entries=entries.slice(0,max);
  }
  return Object.fromEntries(entries);
 }
 if(key==='trilhario_intro_v33_closed')return typeof value==='boolean'?value:fallback;
 if(typeof value!==typeof fallback||Array.isArray(value)!==Array.isArray(fallback))return fallback;
 return value;
}
function storage(key,fallback){
 try{
  const raw=localStorage.getItem(key);
  if(raw===null||raw.length>4500000)return fallback;
  return sanitizeStored(key,JSON.parse(raw),fallback);
 }catch{return fallback;}
}
// Uma falha de escrita nunca pode ser confundida com uma operação guardada.
// Os caches falham silenciosamente; nas acções do utilizador há sempre um aviso.
function persistValue(key,value,quiet=false){
 try{localStorage.setItem(key,JSON.stringify(value));return true;}
 catch{
  if(!quiet&&$('toast'))toast('Não foi possível guardar neste navegador. A alteração não ficou gravada.');
  return false;
 }
}
let custom=storage('trilhario_custom_v1',[]);
const KM_CAP=50, GAIN_CAP=2500;
let state={day:'all',weekend:'all',organizer:'all',kmMin:0,kmMax:KM_CAP,gainMin:0,gainMax:GAIN_CAP,view:'list',month:9,year:2026};
let remoteEvents=null;
let remoteUpdatedAt=null;
let remoteSourcesHealth=null,remoteFeedState='loading';

// v20 — médias diárias da DGEG. Guarda a data do preço; não confunde dados antigos com preço de hoje.
const TRAVEL_PREF_KEY='trilhario_travel_prefs_v19',TRAVEL_ROUTES_KEY='trilhario_routes_v19',TRAVEL_GEO_KEY='trilhario_geocode_v19';
const FUEL_CACHE_KEY='trilhario_dgeg_medianas_v20';
const TRAVEL_TOLL_GEOMETRY_KEY='trilhario_toll_geometry_v43';
// Valores publicados na página da DGEG para 11-10-2026: recurso inicial, datado, não preço de hoje.
const FUEL_OFFICIAL_REFERENCE={gasoleo:{value:2.145,date:'2026-10-11',source:'DGEG'},gasolina:{value:2.072,date:'2026-10-11',source:'DGEG'}};
const FUEL_IDS={gasoleo:2101,gasolina:3201};
let fuelPrices={...FUEL_OFFICIAL_REFERENCE,...storage(FUEL_CACHE_KEY,{})};
const _oldTravelPrefs=storage(TRAVEL_PREF_KEY,{origin:'',consumption:5.5,fuel:1.70});
let travelPrefs={..._oldTravelPrefs,kind:_oldTravelPrefs.kind==='gasolina'?'gasolina':'gasoleo',fuelOverride:
   _oldTravelPrefs.fuelOverride!=null?_oldTravelPrefs.fuelOverride:
   (_oldTravelPrefs.kind==null&&_oldTravelPrefs.origin&&Number.isFinite(Number(_oldTravelPrefs.fuel))?Number(_oldTravelPrefs.fuel):null)};
if(travelPrefs.fuelOverride==null)travelPrefs.fuel=(fuelPrices[travelPrefs.kind]||FUEL_OFFICIAL_REFERENCE.gasoleo).value;
let travelRoutes=storage(TRAVEL_ROUTES_KEY,{}),travelGeocodes=storage(TRAVEL_GEO_KEY,{});
// Geometria compactada e limitada: só serve para repetir consultas à IP sem recalcular rotas.
let travelTollGeometry=storage(TRAVEL_TOLL_GEOMETRY_KEY,{});
if(!travelTollGeometry||typeof travelTollGeometry!=='object'||Array.isArray(travelTollGeometry))travelTollGeometry={};
// Uma consulta em voo terminou ao fechar a página; nunca bloquear a próxima sessão.
for(const route of Object.values(travelRoutes))if(route&&typeof route==='object')delete route.tollRequestId;
let travelBusy=false,geoLastRequest=0,roadLastRequest=0;
// v23: partida GPS validada, geocodificação progressiva e lotes de 10.
const TRAVEL_BATCH_SIZE=10;
let tripJobs=[],tripJobsSet=new Set(),tripActiveKey='',tripProblems=new Map(),tripOriginProblem='';
let tripFilterSignature='',tripBatchObserver=null,tripWorking=false;
let tollJobs=[],tollWorking=false;
const ROUNDTRIP_VERSION=37; // v37: ida e volta com percursos independentes; cache antiga não é fiável.
const GEOCODER_VERSION=36,geoMisses=new Map(),tripRetryAfter=new Map(); // v35: invalidar rotas geocodificadas sem validação geográfica


// Fontes monitorizadas; a presença aqui não significa vagas ou eventos confirmados.
// Trilhário v16 — Trekking4Life e NDesafios no directório; Hike Land já existia.
const ORGANIZER_DIRECTORY = [{"name": "Hiking Around Adventures","url": "https://www.hikingaround.pt/aventurasnacionais"},{"name": "Mais Trilhos","url": "https://maistrilhos.pt/caminhadas"},{"name": "Indoeu","url": "https://indoeu.pt/caminhadas/"},{"name": "GreenTrekker","url": "https://www.greentrekker.pt/agenda/"},{"name": "Trekking Roots","url": "https://trekkingroots.pt/calendario-caminhadas/"},{"name": "Hike Land","url": "https://www.hikeland.pt/atividades-1-dia/"},{"name": "Montanhas Dentro","url": "https://montanhasdentro.pt/"},{"name": "Trekkin","url": "https://www.trekkin.pt/eventos/"},{"name": "Basto Trekking","url": "https://bastotrekking.pt/"},{"name": "Montanhas do Norte","url": "https://montanhasdonorte.pt/percursos-1-dia/"},{"name": "RB Hiking & Trekking","url": "https://barbosa-trekking.pt/"},{"name": "Caminhadas Smile","url": "https://www.caminhadassmile.pt/"},{"name": "DRenergies","url": "https://www.drenergies.com/calendario-inscricoes-caminhadas"},{"name": "Clube de Montanhismo da Guarda","url": "https://www.montanhismo-guarda.pt/portal/eventos/lista/"},{"name": "Amigos da Montanha","url": "https://amigosdamontanha.com/"},{"name": "Caminhando.pt","url": "https://caminhando.pt/agenda-eventos/caminhadas/"},{"name": "Pé no Mundo","url": "https://penomundo.pt/"},{"name": "CAAL — Clube de Actividades de Ar Livre","url": "https://clubearlivre.org/"},{"name": "Trilhos Nocturnos","url": "https://trilhosnocturnos.com/eventos-agenda/"},{"name": "SAL — Sistemas de Ar Livre","url": "https://www.sal.pt/"},{"name": "Associação Geopark Estrela","url": "https://geoparkestrela.pt/atividades"},{"name": "Gerês Viver Turismo","url": "https://geres.pt/programa-anual-de-caminhadas-2026/"},{"name": "Borealis on Trekking","url": "https://borealis.travel/calendario-de-viagens/"},{"name": "Trekking4Life","url": "https://trekking4life.wixsite.com/website-1"},{"name": "NDesafios — Natureza e Desafios","url": "https://ndesafios.pt/"}];
const AGGREGATOR_DIRECTORY = [{"name": "Programa Municipal de Caminhadas de Lousada", "url": "https://app.cm-lousada.pt/servicos/cultura-desporto-e-lazer/desporto/atividades/galeria-39"}];

const ORGANIZERS_PAGE_MODE=new URLSearchParams(location.search).has('organizadores');
if(ORGANIZERS_PAGE_MODE){document.body.classList.add('organizers-mode');document.title='Organizadores — Trilhário';}
function renderOrganizersPage(){
 if(!ORGANIZERS_PAGE_MODE)return;
 const count=new Map();
 const clock=agendaClock();
 const es=allEvents();
 es.forEach(e=>{if(eventHasNotStarted(e,clock)&&e.organizer)count.set(fold(e.organizer),(count.get(fold(e.organizer))||0)+1)});
 const byName=new Map();
 ORGANIZER_DIRECTORY.forEach(e=>byName.set(fold(e.name),e));
 es.forEach(e=>{
  const key=fold(e.organizer||'');
  if(key&&!byName.has(key)){
   let home='';try{if(safeExternalUrl(e.url))home=new URL(e.url).origin+'/'}catch{}
   byName.set(key,{name:e.organizer,url:home});
  }
 });
 const entries=[...byName.values()].sort((a,b)=>a.name.localeCompare(b.name,'pt'));
 const term=fold($('orgPageSearch').value.trim());
 const visible=entries.filter(e=>fold(e.name).includes(term));
 $('orgVisibleCount').textContent=visible.length+' de '+entries.length;
 $('orgPageStats').textContent=entries.length+' organizadores acompanhados · '+[...count.keys()].length+' com caminhadas na agenda';
 const card=e=>{
  const n=count.get(fold(e.name))||0;
  const configured=remoteSourcesHealth&&Object.prototype.hasOwnProperty.call(remoteSourcesHealth,e.name);
  const collectionLabel=remoteSourcesHealth?(configured?'Recolha automática configurada':'Apenas no directório'):'Recolha por confirmar';
  const description=(n?n+' caminhada'+(n===1?'':'s')+' na agenda':'Organizador acompanhado')+' · '+collectionLabel;
  const valid=safeExternalUrl(e.url);
  return '<article class="org-card"><div class="org-card-copy"><h3>'+(valid?'<a href="'+esc(e.url)+'" target="_blank" rel="noopener noreferrer">'+esc(e.name)+'</a>':esc(e.name))+'</h3><small>'+description+'</small></div>'+(valid?'<a class="org-card-open" href="'+esc(e.url)+'" target="_blank" rel="noopener noreferrer" title="Abrir site de '+esc(e.name)+'" aria-label="Abrir site de '+esc(e.name)+'">↗</a>':'')+'</article>';
 };
 $('organizerCards').innerHTML=visible.length?visible.map(card).join(''):'<div class="org-empty">Nenhum organizador encontrado.</div>';
 $('aggregatorCards').innerHTML=AGGREGATOR_DIRECTORY.map(e=>'<article class="org-card"><div class="org-card-copy"><h3><a href="'+esc(e.url)+'" target="_blank" rel="noopener noreferrer">'+esc(e.name)+'</a></h3><small>Fonte complementar</small></div><a class="org-card-open" href="'+esc(e.url)+'" target="_blank" rel="noopener noreferrer" aria-label="Abrir '+esc(e.name)+'">↗</a></article>').join('');
}

function renderSourcesDirectory(){
 const link=e=>'<a href="'+esc(e.url)+'" target="_blank" rel="noopener noreferrer">'+esc(e.name)+' ↗</a>';
 $('sourcesDirectory').innerHTML=ORGANIZER_DIRECTORY.slice().sort((a,b)=>a.name.localeCompare(b.name,'pt')).map(link).join('')+
  '<h4>Programas municipais</h4>'+AGGREGATOR_DIRECTORY.map(link).join('');
}

// v45 — A agenda online provém exclusivamente do eventos.json validado.
// Excepções e correcções verificadas pertencem ao pipeline Python.

// As coordenadas ficam exclusivamente para o mapa, nunca no texto do local de partida.
// Algumas fontes misturam a morada com "Coordenadas GPS Lat..."; mantemos apenas o local.
// Tratar "Por confirmar" como vazio, sem descartar um local publicado noutro campo.
function isPlacePlaceholder(raw){
 const v=fold(String(raw||'').trim());
 return !v || /^(?:por confirmar|a confirmar|desconhecido|local a definir|por definir|nao definido|a definir)$/.test(v);
}
// Há títulos incorrectamente recolhidos como "moderado 25/10/2026 ... NOVIDADE".
// Recuperar apenas nesses casos o nome público já contido no URL do próprio evento.
function legibleEventTitle(e){
 const title=String(e.title||'').trim();
 if(e.organizer!=='Hike Land'||!/^(?:facil|fácil|moderado|moderada|desafiante|dificil|difícil|exigente)\s+\d{1,2}\/\d{1,2}\/20\d{2}\b/i.test(title))return title;
 try{
  const slug=decodeURIComponent(new URL(e.url).pathname.split('/').filter(Boolean).pop()||'').replace(/-\d+$/,'');
  if(slug.length<13||!slug.includes('-'))return title;
  const joinWords=new Set(['de','da','do','das','dos','e','em','na','no','nas','nos','a','o','as','os','entre','por','pelo','pelos']);
  return slug.split('-').map((part,i)=>i&&!(!joinWords.has(part))?part:part.charAt(0).toLocaleUpperCase('pt-PT')+part.slice(1)).join(' ');
 }catch{return title;}
}
function displayDeparture(e){
 const start=localPartidaLegivel(e.start),town=localPartidaLegivel(e.town);
 if(/ponto de encontro\s*2/i.test(start)&&/barco|transtejo/i.test(start))return 'Estação Fluvial de Belém (barco) · segundo ponto de encontro no anúncio';
 // O colector da Hike Land preenche por vezes apenas town com o ponto de encontro.
 if(!isPlacePlaceholder(start))return start;
 return !isPlacePlaceholder(town)?town:'Por confirmar';
}
function localPartidaLegivel(valor){
 let texto=String(valor??'').replace(/\s+/g,' ').trim();
 if(!texto)return '';
 texto=texto.replace(/^Hor[aá]rio\s+IN[IÍ]CIO\s*:?\s*\d{1,2}:\d{2}\s*H?\s+FINAL\s*:?\s*\d{1,2}:\d{2}\s*H?\s*/i,'')
            .replace(/^Ponto\s+de\s+encontro\s*[:\-–—]\s*/i,'')
            .replace(/\s+\d{1,2}[:hH][0-5]\d\s*[–—-]\s*(?:In[ií]cio|Fim|Hora)\b.*$/i,'')
            .replace(/\s+pelas\s+\d{1,2}\s*[hH:]\s*[0-5]\d\b.*$/i,'');
 texto=texto.split(/\b(?:Coordenadas(?:\s+GPS)?|GPS|Latitude|Longitude|Lat|Long|Hora\s+de\s+Fim|A\s+hora\s+de\s+fim|Hora\s+de\s+Início)\b\s*:?(?=\s|$|[-+0-9])/i)[0];
 // O agregador inclui ligações como texto dentro da localidade.
 texto=texto.replace(/\s*\(\s*Ver\s+no\s+Google\s+Maps\s*\)/gi,'')
            .replace(/\s*\bVer\s+no\s+Google\s+Maps\b.*$/gi,'');
 // Também retirar pares de coordenadas escritos sem rótulo.
 texto=texto.replace(/\s*[,;([]?\s*-?\d{1,2}[.,]\d{4,}\s*[,; /]+\s*-?\d{1,3}[.,]\d{4,}.*$/,'');
 texto=texto.replace(/\bVila[\s-]*real\b/gi,'Vila Real')
            .replace(/\bCastelo[\s-]*branco\b/gi,'Castelo Branco')
            .replace(/\bFundao\b/gi,'Fundão')
            .replace(/\bMelgaco\b/gi,'Melgaço')
            .replace(/\bTerras[\s-]*de[\s-]*bouro\b/gi,'Terras de Bouro');
 if((texto.match(/\(/g)||[]).length>(texto.match(/\)/g)||[]).length)texto=texto.slice(0,texto.lastIndexOf('('));
 texto=texto.replace(/[\s,;:–—-]+$/g,'').trim();
 if(/^(?:Estacionamento|Em frente ao caf[eé]|Junto ao cruzeiro|Parque de Merendas|Pequeno largo em \w{1,2}|Estacionamento(?:\s+jun|\s+à\s+fa|\s+a\s+\d+))$/i.test(texto))return 'Por confirmar';
 if(/^[\d\sº°'’′″”.,:NSEW+-]+$/i.test(texto)||/^(?:Hor[aá]rio|In[ií]cio:|Final:|Coordenadas)\b/i.test(texto))return 'Por confirmar';
 return texto||'Por confirmar';
}
// Fonte desactivada: o catálogo anterior confundiu 'EVENTO FECHADO' com títulos
// e misturou actividades não pedestres. Nunca apresentar registos desta origem.
// v39 — rejeitar anúncios cujo link aponta para o agregador, independentemente do nome do organizador.
function isTrilhosCaminhadasSource(e){
 if(String(e?.source||'').trim().toLowerCase()==='trilhos & caminhadas')return true;
 try{const host=new URL(String(e?.url||'')).hostname.replace(/^www\./,'').toLowerCase();return host==='trilhosecaminhadas.pt';}
 catch{return false;}
}
// v38 — os eventos normalizados não dependem dos cálculos de viagem.
// Evita reconstruir o mesmo catálogo centenas de vezes enquanto as rotas são calculadas.
let normalizedEventsCache=null;
function allEvents(){
 const todayKey=catalogToday();
 if(normalizedEventsCache&&normalizedEventsCache.remote===remoteEvents&&
    normalizedEventsCache.custom===custom&&normalizedEventsCache.customLength===custom.length&&
    normalizedEventsCache.today===todayKey&&
    normalizedEventsCache.feedState===remoteFeedState)return normalizedEventsCache.events;
 const isOfficialCatalogue=remoteFeedState==='ready'&&Array.isArray(remoteEvents);
 // Em falha, não criar nem apresentar anúncios que não estejam no catálogo oficial.
 const source=isOfficialCatalogue?remoteEvents:[];
 const catalogue=source.filter(e=>!isTrilhosCaminhadasSource(e));
 // Os eventos pessoais já guardados continuam acessíveis em modo de leitura.
 const normalized=catalogue.concat(custom).map(x=>{
  const e={...x};
  const publishedGps=!(e.verified&&hasCoords(e))?parsePublishedGps(e.start):null;
  return {...e,...(publishedGps||{}),title:legibleEventTitle(e),verified:!!e.verified||!!publishedGps,
          start:displayDeparture(e)};
 });
 normalizedEventsCache={remote:remoteEvents,custom,customLength:custom.length,today:todayKey,feedState:remoteFeedState,events:normalized};
 return normalized;
}
// O catálogo oficial depende de eventos.json; falhas de carregamento nunca geram anúncios fictícios.
function catalogToday(){return new Date().toLocaleDateString('sv-SE',{timeZone:'Europe/Lisbon'});}
// v58 — a agenda usa sempre a hora portuguesa, independentemente do fuso do navegador.
const AGENDA_CLOCK_FORMATTER=new Intl.DateTimeFormat('en-GB',{
 timeZone:'Europe/Lisbon',year:'numeric',month:'2-digit',day:'2-digit',
 hour:'2-digit',minute:'2-digit',hourCycle:'h23'
});
function agendaClock(instant=new Date()){
 const parts=Object.fromEntries(AGENDA_CLOCK_FORMATTER.formatToParts(instant)
  .filter(part=>part.type!=='literal').map(part=>[part.type,part.value]));
 return {date:parts.year+'-'+parts.month+'-'+parts.day,
         minute:Number(parts.hour)*60+Number(parts.minute)};
}
// v75 — fins de semana relativos ao calendário de Portugal, não ao fuso do visitante.
function weekendWindows(clock=agendaClock()){
 const saturday=new Date(clock.date+'T12:00:00Z');
 const weekday=(saturday.getUTCDay()+6)%7; // Segunda=0; domingo=6.
 saturday.setUTCDate(saturday.getUTCDate()+5-weekday);
 const iso=d=>d.toISOString().slice(0,10);
 const range=extraDays=>{
  const from=new Date(saturday);from.setUTCDate(from.getUTCDate()+extraDays);
  const to=new Date(from);to.setUTCDate(to.getUTCDate()+1);
  return {from:iso(from),to:iso(to)};
 };
 const windows={this:range(0),next:range(7),following:range(14)};
 for(let week=3;week<12;week++)windows['w'+week]=range(week*7);
 return windows;
}
// v77 — separar dia e mês para manter a mesma largura em todas as datas.
function weekendLabelLines({from,to}){
 const a=new Date(from+'T12:00:00Z'),b=new Date(to+'T12:00:00Z');
 const month=d=>{const m=d.toLocaleDateString('pt-PT',{month:'short',timeZone:'UTC'}).replaceAll('.','');return m[0].toUpperCase()+m.slice(1);};
 return a.getUTCMonth()===b.getUTCMonth()&&a.getUTCFullYear()===b.getUTCFullYear()
  ?[a.getUTCDate()+'–'+b.getUTCDate(),month(b)]
  :[String(a.getUTCDate()).padStart(2,'0')+'–'+String(b.getUTCDate()).padStart(2,'0'),month(a)+'–'+month(b)];
}
function updateWeekendQuickFilters(){
 const ranges=weekendWindows();
 document.querySelectorAll('[data-quick-weekend]').forEach(button=>{
  const type=button.dataset.quickWeekend,range=ranges[type],on=state.weekend===type;
  if(!range)return;
  const lines=weekendLabelLines(range);
  button.replaceChildren(...lines.map(line=>{
   const span=document.createElement('span');
   span.className='v77-date-line';
   span.textContent=line;
   return span;
  }));
  button.classList.toggle('active',on);
  button.setAttribute('aria-pressed',String(on));
  button.setAttribute('aria-label','Caminhadas de '+range.from+' a '+range.to);
  button.title='Caminhadas de '+range.from+' a '+range.to;
 });
}
function eventHasNotStarted(e,clock=agendaClock()){
 if(!e||typeof e.date!=='string')return false;
 if(e.date!==clock.date)return e.date>clock.date;
 // Se o organizador não indicar uma hora válida, conservar até ao fim desse dia.
 const match=typeof e.time==='string'?e.time.trim().match(/^([01]?\d|2[0-3])[:h]([0-5]\d)$/i):null;
 if(!match)return true;
 return Number(match[1])*60+Number(match[2])>clock.minute;
}
function agendaUpcomingFingerprint(clock=agendaClock()){
 return allEvents().filter(e=>eventHasNotStarted(e,clock)).map(e=>e.id).join('\u001f');
}
let agendaCurrentFingerprint='',agendaDisplayedDate='';
function refreshAgendaForClock(){
 if(document.hidden)return;
 const clock=agendaClock(),current=agendaUpcomingFingerprint(clock);
 if(current!==agendaCurrentFingerprint||clock.date!==agendaDisplayedDate){populateOrganizers();render();}
}
function renderCatalogStatus(){
 // O estado normal do catálogo não ocupa espaço na página.
 // Quando a fonte falha ou está muito desactualizada, mostrar apenas o aviso útil.
 const node=$('catalogStatus');if(!node)return;
 let status=remoteFeedState,message='';
 if(status==='unavailable')message='Não foi possível carregar a agenda online. Tenta actualizar a página.';
 else if(status==='invalid')message='A agenda online está temporariamente indisponível por dados inválidos.';
 else if(status==='offline')message='A agenda necessita de acesso ao servidor; abre o Trilhário através do site.';
 else if(status==='ready'){
  const when=remoteUpdatedAt?new Date(remoteUpdatedAt):null;
  const age=when&&Number.isFinite(when.getTime())?(Date.now()-when.getTime())/3600000:Infinity;
  if(age>48||age< -1){status='stale';message='A agenda pode estar desactualizada. Confirma os detalhes no site do organizador.';}
 }
 node.hidden=!message;
 node.dataset.status=status;
 node.textContent=message;
}
// v44: a data de PUBLICAÇÃO do JSON não confirma cada caminhada individual.
// Só avisar quando existe uma data de observação conhecida e suficientemente antiga.
function eventFreshnessNote(event){
 const stamp=event?.last_confirmed_at||event?.last_seen_at;
 if(typeof stamp!=='string'||!stamp)return '';
 const when=new Date(/^\d{4}-\d{2}-\d{2}$/.test(stamp)?stamp+'T12:00:00Z':stamp);
 if(!Number.isFinite(when.getTime()))return '';
 const days=Math.floor((Date.now()-when.getTime())/86400000);
 if(days<7||days>3650)return '';
 return '<small class="walk-staleness" title="O anúncio não foi reconfirmado pelo Trilhário; consulte o organizador">Não reconfirmado há '+days+' dias</small>';
}

async function loadEventFeed(){
 if(location.protocol==='file:'){remoteFeedState='offline';renderCatalogStatus();render();return;}
 try{
  const response=await fetch('eventos.json',{cache:'no-store'});
  if(!response.ok){remoteFeedState='unavailable';renderCatalogStatus();render();return;}
  const json=await response.json();
  if(!json||!Array.isArray(json.events)||json.events.length>10000){remoteFeedState='invalid';renderCatalogStatus();render();return;}
  const events=json.events.filter(e=>e&&typeof e.id==='string'&&typeof e.title==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(e.date)&&typeof e.organizer==='string'
    && !isTrilhosCaminhadasSource(e)
    && !(e.organizer==='Montanhas Dentro' && e.date_verified!=='official_detail'))
    .map(e=>({...e,url:(typeof e.url==='string'&&/^https?:\/\//i.test(e.url))?e.url:''}));
  remoteEvents=events;
  remoteUpdatedAt=typeof json.updated_at==='string'?json.updated_at:null;
  remoteSourcesHealth=json.sources_health&&typeof json.sources_health==='object'&&!Array.isArray(json.sources_health)?json.sources_health:null;
  remoteFeedState='ready';
  const clock=agendaClock();
  const future=events.filter(e=>eventHasNotStarted(e,clock)).map(e=>e.date).sort();
  if(future.length){state.year=Number(future[0].slice(0,4));state.month=Number(future[0].slice(5,7))-1;}
  geo.selectionShown=false;populateOrganizers();render();
  // Fotografias existentes dos próximos fins de semana entram antecipadamente na cache.
  warmUpcomingWeekendPhotos();
 }catch(err){remoteFeedState='unavailable';console.info('Catálogo externo indisponível; sem eventos de demonstração.',err?.message);renderCatalogStatus();render();}
}

const fold=t=>String(t??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
// Portugal continental e arquipélagos; rejeitar 0,0, pares incompletos e valores fora da área.
const hasCoords=x=>{
 if(x?.lat==null||x?.lon==null||String(x.lat).trim()===''||String(x.lon).trim()==='')return false;
 const lat=Number(x.lat),lon=Number(x.lon);
 if(!Number.isFinite(lat)||!Number.isFinite(lon))return false;
 return (lat>=36&&lat<=43&&lon>=-10&&lon<=-6)|| // continental
        (lat>=31.8&&lat<=33.6&&lon>=-18&&lon<=-15.5)|| // Madeira
        (lat>=36.5&&lat<=40.1&&lon>=-32&&lon<=-24); // Açores
};
function parsePublishedGps(raw){
 const text=String(raw||'');
 // Ex.: «Lat: N 39° 21' 9.5\" Long: W 9° 9' 29.4\"» ou «Lat: 39,580825 Long: -8,327668».
 const m=text.match(/\bLat(?:itude)?\s*:\s*([\s\S]*?)\bLong(?:itude)?\s*:\s*([\s\S]*)/i);
 if(!m)return null;
 const coord=(s,isLongitude)=>{
   const fragment=s.split(/\b(?:Hora|Fim|Início|Inicio|Mapa|Ponto|GPS)\b/i)[0].trim();
   const nums=(fragment.match(/-?\d+(?:[.,]\d+)?/g)||[]).slice(0,3).map(v=>Number(v.replace(',','.')));
   if(!nums.length)return null;
   const direction=(fragment.match(/^[\s]*([NSEW])/i)||[])[1]?.toUpperCase()||'';
   // Uma coordenada apenas em graus inteiros não é informação bastante.
   let absolute;
   if(nums.length===1){if(!/[.,]\d{3,}/.test(fragment))return null;absolute=Math.abs(nums[0]);}
   else {if(nums[1]<0||nums[1]>=60||nums.length===3&&(nums[2]<0||nums[2]>=60))return null;
     absolute=Math.abs(nums[0])+nums[1]/60+(nums[2]||0)/3600;}
   return (direction==='W'||direction==='S'||nums[0]<0?-1:1)*absolute;
 };
 const lat=coord(m[1],false),lon=coord(m[2],true);
 const p={lat,lon};return hasCoords(p)?{...p,verified:true,gpsFromAnnouncement:true}:null;
}
const dur=x=>Number.isFinite(Number(x.duration))&&x.duration!=null&&x.duration!==''?fmtN(x.duration):'—';
function populateOrganizers(){
 const select=$('organizer');
 const orgs=[...new Set(allEvents().map(e=>String(e.organizer||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pt'));
 if(state.organizer!=='all'&&!orgs.includes(state.organizer))state.organizer='all';
 select.innerHTML='<option value="all">Todos os organizadores</option>'+orgs.map(name=>'<option value="'+esc(name)+'">'+esc(name)+'</option>').join('');
 select.value=state.organizer;
}
function selected({ignoreDay=false}={}){const clock=agendaClock(),weekend=state.weekend==='all'?null:weekendWindows(clock)[state.weekend];return allEvents().filter(x=>
  eventHasNotStarted(x,clock)&&
   (ignoreDay||state.day==='all'||x.date===state.day)&&
   (!weekend||(x.date>=weekend.from&&x.date<=weekend.to))&&
  (state.organizer==='all'||x.organizer===state.organizer)&&
  ((state.kmMin===0&&state.kmMax===KM_CAP)||(x.km!=null&&Number(x.km)>=state.kmMin&&Number(x.km)<=state.kmMax))&&
  ((state.gainMin===0&&state.gainMax===GAIN_CAP)||(x.gain!=null&&Number(x.gain)>=state.gainMin&&Number(x.gain)<=state.gainMax))
 ).sort((a,b)=>a.date.localeCompare(b.date)||String(a.time).localeCompare(String(b.time))||a.title.localeCompare(b.title,'pt'))}
function dateShort(x){return new Date(x.date+'T12:00:00').toLocaleDateString('pt-PT',{weekday:'short',day:'2-digit',month:'short'}).replaceAll('.','')}
// Links fiáveis e em novo separador. Não transformar textos em URLs sem validação.
const safeExternalUrl=u=>typeof u==='string'&&/^https?:\/\//i.test(u)?u:'';
function organizerHomepage(x){
 const entry=ORGANIZER_DIRECTORY.find(org=>fold(org.name)===fold(x.organizer));
 if(entry&&safeExternalUrl(entry.url))return entry.url;
 try{return safeExternalUrl(x.url)?new URL(x.url).origin+'/':'';}catch{return '';}
}
function googleMapsDeparture(x,spot){
 const text=String(spot||'').trim();
 if(!text||/^(?:por confirmar|a confirmar|desconhecido)(?:\b|$)/i.test(text))return '';
 // Usar coordenadas apenas quando o próprio ponto foi confirmado pela fonte.
 const query=x.verified&&hasCoords(x)?Number(x.lat)+','+Number(x.lon):
   [text.replace(/\s*\([^)]*(?:a confirmar|ponto exacto|local exacto)[^)]*\)/gi,'').trim(),
    x.town&&fold(text).includes(fold(localPartidaLegivel(x.town)))?'':localPartidaLegivel(x.town),'Portugal'].filter(Boolean).join(', ');
 return 'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(query);
}
const TRILHARIO_DELETE_ICON='<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18m-2 0-1 15H6L5 6m3 0V4h8v2m-6 4v7m4-7v7"/></svg>';
// Guia discreto: visível na primeira visita; o utilizador pode voltar a abri-lo.
const INTRO_HELP_KEY='trilhario_intro_v33_closed';
let introHelpVisible=!storage(INTRO_HELP_KEY,false);
function syncIntroHelp(){
 const guide=$('introGuide'),trigger=$('introHelpOpen');
 guide.hidden=!introHelpVisible;
 trigger.setAttribute('aria-expanded',String(introHelpVisible));
}
function initIntroHelp(){
 $('introHelpOpen').addEventListener('click',()=>{
  introHelpVisible=!introHelpVisible;syncIntroHelp();
  if(introHelpVisible)$('introGuide').scrollIntoView({behavior:'smooth',block:'nearest'});
 });
 $('introHelpClose').addEventListener('click',()=>{
  introHelpVisible=false;
  persistValue(INTRO_HELP_KEY,true);
  syncIntroHelp();$('introHelpOpen').focus({preventScroll:true});
 });
 syncIntroHelp();
}
function eventPhotoUrl(e){
 const val=e&&e.image;
 if(typeof val!=='string'||!/^https:\/\/[^/]+/i.test(val))return '';
 try{const u=new URL(val);return u.protocol==='https:'&&!!u.hostname&&u.username===''&&u.password===''?u.href:''}
 catch{return ''}
}
// v85 — pré-carregamento limitado a dois fins de semana, sem tocar em outros eventos.
// Três transferências simultâneas protegem a resposta no telemóvel; URLs únicas
// deixam a cache HTTP do navegador tratar das imagens já descarregadas.
const queuedWeekendPhotos=new Set();
const pendingWeekendPhotos=[];
const activeWeekendPhotoLoads=new Set();
function pumpUpcomingWeekendPhotos(){
 while(activeWeekendPhotoLoads.size<3&&pendingWeekendPhotos.length){
  const url=pendingWeekendPhotos.shift();
  const image=new Image();
  activeWeekendPhotoLoads.add(image);
  image.decoding='async';
  image.referrerPolicy='strict-origin-when-cross-origin';
  if('fetchPriority' in image)image.fetchPriority='low';
  const done=()=>{image.onload=null;image.onerror=null;activeWeekendPhotoLoads.delete(image);pumpUpcomingWeekendPhotos();};
  image.onload=done;
  image.onerror=done;
  image.src=url;
 }
}
function warmUpcomingWeekendPhotos(){
 if(remoteFeedState!=='ready'||!Array.isArray(remoteEvents))return;
 if(navigator.connection?.saveData)return;
 const windows=weekendWindows(),today=agendaClock().date;
 const keys=today>windows.this.from?['next','following']:['this','next'];
 const chosen=keys.map(key=>windows[key]);
 for(const event of remoteEvents){
  if(!chosen.some(r=>event.date>=r.from&&event.date<=r.to))continue;
  const url=eventPhotoUrl(event);
  if(url&&!queuedWeekendPhotos.has(url)){
   queuedWeekendPhotos.add(url);
   pendingWeekendPhotos.push(url);
  }
 }
 pumpUpcomingWeekendPhotos();
}
function eventRow(x){
 const spot=displayDeparture(x),verified=!!x.verified;
 const photoUrl=eventPhotoUrl(x);
  const organizerUrl=organizerHomepage(x),mapsUrl=isPlacePlaceholder(spot)?null:googleMapsDeparture(x,spot);
 const dt=new Date(x.date+'T12:00:00');
 const month=dt.toLocaleDateString('pt-PT',{month:'short'}).replace('.','').toUpperCase();
 const weekday=dt.toLocaleDateString('pt-PT',{weekday:'short'}).replace('.','').toUpperCase();
 const gain=x.gain!=null?'+'+fmtN(x.gain)+' m':'—';
 const distance=x.km!=null?fmtN(x.km)+' km':'—';
 const duration=x.duration!=null?(x.estimatedDuration?'≈ ':'')+dur(x)+' h':'—';
 // Mostrar o fim previsto apenas quando há hora de início e duração conhecidas.
 // O cálculo é uma estimativa, não um horário publicado pelo organizador.
 const validClock=t=>typeof t==='string'&&/^([01]\d|2[0-3]):[0-5]\d$/.test(t);
 const begin=validClock(x.time)?x.time:'Por confirmar';
 let finish='Por confirmar';
 if(validClock(x.endTime)){
   finish=x.endTime;
 }else if(validClock(x.time)&&x.duration!=null&&Number.isFinite(Number(x.duration))&&Number(x.duration)>0){
   const mins=Number(x.time.slice(0,2))*60+Number(x.time.slice(3,5))+Math.round(Number(x.duration)*60);
   finish='≈ '+String(Math.floor(mins/60)%24).padStart(2,'0')+':'+String(mins%60).padStart(2,'0')+(mins>=1440?' (+1 dia)':'');
 }
 return `<article class="walk-row v51-card v56-card" data-eid="${esc(x.id)}">
  <div class="walk-date"><strong>${dt.getDate()}</strong><span>${month}</span><small>${weekday}</small></div>
  <div class="walk-main">
   <h3 title="${esc(legibleEventTitle(x))}">${safeExternalUrl(x.url)?`<a class="walk-title-link" href="${esc(x.url)}" target="_blank" rel="noopener noreferrer" title="${esc(legibleEventTitle(x))}">${esc(legibleEventTitle(x))}</a>`:esc(legibleEventTitle(x))}</h3>
   <div class="walk-card-details">
   <p class="walk-organizer"><span class="walk-caption">Organizador:</span> ${organizerUrl?`<a class="walk-text-link" href="${esc(organizerUrl)}" target="_blank" rel="noopener noreferrer" title="Abrir site de ${esc(x.organizer)}">${esc(x.organizer)}</a>`:`<strong>${esc(x.organizer)}</strong>`}${eventFreshnessNote(x)}</p>
   <p class="walk-start"><span class="walk-caption">Local de partida:</span> ${mapsUrl?`<a class="walk-text-link" href="${esc(mapsUrl)}" target="_blank" rel="noopener noreferrer" title="Localizar no Google Maps">${esc(spot)}</a>`:`<strong>${esc(spot)}</strong>`}${verified?'':!isPlacePlaceholder(spot)?'':''}</p>
   <p class="walk-times"><span><span class="walk-caption">Início:</span> <strong>${esc(begin)}</strong></span><span class="walk-time-divider" aria-hidden="true">·</span><span><span class="walk-caption">Fim previsto:</span> <strong>${esc(finish)}</strong></span></p>
   <p class="v51-difficulty"><span class="walk-caption">Dificuldade:</span> <strong>${esc(names[x.difficulty]||'Por indicar')}</strong></p>
   </div>
   ${photoUrl?`<img class="walk-photo" src="${esc(photoUrl)}" alt="Imagem ilustrativa publicada pelo organizador para ${esc(x.title)}" loading="lazy" decoding="async" fetchpriority="low" referrerpolicy="strict-origin-when-cross-origin" width="94" height="94" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'v51-no-photo',textContent:'↗'}))">`:'<div class="v51-no-photo" aria-hidden="true">↗</div>'}
  </div>
  <div class="walk-metrics">
   <span><small>Distância</small><b>${distance}</b></span>
   <span><small title="Desnível positivo: subida acumulada em metros" aria-label="Desnível positivo (subida acumulada)">Desnível D+</small><b>${gain}</b></span>
   <span><small>Duração</small><b>${duration}</b></span>
   <span><small>Inscrição</small><b>${fmtP(x.price)}</b></span>
  </div>
  ${travelRow(x)}
  ${x.userAdded?`<div class="walk-actions" role="group" aria-label="Acções de ${esc(x.title)}">
   <div class="walk-action-quick">
    <button type="button" class="walk-icon-btn walk-delete" data-event-action="removeEvent" data-event-id="${esc(x.id)}" aria-label="Eliminar caminhada personalizada: ${esc(x.title)}" title="Eliminar caminhada">${TRILHARIO_DELETE_ICON}</button>
   </div>
  </div>`:''}
 </article>`;
}
function chips(){let xs=[];
 if(state.day!=='all'){const d=new Date(state.day+'T12:00:00').toLocaleDateString('pt-PT',{day:'2-digit',month:'2-digit'});xs.push('<button type="button" class="pill pill-clear-day" data-ui-action="clearDay" title="Remover filtro do dia" aria-label="Remover filtro do dia '+d+'">Dia: '+d+' <span aria-hidden="true">×</span></button>');}
 if(state.organizer!=='all')xs.push('Organizador: '+state.organizer);
 if(state.kmMin>0||state.kmMax<KM_CAP)xs.push('Distância: '+state.kmMin+'–'+state.kmMax+' km');
 if(state.gainMin>0||state.gainMax<GAIN_CAP)xs.push('D+: '+state.gainMin+'–'+state.gainMax+' m');
 return xs.map(t=>t.startsWith('<button')?t:`<span class="pill">${esc(t)}</span>`).join('')}


let geo={zoom:7,center:{lat:40.50,lon:-8.15},layer:'satellite',picked:null,initialized:false,selectionShown:false};
const MAP_BOUNDS={west:-10.4,east:-5.5,south:36.4,north:43.6};
const worldX=(lon,z)=>((Number(lon)+180)/360)*256*2**z;
const worldY=(lat,z)=>{const r=Math.max(-85,Math.min(85,Number(lat)))*Math.PI/180;return (1-Math.log(Math.tan(Math.PI/4+r/2))/Math.PI)/2*256*2**z};
const toScreen=(lat,lon)=>{const c=$('map');return{x:worldX(lon,geo.zoom)-worldX(geo.center.lon,geo.zoom)+c.clientWidth/2,y:worldY(lat,geo.zoom)-worldY(geo.center.lat,geo.zoom)+c.clientHeight/2}};
const toLatLon=(x,y,z)=>{const n=256*2**z,lon=x/n*360-180,lat=(Math.atan(Math.sinh(Math.PI*(1-2*y/n)))*180/Math.PI);return {lat,lon}};
const coordsAt=(px,py)=>{let c=$('map');return toLatLon(worldX(geo.center.lon,geo.zoom)+px-c.clientWidth/2,worldY(geo.center.lat,geo.zoom)+py-c.clientHeight/2,geo.zoom)};
const mapTileUrl=(z,x,y)=>geo.layer==='satellite'?`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${z}/${y}/${x}`:`https://tile.openstreetmap.org/${z}/${x}/${y}.png`;
function setMapLayer(layer){geo.layer=layer;$('layerSatellite').classList.toggle('active',layer==='satellite');$('layerStreets').classList.toggle('active',layer==='streets');$('geoAttribution').textContent=layer==='satellite'?'Imagens © Esri e fornecedores · base offline geográfica':'© OpenStreetMap contributors · base offline geográfica';paintMap()}
// v46: manter os nós existentes; arrastar o mapa altera posições, não URLs/imagens.
let mapPaintScheduled=false;
function scheduleMapPaint(){
 if(mapPaintScheduled)return;
 mapPaintScheduled=true;
 requestAnimationFrame(()=>{mapPaintScheduled=false;paintMap();});
}
function paintMap(){
 if(state.view!=='map')return;
 const root=$('map'),w=root.clientWidth,h=root.clientHeight;if(!w||!h)return;
 const cx=worldX(geo.center.lon,geo.zoom),cy=worldY(geo.center.lat,geo.zoom);
 const x0=Math.floor((cx-w/2)/256)-1,x1=Math.floor((cx+w/2)/256)+1;
 const y0=Math.floor((cy-h/2)/256)-1,y1=Math.floor((cy+h/2)/256)+1,maxTile=2**geo.zoom;
 const tileLayer=$('tileLayer');
 const existingTiles=new Map(Array.from(tileLayer.children).map(node=>[node.dataset.tileKey,node]));
 for(let x=x0;x<=x1;x++)for(let y=y0;y<=y1;y++){
  if(y<0||y>=maxTile)continue;
  const key=`${geo.layer}/${geo.zoom}/${x}/${y}`;
  let tile=existingTiles.get(key);
  if(!tile){
   tile=document.createElement('img');tile.className='map-tile';tile.alt='';tile.loading='lazy';
   tile.dataset.tileKey=key;
   tile.addEventListener('error',()=>{tile.style.display='none'});
   tile.src=mapTileUrl(geo.zoom,((x%maxTile)+maxTile)%maxTile,y);
   tileLayer.appendChild(tile);
  }
  tile.style.left=Math.round(x*256-cx+w/2)+'px';
  tile.style.top=Math.round(y*256-cy+h/2)+'px';
  existingTiles.delete(key);
 }
 for(const stale of existingTiles.values())stale.remove();
 const b=MAP_BOUNDS,fw=worldX(b.east,geo.zoom)-worldX(b.west,geo.zoom),
  fh=worldY(b.south,geo.zoom)-worldY(b.north,geo.zoom),fpos=toScreen(b.north,b.west),base=$('fallbackBase');
 Object.assign(base.style,{left:fpos.x+'px',top:fpos.y+'px',width:fw+'px',height:fh+'px',right:'auto',bottom:'auto'});
 const markerLayer=$('markerLayer'),existingMarkers=new Map(Array.from(markerLayer.children).map(n=>[n.dataset.id,n]));
 const events=selected().filter(hasCoords);
 for(let i=0;i<events.length;i++){
  const e=events[i],pos=toScreen(e.lat,e.lon);
  if(pos.x< -50||pos.x>w+50||pos.y< -50||pos.y>h+50)continue;
  const id=String(e.id),picked=geo.picked===e.id;
  let marker=existingMarkers.get(id);
  if(!marker){
   marker=document.createElement('button');marker.type='button';marker.dataset.id=id;
   marker.addEventListener('click',ev=>{ev.stopPropagation();mapSelect(marker.dataset.id)});
   markerLayer.appendChild(marker);
  }
  marker.className='geo-marker'+(e.verified?'':' approx')+(picked?' picked':'');
  marker.setAttribute('aria-label',e.title);marker.title=e.title;
  marker.style.left=pos.x+'px';marker.style.top=pos.y+'px';
  marker.style.zIndex=String(picked?30:5+i);
  const wasPicked=marker.dataset.picked==='true';
  if(marker.childElementCount===0||picked!==wasPicked){
   marker.innerHTML='<span class="stem"></span>'+(picked?'<span class="pin-number">Seleccionado</span>':'');
   marker.dataset.picked=String(picked);
  }
  existingMarkers.delete(id);
 }
 for(const stale of existingMarkers.values())stale.remove();
 const selectedEvent=geo.picked?events.find(e=>e.id===geo.picked):null;
 const popup=$('geoPopup');
 if(popup&&(!selectedEvent||popup.dataset.eventId!==String(selectedEvent.id)))popup.remove();
 if(selectedEvent){
  const existing=$('geoPopup');
  if(existing){const pos=toScreen(selectedEvent.lat,selectedEvent.lon);
    existing.hidden=pos.x<100||pos.x>w-100||pos.y<145||pos.y>h-20;
    existing.style.left=pos.x+'px';existing.style.top=(pos.y-24)+'px';
  }else showGeoPopup(selectedEvent);
 }
}
function showGeoPopup(e){const pos=toScreen(e.lat,e.lon),w=$('map').clientWidth,h=$('map').clientHeight;if(pos.x<100||pos.x>w-100||pos.y<145||pos.y>h-20)return;const popup=document.createElement('div');popup.className='geo-popup';popup.id='geoPopup';popup.dataset.eventId=String(e.id);popup.style.left=pos.x+'px';popup.style.top=(pos.y-24)+'px';popup.innerHTML=`<button type="button" aria-label="Fechar" class="close" data-ui-action="closeMapPopup">×</button><small>${esc(dateShort(e))} · Organizador: ${esc(e.organizer)}</small><h3>${esc(e.title)}</h3><p>Local de partida: ${esc(displayDeparture(e))} · ${e.verified?'local confirmado':'localidade aproximada (a confirmar)'}</p><div class="popup-stats">${fmtN(e.km)} km · ${e.gain!=null?'+'+fmtN(e.gain)+' m D+':'D+ —'} · ${e.duration!=null?dur(e)+' h':'Tempo —'} · ${fmtP(e.price)}</div><div class="popup-actions">${e.url?`<a target="_blank" rel="noopener noreferrer" href="${esc(e.url)}">Inscrição ↗</a>`:''}</div>`;$('map').appendChild(popup)}
function mapFitTo(events){const ps=events.filter(hasCoords),root=$('map');if(!ps.length||!root.clientWidth)return;const midX=(Math.min(...ps.map(e=>worldX(e.lon,7)))+Math.max(...ps.map(e=>worldX(e.lon,7))))/2,midY=(Math.min(...ps.map(e=>worldY(e.lat,7)))+Math.max(...ps.map(e=>worldY(e.lat,7))))/2;let z=12;for(;z>5;z--){const xx=ps.map(e=>worldX(e.lon,z)),yy=ps.map(e=>worldY(e.lat,z));if(Math.max(...xx)-Math.min(...xx)<root.clientWidth-95 && Math.max(...yy)-Math.min(...yy)<root.clientHeight-100)break;}geo.zoom=z;const pt=toLatLon(midX*2**(z-7),midY*2**(z-7),z);geo.center=pt;paintMap()}
function zoomTo(z,pivot){z=Math.max(5,Math.min(15,z));if(geo.zoom===z)return;const root=$('map'),p=pivot||{x:root.clientWidth/2,y:root.clientHeight/2},oldPos=coordsAt(p.x,p.y),oldZ=geo.zoom;geo.zoom=z;const nowPx=worldX(oldPos.lon,z),nowPy=worldY(oldPos.lat,z),cx=nowPx-(p.x-root.clientWidth/2),cy=nowPy-(p.y-root.clientHeight/2);geo.center=toLatLon(cx,cy,z);paintMap()}
function initGeo(){if(geo.initialized)return;geo.initialized=true;const canvas=$('map');let dragging=null;
 canvas.addEventListener('pointerdown',ev=>{if(ev.target.closest('button')||ev.target.closest('a'))return;dragging={x:ev.clientX,y:ev.clientY,cx:worldX(geo.center.lon,geo.zoom),cy:worldY(geo.center.lat,geo.zoom)};canvas.classList.add('dragging');canvas.setPointerCapture(ev.pointerId)});
 canvas.addEventListener('pointermove',ev=>{if(!dragging)return;geo.center=toLatLon(dragging.cx-(ev.clientX-dragging.x),dragging.cy-(ev.clientY-dragging.y),geo.zoom);scheduleMapPaint()});
 canvas.addEventListener('pointerup',()=>{dragging=null;canvas.classList.remove('dragging');scheduleMapPaint()});canvas.addEventListener('pointercancel',()=>{dragging=null;canvas.classList.remove('dragging')});
 canvas.addEventListener('wheel',ev=>{ev.preventDefault();const r=canvas.getBoundingClientRect();zoomTo(geo.zoom+(ev.deltaY<0?1:-1),{x:ev.clientX-r.left,y:ev.clientY-r.top})},{passive:false});
 $('zoomIn').addEventListener('click',()=>zoomTo(geo.zoom+1));$('zoomOut').addEventListener('click',()=>zoomTo(geo.zoom-1));$('layerSatellite').addEventListener('click',()=>setMapLayer('satellite'));$('layerStreets').addEventListener('click',()=>setMapLayer('streets'));$('fitBtn').addEventListener('click',()=>{geo.picked=null;mapFitTo(selected())});$('kmlBtn').addEventListener('click',downloadKml);
 if('ResizeObserver' in window)new ResizeObserver(()=>{if(state.view==='map')scheduleMapPaint()}).observe(canvas);
}
function downloadKml(){const es=selected().filter(hasCoords);if(!es.length){toast('Sem coordenadas disponíveis para exportar.');return};const xml=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');const content=`<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Trilhário — Caminhadas filtradas</name><Style id="confirmed"><IconStyle><color>ff43aa42</color><scale>1.05</scale></IconStyle></Style><Style id="approx"><IconStyle><color>ff399bcf</color><scale>1.05</scale></IconStyle></Style>${es.map(e=>`<Placemark><name>${xml(e.title)}</name><description>${xml(`${e.date} · ${e.km??'—'} km · ${e.gain??'—'} m D+ · ${fmtP(e.price)} · ${e.organizer} · ${e.verified?'Ponto confirmado':'Ponto APROXIMADO — confirmar local exacto'}`)}</description><styleUrl>#${e.verified?'confirmed':'approx'}</styleUrl><Point><coordinates>${Number(e.lon)},${Number(e.lat)},0</coordinates></Point></Placemark>`).join('')}</Document></kml>`;saveBlob(new Blob([content],{type:'application/vnd.google-earth.kml+xml;charset=utf-8'}),'trilhario-caminhadas.kml');toast(`${es.length} pontos exportados em KML para Google Earth.`)}
function renderMap(events){initGeo();const ps=events.filter(hasCoords),verified=ps.filter(x=>x.verified).length;$('mapCount').textContent=`${ps.length} pins · ${verified} confirmados`;
 $('mapSide').innerHTML=events.length?events.map(x=>`<button class="map-side-item ${geo.picked===x.id?'selected':''}" data-id="${esc(x.id)}" data-event-action="mapSelect" data-event-id="${esc(x.id)}" ${!hasCoords(x)?'disabled':''}><strong>${esc(x.title)}</strong><small>Organizador: ${esc(x.organizer)} · Local de partida: ${esc(displayDeparture(x))}${x.verified?'':' (a confirmar)'}</small><span>${esc(dateShort(x))} · ${x.km!=null?fmtN(x.km)+' km':'km —'} · <span class="mapgain">${x.gain!=null?'+'+fmtN(x.gain)+' m D+':'D+ —'}</span> · ${fmtP(x.price)}</span><small>${x.duration!=null?(x.estimatedDuration?'≈ ':'')+dur(x)+' h':'Duração —'} · ${x.verified?'● início confirmado':'○ ponto aproximado'}</small></button>`).join(''):'<p class="map-side-item">Sem resultados. Altera os filtros.</p>';
 requestAnimationFrame(()=>{if(!geo.selectionShown){geo.selectionShown=true;mapFitTo(events);}else paintMap()})}
function mapSelect(id){const e=selected().find(x=>x.id===id);if(!e)return;if(!hasCoords(e)){toast('Este evento não tem coordenadas.');return}geo.picked=id;geo.zoom=Math.max(geo.zoom,10);geo.center={lat:Number(e.lat),lon:Number(e.lon)};$('mapSide').querySelectorAll('button').forEach(b=>b.classList.toggle('selected',b.dataset.id===id));paintMap()}
function updateDualUI(prefix,low,high,cap,unit){
 const from=100*low/cap,to=100*high/cap;
 const track=$(prefix+'Track');track.style.setProperty('--from',from+'%');track.style.setProperty('--to',to+'%');
 $(prefix+'MinValue').textContent=low+' '+unit;
 $(prefix+'MaxValue').textContent=high+' '+unit;
 const minimum=$(prefix+'Min'),maximum=$(prefix+'Max');
 minimum.value=low;maximum.value=high;
 minimum.setAttribute('aria-valuetext',low+' '+unit);
 maximum.setAttribute('aria-valuetext',high+' '+unit);
 // Quando os cursores se aproximam, manter o mínimo seleccionável.
 minimum.style.zIndex=(low>=high-(prefix==='km'?5:250))?'3':'2';
 maximum.style.zIndex='2';
}
function changeDual(prefix,which,value){
 const isKm=prefix==='km';const minKey=prefix+'Min',maxKey=prefix+'Max';
 const gap=isKm?1:50,cap=isKm?KM_CAP:GAIN_CAP;
 const v=Math.max(0,Math.min(cap,Number(value)));
 if(which==='Min')state[minKey]=Math.min(v,state[maxKey]-gap);
 else state[maxKey]=Math.max(v,state[minKey]+gap);
 render();
}
// v46 — paginação apenas na apresentação. Os filtros, calendário, mapa,
// mapa, calendário e filtros continuam a considerar o catálogo completo.
const LIST_INITIAL=30,LIST_INCREMENT=30;
let listLimit=LIST_INITIAL,listSignature='',listWalks=[],listMoreObserver=null;
function stopListObserver(){if(listMoreObserver){listMoreObserver.disconnect();listMoreObserver=null;}}
function renderProgressiveList(events){
 const stableSignature=JSON.stringify([state.day,state.weekend,state.organizer,state.kmMin,state.kmMax,
   state.gainMin,state.gainMax,$('travelSort')?.value||'date',
   remoteFeedState,remoteUpdatedAt,custom.length,events.length,events[0]?.id,events.at(-1)?.id]);
 if(stableSignature!==listSignature){listSignature=stableSignature;listLimit=LIST_INITIAL;}
 listWalks=events;
 stopListObserver();
 if(!events.length){$('listView').innerHTML='<div class="empty"><h3>Sem caminhadas para estes filtros</h3><p>Altera os filtros de distância, desnível ou organizador.</p><button data-ui-action="resetFilters">Limpar filtros</button></div>';return;}
 listLimit=Math.min(listLimit,events.length);
 $('listView').innerHTML=events.slice(0,listLimit).map(eventRow).join('')+
  (listLimit<events.length?listMoreHtml(events.length):'');
 observeListMore();
}
function listMoreHtml(total){return `<div id="listMoreSentinel" class="list-more" role="status">
 <small>A mostrar ${listLimit} de ${total} caminhadas</small>
 <button type="button" id="listMoreButton" data-ui-action="loadMore">Mostrar mais caminhadas</button></div>`;}
function observeListMore(){
 const node=$('listMoreSentinel');
 if(!node||typeof IntersectionObserver!=='function')return;
 listMoreObserver=new IntersectionObserver(entries=>{
   if(entries.some(entry=>entry.isIntersecting))loadMoreWalks();
 },{root:null,rootMargin:'250px 0px',threshold:0});
 listMoreObserver.observe(node);
}
function loadMoreWalks(){
 if(state.view!=='list'||!$('listMoreSentinel')||listLimit>=listWalks.length)return;
 const old=listLimit,next=Math.min(old+LIST_INCREMENT,listWalks.length);
 const sentinel=$('listMoreSentinel');
 stopListObserver();
 sentinel.insertAdjacentHTML('beforebegin',listWalks.slice(old,next).map(eventRow).join(''));
 listLimit=next;
 if(listLimit>=listWalks.length)sentinel.remove();
 else {sentinel.querySelector('small').textContent=`A mostrar ${listLimit} de ${listWalks.length} caminhadas`;observeListMore();}
 // Respeitar os lotes de cálculo de deslocações para os cartões agora visíveis.
 scheduleTravelBatches(listWalks);
}
function render(){agendaCurrentFingerprint=agendaUpcomingFingerprint();agendaDisplayedDate=agendaClock().date;const events=sortedWalks(selected());
 // O calendário usa os outros filtros, mas não restringe os resultados ao dia destacado.
 const displayedEvents=state.view==='calendar'?sortedWalks(selected({ignoreDay:true})):events;
 renderCatalogStatus();
 const applied=[state.day!=='all',state.weekend!=='all',state.organizer!=='all',state.kmMin>0||state.kmMax<KM_CAP,state.gainMin>0||state.gainMax<GAIN_CAP].filter(Boolean).length;
 $('filtersCounterMini').textContent=applied?String(applied):'';$('filtersCounterMini').hidden=!applied;
 updateDualUI('km',state.kmMin,state.kmMax,KM_CAP,'km');
 updateDualUI('gain',state.gainMin,state.gainMax,GAIN_CAP,'m');
  document.querySelectorAll('[data-quick-km]').forEach(b=>{const on=state.kmMin===Number(b.dataset.quickKm)&&state.kmMax===KM_CAP;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));});
  updateWeekendQuickFilters();
 renderOrganizersPage();$('chips').innerHTML=chips();$('listView').hidden=state.view!=='list';$('calendarView').hidden=state.view!=='calendar';$('mapView').hidden=state.view!=='map';document.querySelectorAll('[data-day]').forEach(b=>b.classList.toggle('active',b.dataset.day===state.day));document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===state.view);b.setAttribute('aria-pressed',String(b.dataset.view===state.view))});if(state.view==='list'){renderProgressiveList(events);
   scheduleTravelBatches(events);
 }else{stopListObserver();if(tripBatchObserver){tripBatchObserver.disconnect();tripBatchObserver=null;}if(state.view==='calendar')renderCalendar(displayedEvents);else renderMap(events)}}
// v47B — calendário mensal completo. A data destacada filtra a Lista, não o mês.
function calendarDateLabel(iso){return new Date(iso+'T12:00:00').toLocaleDateString('pt-PT',{
 weekday:'long',day:'numeric',month:'long',year:'numeric'});}
function renderCalendar(events){
 const byDate=new Map();
 for(const e of events){if(!byDate.has(e.date))byDate.set(e.date,[]);byDate.get(e.date).push(e);}
 const m=state.month,y=state.year,first=new Date(y,m,1),start=(first.getDay()+6)%7,
       total=new Date(y,m+1,0).getDate(),len=Math.ceil((start+total)/7)*7;
 const monthName=first.toLocaleDateString('pt-PT',{month:'long',year:'numeric'}).replace(/^./,c=>c.toUpperCase());
 let html=`<div class="month"><div class="monthbar"><h3 id="calendarMonthTitle">${monthName}</h3>`+
   `<div class="arrows"><button type="button" data-month-nav="prev" data-ui-action="previousMonth" aria-label="Mês anterior">‹</button>`+
   `<button type="button" data-month-nav="next" data-ui-action="nextMonth" aria-label="Mês seguinte">›</button></div></div>`+
   `<div class="calendar-grid" role="group" aria-labelledby="calendarMonthTitle" aria-describedby="calendarHelp">`;
 ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'].forEach(d=>html+=`<div class="day-head">${d}</div>`);
 for(let i=0;i<len;i++){
  const day=i-start+1,inMonth=day>=1&&day<=total;
  // O ISO é construído apenas para dias existentes; não produzir «2026-11--2».
  const iso=inMonth?`${y}-${String(m+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`:'';
  const entries=inMonth?(byDate.get(iso)||[]):[],picked=inMonth&&state.day===iso;
  const count=entries.length,description=`${calendarDateLabel(iso)}; ${count} caminhada${count===1?'':'s'}`;
  html+=`<div class="day-cell ${inMonth?'':'outside'} ${picked?'picked':''}">`;
  if(inMonth){
   html+=`<button type="button" class="day-number" data-cal-date="${iso}" data-ui-action="selectDay" data-day-value="${iso}" `+
     `aria-pressed="${picked}" title="${picked?'Retirar selecção':'Seleccionar dia'}: ${description}" `+
     `aria-label="${picked?'Dia seleccionado, ':'Seleccionar '}${description}">${day}</button>`;
   html+=entries.slice(0,2).map(x=>`<button type="button" title="${esc(x.title)}" `+
     `class="mini-event" data-ui-action="selectDay" data-day-value="${iso}" `+
     `aria-label="Ver caminhadas de ${esc(calendarDateLabel(iso))}: ${esc(x.title)}">${esc(x.title)}</button>`).join('');
   if(count>2)html+=`<button type="button" class="mini-more" data-ui-action="selectDay" data-day-value="${iso}" `+
     `aria-label="Ver mais ${count-2} caminhadas de ${esc(calendarDateLabel(iso))}">+${count-2} mais</button>`;
  }
  html+='</div>';
 }
 html+='</div><div id="calendarHelp" class="legend">Selecciona um dia para filtrar a Lista. No Calendário, os outros dias continuam visíveis. Teclado: setas para mudar de dia, Page Up/Down para mudar de mês.</div></div>';
 $('calendarView').innerHTML=html;
}
function shiftMonth(n){
 // Manter o foco na seta de navegação após reconstruir o calendário.
 const nav=document.activeElement?.getAttribute('data-month-nav');
 state.month+=n;
 if(state.month<0){state.month=11;state.year--}
 if(state.month>11){state.month=0;state.year++}
 render();
 if(nav&&state.view==='calendar')$('calendarView').querySelector(`[data-month-nav="${nav}"]`)?.focus({preventScroll:true});
}
function calendarFocusDate(iso){
 const date=new Date(iso+'T12:00:00');if(!Number.isFinite(date.getTime()))return;
 if(date.getMonth()!==state.month||date.getFullYear()!==state.year){
   state.month=date.getMonth();state.year=date.getFullYear();render();
 }
 $('calendarView').querySelector(`[data-cal-date="${iso}"]`)?.focus({preventScroll:true});
}
function calendarKeyboardNavigation(evt){
 const button=evt.target.closest?.('button.day-number[data-cal-date]');
 if(!button||!$('calendarView').contains(button))return;
 const moves={ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7};
 const base=new Date(button.dataset.calDate+'T12:00:00');
 let next=null;
 if(Object.hasOwn(moves,evt.key))base.setDate(base.getDate()+moves[evt.key]);
 else if(evt.key==='Home')base.setDate(base.getDate()-(base.getDay()+6)%7);
 else if(evt.key==='End')base.setDate(base.getDate()+6-(base.getDay()+6)%7);
 else if(evt.key==='PageUp'||evt.key==='PageDown'){
   const offset=evt.key==='PageUp'?-1:1;
   const target=new Date(base.getFullYear(),base.getMonth()+offset,1,12);
   const max=new Date(target.getFullYear(),target.getMonth()+1,0).getDate();
   target.setDate(Math.min(base.getDate(),max));
   next=target;
 }else return;
 evt.preventDefault();
 next??=base;
 calendarFocusDate(`${next.getFullYear()}-${String(next.getMonth()+1).padStart(2,'0')}-${String(next.getDate()).padStart(2,'0')}`);
}
$('calendarView').addEventListener('keydown',calendarKeyboardNavigation);
function clearSelectedDay(){state.day='all';render()}
function setDay(d){
 if(state.day===d){clearSelectedDay();return;}
  state.day=d;state.weekend='all';state.view='list';render();
 // Após seleccionar pelo teclado, não deixar o foco num botão removido do DOM.
 document.querySelector('[data-view="list"]')?.focus({preventScroll:true});
 document.querySelector('.results').scrollIntoView({behavior:'smooth',block:'start'});
}
function resetFilters(){Object.assign(state,{day:'all',weekend:'all',organizer:'all',kmMin:0,kmMax:KM_CAP,gainMin:0,gainMax:GAIN_CAP});$('organizer').value='all';render()}
function toast(msg){$('toast').textContent=msg;$('toast').hidden=false;clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>$('toast').hidden=true,3000)}
function saveBlob(blob,name){const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),3000)}
function removeEvent(id){if(!confirm('Eliminar este evento?'))return;const next=custom.filter(e=>e.id!==id);if(!persistValue('trilhario_custom_v1',next))return;custom=next;populateOrganizers();render();toast('Evento eliminado')}
document.querySelectorAll('[data-quick-km]').forEach(b=>b.addEventListener('click',()=>{
 const chosen=Number(b.dataset.quickKm);
 const active=state.kmMin===chosen&&state.kmMax===KM_CAP;
 state.kmMin=active?0:chosen;
 state.kmMax=KM_CAP;
 state.view='list';
 render();
}));
// v82 — acrescentar os próximos fins de semana sem ocupar mais altura.
const weekendStrip=document.querySelector('.v79-weekend-buttons');
if(weekendStrip){
 for(let week=3;week<12;week++){
  const button=document.createElement('button');
  button.type='button';
  button.dataset.quickWeekend='w'+week;
  button.setAttribute('aria-pressed','false');
  weekendStrip.appendChild(button);
 }
}
document.querySelectorAll('[data-quick-weekend]').forEach(b=>b.addEventListener('click',()=>{
 const chosen=b.dataset.quickWeekend;
 state.weekend=state.weekend===chosen?'all':chosen;
 state.day='all';state.view='list';render();
}));
// v83 — o mesmo controlo horizontal para quilómetros e fins de semana.
function initQuickFilterScroll(){
 for(const id of ['quickKmStrip','quickWeekendStrip']){
  const strip=$(id);if(!strip)continue;
  const holder=strip.closest('.v83-scroll-shell');
  const prev=holder.querySelector('.v83-arrow-prev'),next=holder.querySelector('.v83-arrow-next');
  const refresh=()=>{
   const max=Math.max(0,strip.scrollWidth-strip.clientWidth);
   prev.hidden=strip.scrollLeft<=2;
   next.hidden=strip.scrollLeft>=max-2;
  };
  strip.addEventListener('scroll',refresh,{passive:true});
  if(typeof ResizeObserver==='function')new ResizeObserver(refresh).observe(strip);
  else window.addEventListener('resize',refresh,{passive:true});
  [prev,next].forEach(button=>button.addEventListener('click',()=>{
   const first=strip.querySelector('button');
   const gap=parseFloat(getComputedStyle(strip).gap)||0;
   const step=(first?.getBoundingClientRect().width||strip.clientWidth/3)+gap;
   strip.scrollBy({left:Number(button.dataset.scrollDirection)*step*3,behavior:'smooth'});
  }));
  refresh();
 }
}
initQuickFilterScroll();

$('organizer').addEventListener('change',e=>{state.organizer=e.target.value;render()});
['km','gain'].forEach(prefix=>{
 $(prefix+'Min').addEventListener('input',e=>changeDual(prefix,'Min',e.target.value));
 $(prefix+'Max').addEventListener('input',e=>changeDual(prefix,'Max',e.target.value));
});
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{state.view=b.dataset.view;render()}));$('resetBtn').addEventListener('click',resetFilters);
$('filterToggleBtn').addEventListener('click',()=>{const panel=$('filterPanel');panel.hidden=!panel.hidden;$('filterToggleBtn').setAttribute('aria-expanded',String(!panel.hidden));});

// v22: pedidos progressivos, uma rota de cada vez, limitados ao bloco visível.
// OSM/Nominatim/OSRM são serviços experimentais sujeitos a limites de utilização.
function persistTravel(notify=false){
 // Guardar as preferências duradouras antes da cache, que pode exceder a quota.
 const prefs=persistValue(TRAVEL_PREF_KEY,travelPrefs,!notify);
 persistValue(TRAVEL_ROUTES_KEY,travelRoutes,true);
 return prefs;
}
function routeCacheKey(e){return String(travelPrefs.origin||'').trim().toLowerCase()+'|'+e.id;}
// v43: rotas e tarifas têm validades independentes. Não apresentar uma estimativa expirada como actual.
const ROUTE_MAX_AGE_MS=14*86400000,TOLL_MAX_AGE_MS=7*86400000,PRECALC_MAX_AGE_MS=90*86400000;
let precomputedRoutes=null;
const ROUTE_GEOMETRY_LIMIT=24,ROUTE_GEOMETRY_MAX_AGE=ROUTE_MAX_AGE_MS;
function routeFresh(e,r,now=Date.now()){
 return Boolean(r&&!r.manual&&r.roundTripVersion===ROUNDTRIP_VERSION&&r.geocoderVersion===GEOCODER_VERSION&&
 r.destinationFingerprint===endpointFingerprint(e)&&Number.isFinite(r.kmOne)&&Number.isFinite(r.kmBack)&&
 r.kmOne>=0&&r.kmBack>=0&&timeValid(r.updated,r.precomputed?PRECALC_MAX_AGE_MS:ROUTE_MAX_AGE_MS,now));
}
function tollFresh(r,now=Date.now()){
 return Boolean(r&&r.tollSource==='IP'&&Number.isFinite(r.tollOut)&&Number.isFinite(r.tollBack)&&
 timeValid(r.tollChecked,TOLL_MAX_AGE_MS,now));
}
function tollsDue(r,now=Date.now()){
 if(!r||r.tollSource==='manual'||tollFresh(r,now))return false;
 return now>=Math.max(Number(r.tollNextRetry||0),tollRetryAfter);
}
// Polyline5, compatível com as coordenadas [longitude, latitude] do OSRM.
// A geometria tem um limite de entradas e nunca é usada como fonte de GPS do evento.
function saveRouteGeometry(key,record,outPoints,backPoints){
 const out=encodeRouteGeometry(compactRouteGeometry(outPoints));
 const back=encodeRouteGeometry(compactRouteGeometry(backPoints));
 if(!out||!back||out.length+back.length>60000)return;
 travelTollGeometry[key]={out,back,routeShape:record.routeShapeFingerprint,backShape:record.backRouteShapeFingerprint,
  updated:record.updated,accessed:Date.now()};
 const entries=Object.entries(travelTollGeometry).filter(([,g])=>g&&timeValid(g.updated,ROUTE_GEOMETRY_MAX_AGE));
 entries.sort((a,b)=>(Number(b[1].accessed)||0)-(Number(a[1].accessed)||0));
 travelTollGeometry=Object.fromEntries(entries.slice(0,ROUTE_GEOMETRY_LIMIT));
 if(!persistValue(TRAVEL_TOLL_GEOMETRY_KEY,travelTollGeometry,true)){
  // Cache descartável: preservar a cópia em memória nesta visita mesmo sem armazenamento.
 }
}
function getRouteGeometry(key,record){
 const g=travelTollGeometry[key];
 if(!g||!record||g.updated!==record.updated||g.routeShape!==record.routeShapeFingerprint||
  g.backShape!==record.backRouteShapeFingerprint||!timeValid(g.updated,ROUTE_GEOMETRY_MAX_AGE))return null;
 const out=decodeRouteGeometry(g.out),back=decodeRouteGeometry(g.back);
 return out.length>=2&&back.length>=2?{out,back}:null;
}

// A cache pública guarda distâncias; o consumo continua definido no navegador.
function normalizeCapital(value){
 return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase()
   .replace(/,\s*portugal\s*$/,'').replace(/\s+/g,' ');
}
function precomputedTravel(e){
 if(!precomputedRoutes||!travelPrefs.origin||!e.verified||!hasCoords(e)||ambiguousDeparture(e))return null;
 const capital=normalizeCapital(travelPrefs.origin);
 if(!Object.prototype.hasOwnProperty.call(precomputedRoutes.origins||{},capital))return null;
 const key=Number(e.lat).toFixed(5)+','+Number(e.lon).toFixed(5);
 const row=precomputedRoutes.locations?.[key]?.routes?.[capital];
 if(!row||!Number.isFinite(row.km)||row.km<0||row.km>=1600||
    !Number.isFinite(row.minutes)||row.minutes<0||row.minutes>=10000)return null;
 const stamp=Date.parse(String(row.updated||'')+'T00:00:00Z');
 if(!timeValid(stamp,PRECALC_MAX_AGE_MS))return null;
 return {kmOne:row.km,kmBack:row.km,minutesOne:row.minutes,minutesBack:row.minutes,
  roundTripVersion:ROUNDTRIP_VERSION,geocoderVersion:GEOCODER_VERSION,
  destinationFingerprint:endpointFingerprint(e),precision:'capital',
  destinationLabel:'Percurso do centro de '+travelPrefs.origin,updated:stamp,precomputed:true};
}
function travelData(e){
 if(!travelPrefs.origin)return null;
 const local=travelRoutes[routeCacheKey(e)];
 if(local&&typeof local==='object'&&routeFresh(e,local))return local;
 return precomputedTravel(e)||(local&&typeof local==='object'?local:null);
}
async function loadPrecomputedRoutes(){
 if(location.protocol==='file:')return;
 try{
  const res=await fetch('rotas_precalculadas.json',{cache:'no-store'});
  if(!res.ok)return;
  const data=await res.json();
  if(data&&data.schema===1&&data.origins&&typeof data.origins==='object'&&
     data.locations&&typeof data.locations==='object'&&!Array.isArray(data.locations)){
   precomputedRoutes=data;
  }
 }catch(error){console.info('Cache partilhada indisponível; cálculo individual activo.',error?.message||error);}
}
function travelMoney(v){return Number.isFinite(v)?v.toLocaleString('pt-PT',{style:'currency',currency:'EUR'}):'—';}
function tripCalc(e){
 if(ambiguousDeparture(e))return null;
 const r=travelData(e);
 if(!routeFresh(e,r))return null;
 const km=Math.round((r.kmOne+r.kmBack)*10)/10;
 const fuel=km*(Number(travelPrefs.consumption)/100)*Number(travelPrefs.fuel);
 const minutes=Number.isFinite(r.minutesOne)&&Number.isFinite(r.minutesBack)?r.minutesOne+r.minutesBack:null;
 // Apenas apresentar portagens totais quando os dois sentidos foram confirmados.
 const toll=tollFresh(r)?Math.round((r.tollOut+r.tollBack)*100)/100:null;
 return {km,minutes,fuel,toll,total:toll==null?null:fuel+toll};
}
function timeStr(min){if(!Number.isFinite(min))return '—';const m=Math.round(min),h=Math.floor(m/60);return (h?h+'h ':'')+String(m%60).padStart(2,'0')+'min';}
function travelRow(e){
 const t=tripCalc(e),hasOrigin=!!travelPrefs.origin,route=travelData(e);
 const key=routeCacheKey(e),error=tripProblems.get(key);
 const unavailable=!departureCandidates(e).length;
 let body,action='';
 if(t){
  const approx=route?.precision&&route.precision!=='gps'?' (aprox.)':'';
  // A inscrição já figura nas métricas do trilho: não integra o total da viagem.
  // Identificar a viagem com um carro lateral, mantendo duas linhas compactas de custo.
  body=`<div class="v74-trip-summary" aria-label="Estimativa da viagem de ida e volta desde ${esc(travelPrefs.origin)}">
    <div class="v74-trip-line v74-trip-route">
     <span class="v74-trip-brand"><svg class="v66-trip-car" viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/></svg><strong>Viagem</strong></span>
     <span class="v74-trip-divider" aria-hidden="true">|</span>
     <strong>${fmtN(t.km)} km${approx}</strong>
     <span class="v74-trip-divider" aria-hidden="true">|</span>
     <strong>${timeStr(t.minutes)}</strong>
    </div>
    <div class="v74-trip-line v74-trip-prices">
     <span class="v74-trip-piece">Combustível <strong>${travelMoney(t.fuel)}</strong></span>
     <span class="v74-trip-divider" aria-hidden="true">|</span>
     <span class="v74-trip-piece">Portagens <strong>${t.toll==null?'—':travelMoney(t.toll)}</strong></span>
     <span class="v74-trip-divider" aria-hidden="true">|</span>
     <span class="v74-trip-piece v74-trip-total" ${t.total==null?'title="Total pendente da confirmação das portagens"':''}>Total <strong>${t.total==null?'—':travelMoney(t.total)}</strong> <small>(ida e volta)</small></span>
    </div>
   </div>`;
  if(t.toll==null&&route?.precomputed)action=`<button type="button" data-event-action="calculateOneRoute" data-event-id="${esc(e.id)}" title="Calcular também as portagens">Calcular portagens</button>`;
  else if(t.toll==null&&route?.tollStatus==='retry'&&tollsDue(route))action=`<button type="button" data-event-action="retryTolls" data-event-id="${esc(e.id)}">Repetir portagens</button>`;
 }else{
  const status=!hasOrigin?'Define a origem acima para calcular a deslocação.':
   unavailable?(ambiguousDeparture(e)?'Vários pontos de encontro ou travessia de barco · sem cálculo rodoviário.':'Local de partida por confirmar · sem cálculo.'):
   tripOriginProblem||error||'A calcular viagem…';
  body=`<div class="v53-trip-empty"><span class="v53-trip-empty-icon" aria-hidden="true">↗</span><span>${esc(status)}</span></div>`;
  if(hasOrigin&&!unavailable&&error&&!tripOriginProblem)action=`<button type="button" data-event-action="calculateOneRoute" data-event-id="${esc(e.id)}">Tentar novamente</button>`;
 }
 return `<div class="walk-trip-line v53-trip"><div class="walk-trip-info">${body}</div>${action?`<div class="walk-trip-ctrl">${action}</div>`:''}</div>`;
}
// Delegação: IDs vindos de catálogos externos nunca entram em código onclick.
// dataset devolve o ID literal, mesmo contendo aspas ou outros caracteres.
// Delegação para comandos de interface, incluindo elementos criados dinamicamente.
document.addEventListener('click',function(event){
 const button=event.target.closest('button[data-ui-action]');
 if(!button)return;
 switch(button.dataset.uiAction){
  case 'clearDay':clearSelectedDay();break;
  case 'closeMapPopup':geo.picked=null;paintMap();break;
  case 'resetFilters':resetFilters();break;
  case 'loadMore':loadMoreWalks();break;
  case 'previousMonth':shiftMonth(-1);break;
  case 'nextMonth':shiftMonth(1);break;
  case 'selectDay':if(/^\d{4}-\d{2}-\d{2}$/.test(button.dataset.dayValue||''))setDay(button.dataset.dayValue);break;
 }
});
document.addEventListener('click',function(event){
 const button=event.target.closest('button[data-event-action][data-event-id]');
 if(!button)return;
 const id=button.dataset.eventId;
 switch(button.dataset.eventAction){
  case 'removeEvent':removeEvent(id);break;
  case 'mapSelect':mapSelect(id);break;
  case 'calculateOneRoute':calculateOneRoute(id);break;
  case 'retryTolls':retryTolls(id);break;
  case 'openOriginSettings':openTravelPanel();break;
 }
});
function travelSortVal(e,sort){const t=tripCalc(e);return sort==='km'?t?.km:sort==='fuel'?t?.fuel:t?.total;}
function sortedWalks(xs){const s=$('travelSort')?.value||'date';if(s==='date')return xs;return xs.sort((a,b)=>{const av=travelSortVal(a,s),bv=travelSortVal(b,s);return av==null?bv==null?0:1:bv==null?-1:av-bv});}
let originEditing=false;
function editTripOrigin(){
 originEditing=true;updateTravelHeader();$('tripOrigin').focus();$('tripOrigin').select();
}
function openTravelPanel(){editTripOrigin();}
function cancelTripOrigin(){originEditing=false;updateTravelHeader();}
function cancelCarEditor(which){
 if(which==='consumption'||!which){$('consumptionForm').hidden=true;$('tripConsumptionEdit').hidden=false;}
 if(which==='fuel'||!which){$('fuelPriceForm').hidden=true;$('priceDisplay').hidden=false;}
}
function toggleTravelPanel(){
 const p=$('travelPanel');p.hidden=!p.hidden;
 $('travelToggle').setAttribute('aria-expanded',String(!p.hidden));
 if(p.hidden)cancelCarEditor();
}
function applyOrigin(event){
 if(event)event.preventDefault();
 const origin=$('tripOrigin').value.trim().replace(/\s+/g,' ');
 if(origin.length<2){toast('Indica uma localidade de partida válida.');$('tripOrigin').focus();return;}
 const changed=travelPrefs.origin.trim().toLocaleLowerCase('pt-PT')!==origin.toLocaleLowerCase('pt-PT');
 const previousOriginError=!!tripOriginProblem;
 travelPrefs={...travelPrefs,origin};
 originEditing=false;tripOriginProblem='';
 if(changed||previousOriginError){tripJobs=[];tripJobsSet.clear();tripFilterSignature='';}
 if(previousOriginError){
  geoMisses.clear();
  const prefix=origin.toLocaleLowerCase('pt-PT')+'|';
  for(const key of tripProblems.keys())if(key.startsWith(prefix))tripProblems.delete(key);
  for(const key of tripRetryAfter.keys())if(key.startsWith(prefix))tripRetryAfter.delete(key);
 }
 const saved=persistTravel(true);
 updateTravelHeader();render();renderTravelProgress();
 if(!saved)toast('Origem aplicada nesta sessão, mas não foi possível guardá-la no navegador.');
}
function saveCarPreference(changes){
 travelPrefs={...travelPrefs,...changes};
 const saved=persistTravel(true);
 updateTravelHeader();render();renderTravelProgress();
 if(!saved)toast('Alteração aplicada nesta sessão, mas não foi possível guardá-la no navegador.');
}
function applyConsumption(event){
 event.preventDefault();
 const consumption=Number($('tripConsumption').value);
 if(!Number.isFinite(consumption)||consumption<1||consumption>35){
  toast('Indica um consumo entre 1 e 35 L/100 km.');$('tripConsumption').focus();return;
 }
 cancelCarEditor('consumption');saveCarPreference({consumption});
}
function applyFuelPrice(event){
 event.preventDefault();
 const fuel=Number($('tripFuel').value);
 if(!Number.isFinite(fuel)||fuel<=0.1||fuel>=5){
  toast('Indica um preço entre 0,10 e 5 €/L.');$('tripFuel').focus();return;
 }
 cancelCarEditor('fuel');saveCarPreference({fuelOverride:fuel,fuel});
}
function editConsumption(){
 cancelCarEditor('fuel');
 $('tripConsumption').value=String(travelPrefs.consumption);
 $('tripConsumptionEdit').hidden=true;$('consumptionForm').hidden=false;
 $('tripConsumption').focus();$('tripConsumption').select();
}
function editFuelPrice(){
 cancelCarEditor('consumption');
 $('tripFuel').value=Number(travelPrefs.fuelOverride??currentFuelPrice(travelPrefs.kind)?.value??travelPrefs.fuel).toFixed(3);
 $('priceDisplay').hidden=true;$('fuelPriceForm').hidden=false;
 $('tripFuel').focus();$('tripFuel').select();
}
function changeFuelKind(){
 const kind=$('tripFuelKind').value;
 const fuel=currentFuelPrice(kind)?.value;
 if(!(Number.isFinite(fuel)&&fuel>0)){toast('Preço médio indisponível.');$('tripFuelKind').value=travelPrefs.kind;return;}
 cancelCarEditor();
 saveCarPreference({kind,fuelOverride:null,fuel});
}
function resetFuelPrice(){
 const fuel=currentFuelPrice(travelPrefs.kind)?.value;
 if(!(Number.isFinite(fuel)&&fuel>0)){toast('Preço médio indisponível.');return;}
 cancelCarEditor('fuel');saveCarPreference({fuelOverride:null,fuel});
}
function prettyFuelDate(date){const m=String(date||'').match(/^(\d{4})-(\d{2})-(\d{2})/);return m?(m[3]+'/'+m[2]+'/'+m[1]):String(date||'—');}
function updateTravelHeader(){
 const hasOrigin=!!String(travelPrefs.origin||'').trim(),showForm=!hasOrigin||originEditing;
 $('originEditor').hidden=!showForm;
 $('originCurrent').textContent=hasOrigin?travelPrefs.origin:'Definir partida';
 $('originCancel').hidden=!hasOrigin;
 if(!originEditing)$('tripOrigin').value=travelPrefs.origin||'';
 $('travelSub').textContent=fmtN(travelPrefs.consumption)+' L/100 km';
 $('tripConsumptionValue').textContent=fmtN(travelPrefs.consumption)+' L/100 km';
 $('tripFuelKind').value=travelPrefs.kind;
 updateFuelInput();
}
function currentFuelPrice(kind){return fuelPrices[kind]||FUEL_OFFICIAL_REFERENCE[kind]||null;}
function updateFuelInput(){
 const rec=currentFuelPrice(travelPrefs.kind);
 const manual=travelPrefs.fuelOverride!=null;
 const price=manual?Number(travelPrefs.fuelOverride):rec?.value;
 $('tripPriceLabel').textContent=manual?'Preço personalizado':'Preço médio';
 $('tripFuelValue').textContent=Number.isFinite(price)?Number(price).toLocaleString('pt-PT',{minimumFractionDigits:3,maximumFractionDigits:3})+' €/L':'— €/L';
 $('tripFuelReset').hidden=!manual;
 if($('fuelPriceForm').hidden&&Number.isFinite(price))$('tripFuel').value=Number(price).toFixed(3);
 $('fuelPriceStatus').textContent=rec
  ?'Média DGEG de '+prettyFuelDate(rec.date)+': '+Number(rec.value).toLocaleString('pt-PT',{minimumFractionDigits:3,maximumFractionDigits:3})+' €/L.'+(manual?' Estás a utilizar um preço personalizado.':'')
  :'Preço médio indisponível. Podes introduzir um valor personalizado.';
}
function parseDgegPrice(s){const n=Number(String(s??'').replace(/[€\s]/g,'').replace(',','.'));return Number.isFinite(n)&&n>0.3&&n<5?n:null;}
function normalizeFuelDay(s){const text=String(s||'');const iso=text.match(/(\d{4})-(\d{2})-(\d{2})/);if(iso)return `${iso[1]}-${iso[2]}-${iso[3]}`;const pt=text.match(/(\d{2})[\/-](\d{2})[\/-](\d{4})/);return pt?`${pt[3]}-${pt[2]}-${pt[1]}`:null;}
async function fetchFuelMedian(kind){const id=FUEL_IDS[kind];if(!id)return null;
 const now=new Date(),past=new Date(now.getTime()-20*86400000),fmt=d=>[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');
 const url=`https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/PMD?idsTiposComb=${id}&dataIni=${fmt(past)}&dataFim=${fmt(now)}&qtdPorPagina=1&pagina=1&orderDesc=1`;
 const resp=await fetch(url,{headers:{Accept:'application/json'},signal:AbortSignal.timeout?AbortSignal.timeout(11000):undefined});
 if(!resp.ok)throw new Error('DGEG HTTP '+resp.status);
 const j=await resp.json();if(j.status===false||!Array.isArray(j.resultado))throw new Error('DGEG: resposta inválida');
 const found=j.resultado.map(x=>({value:parseDgegPrice(x.PrecoMedio),date:normalizeFuelDay(x.Data),source:'DGEG'})).filter(x=>x.value!=null&&x.date&&x.date<=fmt(now)).sort((a,b)=>b.date.localeCompare(a.date));
 return found[0]||null;}
async function refreshFuelPrices(){const results=await Promise.allSettled(['gasoleo','gasolina'].map(fetchFuelMedian));let updated=false;
 for(let i=0;i<2;i++){const kind=['gasoleo','gasolina'][i],item=results[i];if(item.status!=='fulfilled'||!item.value)continue;
 const fresh=item.value;const prev=currentFuelPrice(kind);
 if(!prev||fresh.date>=prev.date){fuelPrices[kind]=fresh;updated=true;}}
 if(updated){persistValue(FUEL_CACHE_KEY,fuelPrices,true);
   if(travelPrefs.fuelOverride==null){travelPrefs.fuel=currentFuelPrice(travelPrefs.kind).value;persistTravel();updateTravelHeader();render();}}
 if($('tripFuelKind'))updateFuelInput();
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function gapThrottle(type){const key=type==='geo'?'geoLastRequest':'roadLastRequest';const now=Date.now(),last=type==='geo'?geoLastRequest:roadLastRequest;const gap=Math.max(0,1200-(now-last));if(gap)await sleep(gap);if(type==='geo')geoLastRequest=Date.now();else roadLastRequest=Date.now();}
// A localização automática usa uma pesquisa pontual, cache local e pedidos sequenciais.
// O Nominatim público é limitado (até 1 pedido/s por aplicação); não fazer varrimentos.
// Photon é uma alternativa para nomes de locais/POI quando a primeira pesquisa falha.
let photonCooldownUntil=0,nominatimCooldownUntil=0;
const GEO_CACHE_MAX_AGE=30*24*60*60*1000, GEO_MISS_MAX_AGE=6*60*60*1000,GEO_TIMEOUT_MS=7500;
// Continente, Açores e Madeira. Uma localização numa ilha não garante rota rodoviária desde o continente.
const pointInPortugal=p=>hasCoords(p)&&(
 (p.lat>=36.6&&p.lat<=42.3&&p.lon>=-9.8&&p.lon<=-6.0)||
 (p.lat>=36.8&&p.lat<=39.9&&p.lon>=-31.6&&p.lon<=-24.3)||
 (p.lat>=32.3&&p.lat<=33.3&&p.lon>=-17.7&&p.lon<=-16.0));
async function fetchTimedJson(url,options={},ms=GEO_TIMEOUT_MS){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),ms);
 try{
  const response=await fetch(url,{...options,signal:controller.signal});
  // Manter o timeout enquanto se descarrega e interpreta o corpo JSON.
  const data=response.ok?await response.json():null;
  return {response,data};
 }finally{clearTimeout(timer)}
}
const GEO_STOPWORDS=new Set(['portugal','posto','turismo','parque','estacionamento','junto','centro','municipal','igreja','estrada','local','partida','aldeia','freguesia','praca','largo','avenida','rua','cafe','estacao','rodoviaria','frente','lado','sobre','perto','edificio','nacional','castelo','santuario','travessa','mercado','de','do','da','dos','das','em','no','na','um','uma']);
function geoTokens(text){return [...new Set(fold(String(text||'')).split(/[^a-z0-9]+/).filter(w=>w.length>=3&&!GEO_STOPWORDS.has(w)&&!/^[0-9]+$/.test(w)))];}
// Não aceitar "Café Central, Faro" para uma pesquisa por "Café Central, Braga".
function matchesGeographicalQuery(query,description){
 const tokens=geoTokens(String(query).replace(/,?\s*Portugal\s*$/i,''));
 if(!tokens.length)return false;
 const descriptionTokens=new Set(geoTokens(description));
 const matches=tokens.filter(w=>descriptionTokens.has(w));
 const needed=tokens.length<=2?tokens.length:Math.max(2,Math.ceil(tokens.length*.65));
 if(matches.length<needed)return false;
 const parts=String(query).replace(/,?\s*Portugal\s*$/i,'').split(',').map(x=>x.trim()).filter(Boolean);
 // O contexto administrativo depois da primeira vírgula nunca pode contradizer o resultado.
 if(parts.length>1){const admin=geoTokens(parts.slice(1).join(' '));if(admin.length&&!admin.every(w=>descriptionTokens.has(w)))return false;}
 return true;
}
function saveGeocode(key,p,provider,label){
 const record={lat:p.lat,lon:p.lon,provider,label,checkedAt:Date.now()};
 travelGeocodes[key]=record;
 persistValue(TRAVEL_GEO_KEY,travelGeocodes,true);
 return record;
}
async function geocodeText(text){
 const key=String(text||'').trim().toLocaleLowerCase('pt-PT');
 if(!key)return null;
 const miss=geoMisses.get(key);if(miss&&Date.now()-miss<GEO_MISS_MAX_AGE)return null;
 if(miss)geoMisses.delete(key);
 const cached=travelGeocodes[key];
 // A cache legada não guardava proveniência, correspondência nem prazo de validade: revalidar.
 if(cached&&pointInPortugal(cached)&&cached.provider&&cached.checkedAt&&
     Date.now()-cached.checkedAt<GEO_CACHE_MAX_AGE&&matchesGeographicalQuery(text,cached.label||''))return cached;
 if(Date.now()<photonCooldownUntil&&Date.now()<nominatimCooldownUntil)
  throw new Error('Serviços de localização temporariamente limitados. Tenta novamente mais tarde.');
 let photonResolved=false,nominatimResolved=false;
 if(Date.now()>=photonCooldownUntil){
  try{
   await gapThrottle('geo');
   const u='https://photon.komoot.io/api/?limit=6&q='+encodeURIComponent(text);
   const {response:r,data:j}=await fetchTimedJson(u,{headers:{Accept:'application/json'}});
   if(r.status===429||r.status===403){photonCooldownUntil=Date.now()+120000;}
   else if(!r.ok){photonCooldownUntil=Date.now()+30000;}
   else{
    photonResolved=true;
    for(const f of (j?.features||[]).slice(0,6)){
     if(String(f?.properties?.countrycode||'').toUpperCase()!=='PT')continue;
     const xy=f?.geometry?.coordinates;if(!Array.isArray(xy)||xy.length!==2)continue;
     const p={lat:Number(xy[1]),lon:Number(xy[0])};if(!pointInPortugal(p))continue;
     const label=[f.properties.name,f.properties.city,f.properties.county,f.properties.district,f.properties.state].filter(Boolean).join(', ');
     if(matchesGeographicalQuery(text,label))return saveGeocode(key,p,'Photon',label);
    }
   }
  }catch(err){photonCooldownUntil=Date.now()+30000;console.info('Photon indisponível:',err?.message||err)}
 }
 if(Date.now()>=nominatimCooldownUntil){
  try{
   await gapThrottle('geo');
   const u='https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=5&countrycodes=pt&q='+encodeURIComponent(text);
   const {response:r,data:j}=await fetchTimedJson(u,{headers:{Accept:'application/json'}});
   if(r.status===429||r.status===403){nominatimCooldownUntil=Date.now()+120000;}
   else if(!r.ok){nominatimCooldownUntil=Date.now()+30000;}
   else{
    nominatimResolved=true;
    for(const item of (Array.isArray(j)?j:[])){
     if(item.address?.country_code&&item.address.country_code!=='pt')continue;
     const p={lat:Number(item.lat),lon:Number(item.lon)};
     if(!pointInPortugal(p))continue;
     const label=String(item.display_name||'');
     if(matchesGeographicalQuery(text,label))return saveGeocode(key,p,'Nominatim',label);
    }
   }
  }catch(err){nominatimCooldownUntil=Date.now()+30000;console.info('Nominatim indisponível:',err?.message||err)}
 }
 if(!photonResolved||!nominatimResolved)throw new Error('Localização não confirmada: um dos fornecedores está indisponível. Tenta novamente mais tarde.');
 geoMisses.set(key,Date.now());
 if(geoMisses.size>250)geoMisses.delete(geoMisses.keys().next().value); // Sem correspondência por até 6 h.
 return null;
}
// Remover notas logísticas, mas conservar a localidade real anunciada.
function cleanLocationHint(s){
 return localPartidaLegivel(s)
  .replace(/\s*\([^)]*\b(?:a confirmar|local exacto|ponto exacto)\b[^)]*\)/gi,'')
  .replace(/\s+/g,' ').replace(/[\s.\-–—,;]+$/,'').trim();
}
function isUsablePlace(s){
 const value=cleanLocationHint(s);
 return value.length>=3&&value.length<=135&&!/^(?:por confirmar|a confirmar|desconhecido|local a definir|por definir|não definido)$/i.test(value)
  &&!/^\d{1,2}h\d{0,2}\s/i.test(value);
}
// v31: extrair localidades administrativas explícitas do texto do organizador.
// Os resultados sem GPS são aproximações; não tratar como ponto exacto de partida.
const LOCALIDADES_31=[
 'Pedrógão Pequeno','Portela de Sintra','Malveira da Serra','Paredes de Coura',
 'Vila Nova de Gaia','Cabeceiras de Basto','Castanheira de Pera','Terras de Bouro',
 'Porto de Mós','São Pedro do Sul','Pedrógão Grande','Castro Laboreiro',
 'Alcabideche','Alcanadas','Manteigas','Palmela','Óbidos',
 'Batalha','Mafra','Sintra','Ourém','Lousã','Regoufe','Valdigem',
 'Mendiga','Montalegre','Alvações do Corgo','Cascais','Coentral',
 'Leonte','Fafe','Góis','Arouca','Matosinhos','Tomar','Lamego',
 'Braga','Melgaço','Almada','Lisboa','Seia','Loriga','Pombal','Valongo',
 'Fundão','Castelo Branco','Aveiro','Mafomedes','Bezerra',
 'Colares','Alenquer','Santarém','Trafaria'
];
function localityHints31(e,start,town){
 const hints=[],seen=new Set();
 const push=(name)=>{const k=fold(name);if(name&&!seen.has(k)){seen.add(k);hints.push(name)}};
 const full=fold([start,town].filter(Boolean).join(' '));
 const titled=fold(e.title||'');
 // POI publicados com referência municipal inequívoca.
 if(/rio da mula/.test(full))push('Barragem do Rio da Mula, Alcabideche');
 if(/monserrate/.test(full))push('Monserrate, Sintra');
 if(/peninha/.test(full))push('Peninha, Sintra');
 if(/palacio nacional de sintra/.test(full))push('Palácio Nacional de Sintra');
 if(/portela de sintra/.test(full))push('Portela de Sintra');
 if(/terreiro das bruxas/.test(full))push('Lousã');
 if(/alcanadas/.test(full))push('Alcanadas, Batalha');
 if(/valdigem/.test(full))push('Valdigem, Lamego');
 if(/malveira da serra/.test(full))push('Malveira da Serra, Cascais');
 if(/cova[oã] da ametade/.test(full))push('Covão da Ametade, Manteigas');
 const concelho=start.match(/\bconcelho\s+d[aeo]s?\s+([^,.;()]{3,45})/i);
 if(concelho)push(concelho[1].trim());
 const escaped=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 // Preferir lugares com mais palavras, evitando confundir 'Sintra' com 'Portela de Sintra'.
 for(const place of LOCALIDADES_31){
  const rx=new RegExp('(^|[^a-z0-9])'+escaped(fold(place))+'($|[^a-z0-9])');
  if(rx.test(full))push(place);
 }
 // Fallback de último recurso: município mencionado no título, nunca inferir a partir de 'floresta' ou 'serra'.
 if(!hints.length){
  for(const place of LOCALIDADES_31){
   if(place.length<5)continue;
   const rx=new RegExp('(^|[^a-z0-9])'+escaped(fold(place))+'($|[^a-z0-9])');
   if(rx.test(titled)){push(place);break;}
  }
 }
 return hints.slice(0,3);
}
// Começar pelo ponto anunciado; se for demasiado detalhado, recuar para aldeia/localidade/concelho.
// Nunca assumir que o nome do trilho é o local de partida.
// Com barco ou múltiplos pontos de encontro, não inferir um destino rodoviário.
// Exemplo: Trafaria, com encontro na Estação Fluvial de Belém e travessia de barco.
function ambiguousDeparture(e){
 const description=[e.start,e.start_raw,e.description].filter(Boolean).join(' ');
 const ferry=/\b(barco|ferry|transtejo|travessia\s+fluvial|estação\s+fluvial)\b/i.test(description);
 const multiple=/\b(segundo\s+ponto|ponto\s+de\s+encontro\s*(?:2|ii|dois)|dois\s+pontos\s+de\s+encontro|outro\s+ponto\s+de\s+encontro|vários\s+pontos\s+de\s+encontro)\b/i.test(description);
 const titleFerry=/\btrafaria\b/i.test(String(e.title||''))&&ferry;
 return Boolean((ferry&&multiple)||titleFerry);
}
function departureCandidates(e){
 if(ambiguousDeparture(e))return [];
 if(e.verified&&hasCoords(e))return [{coords:{lat:Number(e.lat),lon:Number(e.lon)},precision:'gps',label:'GPS do organizador'}];
 const start=cleanLocationHint(displayDeparture(e)),town=cleanLocationHint(e.town);
 const candidates=[],seen=new Set();
 const add=(place,precision='localidade')=>{
  let p=cleanLocationHint(place);
  if(!isUsablePlace(p))return;
  p=p.replace(/\s*,?\s*Portugal\s*$/i,'').trim();
  const key=fold(p).replace(/[^a-z0-9]/g,'');if(!key||seen.has(key))return;
  seen.add(key);candidates.push({query:p+', Portugal',precision,label:p});
 };
 const context=(()=>{
  const info=fold([e.title,e.url].join(' '));
  if(info.includes('cabeceiras-de-basto')||info.includes('cabeceiras de basto'))return 'Cabeceiras de Basto';
  if(info.includes('vale-de-cambra')||info.includes('vale de cambra'))return 'Vale de Cambra';
  if(info.includes('sintra'))return 'Sintra';
  if(info.includes('lisboa'))return 'Lisboa';
  if(info.includes('tomar'))return 'Tomar';
  if(info.includes('arouca'))return 'Arouca';
  if(info.includes('almada')||info.includes('mata-dos-medos'))return 'Almada';
  return '';
 })();
 if(isUsablePlace(start)){
  // Um texto que só contém horários e uma referência vaga não permite geocodificação segura.
  if(/^Hor[aá]rio\s+IN[IÍ]CIO\b/i.test(start)&&!isUsablePlace(town))return [];
  // Agregadores por vezes só publicam município e distrito, não um GPS de início.
  // Tentar a localidade administrativa primeiro, claramente marcada como aproximada.
  const aggregatorHost=(()=>{try{return new URL(e.url||'').hostname.replace(/^www\./,'')}catch{return ''}})();
  if(aggregatorHost==='trilhosecaminhadas.pt'){
   const municipality=start.split(',').map(p=>p.trim()).filter(Boolean);
   if(municipality.length>=2&&municipality[0].length>=3&&municipality[0].length<45){
    add(municipality.slice(0,2).join(', '),'localidade');
    add(municipality[0],'localidade');
   }else if(municipality.length===1&&municipality[0].length<55){add(municipality[0],'localidade');}
  }
  // Lugares evidentes no texto têm prioridade sobre fragmentos de morada longos.
  const locationHints=localityHints31(e,start,town);
  // Tentar o ponto anunciado quando é curto e minimamente pesquisável.
  if(start.length<=90&&!/\b(?:que desce|ponto de encontro|Hora|final|contacto)\b/i.test(start))add(start,'descricao');
  for(const hint of locationHints)add(hint,'localidade');
  // 1.º experimentar a localidade explícita, em vez de endereços narrativos enormes.
  const village=start.match(/\b(?:aldeia|localidade|vila|freguesia|povoação)\s+d[aeo]s?\s+([^,.;()]+)/i);
  if(village){add(village[1]+(context?', '+context:''),'localidade');add(village[1]);}
  const postal=start.match(/\b\d{4}-\d{3}\s+([^,.;()]{3,55})/);
  if(postal)add(postal[1],'localidade');
  // Alguns pontos de encontro são instalações conhecidas, não ruas numeradas.
  if(/\bpeninha\b/i.test(start)){add('Santuário da Peninha, Sintra');add('Peninha, Sintra');}
  if(/Malveira da Serra/i.test(start))add('Malveira da Serra, Cascais','localidade');
  if(/Nossa Senhora das Neves/i.test(start)&&/Fafe/i.test(start))add('Santuário Nossa Senhora das Neves, Fafe','descricao');
  if(/Covão da Ametade/i.test(start))add('Covão da Ametade, Manteigas','descricao');
  if(/Pousadas Vedras/i.test(start))add('Pousadas Vedras, Redinha, Pombal','localidade');
  if(/Fraguinha/i.test(start))add('Retiro da Fraguinha, Candal, São Pedro do Sul','localidade');
  if(/Covas de Ferro/i.test(start))add('Covas de Ferro, Almargem do Bispo, Sintra','localidade');
  const railway=start.match(/\b(?:estação(?:\s+de\s+(?:comboio|comboios))?\s+de)\s+([A-Za-zÀ-ÿ ]{4,65})/i);
  if(railway){let place=railway[1].split(/\bCoordenadas\b/i)[0].trim();add('Estação ferroviária de '+place);add(place);}
  const parish=start.match(/\b(?:Igreja Paroquial|Igreja Matriz)\s+de\s+([A-Za-zÀ-ÿ]{3,40})/i);
  if(parish)add(parish[1]+(context?', '+context:''));
  if(/\b(?:Praça do Comércio|Terreiro do Paço)\b/i.test(start))add('Praça do Comércio, Lisboa');
  // Ex.: "Na Godigana ...", "No café da Ilda ... em Regoufe".
  const prep=start.match(/\b(?:na|no|em)\s+(?:aldeia\s+de\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç-]+(?:\s+d[aeo]s?\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç-]+)?)/);
  if(prep&&prep[1].length>=4&&!/^(?:parque|igreja|centro|restaurante|café|estação|localidade)$/i.test(prep[1]))add(prep[1]+(context?', '+context:''));
  // 2.º tentar o nome anunciado quando é uma morada curta; descartar notas logísticas.
  const parts=start.split(',').map(v=>v.trim()).filter(Boolean);
  if(start.length<=85&&!/\b(?:junto|frente|perto|em frente|que desce|hora|ponto de encontro)\b/i.test(start))add(start,'descricao');
  if(parts.length>=2){
    const valid=parts.filter(v=>v.length<53&&!/^(?:junto|frente|perto|ao lado|ponto de encontro|barco|hora)/i.test(v));
    if(valid.length>1)add(valid.slice(-2).join(', '),'localidade');
    if(valid.length)add(valid.at(-1)+((context&&!fold(valid.at(-1)).includes(fold(context)))?', '+context:''),'localidade');
  }
  // 3.º recuar para a localidade identificável; não usar apenas "parque" ou "estrada".
  if(isUsablePlace(town)&&!isPlacePlaceholder(town)&&!fold(town).includes('parque de merendas'))add(town,'localidade');
  // Algumas páginas apresentam um ponto descritivo e nenhuma localidade estruturada.
  if(/\bMata dos Medos\b/i.test(e.title||''))add('Mata dos Medos, Almada','zona');
  if(!candidates.length&&start.length<=115)add(start,'descricao');
 }
 if(!candidates.length&&isUsablePlace(start)){
  for(const hint of localityHints31(e,start,town))add(hint,'localidade');
 }
 if(isUsablePlace(town)&&!isPlacePlaceholder(town)&&town!==start&&town.length<65)add(town,'localidade');
 if(hasCoords(e))candidates.push({coords:{lat:Number(e.lat),lon:Number(e.lon)},precision:'aproximado',label:'ponto de referência'});
 return candidates.filter(x=>!x.coords).slice(0,4).concat(candidates.filter(x=>x.coords).slice(0,1)); // Poucas tentativas, preservando GPS se houver.
}
function endpointFingerprint(e){const refined=/Pousadas Vedras|Fraguinha|Covas de Ferro|Mendiga|Malveira da Serra|Santuário Nossa Senhora das Neves|Covão da Ametade|Ver\s+no\s+Google\s+Maps/i.test(String(e.start||''))?'geo-refinado-v30':'';return [e.start||'',e.town||'',e.lat??'',e.lon??'',!!e.verified,refined].join('|');}
async function locateEndpoint(e){
 const candidates=departureCandidates(e),failed=[];
 for(const item of candidates){
  if(item.coords)return {...item.coords,precision:item.precision,label:item.label};
  try{
   const p=await geocodeText(item.query);
   if(p)return {...p,precision:item.precision,label:item.label};
  }catch(err){failed.push(err?.message||'Serviço de geocodificação indisponível');}
 }
 if(failed.length)throw new Error(failed[0]);
 return null;
}
async function roadRoute(p,q){
 await gapThrottle('road');
 const u=`https://router.project-osrm.org/route/v1/driving/${p.lon},${p.lat};${q.lon},${q.lat}?overview=full&geometries=geojson&steps=false`;
 const {response:r,data:j}=await fetchTimedJson(u,{},12000);
 if(!r.ok)throw new Error('Serviço de rotas indisponível');if(j.code!=='Ok'||!j.routes?.[0])throw new Error('Sem rota rodoviária');
 // O OSRM pode ajustar um ponto remoto a uma estrada muitos quilómetros distante.
 const snap=Number(j.waypoints?.[1]?.distance);
 if(Number.isFinite(snap)&&snap>2500)throw new Error('Ponto de partida a mais de 2,5 km da estrada calculada. Confirma a localização.');
 const route=j.routes[0];
 return {kmOne:Math.round(route.distance/100)/10,minutesOne:Math.round(route.duration/60),geometry:Array.isArray(route.geometry?.coordinates)?route.geometry.coordinates:[]};
}
// A IP recebe o percurso real e devolve portagem para Classe 1, só ida.
// Usamos uma função do próprio Netlify para não depender de CORS no navegador.
const TOLL_RETRY_MS=3*60*1000,TOLL_UNKNOWN_MS=12*60*60*1000;
let tollRetryAfter=0,tollRequestSerial=0;
// Erros de rede são temporários; ausência de estimativa não é uma portagem de zero euros.
async function autoTollsForGeometry(geometry){
 if(!Array.isArray(geometry)||geometry.length<2)return {status:'unknown'};
 if(Date.now()<tollRetryAfter)return {status:'retry'};
 try{
  const {response,data:result}=await fetchTimedJson('/.netlify/functions/portagens',{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({coordinates:geometry})
  },17000);
  if(!response.ok){
   if(response.status===404)tollRetryAfter=Date.now()+30*60*1000;
   else tollRetryAfter=Date.now()+TOLL_RETRY_MS;
   return {status:'retry'};
  }
  if(result?.source==='IP'&&result?.class===1&&Number.isFinite(result.oneWay)&&result.oneWay>=0)
   return {status:'ok',amount:Math.round(result.oneWay*100)/100}; // Um sentido de cada vez; somar apenas após ambos confirmados.
  return {status:'unknown'};
 }catch(error){
  tollRetryAfter=Date.now()+TOLL_RETRY_MS;
  console.info('Portagens temporariamente indisponíveis:',error?.message||error);
  return {status:'retry'};
 }
}
// Primeiras 10 caminhadas ao definir a origem; mais 10 quando se aproximam do ecrã.
function scheduleTravelBatches(events){
 if(ORGANIZERS_PAGE_MODE||state.view!=='list'||!travelPrefs.origin)return;
 const signature=travelPrefs.origin.trim().toLowerCase()+'|'+events.map(e=>e.id).join(',');
 if(signature!==tripFilterSignature){
  tripFilterSignature=signature;
  // Filtragem nova tem prioridade sobre cálculos automáticos do filtro anterior.
  tripJobs=tripJobs.filter(job=>job.manual);
  tripJobsSet=new Set(tripJobs.map(job=>job.key));
 }
 queueTrips(events.slice(0,TRAVEL_BATCH_SIZE),false);
 if(tripBatchObserver)tripBatchObserver.disconnect();
 if(typeof IntersectionObserver!=='function')return;
 tripBatchObserver=new IntersectionObserver(entries=>{
  for(const entry of entries){if(!entry.isIntersecting)continue;
   const batch=Number(entry.target.dataset.travelBatch);
   if(!Number.isInteger(batch)||batch<1)continue;
   tripBatchObserver.unobserve(entry.target);
   // Carrega apenas os 10 resultados seguintes ao bloco que entrou na proximidade do ecrã.
   queueTrips(events.slice(batch*TRAVEL_BATCH_SIZE,(batch+1)*TRAVEL_BATCH_SIZE),false);
  }
 },{root:null,rootMargin:'300px 0px',threshold:0});
 const cards=$('listView').querySelectorAll('.walk-row');
 for(let index=TRAVEL_BATCH_SIZE;index<cards.length;index+=TRAVEL_BATCH_SIZE){
  const card=cards[index];card.dataset.travelBatch=String(index/TRAVEL_BATCH_SIZE);
  tripBatchObserver.observe(card);
 }
}
function tripNeedsRoute(e,force=false){
 const r=travelData(e),key=routeCacheKey(e);
 if(tripRetryAfter.has(key)&&Date.now()>=tripRetryAfter.get(key)){tripRetryAfter.delete(key);tripProblems.delete(key);}
 if(force||!routeFresh(e,r))return !tripProblems.has(key)||force;
 // A rota pré-calculada oferece distância e combustível instantâneos; portagens são opcionais.
 if(r?.precomputed)return false;
 return tollsDue(r)&&!getRouteGeometry(key,r)&&!tripProblems.has(key);
}
function scheduleCachedTolls(e,r,geometry){
 const key=routeCacheKey(e);
 if(!r||!geometry||!tollsDue(r)||r.tollRequestId)return false;
 const now=Date.now();
 // Tarifa expirada: nenhum dos sentidos pode ser reutilizado como preço actual.
 if(!tollFresh(r)&&r.tollChecked){
  for(const f of ['tollOut','tollBack','tollReturn','tollChecked','tollSource'])delete r[f];
 }
 r.tollNextRetry=now+TOLL_RETRY_MS;
 r.tollRequestId=++tollRequestSerial;
 tollJobs.push({key,id:e.id,outGeometry:geometry.out,backGeometry:geometry.back,requestId:r.tollRequestId});
 persistTravel();runTollQueue();return true;
}
function queueTrips(events,manual=false){
 if(!travelPrefs.origin||tripOriginProblem&&!manual)return;
 const accepted=[];
 for(const e of events){
  if(!e)continue;
  const key=routeCacheKey(e),r=travelData(e);
  if(routeFresh(e,r)&&tollsDue(r)){
   const geometry=getRouteGeometry(key,r);
   if(geometry){scheduleCachedTolls(e,r,geometry);refreshTravelCard(e.id);continue;}
  }
  if(!tripNeedsRoute(e,manual))continue;
  if(!departureCandidates(e).length){if(manual)tripProblems.set(routeCacheKey(e),'Não foi possível localizar o ponto de partida.');continue;}
  if(manual)tripProblems.delete(key);
  if(tripActiveKey===key)continue;
  if(tripJobsSet.has(key)){
   if(manual){const job=tripJobs.find(j=>j.key===key);if(job){tripJobs=tripJobs.filter(j=>j.key!==key);job.manual=true;accepted.push(job);}}
   continue;
  }
  const job={id:e.id,key,origin:travelPrefs.origin,manual};
  tripJobsSet.add(key);accepted.push(job);
 }
 if(manual)tripJobs.unshift(...accepted);else tripJobs.push(...accepted);
 if(accepted.length)requestAnimationFrame(()=>{renderTravelProgress();processTripQueue();});
}
// v38 — actualização incremental: a geocodificação e portagens nunca precisam de
// reconstruir a lista completa quando a ordenação continua por data.
function refreshTravelCard(id){
 if(ORGANIZERS_PAGE_MODE){renderTravelProgress();return;}
 if(state.view!=='list'){renderTravelProgress();return;}
 // Nos modos ordenados por distância/custo, o resultado altera a ordem dos cartões.
 if(($('travelSort')?.value||'date')!=='date'){render();renderTravelProgress();return;}
 const nodes=$('listView').querySelectorAll('.walk-row[data-eid]');
 if(!nodes.length){renderTravelProgress();return;}
 const catalogue=allEvents();
 const visible=id?new Set([String(id)]):null;
 const matches=new Map(catalogue.filter(e=>!visible||visible.has(String(e.id))).map(e=>[String(e.id),e]));
 for(const card of nodes){
  if(visible&&!visible.has(card.dataset.eid))continue;
  const e=matches.get(card.dataset.eid),line=card.querySelector('.walk-trip-line');
  if(e&&line)line.outerHTML=travelRow(e);
 }
 renderTravelProgress();
}

function renderTravelProgress(){
 const n=tripJobs.length+(tripActiveKey?1:0),status=$('travelProgress');
 if(!status)return;
 const message=tripOriginProblem?tripOriginProblem:n?`${n} deslocaç${n===1?'ão':'ões'} em cálculo…`:'';
 status.textContent=message;status.hidden=!message;
}
function retryTolls(id){
 const e=allEvents().find(x=>x.id===id);if(!e)return;
 const r=travelData(e);if(!r||!routeFresh(e,r))return calculateOneRoute(id);
 if(r.tollRequestId){toast('As portagens já estão a ser consultadas.');return;}
 if(Date.now()<tollRetryAfter){toast('O serviço de portagens está temporariamente indisponível.');return;}
 r.tollNextRetry=0;
 queueTrips([e],false);
 refreshTravelCard(id);
}
function calculateOneRoute(id){
 const e=allEvents().find(x=>x.id===id);if(!e)return;
 if(!travelPrefs.origin){openTravelPanel();toast('Define primeiro a origem.');return;}
 tripOriginProblem='';tripProblems.delete(routeCacheKey(e));geoMisses.clear();
 // Pedido manual não pode ficar atrás dos restantes cálculos.
 queueTrips([e],true);refreshTravelCard(id);
}
function runTollQueue(){
 if(tollWorking)return;
 tollWorking=true;
 (async()=>{try{while(tollJobs.length){
  const job=tollJobs.shift(),current=travelRoutes[job.key];
  if(!current||current.tollSource==='manual'||current.tollReturn!=null||current.tollRequestId!==job.requestId)continue;
  let unknown=false,retry=false;
  for(const part of [{field:'tollOut',geometry:job.outGeometry},{field:'tollBack',geometry:job.backGeometry}]){
   const latest=travelRoutes[job.key];
   if(!latest||latest.tollRequestId!==job.requestId||latest.tollSource==='manual')break;
   if(Number.isFinite(latest[part.field]))continue;
   const result=await autoTollsForGeometry(part.geometry);
   const still=travelRoutes[job.key];
   if(!still||still.tollRequestId!==job.requestId||still.tollSource==='manual')break;
   if(result.status==='ok')still[part.field]=result.amount;
   else if(result.status==='unknown')unknown=true;
   else retry=true;
  }
  // Não aplicar portagens de um traçado antigo à cache de um percurso novo.
  const latest=travelRoutes[job.key];
  if(!latest||latest.tollRequestId!==job.requestId||latest.tollSource==='manual')continue;
  if(Number.isFinite(latest.tollOut)&&Number.isFinite(latest.tollBack)){
   latest.tollReturn=Math.round((latest.tollOut+latest.tollBack)*100)/100;
   latest.tollSource='IP';latest.tollChecked=Date.now();
   delete latest.tollNextRetry;delete latest.tollStatus;
  }else{
   delete latest.tollReturn;delete latest.tollChecked;
   latest.tollNextRetry=Date.now()+(unknown?TOLL_UNKNOWN_MS:TOLL_RETRY_MS);
   latest.tollStatus=unknown?'unknown':retry?'retry':'unknown';
  }
  delete latest.tollRequestId;persistTravel();refreshTravelCard(job.id||null);
 }}finally{tollWorking=false;}})();
}
// Assinatura reduzida da geometria para não reutilizar portagens se o OSRM mudar o traçado.
async function processTripQueue(){
 if(tripWorking)return;
 tripWorking=true;travelBusy=true;
 try{while(tripJobs.length){
  const job=tripJobs.shift();tripJobsSet.delete(job.key);
  const e=allEvents().find(x=>x.id===job.id);
  if(!e||job.key!==routeCacheKey(e)||!tripNeedsRoute(e,job.manual))continue;
  tripActiveKey=job.key;refreshTravelCard(e.id);
  try{
   let p=await geocodeText(job.origin.replace(/,?\s*Portugal\s*$/i,'')+', Portugal');
   if(!p){tripOriginProblem='Origem não localizada. Verifica a localidade.';throw new Error(tripOriginProblem);}
   const q=await locateEndpoint(e);
   if(!q)throw new Error('Ponto de partida sem correspondência no mapa (também tentámos a localidade).');
   // Calcular em separado o percurso de ida e o de regresso: podem ter sentidos únicos e portagens diferentes.
   const outward=await roadRoute(p,q);
   const backward=await roadRoute(q,p);
   const previous=travelRoutes[job.key]||{};
   const routeShape=routeShapeFingerprint(outward.geometry);
   const backShape=routeShapeFingerprint(backward.geometry);
   const sameDestination=previous.geocoderVersion===GEOCODER_VERSION&&previous.destinationFingerprint===endpointFingerprint(e);
   const sameRoute=sameDestination&&previous.roundTripVersion===ROUNDTRIP_VERSION&&
       previous.routeShapeFingerprint===routeShape&&previous.backRouteShapeFingerprint===backShape&&
       previous.kmOne===outward.kmOne&&previous.minutesOne===outward.minutesOne&&
       previous.kmBack===backward.kmOne&&previous.minutesBack===backward.minutesOne;
   const kept=previous.manual?{}:{...previous};
   // Não reutilizar valores antigos baseados em 2 × ida, nem portagens de traçados alterados.
   if(!sameRoute){for(const field of ['tollReturn','tollOut','tollBack','tollSource','tollChecked','tollNextRetry','tollRequestId','tollStatus'])delete kept[field];}
   travelRoutes[job.key]={...kept,kmOne:outward.kmOne,minutesOne:outward.minutesOne,
      kmBack:backward.kmOne,minutesBack:backward.minutesOne,
      routeShapeFingerprint:routeShape,backRouteShapeFingerprint:backShape,
      roundTripVersion:ROUNDTRIP_VERSION,precision:q.precision,destinationLabel:q.label,
      destinationFingerprint:endpointFingerprint(e),geocoderVersion:GEOCODER_VERSION,updated:Date.now()};
   const next=travelRoutes[job.key];
   saveRouteGeometry(job.key,next,outward.geometry,backward.geometry);
   tripProblems.delete(job.key);persistTravel();
   // A geometria foi obtida nesta única consulta OSRM; portagens têm fila independente.
   if(outward.geometry.length>1&&backward.geometry.length>1&&tollsDue(next)){
    scheduleCachedTolls(e,next,{out:compactRouteGeometry(outward.geometry),back:compactRouteGeometry(backward.geometry)});
   }
  }catch(err){
   const reason=err?.message||'Serviço de rotas indisponível';
   tripProblems.set(job.key,reason);
   if(/temporariamente|indisponível|HTTP|Sem rota rodoviária/i.test(reason))tripRetryAfter.set(job.key,Date.now()+180000);
   if(reason==='Origem não localizada. Verifica a localidade.'){ 
    tripOriginProblem=reason==='Origem não localizada. Verifica a localidade.'?reason:'Serviço de localização indisponível. Tenta novamente.';
    tripJobs=[];tripJobsSet.clear();
   }
   console.info('Deslocação indisponível:',e.title,reason);
  }finally{tripActiveKey='';refreshTravelCard(e.id);}
 }}finally{tripWorking=false;travelBusy=false;renderTravelProgress();}}
function updateSortLabel(){
 const select=$('travelSort'),container=select.closest('.toolbar-sort');
 const label='Ordenar: '+select.options[select.selectedIndex].textContent;
 container.title=label;select.title=label;
}
updateSortLabel();
$('tripOrigin').value=travelPrefs.origin||'';
updateTravelHeader();
$('tripFuelKind').addEventListener('change',changeFuelKind);
$('tripConsumptionEdit').addEventListener('click',editConsumption);
$('tripFuelEdit').addEventListener('click',editFuelPrice);
$('consumptionForm').addEventListener('submit',applyConsumption);
$('fuelPriceForm').addEventListener('submit',applyFuelPrice);
$('consumptionCancel').addEventListener('click',()=>cancelCarEditor('consumption'));
$('fuelPriceCancel').addEventListener('click',()=>cancelCarEditor('fuel'));
$('tripFuelReset').addEventListener('click',resetFuelPrice);
$('travelToggle').addEventListener('click',toggleTravelPanel);
$('travelInfoToggle').addEventListener('click',()=>{
 const panel=$('travelInfo');panel.hidden=!panel.hidden;
 $('travelInfoToggle').setAttribute('aria-expanded',String(!panel.hidden));
});
$('originForm').addEventListener('submit',applyOrigin);
$('originEdit').addEventListener('click',editTripOrigin);
$('originCancel').addEventListener('click',cancelTripOrigin);
$('travelSort').addEventListener('change',()=>{updateSortLabel();render();});
window.addEventListener('storage',e=>{if(e.key===TRAVEL_ROUTES_KEY){travelRoutes=storage(TRAVEL_ROUTES_KEY,{});render()}if(e.key===TRAVEL_PREF_KEY){travelPrefs=storage(TRAVEL_PREF_KEY,travelPrefs);updateTravelHeader();render()}if(e.key==='trilhario_custom_v1'){custom=storage('trilhario_custom_v1',[]);populateOrganizers();render()}});

initIntroHelp();
renderSourcesDirectory();
$('orgPageSearch').addEventListener('input',renderOrganizersPage);
populateOrganizers();
render();
renderTravelProgress();
loadPrecomputedRoutes().finally(loadEventFeed);
// A lista também se actualiza sozinha ao chegar a hora de início de uma caminhada.
setInterval(refreshAgendaForClock,30000);
document.addEventListener('visibilitychange',refreshAgendaForClock);
window.addEventListener('focus',refreshAgendaForClock);
refreshFuelPrices().catch(()=>{if($('tripFuelKind'))updateFuelInput();});
