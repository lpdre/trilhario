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
     if(!id||row.querySelector('.v86-weather'))continue;
     const event=allEvents().find(item=>String(item.id)===id);
     if(!event||!eligible.has(event.date))continue;
     // Nunca ocupar espaço nem fazer consulta se não há local fiável.
     if(!weather.locationPlan(event))continue;
     const line=row.querySelector('.v74-trip-route')||row.querySelector('.walk-trip-line');
     if(!line)continue;
     const slot=document.createElement('span');
     slot.className='v86-weather';
     slot.dataset.weatherId=id;
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
  if(typeof MutationObserver==='function'){
   const observer=new MutationObserver(schedule);
   observer.observe(list,{subtree:true,childList:true});
  }
  schedule();
 }catch(error){
  console.info('Módulo meteorológico opcional indisponível.',error?.message||error);
 }
})();
