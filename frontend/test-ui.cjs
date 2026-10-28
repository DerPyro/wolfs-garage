// Offline DOM/HTTP smoke test; no browser, backend or production data required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.attributes = {}; this.hidden = false; this.listeners = {}; this._text = ''; this.classList = { toggle() {}, add() {} }; this.value = ''; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  append(...children) { for (const child of children) child.parent = this; this.children.push(...children); }
  prepend(...children) { for (const child of children) child.parent = this; this.children.unshift(...children); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
  focus() {}
  querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tagName === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
}
async function run(fetchMock, {standalone = false, recordCorrections = false} = {}) {
  const nodes = Object.fromEntries(['status','vehicles','vehicle-count','refresh','detail','detail-heading','detail-meta','detail-status','detail-content','reminders','services','condition-panel','condition-view','condition-readiness','condition-issues','condition-edit','condition-form','readiness-input','issue-editor','issue-add','condition-message','condition-save','condition-cancel','legacy-manage','legacy-banner','own-toolbar','own-detail-actions','own-notice','own-panel','own-title','own-form','own-fields','own-hint','own-message','own-save','own-cancel','record-edit-readonly','record-edit-readonly-date','record-edit-readonly-odometer','record-edit-readonly-closed-issue','vehicle-add','vehicle-edit','odometer-add','record-add','history-toggle','history-panel','history-events','history-message','reminders-panel'].map(id => [id, new Element()]));
  for (const id of ['own-panel', 'history-panel', 'condition-form']) nodes[id].hidden = true;
  const find = (node, id) => node.id === id ? node : node.children.map(child => find(child, id)).find(Boolean);
  const document = { getElementById: id => nodes[id] || Object.values(nodes).map(node => find(node, id)).find(Boolean), createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag), createTextNode: text => { const n = new Element('#text'); n.textContent = text; return n; } };
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname, 'app.js'), 'utf8'), {document, fetch: (path, options) => path === '/garage-api/capabilities' ? Promise.resolve(standalone ? {ok:true,json:async()=>({backend:'standalone',features:['vehicles','status','odometer','records','history',...(recordCorrections?['recordCorrections']:[])]})} : {ok:false,status:404}) : fetchMock(path, options), Intl, URL, crypto:require('node:crypto').webcrypto, encodeURIComponent, console});
  await new Promise(resolve => setTimeout(resolve, 25));
  return nodes;
}
(async () => {
  let nodes = await run(async () => ({ok: true, json: async () => ({vehicles: []})}));
  assert.match(nodes.status.textContent, /Garage ist noch leer/);
  assert.equal(nodes.vehicles.children.length, 0);
  assert.equal(nodes.status.children[1].href, '/Home');

  nodes = await run(async () => ({ok: false, status: 502}));
  assert.match(nodes.status.textContent, /konnten nicht geladen/);

  const calls = [];
  const status = {readiness:'ready',issues:[{id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',text:'Reifen wechseln'}],revision:2};
  let putBody;
  nodes = await run(async (path,options={}) => {
    calls.push(path);
    if (options.method === 'PUT') { putBody=JSON.parse(options.body); assert.equal(options.headers['X-Garage-Request'],'1'); return {ok:true,json:async()=>({...putBody,issues:[putBody.issues[0],{id:'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',text:'Kontrolle'}],revision:3})}; }
    return {ok: true, json: async () => path.endsWith('/summary')
      ? {vehicle:{status}, reminders: [{description: '<img src=x onerror=alert(1)>', dueDate: '2026-11-01', dueOdometer: null, status: 'Bald'}], services: [{date:'2026-10-20', description:'Ölwechsel', odometer:12000, cost:15, documentUrl:'javascript:alert(1)'}]}
      : {vehicles: [{id: 7, name: 'Mein Auto', make:'Peugeot', vehicleType:'Limousine', licensePlate:'XX-TEST', year:2020, odometer:12000,status}, {id: 8, name:'Mein Motorrad', make:'Yamaha', vehicleType:'Cross-Motorrad',status:{readiness:'not_ready',issues:[{id:20,text:'Reparatur'}],revision:1}}, {id: 9, name:'Ohne Typ', make:'Unbekannt', vehicleType:null, licensePlate:'SEHR-LANGES-TEST-KENNZEICHEN-123456789'}, {id:10, name:'Sicher', make:'<img src=x onerror=alert(1)>', vehicleType:'<script>alert(1)</script>', licensePlate:'<img src=x>'}, {id:11, name:'Beispiel Van', make:'Opel', vehicleType:'Hochdachkombi'}, {id:12, name:'Beispiel Motorrad', make:'Suzuki', vehicleType:'Naked Bike'}, {id:13, name:'Beispiel 1', vehicleType:'Schrägheck'}, {id:14, name:'Beispiel 2', vehicleType:'Schraegheck'}, {id:15, name:'Beispiel 3', vehicleType:'Hatchback'}]}};
  });
  assert.deepEqual(calls, ['/garage-api/vehicles','/garage-api/vehicles/7/summary']);
  assert.equal(nodes.vehicles.children.length, 9);
  assert.match(nodes.vehicles.textContent, /Mein Auto/);
  const meta = card => card.children.find(child => child.className === 'vehicle-meta');
  const plate = meta(nodes.vehicles.children[0]).children.find(child => child.className === 'license-plate');
  assert.equal(plate.textContent, 'XX-TEST');
  assert.equal(plate.attributes['aria-label'], 'Kennzeichen XX-TEST');
  assert.equal(plate.attributes.role, 'img');
  assert.equal(meta(nodes.vehicles.children[0]).children[1].textContent, '2020');
  assert.equal(meta(nodes.vehicles.children[1]), undefined);
  assert.equal(meta(nodes.vehicles.children[2]).children[0].textContent, 'SEHR-LANGES-TEST-KENNZEICHEN-123456789');
  assert.equal(meta(nodes.vehicles.children[3]).children[0].textContent, '<img src=x>');
  assert.match(nodes.vehicles.textContent, /PEUGEOT/);
  assert.match(nodes.vehicles.textContent, /YAMAHA/);
  assert.doesNotMatch(nodes.vehicles.textContent, /Cross-Motorrad/);
  assert.match(nodes.vehicles.children[1].attributes['aria-label'], /Fahrzeugtyp Cross-Motorrad/);
  assert.match(nodes.vehicles.children[4].attributes['aria-label'], /Fahrzeugtyp Hochdachkombi/);
  assert.match(nodes.vehicles.children[5].attributes['aria-label'], /Fahrzeugtyp Naked Bike/);
  const glyph = card => card.children[0].children[0].children[0].children[0].attributes.href;
  assert.equal(glyph(nodes.vehicles.children[0]), '#i-sedan');
  assert.equal(glyph(nodes.vehicles.children[1]), '#i-cross');
  assert.equal(glyph(nodes.vehicles.children[2]), '#i-vehicle');
  assert.equal(glyph(nodes.vehicles.children[4]), '#i-highroof');
  assert.equal(glyph(nodes.vehicles.children[5]), '#i-naked');
  for (const i of [6, 7, 8]) assert.equal(glyph(nodes.vehicles.children[i]), '#i-hatchback');
  const mark = card => card.children.find(child => child.className === 'manufacturer manufacturer-watermark');
  assert.equal(mark(nodes.vehicles.children[0]).children[0].src, '/garage-assets/brands/peugeot.svg');
  assert.equal(mark(nodes.vehicles.children[1]).children[0].src, '/garage-assets/brands/yamaha-motor.svg');
  assert.equal(mark(nodes.vehicles.children[4]).children[0].src, '/garage-assets/brands/opel.svg');
  assert.equal(mark(nodes.vehicles.children[5]).children[0].src, '/garage-assets/brands/suzuki.svg');
  assert.equal(mark(nodes.vehicles.children[2]).children[0].tagName, 'span');
  assert.equal(glyph(nodes.vehicles.children[3]), '#i-vehicle');
  assert.equal(mark(nodes.vehicles.children[3]).children[0].tagName, 'span');
  assert.doesNotMatch(nodes.vehicles.children[3].textContent, /<script>/);
  assert.match(nodes.vehicles.children[3].attributes['aria-label'], /<script>alert\(1\)<\/script>/);
  assert.equal(nodes.detail.hidden, false);
  assert.equal(nodes['detail-content'].hidden, false);
  assert.match(nodes.reminders.textContent, /<img src=x onerror=alert\(1\)>/);
  assert.match(nodes.reminders.textContent, /01\.11\.2026/);
  assert.match(nodes.services.textContent, /Ölwechsel/);
  assert.doesNotMatch(nodes.services.textContent, /Beleg öffnen/);
  assert.match(nodes.services.textContent, /Stand 12\.000 \(Einheit unbekannt\)/);
  assert.match(nodes.services.textContent, /Kosten: 15 \(Währung unbekannt\)/);
  const indicators = card => card.children[0].children.find(child => child.className === 'card-indicators');
  assert.equal(indicators(nodes.vehicles.children[0]).children.length, 1);
  assert.equal(indicators(nodes.vehicles.children[0]).children[0].className, 'card-work');
  assert.equal(indicators(nodes.vehicles.children[0]).children[0].attributes.title, 'Wartung ausstehend');
  assert.equal(indicators(nodes.vehicles.children[0]).children[0].children.length, 1);
  assert.equal(indicators(nodes.vehicles.children[1]).children[0].textContent, 'INOP');
  assert.equal(indicators(nodes.vehicles.children[1]).children[1].className, 'card-work');
  assert.equal(indicators(nodes.vehicles.children[1]).children[1].attributes.title, 'Wartung ausstehend');
  assert.equal(indicators(nodes.vehicles.children[2]).children[0].textContent, '!');
  assert.doesNotMatch(nodes.vehicles.children[0].textContent, /Reifen wechseln/);
  assert.match(nodes.vehicles.children[0].attributes['aria-label'], /Fahrbereit, Offen: Reifen wechseln/);
  assert.match(nodes.vehicles.children[1].attributes['aria-label'], /Nicht fahrbereit, Offen: Reparatur/);
  assert.match(nodes['condition-issues'].textContent, /Reifen wechseln/);
  nodes['condition-edit'].listeners.click();
  assert.equal(nodes['condition-form'].hidden, false);
  assert.equal(nodes['issue-editor'].querySelectorAll('input')[0].value, 'Reifen wechseln');
  nodes['readiness-input'].value='not_ready';
  nodes['issue-add'].listeners.click();
  nodes['issue-editor'].querySelectorAll('input')[1].value='Kontrolle';
  await nodes['condition-form'].listeners.submit({preventDefault(){}});
  assert.deepEqual(putBody,{readiness:'not_ready',issues:[{id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',text:'Reifen wechseln'},{text:'Kontrolle'}],revision:2});
  assert.equal(nodes['condition-form'].hidden,true);
  assert.equal(indicators(nodes.vehicles.children[0]).children[0].textContent,'INOP');
  const conflictStatus = {readiness:'unknown',issues:[],revision:0};
  nodes = await run(async (path,options={}) => options.method === 'PUT'
    ? {ok:false,status:409}
    : {ok:true,json:async()=>path.endsWith('/summary') ? {vehicle:{status:conflictStatus},reminders:[],services:[]} : {vehicles:[{id:1,name:'Test',status:conflictStatus}]}});
  assert.equal(indicators(nodes.vehicles.children[0]).children[0].textContent, '?');
  assert.match(nodes.vehicles.children[0].attributes['aria-label'], /Status nicht erfasst/);
  nodes['condition-edit'].listeners.click();
  await nodes['condition-form'].listeners.submit({preventDefault(){}});
  assert.equal(nodes['condition-form'].hidden,false);
  assert.match(nodes['condition-message'].textContent,/inzwischen geändert/);
  const manyIssues = Array.from({length:20}, (_,index) => ({id:String(index),text:'Lang'.repeat(40)}));
  nodes = await run(async path => ({ok:true,json:async()=>path.endsWith('/summary') ? {vehicle:{status:{readiness:'ready',issues:manyIssues,revision:1}},reminders:[],services:[]} : {vehicles:[{id:1,name:'Test',status:{readiness:'ready',issues:manyIssues,revision:1}}]}}));
  assert.equal(indicators(nodes.vehicles.children[0]).children[0].attributes.title, 'Wartung ausstehend');
  assert.equal(indicators(nodes.vehicles.children[0]).children[0].children.length, 1);
  assert.doesNotMatch(nodes.vehicles.children[0].textContent, /LangLang/);
  assert.match(nodes.vehicles.children[0].attributes['aria-label'], /Offen: LangLang/);
  assert.match(nodes['condition-issues'].textContent, /LangLang/);
  nodes = await run(async () => ({ok:false,status:503}));
  assert.match(nodes.status.textContent,/Zustandsspeicher.*nicht verfügbar/);

  // The standalone flow preserves command IDs after a failed response and keeps readiness independent of a completed issue.
  let ownVehicles = [];
  const ownWrites = [];
  let odometerAttempts = 0;
  let lastRecord;
  const ownStatus = {readiness:'not_ready',issues:[{id:'cccccccccccccccccccccccccccccccc',text:'Prüfung durchführen'}],revision:1};
  nodes = await run(async (path, options = {}) => {
    if (options.method) {
      const body=JSON.parse(options.body); ownWrites.push({path,method:options.method,body});
      assert.equal(options.headers['X-Garage-Request'],'1'); assert.equal(options.credentials,'same-origin');
      if (path === '/garage-api/vehicles') { ownVehicles=[{id:1,...body,name:body.make+' '+body.model,revision:1,status:ownStatus}]; return {ok:true,json:async()=>ownVehicles[0]}; }
      if (options.method === 'PUT') { ownVehicles[0]={...ownVehicles[0],...body,name:body.make+' '+body.model,revision:2}; return {ok:true,json:async()=>ownVehicles[0]}; }
      if (path.endsWith('/odometer')) { if (++odometerAttempts===1) return {ok:false,status:502,json:async()=>({error:'Bitte erneut versuchen'})}; ownVehicles[0].odometer=body.odometer; return {ok:true,json:async()=>body}; }
      if (path.endsWith('/records')) { ownVehicles[0].status={...ownStatus,issues:[],revision:2}; lastRecord={...body,id:1,odometerUnit:'km'}; return {ok:true,json:async()=>({record:lastRecord,status:ownVehicles[0].status})}; }
    }
    if (path.endsWith('/history')) return {ok:true,json:async()=>({events:[{action:'status.updated',occurredAt:'2026-10-28T12:00:00Z',before:ownStatus,after:ownVehicles[0].status}]})};
    if (path.endsWith('/summary')) return {ok:true,json:async()=>({vehicle:ownVehicles[0],reminders:[],services:lastRecord?[lastRecord]:[]})};
    return {ok:true,json:async()=>({vehicles:ownVehicles})};
  }, {standalone:true});
  assert.equal(nodes['legacy-manage'].hidden,true); assert.equal(nodes['legacy-banner'].hidden,true); assert.equal(nodes['own-toolbar'].hidden,false);
  nodes['vehicle-add'].listeners.click();
  const input = id => { const search = node => node.id === 'entry-'+id ? node : node.children.map(search).find(Boolean); return search(nodes['own-fields']); };
  input('make').value='Beispiel'; input('model').value='Fahrzeug'; input('year').value='2020';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(ownWrites[0].path,'/garage-api/vehicles'); assert.equal(nodes['own-panel'].hidden,true); assert.match(nodes.vehicles.textContent,/Beispiel Fahrzeug/);
  nodes['vehicle-edit'].listeners.click(); input('model').value='Korrigiert';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(ownWrites[1].body.revision,1); assert.match(nodes.vehicles.textContent,/Beispiel Korrigiert/);
  nodes['odometer-add'].listeners.click(); input('odometer').value='1200';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(nodes['own-panel'].hidden,false); assert.match(nodes['own-message'].textContent,/erneut versuchen/);
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(ownWrites[2].body.commandId,ownWrites[3].body.commandId); assert.match(ownWrites[2].body.commandId,/^[0-9a-f-]{36}$/);
  nodes['record-add'].listeners.click(); input('description').value='Prüfung abgeschlossen'; input('kind').value='repair'; input('cost').value='49,90'; input('currency').value='eur'; input('closeIssueId').value='cccccccccccccccccccccccccccccccc'; input('documentUrl').value='https://example.invalid/beleg';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  const completion=ownWrites[4].body; assert.equal(completion.statusRevision,1); assert.equal(completion.cost,'49.90'); assert.equal(completion.currency,'EUR'); assert.equal(completion.closeIssueId,'cccccccccccccccccccccccccccccccc');
  assert.equal(indicators(nodes.vehicles.children[0]).children[0].textContent,'INOP'); assert.equal(indicators(nodes.vehicles.children[0]).children.length,1);
  assert.match(nodes.services.textContent,/Prüfung abgeschlossen/); assert.match(nodes.services.textContent,/Beleg öffnen/);
  assert.equal(nodes.services.querySelectorAll('button').some(button=>button.className==='condition-edit record-edit'),false);
  await nodes['history-toggle'].listeners.click();
  assert.equal(nodes['history-panel'].hidden,false); assert.match(nodes['history-events'].textContent,/Zustand aktualisiert/); assert.match(nodes['history-events'].textContent,/Nicht fahrbereit/); assert.match(nodes['history-events'].textContent,/Prüfung durchführen/);
  // Record correction loads the canonical record first, sends only mutable fields and records removals in history.
  const correctionCalls=[];
  const closedIssueId='cccccccccccccccccccccccccccccccc';
  const originalRecord={id:77,description:'Ölwechsel',kind:'service',date:'2026-10-20',odometer:12000,odometerUnit:'km',cost:'49.90',currency:'EUR',documentUrl:'https://example.invalid/rechnung',closedIssueId,revision:4};
  let correctedRecord;
  nodes=await run(async (path,options={})=>{
    correctionCalls.push({path,options});
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[{id:1,name:'Testfahrzeug',status:{readiness:'ready',issues:[],revision:2}}]})};
    if(path==='/garage-api/vehicles/1/summary') return {ok:true,json:async()=>({vehicle:{status:{readiness:'ready',issues:[],revision:2}},reminders:[],services:[correctedRecord||originalRecord]})};
    if(path==='/garage-api/vehicles/1/records/77' && !options.method) return {ok:true,json:async()=>originalRecord};
    if(path==='/garage-api/vehicles/1/records/77' && options.method==='PUT') {
      correctedRecord={...originalRecord,...JSON.parse(options.body),revision:5}; return {ok:true,json:async()=>({record:correctedRecord})};
    }
    if(path==='/garage-api/vehicles/1/history') return {ok:true,json:async()=>({events:[{action:'record.corrected',occurredAt:'2026-10-28T12:00:00Z',before:{record:originalRecord},after:{record:correctedRecord,correctionReason:'Rechnung war doppelt'}}]})};
    throw new Error('Unexpected mock request: '+path);
  },{standalone:true,recordCorrections:true});
  const correctionButton=nodes.services.querySelectorAll('button').find(button=>button.id==='record-edit-77');
  assert.ok(correctionButton,'recordCorrections capability exposes the per-record editor');
  await correctionButton.listeners.click();
  assert.deepEqual(correctionCalls.filter(call=>!call.options.method).map(call=>call.path).filter(path=>path.endsWith('/records/77')),['/garage-api/vehicles/1/records/77']);
  assert.equal(nodes['record-edit-readonly'].hidden,false);
  assert.match(nodes['record-edit-readonly-date'].textContent,/20\.10\.2026/);
  assert.match(nodes['record-edit-readonly-odometer'].textContent,/12\.000 km/);
  assert.match(nodes['record-edit-readonly-closed-issue'].textContent,/Punktabschluss.*unverändert/);
  assert.doesNotMatch(nodes['record-edit-readonly-closed-issue'].textContent,/cccccccc/);
  const correctionInput=name=>nodes['own-fields'].querySelectorAll('input').concat(nodes['own-fields'].querySelectorAll('select')).find(field=>field.id==='entry-'+name);
  assert.equal(correctionInput('description').value,'Ölwechsel');
  assert.equal(correctionInput('kind').value,'service');
  correctionInput('description').value='Ölwechsel und Filter';
  correctionInput('kind').value='repair';
  correctionInput('cost').value='';
  correctionInput('currency').value='';
  correctionInput('documentUrl').value='';
  correctionInput('correctionReason').value='Rechnung war doppelt';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  const correctionWrite=correctionCalls.find(call=>call.options.method==='PUT');
  assert.equal(correctionWrite.path,'/garage-api/vehicles/1/records/77');
  assert.equal(correctionWrite.options.headers['X-Garage-Request'],'1');
  const correctionPayload=JSON.parse(correctionWrite.options.body);
  assert.deepEqual(Object.keys(correctionPayload).sort(),['commandId','correctionReason','cost','currency','description','documentUrl','kind','revision'].sort());
  assert.equal(correctionPayload.revision,4);
  assert.match(correctionPayload.commandId,/^[0-9a-f-]{36}$/);
  assert.equal(correctionPayload.cost,null); assert.equal(correctionPayload.currency,null); assert.equal(correctionPayload.documentUrl,null);
  assert.equal(correctionPayload.description,'Ölwechsel und Filter'); assert.equal(correctionPayload.kind,'repair');
  assert.equal(correctionPayload.correctionReason,'Rechnung war doppelt');
  assert.equal(nodes['record-edit-readonly'].hidden,true);
  assert.equal(nodes['history-panel'].hidden,false);
  assert.match(nodes['history-events'].textContent,/Beleg korrigiert/);
  assert.match(nodes['history-events'].textContent,/Kosten entfernt/);
  assert.match(nodes['history-events'].textContent,/Beleglink entfernt/);
  assert.match(nodes['history-events'].textContent,/Rechnung war doppelt/);
  assert.match(nodes['history-events'].textContent,/Offener Punkt bei der Erfassung abgeschlossen/);
  assert.doesNotMatch(nodes['history-events'].textContent,/cccccccccccccccccccccccccccccccc/);
  assert.match(nodes['history-events'].textContent,/49,9 EUR|49,90 EUR/);
  assert.match(nodes.services.textContent,/Ölwechsel und Filter/);

  console.log('Frontend: Legacy-Anzeige, Standalone-Erfassung, Retry-ID, Belegkorrektur und Verlauf bestanden.');
})().catch(err => { console.error(err); process.exitCode = 1; });
