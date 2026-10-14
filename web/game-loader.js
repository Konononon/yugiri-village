const canvas=document.querySelector('#unity-canvas');
const status=document.querySelector('#status');
function loadScript(src){return new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=src;script.onload=resolve;script.onerror=()=>reject(new Error('게임 로더를 내려받지 못했습니다. 페이지를 새로고침해주세요.'));document.head.append(script);});}
function waitWarmupFrames(count){return new Promise(resolve=>{let n=0;function tick(){if(++n>=count)resolve();else requestAnimationFrame(tick);}requestAnimationFrame(tick);});}
async function loadGame(){
  try{
    if(typeof WebAssembly==='undefined')throw new Error('게임 실행에는 WebAssembly를 지원하는 최신 브라우저가 필요합니다.');
    const response=await fetch('build-config.json',{cache:'no-cache'});if(!response.ok)throw new Error('게임 정보를 불러오지 못했습니다. 페이지를 새로고침해주세요.');
    const config=await response.json();await loadScript(config.loaderUrl);
    const instance=await window.createUnityInstance(canvas,{...config,streamingAssetsUrl:'StreamingAssets',autoSyncPersistentDataPath:true,devicePixelRatio:Math.min(window.devicePixelRatio||1,1.5),showBanner:(message,type)=>{if(type==='error')status.textContent=message;}},progress=>{const pct=Math.min(99,Math.round(progress*100));document.querySelector('#progress-fill').style.width=`${pct}%`;document.querySelector('#progress-text').textContent=`${pct}%`;});
    await waitWarmupFrames(135);
    document.querySelector('#progress-fill').style.width='100%';document.querySelector('#progress-text').textContent='100%';
    window.yugiriUnity=instance;document.querySelector('#loading').hidden=true;canvas.focus();
  }catch(error){console.error(error);status.textContent=error.message||'게임을 열지 못했습니다. 페이지를 새로고침해주세요.';document.querySelector('.progress-track').hidden=true;document.querySelector('#progress-text').hidden=true;}
}
void loadGame();
