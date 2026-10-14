import http from 'node:http';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import {resolve,dirname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'../web');
const port=Number(process.env.PORT??4173);
const server=http.createServer(async(req,res)=>{
  try{
    const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    const file=resolve(root,'.'+(pathname==='/'?'/index.html':pathname));
    if(!file.startsWith(root+sep)){res.writeHead(403).end();return;}
    const info=await stat(file);if(!info.isFile()){res.writeHead(404).end();return;}
    const extension=file.replace(/\.gz$/,'').split('.').pop();
    const mime={html:'text/html; charset=utf-8',css:'text/css; charset=utf-8',js:'application/javascript',json:'application/json',wasm:'application/wasm',png:'image/png',data:'application/octet-stream'}[extension]??'application/octet-stream';
    const headers={'Content-Type':mime,'Content-Length':info.size,'Cache-Control':'no-store'};
    if(file.endsWith('.gz'))headers['Content-Encoding']='gzip';res.writeHead(200,headers);
    if(req.method==='HEAD'){res.end();return;}createReadStream(file).pipe(res);
  }catch{res.writeHead(404).end('Not found');}
});
server.listen(port,'127.0.0.1',()=>console.log(`Yugiri web build: http://127.0.0.1:${port}`));
export {server};
