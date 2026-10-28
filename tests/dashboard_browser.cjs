// Chromium smoke test against a local synthetic-data adapter, never a live garage.
const fs = require('fs');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const browserDir = fs.readdirSync('/ms-playwright').find(x => x.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
let socket, browser, seq=0;
const pending = new Map();
const exceptions = [];
function call(method,params={}) { return new Promise((resolve,reject) => { const id=++seq; pending.set(id,{resolve,reject}); socket.send(JSON.stringify({id,method,params})); setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error('CDP timeout'));}},10000).unref(); }); }
async function value(expression) { const r=await call('Runtime.evaluate',{expression,returnByValue:true}); if(r.exceptionDetails) throw Error(r.exceptionDetails.text); return r.result.value; }
async function main() {
  browser=spawn(binary,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--remote-debugging-port=9236','--remote-allow-origins=*','--user-data-dir=/tmp/wg-chromium','about:blank'],{stdio:'ignore'});
  let target;
  for(let i=0;i<80;i++){try{const r=await fetch('http://127.0.0.1:9236/json/new?about:blank',{method:'PUT'});if(r.ok){target=await r.json();break;}}catch{}await delay(100)}
  if(!target)throw Error('Chromium start failed');
  socket=new WebSocket(target.webSocketDebuggerUrl); await new Promise((ok,fail)=>{socket.onopen=ok;socket.onerror=fail});
  socket.onmessage=e=>{const m=JSON.parse(e.data); if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params.exceptionDetails.text); if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}};
  await call('Page.enable'); await call('Runtime.enable');
  for(const width of [320,390,768,1280]) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});
    await call('Page.navigate',{url:'http://127.0.0.1:18980/'});
    let ready=false;
    for(let i=0;i<80;i++){await delay(100);try{if(await value('document.querySelector("#detail-heading")?.textContent === "Peugeot Muster" && !document.querySelector("#detail-content").hidden && Array.from(document.querySelectorAll(".vehicle-card .manufacturer-logo")).every(x=>x.complete)')){ready=true;break}}catch{}}
    if(!ready)throw Error(`Data not displayed at ${width}px`);
    const result=await value('({viewport:innerWidth,document:document.documentElement.scrollWidth,card:document.querySelector(".vehicle-card")?.getAttribute("aria-pressed"),native:document.querySelector(".manage-link")?.getAttribute("href"),service:document.querySelector("#services")?.innerText,icons:Array.from(document.querySelectorAll(".vehicle-card .car-icon use"),x=>x.getAttribute("href")),logos:Array.from(document.querySelectorAll(".vehicle-card .manufacturer-logo"),x=>x.getAttribute("src")),logosLoaded:Array.from(document.querySelectorAll(".vehicle-card .manufacturer-logo"),x=>x.complete&&x.naturalWidth>0),badges:document.querySelectorAll(".vehicle-card .vehicle-type").length,labels:Array.from(document.querySelectorAll(".vehicle-card"),x=>x.getAttribute("aria-label")),markers:Array.from(document.querySelectorAll(".vehicle-card .card-readiness"),x=>x.textContent),work:Array.from(document.querySelectorAll(".vehicle-card"),x=>{const w=x.querySelector(".card-work");return {title:w?.title||"",icon:!!w?.querySelector("svg")}}),heights:Array.from(document.querySelectorAll(".vehicle-card"),x=>x.getBoundingClientRect().height)})');
    if(result.viewport!==width || result.document>width || result.card!=='true' || result.native!=='/Home' || !result.service.includes('Prüfung') || result.icons.join(',')!=='#i-sedan,#i-cross,#i-highroof,#i-naked,#i-hatchback' || result.logos.join(',')!=='/garage-assets/brands/peugeot.svg,/garage-assets/brands/yamaha-motor.svg,/garage-assets/brands/opel.svg,/garage-assets/brands/suzuki.svg,/garage-assets/brands/opel.svg' || result.logosLoaded.length!==5 || !result.logosLoaded.every(Boolean) || result.badges!==0 || result.markers.join(',')!=='INOP,?,?,?' || result.work[0].title!=='Wartung ausstehend' || !result.work[0].icon || result.work[1].title!=='Wartung ausstehend' || !result.work[1].icon || result.work[2].title || result.work[3].title || result.work[4].title || (width<700 && Math.max(...result.heights)-Math.min(...result.heights)>1) || !result.labels[0].includes('Fahrbereit, Offen: Inspektion prüfen') || !result.labels[1].includes('Cross-Motorrad') || !result.labels[1].includes('Nicht fahrbereit, Offen: Beispielreparatur offen') || !result.labels[2].includes('Hochdachkombi') || !result.labels[2].includes('Status nicht erfasst') || !result.labels[3].includes('Naked Bike') || !result.labels[4].includes('Schrägheck') || exceptions.length) throw Error(`Wrong layout/data ${width}: ${JSON.stringify(result)}; JS errors ${exceptions.join(',')}`);
    if(width===390){const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/garage-preview-mobile.png',Buffer.from(shot.data,'base64'));}
    console.log(`${width}px: synthetic vehicle, maintenance, navigation and width passed`);
  }
}
main().catch(e=>{console.error(e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
