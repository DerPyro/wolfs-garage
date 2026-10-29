// Synthetic Chromium acceptance. The caller serves a fresh schema-5 DB at
// http://127.0.0.1:18987; this script creates two fixtures through the API.
const fs = require('fs');
const os = require('os');
const path = require('path');
const {spawn} = require('child_process');
const {setTimeout: delay} = require('timers/promises');
const browserDir = fs.readdirSync('/ms-playwright').find(x => x.startsWith('chromium-'));
const binary = [`/ms-playwright/${browserDir}/chrome-linux/chrome`, `/ms-playwright/${browserDir}/chrome-linux64/chrome`].find(fs.existsSync);
let socket, browser, seq=0; const pending=new Map(), errors=[];
const downloadDir=fs.mkdtempSync(path.join(os.tmpdir(),'wg-owner-export-'));
function call(method,params={}) {return new Promise((resolve,reject)=>{const id=++seq;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error('CDP timeout'))}},10000).unref()})}
async function value(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value}
async function until(expression,label){for(let i=0;i<120;i++){await delay(100);try{if(await value(expression))return}catch{}}let diagnostic={};try{diagnostic=await value('({status:document.querySelector("#status")?.textContent||"",exportLink:!!document.querySelector("#data-export"),vehicles:document.querySelectorAll(".vehicle-card").length,errors:'+JSON.stringify(errors)+'})')}catch(e){diagnostic={diagnosticError:String(e)}}throw Error('Timed out: '+label+'; browser state='+JSON.stringify(diagnostic))}
async function fixture(){
  return await value(`(async()=>{
    async function request(path,method,payload){const response=await fetch(path,{method,headers:{'Content-Type':'application/json','X-Garage-Request':'1'},body:JSON.stringify(payload)});let body;try{body=await response.json()}catch{}if(!response.ok)throw Error(path+' failed ('+response.status+'): '+JSON.stringify(body));return body}
    const capabilities=await(await fetch('/garage-api/capabilities')).json();
    const one=(await request('/garage-api/vehicles','POST',{make:'Synthetic Export',model:'One',odometerUnit:'km'}));
    const two=(await request('/garage-api/vehicles','POST',{make:'Synthetic Export',model:'Two',odometerUnit:'mi'}));
    const status=await request('/garage-api/vehicles/'+one.id+'/status','PUT',{readiness:'not_ready',revision:0,issues:[{text:'Synthetic completed issue',dueDate:'2026-10-20',severity:'critical'},{text:'Synthetic remaining issue',dueDate:null,severity:null,lifecycle:'observed'}]});
    await request('/garage-api/vehicles/'+one.id+'/odometer','POST',{date:'2026-10-27',odometer:12345.875,unit:'km',note:'Synthetic fractional reading',commandId:crypto.randomUUID()});
    await request('/garage-api/vehicles/'+two.id+'/odometer','POST',{date:'2026-10-27',odometer:9876.125,unit:'mi',note:'Second vehicle reading',commandId:crypto.randomUUID()});
    const created=await request('/garage-api/vehicles/'+one.id+'/records','POST',{description:'Synthetic repair before correction',kind:'repair',date:'2026-10-26',odometer:12345.125,cost:'12.30',currency:'EUR',documentUrl:'https://documents.example.test/export/receipt',closeIssueId:status.issues[0].id,statusRevision:status.revision,commandId:crypto.randomUUID()});
    const record=created.record;
    await request('/garage-api/vehicles/'+one.id+'/records/'+record.id,'PUT',{revision:record.revision,commandId:crypto.randomUUID(),description:'Synthetic repair after correction',kind:'service',cost:'13.40',currency:'EUR',documentUrl:'https://documents.example.test/export/corrected',correctionReason:'Synthetic receipt checked.'});
    return {one,two,applicationVersion:capabilities.version};
  })()`);
}
async function main(){
  if(!binary)throw Error('Chromium binary not found');
  browser=spawn(binary,['--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-proxy-server','--remote-debugging-port=9243','--remote-allow-origins=*','--user-data-dir=/tmp/wg-owner-export-chromium','about:blank'],{stdio:'ignore'});
  let target;for(let i=0;i<80;i++){try{const r=await fetch('http://127.0.0.1:9243/json/new?about:blank',{method:'PUT'});if(r.ok){target=await r.json();break}}catch{}await delay(100)}
  if(!target)throw Error('Chromium start failed');
  socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((ok,fail)=>{socket.onopen=ok;socket.onerror=fail});
  socket.onmessage=e=>{const m=JSON.parse(e.data);if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}};
  await call('Page.enable');await call('Runtime.enable');await call('Emulation.setDeviceMetricsOverride',{width:390,height:900,deviceScaleFactor:1,mobile:true});
  await call('Page.setDownloadBehavior',{behavior:'allow',downloadPath:downloadDir});
  await call('Page.navigate',{url:'http://127.0.0.1:18987/'});
  await until('!document.querySelector("#own-toolbar")?.hidden && document.querySelector("#status")?.textContent.includes("leer")','empty standalone page');
  const vehicles=await fixture();
  await value('document.querySelector("#refresh").click()');
  await until('document.querySelectorAll(".vehicle-card").length===2 && !document.querySelector("#data-export-wrap").hidden','two vehicles and export link visible');
  if(!await value('document.querySelector("#data-export")?.getAttribute("download")==="wolfs-garage-export.json" && document.querySelector("#data-export").getAttribute("href")==="/garage-api/export"'))throw Error('Visible export link does not identify the JSON attachment');

  await value('document.querySelector("#data-export").click()');
  const downloaded=path.join(downloadDir,'wolfs-garage-export.json');
  for(let i=0;i<120&&!fs.existsSync(downloaded);i++)await delay(100);
  if(!fs.existsSync(downloaded))throw Error('JSON export download did not complete');
  const text=fs.readFileSync(downloaded,'utf8');const data=JSON.parse(text);
  if(data.format!=='wolfs-garage-owner-export'||data.formatVersion!==3||data.databaseSchema!==5||data.applicationVersion!==vehicles.applicationVersion)throw Error('Downloaded export metadata is invalid');
  if(data.vehicles.length!==2||!data.vehicles.some(v=>v.id===vehicles.one.id)||!data.vehicles.some(v=>v.id===vehicles.two.id))throw Error('Downloaded export does not include both synthetic vehicles');
  if(data.records.length!==1||data.records[0].description!=='Synthetic repair after correction'||data.records[0].cost!=='13.40')throw Error('Downloaded export does not include corrected synthetic record');
  if(data.odometerReadings.length!==3||!data.odometerReadings.every(x=>typeof x.odometer==='string'))throw Error('Downloaded export lost odometer rows or exact string values');
  if(!data.odometerReadings.every(x=>Number.isInteger(x.revision)&&['manual','record'].includes(x.provenance))||!data.odometerReadings.some(x=>x.provenance==='record'&&x.sourceRecordId===data.records[0].id))throw Error('Format 3 export omitted reading revision/provenance/link fields');
  if(!data.history.some(e=>e.action==='issue.completed')||!data.history.some(e=>e.action==='record.corrected'))throw Error('Downloaded export is missing closure or correction history');
  if(data.commands!==undefined||text.includes('commandId'))throw Error('Export unexpectedly contains command replay state');
  if(errors.length)throw Error('JavaScript errors: '+errors.join(','));
  console.log('Visible JSON export link, two synthetic vehicles, corrected record, exact odometer text and audit history: PASS');
}
main().catch(e=>{console.error(e.stack||e.message);process.exitCode=1}).finally(()=>{if(socket)socket.close();if(browser)browser.kill();fs.rmSync(downloadDir,{recursive:true,force:true})});
