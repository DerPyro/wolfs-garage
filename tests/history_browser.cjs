// Synthetic real-Chromium check. The caller serves a fresh schema-4 database at
// http://127.0.0.1:18984 with an empty vehicle list.
const fs = require('fs');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const browserDir = fs.readdirSync('/ms-playwright').find(x => x.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
let socket, browser, seq=0; const pending=new Map(), errors=[];
function call(method,params={}) {return new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error('CDP timeout'));}},10000).unref()})}
async function value(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value}
async function until(expression,label){for(let i=0;i<120;i++){await delay(100);try{if(await value(expression))return}catch{}}let diagnostic={};try{diagnostic=await value('({message:document.querySelector("#logbook-message")?.textContent||"",rows:document.querySelectorAll("#logbook-records .logbook-row").length,moreHidden:document.querySelector("#logbook-more")?.hidden,moreDisabled:document.querySelector("#logbook-more")?.disabled,applyDisabled:document.querySelector("#logbook-apply")?.disabled,errors:'+JSON.stringify(errors)+'})')}catch(e){diagnostic={diagnosticError:String(e)}}throw Error('Timed out: '+label+'; browser state='+JSON.stringify(diagnostic))}
async function main(){
  if(!binary)throw Error('Chromium binary not found');
  browser=spawn(binary,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--remote-debugging-port=9240','--remote-allow-origins=*','--user-data-dir=/tmp/wg-history-browser-chromium','about:blank'],{stdio:'ignore'});
  let target;for(let i=0;i<80;i++){try{const r=await fetch('http://127.0.0.1:9240/json/new?about:blank',{method:'PUT'});if(r.ok){target=await r.json();break}}catch{}await delay(100)}
  if(!target)throw Error('Chromium start failed');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,fail)=>{socket.onopen=ok;socket.onerror=fail});
  socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}};
  await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate',{url:'http://127.0.0.1:18984/'});
  await until('!document.querySelector("#own-toolbar")?.hidden && document.querySelector("#status")?.innerText.includes("leer")','empty standalone state');
  await value('document.querySelector("#vehicle-add").click()');
  await until('!document.querySelector("#own-panel").hidden','vehicle form');
  await value('document.querySelector("#entry-make").value="Synthetic";document.querySelector("#entry-model").value="History Browser";document.querySelector("#entry-vehicleType").value="Limousine";document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#detail-heading")?.textContent==="Synthetic History Browser" && document.querySelector("#own-panel").hidden','created vehicle');
  const fixture=await value(`(async()=>{
    const vehicles=await(await fetch('/garage-api/vehicles')).json();const vehicle=vehicles.vehicles.find(v=>v.model==='History Browser');
    if(!vehicle)throw Error('Synthetic vehicle missing');
    const records=[],readings=[];
    for(let i=0;i<31;i++){
      const date='2026-10-'+String(i+1).padStart(2,'0');
      const kind=i%2?'repair':'service';
      const r=await fetch('/garage-api/vehicles/'+vehicle.id+'/records',{method:'POST',headers:{'Content-Type':'application/json','X-Garage-Request':'1'},body:JSON.stringify({description:'History record '+String(i).padStart(2,'0'),kind,date,commandId:crypto.randomUUID()})});
      if(!r.ok)throw Error('Fixture record failed: '+r.status);records.push((await r.json()).record);
      const o=await fetch('/garage-api/vehicles/'+vehicle.id+'/odometer',{method:'POST',headers:{'Content-Type':'application/json','X-Garage-Request':'1'},body:JSON.stringify({date,odometer:1000+i,unit:'km',note:'Reading note '+String(i).padStart(2,'0'),commandId:crypto.randomUUID()})});
      if(!o.ok)throw Error('Fixture reading failed: '+o.status);readings.push(await o.json());
    }
    return {id:vehicle.id,records,readings};})()`);
  if(!fixture || fixture.records.length!==31 || fixture.readings.length!==31)throw Error('Synthetic fixture incomplete');
  if(!await value('!document.querySelector("#logbook-toggle").hidden'))throw Error('History browsing capability did not expose the logbook');
  await value('document.querySelector("#logbook-toggle").click()');
  await until('document.querySelectorAll("#logbook-records .logbook-row").length===25 && !document.querySelector("#logbook-apply").disabled','first record page');
  if(await value('document.querySelector("#logbook-more").hidden'))throw Error('More records button is hidden with a continuation page');
  await value('document.querySelector("#logbook-more").click()');
  await until('document.querySelectorAll("#logbook-records .logbook-row").length===31 && document.querySelector("#logbook-more").hidden','second record page');
  const oldestTitle='History record 00';
  if(!await value(`Array.from(document.querySelectorAll('#logbook-records .logbook-row-title')).some(x=>x.textContent==='${oldestTitle}')`))throw Error('Oldest record missing after paging');
  const oldestEditId=`log-record-edit-${fixture.records[0].id}`;
  await value(`document.getElementById('${oldestEditId}')?.click()`);
  await until('!document.querySelector("#own-panel").hidden && !!document.querySelector("#entry-correctionReason")','correction editor for older page record');
  await value('document.querySelector("#entry-description").value="History record 00 corrected";document.querySelector("#entry-correctionReason").value="Synthetic browser correction";document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#own-panel").hidden && !document.querySelector("#logbook-panel").hidden && document.querySelectorAll("#logbook-records .logbook-row").length===25 && !document.querySelector("#logbook-apply").disabled','older record correction saved and logbook refreshed');
  const corrected=await value(`(async()=>{const r=await fetch('/garage-api/vehicles/${fixture.id}/records/${fixture.records[0].id}');return r.ok?await r.json():null})()`);
  if(!corrected || corrected.description!=="History record 00 corrected")throw Error('Correction from a later page did not persist');

  await value('document.querySelector("#logbook-type").value="records";document.querySelector("#logbook-from").value="2026-10-10";document.querySelector("#logbook-to").value="2026-10-20";document.querySelector("#logbook-kind").value="repair";document.querySelector("#logbook-filters").requestSubmit()');
  await until('document.querySelectorAll("#logbook-records .logbook-row").length===6 && !document.querySelector("#logbook-apply").disabled','date and kind filtered records');
  if(await value('Array.from(document.querySelectorAll("#logbook-records .logbook-kind")).some(x=>x.textContent!=="Reparatur")'))throw Error('Kind filter returned a different work type');
  await value('document.querySelector("#logbook-type").value="odometer";document.querySelector("#logbook-type").dispatchEvent(new Event("change"));document.querySelector("#logbook-filters").requestSubmit()');
  await until('document.querySelectorAll("#logbook-records .logbook-row").length===11 && !document.querySelector("#logbook-apply").disabled','inclusive filtered odometer rows');
  if(!await value('document.querySelector("#logbook-records").innerText.includes("Reading note 19")'))throw Error('Odometer note is not visible');
  if(await value('!document.querySelector("#logbook-kind-field").hidden'))throw Error('Record kind filter should be hidden for odometer history');

  await value('document.querySelector("#logbook-type").value="records";document.querySelector("#logbook-type").dispatchEvent(new Event("change"));document.querySelector("#logbook-from").value="";document.querySelector("#logbook-to").value="";document.querySelector("#logbook-kind").value="";document.querySelector("#logbook-filters").requestSubmit()');
  await until('document.querySelectorAll("#logbook-records .logbook-row").length===25 && !document.querySelector("#logbook-apply").disabled','unfiltered first page after filters');
  // A backdated API write changes the vehicle audit sequence. The stale page is rejected visibly.
  await value(`(async()=>{const r=await fetch('/garage-api/vehicles/${fixture.id}/records',{method:'POST',headers:{'Content-Type':'application/json','X-Garage-Request':'1'},body:JSON.stringify({description:'Synthetic backdated insertion',kind:'service',date:'2026-09-01',commandId:crypto.randomUUID()})});if(!r.ok)throw Error('Backdated fixture mutation failed')})()`);
  await value('document.querySelector("#logbook-more").click()');
  await until('document.querySelector("#logbook-message").textContent.includes("seit der letzten Seite geändert") && !document.querySelector("#logbook-reload").hidden','stale cursor recovery notice');
  await value('document.querySelector("#logbook-reload").click()');
  await until('document.querySelectorAll("#logbook-records .logbook-row").length===25 && document.querySelector("#logbook-more").hidden===false','reloaded first page after stale cursor');

  for(const width of [320,390,768,1280]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});await delay(120);
    if(await value('document.documentElement.scrollWidth>innerWidth'))throw Error('Horizontal overflow at '+width);
    if(width===390){await value('document.querySelector("#logbook-panel").scrollIntoView({block:"start"})');await delay(180);const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/history-browser-mobile.png',Buffer.from(shot.data,'base64'));}
    console.log(width+'px history browser layout passed');
  }
  if(errors.length)throw Error('JavaScript errors: '+errors.join(','));
  console.log('Synthetic paginated records/odometer, filters, older-page correction and stale cursor recovery: PASS');
}
main().catch(e=>{console.error(e.stack||e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
