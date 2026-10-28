'use strict';
// Publicar apenas os ficheiros da interface; manter funções e colectores fora de dist.
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..'),out=path.join(root,'dist');
fs.rmSync(out,{recursive:true,force:true});
fs.mkdirSync(out,{recursive:true});
for(const file of ['index.html','eventos.json','rotas_precalculadas.json','portagens-config.json'])
 fs.copyFileSync(path.join(root,file),path.join(out,file));
fs.cpSync(path.join(root,'assets'),path.join(out,'assets'),{recursive:true});
console.log('Trilhário: interface estática pronta em dist/');
