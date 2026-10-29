// Synthetic real-Chromium acceptance for schema-5 reading provenance/corrections.
// Prepare an isolated fixture with PYTHONPATH=. python tests/prepare_measurement_preview.py DB BACKUP,
// then serve the app on loopback port 18994 and set GARAGE_BROWSER_ORIGIN if needed.
const fs = require('fs');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const origin = process.env.GARAGE_BROWSER_ORIGIN || 'http://127.0.0.1:18994';
const output = '/out/measurement-corrections-browser';
const browserDir = fs.readdirSync('/ms-playwright').find(name => name.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
let browser, socket, seq=0;
const pending=new Map(), errors=[];
function call(method,params={}) { return new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error(`CDP timeout: ${method}`))}},10000).unref();}); }
async function value(expression) { const result=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.text);return result.result.value; }
async function until(expression,label) { for(let i=0;i<150;i++){await delay(100);try{if(await value(expression))return;}catch(_){}}let diagnostic={};try{diagnostic=await value(`({title:document.querySelector('#own-title')?.textContent,ownMessage:document.querySelector('#own-message')?.textContent,notice:document.querySelector('#own-notice')?.textContent,recordRows:document.querySelectorAll('#logbook-records .logbook-row').length,history:document.querySelector('#history-message')?.textContent,errors:${JSON.stringify(errors)}})`)}catch(error){diagnostic={error:String(error)}}throw Error(`Timed out waiting for ${label}: ${JSON.stringify(diagnostic)}`); }
async function click(selector) { await value(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw Error('missing '+${JSON.stringify(selector)});el.click()})()`); }
async function api(path) { return value(`(async()=>{const response=await fetch(${JSON.stringify(path)});const data=await response.json();if(!response.ok)throw Error(${JSON.stringify(path)}+' returned '+response.status+': '+JSON.stringify(data));return data})()`); }
async function fill(selector, text) { await value(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw Error('missing '+${JSON.stringify(selector)});el.value=${JSON.stringify(text)};el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}))})()`); }
async function save() { await click('#own-save'); await until("document.querySelector('#own-panel').hidden",'measurement save closes editor'); }
async function screenshot(name) { fs.mkdirSync(output,{recursive:true});const result=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(`${output}/${name}.png`,Buffer.from(result.data,'base64')); }

