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
  try { state = await value(`(()=>{const toolbar=document.querySelector('#own-detail-actions'),rect=toolbar?.getBoundingClientRect();return {heading:document.querySelector('#detail-heading')?.textContent,message:document.querySelector('#inspection-message')?.textContent,editor:!document.querySelector('#own-panel')?.hidden,cards:document.querySelectorAll('#vehicles .vehicle-card').length,scrollY,scrollHeight:document.documentElement.scrollHeight,innerHeight,toolbar:rect&&{top:rect.top,bottom:rect.bottom,height:rect.height},activeElement:document.activeElement?.id||document.activeElement?.getAttribute('aria-label'),errors:${JSON.stringify(errors)}}})()`); } catch (_) {}
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
  await until(`!document.querySelector('#detail').hidden && document.querySelector('#detail-heading').textContent.endsWith(${JSON.stringify(model)}) && !document.querySelector('#inspection-panel').hidden && document.querySelector('#inspection-message').textContent.trim() && document.querySelector('#inspection-panel').children.length===1 && !document.querySelector('#inspection-meter')`, `compact detail ${model}`);
}
function lastDayLabel(month) {
  const [year,number]=month.split('-').map(Number), day=new Date(Date.UTC(year,number,0)).getUTCDate();
  return `${String(day).padStart(2,'0')}.${String(number).padStart(2,'0')}.${year}`;
}
async function assertSummary(model, expected, label=model) {
  await selectModel(model);
  const summary=await value("document.querySelector('#inspection-message').textContent.trim()");
  if(!expected.every(fragment=>summary.includes(fragment)))throw Error(`Compact HU summary for ${label} is incomplete: ${summary}`);
  if(await value("!!document.querySelector('#inspection-meter') || !!document.querySelector('#inspection-asof') || document.querySelector('#inspection-panel').children.length!==1"))throw Error('HU detail still contains a meter, duplicate as-of date, or extra panel content');
  return summary;
}
async function saveRenewal(model, dueMonth) {
  await selectModel(model);
  await value("document.querySelector('#vehicle-edit').click()");
  await until("!document.querySelector('#own-panel').hidden && !!document.querySelector('#entry-inspectionDueMonth')", 'inspection month editor');
  await value(`(()=>{const field=document.querySelector('#entry-inspectionDueMonth');field.value=${JSON.stringify(dueMonth)};field.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#own-form').requestSubmit()})()`);
  await until(`document.querySelector('#own-panel').hidden && document.querySelector('#detail-heading').textContent.endsWith(${JSON.stringify(model)}) && !document.querySelector('#inspection-panel').hidden && document.querySelector('#inspection-message').textContent.includes('fällig in circa')`, 'renewed inspection projection');
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
  await call('Page.addScriptToEvaluateOnNewDocument',{source:'window.__garageOriginalSetInterval=window.setInterval.bind(window);window.setInterval=(callback,delay,...args)=>{if(delay===60000)window.__garageInspectionRefreshTick=callback;return window.__garageOriginalSetInterval(callback,delay,...args)}'});
  await call('Page.navigate',{url:'http://127.0.0.1:18988'});
  await until("document.querySelector('#status')?.textContent.includes('leer')", 'synthetic empty garage');

  const initial=await request('/garage-api/vehicles','POST',{make:'Synthetic',model:'Case A',vehicleType:'Limousine',odometerUnit:'km'});
  const asOf=initial.inspection.asOf;
  const thisMonth=asOf.slice(0,7), lastMonth=shiftMonth(asOf,-1), twoMonthsBack=shiftMonth(asOf,-2), thirteenAhead=shiftMonth(asOf,13);
  const cases=[
    {model:'Case B',month:thirteenAhead,readiness:'unknown'},
    {model:'Case G',month:shiftMonth(asOf,24),readiness:'unknown'},
    {model:'Case H',month:shiftMonth(asOf,1),readiness:'unknown'},
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
  await until(`document.querySelectorAll('#vehicles .vehicle-card').length===8 && document.querySelectorAll('.card-inspection-progress').length===8`, 'eight inspection cards');
  await until(`document.querySelector('#detail-heading').textContent.endsWith('Case A') && !document.querySelector('#inspection-panel').hidden && document.querySelector('#inspection-message').textContent.includes('nicht eingetragen') && !document.querySelector('#refresh').disabled && !document.querySelector('#detail-content').hidden && document.querySelector('#work-status').textContent.includes('Stand:')`, 'initial default vehicle selection and load complete');
  await delay(120);
  if(await value('window.scrollY>2'))throw Error('Initial vehicle load scrolled away from the page start');
  await value("document.querySelector('#vehicles .vehicle-card:nth-child(5)').scrollIntoView({block:'center'})");await delay(300);
  const scrollBeforeRefresh=await value('window.scrollY');
  if(!await value("typeof window.__garageInspectionRefreshTick==='function'"))throw Error('Scheduled inspection refresh callback was not registered');
  if(!await value('window.__garageInspectionRefreshTick()'))throw Error('Scheduled HU refresh did not execute');
  const scrollAfterRefresh=await value('window.scrollY');
  if(Math.abs(scrollAfterRefresh-scrollBeforeRefresh)>1)throw Error(`Automatic inspection refresh changed scroll position: ${scrollBeforeRefresh} -> ${scrollAfterRefresh}`);
  await value('window.scrollTo(0,0)');await delay(120);
  const cardFacts=await value(`(()=>{const cards=Array.from(document.querySelectorAll('#vehicles .vehicle-card'));const a=cards.find(x=>x.getAttribute('aria-label')?.includes('Case A'));const b=cards.find(x=>x.getAttribute('aria-label')?.includes('Case B'));return {a:a?.getBoundingClientRect().height,b:b?.getBoundingClientRect().height,labels:cards.map(x=>x.getAttribute('aria-label'))}})()`);
  if(cardFacts.a!==cardFacts.b)throw Error('Inspection icon changed vehicle-card height: '+JSON.stringify(cardFacts));
  for(const expected of ['nicht eingetragen','fällig in circa 13 Monaten','fällig diesen Monat','überfällig seit circa 1 Monat','automatisch INOP ab'])if(!cardFacts.labels.some(x=>x.includes(expected)))throw Error(`Missing card inspection summary ${expected}: ${cardFacts.labels}`);
  const cardBars=await value("(()=>{const cards=Array.from(document.querySelectorAll('#vehicles .vehicle-card'));return cards.map(card=>{const wrap=card.querySelector('.card-inspection-progress'),cells=Array.from(wrap?.querySelectorAll('.card-inspection-cell')||[]),firstFilled=cells.find(cell=>cell.classList.contains('filled')),marker=wrap?.querySelector('.card-inspection-marker'),barRect=wrap?.getBoundingClientRect(),markerRect=marker?.getBoundingClientRect();return {model:card.getAttribute('aria-label'),count:cells.length,filled:cells.map((cell,index)=>cell.classList.contains('filled')?index:-1).filter(index=>index>=0),unknown:wrap?.classList.contains('unknown'),expired:wrap?.classList.contains('expired'),due:wrap?.classList.contains('due'),level:[...(wrap?.classList||[])].find(name=>name.startsWith('level-')),color:firstFilled?getComputedStyle(firstFilled).backgroundColor:null,marker:marker?.textContent||null,centered:!!marker&&Math.abs(markerRect.x+markerRect.width/2-(barRect.x+barRect.width/2))<1}})})()");
  const cardB=cardBars.find(item=>item.model?.includes('Case B')),cardA=cardBars.find(item=>item.model?.includes('Case A')),cardG=cardBars.find(item=>item.model?.includes('Case G')),cardH=cardBars.find(item=>item.model?.includes('Case H')),cardC=cardBars.find(item=>item.model?.includes('Case C')),cardD=cardBars.find(item=>item.model?.includes('Case D')),cardE=cardBars.find(item=>item.model?.includes('Case E'));
  const red=cardH?.color?.match(/\d+/g)?.map(Number),purple=cardA?.color?.match(/\d+/g)?.map(Number),expiredRed=cardD?.color?.match(/\d+/g)?.map(Number),yellow=cardC?.color?.match(/\d+/g)?.map(Number);
  if(cardBars.some(item=>item.count!==24)||cardB?.filled.length!==13||cardB.filled[0]!==11||cardB.filled.at(-1)!==23||cardG?.filled.length!==24||cardH?.level!=='level-1'||cardH.filled.length!==1||cardH.filled[0]!==23||!red||red[0]<=red[1]||red[0]<=red[2]||!cardA?.unknown||cardA.filled.length!==24||cardA.marker!=='?'||!cardA.centered||!purple||purple[2]<=purple[0]||!cardD?.expired||cardD.filled.length!==24||cardD.marker!=='!'||!cardD.centered||!expiredRed||expiredRed[0]<=expiredRed[1]||expiredRed[0]<=expiredRed[2]||!cardE?.expired||cardE.marker!=='!'||!cardC?.due||cardC.filled.length!==24||cardC.marker||!yellow||yellow[0]<=yellow[2]||yellow[1]<=yellow[2])throw Error('Card bars do not match scale and status overrides: '+JSON.stringify(cardBars));
  await value("document.querySelector('#vehicles').scrollIntoView({block:'start'})");await delay(150);
  let shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/inspection-cards-mobile.png',Buffer.from(shot.data,'base64'));

  await value(`(()=>{const card=(model)=>Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(node=>node.getAttribute('aria-label')?.includes(model));card('Case B').click();card('Case H').click()})()`);
  await until(`(()=>{const toolbar=document.querySelector('#own-detail-actions'),rect=toolbar.getBoundingClientRect();return document.querySelector('#detail-heading').textContent.endsWith('Case H') && !document.querySelector('#inspection-panel').hidden && rect.top>=-2 && rect.bottom<=innerHeight+2 && window.scrollY>0 && !!document.activeElement.closest('#own-detail-actions')})()`, 'rapid selection scrolls to current vehicle actions');
  const scrollCheck=await value("(()=>{const toolbar=document.querySelector('#own-detail-actions'),rect=toolbar.getBoundingClientRect();return {selected:document.querySelector('#vehicles .vehicle-card[aria-pressed=\"true\"]')?.getAttribute('aria-label'),scrollY,innerHeight,scrollHeight:document.documentElement.scrollHeight,toolbar:{top:rect.top,bottom:rect.bottom,height:rect.height},focused:!!document.activeElement.closest('#own-detail-actions')}})()");
  if(!scrollCheck.selected?.includes('Case H')||scrollCheck.scrollY<=0||scrollCheck.toolbar.top < -2||scrollCheck.toolbar.bottom > scrollCheck.innerHeight+2||!scrollCheck.focused)throw Error('Rapid card selection did not leave the selected vehicle and action toolbar in view: '+JSON.stringify(scrollCheck));
  await assertSummary('Case B',[lastDayLabel(thirteenAhead),'fällig in circa 13 Monaten']);
  await assertSummary('Case G',[lastDayLabel(shiftMonth(asOf,24)),'fällig in circa 24 Monaten']);
  await assertSummary('Case H',[lastDayLabel(shiftMonth(asOf,1)),'fällig in circa 1 Monat']);
  await assertSummary('Case A',['nicht eingetragen']);
  await assertSummary('Case C',[lastDayLabel(thisMonth),'fällig diesen Monat']);
  await selectModel('Case D');
  if(!await value(`document.querySelector('#inspection-message').textContent.includes('${lastDayLabel(lastMonth)}') && document.querySelector('#inspection-message').textContent.includes('überfällig seit circa 1 Monat') && document.querySelector('#condition-readiness .readiness-badge').textContent.includes('Fahrbereit') && !document.querySelector('#vehicles .vehicle-card[aria-pressed=\"true\"] .card-readiness.not_ready')`))throw Error('First overdue month should show its date but remain ready until the blocking date');
  await selectModel('Case E');
  if(!await value(`document.querySelector('#inspection-message').textContent.includes('${lastDayLabel(twoMonthsBack)}') && document.querySelector('#inspection-message').textContent.includes('überfällig seit circa 2 Monaten') && document.querySelector('#inspection-message').textContent.includes('automatisch INOP ab') && document.querySelector('#condition-readiness .readiness-badge').textContent.includes('Nicht fahrbereit')`))throw Error('Blocking inspection summary or readiness projection is missing');
  const readyBefore=await value(`(async()=>{const vehicles=await(await fetch('/garage-api/vehicles')).json();return vehicles.vehicles.find(v=>v.model==='Case E')})()`);
  if(readyBefore.status.readiness!=='ready'||readyBefore.effectiveReadiness!=='not_ready'||readyBefore.status.issues.length!==1)throw Error('Raw manual status was not kept separate from the blocker');
  const renewedReady=await saveRenewal('Case E',thirteenAhead);
  if(renewedReady.status.readiness!=='ready'||renewedReady.effectiveReadiness!=='ready'||renewedReady.status.issues.length!==1)throw Error('Renewal changed raw readiness or issue data');
  await selectModel('Case F');
  const renewedNotReady=await saveRenewal('Case F',thirteenAhead);
  if(renewedNotReady.status.readiness!=='not_ready'||renewedNotReady.effectiveReadiness!=='not_ready')throw Error('Renewal cleared a manual not-ready assessment');
  const persisted=await request('/garage-api/vehicles/'+renewedNotReady.id,'GET');
  if(persisted.inspectionDueMonth!==thirteenAhead||persisted.status.issues.length!==1)throw Error('Renewed date or issue did not persist');
  await selectModel('Case A');
  const unavailable=await value(`(()=>{const vehicle=state.vehicles.find(item=>item.model==='Case A');vehicle.inspectionDueMonth='1900-01';renderCondition(vehicle.status);return {message:document.querySelector('#inspection-message').textContent,unavailable:document.querySelector('#inspection-message').classList.contains('unavailable'),meter:!!document.querySelector('#inspection-meter')}})()`);
  if(!unavailable.unavailable||unavailable.meter||!unavailable.message.includes('Status momentan nicht verfügbar'))throw Error('Invalid inspection projection did not show a clear unavailable summary: '+JSON.stringify(unavailable));

  for(const width of [320,390,768,1280]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});await delay(120);
    if(await value('document.documentElement.scrollWidth>innerWidth'))throw Error('Horizontal overflow at '+width);
    const heights=await value("Array.from(document.querySelectorAll('#vehicles .vehicle-card')).map(x=>x.getBoundingClientRect().height)");
    if(heights.some(height=>height!==heights[0]))throw Error('Inspection bars/markers changed or varied vehicle-card height at '+width+'px: '+heights);
    if(width===320){await value("Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(card=>card.getAttribute('aria-label')?.includes('Case F')).scrollIntoView({block:'center'})");await delay(150);shot=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync('/out/inspection-inop-card-320.png',Buffer.from(shot.data,'base64'));}
    console.log(width+'px inspection layout passed');
  }
  if(errors.length)throw Error('JavaScript errors: '+errors.join('; '));
  console.log('Compact HU summaries, no detail meter, explicit card selection scroll, scroll-free initial/timed refresh, rapid selection, unchanged 24-month card bars, stable card heights: PASS');
}
main().catch(error=>{console.error(error.stack||error.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
