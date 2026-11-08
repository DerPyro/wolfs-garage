// Synthetic real-Chromium acceptance for the public, shared demo.
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const fs = require('fs');
const path = require('path');
const browserDir = fs.readdirSync('/ms-playwright').find(name => name.startsWith('chromium-'));
const binary = browserDir && [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
const origin = process.env.GARAGE_BROWSER_ORIGIN || 'http://localhost:18996';
let browser, socket, sequence = 0;
const pending = new Map(), errors = [];

function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, {resolve, reject});
    socket.send(JSON.stringify({id, method, params}));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Error(`CDP timeout: ${method}`)); } }, 10000).unref();
  });
}
async function value(expression) {
  const result = await call('Runtime.evaluate', {expression, returnByValue:true, awaitPromise:true});
  if (result.exceptionDetails) throw Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || 'Browser evaluation failed');
  return result.result.value;
}
async function until(expression, label) {
  for (let i = 0; i < 120; i++) {
    await delay(100);
    try { if (await value(expression)) return; } catch (_) { /* wait for the browser transition */ }
  }
  throw Error(`Timed out waiting for ${label}`);
}
async function setInput(selector, text) {
  await value(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});
    if(!input)throw Error('Missing input');input.value=${JSON.stringify(text)};
    input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}))})()`);
}
async function main() {
  if (!binary) throw Error('Chromium binary not found under /ms-playwright');
  browser = spawn(binary, ['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking',
    '--no-proxy-server','--remote-debugging-port=9253','--remote-allow-origins=*',
    '--user-data-dir=/tmp/wg-public-demo-browser','about:blank'], {stdio:'ignore'});
  let target;
  for (let i = 0; i < 80; i++) {
    try {
      const response = await fetch('http://127.0.0.1:9253/json/new?about:blank', {method:'PUT'});
      if (response.ok) { target = await response.json(); break; }
    } catch (_) {}
    await delay(100);
  }
  if (!target) throw Error('Chromium start failed');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  socket.onmessage = event => {
    const data = JSON.parse(event.data);
    if (data.method === 'Runtime.exceptionThrown') errors.push('browser runtime exception');
    if (data.id && pending.has(data.id)) {
      const entry = pending.get(data.id); pending.delete(data.id);
      data.error ? entry.reject(Error(data.error.message)) : entry.resolve(data.result);
    }
  };
  await call('Page.enable'); await call('Runtime.enable');
  await call('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate', {url:origin});
  await until(`!document.querySelector('#demo-banner')?.hidden &&
    document.querySelectorAll('#vehicles .vehicle-card').length===5`, 'shared demo banner and five seeded vehicles');

  const capabilities = await value("(async()=>await(await fetch('/garage-api/capabilities')).json())()");
  const demo = capabilities.demo;
  if (!demo || demo.shared !== true || !/^[0-9a-f]{32}$/.test(demo.generation) || !Number.isFinite(Date.parse(demo.resetAt))) {
    throw Error('Demo capability metadata is missing or invalid');
  }
  const backupNavHidden = await value("document.querySelector('#nav-backups').hidden");
  if (capabilities.features.includes('dataExport') || capabilities.features.includes('databaseBackup') || !backupNavHidden) {
    throw Error('Demo exposed an owner backup or export feature');
  }
  const banner = await value(`(()=>({text:document.querySelector('#demo-message').textContent,
    resetLabel:document.querySelector('#demo-message').textContent.includes('Nächster Reset:')}))()`);
  if (!banner.resetLabel || !banner.text.includes('Öffentliche Demo') || !banner.text.includes('Gemeinsame Beispieldaten') ||
      !banner.text.includes('stündlich zurückgesetzt') || !banner.text.includes('Keine persönlichen Daten eingeben') ||
      !/Nächster Reset: .+, \d{2}:\d{2} .+\.$/.test(banner.text)) {
    throw Error('Demo banner is missing its sharing notice or readable local timezone');
  }
  const seeds = await value("(async()=>await(await fetch('/garage-api/vehicles')).json())()");
  if (!Array.isArray(seeds.vehicles) || seeds.vehicles.length !== 5) throw Error('Demo seed is not the expected synthetic set');
  const vehicle = seeds.vehicles[0];
  if (!String(vehicle.name).includes('Demo') || !String(vehicle.licensePlate).startsWith('DEMO-')) throw Error('Refusing to edit a non-demo vehicle');

  const screenshotPath = process.env.GARAGE_BROWSER_SCREENSHOT || '.sandbox/demo-evidence/mobile.png';
  let screenshotSaved = false;
  try {
    fs.mkdirSync(path.dirname(screenshotPath), {recursive:true});
    const screenshot = await call('Page.captureScreenshot', {format:'png',captureBeyondViewport:true});
    fs.writeFileSync(screenshotPath, Buffer.from(screenshot.data, 'base64')); screenshotSaved = true;
  } catch (_) { /* visual evidence is optional when no writable artifact mount is provided */ }

  // Capture only request method/path/headers to confirm the UI sends the capability generation.
  await value(`(()=>{window.__demoWrites=[];const original=window.fetch.bind(window);window.fetch=(input,init={})=>{
    const method=(init.method||'GET').toUpperCase();if(method!=='GET')window.__demoWrites.push({path:String(input),method,headers:init.headers||{}});
    return original(input,init);};})()`);
  await value("document.querySelector('#vehicle-edit').click()");
  await until("!document.querySelector('#own-panel').hidden && document.querySelector('#entry-model')", 'vehicle metadata editor');
  const changedModel = '508 Demo Browser Probe';
  await setInput('#entry-model', changedModel);
  await value("document.querySelector('#own-form').requestSubmit()");
  await until(`(async()=>{const v=await(await fetch('/garage-api/vehicles/${vehicle.id}')).json();return v.model===${JSON.stringify(changedModel)}})()`, 'synthetic vehicle metadata save');
  const metadataWrite = await value("window.__demoWrites.at(-1)");
  if (!metadataWrite || metadataWrite.method !== 'PUT' || !metadataWrite.path.endsWith(`/vehicles/${vehicle.id}`) ||
      metadataWrite.headers['X-Garage-Demo-Generation'] !== demo.generation) throw Error('Vehicle metadata write omitted the initial demo generation');

  // Record a synthetic actual reading through the ordinary owner form.
  await value("document.querySelector('#odometer-add').click()");
  await until("!document.querySelector('#own-panel').hidden && document.querySelector('#entry-odometer')", 'odometer form');
  const odometerValue = '55555.125';
  await setInput('#entry-odometer', odometerValue);
  await setInput('#entry-note', 'Synthetic browser acceptance reading');
  await value("document.querySelector('#own-form').requestSubmit()");
  await until('document.querySelector(\'#own-panel\').hidden', 'odometer save');
  const odometerWrite = await value("window.__demoWrites.at(-1)");
  if (!odometerWrite || odometerWrite.method !== 'POST' || !odometerWrite.path.endsWith(`/vehicles/${vehicle.id}/odometer`) ||
      odometerWrite.headers['X-Garage-Demo-Generation'] !== demo.generation) throw Error('Odometer write omitted the initial demo generation');
  const savedVehicle = await value(`(async()=>await(await fetch('/garage-api/vehicles/${vehicle.id}')).json())()`);
  if (savedVehicle.model !== changedModel || String(savedVehicle.odometer) !== odometerValue) throw Error('Synthetic vehicle/read values did not persist');

  // The unsupported document link remains unavailable in the public demo form.
  await value("document.querySelector('#record-add').click()");
  await until("!document.querySelector('#own-panel').hidden && document.querySelector('#entry-documentUrl')", 'work record form');
  const documentLink = await value("(()=>{const input=document.querySelector('#entry-documentUrl');return {fieldHidden:input.parentElement.hidden,value:input.value}})()");
  if (!documentLink.fieldHidden || documentLink.value) throw Error('Demo displayed or prefilled an unsupported document link field');
  await value("document.querySelector('#own-cancel').click()");
  await until('document.querySelector(\'#own-panel\').hidden', 'work form cancellation');

  // A direct write without the capability generation must be rejected before it changes shared data.
  const missingGeneration = await value(`(async()=>{const r=await fetch('/garage-api/vehicles',{method:'POST',
    headers:{'Content-Type':'application/json','X-Garage-Request':'1'},
    body:JSON.stringify({make:'Synthetic',model:'Missing Generation Probe',odometerUnit:'km'})});return r.status})()`);
  if (missingGeneration !== 409) throw Error('A demo write without generation was not rejected with HTTP 409');
  const vehiclesAfterReject = await value("(async()=>await(await fetch('/garage-api/vehicles')).json())()");
  if (vehiclesAfterReject.vehicles.length !== 5 || vehiclesAfterReject.vehicles.some(item => item.model === 'Missing Generation Probe')) {
    throw Error('Rejected missing-generation request changed demo data');
  }

  for (const width of [320,390,768,1280]) {
    await call('Emulation.setDeviceMetricsOverride', {width,height:900,deviceScaleFactor:1,mobile:width<700});
    await delay(100);
    const dimensions = await value('({width:document.documentElement.scrollWidth,innerWidth})');
    if (dimensions.width > dimensions.innerWidth) throw Error(`Horizontal overflow at ${width}px`);
  }
  if (errors.length) throw Error('Browser runtime error observed');
  console.log(`Public demo banner, 5 synthetic vehicles, guarded UI writes, rejected stale-less POST, hidden document link, 320/390/768/1280 px: PASS${screenshotSaved ? ` (${screenshotPath})` : ''}`);
}
main().catch(error => { console.error(error.stack || error.message); process.exitCode = 1; })
  .finally(() => { if (socket) socket.close(); if (browser) browser.kill(); });
