import {readFile,stat} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {createGunzip} from 'node:zlib';
import {resolve,dirname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const web=resolve(root,'web');
const json=async(path)=>JSON.parse((await readFile(path,'utf8')).replace(/^\uFEFF/,''));
const config=await json(resolve(web,'build-config.json'));
const deployment=await json(resolve(root,'vercel.json'));
assert.equal(deployment.outputDirectory,'web');
const page=await readFile(resolve(web,'index.html'),'utf8');
assert.ok(page.includes('game-loader.js'));
for(const key of ['loaderUrl','dataUrl','frameworkUrl','codeUrl']){
  assert.equal(typeof config[key],'string');
  const file=resolve(web,config[key]);assert.ok(file.startsWith(web+sep));
  const info=await stat(file);assert.ok(info.size>100,`Empty build file: ${file}`);
  assert.ok(info.size<95*1024*1024,`Build file exceeds safe GitHub file size: ${file}`);
  if(file.endsWith('.gz')){
    const gzip=createGunzip(),source=createReadStream(file);source.on('error',error=>gzip.destroy(error));source.pipe(gzip);
    let first=null,bytes=0;for await(const chunk of gzip){if(!first)first=chunk.subarray(0,32);bytes+=chunk.length;}
    if(key==='codeUrl')assert.equal(first.subarray(0,4).toString('hex'),'0061736d','Invalid WebAssembly header');
    if(key==='dataUrl')assert.ok(first.toString('ascii').startsWith('UnityWebData'),'Invalid Unity asset archive');
    console.log(`${key}: ${(info.size/1024/1024).toFixed(1)} MB compressed, ${(bytes/1024/1024).toFixed(1)} MB decoded`);
  }else console.log(`${key}: ${info.size} bytes`);
}
assert.ok(deployment.headers.some(rule=>rule.source.includes('wasm.gz')&&rule.headers.some(header=>header.key==='Content-Encoding'&&header.value==='gzip')));
console.log('Verified complete Unity web build and Vercel headers.');
