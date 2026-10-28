// Synthetic real-Chromium workflow. The caller provides an empty schema-2 DB
// and serves the standalone app on http://127.0.0.1:18983.
const fs = require('fs');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const browserDir = fs.readdirSync('/ms-playwright').find(x => x.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
let socket, browser, seq=0; const pending=new Map(), errors=[];
function call(method,params={}) {return new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error('CDP timeout'));}},10000).unref()})}
async function value(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value}
async function until(expression,label){for(let i=0;i<120;i++){await delay(100);try{if(await value(expression))return}catch{}}throw Error('Timed out: '+label)}
async function main(){
  if(!binary)throw Error('Chromium binary not found');
  browser=spawn(binary,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--remote-debugging-port=9239','--remote-allow-origins=*','--user-data-dir=/tmp/wg-record-corrections-chromium','about:blank'],{stdio:'ignore'});
  let target;for(let i=0;i<80;i++){try{const r=await fetch('http://127.0.0.1:9239/json/new?about:blank',{method:'PUT'});if(r.ok){target=await r.json();break}}catch{}await delay(100)}
  if(!target)throw Error('Chromium start failed');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,fail)=>{socket.onopen=ok;socket.onerror=fail});
  socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}};
  await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate',{url:'http://127.0.0.1:18983/'});
  await until('!document.querySelector("#own-toolbar")?.hidden && document.querySelector("#status")?.innerText.includes("leer")','standalone empty state');
  await value('document.querySelector("#vehicle-add").click()');
  await until('!document.querySelector("#own-panel").hidden','vehicle form');
  await value('document.querySelector("#entry-make").value="Demo";document.querySelector("#entry-model").value="Korrekturtest";document.querySelector("#entry-year").value="2020";document.querySelector("#entry-vehicleType").value="Limousine";document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#detail-heading")?.textContent==="Demo Korrekturtest" && document.querySelector("#own-panel").hidden','created vehicle');
  await value('document.querySelector("#condition-edit").click();document.querySelector("#readiness-input").value="not_ready";document.querySelector("#issue-add").click();document.querySelector(".issue-input").value="Synthetische Reparatur";document.querySelector("#condition-form").requestSubmit()');
  await until('document.querySelector("#condition-form").hidden && document.querySelector(".card-readiness.not_ready")?.textContent==="INOP"','status saved');
  const vehicleId=await value('(async()=>{const x=await(await fetch("/garage-api/vehicles")).json();return x.vehicles.find(v=>v.model==="Korrekturtest")?.id})()');
  if(!vehicleId)throw Error('Created vehicle was not found through the API');
  await value('document.querySelector("#record-add").click();document.querySelector("#entry-kind").value="repair";document.querySelector("#entry-description").value="Bremsen prüfen erledigt";document.querySelector("#entry-date").value="2026-10-28";document.querySelector("#entry-odometer").value="45678";document.querySelector("#entry-cost").value="145,90";document.querySelector("#entry-currency").value="EUR";document.querySelector("#entry-documentUrl").value="https://documents.example.test/receipt/original";document.querySelector("#entry-closeIssueId").selectedIndex=1;document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#own-panel").hidden && document.querySelector("#services")?.innerText.includes("Bremsen prüfen erledigt")','record saved');
  await until('!document.querySelector("#condition-issues")?.innerText.includes("Synthetische Reparatur")','issue closed');
  if(!await value('document.querySelector(".card-readiness.not_ready")?.textContent==="INOP"'))throw Error('Record completion changed readiness');
  const originalRecord=await value(`(async()=>{const x=await(await fetch("/garage-api/vehicles/${vehicleId}/records")).json();return x.records[0]})()`);
  if(!originalRecord)throw Error('Created record was not found through the API');
  const original=await value('(()=>{const b=document.querySelector(".record-edit");return b&&b.id})()');
  if(!original)throw Error('Record correction control was not rendered');
  await value('document.querySelector(".record-edit").click()');
  await until('!document.querySelector("#own-panel").hidden && !!document.querySelector("#entry-correctionReason")','correction form');
  const locked=await value('({date:document.querySelector("#record-edit-readonly-date")?.textContent,odometer:document.querySelector("#record-edit-readonly-odometer")?.textContent,description:document.querySelector("#entry-description")?.value})');
  if(!locked.date || !locked.odometer || locked.description!=="Bremsen prüfen erledigt")throw Error('Readonly facts or loaded correction fields missing');
  await value('document.querySelector("#entry-description").value="Bremsanlage geprüft";document.querySelector("#entry-kind").value="service";document.querySelector("#entry-cost").value="0,00";document.querySelector("#entry-currency").value="EUR";document.querySelector("#entry-documentUrl").value="";document.querySelector("#entry-correctionReason").value="Werkstattrechnung nach Abgleich korrigiert.";document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#own-panel").hidden && document.querySelector("#services")?.innerText.includes("Bremsanlage geprüft")','record corrected');
  if(!await value('document.querySelector("#services")?.innerText.includes("Beleg öffnen")===false'))throw Error('Removed document link remains visible');
  if(!await value('document.querySelector(".card-readiness.not_ready")?.textContent==="INOP" && !document.querySelector("#condition-issues").innerText.includes("Synthetische Reparatur")'))throw Error('Correction changed issue closure or readiness');
  await value('document.querySelector("#history-toggle").click()');
  await until('document.querySelector("#history-events")?.innerText.includes("Werkstattrechnung nach Abgleich korrigiert")','correction history');
  await call('Page.reload');
  await until('document.querySelector("#services")?.innerText.includes("Bremsanlage geprüft")','persisted correction');
  await value('document.querySelector("#history-toggle").click()');
  await until('document.querySelector("#history-events")?.innerText.includes("Werkstattrechnung nach Abgleich korrigiert")','persisted correction history');
  const correctedHistory=await value('(()=>{const row=Array.from(document.querySelectorAll("#history-events .history-event")).find(x=>x.querySelector("h4")?.textContent==="Beleg korrigiert");if(!row)return null;const details=row.querySelector("details");if(details)details.open=true;return {before:details?.querySelector(".history-facts")?.textContent||"",after:row.querySelector(".history-facts")?.textContent||""}})()');
  if(!correctedHistory || !correctedHistory.before.includes("Bremsen prüfen erledigt") || !correctedHistory.after.includes("Bremsanlage geprüft") || !correctedHistory.after.includes("Werkstattrechnung nach Abgleich korrigiert"))throw Error('Correction event does not show its before, after and reason');
  // The record detail API is the source of immutable fields. Compare before/after correction directly.
  const facts=await value(`(async()=>{const r=await fetch("/garage-api/vehicles/${vehicleId}/records/${originalRecord.id}");return r.ok?await r.json():null})()`);
  if(!facts)throw Error('Corrected record detail could not be fetched');
  for(const field of ["date","odometer","odometerUnit","closedIssueId","id"])if(facts[field]!==originalRecord[field])throw Error('Immutable '+field+' changed during correction');
  if(facts.date!=="2026-10-28" || facts.odometer!==45678 || facts.closedIssueId==null)throw Error('Initial record did not include the expected date, reading and issue closure');
  if(!facts.documentUrl && facts.description==="Bremsanlage geprüft" && facts.cost==="0.00" && facts.kind==="service")console.log('Full replacement fields persisted; HTTPS link removed');
  else throw Error('Corrected editable fields do not match');
  for(const width of [320,390,768,1280]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});await delay(120);
    if(await value('document.documentElement.scrollWidth>innerWidth'))throw Error('Horizontal overflow at '+width);
    if(width===390){
      await value('(()=>{const row=Array.from(document.querySelectorAll("#history-events .history-event")).find(x=>x.querySelector("h4")?.textContent==="Beleg korrigiert");if(!row)throw Error("Corrected history event missing");row.scrollIntoView({block:"start"});const details=row.querySelector("details");if(details)details.open=true})()');
      await delay(180);
      let shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/record-corrections-mobile.png',Buffer.from(shot.data,'base64'));

      // Capture the freshly reloaded correction editor as a second focused view.
      await value('document.querySelector(".record-edit").click()');
      await until('!document.querySelector("#own-panel").hidden && !!document.querySelector("#entry-correctionReason")','reloaded correction editor');
      await value('document.querySelector("#own-panel").scrollIntoView({block:"start"})');
      await delay(180);
      shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/record-correction-editor-mobile.png',Buffer.from(shot.data,'base64'));
    }
    console.log(width+'px record-correction layout passed');
  }
  if(errors.length)throw Error('JavaScript errors: '+errors.join(','));
  console.log('Create, close issue, correct record, immutable facts, audit history and reload: PASS');
}
main().catch(e=>{console.error(e.stack||e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
