// Synthetic real-Chromium workflow. The caller serves a fresh schema-5 DB at
// http://127.0.0.1:18985; this script creates its own vehicle and work items.
const fs = require('fs');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const browserDir = fs.readdirSync('/ms-playwright').find(x => x.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
let socket, browser, seq=0; const pending=new Map(), errors=[];
function call(method,params={}) {return new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error('CDP timeout'));}},10000).unref()})}
async function value(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value}
async function until(expression,label){for(let i=0;i<120;i++){await delay(100);try{if(await value(expression))return}catch{}}let diagnostic={};try{diagnostic=await value('({workStatus:document.querySelector("#work-status")?.textContent||"",items:Array.from(document.querySelectorAll("#work-items .work-item-text")).map(x=>x.textContent),condition:document.querySelector("#condition-message")?.textContent||"",errors:'+JSON.stringify(errors)+'})')}catch(e){diagnostic={diagnosticError:String(e)}}throw Error('Timed out: '+label+'; browser state='+JSON.stringify(diagnostic))}
async function main(){
  if(!binary)throw Error('Chromium binary not found');
  browser=spawn(binary,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--remote-debugging-port=9242','--remote-allow-origins=*','--user-data-dir=/tmp/wg-scheduled-work-chromium','about:blank'],{stdio:'ignore'});
  let target;for(let i=0;i<80;i++){try{const r=await fetch('http://127.0.0.1:9242/json/new?about:blank',{method:'PUT'});if(r.ok){target=await r.json();break}}catch{}await delay(100)}
  if(!target)throw Error('Chromium start failed');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,fail)=>{socket.onopen=ok;socket.onerror=fail});
  socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}};
  await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate',{url:'http://127.0.0.1:18985/'});
  await until('!document.querySelector("#own-toolbar")?.hidden && document.querySelector("#status")?.innerText.includes("leer")','empty standalone state');
  const dates=await value(`(async()=>{const r=await fetch('/garage-api/work');if(!r.ok)throw Error('Work date unavailable');const today=(await r.json()).today;const plus=n=>{const d=new Date(today+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)};return {today,overdue:plus(-1),upcoming:plus(2)}})()`);
  if(!dates || !dates.today || !dates.overdue || !dates.upcoming)throw Error('Could not derive synthetic dates from the displayed Berlin day');

  await value('document.querySelector("#vehicle-add").click()');
  await until('!document.querySelector("#own-panel").hidden','vehicle form');
  await value('document.querySelector("#entry-make").value="Synthetic";document.querySelector("#entry-model").value="Scheduled Work";document.querySelector("#entry-vehicleType").value="Limousine";document.querySelector("#own-form").requestSubmit()');
  await until('document.querySelector("#detail-heading")?.textContent==="Synthetic Scheduled Work" && document.querySelector("#own-panel").hidden','created vehicle');

  await value('document.querySelector("#condition-edit").click()');
  await until('!document.querySelector("#condition-form").hidden','condition editor');
  await value('document.querySelector("#issue-add").click();document.querySelector("#issue-add").click();document.querySelector("#issue-add").click();document.querySelector("#issue-add").click()');
  const spec=JSON.stringify([
    {text:'Unclassified future work',date:dates.upcoming,severity:'',lifecycle:'open'},
    {text:'Critical overdue work',date:dates.overdue,severity:'critical',lifecycle:'open'},
    {text:'Observed work due today',date:dates.today,severity:'observation',lifecycle:'observed'},
    {text:'Unscheduled repair work',date:'',severity:'repair',lifecycle:'open'},
  ]);
  await value(`(()=>{const specs=${spec};const rows=Array.from(document.querySelectorAll('#issue-editor .issue-row'));if(rows.length!==specs.length)throw Error('Wrong issue editor row count');rows.forEach((row,i)=>{const item=specs[i];row.querySelector('.issue-field-text input').value=item.text;row.querySelector('.issue-field-due-date input').value=item.date;row.querySelector('.issue-field-severity select').value=item.severity;row.querySelector('.issue-field-lifecycle select').value=item.lifecycle});document.querySelector('#readiness-input').value='not_ready';document.querySelector('#condition-form').requestSubmit()})()`);
  await until('document.querySelector("#condition-form").hidden && document.querySelectorAll("#work-items .work-item").length===4 && document.querySelector("#condition-work-asof").textContent.includes("Europe/Berlin")','scheduled work saved and projected');
  const dashboard=await value('Array.from(document.querySelectorAll("#work-items .work-item-text")).map(x=>x.textContent)');
  if(dashboard.join('|')!=='Critical overdue work|Observed work due today|Unclassified future work|Unscheduled repair work')throw Error('Unexpected critical/due ordering: '+dashboard.join('|'));
  if(!await value('!!document.querySelector(".card-readiness.not_ready")'))throw Error('Scheduled work changed INOP readiness');

  const filters={overdue:['Critical overdue work'],today:['Observed work due today'],critical:['Critical overdue work'],observed:['Observed work due today'],all:['Critical overdue work','Observed work due today','Unclassified future work','Unscheduled repair work']};
  for(const [filter,expected] of Object.entries(filters)){
    await value(`document.querySelector('#issue-filter').value=${JSON.stringify(filter)};document.querySelector('#issue-filter').dispatchEvent(new Event('change'))`);
    await until(`JSON.stringify(Array.from(document.querySelectorAll('#condition-issues .condition-issue-text')).map(x=>x.textContent))===${JSON.stringify(JSON.stringify(expected))}`,filter+' issue filter');
  }

  // Clear a previously saved date in the editor, then verify the null survives reload.
  await value('document.querySelector("#condition-edit").click()');
  await until('!document.querySelector("#condition-form").hidden','reopened condition editor');
  await value('document.querySelectorAll("#issue-editor .issue-row")[0].querySelector(".issue-field-due-date input").value="";document.querySelector("#condition-form").requestSubmit()');
  await until('document.querySelector("#condition-form").hidden && document.querySelector("#work-items .work-item-text")?.textContent==="Critical overdue work"','cleared date saved');
  const saved=await value(`(async()=>{const v=await(await fetch('/garage-api/vehicles')).json();const vehicle=v.vehicles.find(x=>x.model==='Scheduled Work');if(!vehicle)throw Error('Vehicle missing');const status=await(await fetch('/garage-api/vehicles/'+vehicle.id+'/status')).json();return {id:vehicle.id,status}})()`);
  const future=saved.status.issues.find(x=>x.text==='Unclassified future work');
  if(!saved || !future || future.dueDate!==null || future.severity!==null || future.lifecycle!=='open')throw Error('Explicitly cleared date was not persisted as unclassified open work');
  await call('Page.reload');
  await until('document.querySelector("#work-dashboard") && !document.querySelector("#work-dashboard").hidden && document.querySelector("#work-items").innerText.includes("Unclassified future work")','scheduled work persisted after reload');
  const afterReload=await value(`(async()=>{const s=await(await fetch('/garage-api/vehicles/${saved.id}/status')).json();return s.issues.find(x=>x.text==='Unclassified future work')})()`);
  if(!afterReload || afterReload.dueDate!==null)throw Error('Cleared date returned after reload');

  // Close the critical issue via the existing completion form; readiness and
  // metadata for all other work remain unchanged.
  const critical=saved.status.issues.find(x=>x.text==='Critical overdue work');
  const remainingBefore=saved.status.issues.filter(x=>x.id!==critical.id);
  await value(`document.querySelector('#record-add').click()`);
  await until('!document.querySelector("#own-panel").hidden && !!document.querySelector("#entry-closeIssueId")','record completion form');
  await value(`document.querySelector('#entry-kind').value='repair';document.querySelector('#entry-description').value='Synthetic critical work completed';document.querySelector('#entry-date').value=${JSON.stringify(dates.today)};document.querySelector('#entry-closeIssueId').value=${JSON.stringify(critical.id)};document.querySelector('#own-form').requestSubmit()`);
  await until('document.querySelector("#own-panel").hidden && !document.querySelector("#detail-content").hidden && document.querySelectorAll("#work-items .work-item").length===3 && !document.querySelector("#work-status").textContent.includes("werden geladen")','record completion saved and dashboard refreshed');
  const afterClose=await value(`(async()=>{const s=await(await fetch('/garage-api/vehicles/${saved.id}/status')).json();const w=await(await fetch('/garage-api/work')).json();const v=await(await fetch('/garage-api/vehicles/${saved.id}')).json();return {status:s,work:w.items.filter(x=>x.vehicleId===${saved.id}).map(x=>x.text),readiness:v.status.readiness}})()`);
  if(afterClose.status.readiness!=='not_ready' || afterClose.readiness!=='not_ready')throw Error('Closing work changed INOP readiness');
  if(afterClose.status.issues.some(x=>x.id===critical.id) || afterClose.work.includes('Critical overdue work'))throw Error('Completed issue still appears as active work');
  for(const previous of remainingBefore){const actual=afterClose.status.issues.find(x=>x.id===previous.id);if(!actual || actual.text!==previous.text || actual.dueDate!==previous.dueDate || actual.severity!==previous.severity || actual.lifecycle!==previous.lifecycle)throw Error('Remaining issue metadata changed during record closure: '+previous.text)}
  if(!await value('!!document.querySelector(".card-readiness.not_ready")'))throw Error('Vehicle no longer displays INOP after completing an issue');

  for(const width of [320,390,768,1280]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});await delay(120);
    if(await value('document.documentElement.scrollWidth>innerWidth'))throw Error('Horizontal overflow at '+width);
    if(width===390){await value('document.querySelector("#work-dashboard").scrollIntoView({block:"start"})');await delay(180);const shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/scheduled-work-mobile.png',Buffer.from(shot.data,'base64'));}
    console.log(width+'px scheduled work layout passed');
  }
  if(errors.length)throw Error('JavaScript errors: '+errors.join(','));
  console.log('Synthetic scheduling, filters, date clearing, reload, atomic completion and readiness preservation: PASS');
}
main().catch(e=>{console.error(e.stack||e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
