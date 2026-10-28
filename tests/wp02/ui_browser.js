// WP02 UI exploration, synthetic isolated target only. Node and bundled Chromium; no Playwright dependency.
const fs = require('fs');
const {spawn} = require('child_process');
const path = require('path');
const { setTimeout: delay } = require('timers/promises');

const app = 'http://lubelogger:8080';
const expected = ['UI-A','UI-B','UI-C','UI-D','UI-E'];
const out = {tool:'Chromium via Chrome DevTools Protocol', viewports:[],consoleExceptions:[], externalRequests:[],network:[]};
let chrome;
let ws;
let seq=0;
const waiting=new Map();

function chromePath(){
  const root='/ms-playwright';
  const directories=fs.readdirSync(root).filter(x=>x.startsWith('chromium-')).sort().reverse();
  for (const d of directories){
    for(const rel of ['chrome-linux/chrome','chrome-linux64/chrome']){
      const candidate=path.join(root,d,rel);
      if(fs.existsSync(candidate)) return candidate;
    }
  }
  throw new Error('Pinned test image contains no compatible Chromium executable');
}

async function connect(){
  chrome=spawn(chromePath(),['--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage',
    '--remote-debugging-port=9234','--remote-debugging-address=127.0.0.1',
    '--remote-allow-origins=*','--no-first-run','--disable-background-networking',
    '--disable-component-update','--user-data-dir=/tmp/wp02-chrome','about:blank'],{stdio:'ignore'});
  let version;
  for(let i=0;i<100;i++){
    try { const r=await fetch('http://127.0.0.1:9234/json/version'); if(r.ok){version=await r.json();break;} }
    catch {} await delay(200);
  }
  if(!version) throw new Error('Chromium did not start');
  out.browser=version.Browser;
  const target=await (await fetch('http://127.0.0.1:9234/json/new?about:blank',{method:'PUT'})).json();
  ws=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
  ws.onmessage=(event)=>{
    const msg=JSON.parse(event.data);
    if(msg.id){const p=waiting.get(msg.id); if(p){waiting.delete(msg.id);msg.error?p.reject(new Error(msg.error.message)):p.resolve(msg.result);}}
    else if(msg.method==='Runtime.exceptionThrown'){
      const e=msg.params.exceptionDetails;
      out.consoleExceptions.push({text:e.text,description:e.exception?.description?.slice(0,300)});
    } else if(msg.method==='Network.responseReceived'){
      const r=msg.params.response;if(r.url.startsWith(app))out.network.push({path:new URL(r.url).pathname,status:r.status});
    } else if(msg.method==='Network.requestWillBeSent'){
      const url=msg.params.request.url;
      if(url.startsWith('http')&&!url.startsWith(app)) out.externalRequests.push(new URL(url).origin);
    }
  };
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
}
function send(method,params={}){
  return new Promise((resolve,reject)=>{const id=++seq;waiting.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));
    setTimeout(()=>{if(waiting.has(id)){waiting.delete(id);reject(new Error('CDP timeout: '+method));}},15000).unref();});
}
async function evaluate(expr){
  const r=await send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true});
  if(r.exceptionDetails)throw new Error('Page evaluation failed: '+r.exceptionDetails.text);
  return r.result.value;
}
async function waitFor(expr,label){
  for(let i=0;i<120;i++){try{if(await evaluate(expr)) return;}catch{} await delay(100);}
  throw new Error('Timed out: '+label);
}
async function screenshot(name){
  const img=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  fs.writeFileSync('/artifacts/'+name+'.png',Buffer.from(img.data,'base64'));
}
async function click(expr,label){
  const rect=await evaluate(`(() => { const e=(${expr}); if(!e)return null; e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect(); const s=getComputedStyle(e);const x=r.x+r.width/2,y=r.y+r.height/2,hit=document.elementFromPoint(x,y);return {x,y,w:r.width,h:r.height,display:s.display,visibility:s.visibility,receivesPointer:!!hit&&(hit===e||e.contains(hit))}; })()`);
  if(!rect||rect.w<=0||rect.h<=0||rect.display==='none'||rect.visibility==='hidden'||!rect.receivesPointer)throw new Error('Unavailable control: '+label);
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:rect.x,y:rect.y});
  await send('Input.dispatchMouseEvent',{type:'mousePressed',x:rect.x,y:rect.y,button:'left',clickCount:1});
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:rect.x,y:rect.y,button:'left',clickCount:1});
}
function visibleButton(id){return `Array.from(document.querySelectorAll('[id="${id}"]')).find(e=>{const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;const hit=document.elementFromPoint(x,y);return r.width>0&&r.height>0&&getComputedStyle(e).visibility==='visible'&&!!hit&&(hit===e||e.contains(hit))})`;}
async function selectTab(id,width){
  await evaluate('window.scrollTo(0,0)');
  await delay(150);
  const hamburger=`document.querySelector('button[onclick="showMobileNav()"]')`;
  const mobile=await evaluate(`(() => {const e=${hamburger};if(!e)return false;const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.x>=0&&r.y>=0&&r.x<innerWidth&&r.y<innerHeight&&getComputedStyle(e).visibility==='visible';})()`);
  if(mobile){
    await waitFor(`(() => {const e=${hamburger};const r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return !!hit&&(hit===e||e.contains(hit));})()`,'mobile menu becomes clickable');
    await click(hamburger,'mobile navigation menu');
    await waitFor(`Boolean(document.querySelector('.lubelogger-mobile-nav-show'))`,'mobile menu');
    await delay(350);
    await click(`document.querySelector('.lubelogger-mobile-nav-show [id="${id}"]')`,id+' mobile menu tab');
  } else {
    // Desktop tab overflow uses the built-in 'more' dropdown. Wait for toast overlays to disappear.
    await delay(3000);
    let tab=await evaluate(`Boolean(${visibleButton(id)})`);
    if(!tab){
      const more=`Array.from(document.querySelectorAll('.nav-item-more a[data-bs-toggle="dropdown"]')).find(e=>{let r=e.getBoundingClientRect();return r.width>0&&r.height>0})`;
      await click(more,'desktop more dropdown');
      await delay(300);
    }
    await waitFor(`Boolean(${visibleButton(id)})`,id+' clickable desktop tab');
    await click(visibleButton(id),id+' visible desktop tab');
  }
  await waitFor(`(() => {let p=document.querySelector('#${id.replace('-tab','-tab-pane')}');return p&&p.classList.contains('active')&&getComputedStyle(p).display!=='none';})()`,id+' active pane');
  await delay(350);
  await evaluate('window.scrollTo(0,0)');
}

