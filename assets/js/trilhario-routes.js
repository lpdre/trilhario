/* Trilhário v87: operações puras de geometria e validade de rotas. */
(function(root){
'use strict';
const timeValid=(stamp,maxAge,now=Date.now())=>Number.isFinite(Number(stamp))&&Number(stamp)>0&&Number(stamp)<=now+300000&&now-Number(stamp)<=maxAge;
function encodeRouteGeometry(points){
 if(!Array.isArray(points)||points.length<2)return '';
 let lastLat=0,lastLon=0,out='';
 function part(diff){let n=diff<0?~(diff<<1):(diff<<1);while(n>=32){out+=String.fromCharCode((32|(n&31))+63);n>>>=5;}out+=String.fromCharCode(n+63);}
 for(const point of points){if(!Array.isArray(point)||point.length<2||!Number.isFinite(point[0])||!Number.isFinite(point[1]))return '';
  const lat=Math.round(point[1]*1e5),lon=Math.round(point[0]*1e5);part(lat-lastLat);part(lon-lastLon);lastLat=lat;lastLon=lon;
 }
 return out;
}
function decodeRouteGeometry(value){
 if(typeof value!=='string'||!value||value.length>80000)return [];
 let pos=0,lat=0,lon=0;const result=[];
 function part(){let amount=0,shift=0;while(pos<value.length){const code=value.charCodeAt(pos++)-63;
  if(code<0||code>63||shift>30)throw new Error('Polyline inválida');
  amount|=(code&31)<<shift;if(!(code&32))return (amount&1)?~(amount>>1):(amount>>1);shift+=5;
 }throw new Error('Polyline incompleta');}
 try{while(pos<value.length&&result.length<2001){lat+=part();lon+=part();result.push([lon/1e5,lat/1e5]);}}
 catch{return []}
 return result.length>=2&&result.length<=1800?result:[];
}
function compactRouteGeometry(points){
 if(!Array.isArray(points)||points.length<2)return [];
 if(points.length<=1800)return points;
 return Array.from({length:1800},(_,i)=>points[Math.round(i*(points.length-1)/1799)]);
}
function routeShapeFingerprint(points){
 if(!Array.isArray(points)||!points.length)return '';
 const n=points.length;
 return n+':'+[0,Math.floor(n/4),Math.floor(n/2),Math.floor(3*n/4),n-1]
  .map(i=>Array.isArray(points[i])?points[i].map(x=>Number(x).toFixed(4)).join(','):'').join(';');
}
const api=Object.freeze({timeValid,encodeRouteGeometry,decodeRouteGeometry,compactRouteGeometry,routeShapeFingerprint});
if(typeof module==='object'&&module.exports)module.exports=api;
else root.TrilharioRoutes=api;
})(typeof globalThis!=='undefined'?globalThis:this);
