// Local synthetic end-to-end HTTPS edit; requires the documented localhost fixture.
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
  browser=spawn(binary,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--ignore-certificate-errors','--host-resolver-rules=MAP garage.test 127.0.0.1','--remote-debugging-port=9237','--remote-allow-origins=*','--user-data-dir=/tmp/wg-edit-chromium','about:blank'],{stdio:'ignore'});
  let target;for(let i=0;i<80;i++){try{const r=await fetch('http://127.0.0.1:9237/json/new?about:blank',{method:'PUT'});if(r.ok){target=await r.json();break}}catch{}await delay(100)}
  if(!target)throw Error('Chromium start failed');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,fail)=>{socket.onopen=ok;socket.onerror=fail});
  socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}};
  await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate',{url:'https://garage.test/'});
  await until('document.querySelector("#detail-heading")?.textContent === "Peugeot Muster" && !document.querySelector("#condition-edit").disabled','initial vehicle');
  await value('document.querySelector("#condition-edit").click()');
  await until('!document.querySelector("#condition-form").hidden','editor open');
  await value('document.querySelector("#readiness-input").value="not_ready"; document.querySelector("#issue-add").click(); document.querySelectorAll(".issue-input")[1].value="Synthetischer Testpunkt"; document.querySelector("#condition-form").requestSubmit()');
  await until('document.querySelector("#condition-form").hidden && document.querySelector(".vehicle-card .card-readiness.not_ready")?.textContent === "INOP" && document.querySelector("#condition-issues")?.innerText.includes("Synthetischer Testpunkt")','saved state');
  await call('Page.reload');
  await until('document.querySelector(".vehicle-card .card-readiness.not_ready")?.textContent === "INOP" && document.querySelector("#condition-issues")?.innerText.includes("Synthetischer Testpunkt")','state after reload');
  if(errors.length)throw Error('JavaScript errors: '+errors.join(','));
  console.log('HTTPS synthetic edit, real PUT, save and persisted reload: PASS');
}
main().catch(e=>{console.error(e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
