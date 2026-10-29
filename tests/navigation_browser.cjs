// Synthetic Chromium acceptance for hash navigation, focus, view state and motion preference.
// Serve a fresh schema-4 standalone database on loopback port 18993 first.
const fs = require('fs');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const browserDir = fs.readdirSync('/ms-playwright').find(name => name.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
const origin = process.env.GARAGE_BROWSER_ORIGIN || 'http://127.0.0.1:18993';
let browser, socket, sequence = 0;
const pending = new Map(), errors = [];

function call(method, params = {}) {
  return new Promise((resolve,reject)=>{
    const id=++sequence;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));
    setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error(`CDP timeout: ${method}`))}},10000).unref();
  });
}
async function value(expression) {
  const result=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
  if(result.exceptionDetails)throw Error(result.exceptionDetails.text);
  return result.result.value;
}
async function until(expression,label) {
  let evaluationError=null;
  for(let i=0;i<120;i++){await delay(100);try{if(await value(expression))return}catch(error){evaluationError=String(error)}}
  let state={};try{state=await value(`({hash:location.hash,navOpen:!document.querySelector('#site-navigation')?.hidden,navExpanded:document.querySelector('#nav-toggle')?.getAttribute('aria-expanded'),navToggle:document.querySelector('#nav-toggle')?.outerHTML,garage:!document.querySelector('#garage-view')?.hidden,backups:!document.querySelector('#backups-view')?.hidden,settings:!document.querySelector('#settings-view')?.hidden,model:document.querySelector('#entry-model')?.value,errors:${JSON.stringify(errors)}})`)}catch{}
  throw Error(`Timed out waiting for ${label}: ${JSON.stringify({state,evaluationError})}`);
}
async function request(path,method='GET',payload=null) {
  const write=method!=='GET',headers=write?{'Content-Type':'application/json','X-Garage-Request':'1'}:{Accept:'application/json'};
  const body=write?JSON.stringify(payload):null;
  return await value(`(async()=>{const r=await fetch(${JSON.stringify(path)},{method:${JSON.stringify(method)},headers:${JSON.stringify(headers)}${write?`,body:${JSON.stringify(body)}`:''}});let j;try{j=await r.json()}catch{}if(!r.ok)throw Error(${JSON.stringify(path)}+' ('+r.status+'): '+JSON.stringify(j));return j})()`);
}
async function openNavLink(linkId,hash) {
  if(await value("document.querySelector('#site-navigation').hidden"))await value("document.querySelector('#nav-toggle').click()");
  await value(`document.querySelector(${JSON.stringify(`#${linkId}`)}).click()`);
  await until(`location.hash===${JSON.stringify(`#${hash}`)} && !document.querySelector(${JSON.stringify(`#${hash==='garage'?'garage':hash==='sicherungen'?'backups':'settings'}-view`)}).hidden && document.querySelector('#site-navigation').hidden`,`navigate to ${hash}`);
}
async function keyEscape() {
  await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});
  await call('Input.dispatchKeyEvent',{type:'keyUp',key:'Escape',code:'Escape',windowsVirtualKeyCode:27,nativeVirtualKeyCode:27});
}
async function main() {
  if(!binary)throw Error('Chromium binary not found under /ms-playwright');
  fs.mkdirSync('/out/navigation-browser',{recursive:true});
  browser=spawn(binary,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--remote-debugging-port=9250','--remote-allow-origins=*','--user-data-dir=/tmp/wg-navigation-browser','about:blank'],{stdio:'ignore'});
  let target;
  for(let i=0;i<100;i++){try{const r=await fetch('http://127.0.0.1:9250/json/new?about:blank',{method:'PUT'});if(r.ok){target=await r.json();break}}catch{}await delay(100)}
  if(!target)throw Error('Chromium debugging target did not start');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject});
  socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.method==='Runtime.exceptionThrown')errors.push(message.params.exceptionDetails.exception?.description||message.params.exceptionDetails.text||'runtime exception');if(message.id&&pending.has(message.id)){const item=pending.get(message.id);pending.delete(message.id);message.error?item.reject(Error(message.error.message)):item.resolve(message.result)}};
  await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Network.setCacheDisabled',{cacheDisabled:true});
  await call('Page.addScriptToEvaluateOnNewDocument',{source:`window.__scrollEvents=[];const original=Element.prototype.scrollIntoView;Element.prototype.scrollIntoView=function(options){window.__scrollEvents.push({id:this.id,behavior:typeof options==='object'?options?.behavior:options});return original?.call(this,options)}`});
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await call('Page.navigate',{url:`${origin}/`});
  await until("document.querySelector('#vehicle-add')?.getClientRects().length>0 && !!document.querySelector('#nav-toggle')",'initial garage view and loaded capabilities');

  const initial=await value(`({hash:location.hash,garage:!document.querySelector('#garage-view').hidden,intro:!!document.querySelector('.intro'),backup:document.querySelector('#database-backup').getClientRects().length>0,vehicleAdd:document.querySelector('#vehicle-add').getClientRects().length>0,menu:document.querySelector('#site-navigation').hidden})`);
  if(!initial.garage||initial.intro||initial.backup||!initial.vehicleAdd||!initial.menu)throw Error(`Unexpected initial view: ${JSON.stringify(initial)}`);
  const capture=async name=>{const result=await call('Page.captureScreenshot',{format:'png'});fs.writeFileSync(`/out/navigation-browser/${name}.png`,Buffer.from(result.data,'base64'))};
  await capture('navigation-garage-mobile');
  if(!initial.hash)await openNavLink('nav-garage','garage');

  // Keyboard dismissal returns focus to the disclosure button.
  await value("document.querySelector('#nav-toggle').click()");
  await until("!document.querySelector('#site-navigation').hidden && document.querySelector('#nav-toggle').getAttribute('aria-expanded')==='true'",'navigation opens');
  await capture('navigation-menu-mobile');
  await value("document.querySelector('#nav-backups').focus()");await keyEscape();
  await until("document.querySelector('#site-navigation').hidden && document.querySelector('#nav-toggle').getAttribute('aria-expanded')==='false' && document.activeElement.id==='nav-toggle'",'Escape closes menu and restores focus');

  // Outside clicks close the disclosure and leave focus at the clicked control.
  await value("document.querySelector('#nav-toggle').click()");
  await value("document.querySelector('#garage-title').focus()");
  await value("document.querySelector('#garage-title').click()");
  await until("document.querySelector('#site-navigation').hidden && document.querySelector('#nav-toggle').getAttribute('aria-expanded')==='false' && document.activeElement.id==='garage-title'",'outside click closes menu without focus theft');

  // Create synthetic vehicles and issue metadata through public APIs only.
  const first=await request('/garage-api/vehicles','POST',{make:'Synthetic',model:'Navigation One',vehicleType:'Limousine',odometerUnit:'km'});
  const second=await request('/garage-api/vehicles','POST',{make:'Synthetic',model:'Navigation Two',vehicleType:'Limousine',odometerUnit:'km'});
  const status=await request(`/garage-api/vehicles/${first.id}/status`);
  await request(`/garage-api/vehicles/${first.id}/status`,'PUT',{readiness:'ready',revision:status.revision,issues:[{text:'Synthetic navigation issue'}]});
  await call('Page.reload');
  await until(`document.querySelectorAll('#vehicles .vehicle-card').length>=2 && !document.querySelector('#garage-view').hidden`,'synthetic vehicle cards load');

  await value(`(()=>{const card=Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(node=>node.getAttribute('aria-label')?.includes('Navigation One'));if(!card)throw Error('synthetic vehicle card missing');card.click()})()`);
  await until(`document.querySelector('#detail-heading')?.textContent.includes('Navigation One') && !document.querySelector('#own-detail-actions').hidden`,'select synthetic vehicle');
  await value(`(()=>Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(node=>node.getAttribute('aria-label')?.includes('Navigation Two')).click())()`);
  await until(`document.querySelector('#detail-heading')?.textContent.includes('Navigation Two')`,'system-motion selection');
  const smoothBehavior=await value("window.__scrollEvents.filter(event=>event.id==='own-detail-actions').at(-1)?.behavior");
  if(smoothBehavior!=='smooth')throw Error(`System motion should use smooth card selection by default: ${smoothBehavior}`);
  await value(`(()=>Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(node=>node.getAttribute('aria-label')?.includes('Navigation One')).click())()`);
  await until(`document.querySelector('#detail-heading')?.textContent.includes('Navigation One')`,'restore first selection');
  await value("document.querySelector('#vehicle-edit').click()");
  await until("!document.querySelector('#own-panel').hidden && !!document.querySelector('#entry-model')",'open vehicle editor');
  const draft='Navigation One unsaved draft';
  await value(`(()=>{const field=document.querySelector('#entry-model');field.value=${JSON.stringify(draft)};field.dispatchEvent(new Event('input',{bubbles:true}))})()`);
  const before=await value(`(async()=>{const [v,s,h]=await Promise.all([fetch('/garage-api/vehicles/${first.id}').then(r=>r.json()),fetch('/garage-api/vehicles/${first.id}/status').then(r=>r.json()),fetch('/garage-api/vehicles/${first.id}/history').then(r=>r.json())]);return {vehicle:v,status:s,history:h.events}})()`);

  await openNavLink('nav-backups','sicherungen');
  if(await value("!document.querySelector('#database-backup').hidden && !document.querySelector('#data-export').hidden" )!==true)throw Error('Backups view did not expose both distinct backup/export actions');
  await capture('navigation-backups-mobile');
  await value('history.back()');
  await until(`location.hash==='#garage' && !document.querySelector('#garage-view').hidden && document.querySelector('#backups-view').hidden`,'back to garage');
  const backState=await value(`({hash:location.hash,garage:!document.querySelector('#garage-view').hidden,backups:!document.querySelector('#backups-view').hidden,selected:document.querySelector('#vehicles .vehicle-card[aria-pressed="true"]')?.getAttribute('aria-label'),editor:!document.querySelector('#own-panel').hidden,draft:document.querySelector('#entry-model')?.value})`);
  if(backState.hash!=='#garage'||!backState.garage||backState.backups||!backState.selected?.includes('Navigation One')||!backState.editor||backState.draft!==draft)throw Error(`Back navigation lost selected card or unsaved editor: ${JSON.stringify(backState)}`);
  await value("document.querySelector('#own-cancel').click()");
  await until("document.querySelector('#own-panel').hidden",'discard the preserved unsaved draft');

  await openNavLink('nav-settings','einstellungen');
  const version=await value("document.querySelector('#app-version').textContent.trim()");
  const apiVersion=(await request('/garage-api/capabilities')).version;
  if(!version||!version.includes(apiVersion))throw Error(`Settings version does not match API capability version: ${version} vs ${apiVersion}`);
  await value(`(()=>{const select=document.querySelector('#motion-preference');select.value='reduce';select.dispatchEvent(new Event('change',{bubbles:true}))})()`);
  const preference=await value(`({select:document.querySelector('#motion-preference').value,stored:localStorage.getItem('wolfs-garage-motion-preference')})`);
  if(preference.select!=='reduce'||preference.stored!=='reduce')throw Error(`Reduced motion was not stored: ${JSON.stringify(preference)}`);
  await call('Page.reload');
  await until(`location.hash==='#einstellungen' && document.querySelector('#motion-preference')?.value==='reduce'`, 'motion setting survives reload');
  const persisted=await value("localStorage.getItem('wolfs-garage-motion-preference')");
  if(persisted!=='reduce')throw Error('Motion preference did not persist after reload');

  // Choosing system follows the operating-system reduced-motion preference.
  await value("(()=>{const select=document.querySelector('#motion-preference');select.value='system';select.dispatchEvent(new Event('change',{bubbles:true}))})()");
  if(await value("localStorage.getItem('wolfs-garage-motion-preference')")!=='system')throw Error('System motion preference was not persisted');
  await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  if(!await value("window.matchMedia('(prefers-reduced-motion: reduce)').matches"))throw Error('Chromium did not emulate the OS reduced-motion setting');
  await openNavLink('nav-garage','garage');
  await value(`(()=>Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(node=>node.getAttribute('aria-label')?.includes('Navigation Two')).click())()`);
  await until(`document.querySelector('#detail-heading')?.textContent.includes('Navigation Two')`,'OS reduced-motion vehicle selection');
  const reducedMotionBehavior=await value("window.__scrollEvents.filter(event=>event.id==='own-detail-actions').at(-1)?.behavior");
  if(reducedMotionBehavior!=='auto')throw Error(`System preference ignored OS reduced motion: ${reducedMotionBehavior}`);
  await call('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]});
  await value(`(()=>Array.from(document.querySelectorAll('#vehicles .vehicle-card')).find(node=>node.getAttribute('aria-label')?.includes('Navigation One')).click())()`);
  await until(`document.querySelector('#detail-heading')?.textContent.includes('Navigation One')`,'system-motion preference restored');
  const restoredMotionBehavior=await value("window.__scrollEvents.filter(event=>event.id==='own-detail-actions').at(-1)?.behavior");
  if(restoredMotionBehavior!=='smooth')throw Error(`System preference did not restore smooth scrolling: ${restoredMotionBehavior}`);
  const after=await value(`(async()=>{const [v,s,h]=await Promise.all([fetch('/garage-api/vehicles/${first.id}').then(r=>r.json()),fetch('/garage-api/vehicles/${first.id}/status').then(r=>r.json()),fetch('/garage-api/vehicles/${first.id}/history').then(r=>r.json())]);return {vehicle:v,status:s,history:h.events}})()`);
  if(after.vehicle.model!==before.vehicle.model||after.vehicle.revision!==before.vehicle.revision||JSON.stringify(after.status)!==JSON.stringify(before.status)||JSON.stringify(after.history)!==JSON.stringify(before.history))throw Error('Navigation or cancelling the draft wrote vehicle, status or history data');

  const widths=[320,390,768,1280];
  for(const width of widths){
    await call('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:width<700});
    for(const [link,hash,viewId] of [['nav-garage','garage','garage-view'],['nav-backups','sicherungen','backups-view'],['nav-settings','einstellungen','settings-view']]){
      await openNavLink(link,hash);
      const facts=await value(`({overflow:document.documentElement.scrollWidth>innerWidth,toggle:document.querySelector('#nav-toggle').getBoundingClientRect().width>0,view:!document.querySelector(${JSON.stringify(`#${viewId}`)}).hidden})`);
      if(facts.overflow||!facts.toggle||!facts.view)throw Error(`Navigation layout ${hash} failed at ${width}px: ${JSON.stringify(facts)}`);
    }
    console.log(`${width}px garage/backups/settings layout passed`);
  }
  if(errors.length)throw Error(`JavaScript errors: ${errors.join('; ')}`);
  console.log('Initial garage, menu Escape/outside focus, hash back with selected draft, version/motion persistence and no-write navigation: PASS');
}
main().catch(error=>{console.error(error.stack||error.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill()});
