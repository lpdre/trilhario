/* Camada meteorológica opcional.
 * Carregada DEPOIS da aplicação: nunca pode bloquear a agenda de caminhadas.
 */
(function(){
 'use strict';
 try{
  const weather=window.TrilharioWeather;
  const list=document.getElementById('listView');
  if(!weather||!list||typeof allEvents!=='function')return;
  const engine=weather.create({
   today:()=>typeof agendaClock==='function'?agendaClock().date:
    new Date().toLocaleDateString('sv-SE',{timeZone:'Europe/Lisbon'}),
   getEvent:id=>allEvents().find(event=>String(event.id)===String(id))
  });
  let pending=false;
  function mount(){
   pending=false;
   try{
    const eligible=weather.weekendDates(
     typeof agendaClock==='function'?agendaClock().date:
      new Date().toLocaleDateString('sv-SE',{timeZone:'Europe/Lisbon'})
    );
    for(const row of list.querySelectorAll('.walk-row[data-eid]')){
     const id=row.dataset.eid;
     if(!id)continue;
     const existing=row.querySelector('.v86-weather');
     const event=allEvents().find(item=>String(item.id)===id);
     // Não apresentar previsão fora da janela ou para locais desconhecidos.
     // Isto também remove espaços deixados pelo desenho inicial do cartão.
     if(!event||!eligible.has(event.date)||!weather.locationPlan(event)){
      existing?.remove?.();
      continue;
     }
     const route=row.querySelector('.v74-trip-route');
     const line=route||row.querySelector('.walk-trip-line');
     if(!line)continue;
     // Colocar o símbolo na linha da distância/tempo da viagem, nunca
     // ao lado dos preços: evita empurrar o combustível no telemóvel.
     if(existing){
      if(route&&existing.parentElement!==route)route.appendChild(existing);
      if(!existing.textContent.trim()){
       existing.textContent='…';
       existing.title='A consultar a previsão meteorológica';
      }
      continue;
     }
     const slot=document.createElement('a');
     slot.className='v86-weather';
     slot.dataset.weatherId=id;
     // O estado fica visível enquanto se consulta a previsão; uma falha
     // deixa um travessão explicativo, nunca inventa temperatura.
     slot.textContent='…';
     slot.title='A consultar a previsão meteorológica';
     slot.setAttribute('aria-live','off');
     line.appendChild(slot);
    }
    engine.observe(list.querySelectorAll('[data-weather-id]'));
   }catch(error){
    console.info('Previsão meteorológica ignorada; agenda mantém-se disponível.',error?.message||error);
   }
  }
  function schedule(){
   if(pending)return;
   pending=true;
   if(typeof requestAnimationFrame==='function')requestAnimationFrame(mount);
   else Promise.resolve().then(mount);
  }
  document.addEventListener?.('trilhario:cards-updated',schedule);
  if(typeof MutationObserver==='function'){
   const observer=new MutationObserver(records=>{
    // Ignorar a escrita da própria temperatura no <span> para evitar ciclos.
    // Reagir só a novos cartões ou a linhas de viagem substituídas pelo núcleo.
    const updated=records.some(record=>Array.from(record.addedNodes||[]).some(node=>
     node.nodeType===1&&(
      node.matches?.('.walk-row, .walk-trip-line')||
      node.querySelector?.('.walk-row, .walk-trip-line')
     )));
    if(updated)schedule();
   });
   observer.observe(list,{subtree:true,childList:true});
  }
  schedule();
 }catch(error){
  console.info('Módulo meteorológico opcional indisponível.',error?.message||error);
 }
})();
