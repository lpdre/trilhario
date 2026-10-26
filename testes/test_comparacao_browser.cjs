'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const src=fs.readFileSync(__dirname+'/../assets/js/trilhario.js','utf8');
const start=src.indexOf('function renderComparison(){'),end=src.indexOf('let originEditing=false;',start);
assert.ok(start>0&&end>start);
const fake=Array.from({length:12},(_,i)=>({id:'e'+i,title:'Trilho '+i,organizer:'X',date:'2026-11-01',
 time:'09:00',km:15,gain:300,difficulty:3,price:10,start:'Arouca',url:''}));
const target={innerHTML:'',querySelectorAll:()=>[]};
const ctx={COMPARE_PAGE_MODE:true,$:id=>id==='comparisonContent'?target:null,
 allEvents:()=>fake,compared:new Set(fake.map(e=>e.id)),travelBusy:false,
 esc:x=>String(x??''),fmtN:x=>String(x),fmtP:x=>String(x),dateShort:e=>e.date,
 names:['','Fácil','Moderada','Exigente','Difícil','Muito difícil'],
 comparisonTravelCell:()=> '—',displayDeparture:e=>e.start,safeExternalUrl:()=>false};
vm.runInNewContext(src.slice(start,end),ctx);
ctx.renderComparison();
assert.ok(target.innerHTML.includes('12 caminhadas seleccionadas'));
assert.ok(target.innerHTML.includes('min-width:2855px'),'sem limite de 10 caminhadas');
assert.ok(target.innerHTML.includes('Dificuldade'),'dificuldade mantida');
assert.ok(target.innerHTML.includes('data-ui-action="calculateComparedRoutes"'));
assert.ok(target.innerHTML.includes('data-ui-action="refreshComparison"'));
assert.ok(!target.innerHTML.includes('onclick='));
console.log('OK: tabela comparativa com 12 caminhadas e sem eventos inline');
