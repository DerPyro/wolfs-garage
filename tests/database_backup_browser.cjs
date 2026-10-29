// Synthetic Chromium acceptance for the distinct full-database backup download.
// Serve a fresh schema-4 standalone database on loopback port 18990 first.
const fs = require('fs');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const browserDir = fs.readdirSync('/ms-playwright').find(name => name.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
const output = '/out/database-backup-browser';
let browser, pageSocket, browserSocket, sequence = 0;
const pagePending = new Map(), browserPending = new Map(), downloadEvents = [], errors = [];

function rpc(socket, pending, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, {resolve, reject});
    socket.send(JSON.stringify({id, method, params}));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(Error(`CDP timeout: ${method}`)); } }, 10000).unref();
  });
}
async function value(expression) {
  const result = await rpc(pageSocket, pagePending, 'Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  if (result.exceptionDetails) throw Error(result.exceptionDetails.text);
  return result.result.value;
}
async function until(expression, label) {
  for (let attempt = 0; attempt < 120; attempt++) {
    await delay(100);
    try { if (await value(expression)) return; } catch (_) {}
  }
  const diagnostic = await value(`({status:document.querySelector('#status')?.textContent,button:document.querySelector('#database-backup')?.outerHTML,errors:${JSON.stringify(errors)}})`);
  throw Error(`Timed out waiting for ${label}: ${JSON.stringify(diagnostic)}`);
}

async function main() {
  if (!binary) throw Error('Chromium binary not found under /ms-playwright');
  fs.mkdirSync(output, {recursive: true});
  for (const name of fs.readdirSync(output)) fs.rmSync(`${output}/${name}`, {recursive: true, force: true});
  browser = spawn(binary, ['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server',
    '--remote-debugging-port=9249','--remote-allow-origins=*','--user-data-dir=/tmp/wg-database-backup-browser','about:blank'], {stdio:'ignore'});
  let pageTarget, browserEndpoint;
  for (let attempt = 0; attempt < 100; attempt++) {
    try {
      const targetResponse = await fetch('http://127.0.0.1:9249/json/new?about:blank', {method:'PUT'});
      if (targetResponse.ok) pageTarget = await targetResponse.json();
      const versionResponse = await fetch('http://127.0.0.1:9249/json/version');
      if (versionResponse.ok) browserEndpoint = (await versionResponse.json()).webSocketDebuggerUrl;
      if (pageTarget && browserEndpoint) break;
    } catch (_) {}
    await delay(100);
  }
  if (!pageTarget || !browserEndpoint) throw Error('Chromium debugging endpoints did not start');

  browserSocket = new WebSocket(browserEndpoint);
  await new Promise((resolve,reject)=>{browserSocket.onopen=resolve;browserSocket.onerror=reject;});
  browserSocket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Browser.downloadWillBegin' || message.method === 'Browser.downloadProgress') downloadEvents.push(message);
    if (message.id && browserPending.has(message.id)) {
      const item=browserPending.get(message.id);browserPending.delete(message.id);
      message.error?item.reject(Error(message.error.message)):item.resolve(message.result);
    }
  };
  await rpc(browserSocket,browserPending,'Browser.setDownloadBehavior',{behavior:'allow',downloadPath:output,eventsEnabled:true});

  pageSocket = new WebSocket(pageTarget.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{pageSocket.onopen=resolve;pageSocket.onerror=reject;});
  pageSocket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text || 'runtime exception');
    if (message.id && pagePending.has(message.id)) {
      const item=pagePending.get(message.id);pagePending.delete(message.id);
      message.error?item.reject(Error(message.error.message)):item.resolve(message.result);
    }
  };
  await rpc(pageSocket,pagePending,'Page.enable');
  await rpc(pageSocket,pagePending,'Runtime.enable');
  await rpc(pageSocket,pagePending,'Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await rpc(pageSocket,pagePending,'Page.navigate',{url:'http://127.0.0.1:18990/'});
  await until("document.querySelector('#status')?.textContent.includes('leer') && !!document.querySelector('#database-backup')",'backup action on empty standalone page');

  const widths=[320,390,768,1280];
  for (const width of widths) {
    await rpc(pageSocket,pagePending,'Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});
    const layout=await value(`(()=>{const button=document.querySelector('#database-backup');return {overflow:document.documentElement.scrollWidth>innerWidth,visible:!!button&&!button.hidden&&button.getBoundingClientRect().width>0,label:button?.textContent?.trim()}})()`);
    if(layout.overflow||!layout.visible)throw Error(`Backup action is missing or overflows at ${width}px: ${JSON.stringify(layout)}`);
    console.log(`${width}px backup action layout passed`);
  }

  await rpc(pageSocket,pagePending,'Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  const buttons=await value(`({json:document.querySelector('#data-export')?.textContent?.trim(),backup:document.querySelector('#database-backup')?.textContent?.trim()})`);
  if(!buttons.backup||!buttons.json||buttons.backup===buttons.json||!buttons.backup.toLowerCase().includes('sicherung'))throw Error(`JSON export and SQLite backup are not clearly separate actions: ${JSON.stringify(buttons)}`);
  await value("document.querySelector('#database-backup').click()");
  for(let attempt=0;attempt<150;attempt++){
    await delay(100);
    if(downloadEvents.some(item=>item.method==='Browser.downloadProgress'&&item.params.state==='completed'))break;
  }
  const began=downloadEvents.find(item=>item.method==='Browser.downloadWillBegin');
  const completed=downloadEvents.find(item=>item.method==='Browser.downloadProgress'&&item.params.state==='completed');
  if(!began||!completed)throw Error(`Backup download did not complete: ${JSON.stringify(downloadEvents)}`);
  const filename=began.params.suggestedFilename;
  if(!/^wolfs-garage-backup-.+\.sqlite3$/.test(filename))throw Error(`Unexpected backup filename: ${filename}`);
  const file=`${output}/${filename}`;
  for(let attempt=0;attempt<40&&!fs.existsSync(file);attempt++)await delay(100);
  if(!fs.existsSync(file)||fs.statSync(file).size<100)throw Error(`Downloaded SQLite backup is missing or empty: ${file}`);
  const header=fs.readFileSync(file).subarray(0,16).toString('binary');
  if(header!=='SQLite format 3\u0000')throw Error(`Download is not SQLite bytes (header=${JSON.stringify(header)})`);
  if(errors.length)throw Error(`JavaScript errors: ${errors.join('; ')}`);
  console.log('Separate JSON/SQLite actions, completed real SQLite browser download, responsive layout: PASS');
}
main().catch(error=>{console.error(error.stack||error.message);process.exitCode=1}).finally(()=>{if(pageSocket)pageSocket.close();if(browserSocket)browserSocket.close();if(browser)browser.kill()});
