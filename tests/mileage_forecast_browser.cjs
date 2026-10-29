// Synthetic real-Chromium acceptance; serve a fresh schema-6 app on loopback.
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const fs = require('fs');
const path = require('path');
const browserDir = fs.readdirSync('/ms-playwright').find(name => name.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
const origin = process.env.GARAGE_BROWSER_ORIGIN || 'http://127.0.0.1:18995';
let browser, socket, sequence = 0;
const pending = new Map(), errors = [];

function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, {resolve, reject});
    socket.send(JSON.stringify({id, method, params}));
    setTimeout(() => {
      if (pending.has(id)) { pending.delete(id); reject(Error(`CDP timeout: ${method}`)); }
    }, 10000).unref();
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
  try {
    state = await value(`(()=>({status:document.querySelector('#status')?.textContent||'',
      cards:document.querySelectorAll('#vehicles .vehicle-card').length,
      prompt:document.querySelector('#mileage-prompts')?.textContent||'',
      forecast:document.querySelector('#mileage-forecast')?.textContent||'',
      editor:!document.querySelector('#own-panel')?.hidden,
      errors:${JSON.stringify(errors)}}))()`);
  } catch (_) {}
  throw Error(`Timed out waiting for ${label}: ${JSON.stringify(state)}`);
}
async function request(path, method = 'GET', payload = null) {
  const write = method !== 'GET';
  return await value(`(async()=>{
    const response=await fetch(${JSON.stringify(path)},{method:${JSON.stringify(method)},
      headers:${JSON.stringify(write ? {'Content-Type':'application/json','X-Garage-Request':'1'} : {Accept:'application/json'})}
      ${write ? `,body:${JSON.stringify(JSON.stringify(payload))}` : ''}});
    let body;try{body=await response.json()}catch{}
    if(!response.ok)throw Error(${JSON.stringify(path)}+' failed ('+response.status+'): '+JSON.stringify(body));
    return body;
  })()`);
}
function addDays(iso, count) {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + count);
  return date.toISOString().slice(0, 10);
}
async function selectVehicle(model) {
  await value(`(()=>{const card=Array.from(document.querySelectorAll('#vehicles .vehicle-card'))
    .find(node=>node.getAttribute('aria-label')?.includes(${JSON.stringify(model)}));
    if(!card)throw Error('Missing vehicle card '+${JSON.stringify(model)});card.click()})()`);
  await until(`!document.querySelector('#detail').hidden &&
    document.querySelector('#detail-heading').textContent.includes(${JSON.stringify(model)}) &&
    document.querySelector('#mileage-forecast')`, `detail ${model}`);
}
async function setInput(selector, text) {
  await value(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});
    if(!input)throw Error('Missing input '+${JSON.stringify(selector)});
    input.value=${JSON.stringify(text)};input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}))})()`);
}
async function setCheckbox(selector, checked) {
  await value(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});
    if(!input)throw Error('Missing checkbox '+${JSON.stringify(selector)});
    input.checked=${checked};input.dispatchEvent(new Event('change',{bubbles:true}))})()`);
}
async function main() {
  if (!binary) throw Error('Chromium binary not found under /ms-playwright');
  browser = spawn(binary, ['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking',
    '--no-proxy-server','--remote-debugging-port=9250','--remote-allow-origins=*',
    '--user-data-dir=/tmp/wg-mileage-forecast-browser','about:blank'], {stdio:'ignore'});
  let target;
  for (let i = 0; i < 80; i++) {
    try {
      const response = await fetch('http://127.0.0.1:9250/json/new?about:blank', {method:'PUT'});
      if (response.ok) { target = await response.json(); break; }
    } catch (_) {}
    await delay(100);
  }
  if (!target) throw Error('Chromium start failed');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  socket.onmessage = event => {
    const data = JSON.parse(event.data);
    if (data.method === 'Runtime.exceptionThrown') errors.push(data.params.exceptionDetails.exception?.description || 'runtime exception');
    if (data.id && pending.has(data.id)) {
      const entry = pending.get(data.id); pending.delete(data.id);
      data.error ? entry.reject(Error(data.error.message)) : entry.resolve(data.result);
    }
  };
  await call('Page.enable'); await call('Runtime.enable');
  await call('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate', {url:origin});
  await until(`!document.querySelector('#own-toolbar')?.hidden &&
    document.querySelectorAll('#vehicles .vehicle-card').length===0`, 'empty synthetic Garage');

  let vehicle = await request('/garage-api/vehicles', 'POST', {
    make:'Synthetic', model:'Mileage Prompt', vehicleType:'Limousine', odometerUnit:'km', annualUsage:'3650',
  });
  const asOf = vehicle.mileageEstimate.asOf;
  const oldDate = addDays(asOf, -40);
  const actual = await request(`/garage-api/vehicles/${vehicle.id}/odometer`, 'POST', {
    date:oldDate, odometer:'1000.125', unit:'km', note:'Synthetic verified actual stand', commandId:crypto.randomUUID(),
  });
  vehicle = await request(`/garage-api/vehicles/${vehicle.id}`);
  const disabled = await request('/garage-api/vehicles', 'POST', {
    make:'Synthetic', model:'Prompt Disabled', vehicleType:'Limousine', odometerUnit:'mi',
    annualUsage:null, readingPromptDays:null,
  });
  await value("document.querySelector('#refresh').click()");
  await until(`document.querySelectorAll('#vehicles .vehicle-card').length===2`, 'two synthetic vehicles');

  const dueDate = addDays(oldDate, 30);
  const expectedEstimate = (1000.125 + 3650 * 40 / 365).toFixed(3);
  if (vehicle.readingPrompt.state !== 'due' || vehicle.readingPrompt.dueDate !== dueDate) {
    throw Error('Synthetic seed did not produce the expected due prompt: '+JSON.stringify(vehicle.readingPrompt));
  }
  const dueRow = `#mileage-prompt-${vehicle.id}`;
  const disabledRow = `#mileage-prompt-${disabled.id}`;
  await until(`document.querySelector(${JSON.stringify(dueRow)})?.classList.contains('state-due') &&
    !document.querySelector(${JSON.stringify(disabledRow)})`, 'due prompt shown and disabled prompt omitted');
  const screenshotPath = process.env.GARAGE_BROWSER_SCREENSHOT || '.sandbox/mileage-browser/mobile.png';
  fs.mkdirSync(path.dirname(screenshotPath), {recursive:true});
  const screenshot = await call('Page.captureScreenshot', {format:'png', captureBeyondViewport:true});
  fs.writeFileSync(screenshotPath, Buffer.from(screenshot.data, 'base64'));
  console.log(`Synthetic mobile screenshot: ${screenshotPath}`);

  await selectVehicle('Mileage Prompt');
  const forecast = await value(`(()=>{const node=document.querySelector('#mileage-forecast');
    return {text:node.textContent.trim(),estimated:node.classList.contains('state-estimated')}})()`);
  const localizedEstimate = Number(expectedEstimate).toLocaleString('de-DE',{minimumFractionDigits:3,maximumFractionDigits:3});
  if (!forecast.estimated || !forecast.text.includes(localizedEstimate) || !forecast.text.includes('km') ||
      !forecast.text.includes('letzter tatsächlicher Stand')) {
    throw Error('Forecast is not clearly labeled or does not match the read-only projection: '+JSON.stringify(forecast));
  }
  const readingsBeforeCancel = await request(`/garage-api/vehicles/${vehicle.id}/odometer`);
  const historyBeforeCancel = await request(`/garage-api/vehicles/${vehicle.id}/history`);
  await value(`document.querySelector('#mileage-prompt-action-${vehicle.id}').click()`);
  await until(`!document.querySelector('#own-panel').hidden && document.querySelector('#entry-odometer')`, 'blank actual-reading form');
  const draft = await value(`({date:document.querySelector('#entry-date').value,
    value:document.querySelector('#entry-odometer').value,
    placeholder:document.querySelector('#entry-odometer').placeholder})`);
  if (draft.date !== asOf || draft.value !== '' || draft.placeholder.toLocaleLowerCase('de-DE') !== 'abgelesener stand') {
    throw Error('Prompt form must default to today and a blank actual reading: '+JSON.stringify(draft));
  }
  await value("document.querySelector('#own-cancel').click()");
  await until("document.querySelector('#own-panel').hidden", 'prompt cancellation');
  if (JSON.stringify(await request(`/garage-api/vehicles/${vehicle.id}/odometer`)) !== JSON.stringify(readingsBeforeCancel) ||
      JSON.stringify(await request(`/garage-api/vehicles/${vehicle.id}/history`)) !== JSON.stringify(historyBeforeCancel)) {
    throw Error('Opening and cancelling a read prompt changed actual readings or history');
  }

  // Edit the saved annual rate through Garage. Omitted settings remain vehicle data.
  await selectVehicle('Mileage Prompt');
  await value("document.querySelector('#vehicle-edit').click()");
  await until("!document.querySelector('#own-panel').hidden && document.querySelector('#entry-annualUsage') && document.querySelector('#entry-readingPromptDays')", 'annual usage editor');
  await setInput('#entry-annualUsage','4000');
  await setCheckbox('#entry-readingPromptEnabled',true);
  await setInput('#entry-readingPromptDays','30');
  await value("document.querySelector('#own-form').requestSubmit()");
  await until(`(async()=>{const v=await(await fetch('/garage-api/vehicles/${vehicle.id}')).json();return v.annualUsage==='4000'&&v.readingPromptDays===30})()`, 'annual usage save');
  const changed = await request(`/garage-api/vehicles/${vehicle.id}`);
  if (changed.annualUsage !== '4000' || changed.readingPromptDays !== 30) throw Error('Saved vehicle estimate/prompt settings do not round-trip');

  // Save only the user-entered reading. Its new actual date resets the prompt age and anchor.
  const freshDueRow = `#mileage-prompt-${vehicle.id}`;
  await until(`document.querySelector(${JSON.stringify(freshDueRow)})?.classList.contains('state-due')`, 'due prompt after settings update');
  await value(`document.querySelector('#mileage-prompt-action-${vehicle.id}').click()`);
  await until(`!document.querySelector('#own-panel').hidden && document.querySelector('#entry-odometer')`, 'actual reading form after rate edit');
  await setInput('#entry-odometer','1300.125');
  await value("document.querySelector('#own-save').click()");
  await until(`document.querySelector('#own-panel').hidden`, 'actual reading save');
  await until(`(async()=>{const v=await(await fetch('/garage-api/vehicles/${vehicle.id}')).json();return v.readingPrompt.state==='not_due'&&v.mileageEstimate.anchor?.date===${JSON.stringify(asOf)}})()`, 'new actual reading resets prompt and anchor');
  const afterSave = await request(`/garage-api/vehicles/${vehicle.id}`);
  const actualRows = await request(`/garage-api/vehicles/${vehicle.id}/odometer`);
  if (actualRows.readings.length !== 2 || afterSave.mileageEstimate.anchor.odometer !== '1300.125' ||
      afterSave.mileageEstimate.estimatedOdometer !== '1300.125') {
    throw Error('Only explicit readings must anchor the recomputed estimate: '+JSON.stringify(afterSave.mileageEstimate));
  }

  // The user can disable future prompts from the vehicle editor; no reading is removed.
  await selectVehicle('Mileage Prompt');
  await value("document.querySelector('#vehicle-edit').click()");
  await until("!document.querySelector('#own-panel').hidden && document.querySelector('#entry-readingPromptEnabled')", 'prompt settings editor');
  await setCheckbox('#entry-readingPromptEnabled',false);
  await value("document.querySelector('#own-form').requestSubmit()");
  await until("document.querySelector('#own-panel').hidden", 'disable prompt save');
  const off = await request(`/garage-api/vehicles/${vehicle.id}`);
  if (off.readingPromptDays !== null || off.readingPrompt.state !== 'disabled' ||
      (await request(`/garage-api/vehicles/${vehicle.id}/odometer`)).readings.length !== 2) {
    throw Error('Disabling prompt changed readings or failed to disable the projection');
  }

  for (const width of [320,390,768,1280]) {
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});
    await delay(100);
    const dimensions = await value('({width:document.documentElement.scrollWidth,innerWidth})');
    if (dimensions.width > dimensions.innerWidth) throw Error(`Horizontal overflow at ${width}px: ${JSON.stringify(dimensions)}`);
  }
  if (errors.length) throw Error('JavaScript errors: '+errors.join('; '));
  console.log('Read-only estimate from actual anchor, blank/cancelled prompt, explicit actual save/reanchor, prompt disable, no synthetic reads and 320/390/768/1280 px: PASS');
}
main().catch(error=>{console.error(error.stack||error.message);process.exitCode=1})
  .finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