async function main() {
  if(!binary)throw Error('Chromium binary not found under /ms-playwright');
  browser=spawn(binary,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--remote-debugging-port=9250','--remote-allow-origins=*','--user-data-dir=/tmp/wg-measurement-corrections-chromium','about:blank'],{stdio:'ignore'});
  let target;for(let i=0;i<100;i++){try{const response=await fetch('http://127.0.0.1:9250/json/new?about:blank',{method:'PUT'});if(response.ok){target=await response.json();break;}}catch(_){}await delay(100);}if(!target)throw Error('Chromium start failed');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.method==='Runtime.exceptionThrown')errors.push(message.params.exceptionDetails.exception?.description||message.params.exceptionDetails.text||'runtime exception');if(message.id&&pending.has(message.id)){const item=pending.get(message.id);pending.delete(message.id);message.error?item.reject(Error(message.error.message)):item.resolve(message.result);}};
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Network.setCacheDisabled',{cacheDisabled:true});
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate',{url:origin});
  await until("!document.querySelector('#own-toolbar')?.hidden && document.querySelector('#detail-heading')?.textContent==='Synthetic Legacy'",'synthetic migrated vehicle loaded');
  const base='/garage-api/vehicles/7';

  const recordBefore=(await api(`${base}/records/11/measurement`)).record;
  const statusBefore=await api(`${base}/status`);
  await click('#logbook-toggle');
  await until("!document.querySelector('#logbook-panel').hidden && !!document.querySelector('#log-record-measurement-edit-11')",'record appears in history browser');
  await click('#log-record-measurement-edit-11');
  await until("document.querySelector('#own-title')?.textContent==='Kilometerstand zuordnen' && !!document.querySelector('#entry-candidateReadingId')",'legacy link confirmation editor');
  const selection=await value("({value:document.querySelector('#entry-candidateReadingId').value,options:[...document.querySelector('#entry-candidateReadingId').options].map(option=>option.value),checked:document.querySelector('#entry-provenanceConfirm').checked})");
  if(selection.value!==''||!selection.options.includes('17')||selection.checked)throw Error('Legacy candidate was missing or automatically selected: '+JSON.stringify(selection));
  await value("document.querySelector('#entry-candidateReadingId').value='17';document.querySelector('#entry-candidateReadingId').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#entry-provenanceConfirm').checked=true;document.querySelector('#entry-provenanceConfirm').dispatchEvent(new Event('change',{bubbles:true}))");
  await fill('#entry-measurement-reason','Synthetic owner confirmed the matching legacy source.');
  await click('#own-save');
  await until("!document.querySelector('#own-panel').hidden && document.querySelector('#own-title')?.textContent==='Datum / Stand korrigieren' && document.querySelector('#entry-measurement-odometer')?.value==='1234.125'",'explicit link saved and correction form reopened');
  await screenshot('linked-correction-form-mobile');
  const linkedInfo=await api(`${base}/records/11/measurement`);
  if(linkedInfo.correctionMode!=='linked'||linkedInfo.sourceReading.sourceRecordId!==11||linkedInfo.sourceReading.provenance!=='record')throw Error('Legacy link was not explicitly persisted');

  await fill('#entry-measurement-date','2025-04-06');
  await fill('#entry-measurement-odometer','1234.250');
  await fill('#entry-measurement-reason','Synthetic record date and reading verified together.');
  await save();
  await until("!document.querySelector('#history-panel').hidden && document.querySelector('#history-events').innerText.includes('Datum oder Stand korrigiert')",'record correction audit is visible');
  const linkedAfter=await api(`${base}/records/11/measurement`);
  const expectedRecord={...recordBefore,date:'2025-04-06',odometer:1234.25,revision:3};
  if(linkedAfter.record.date!==expectedRecord.date||linkedAfter.record.odometer!==expectedRecord.odometer||linkedAfter.record.revision!==expectedRecord.revision||linkedAfter.sourceReading.date!==expectedRecord.date||linkedAfter.sourceReading.odometerExact!=='1234.25'||linkedAfter.sourceReading.revision!==3||linkedAfter.sourceReading.sourceRecordId!==11)throw Error('Linked measurement did not persist exact paired correction: '+JSON.stringify(linkedAfter));
  if(JSON.stringify([linkedAfter.record.kind,linkedAfter.record.cost,linkedAfter.record.currency,linkedAfter.record.closedIssueId])!==JSON.stringify([recordBefore.kind,recordBefore.cost,recordBefore.currency,recordBefore.closedIssueId]))throw Error('Measurement correction changed unrelated record fields');
  if(JSON.stringify(await api(`${base}/status`))!==JSON.stringify(statusBefore))throw Error('Measurement correction changed manual readiness or issue state');
  const linkedHistory=await api(`${base}/history`);
  const linkedEvents=linkedHistory.events.filter(event=>event.action==='record.measurement-corrected');
  if(!linkedEvents.length||linkedEvents.at(-1).after.correctionReason!=='Synthetic record date and reading verified together.')throw Error('Linked correction reason/history missing');

  await value("document.querySelector('#logbook-type').value='odometer';document.querySelector('#logbook-type').dispatchEvent(new Event('change',{bubbles:true}));document.querySelector('#logbook-filters').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))");
  await until("document.querySelector('#logbook-records').innerText.includes('Synthetic old standalone reading') && !!document.querySelector('#log-odometer-resolve-18')",'unresolved standalone legacy reading appears');
  await click('#log-odometer-resolve-18');
  await until("!document.querySelector('#own-panel').hidden && document.querySelector('#own-title')?.textContent==='Herkunft bestätigen'",'legacy manual confirmation form');
  await value("document.querySelector('#entry-provenanceConfirm').checked=true;document.querySelector('#entry-provenanceConfirm').dispatchEvent(new Event('change',{bubbles:true}))");
  await fill('#entry-measurement-reason','Synthetic owner confirms this was recorded independently.');
  await save();
  await until("!document.querySelector('#logbook-panel').hidden && !!document.querySelector('#log-odometer-edit-18')",'manual provenance appears after confirmation');
  const manualBefore=await api(`${base}/odometer/18`);
  if(manualBefore.reading.provenance!=='manual'||manualBefore.reading.sourceRecordId!==null)throw Error('Legacy reading manual provenance was not saved');
  await click('#log-odometer-edit-18');
  await until("!document.querySelector('#own-panel').hidden && document.querySelector('#entry-measurement-note')",'manual reading correction form');
  await fill('#entry-measurement-date','2025-03-02');
  await fill('#entry-measurement-odometer','901.25');
  await fill('#entry-measurement-note','Synthetic manually corrected note');
  await fill('#entry-measurement-reason','Synthetic handwritten log checked.');
  await save();
  const manualAfter=await api(`${base}/odometer/18`);
  if(manualAfter.reading.date!=='2025-03-02'||manualAfter.reading.odometerExact!=='901.25'||manualAfter.reading.note!=='Synthetic manually corrected note'||manualAfter.reading.revision!==3||manualAfter.reading.provenance!=='manual')throw Error('Manual reading correction did not persist');
  const projectedVehicle=(await api(`${base}/summary`)).vehicle;
  if(projectedVehicle.odometer!==1234.25)throw Error('Manual backdated correction changed the latest reading projection');
  const allHistory=await api(`${base}/history`);
  const actions=allHistory.events.map(event=>event.action);
  if(!actions.includes('odometer.provenance-confirmed')||!actions.includes('odometer.corrected')||actions.filter(action=>action==='record.measurement-corrected').length!==1)throw Error('Expected correction and provenance audit actions are missing');
  if(!await value("document.querySelector('#history-events').innerText.includes('Herkunft des Kilometerstands bestätigt') && document.querySelector('#history-events').innerText.includes('Kilometerstand korrigiert')"))throw Error('Manual provenance/correction audit details are not rendered');
  await screenshot('measurement-history-mobile');

  await call('Page.reload');
  await until("document.querySelector('#detail-heading')?.textContent==='Synthetic Legacy' && !document.querySelector('#detail-content').hidden",'updated synthetic vehicle reloads');
  const afterReload=await api(`${base}/records/11/measurement`);
  const manualReload=await api(`${base}/odometer/18`);
  if(afterReload.record.date!=='2025-04-06'||afterReload.sourceReading.odometerExact!=='1234.25'||manualReload.reading.date!=='2025-03-02'||manualReload.reading.provenance!=='manual')throw Error('Measurement corrections did not persist across reload');

  for(const width of [320,390,768,1280]){await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});await delay(120);if(await value('document.documentElement.scrollWidth>innerWidth'))throw Error(`Horizontal overflow at ${width}px`);}
  if(errors.length)throw Error('Browser reported JavaScript errors: '+JSON.stringify(errors));
  console.log('PASS: schema-4 legacy-link confirmation, linked and manual exact corrections, explicit reasons/audit, readiness and issue preservation, latest-reading projection, reload persistence, and responsive widths 320/390/768/1280. Synthetic data only.');
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{if(socket)socket.close();if(browser)browser.kill();});
