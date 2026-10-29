// Synthetic real-Chromium acceptance for editing and completing active work.
// Serve a fresh schema-5 database at http://127.0.0.1:18989 before running.
const fs = require('fs');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const browserDir = fs.readdirSync('/ms-playwright').find(name => name.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
let browser, socket, seq = 0, captureRecordPost = false;
const pending = new Map(), errors = [], recordPosts = [];

function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++seq; pending.set(id, {resolve, reject}); socket.send(JSON.stringify({id, method, params}));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Error(`CDP timeout: ${method}`)); } }, 10000).unref();
  });
}
async function value(expression) {
  const result = await call('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (result.exceptionDetails) throw Error(result.exceptionDetails.text);
  return result.result.value;
}
async function until(expression, label) {
  for (let i = 0; i < 120; i++) { await delay(100); try { if (await value(expression)) return; } catch (_) {} }
  let diagnostic = {};
  try { diagnostic = await value(`({title:document.querySelector('#own-title')?.textContent, ownMessage:document.querySelector('#own-message')?.textContent, issueRows:document.querySelectorAll('#condition-issues .condition-issue-row').length, detail:document.querySelector('#detail-heading')?.textContent, errors:${JSON.stringify(errors)}})`); } catch (error) { diagnostic = {error:String(error)}; }
  throw Error(`Timed out waiting for ${label}: ${JSON.stringify(diagnostic)}`);
}
async function request(path, method = 'GET', payload = null) {
  const write = method !== 'GET'; const headers = write ? {'Content-Type':'application/json','X-Garage-Request':'1'} : {Accept:'application/json'};
  const body = write ? JSON.stringify(payload) : null;
  return await value(`(async()=>{const response=await fetch(${JSON.stringify(path)},{method:${JSON.stringify(method)},headers:${JSON.stringify(headers)}${write?`,body:${JSON.stringify(body)}`:''}});let body;try{body=await response.json()}catch{}if(!response.ok)throw Error(${JSON.stringify(path)}+' failed ('+response.status+'): '+JSON.stringify(body));return body})()`);
}
async function snapshot(vehicleId) {
  return await value(`(async()=>{const base='/garage-api/vehicles/${vehicleId}';const [status,records,history]=await Promise.all([fetch(base+'/status').then(r=>r.json()),fetch(base+'/records').then(r=>r.json()),fetch(base+'/history').then(r=>r.json())]);return {status,records:records.records,events:history.events}})()`);
}
async function clickIssueButton(id, action) {
  const selector = `#issue-${action}-${encodeURIComponent(String(id))}`;
  await value(`(()=>{const button=document.querySelector(${JSON.stringify(selector)});if(!button)throw Error('Missing issue action '+${JSON.stringify(selector)});button.click()})()`);
}
async function main() {
  if (!binary) throw Error('Chromium binary not found under /ms-playwright');
  browser = spawn(binary, ['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--remote-debugging-port=9241','--remote-allow-origins=*','--user-data-dir=/tmp/wg-work-completion-chromium','about:blank'], {stdio:'ignore'});
  let target;
  for (let i = 0; i < 80; i++) { try { const response = await fetch('http://127.0.0.1:9241/json/new?about:blank',{method:'PUT'}); if (response.ok) { target=await response.json(); break; } } catch (_) {} await delay(100); }
  if (!target) throw Error('Chromium start failed');
  socket = new WebSocket(target.webSocketDebuggerUrl); await new Promise((resolve,reject) => { socket.onopen=resolve; socket.onerror=reject; });
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text || 'runtime exception');
    if (message.method === 'Network.requestWillBeSent' && captureRecordPost) {
      const request = message.params.request;
      if (request.method === 'POST' && new URL(request.url).pathname.endsWith('/records')) { try { recordPosts.push(JSON.parse(request.postData || '{}')); } catch (_) { recordPosts.push(null); } }
    }
    if (message.id && pending.has(message.id)) { const item=pending.get(message.id); pending.delete(message.id); message.error?item.reject(Error(message.error.message)):item.resolve(message.result); }
  };
  await call('Page.enable'); await call('Runtime.enable'); await call('Network.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate',{url:'http://127.0.0.1:18989/'});
  await until('!document.querySelector("#own-toolbar")?.hidden && document.querySelector("#status")?.innerText.includes("leer")','empty standalone garage');

  const today = (await request('/garage-api/work')).today;
  const plusDays = n => { const date=new Date(`${today}T00:00:00Z`); date.setUTCDate(date.getUTCDate()+n); return date.toISOString().slice(0,10); };
  const vehicle = await request('/garage-api/vehicles','POST',{make:'Synthetic',model:'Work Completion',vehicleType:'Limousine',odometerUnit:'km'});
  const initialStatus = await request(`/garage-api/vehicles/${vehicle.id}/status`);
  const targetText = 'Synthetic brake inspection';
  const otherText = 'Synthetic oil leak';
  const observedText = 'Synthetic rattle observation';
  const updatedText = 'Synthetic brake inspection reviewed';
  const createdStatus = await request(`/garage-api/vehicles/${vehicle.id}/status`,'PUT',{
    readiness:'ready', revision:initialStatus.revision,
    issues:[
      {text:targetText,dueDate:plusDays(3),severity:'repair',lifecycle:'open'},
      {text:otherText,dueDate:plusDays(-2),severity:'critical',lifecycle:'open'},
      {text:observedText,dueDate:null,severity:'observation',lifecycle:'observed'},
    ],
  });
  const targetIssue = createdStatus.issues.find(issue=>issue.text===targetText);
  const otherIssuesBefore = createdStatus.issues.filter(issue=>issue.id!==targetIssue.id);
  await call('Page.reload');
  await until(`document.querySelector('#detail-heading')?.textContent==='Synthetic Work Completion' && document.querySelectorAll('#condition-issues .condition-issue-row').length===3`,'vehicle and three issues loaded');

  const widths=[320,390,768,1280], originalHeights={};
  for (const width of widths) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700}); await delay(100);
    if (await value('document.documentElement.scrollWidth>innerWidth')) throw Error(`Horizontal overflow before actions at ${width}px`);
    originalHeights[width]=await value(`(()=>{const card=Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(node=>node.getAttribute('aria-label')?.includes('Work Completion'));return card?.getBoundingClientRect().height})()`);
    if (!originalHeights[width]) throw Error(`Could not measure vehicle card at ${width}px`);
  }
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  const base = await snapshot(vehicle.id);

  // Editing opens the existing condition form on the selected row and focuses it.
  await clickIssueButton(targetIssue.id,'edit');
  const inputId=`issue-edit-${encodeURIComponent(String(targetIssue.id))}-text`;
  await until(`!document.querySelector('#condition-form').hidden && document.activeElement?.id===${JSON.stringify(inputId)}`,'selected issue editor focused');
  await value(`document.querySelector(${JSON.stringify(`#${inputId}`)}).value=${JSON.stringify(updatedText)}`);
  await value('document.querySelector("#condition-save").click()');
  await until(`document.querySelector('#condition-form').hidden && Array.from(document.querySelectorAll('#condition-issues .condition-issue-text')).some(node=>node.textContent===${JSON.stringify(updatedText)})`,'issue edit saved');
  const edited = await request(`/garage-api/vehicles/${vehicle.id}/status`);
  const editedTarget=edited.issues.find(issue=>issue.id===targetIssue.id);
  if (!editedTarget || editedTarget.text!==updatedText || editedTarget.dueDate!==targetIssue.dueDate || editedTarget.severity!==targetIssue.severity || editedTarget.lifecycle!==targetIssue.lifecycle || edited.readiness!=='ready') throw Error('Editing issue text changed its saved metadata or readiness');
  for (const previous of otherIssuesBefore) { const actual=edited.issues.find(issue=>issue.id===previous.id); if (JSON.stringify(actual)!==JSON.stringify(previous)) throw Error(`Editing changed another issue: ${previous.text}`); }

  // Cancel a second edit and confirm it writes no state, record or history.
  await clickIssueButton(targetIssue.id,'edit');
  await until(`!document.querySelector('#condition-form').hidden && document.activeElement?.id===${JSON.stringify(inputId)}`,'reopened issue editor');
  const cancelledEditText='Synthetic unsaved edit';
  await value(`document.querySelector(${JSON.stringify(`#${inputId}`)}).value=${JSON.stringify(cancelledEditText)};document.querySelector('#condition-cancel').click()`);
  await until(`document.querySelector('#condition-form').hidden && document.activeElement?.id===${JSON.stringify(`issue-edit-${encodeURIComponent(String(targetIssue.id))}`)}`,'cancelled edit returns focus');
  const afterEditCancel=await snapshot(vehicle.id);
  if (afterEditCancel.status.revision!==edited.revision || afterEditCancel.records.length!==base.records.length || afterEditCancel.events.length!==base.events.length+1 || afterEditCancel.status.issues.find(issue=>issue.id===targetIssue.id)?.text!==updatedText) throw Error('Cancelling issue edit performed a write');

  // The completion form drafts the selected issue. Opening/cancelling it is read-only.
  const openerId=`issue-complete-${encodeURIComponent(String(targetIssue.id))}`;
  await clickIssueButton(targetIssue.id,'complete');
  await until(`!document.querySelector('#own-panel').hidden && document.querySelector('#own-title').textContent==='Punkt abschließen' && document.querySelector('#entry-closeIssueId')`,'completion form opened');
  const draft=await value(`(()=>{const field=document.querySelector('#entry-closeIssueId');return {description:document.querySelector('#entry-description').value,date:document.querySelector('#entry-date').value,kind:document.querySelector('#entry-kind').value,issueId:field.value,locked:field.disabled||field.hidden||field.type==='hidden',save:document.querySelector('#own-save').textContent}})()`);
  if (draft.description!==updatedText || draft.date!==today || draft.kind!=='' || draft.issueId!==targetIssue.id || !draft.locked || !draft.save.includes('Punkt abschließen')) throw Error('Completion form is not a fixed, editable draft of the selected issue: '+JSON.stringify(draft));
  const beforeCompletion=await snapshot(vehicle.id);
  if (beforeCompletion.status.revision!==edited.revision || beforeCompletion.records.length!==afterEditCancel.records.length || beforeCompletion.events.length!==afterEditCancel.events.length) throw Error('Opening completion form wrote data');
  await value('document.querySelector("#own-cancel").click()');
  await until(`document.querySelector('#own-panel').hidden && document.activeElement?.id===${JSON.stringify(openerId)}`,'completion cancel returns focus');
  const afterCompletionCancel=await snapshot(vehicle.id);
  if (afterCompletionCancel.status.revision!==beforeCompletion.status.revision || afterCompletionCancel.records.length!==beforeCompletion.records.length || afterCompletionCancel.events.length!==beforeCompletion.events.length) throw Error('Cancelling completion wrote data');

  // Save a reviewed work description with no odometer or cost; check the exact close target/revision sent.
  await clickIssueButton(targetIssue.id,'complete');
  await until(`!document.querySelector('#own-panel').hidden && document.querySelector('#entry-closeIssueId')?.value===${JSON.stringify(targetIssue.id)}`,'completion form reopened');
  const recordDescription='Synthetic brake pads replaced';
  await value(`document.querySelector('#entry-kind').value='repair';document.querySelector('#entry-description').value=${JSON.stringify(recordDescription)}`);
  captureRecordPost=true;
  await value('document.querySelector("#own-save").click()');
  await until(`document.querySelector('#own-panel').hidden && !document.querySelector('#detail-content').hidden && !document.querySelector('#history-panel').hidden && document.querySelector('#services').innerText.includes(${JSON.stringify(recordDescription)})`,'saved work visible in history and latest work');
  captureRecordPost=false;
  if (recordPosts.length!==1 || recordPosts[0]?.closeIssueId!==targetIssue.id || recordPosts[0]?.statusRevision!==beforeCompletion.status.revision) throw Error('Completion POST did not bind the selected issue and expected status revision: '+JSON.stringify(recordPosts));
  if (recordPosts[0].date!==today || recordPosts[0].description!==recordDescription || recordPosts[0].odometer!==undefined || recordPosts[0].cost!==undefined) throw Error('Completion POST did not retain the reviewed date/description or omit optional values');

  const result = await value(`(async()=>{const base='/garage-api/vehicles/${vehicle.id}';const [status,records,history,work]=await Promise.all([fetch(base+'/status').then(r=>r.json()),fetch(base+'/records').then(r=>r.json()),fetch(base+'/history').then(r=>r.json()),fetch('/garage-api/work').then(r=>r.json())]);return {status,records:records.records,events:history.events,active:work.items.filter(item=>String(item.vehicleId)==='${vehicle.id}')}})()`);
  if (result.status.readiness!=='ready' || result.status.revision!==beforeCompletion.status.revision+1 || result.status.issues.some(issue=>issue.id===targetIssue.id)) throw Error('Completion did not close only the selected issue or changed readiness');
  for (const previous of otherIssuesBefore) { const actual=result.status.issues.find(issue=>issue.id===previous.id); if (JSON.stringify(actual)!==JSON.stringify(previous)) throw Error(`Completion changed another issue: ${previous.text}`); }
  const record=result.records.find(item=>item.description===recordDescription);
  if (!record || record.closedIssueId!==targetIssue.id || record.date!==today || record.odometer!==null || record.cost!==null || record.currency!==null) throw Error('Completed work record did not preserve expected values: '+JSON.stringify(record));
  if (result.active.some(item=>String(item.id)===String(targetIssue.id)) || otherIssuesBefore.some(issue=>!result.active.some(item=>String(item.id)===String(issue.id)))) throw Error('Active-work projection did not remove only the selected issue');
  const completionActions=result.events.slice(-2).map(item=>item.action);
  if (completionActions.length!==2 || !completionActions.includes('issue.completed') || !completionActions.includes('record.created')) throw Error('Completion history does not contain both closure and record events: '+JSON.stringify(completionActions));
  if (!await value(`Array.from(document.querySelectorAll('#history-events .history-event h4')).some(node=>node.textContent==='Offenen Punkt abgeschlossen') && Array.from(document.querySelectorAll('#history-events .history-event h4')).some(node=>node.textContent==='Arbeit dokumentiert')`)) throw Error('Both completion events are not visible in the history panel');

  await value('document.querySelector("#logbook-toggle").click()');
  await until(`!document.querySelector('#logbook-panel').hidden && Array.from(document.querySelectorAll('#logbook-records .logbook-row-title')).some(node=>node.textContent===${JSON.stringify(recordDescription)})`,'record appears in logbook');
  await call('Page.reload');
  await until(`document.querySelector('#detail-heading')?.textContent==='Synthetic Work Completion' && document.querySelectorAll('#condition-issues .condition-issue-row').length===2 && document.querySelector('#services').innerText.includes(${JSON.stringify(recordDescription)})`,'completed state persisted after reload');
  await value('document.querySelector("#logbook-toggle").click()');
  await until(`!document.querySelector('#logbook-panel').hidden && Array.from(document.querySelectorAll('#logbook-records .logbook-row-title')).some(node=>node.textContent===${JSON.stringify(recordDescription)})`,'logbook record persisted after reload');
  await value('document.querySelector("#history-toggle").click()');
  await until(`!document.querySelector('#history-panel').hidden && Array.from(document.querySelectorAll('#history-events .history-event h4')).some(node=>node.textContent==='Offenen Punkt abgeschlossen') && Array.from(document.querySelectorAll('#history-events .history-event h4')).some(node=>node.textContent==='Arbeit dokumentiert')`,'completion history persisted after reload');

  for (const width of widths) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700}); await delay(120);
    if (await value('document.documentElement.scrollWidth>innerWidth')) throw Error(`Horizontal overflow after completion at ${width}px`);
    const height=await value(`(()=>{const card=Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(node=>node.getAttribute('aria-label')?.includes('Work Completion'));return card?.getBoundingClientRect().height})()`);
    if (height!==originalHeights[width]) throw Error(`Vehicle card height changed at ${width}px: ${originalHeights[width]} -> ${height}`);
    console.log(`${width}px work-completion layout passed`);
  }
  if (errors.length) throw Error('JavaScript errors: '+errors.join('; '));
  console.log('Issue edit focus/cancel, explicit completion cancel/save, selected issue closure, metadata/readiness preservation, history/logbook persistence: PASS');
}
main().catch(error=>{captureRecordPost=false;console.error(error.stack||error.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
