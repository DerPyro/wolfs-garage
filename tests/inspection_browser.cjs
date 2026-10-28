// Synthetic real-Chromium acceptance. Serve a fresh schema-4 test database
// with tests/inspection_preview.py on loopback port 18988.
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const fs = require('fs');
const browserDir = fs.readdirSync('/ms-playwright').find(x => x.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
let browser, socket, sequence = 0;
const pending = new Map(), errors = [];

function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence; pending.set(id, {resolve, reject}); socket.send(JSON.stringify({id, method, params}));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Error(`CDP timeout: ${method}`)); } }, 10000).unref();
  });
}
async function value(expression) {
  const result = await call('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (result.exceptionDetails) throw Error(result.exceptionDetails.text);
  return result.result.value;
}
async function until(expression, label) {
  for (let i = 0; i < 120; i++) {
    await delay(100);
    try { if (await value(expression)) return; } catch (_) { /* wait for DOM/network transition */ }
  }
  let state = null;
  try { state = await value(`({heading:document.querySelector('#detail-heading')?.textContent, message:document.querySelector('#inspection-message')?.textContent, editor:!document.querySelector('#own-panel')?.hidden, cards:document.querySelectorAll('#vehicles .vehicle-card').length, errors:${JSON.stringify(errors)}})`); } catch (_) {}
  throw Error(`Timed out waiting for ${label}: ${JSON.stringify(state)}`);
}
function shiftMonth(isoDate, offset) {
  const [year, month] = isoDate.slice(0, 7).split('-').map(Number);
  const index = year * 12 + month - 1 + offset;
  const nextYear = Math.floor(index / 12), nextMonth = index % 12 + 1;
  return `${String(nextYear).padStart(4, '0')}-${String(nextMonth).padStart(2, '0')}`;
}
async function request(path, method, payload) {
  const write = method !== 'GET';
  const headers = write ? {'Content-Type':'application/json','X-Garage-Request':'1'} : {Accept:'application/json'};
  const body = write ? JSON.stringify(payload) : null;
  return await value(`(async()=>{const response=await fetch(${JSON.stringify(path)},{method:${JSON.stringify(method)},headers:${JSON.stringify(headers)}${write?`,body:${JSON.stringify(body)}`:''}});let body;try{body=await response.json()}catch{}if(!response.ok)throw Error(${JSON.stringify(path)}+' failed ('+response.status+'): '+JSON.stringify(body));return body})()`);
}
async function selectModel(model) {
  await value(`(()=>{const card=Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(node=>node.getAttribute('aria-label')?.includes(${JSON.stringify(model)}));if(!card)throw Error('Vehicle card not found: '+${JSON.stringify(model)});card.click()})()`);
  await until(`!document.querySelector('#detail').hidden && document.querySelector('#detail-heading').textContent.endsWith(${JSON.stringify(model)}) && !document.querySelector('#inspection-panel').hidden`, `detail ${model}`);
}
async function saveRenewal(model, dueMonth) {
  await selectModel(model);
  await value("document.querySelector('#vehicle-edit').click()");
  await until("!document.querySelector('#own-panel').hidden && !!document.querySelector('#entry-inspectionDueMonth')", 'inspection month editor');
  await value(`(()=>{const field=document.querySelector('#entry-inspectionDueMonth');field.value=${JSON.stringify(dueMonth)};field.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#own-form').requestSubmit()})()`);
  await until(`document.querySelector('#own-panel').hidden && document.querySelector('#detail-heading').textContent.endsWith(${JSON.stringify(model)}) && !document.querySelector('#inspection-panel').hidden && document.querySelector('#inspection-message').textContent.includes('noch')`, 'renewed inspection projection');
  return await value(`(async()=>{const vehicles=await(await fetch('/garage-api/vehicles')).json();return vehicles.vehicles.find(v=>v.model===${JSON.stringify(model)})})()`);
}

async function main() {
  if (!binary) throw Error('Chromium binary not found under /ms-playwright');
  browser = spawn(binary, ['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--remote-debugging-port=9244','--remote-allow-origins=*','--user-data-dir=/tmp/wg-inspection-browser','about:blank'], {stdio:'ignore'});
  let target;
  for(let i=0;i<80;i++){try{const response=await fetch('http://127.0.0.1:9244/json/new?about:blank',{method:'PUT'});if(response.ok){target=await response.json();break}}catch{}await delay(100)}
  if(!target)throw Error('Chromium start failed');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject});
  socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.id&&pending.has(data.id)){const p=pending.get(data.id);pending.delete(data.id);data.error?p.reject(Error(data.error.message)):p.resolve(data.result)}else if(data.method==='Runtime.exceptionThrown'){errors.push(data.params.exceptionDetails.exception?.description||'runtime exception')}};
  await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate',{url:'http://127.0.0.1:18988'});
  await until("document.querySelector('#status')?.textContent.includes('leer')", 'synthetic empty garage');

  const initial=await request('/garage-api/vehicles','POST',{make:'Synthetic',model:'Case A',vehicleType:'Limousine',odometerUnit:'km'});
  const asOf=initial.inspection.asOf;
  const thisMonth=asOf.slice(0,7), lastMonth=shiftMonth(asOf,-1), twoMonthsBack=shiftMonth(asOf,-2), thirteenAhead=shiftMonth(asOf,13);
  const cases=[
    {model:'Case B',month:thirteenAhead,readiness:'unknown'},
    {model:'Case C',month:thisMonth,readiness:'ready'},
    {model:'Case D',month:lastMonth,readiness:'ready'},
    {model:'Case E',month:twoMonthsBack,readiness:'ready'},
    {model:'Case F',month:twoMonthsBack,readiness:'not_ready'},
  ];
  for(const item of cases){
    const vehicle=await request('/garage-api/vehicles','POST',{make:'Synthetic',model:item.model,vehicleType:'Limousine',odometerUnit:'km',inspectionDueMonth:item.month});
    const issues=(item.model==='Case E'||item.model==='Case F')?[{text:'Synthetic retained open issue'}]:[];
    await request(`/garage-api/vehicles/${vehicle.id}/status`,'PUT',{readiness:item.readiness,issues,revision:0});
  }
  await call('Page.reload');
  await until(`document.querySelectorAll('#vehicles .vehicle-card').length===6 && document.querySelectorAll('.card-inspection').length===6`, 'six inspection cards');
  const cardFacts=await value(`(()=>{const cards=Array.from(document.querySelectorAll('#vehicles .vehicle-card'));const a=cards.find(x=>x.getAttribute('aria-label')?.includes('Case A'));const b=cards.find(x=>x.getAttribute('aria-label')?.includes('Case B'));return {a:a?.getBoundingClientRect().height,b:b?.getBoundingClientRect().height,states:cards.map(x=>x.querySelector('.card-inspection')?.className)}})()`);
  if(cardFacts.a!==cardFacts.b)throw Error('Inspection icon changed vehicle-card height: '+JSON.stringify(cardFacts));
  for(const expected of ['state-unknown','state-upcoming','state-due','state-overdue','state-blocking'])if(!cardFacts.states.some(x=>x.includes(expected)))throw Error(`Missing card status ${expected}: ${cardFacts.states}`);
  await value("document.querySelector('#vehicles').scrollIntoView({block:'start'})");await delay(150);
  let shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/inspection-cards-mobile.png',Buffer.from(shot.data,'base64'));

  await selectModel('Case B');
  await value("document.querySelector('#inspection-panel').scrollIntoView({block:'center'})");await delay(150);
  shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/inspection-battery-mobile.png',Buffer.from(shot.data,'base64'));
  if(await value("document.querySelectorAll('#inspection-meter .inspection-meter-cell.filled').length")!==12)throw Error('Twelve-month preview did not clamp to 12');

  await selectModel('Case A');
  if(!await value("document.querySelector('#inspection-meter-wrap').hidden && document.querySelector('#inspection-message').textContent.includes('nicht erfasst')"))throw Error('Unknown month should have no guessed battery/deadline');
  await selectModel('Case C');
  if(await value("document.querySelectorAll('#inspection-meter .inspection-meter-cell.filled').length")!==0)throw Error('Due-this-month battery should be empty');
  await selectModel('Case D');
  if(!await value("document.querySelector('#inspection-message').textContent.includes('überfällig') && document.querySelector('#condition-readiness .readiness-badge').textContent.includes('Fahrbereit') && !document.querySelector('#vehicles .vehicle-card[aria-pressed=\"true\"] .card-readiness.not_ready')"))throw Error('First overdue month should remain ready until the blocking date');
  await selectModel('Case E');
  if(!await value("document.querySelector('#condition-readiness .readiness-badge').textContent.includes('Nicht fahrbereit') && document.querySelector('#inspection-message').textContent.includes('INOP')"))throw Error('Blocking inspection did not project INOP for a manually ready vehicle');
  const readyBefore=await value(`(async()=>{const vehicles=await(await fetch('/garage-api/vehicles')).json();return vehicles.vehicles.find(v=>v.model==='Case E')})()`);
  if(readyBefore.status.readiness!=='ready'||readyBefore.effectiveReadiness!=='not_ready'||readyBefore.status.issues.length!==1)throw Error('Raw manual status was not kept separate from the blocker');
  const renewedReady=await saveRenewal('Case E',thirteenAhead);
  if(renewedReady.status.readiness!=='ready'||renewedReady.effectiveReadiness!=='ready'||renewedReady.status.issues.length!==1)throw Error('Renewal changed raw readiness or issue data');
  await selectModel('Case F');
  const renewedNotReady=await saveRenewal('Case F',thirteenAhead);
  if(renewedNotReady.status.readiness!=='not_ready'||renewedNotReady.effectiveReadiness!=='not_ready')throw Error('Renewal cleared a manual not-ready assessment');
  const persisted=await request('/garage-api/vehicles/'+renewedNotReady.id,'GET');
  if(persisted.inspectionDueMonth!==thirteenAhead||persisted.status.issues.length!==1)throw Error('Renewed date or issue did not persist');

  for(const width of [320,390,768,1280]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});await delay(120);
    if(await value('document.documentElement.scrollWidth>innerWidth'))throw Error('Horizontal overflow at '+width);
    const heights=await value("Array.from(document.querySelectorAll('#vehicles .vehicle-card')).slice(0,2).map(x=>x.getBoundingClientRect().height)");
    if(heights[0]!==heights[1])throw Error('Compact inspection icon expands only one card at '+width+'px: '+heights);
    if(width===320){await value("Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(card=>card.getAttribute('aria-label')?.includes('Case F')).scrollIntoView({block:'center'})");await delay(150);shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/inspection-inop-card-320.png',Buffer.from(shot.data,'base64'));}
    console.log(width+'px inspection layout passed');
  }
  if(errors.length)throw Error('JavaScript errors: '+errors.join('; '));
  console.log('Unknown/due/overdue/blocking states, month editor, manual readiness separation, renewal, 12-month battery clamp: PASS');
}
main().catch(error=>{console.error(error.stack||error.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