async function runViewport(width,height){
  const record={width,height,steps:[]}; out.viewports.push(record);
  await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<600});
  await send('Page.navigate',{url:app+'/'});
  await waitFor(`document.querySelectorAll('.garage-item').length===5`,'five garage cards');
  await delay(500);
  const overview=await evaluate(`(() => {const cards=Array.from(document.querySelectorAll('.garage-item'));
    return {count:cards.length,names:cards.map(x=>x.innerText.replace(/\\s+/g,' ').trim()),
      viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
      cardRects:cards.map(x=>{let r=x.getBoundingClientRect();return {x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height),tabIndex:x.tabIndex,role:x.getAttribute('role')};}),
      reminderIcons:document.querySelectorAll('.garage-item .bi-bell-fill').length};})()`);
  record.overview=overview;
  if(!expected.every(v=>overview.names.some(name=>name.includes(v))))throw new Error('Garage cards do not contain the five synthetic names');
  await screenshot('ui-garage-'+width);
  record.steps.push('five rendered garage cards');
  const keyboard=await evaluate(`(() => { const card=document.querySelector('.garage-item'); const old=document.activeElement; card.focus(); return {focusable:document.activeElement===card,tag:card.tagName,tabIndex:card.tabIndex,role:card.getAttribute('role')}; })()`);
  record.keyboard=keyboard;
  await click(`document.querySelector('.garage-item')`,'first garage card');
  await waitFor(`location.pathname.toLowerCase()==='/vehicle/index'`,'vehicle detail navigation');
  await waitFor(`Boolean(document.querySelector('#report-tab-pane'))`,'vehicle tabs');
  await delay(400);
  const vehicle=await evaluate(`(() => ({path:location.pathname,viewport:innerWidth,documentWidth:document.documentElement.scrollWidth,
    pageTitle:document.title,bodyText:document.body.innerText.replace(/\\s+/g,' ').slice(0,1500)}))()`);
  record.vehicle=vehicle;
  await screenshot('ui-vehicle-'+width);
  record.steps.push('mouse navigation into first vehicle');
  await selectTab('servicerecord-tab',width);
  await waitFor(`document.querySelector('#servicerecord-tab-pane')?.innerText.includes('UI-SERVICE-ALPHA')`,'service row');
  const services=await evaluate(`(() => {let p=document.querySelector('#servicerecord-tab-pane');let row=Array.from(p.querySelectorAll('tbody tr')).find(x=>x.innerText.includes('UI-SERVICE-ALPHA'));let t=p.querySelector('table');return {
     recordVisible:!!row,rowText:row?.innerText.replace(/\\s+/g,' ').trim(),
     costBadge:p.querySelector('[data-aggregate-type="sum"]')?.innerText,
     tableWidth:t?.scrollWidth,containerWidth:t?.parentElement?.clientWidth,documentWidth:document.documentElement.scrollWidth,
     dateCell:(()=>{let d=row?.querySelector('[data-column=date]');return d?{clientWidth:d.clientWidth,scrollWidth:d.scrollWidth,cssTextOverflow:getComputedStyle(d).textOverflow,title:d.getAttribute('title'),text:d.innerText}:null;})(),
     addButtons:p.querySelectorAll('[onclick*="showAddServiceRecordModal"]').length};})()`);
  record.services=services;
  if(!services.recordVisible)throw new Error('Synthetic maintenance record not rendered');
  await screenshot('ui-service-'+width);
  record.steps.push('service history and explicit cost visible');
  await click(`Array.from(document.querySelectorAll('#servicerecord-tab-pane [onclick*="showAddServiceRecordModal"]')).find(e=>{let r=e.getBoundingClientRect();return r.width>0&&r.height>0})`,'add service');
  await delay(1000);
  record.addDebug=await evaluate(`(() => {let m=document.querySelector('#serviceRecordModal');return {classes:m?.className,htmlLength:document.querySelector('#serviceRecordModalContent')?.innerHTML.length,hasDate:!!document.querySelector('#serviceRecordDate'),shown:!!document.querySelector('#serviceRecordModal.show')};})()`);
  await screenshot('ui-after-add-'+width);
  await waitFor(`Boolean(document.querySelector('#serviceRecordModal.show #serviceRecordDate'))`,'service modal');
  await delay(350);
  const form=await evaluate(`(() => {let m=document.querySelector('#serviceRecordModal.show');const fields=Array.from(m.querySelectorAll('input,textarea,select')).map(e=>({id:e.id,placeholder:e.getAttribute('placeholder'),type:e.type}));
    return {fields,modalWidth:Math.round(m.querySelector('.modal-dialog').getBoundingClientRect().width),viewport:innerWidth,
      hasDate:!!m.querySelector('#serviceRecordDate'),hasOdometer:!!m.querySelector('#serviceRecordMileage'),
      hasDescription:!!m.querySelector('#serviceRecordDescription'),hasCost:!!m.querySelector('#serviceRecordCost'),
      visibleText:m.innerText.replace(/\\s+/g,' ').slice(0,1500)};})()`);
  record.form=form;
  if(!form.hasDate||!form.hasOdometer||!form.hasDescription||!form.hasCost) throw new Error('Core service modal inputs missing');
  await screenshot('ui-service-form-'+width);
  record.steps.push('service entry modal opens with key fields');
  // Enter synthetic values through Chromium input events and save through the actual modal button.
  for(const [id,value] of [['serviceRecordMileage','12500'],['serviceRecordDescription','UI-NEW-'+width],['serviceRecordCost','5']]) {
    await click(`document.querySelector('#${id}')`,id);
    await send('Input.insertText',{text:value});
  }
  await click(`document.querySelector('#serviceRecordModal.show [onclick="saveServiceRecordToVehicle()"]')`,'submit service form');
  await waitFor(`!document.querySelector('#serviceRecordModal.show')`,'service modal close after save');
  await waitFor(`document.querySelector('#servicerecord-tab-pane')?.innerText.includes('UI-NEW-${width}')`,'new synthetic service row');
  record.serviceCreated=await evaluate(`document.querySelector('#servicerecord-tab-pane')?.innerText.includes('UI-NEW-${width}')`);
  record.steps.push('synthetic maintenance entered and saved using UI');
  await delay(800);
  await selectTab('reminder-tab',width);
  await waitFor(`document.querySelector('#reminder-tab-pane')?.innerText.includes('UI-REMINDER-ALPHA')`,'reminder row');
  record.reminders=await evaluate(`(() => {let p=document.querySelector('#reminder-tab-pane');return {shown:p.innerText.includes('UI-REMINDER-ALPHA'),text:p.innerText.replace(/\\s+/g,' ').slice(0,1300),documentWidth:document.documentElement.scrollWidth};})()`);
  await screenshot('ui-reminder-'+width);
  record.steps.push('vehicle reminder visible');
  await selectTab('supply-tab',width);
  await waitFor(`document.querySelector('#supply-tab-pane')?.innerText.includes('UI-PART-ALPHA')`,'part row');
  record.supply=await evaluate(`(() => {let p=document.querySelector('#supply-tab-pane');return {shown:p.innerText.includes('UI-PART-ALPHA'),text:p.innerText.replace(/\\s+/g,' ').slice(0,1300),documentWidth:document.documentElement.scrollWidth};})()`);
  await screenshot('ui-supply-'+width);
  record.steps.push('synthetic part visible');
}
(async()=>{
 try {
  if(typeof WebSocket!=='function')throw new Error('Node does not provide a WebSocket client');
  await connect();
  for(const [w,h] of [[320,800],[768,1024],[1280,800]])await runViewport(w,h);
  out.externalRequests=[...new Set(out.externalRequests)];
  out.ok=true;
 } catch(e){out.ok=false;out.error=String(e.message||e);try {out.errorState=await evaluate(`(() => {let h=document.querySelector('button[onclick="showMobileNav()"]'),r=h?.getBoundingClientRect();let hit=r?document.elementFromPoint(r.x+r.width/2,r.y+r.height/2):null;return {scrollY,bodyClass:document.body.className,backdrops:document.querySelectorAll('.modal-backdrop').length,hamburger:r?{x:r.x,y:r.y,width:r.width,height:r.height,hit:hit?.outerHTML.slice(0,250)}:null};})()`); await screenshot('ui-on-error');} catch {}}
 finally {
  try{if(ws)ws.close();}catch{}
  if(chrome)chrome.kill('SIGTERM');
  fs.writeFileSync('/artifacts/ui-result.json',JSON.stringify(out,null,2)+'\n');
  console.log(JSON.stringify(out));
  process.exitCode=out.ok?0:1;
 }
})();
