// Synthetic standalone browser workflow. Requires an empty local database on port 18981.
const fs = require('fs');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const browserDir = fs.readdirSync('/ms-playwright').find(x => x.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
let socket, browser, seq=0; const pending=new Map(), errors=[];
function call(method,params={}) {return new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error('CDP timeout'));}},10000).unref()})}
async function value(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value}
async function until(expression,label){for(let i=0;i<100;i++){await delay(100);try{if(await value(expression))return}catch{}}throw Error('Timed out: '+label)}
async function main(){
  browser=spawn(binary,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--remote-debugging-port=9238','--remote-allow-origins=*','--user-data-dir=/tmp/wg-own-chromium','about:blank'],{stdio:'ignore'});
  let target;for(let i=0;i<80;i++){try{const r=await fetch('http://127.0.0.1:9238/json/new?about:blank',{method:'PUT'});if(r.ok){target=await r.json();break}}catch{}await delay(100)}
  if(!target)throw Error('Chromium start failed');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,fail)=>{socket.onopen=ok;socket.onerror=fail});
  socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}};
  await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate',{url:'http://127.0.0.1:18981/'});
  await until('!document.querySelector("#own-toolbar")?.hidden && document.querySelector("#status")?.innerText.includes("leer")','standalone empty state');
  await value('document.querySelector("#vehicle-add").click()');
  await until('!document.querySelector("#own-panel").hidden','vehicle form');
  await value('document.querySelector("#entry-make").value="Peugeot";document.querySelector("#entry-model").value="Muster";document.querySelector("#entry-year").value="2020";document.querySelector("#entry-licensePlate").value="XY AB 123";document.querySelector("#entry-vehicleType").value="Limousine";document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#detail-heading")?.textContent==="Peugeot Muster" && document.querySelector("#own-panel").hidden','created vehicle');
  await value('document.querySelector("#condition-edit").click();document.querySelector("#readiness-input").value="not_ready";document.querySelector("#issue-add").click();document.querySelector("#issue-add").click();document.querySelectorAll(".issue-input")[0].value="Synthetische Reparatur";document.querySelectorAll(".issue-input")[1].value="Weitere Testarbeit";document.querySelector("#condition-form").requestSubmit()');
  await until('document.querySelector("#condition-form").hidden && document.querySelector(".card-readiness.not_ready")?.textContent==="INOP"','status saved');
  await value('document.querySelector("#vehicle-edit").click();document.querySelector("#entry-model").value="Muster Korrigiert";document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#detail-heading")?.textContent==="Peugeot Muster Korrigiert" && document.querySelector("#own-panel").hidden','metadata corrected');
  await value('document.querySelector("#odometer-add").click();document.querySelector("#entry-date").value="2026-10-28";document.querySelector("#entry-odometer").value="1200";document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#own-panel").hidden && document.querySelector(".vehicle-card .mileage")?.textContent.includes("1.200")','odometer saved');
  await value('document.querySelector("#record-add").click();document.querySelector("#entry-kind").value="repair";document.querySelector("#entry-description").value="Synthetische Reparatur erledigt";document.querySelector("#entry-date").value="2026-10-28";document.querySelector("#entry-cost").value="12,30";document.querySelector("#entry-currency").value="EUR";document.querySelector("#entry-documentUrl").value="https://documents.example.test/receipt/1";document.querySelector("#entry-closeIssueId").selectedIndex=1;document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#own-panel").hidden && document.querySelector("#services")?.innerText.includes("Synthetische Reparatur erledigt")','repair saved');
  const condition=await value('document.querySelector("#condition-issues").innerText');
  if(condition.includes('Synthetische Reparatur')||!condition.includes('Weitere Testarbeit'))throw Error('Incorrect atomic issue closure');
  if(!await value('document.querySelector(".card-readiness.not_ready")?.textContent==="INOP" && !!document.querySelector(".card-work") && !document.querySelector(".card-work-count")'))throw Error('Readiness changed or counter returned');
  await value('document.querySelector("#history-toggle").click()');
  await until('document.querySelector("#history-events")?.innerText.includes("Synthetische Reparatur erledigt")','history');
  await call('Page.reload');
  await until('document.querySelector("#services")?.innerText.includes("Synthetische Reparatur erledigt")','persisted reload');
  for(const width of [320,390,768,1280]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});await delay(100);
    if(await value('document.documentElement.scrollWidth>innerWidth'))throw Error('Horizontal overflow at '+width);
    if(!await value('document.querySelector("#legacy-manage").hidden && document.querySelector("#legacy-banner").hidden'))throw Error('Legacy navigation visible');
    if(width===390){const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/standalone-preview-mobile.png',Buffer.from(shot.data,'base64'));}
    console.log(width+'px standalone layout passed');
  }
  if(errors.length)throw Error('JavaScript errors: '+errors.join(','));
  console.log('Standalone create, correct identity, odometer, atomic repair, independent INOP, history and reload: PASS');
}
main().catch(e=>{console.error(e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
