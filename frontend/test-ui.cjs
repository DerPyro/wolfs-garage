// Offline DOM/HTTP smoke test; no browser, backend or production data required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.attributes = {}; this.hidden = false; this.listeners = {}; this._text = ''; this.classList = { toggle() {}, add() {} }; this.value = ''; this.checked = false; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; }
  append(...children) { for (const child of children) child.parent = this; this.children.push(...children); }
  prepend(...children) { for (const child of children) child.parent = this; this.children.unshift(...children); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); }
  focus(options) { this.focused = true; this.focusOptions = options; }
  scrollIntoView(options) { this.scrollCount = (this.scrollCount || 0) + 1; this.scrollOptions = options; }
  click() { this.clicked = true; if (this.listeners.click) return this.listeners.click(); }
  contains(target) { return this === target || this.children.some(child => child.contains(target)); }
  querySelectorAll(tag) { return this.children.flatMap(child => [...(child.tagName === tag ? [child] : []), ...child.querySelectorAll(tag)]); }
  replaceChildren(...children) { this._text = ''; this.children = children; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
}
async function run(fetchMock, {standalone = false, recordCorrections = false, measurementCorrections = false, historyBrowsing = false, scheduledWork = false, dataExport = false, databaseBackup = false, inspectionStatus = false, mileageForecast = false, reducedMotion = false, version = '0.1.0a0', initialHash = '', storageUnavailable = false, storedMotionPreference = null} = {}) {
  const nodes = Object.fromEntries(['status','vehicles','vehicle-count','refresh','detail','detail-heading','detail-meta','detail-status','detail-content','mileage-forecast','mileage-prompts','mileage-prompt-status','mileage-prompt-items','reminders','services','condition-panel','condition-view','condition-readiness','condition-issues','condition-work-asof','inspection-panel','inspection-message','issue-filter-wrap','issue-filter','condition-edit','condition-form','readiness-input','issue-editor','issue-add','condition-message','condition-save','condition-cancel','legacy-manage','legacy-banner','own-toolbar','data-export-wrap','data-export','data-export-hint','database-backup','database-backup-hint','database-backup-message','backup-restore-help','own-detail-actions','own-notice','own-panel','own-title','own-form','own-fields','own-hint','own-message','own-save','own-cancel','record-edit-readonly','record-edit-readonly-date','record-edit-readonly-odometer','record-edit-readonly-closed-issue','measurement-projection-warning','vehicle-add','vehicle-edit','odometer-add','record-add','history-toggle','history-panel','history-events','history-message','reminders-panel','work-dashboard','work-status','work-items','logbook-toggle','logbook-panel','logbook-close','logbook-filters','logbook-type','logbook-from','logbook-to','logbook-kind','logbook-kind-field','logbook-apply','logbook-message','logbook-records','logbook-more','logbook-reload','nav-toggle','site-navigation','nav-garage','nav-backups','nav-settings','garage-view','backups-view','settings-view','garage-title','backups-title','settings-title','app-version','motion-preference','motion-message'].map(id => [id, new Element()]));
  nodes['nav-garage'].setAttribute('href','#garage'); nodes['nav-backups'].setAttribute('href','#sicherungen'); nodes['nav-settings'].setAttribute('href','#einstellungen');
  nodes['site-navigation'].append(nodes['nav-garage'],nodes['nav-backups'],nodes['nav-settings']);
  nodes['garage-view'].hidden=false; nodes['backups-view'].hidden=true; nodes['settings-view'].hidden=true; nodes['site-navigation'].hidden=true;
  nodes['inspection-panel'].append(nodes['inspection-message']);
  nodes['own-detail-actions'].setAttribute('tabindex','-1');
  nodes['data-export'].href='/garage-api/export'; nodes['data-export'].download='wolfs-garage-export.json'; nodes['data-export'].textContent='Portabler JSON-Export';
  nodes['data-export-hint'].textContent='JSON-Datei mit Fahrzeugdaten und Verlauf zur Ansicht oder Übertragung. Sie dient nicht zur Wiederherstellung.';
  nodes['database-backup-hint'].textContent='Die Sicherung enthält alle Garage-Anwendungsdaten einschließlich Verlauf. Konfiguration und externe Dokumente sind nicht enthalten.';
  nodes['backup-restore-help'].append(new Element('summary'), new Element('div'));
  nodes['backup-restore-help'].children[0].textContent='Import / Wiederherstellen'; nodes['backup-restore-help'].children[1].textContent='Die Wiederherstellung läuft offline auf dem Server. Stoppe die Anwendung vor der Übernahme und erstelle eine neue Datenbank: python -m wolfs_garage restore-backup BACKUP.sqlite3 NEUE_DATENBANK.sqlite3 Es gibt keinen Upload oder Import im Browser.';
  for (const id of ['own-panel', 'history-panel', 'condition-form', 'work-dashboard','inspection-panel']) nodes[id].hidden = true;
  const find = (node, id) => node.id === id ? node : node.children.map(child => find(child, id)).find(Boolean);
  const documentListeners = {}, windowListeners = {}, storage = new Map();
  if (storedMotionPreference === 'system' || storedMotionPreference === 'reduce') storage.set('wolfs-garage-motion-preference', storedMotionPreference);
  let inspectionInterval;
  const downloads = []; const body = new Element('body');
  const objectUrls = {created:[],revoked:[],createObjectURL(blob){this.created.push(blob);return `blob:test-${this.created.length}`;},revokeObjectURL(url){this.revoked.push(url);}};
  const URLMock = class extends URL {};
  URLMock.createObjectURL = blob => objectUrls.createObjectURL(blob); URLMock.revokeObjectURL = url => objectUrls.revokeObjectURL(url);
  const document = { body, visibilityState:'visible', addEventListener:(name, listener)=>{documentListeners[name]=listener;}, getElementById: id => nodes[id] || Object.values(nodes).map(node => find(node, id)).find(Boolean), createElement: tag => {const element=new Element(tag); if(tag==='a')downloads.push(element); return element;}, createElementNS: (_, tag) => new Element(tag), createTextNode: text => { const n = new Element('#text'); n.textContent = text; return n; } };
  const scrollCalls=[]; const window = {location:{_hash:initialHash},matchMedia:()=>({matches:reducedMotion}),addEventListener:(name,listener)=>{windowListeners[name]=listener;},scrollTo:options=>scrollCalls.push(options)};
  Object.defineProperty(window.location,'hash',{get(){return this._hash||'';},set(value){this._hash=String(value).startsWith('#')?String(value):`#${value}`; if(windowListeners.hashchange)windowListeners.hashchange({});}});
  const localStorage = storageUnavailable ? {getItem(){throw new Error('blocked');},setItem(){throw new Error('blocked');}} : {getItem(key){return storage.has(key)?storage.get(key):null;},setItem(key,value){storage.set(key,String(value));}};
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname, 'app.js'), 'utf8'), {document, window, localStorage, fetch: (path, options) => path === '/garage-api/capabilities' ? Promise.resolve(standalone ? {ok:true,json:async()=>({backend:'standalone',version,features:['vehicles','status','odometer','records','history',...(recordCorrections?['recordCorrections']:[]),...(measurementCorrections?['measurementCorrections']:[]),...(historyBrowsing?['historyBrowsing']:[]),...(scheduledWork?['scheduledWork']:[]),...(dataExport?['dataExport']:[]),...(databaseBackup?['databaseBackup']:[]),...(inspectionStatus?['inspectionStatus']:[]),...(mileageForecast?['mileageForecast']:[])]})} : {ok:false,status:404}) : fetchMock(path, options), Intl, URL:URLMock, TextDecoder, TypeError, crypto:require('node:crypto').webcrypto, encodeURIComponent, console, setInterval:(callback,delay)=>{inspectionInterval={callback,delay};return 1;}});
  Object.defineProperty(nodes,'__downloads',{value:downloads}); Object.defineProperty(nodes,'__objectUrls',{value:objectUrls});
  Object.defineProperty(nodes,'__storage',{value:storage}); Object.defineProperty(nodes,'__documentListeners',{value:documentListeners}); Object.defineProperty(nodes,'__windowListeners',{value:windowListeners});
  Object.defineProperty(nodes,'__setHash',{value:value=>{window.location.hash=value;}});
  Object.defineProperty(nodes,'__scrollCalls',{value:scrollCalls});
  Object.defineProperty(nodes,'__visibilityChanged',{value:async visibilityState=>{document.visibilityState=visibilityState;return documentListeners.visibilitychange&&documentListeners.visibilitychange();}});
  Object.defineProperty(nodes,'__inspectionTick',{value:async()=>inspectionInterval&&inspectionInterval.callback()});
  Object.defineProperty(nodes,'__inspectionInterval',{value:()=>inspectionInterval&&inspectionInterval.delay});
  await new Promise(resolve => setTimeout(resolve, 25));
  return nodes;
}
function huProjection({asOf='2026-10-28',dueMonth=null,state='unknown',monthsUntilDue=null,batteryLevel=null,blocksReadiness=false,validUntil=null,blockingFrom=null}={}) {
  return {asOf,timeZone:'Europe/Berlin',dueMonth,validUntil,blockingFrom,state,monthsUntilDue,blocksReadiness,batteryLevel,scaleMonths:12};
}
function huVehicle({id=1,name='Prüffahrzeug',dueMonth=null,inspection=huProjection(),readiness='ready',effectiveReadiness=readiness,revision=1}={}) {
  return {id,name,make:'Test',model:'Fahrzeug',vehicleType:'Limousine',odometerUnit:'km',revision,inspectionDueMonth:dueMonth,inspection,effectiveReadiness,status:{readiness,issues:[],revision:1}};
}
(async () => {
  let nodes = await run(async () => ({ok: true, json: async () => ({vehicles: []})}));
  assert.match(nodes.status.textContent, /Garage ist noch leer/);
  assert.equal(nodes.vehicles.children.length, 0);
  assert.equal(nodes.status.children[1].href, '/Home');

  nodes = await run(async () => ({ok: false, status: 502}));
  assert.match(nodes.status.textContent, /konnten nicht geladen/);

  // Header views are hash-addressable, backup navigation is capability-gated, and settings are backed by version data.
  nodes = await run(async () => ({ok:true,json:async()=>({vehicles:[]})}), {standalone:true,dataExport:true,databaseBackup:true,version:'0.1.0a7'});
  assert.equal(nodes['garage-view'].hidden,false); assert.equal(nodes['backups-view'].hidden,true); assert.equal(nodes['settings-view'].hidden,true);
  assert.equal(nodes['nav-backups'].hidden,false); assert.equal(nodes['app-version'].textContent,'Version 0.1.0a7');
  nodes['nav-toggle'].listeners.click();
  assert.equal(nodes['site-navigation'].hidden,false); assert.equal(nodes['nav-toggle'].attributes['aria-expanded'],'true');
  nodes['nav-settings'].listeners.click({currentTarget:nodes['nav-settings'],preventDefault(){}});
  assert.equal(nodes['settings-view'].hidden,false); assert.equal(nodes['garage-view'].hidden,true); assert.equal(nodes['nav-settings'].attributes['aria-current'],'page');
  assert.equal(nodes['settings-title'].focused,true); assert.equal(nodes['settings-title'].focusOptions.preventScroll,true);
  assert.equal(nodes.__scrollCalls.at(-1).top,0); assert.equal(nodes.__scrollCalls.at(-1).behavior,'auto');
  assert.equal(nodes['site-navigation'].hidden,true); assert.equal(nodes['nav-toggle'].attributes['aria-expanded'],'false');
  nodes['nav-toggle'].listeners.click();
  nodes.__documentListeners.keydown({key:'Escape',preventDefault(){this.prevented=true;}});
  assert.equal(nodes['site-navigation'].hidden,true); assert.equal(nodes['nav-toggle'].focused,true,'Escape closes disclosure and returns focus to its button');
  nodes['nav-toggle'].listeners.click();
  nodes.__documentListeners.click({target:nodes.status});
  assert.equal(nodes['site-navigation'].hidden,true,'clicking outside closes the disclosure');
  nodes.__setHash('#garage');
  assert.equal(nodes['garage-view'].hidden,false); assert.equal(nodes['nav-garage'].attributes['aria-current'],'page');
  nodes.__setHash('#sicherungen');
  assert.equal(nodes['backups-view'].hidden,false); assert.equal(nodes['data-export-wrap'].hidden,false);
  nodes['motion-preference'].value='reduce'; nodes['motion-preference'].listeners.change();
  assert.equal(nodes['__storage'].get('wolfs-garage-motion-preference'),'reduce'); assert.match(nodes['motion-message'].textContent,/gespeichert/);
  nodes = await run(async () => ({ok:true,json:async()=>({vehicles:[]})}), {standalone:false,initialHash:'#sicherungen'});
  assert.equal(nodes['nav-backups'].hidden,true); assert.equal(nodes['backups-view'].hidden,true); assert.equal(nodes['garage-view'].hidden,false,'legacy mode cannot open the backup view');
  assert.match(nodes['app-version'].textContent,/in diesem Modus nicht verfügbar/);
  nodes = await run(async () => ({ok:true,json:async()=>({vehicles:[]})}), {standalone:true,storageUnavailable:true});
  assert.equal(nodes['motion-preference'].value,'system');
  nodes['motion-preference'].value='reduce'; nodes['motion-preference'].listeners.change();
  assert.match(nodes['motion-message'].textContent,/bis zum Neuladen/,'storage exceptions leave the setting usable for this page');
  assert.doesNotMatch(fs.readFileSync(require('node:path').join(__dirname,'index.html'),'utf8'),/Alles im <em>Blick/,'the promotional intro is removed');

  // HU month projection is explicitly capability-gated and server-dated; the UI only renders its values.
  const huCases = [
    {name:'Vorschau',dueMonth:'2026-12',inspection:huProjection({dueMonth:'2026-12',state:'upcoming',monthsUntilDue:2,batteryLevel:2,validUntil:'2026-12-31',blockingFrom:'2027-02-01'}),expected:/HU \/ TÜV: 31\.12\.2026 · fällig in circa 2 Monaten/,visualLevel:2},
    {name:'Volle Kartenleiste',dueMonth:'2028-10',inspection:huProjection({dueMonth:'2028-10',state:'upcoming',monthsUntilDue:24,batteryLevel:12,validUntil:'2028-10-31',blockingFrom:'2028-12-01'}),expected:/fällig in circa 24 Monaten/,visualLevel:24},
    {name:'Kartenleiste Mitte',dueMonth:'2027-10',inspection:huProjection({dueMonth:'2027-10',state:'upcoming',monthsUntilDue:12,batteryLevel:12,validUntil:'2027-10-31',blockingFrom:'2027-12-01'}),expected:/fällig in circa 12 Monaten/,visualLevel:12},
    {name:'Im Fälligkeitsmonat',dueMonth:'2026-10',inspection:huProjection({dueMonth:'2026-10',state:'due',monthsUntilDue:0,batteryLevel:0,validUntil:'2026-10-31',blockingFrom:'2026-12-01'}),expected:/31\.10\.2026 · fällig diesen Monat/,visualLevel:24,barState:'due'},
    {name:'Erster überfälliger Monat',dueMonth:'2026-08',inspection:huProjection({asOf:'2026-09-15',dueMonth:'2026-08',state:'overdue',monthsUntilDue:-1,batteryLevel:0,validUntil:'2026-08-31',blockingFrom:'2026-10-01'}),expected:/31\.08\.2026 · überfällig seit circa 1 Monat/,visualLevel:24,barState:'expired',marker:'!'},
    {name:'Ab dem zweiten überfälligen Monat blockiert',dueMonth:'2026-08',inspection:huProjection({asOf:'2026-10-01',dueMonth:'2026-08',state:'blocking',monthsUntilDue:-2,batteryLevel:0,blocksReadiness:true,validUntil:'2026-08-31',blockingFrom:'2026-10-01'}),effectiveReadiness:'not_ready',expected:/31\.08\.2026 · überfällig seit circa 2 Monaten · automatisch INOP ab 01\.10\.2026/,visualLevel:24,barState:'expired',marker:'!'},
    {name:'HU nicht erfasst',dueMonth:null,inspection:huProjection(),expected:/HU \/ TÜV: nicht eingetragen/,visualLevel:24,barState:'unknown',marker:'?'}
  ];
  for (const testCase of huCases) {
    const vehicle=huVehicle({...testCase,effectiveReadiness:testCase.effectiveReadiness||'ready'});
    nodes = await run(async path => ({ok:true,json:async()=>path.endsWith('/summary')?{vehicle,reminders:[],services:[]}:{vehicles:[vehicle]}}),{standalone:true,inspectionStatus:true});
    assert.equal(nodes['inspection-panel'].hidden,false,testCase.name);
    assert.match(nodes['inspection-message'].textContent,testCase.expected,testCase.name);
    assert.equal(nodes['inspection-panel'].children.length,1,testCase.name);
    assert.doesNotMatch(nodes['inspection-panel'].textContent,/Stand:|Darstellung:|Vorlauf/,testCase.name);
    assert.match(nodes.vehicles.children[0].attributes['aria-label'],/HU \/ TÜV/,testCase.name);
    assert.equal(nodes['condition-readiness'].textContent,testCase.effectiveReadiness==='not_ready'?'Nicht fahrbereit':'Fahrbereit',testCase.name);
    const cardIndicators=nodes.vehicles.children[0].children[0].children.find(child=>child.className==='card-indicators');
    const cardBattery=nodes.vehicles.children[0].children.find(child=>(child.className||'').startsWith('card-inspection-progress'));
    assert.ok(cardBattery,testCase.name);
    assert.match(cardBattery.attributes.title,/HU \/ TÜV/,testCase.name);
    assert.equal(cardBattery.children.filter(cell=>cell.className.startsWith('card-inspection-cell')).length,24,testCase.name);
    assert.equal(cardBattery.children.filter(cell=>cell.className.includes('filled')).length,testCase.visualLevel||0,testCase.name);
    if (testCase.barState) assert.match(cardBattery.className,new RegExp(` ${testCase.barState}$`),testCase.name);
    else if (testCase.visualLevel) assert.match(cardBattery.className,new RegExp(`level-${testCase.visualLevel}$`),testCase.name);
    const marker=cardBattery.children.find(cell=>cell.className==='card-inspection-marker');
    if (testCase.marker) assert.equal(marker.textContent,testCase.marker,testCase.name);
    else assert.equal(marker,undefined,testCase.name);
    if (testCase.visualLevel) {
      assert.equal(cardBattery.children.findIndex(cell=>cell.className.includes('filled')),24-testCase.visualLevel,testCase.name);
    }
    if (testCase.inspection.state==='unknown') {
      assert.doesNotMatch(nodes['inspection-message'].textContent,/überfällig/);
      assert.doesNotMatch(nodes.vehicles.children[0].attributes['aria-label'],/INOP/);
      assert.equal(cardBattery.className,'card-inspection-progress unknown');
    }
    if (testCase.inspection.state==='blocking') {
      assert.match(nodes.vehicles.children[0].textContent,/INOP/);
      assert.match(nodes['condition-readiness'].textContent,/Nicht fahrbereit/);
      nodes['condition-edit'].listeners.click();
      assert.equal(nodes['readiness-input'].value,'ready','the editor shows manual readiness even while derived readiness is blocked');
    }
  }
  assert.equal(nodes['inspection-panel'].hidden,false);
  const hostileProjection=huVehicle({name:'<img src=x onerror=alert(1)>',dueMonth:'<script>x</script>',inspection:huProjection({dueMonth:'<script>x</script>',state:'upcoming',monthsUntilDue:1,batteryLevel:1,validUntil:'2026-11-30',blockingFrom:'2027-01-01'})});
  nodes=await run(async path=>({ok:true,json:async()=>path.endsWith('/summary')?{vehicle:hostileProjection,reminders:[],services:[]}:{vehicles:[hostileProjection]}}),{standalone:true,inspectionStatus:true});
  assert.equal(nodes.vehicles.children[0].querySelectorAll('img').length,0);
  assert.equal(nodes.vehicles.children[0].querySelectorAll('script').length,0);
  const invalidCardBar=nodes.vehicles.children[0].children.find(child=>(child.className||'').startsWith('card-inspection-progress'));
  assert.equal(invalidCardBar.className,'card-inspection-progress unavailable');
  assert.equal(invalidCardBar.children.filter(cell=>cell.className.includes('filled')).length,24);
  assert.equal(invalidCardBar.children.find(cell=>cell.className==='card-inspection-marker').textContent,'!');
  assert.match(nodes['inspection-message'].textContent,/HU \/ TÜV: Status momentan nicht verfügbar/);

  // Initial selection never scrolls; only the latest explicit card click navigates to its action bar.
  const navVehicles=[1,2].map(id=>({id,name:`Navigation ${id}`,status:{readiness:'ready',issues:[],revision:0}}));
  let releaseStaleSummary, signalStaleSummary; const staleSummaryStarted=new Promise(resolve=>{signalStaleSummary=resolve;});
  nodes=await run(async path=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:navVehicles})};
    const id=Number(path.split('/')[3]), vehicle=navVehicles.find(item=>item.id===id);
    if(id===2) return new Promise(resolve=>{releaseStaleSummary=resolve;signalStaleSummary();});
    return {ok:true,json:async()=>({vehicle,reminders:[],services:[]})};
  },{standalone:true});
  const actionBar=nodes['own-detail-actions'];
  assert.equal(actionBar.scrollCount,undefined,'initial vehicle load does not navigate to detail actions');
  assert.equal(actionBar.focused,undefined);
  const staleCard=nodes.vehicles.children.find(card=>card.attributes['aria-label'].startsWith('Navigation 2'));
  const staleClick=staleCard.listeners.click(); await staleSummaryStarted;
  assert.equal(actionBar.scrollCount,undefined,'navigation waits for the selected vehicle summary');
  const currentCard=nodes.vehicles.children.find(card=>card.attributes['aria-label'].startsWith('Navigation 1'));
  await currentCard.listeners.click();
  assert.equal(actionBar.scrollCount,1); assert.equal(actionBar.scrollOptions.behavior,'smooth'); assert.equal(actionBar.scrollOptions.block,'start');
  assert.equal(actionBar.focused,true); assert.equal(actionBar.focusOptions.preventScroll,true);
  releaseStaleSummary({ok:true,json:async()=>({vehicle:navVehicles[1],reminders:[],services:[]})}); await staleClick;
  assert.equal(actionBar.scrollCount,1,'a stale A→B→A selection cannot scroll or steal focus');
  assert.equal(nodes.vehicles.children.find(card=>card.attributes['aria-label'].startsWith('Navigation 1')).attributes['aria-pressed'],'true');
  nodes=await run(async path=>path==='/garage-api/vehicles'
    ? {ok:true,json:async()=>({vehicles:[navVehicles[0]]})}
    : {ok:true,json:async()=>({vehicle:navVehicles[0],reminders:[],services:[]})},{standalone:true,reducedMotion:true});
  await nodes.vehicles.children[0].listeners.click();
  assert.equal(nodes['own-detail-actions'].scrollOptions.behavior,'auto','reduced motion avoids smooth scrolling');
  nodes=await run(async path=>path==='/garage-api/vehicles'
    ? {ok:true,json:async()=>({vehicles:[navVehicles[0]]})}
    : {ok:true,json:async()=>({vehicle:navVehicles[0],reminders:[],services:[]})},{standalone:true,storedMotionPreference:'reduce'});
  assert.equal(nodes['motion-preference'].value,'reduce','stored motion preference is restored from local storage');
  await nodes.vehicles.children[0].listeners.click();
  assert.equal(nodes['own-detail-actions'].scrollOptions.behavior,'auto','the saved preference reduces action-bar scrolling even when the OS allows motion');
  let delayNextSummary=false, releaseNavigationSummary;
  nodes=await run(async path=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[navVehicles[0]]})};
    if(delayNextSummary){delayNextSummary=false;return new Promise(resolve=>{releaseNavigationSummary=resolve;});}
    return {ok:true,json:async()=>({vehicle:navVehicles[0],reminders:[],services:[]})};
  },{standalone:true});
  delayNextSummary=true;
  const pendingCardSelection=nodes.vehicles.children[0].listeners.click();
  while(!releaseNavigationSummary) await new Promise(resolve=>setTimeout(resolve,1));
  nodes['nav-settings'].listeners.click({currentTarget:nodes['nav-settings'],preventDefault(){}});
  releaseNavigationSummary({ok:true,json:async()=>({vehicle:navVehicles[0],reminders:[],services:[]})}); await pendingCardSelection;
  assert.equal(nodes['own-detail-actions'].scrollCount,undefined,'a vehicle summary finishing after a view switch cannot focus hidden garage actions');
  assert.equal(nodes['settings-title'].focused,true);

  let unsavedVehicle={id:31,name:'Draft vehicle',make:'Example',model:'Original',year:2022,vehicleType:'Limousine',revision:2,status:{readiness:'ready',issues:[],revision:1}}, draftWrites=0;
  nodes=await run(async(path,options={})=>{
    if(options.method){draftWrites++;return {ok:true,json:async()=>unsavedVehicle};}
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[unsavedVehicle]})};
    return {ok:true,json:async()=>({vehicle:unsavedVehicle,reminders:[],services:[]})};
  },{standalone:true,dataExport:true});
  nodes['vehicle-edit'].listeners.click();
  const findModel=node=>node.id==='entry-model'?node:node.children.map(findModel).find(Boolean);
  findModel(nodes['own-fields']).value='Unsaved draft';
  nodes['nav-settings'].listeners.click({currentTarget:nodes['nav-settings'],preventDefault(){}});
  assert.equal(nodes['garage-view'].hidden,true); assert.equal(nodes['own-panel'].hidden,false); assert.equal(findModel(nodes['own-fields']).value,'Unsaved draft');
  assert.equal(draftWrites,0,'changing views does not submit an active form');
  nodes['nav-garage'].listeners.click({currentTarget:nodes['nav-garage'],preventDefault(){}});
  assert.equal(findModel(nodes['own-fields']).value,'Unsaved draft','returning to Garage preserves the unsaved form values');

  const legacyHuNodes=await run(async path=>({ok:true,json:async()=>path.endsWith('/summary')?{vehicle:{status:{readiness:'ready',issues:[],revision:1}},reminders:[],services:[]}:{vehicles:[{id:1,name:'Legacy',status:{readiness:'ready',issues:[],revision:1}}]}}),{standalone:true});
  assert.equal(legacyHuNodes['inspection-panel'].hidden,true);
  legacyHuNodes['vehicle-edit'].listeners.click();
  assert.equal(legacyHuNodes['own-fields'].querySelectorAll('input').some(input=>input.id==='entry-inspectionDueMonth'),false);

  // The optional month is submitted on vehicle create/update, and an explicit clear never changes manual readiness.
  const huWrites=[];
  let editableVehicle=huVehicle({dueMonth:'2026-08',inspection:huProjection({asOf:'2026-10-01',dueMonth:'2026-08',state:'blocking',monthsUntilDue:-2,batteryLevel:0,blocksReadiness:true,validUntil:'2026-08-31',blockingFrom:'2026-10-01'}),readiness:'not_ready',effectiveReadiness:'not_ready'});
  let nextVehicleId=2;
  const editableVehicles=[editableVehicle];
  nodes=await run(async (path,options={})=>{
    if(options.method){
      const body=JSON.parse(options.body); huWrites.push({path,method:options.method,body});
      if(options.method==='PUT'){
        editableVehicle={...editableVehicle,...body,revision:editableVehicle.revision+1};
        if(body.inspectionDueMonth===null){editableVehicle.inspection=huProjection();editableVehicle.effectiveReadiness=editableVehicle.status.readiness;}
        editableVehicles[0]=editableVehicle;
        return {ok:true,json:async()=>editableVehicle};
      }
      if(path==='/garage-api/vehicles'){
        const created=huVehicle({id:nextVehicleId++,name:body.make+' '+body.model,dueMonth:body.inspectionDueMonth,inspection:body.inspectionDueMonth?huProjection({dueMonth:body.inspectionDueMonth,state:'upcoming',monthsUntilDue:4,batteryLevel:4,validUntil:'2027-02-28',blockingFrom:'2027-04-01'}):huProjection(),readiness:'unknown',effectiveReadiness:'unknown'});
        Object.assign(created,body,{revision:1}); editableVehicles.push(created); return {ok:true,json:async()=>created};
      }
    }
    if(path.endsWith('/summary')){const id=Number(path.split('/')[3]);const vehicle=editableVehicles.find(item=>item.id===id);return {ok:true,json:async()=>({vehicle,reminders:[],services:[]})};}
    return {ok:true,json:async()=>({vehicles:editableVehicles})};
  },{standalone:true,inspectionStatus:true});
  const entryInput=id=>nodes['own-fields'].querySelectorAll('input').find(input=>input.id==='entry-'+id);
  nodes['vehicle-edit'].listeners.click();
  assert.equal(entryInput('inspectionDueMonth').value,'2026-08');
  const inspectionHelp=nodes['own-fields'].querySelectorAll('details');
  assert.equal(inspectionHelp.length,1,'the HU help is available as a native disclosure');
  assert.equal(inspectionHelp[0].querySelectorAll('summary')[0].attributes['aria-label'],'Information zum Ablesen des HU-Monats');
  assert.match(inspectionHelp[0].textContent,/hinteren Kennzeichen.*ganz oben.*zweistellige Zahl in der Mitte.*9 und Mitte 28 bedeutet September 2028.*letzten HU-Bericht/);
  const huSource=inspectionHelp[0].querySelectorAll('a')[0];
  assert.equal(huSource.href,'https://www.tuev-nord.de/de/dienstleistungen/pruefung-und-gutachten/hauptuntersuchung/');
  assert.equal(huSource.target,'_blank');
  assert.equal(huSource.rel,'noopener noreferrer');
  assert.equal(nodes['own-fields'].querySelectorAll('label').find(label=>label.textContent==='HU / TÜV gültig bis').attributes.for,entryInput('inspectionDueMonth').id,'the label remains directly associated with the month input');
  entryInput('model').value='Bearbeitet';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(huWrites[0].body.inspectionDueMonth,'2026-08','unmodified month is preserved on vehicle PUT');
  assert.equal(huWrites[0].body.revision,1);
  nodes['vehicle-edit'].listeners.click();
  entryInput('inspectionDueMonth').value='';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(huWrites[1].body.inspectionDueMonth,null,'blank month explicitly clears the date');
  assert.equal(editableVehicle.status.readiness,'not_ready','vehicle edits retain manual readiness');
  assert.equal(nodes['condition-readiness'].textContent,'Nicht fahrbereit');
  assert.match(nodes['inspection-message'].textContent,/nicht eingetragen/);
  nodes['vehicle-add'].listeners.click();
  const createdInput=id=>nodes['own-fields'].querySelectorAll('input').find(input=>input.id==='entry-'+id);
  createdInput('make').value='Neu'; createdInput('model').value='Fahrzeug';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(huWrites[2].body.inspectionDueMonth,null,'blank month is sent explicitly for vehicle create too');
  assert.equal(editableVehicles[1].status.readiness,'unknown');

  // A status save is followed by the existing summary read so the server remains authoritative for effective readiness.
  let summaryReads=0;
  const manualStatus={readiness:'ready',issues:[],revision:1};
  const beforeInspection=huProjection({dueMonth:'2026-12',state:'upcoming',monthsUntilDue:2,batteryLevel:2,validUntil:'2026-12-31',blockingFrom:'2027-02-01'});
  const afterInspection=huProjection({asOf:'2026-10-01',dueMonth:'2026-08',state:'blocking',monthsUntilDue:-2,batteryLevel:0,blocksReadiness:true,validUntil:'2026-08-31',blockingFrom:'2026-10-01'});
  const changingVehicle={...huVehicle({dueMonth:'2026-12',inspection:beforeInspection}),status:manualStatus};
  nodes=await run(async(path,options={})=>{
    if(options.method==='PUT') return {ok:true,json:async()=>manualStatus};
    if(path.endsWith('/summary')) { summaryReads++; return {ok:true,json:async()=>({vehicle:{...changingVehicle,inspection:summaryReads===1?beforeInspection:afterInspection,inspectionDueMonth:summaryReads===1?'2026-12':'2026-08',effectiveReadiness:summaryReads===1?'ready':'not_ready'},reminders:[],services:[]})}; }
    return {ok:true,json:async()=>({vehicles:[changingVehicle]})};
  },{standalone:true,inspectionStatus:true});
  assert.equal(summaryReads,1);
  nodes['condition-edit'].listeners.click();
  nodes['readiness-input'].value='ready';
  await nodes['condition-form'].listeners.submit({preventDefault(){}});
  assert.equal(summaryReads,2,'status write forces a fresh vehicle summary');
  assert.equal(nodes['condition-readiness'].textContent,'Nicht fahrbereit','new server projection can override manual ready');
  assert.equal(changingVehicle.status.readiness,'ready');
  assert.match(nodes['inspection-message'].textContent,/31\.08\.2026 · überfällig seit circa 2 Monaten · automatisch INOP ab 01\.10\.2026/);

  // On tab return, refresh the server month only when no entry form is being edited.
  const visibilityVehicle=huVehicle({dueMonth:'2026-12',inspection:beforeInspection});
  let vehicleReads=0;
  nodes=await run(async path=>{
    if(path==='/garage-api/vehicles'){vehicleReads++;return {ok:true,json:async()=>({vehicles:[visibilityVehicle]})};}
    if(path.endsWith('/history'))return {ok:true,json:async()=>({events:[]})};
    if(path.endsWith('/records/page'))return {ok:true,json:async()=>({records:[],nextCursor:null})};
    return {ok:true,json:async()=>({vehicle:visibilityVehicle,reminders:[],services:[]})};
  },{standalone:true,inspectionStatus:true,historyBrowsing:true});
  assert.equal(nodes.__inspectionInterval(),60000,'inspection refresh runs once per minute');
  await nodes['history-toggle'].listeners.click(); await nodes['logbook-toggle'].listeners.click();
  assert.equal(nodes['history-panel'].hidden,false); assert.equal(nodes['logbook-panel'].hidden,false);
  nodes['vehicle-edit'].listeners.click();
  const readsBeforeForm=vehicleReads;
  await nodes.__visibilityChanged('hidden'); await nodes.__visibilityChanged('visible');
  assert.equal(vehicleReads,readsBeforeForm,'visible refresh does not discard an active edit form');
  assert.equal(nodes['own-panel'].hidden,false);
  nodes['own-cancel'].listeners.click();
  visibilityVehicle.inspection=huProjection({asOf:'2026-10-29',dueMonth:'2026-12',state:'upcoming',monthsUntilDue:2,batteryLevel:2,validUntil:'2026-12-31',blockingFrom:'2027-02-01'});
  await nodes.__visibilityChanged('hidden'); await nodes.__visibilityChanged('visible');
  assert.equal(vehicleReads,readsBeforeForm+1);
  assert.match(nodes['inspection-message'].textContent,/31\.12\.2026 · fällig in circa 2 Monaten/);
  visibilityVehicle.inspection=huProjection({asOf:'2026-10-30',dueMonth:'2026-12',state:'upcoming',monthsUntilDue:2,batteryLevel:2,validUntil:'2026-12-31',blockingFrom:'2027-02-01'});
  await nodes.__inspectionTick();
  assert.equal(vehicleReads,readsBeforeForm+2);
  assert.match(nodes['inspection-message'].textContent,/31\.12\.2026 · fällig in circa 2 Monaten/);
  assert.equal(nodes['history-panel'].hidden,false,'periodic projection refresh preserves history visibility');
  assert.equal(nodes['logbook-panel'].hidden,false,'periodic projection refresh preserves logbook visibility');
  assert.equal(nodes.vehicles.children[0].attributes['aria-pressed'],'true','periodic projection refresh preserves selection');
  nodes['vehicle-edit'].listeners.click();
  const readsBeforePeriodicForm=vehicleReads;
  await nodes.__inspectionTick();
  assert.equal(vehicleReads,readsBeforePeriodicForm,'timer leaves the month input untouched while an edit form is open');
  assert.equal(nodes['own-panel'].hidden,false);

  // Standalone export stays a fixed browser download; capability data cannot alter its URL.
  let exportCalls=0;
  nodes = await run(async path => { if(path==='/garage-api/export') exportCalls++; return {ok:true,json:async()=>({vehicles:[]})}; }, {standalone:true,dataExport:true});
  assert.equal(nodes['data-export-wrap'].hidden,false);
  assert.equal(nodes['data-export'].href,'/garage-api/export');
  assert.equal(nodes['data-export'].download,'wolfs-garage-export.json');
  assert.equal(nodes['data-export'].textContent,'Portabler JSON-Export');
  assert.match(nodes['data-export-hint'].textContent,/dient nicht zur Wiederherstellung/);
  assert.equal(exportCalls,0,'normal anchor download avoids loading the complete export in app memory');
  const exportMarkup=fs.readFileSync(require('node:path').join(__dirname,'index.html'),'utf8');
  assert.match(exportMarkup,/<a id="data-export"[^>]*href="\/garage-api\/export"[^>]*download="wolfs-garage-export\.json"/);
  assert.match(exportMarkup,/Vollständige Sicherung herunterladen/);
  assert.match(exportMarkup,/restore-backup BACKUP\.sqlite3 NEUE_DATENBANK\.sqlite3/);
  assert.match(nodes['backup-restore-help'].textContent,/offline auf dem Server/);
  nodes = await run(async path => ({ok:true,json:async()=>({vehicles:[]})}), {standalone:true,dataExport:true,databaseBackup:true});
  assert.equal(nodes['database-backup'].hidden,false);
  assert.equal(nodes['database-backup-hint'].hidden,false);
  assert.match(nodes['database-backup-hint'].textContent,/alle Garage-Anwendungsdaten einschließlich Verlauf/);
  assert.match(nodes['database-backup-hint'].textContent,/Konfiguration und externe Dokumente sind nicht enthalten/);
  let backupFetches=0, finishBackup;
  const pendingBackup = new Promise(resolve=>{finishBackup=resolve;});
  nodes = await run(async path => {
    if(path==='/garage-api/backup') { backupFetches++; return pendingBackup; }
    return {ok:true,json:async()=>({vehicles:[]})};
  }, {standalone:true,databaseBackup:true});
  const backupRequest=nodes['database-backup'].listeners.click();
  assert.equal(nodes['database-backup'].disabled,true,'download button disables while the backup is being fetched');
  assert.equal(nodes['database-backup'].attributes['aria-busy'],'true');
  const duplicate=nodes['database-backup'].listeners.click(); await duplicate;
  assert.equal(backupFetches,1,'a second click cannot start a concurrent download');
  finishBackup({ok:true,status:200,blob:async()=>new Blob(['SQLite format 3\u0000synthetic backup'],{type:'application/vnd.sqlite3'})});
  await backupRequest;
  assert.equal(backupFetches,1);
  assert.match(nodes['__downloads'][0].download,/^wolfs-garage-backup-.*\.sqlite3$/);
  assert.equal(nodes['__downloads'][0].clicked,true);
  assert.equal(nodes['__objectUrls'].created.length,1);
  assert.equal(nodes['__objectUrls'].revoked.length,1);
  assert.match(nodes['database-backup-message'].textContent,/Sicherung erstellt\. Der Download wurde gestartet/);
  assert.equal(nodes['database-backup'].disabled,false);
  let backupAttempts=0;
  nodes = await run(async path => {
    if(path==='/garage-api/backup') { backupAttempts++; return {ok:false,status:503}; }
    return {ok:true,json:async()=>({vehicles:[]})};
  }, {standalone:true,databaseBackup:true});
  await nodes['database-backup'].listeners.click();
  assert.equal(backupAttempts,1);
  assert.match(nodes['database-backup-message'].textContent,/konnte nicht heruntergeladen werden/);
  assert.equal(nodes['__downloads'].length,0,'failed backup response never reports or triggers a download');
  assert.equal(nodes['database-backup'].disabled,false,'retry is available after failure');
  nodes = await run(async path => path==='/garage-api/backup' ? {ok:true,status:200,blob:async()=>new Blob(['not a database'],{type:'application/octet-stream'})} : {ok:true,json:async()=>({vehicles:[]})}, {standalone:true,databaseBackup:true});
  await nodes['database-backup'].listeners.click();
  assert.match(nodes['database-backup-message'].textContent,/konnte nicht heruntergeladen werden/);
  assert.equal(nodes['__downloads'].length,0,'a non-SQLite success response is not presented as a backup');
  nodes = await run(async () => ({ok:true,json:async()=>({vehicles:[]})}), {standalone:true,dataExport:true});
  assert.equal(nodes['data-export-wrap'].hidden,false);
  assert.equal(nodes['database-backup'].hidden,true,'older standalone capability sets hide the backup download');
  assert.equal(nodes['backup-restore-help'].hidden,true);
  nodes = await run(async () => ({ok:true,json:async()=>({vehicles:[]})}), {standalone:false,dataExport:true});
  assert.equal(nodes['data-export-wrap'].hidden,true,'legacy mode never shows the standalone export');

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
  assert.equal(nodes['condition-issues'].querySelectorAll('button').length,0,'legacy mode does not expose standalone issue actions');
  nodes['condition-edit'].listeners.click();
  assert.equal(nodes['condition-form'].hidden, false);
  assert.equal(nodes['issue-editor'].querySelectorAll('input')[0].value, 'Reifen wechseln');
  nodes['readiness-input'].value='not_ready';
  nodes['issue-add'].listeners.click();
  nodes['issue-editor'].querySelectorAll('input').filter(input=>input.type==='text')[1].value='Kontrolle';
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

  // Point actions edit the existing status form or atomically complete exactly one point with a record.
  const directIssues=[{id:'direct/a',text:'Bremsbeläge prüfen'},{id:'direct-b',text:'Licht kontrollieren'}];
  const directOriginalStatus={readiness:'not_ready',issues:directIssues,revision:6};
  let directStatus={...directOriginalStatus}; const directWrites=[]; const directRecords=[]; let directPostAttempts=0;
  const directVehicle={id:35,name:'Direktabschluss',make:'Test',model:'Auto',vehicleType:'Limousine',odometerUnit:'km',revision:1,status:directStatus};
  nodes=await run(async(path,options={})=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[directVehicle]})};
    if(path==='/garage-api/vehicles/35/summary') return {ok:true,json:async()=>({vehicle:{...directVehicle,status:directStatus},reminders:[],services:directRecords})};
    if(path==='/garage-api/vehicles/35/records' && options.method==='POST') {
      const payload=JSON.parse(options.body); directWrites.push(payload);
      if(++directPostAttempts===1) return {ok:false,status:409};
      directStatus={...directStatus,issues:directStatus.issues.filter(issue=>String(issue.id)!==String(payload.closeIssueId)),revision:directStatus.revision+1};
      const record={id:90,...payload,odometerUnit:'km'}; directRecords.push(record);
      return {ok:true,json:async()=>({record,status:directStatus})};
    }
    if(path==='/garage-api/vehicles/35/history') return {ok:true,json:async()=>({events:[{action:'issue.completed',occurredAt:'2026-10-29T12:00:00Z',before:{issues:directIssues},after:{record:directRecords[0],status:directStatus}}]})};
    throw new Error(`Unexpected direct-completion request: ${path}`);
  },{standalone:true});
  const issueRows=()=>nodes['condition-issues'].children.filter(child=>child.className==='condition-issue-row');
  const firstIssueRow=issueRows().find(row=>row.textContent.includes('Bremsbeläge prüfen'));
  const firstEdit=firstIssueRow.querySelectorAll('button').find(button=>button.id==='issue-edit-direct%2Fa');
  const firstDone=firstIssueRow.querySelectorAll('button').find(button=>button.id==='issue-complete-direct%2Fa');
  assert.ok(firstEdit); assert.ok(firstDone);
  assert.match(firstEdit.attributes['aria-label'],/Bremsbeläge prüfen/); assert.match(firstDone.attributes['aria-label'],/Bremsbeläge prüfen/);
  assert.equal(directWrites.length,0,'opening either action makes no API write');
  await firstEdit.listeners.click();
  const focusedIssueField=nodes['issue-editor'].querySelectorAll('input')[0];
  assert.equal(focusedIssueField.id,'issue-edit-direct%2Fa-text'); assert.equal(focusedIssueField.focused,true);
  assert.equal(focusedIssueField.parent.children.find(child=>child.tagName==='label').attributes.for,focusedIssueField.id,'the stable editor ID remains connected to its label');
  assert.equal(nodes['condition-form'].hidden,false);
  await nodes['condition-cancel'].listeners.click();
  assert.equal(firstEdit.focused,true,'cancel returns focus to the issue edit button');
  assert.equal(directWrites.length,0);

  const secondDone=issueRows().find(row=>row.textContent.includes('Licht kontrollieren')).querySelectorAll('button').find(button=>button.id==='issue-complete-direct-b');
  await secondDone.listeners.click();
  const directField=name=>nodes['own-fields'].querySelectorAll('input').concat(nodes['own-fields'].querySelectorAll('select')).find(field=>field.id==='entry-'+name);
  assert.equal(nodes['own-title'].textContent,'Punkt abschließen');
  assert.equal(nodes['own-save'].textContent,'Arbeit speichern & Punkt abschließen');
  assert.equal(directField('description').value,'Licht kontrollieren');
  assert.equal(directField('kind').value,''); assert.equal(directField('kind').required,true);
  assert.equal(directField('closeIssueId').type,'hidden'); assert.equal(directField('closeIssueId').value,'direct-b');
  assert.notEqual(directField('date').value,''); assert.equal(directField('odometer').required,false);
  assert.match(nodes['own-hint'].textContent,/Entwurf.*tatsächlich durchgeführte Arbeit/);
  firstDone.listeners.click();
  assert.equal(directField('closeIssueId').value,'direct-b','a second issue action cannot replace an open form');
  await nodes['own-cancel'].listeners.click();
  assert.equal(secondDone.focused,true,'cancel returns focus to the selected issue action');
  assert.equal(directWrites.length,0,'cancel makes no write');

  await firstDone.listeners.click();
  directField('description').value='Bremsbeläge erneuert';
  directField('cost').value='35,50'; directField('currency').value='eur';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(directWrites.length,0,'direct completion requires a deliberate work kind');
  assert.match(nodes['own-message'].textContent,/Arbeitsart aus/);
  directField('kind').value='service';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(directWrites.length,1);
  const firstDirectWrite=directWrites[0];
  assert.equal(firstDirectWrite.closeIssueId,'direct/a'); assert.equal(firstDirectWrite.statusRevision,6);
  assert.equal(firstDirectWrite.description,'Bremsbeläge erneuert'); assert.equal(firstDirectWrite.kind,'service');
  assert.equal(firstDirectWrite.cost,'35.50'); assert.equal(firstDirectWrite.currency,'EUR');
  assert.equal(typeof firstDirectWrite.commandId,'string');
  assert.match(nodes['own-message'].textContent,/inzwischen geändert/);
  assert.equal(nodes['own-panel'].hidden,false,'a conflict leaves the draft available for retry');
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(directWrites.length,2);
  assert.equal(directWrites[1].commandId,firstDirectWrite.commandId,'retry preserves its idempotency key');
  assert.equal(directWrites[1].closeIssueId,'direct/a','retry retains the originally selected point');
  assert.deepEqual(directStatus.issues.map(issue=>issue.id),['direct-b']);
  assert.equal(directStatus.readiness,'not_ready','closing work leaves manual readiness unchanged');
  assert.match(nodes['own-notice'].textContent,/Arbeit gespeichert und Punkt abgeschlossen/);
  assert.equal(nodes['history-panel'].hidden,false,'success exposes the audit history');
  assert.equal(nodes['history-toggle'].focused,true,'success moves focus to the visible history control');
  assert.match(nodes['history-events'].textContent,/Offenen Punkt abgeschlossen/);
  assert.equal(nodes['condition-issues'].textContent.includes('Licht kontrollieren'),true);
  assert.equal(nodes['condition-issues'].textContent.includes('Bremsbeläge prüfen'),false);

  // The optional full logbook keeps filters across pages and leaves the separate audit panel intact.
  const pageCalls=[]; let moreFailures=0; let reloads=0;
  nodes=await run(async path=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[{id:3,name:'Logbuch-Test',status:{readiness:'ready',issues:[],revision:0}}]})};
    if(path==='/garage-api/vehicles/3/summary') return {ok:true,json:async()=>({vehicle:{status:{readiness:'ready',issues:[],revision:0}},reminders:[],services:[{id:4,date:'2026-10-20',description:'Kurzbeleg',kind:'service'}]})};
    if(/^\/garage-api\/vehicles\/3\/records\/[46]$/.test(path)) { const id=Number(path.split('/').pop()); return {ok:true,json:async()=>({id,description:'Ölwechsel',kind:'service',date:'2026-10-20',odometer:12000,odometerUnit:'km',revision:1})}; }
    if(path.includes('/records/page?')) {
      pageCalls.push(path);
      if(path.includes('cursor=c1') && moreFailures++===0) return {ok:false,status:502};
      if(path.includes('cursor=c1')) return {ok:true,json:async()=>({records:[{id:5,date:'2026-09-10',description:'<img src=x onerror=alert(1)>',kind:'repair',odometer:0,odometerUnit:'km',cost:null,currency:null,note:'Record 5'}],nextCursor:'c2'})};
      if(path.includes('cursor=c2')) return {ok:false,status:409};
      return path.includes('kind=repair') ? {ok:true,json:async()=>({records:[{id:6,date:'2026-10-15',description:'Bremsen',kind:'repair'}],nextCursor:null})} : {ok:true,json:async()=>({records:[{id:4,date:'2026-10-20',description:'Ölwechsel',kind:'service',odometer:12000,odometerUnit:'km',cost:'20.00',currency:'EUR'}],nextCursor:'c1'})};
    }
    if(path.includes('/odometer/page?')) { pageCalls.push(path); return {ok:true,json:async()=>({readings:[{id:8,date:'2026-10-01',odometer:15000,unit:'km',note:'Record 4'}],nextCursor:null})}; }
    throw new Error('Unexpected logbook request: '+path);
  },{standalone:true,recordCorrections:true,historyBrowsing:true});
  assert.equal(nodes['logbook-toggle'].hidden,false);
  nodes['logbook-toggle'].listeners.click();
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(nodes['logbook-panel'].hidden,false);
  assert.match(pageCalls[0],/\/records\/page\?limit=25/);
  assert.equal(nodes['logbook-records'].querySelectorAll('button').find(button=>button.id==='log-record-edit-4').tagName,'button');
  assert.ok(nodes.services.querySelectorAll('button').find(button=>button.id==='record-edit-4'));
  nodes['logbook-more'].listeners.click(); await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(nodes['logbook-records'].children.length,1);
  assert.match(nodes['logbook-message'].textContent,/konnten nicht geladen werden/);
  assert.equal(nodes['logbook-more'].hidden,false);
  nodes['logbook-more'].listeners.click(); await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(nodes['logbook-records'].children.length,2);
  assert.match(nodes['logbook-records'].textContent,/<img src=x onerror=alert\(1\)>/);
  assert.equal(nodes['logbook-records'].querySelectorAll('img').length,0);
  assert.match(pageCalls[2],/cursor=c1/);
  nodes['logbook-more'].listeners.click(); await new Promise(resolve=>setTimeout(resolve,0));
  assert.match(nodes['logbook-message'].textContent,/seit der letzten Seite geändert/);
  assert.equal(nodes['logbook-more'].hidden,true); assert.equal(nodes['logbook-reload'].hidden,false);
  assert.equal(nodes['logbook-records'].children.length,2);
  nodes['logbook-reload'].listeners.click(); await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(nodes['logbook-records'].children.length,1);
  nodes['logbook-type'].value='records'; nodes['logbook-kind'].value='repair'; nodes['logbook-from'].value='2026-01-01'; nodes['logbook-to'].value='2026-12-31';
  await nodes['logbook-filters'].listeners.submit({preventDefault(){}});
  assert.match(pageCalls.at(-1),/\/records\/page\?limit=25&from=2026-01-01&to=2026-12-31&kind=repair/);
  const oldLogEdit=nodes['logbook-records'].querySelectorAll('button').find(button=>button.id==='log-record-edit-4');
  assert.equal(oldLogEdit,undefined);
  const correctionFromLog=nodes['logbook-records'].querySelectorAll('button').find(button=>button.id==='log-record-edit-6');
  await correctionFromLog.listeners.click();
  assert.equal(nodes['own-panel'].hidden,false);
  nodes['own-cancel'].listeners.click();
  assert.equal(nodes['own-panel'].hidden,true);
  nodes['logbook-type'].value='odometer'; nodes['logbook-type'].listeners.change();
  assert.equal(nodes['logbook-kind-field'].hidden,true);
  nodes['logbook-from'].value='2026-01-01'; nodes['logbook-to'].value='2026-12-31';
  await nodes['logbook-filters'].listeners.submit({preventDefault(){}});
  assert.match(pageCalls.at(-1),/\/odometer\/page\?limit=25&from=2026-01-01&to=2026-12-31/);
  assert.match(nodes['logbook-records'].textContent,/Record 4/);
  nodes['logbook-close'].listeners.click(); assert.equal(nodes['logbook-panel'].hidden,true);
  nodes=await run(async path=>path==='/garage-api/vehicles' ? {ok:true,json:async()=>({vehicles:[{id:1,name:'Legacy',status:{readiness:'unknown',issues:[],revision:0}}]})} : {ok:true,json:async()=>path.endsWith('/summary')?{vehicle:{status:{readiness:'unknown',issues:[],revision:0}},reminders:[],services:[]}:{vehicles:[]}});
  assert.equal(nodes['logbook-toggle'].hidden,true);

  // A response from a closed logbook cannot overwrite a newer reopen request.
  let releaseStale; let startedStale; const staleStarted=new Promise(resolve=>{startedStale=resolve;}); let racePage=0;
  nodes=await run(async path=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[{id:1,name:'Race-Test',status:{readiness:'ready',issues:[],revision:0}}]})};
    if(path.endsWith('/summary')) return {ok:true,json:async()=>({vehicle:{status:{readiness:'ready',issues:[],revision:0}},reminders:[],services:[]})};
    if(path.includes('/records/page?') && racePage++===0) return new Promise(resolve=>{releaseStale=resolve; startedStale();});
    if(path.includes('/records/page?')) return {ok:true,json:async()=>({records:[{id:2,date:'2026-10-27',description:'Neues Ergebnis',kind:'service'}],nextCursor:null})};
    throw new Error('Unexpected race request: '+path);
  },{standalone:true,historyBrowsing:true});
  nodes['logbook-toggle'].listeners.click(); await staleStarted;
  nodes['logbook-close'].listeners.click(); nodes['logbook-toggle'].listeners.click(); await new Promise(resolve=>setTimeout(resolve,0));
  assert.match(nodes['logbook-records'].textContent,/Neues Ergebnis/);
  releaseStale({ok:true,json:async()=>({records:[{id:1,date:'2026-10-26',description:'Veraltetes Ergebnis',kind:'repair'}],nextCursor:null})});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.match(nodes['logbook-records'].textContent,/Neues Ergebnis/);
  assert.doesNotMatch(nodes['logbook-records'].textContent,/Veraltetes Ergebnis/);

  // Structured issue metadata is saved explicitly, while readiness remains independent.
  const originalIssues=[
    {id:'issue-1',text:'<img src=x onerror=alert(1)>',dueDate:'2026-10-27',severity:'critical',lifecycle:'open'},
    {id:'issue-2',text:'Beobachten',dueDate:null,severity:null,lifecycle:'observed'}
  ];
  let currentIssues=originalIssues; let structuredPayload; let workReads=0; let currentRevision=1;
  const otherIssue={id:'issue-3',text:'Ein einzelner offener Punkt',dueDate:null,severity:'repair',lifecycle:'open'};
  nodes=await run(async(path,options={})=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[{id:20,name:'Bereit trotz kritisch',status:{readiness:'ready',issues:currentIssues,revision:currentRevision}},{id:21,name:'Ein Punkt',status:{readiness:'ready',issues:[otherIssue],revision:1}}]})};
    if(path==='/garage-api/vehicles/20/summary') return {ok:true,json:async()=>({vehicle:{status:{readiness:'ready',issues:currentIssues,revision:currentRevision}},reminders:[],services:[]})};
    if(path==='/garage-api/vehicles/21/summary') return {ok:true,json:async()=>({vehicle:{status:{readiness:'ready',issues:[otherIssue],revision:1}},reminders:[],services:[]})};
    if(path==='/garage-api/work') { workReads++; return {ok:true,json:async()=>({today:'2026-10-28',timeZone:'Europe/Berlin',items:[...currentIssues.map((issue,index)=>({vehicleId:20,id:issue.id,text:issue.text,dueDate:issue.dueDate,severity:issue.severity,lifecycle:issue.lifecycle,dueState:index===0?'overdue':'unscheduled'})),{vehicleId:21,...otherIssue,dueState:'unscheduled'}]})}; }
    if(path==='/garage-api/vehicles/20/status' && options.method==='PUT') { structuredPayload=JSON.parse(options.body); currentIssues=structuredPayload.issues.map((issue,index)=>({...issue,id:issue.id||`new-${index}`})); currentRevision=2; return {ok:true,json:async()=>({readiness:structuredPayload.readiness,issues:currentIssues,revision:currentRevision})}; }
    if(path==='/garage-api/vehicles/20/records' && options.method==='POST') { const payload=JSON.parse(options.body); currentIssues=currentIssues.filter(issue=>issue.id!==payload.closeIssueId); currentRevision=3; return {ok:true,json:async()=>({record:{id:99,...payload},status:{readiness:'ready',issues:currentIssues,revision:currentRevision}})}; }
    if(path==='/garage-api/vehicles/20/history') return {ok:true,json:async()=>({events:[{action:'status.updated',occurredAt:'2026-10-28T12:00:00Z',before:{issues:originalIssues},after:{issues:currentIssues}}]})};
    throw new Error('Unexpected scheduled work request: '+path);
  },{standalone:true,scheduledWork:true});
  assert.equal(nodes['work-dashboard'].hidden,false); assert.equal(workReads,1);
  assert.match(nodes['work-status'].textContent,/Stand: 28\.10\.2026 \(Europe\/Berlin\)/);
  assert.match(nodes['condition-work-asof'].textContent,/Fälligkeitsstand: 28\.10\.2026/);
  assert.match(nodes.vehicles.children[0].attributes['aria-label'],/Kritisch/);
  assert.doesNotMatch(nodes.vehicles.children[0].attributes['aria-label'],/Nicht fahrbereit/);
  assert.match(nodes['work-items'].textContent,/<img src=x onerror=alert\(1\)>/);
  assert.equal(nodes['work-items'].querySelectorAll('img').length,0);
  assert.match(nodes['condition-issues'].textContent,/Auffälligkeit|Kritisch/);
  nodes['issue-filter'].value='overdue'; nodes['issue-filter'].listeners.change();
  assert.match(nodes['condition-issues'].textContent,/<img src=x onerror=alert\(1\)>/);
  assert.doesNotMatch(nodes['condition-issues'].textContent,/Beobachten/);
  nodes['issue-filter'].value='observed'; nodes['issue-filter'].listeners.change();
  assert.match(nodes['condition-issues'].textContent,/Beobachten/);
  const secondVehicle=nodes.vehicles.children.find(card=>card.attributes['aria-label'].includes('Ein Punkt'));
  await secondVehicle.listeners.click();
  assert.equal(nodes['issue-filter'].value,'all'); assert.equal(nodes['issue-filter-wrap'].hidden,true);
  assert.match(nodes['condition-issues'].textContent,/Ein einzelner offener Punkt/);
  assert.equal(workReads,2);
  await nodes.vehicles.children.find(card=>card.attributes['aria-label'].includes('Bereit trotz kritisch')).listeners.click();
  assert.equal(nodes['issue-filter'].value,'all');
  nodes['condition-edit'].listeners.click();
  nodes['issue-add'].listeners.click();
  const newIssue=nodes['issue-editor'].children[2];
  assert.equal(newIssue.querySelectorAll('input')[1].value,''); assert.equal(newIssue.querySelectorAll('select')[0].value,''); assert.equal(newIssue.querySelectorAll('select')[1].value,'open');
  assert.equal(newIssue.querySelectorAll('button')[0].textContent,'Punkt entfernen'); newIssue.querySelectorAll('button')[0].listeners.click();
  const firstIssue=nodes['issue-editor'].children[0];
  assert.equal(firstIssue.querySelectorAll('input')[1].value,'2026-10-27');
  assert.equal(firstIssue.querySelectorAll('select')[0].value,'critical');
  firstIssue.querySelectorAll('input')[1].value=''; firstIssue.querySelectorAll('select')[0].value=''; firstIssue.querySelectorAll('select')[1].value='observed';
  await nodes['condition-form'].listeners.submit({preventDefault(){}});
  assert.equal(structuredPayload.readiness,'ready');
  assert.deepEqual(structuredPayload.issues[0],{text:'<img src=x onerror=alert(1)>',id:'issue-1',dueDate:null,severity:null,lifecycle:'observed'});
  assert.equal(structuredPayload.issues[1].dueDate,null); assert.equal(structuredPayload.issues[1].severity,null); assert.equal(structuredPayload.issues[1].lifecycle,'observed');
  assert.equal(workReads,4);
  assert.match(nodes.vehicles.children[0].attributes['aria-label'],/Fahrbereit/);
  assert.doesNotMatch(nodes.vehicles.children[0].attributes['aria-label'],/INOP|Nicht fahrbereit/);
  await nodes['history-toggle'].listeners.click();
  assert.match(nodes['history-events'].textContent,/Keine Fälligkeit/);
  assert.match(nodes['history-events'].textContent,/Schweregrad Nicht eingestuft/);
  assert.match(nodes['history-events'].textContent,/Status Beobachten/);
  nodes['record-add'].listeners.click();
  const entryField=id=>nodes['own-fields'].querySelectorAll('input').concat(nodes['own-fields'].querySelectorAll('select')).find(field=>field.id==='entry-'+id);
  entryField('description').value='Arbeit erledigt'; entryField('kind').value='repair'; entryField('closeIssueId').value='issue-1';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(workReads,5);
  assert.doesNotMatch(nodes['work-items'].textContent,/<img src=x onerror=alert\(1\)>/);
  assert.match(nodes['work-items'].textContent,/Ein einzelner offener Punkt/);

  // Failed and stale projection reads never replace manual issues with a false empty state.
  let releaseOldWork; let staleWorkStarted; const staleWorkPromise=new Promise(resolve=>{staleWorkStarted=resolve;}); let workCall=0; let failNextWork=false;
  nodes=await run(async(path)=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[{id:21,name:'Projektion',status:{readiness:'ready',issues:[{id:'w1',text:'Manuell erfasst',dueDate:'2026-10-28',severity:null,lifecycle:'open'}],revision:1}}]})};
    if(path==='/garage-api/vehicles/21/summary') return {ok:true,json:async()=>({vehicle:{status:{readiness:'ready',issues:[{id:'w1',text:'Manuell erfasst',dueDate:'2026-10-28',severity:null,lifecycle:'open'}],revision:1}},reminders:[],services:[]})};
    if(path==='/garage-api/work' && workCall++===0) return new Promise(resolve=>{releaseOldWork=resolve;staleWorkStarted();});
    if(path==='/garage-api/work' && failNextWork) { failNextWork=false; return {ok:false,status:503}; }
    if(path==='/garage-api/work') return {ok:true,json:async()=>({today:'2026-10-29',timeZone:'Europe/Berlin',items:[{vehicleId:21,id:'w1',text:'Manuell erfasst',dueDate:'2026-10-28',severity:null,lifecycle:'open',dueState:'overdue'}]})};
    throw new Error('Unexpected projection race request: '+path);
  },{standalone:true,scheduledWork:true});
  await staleWorkPromise;
  assert.match(nodes['condition-issues'].textContent,/Manuell erfasst/);
  nodes['issue-filter'].value='overdue'; nodes['issue-filter'].listeners.change();
  assert.match(nodes['work-status'].textContent,/Fälligkeiten werden geladen/);
  assert.doesNotMatch(nodes['work-status'].textContent,/Keine offenen Punkte/);
  assert.match(nodes['condition-issues'].textContent,/Fälligkeitsstatus wird geladen/);
  nodes.refresh.listeners.click(); await new Promise(resolve=>setTimeout(resolve,30));
  assert.match(nodes['work-status'].textContent,/Stand: 29\.10\.2026/);
  assert.match(nodes['work-items'].textContent,/Überfällig/);
  releaseOldWork({ok:true,json:async()=>({today:'2026-10-28',timeZone:'Europe/Berlin',items:[{vehicleId:21,id:'w1',text:'Manuell erfasst',dueDate:'2026-10-28',severity:null,lifecycle:'open',dueState:'today'}]})});
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.match(nodes['work-status'].textContent,/Stand: 29\.10\.2026/);
  assert.match(nodes['work-items'].textContent,/Überfällig/);
  failNextWork=true; nodes.refresh.listeners.click(); await new Promise(resolve=>setTimeout(resolve,30));
  assert.match(nodes['work-status'].textContent,/Fälligkeiten momentan nicht verfügbar/);
  nodes['issue-filter'].value='overdue'; nodes['issue-filter'].listeners.change();
  assert.match(nodes['condition-issues'].textContent,/Manuell erfasst/);
  assert.match(nodes['condition-issues'].textContent,/Fälligkeitsstatus momentan nicht verfügbar/);
  assert.doesNotMatch(nodes['work-status'].textContent,/Keine offenen Punkte/);
  nodes.refresh.listeners.click(); await new Promise(resolve=>setTimeout(resolve,30));
  assert.match(nodes['work-status'].textContent,/Stand: 29\.10\.2026/);

  // Linked record measurement corrections use exact decimal strings, retain revisions and commandId on conflict, and expose audit facts.
  const linkedVehicle={id:60,name:'Messkorrektur',revision:2,status:{readiness:'ready',issues:[],revision:1}};
  const currentBefore={id:12,date:'2026-03-01',odometer:1234.5,odometerExact:'1234.500',unit:'km',note:'',revision:7,provenance:'record',sourceRecordId:10};
  const currentAfter={...currentBefore,date:'2026-03-02',odometer:1235.125,odometerExact:'1235.125',revision:8};
  let measurementAttempt=0; const measurementWrites=[];
  nodes=await run(async(path,options={})=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[linkedVehicle]})};
    if(path==='/garage-api/vehicles/60/summary') return {ok:true,json:async()=>({vehicle:{status:linkedVehicle.status},reminders:[],services:[{id:10,date:'2026-03-01',description:'Ölwechsel',kind:'service',odometer:1234.5,odometerUnit:'km'}]})};
    if(path==='/garage-api/vehicles/60/records/10/measurement' && !options.method) return {ok:true,json:async()=>({record:{id:10,revision:4,description:'Ölwechsel',kind:'service',date:'2026-03-01',odometer:1234.5,odometerUnit:'km',closedIssueId:null},odometerExact:'1234.500',sourceReading:currentBefore,correctionMode:'linked',currentReading:currentBefore})};
    if(options.method==='PUT' && path==='/garage-api/vehicles/60/records/10/measurement') {measurementWrites.push(JSON.parse(options.body));if(++measurementAttempt===1)return {ok:false,status:409};if(measurementAttempt===2)throw new TypeError('temporary network interruption');return {ok:true,json:async()=>({record:{id:10,revision:5,date:'2026-03-02',odometer:1235.125,odometerUnit:'km',closedIssueId:null},reading:currentAfter,currentReadingBefore:currentBefore,currentReadingAfter:currentAfter})};}
    if(path==='/garage-api/vehicles/60/history') return {ok:true,json:async()=>({events:[{action:'record.measurement-corrected',occurredAt:'2026-03-02T12:00:00Z',before:{record:{id:10,date:'2026-03-01',odometer:1234.5,odometerExact:'1234.500',odometerUnit:'km'},odometerReading:currentBefore},after:{record:{id:10,date:'2026-03-02',odometer:1235.125,odometerExact:'1235.125',odometerUnit:'km'},odometerReading:currentAfter,correctionReason:'Beleg geprüft'}}]})};
    throw Error('Unexpected measurement correction request: '+path);
  },{standalone:true,measurementCorrections:true});
  const linkedAction=nodes.services.querySelectorAll('button').find(button=>button.id==='record-measurement-edit-10'); assert.ok(linkedAction);
  await linkedAction.listeners.click();
  const measurementField=name=>nodes['own-fields'].querySelectorAll('input').concat(nodes['own-fields'].querySelectorAll('select')).find(field=>field.id==='entry-'+name);
  assert.equal(nodes['own-title'].textContent,'Datum / Stand korrigieren'); assert.equal(measurementField('measurement-date').value,'2026-03-01');
  assert.equal(measurementField('measurement-odometer').value,'1234.500'); assert.match(nodes['measurement-projection-warning'].textContent,/neueste Datum.*zuletzt angelegte Stand/);
  measurementField('measurement-date').value='2026-03-02'; measurementField('measurement-odometer').value='1235,125';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(measurementWrites.length,0,'a correction without a reason never writes'); assert.match(nodes['own-message'].textContent,/Korrekturgrund/);
  measurementField('measurement-reason').value='Beleg geprüft';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.match(nodes['own-message'].textContent,/Entwurf, Revisionen und Wiederholungskennung bleiben erhalten/); assert.equal(nodes['own-panel'].hidden,false);
  const linkedPayload=measurementWrites[0]; assert.equal(linkedPayload.revision,4); assert.equal(linkedPayload.readingRevision,7); assert.equal(linkedPayload.date,'2026-03-02');
  assert.equal(linkedPayload.odometer,'1235.125'); assert.equal(typeof linkedPayload.odometer,'string'); assert.match(linkedPayload.commandId,/^[0-9a-f-]{36}$/);
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.match(nodes['own-message'].textContent,/Antwort konnte nicht empfangen/);
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(measurementWrites[1].commandId,linkedPayload.commandId,'measurement retry after a network failure keeps the same commandId');
  assert.equal(measurementWrites[2].commandId,linkedPayload.commandId,'measurement retry after a stale revision keeps the same commandId');
  assert.equal(measurementWrites[2].revision,linkedPayload.revision); assert.equal(measurementWrites[2].readingRevision,linkedPayload.readingRevision);
  assert.match(nodes['own-notice'].textContent,/Der aktuelle Fahrzeugstand hat sich geändert/);
  assert.match(nodes['history-events'].textContent,/Datum oder Stand korrigiert/); assert.match(nodes['history-events'].textContent,/1235\.125 km/); assert.match(nodes['history-events'].textContent,/Beleg geprüft/);
  assert.equal(nodes.services.querySelectorAll('button').find(button=>button.id==='record-measurement-edit-10').focused,true,'success returns focus to the action after reloading the service list');

  // Date-only records have no stand field and cannot create, remove or alter a reading.
  const dateVehicle={id:61,name:'Nur Datum',revision:1,status:{readiness:'ready',issues:[],revision:0}}; let dateOnlyWrite;
  nodes=await run(async(path,options={})=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[dateVehicle]})};
    if(path==='/garage-api/vehicles/61/summary') return {ok:true,json:async()=>({vehicle:{status:dateVehicle.status},reminders:[],services:[{id:11,date:'2026-01-10',description:'Prüfung ohne Stand',kind:'service',odometer:null,odometerUnit:'km'}]})};
    if(path==='/garage-api/vehicles/61/records/11/measurement' && !options.method) return {ok:true,json:async()=>({record:{id:11,revision:2,date:'2026-01-10',odometer:null,odometerUnit:'km',closedIssueId:null},odometerExact:null,sourceReading:null,correctionMode:'date_only',currentReading:null})};
    if(options.method==='PUT') {dateOnlyWrite=JSON.parse(options.body);return {ok:true,json:async()=>({record:{id:11,revision:3,date:dateOnlyWrite.date,odometer:null},reading:null,currentReadingBefore:null,currentReadingAfter:null})};}
    if(path==='/garage-api/vehicles/61/history') return {ok:true,json:async()=>({events:[]})};
    throw Error('Unexpected date-only request: '+path);
  },{standalone:true,measurementCorrections:true});
  await nodes.services.querySelectorAll('button').find(button=>button.id==='record-measurement-edit-11').listeners.click();
  assert.equal(measurementField('measurement-odometer'),undefined); assert.match(nodes['own-hint'].textContent,/nur das Datum ändern/);
  measurementField('measurement-date').value='2026-01-11'; measurementField('measurement-reason').value='Datum auf Rechnung geprüft';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(dateOnlyWrite.date,'2026-01-11'); assert.equal(dateOnlyWrite.odometer,null); assert.equal(dateOnlyWrite.readingRevision,null); assert.equal(typeof dateOnlyWrite.commandId,'string');

  // Legacy record provenance is resolved only through date/value/unit-matched unknown readings and explicit confirmation.
  const legacyRecordVehicle={id:62,name:'Altdaten-Beleg',revision:1,status:{readiness:'ready',issues:[],revision:0}}; let linkedResolution=false, candidateWrites=[]; let candidatePageCalls=[]; let measurementGets=0;
  nodes=await run(async(path,options={})=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[legacyRecordVehicle]})};
    if(path==='/garage-api/vehicles/62/summary') return {ok:true,json:async()=>({vehicle:{status:legacyRecordVehicle.status},reminders:[],services:[{id:40,date:'2026-04-04',description:'Historischer Service',kind:'service',odometer:1000,odometerUnit:'km'}]})};
    if(path==='/garage-api/vehicles/62/records/40/measurement') {measurementGets++;return {ok:true,json:async()=>linkedResolution?{record:{id:40,revision:6,date:'2026-04-04',odometer:1000,odometerUnit:'km',closedIssueId:null},odometerExact:'1000.000',sourceReading:{id:700,date:'2026-04-04',odometer:1000,odometerExact:'1000.000',unit:'km',note:'Record 40',revision:3,provenance:'record',sourceRecordId:40},correctionMode:'linked',currentReading:null}:{record:{id:40,revision:5,date:'2026-04-04',odometer:1000,odometerUnit:'km',closedIssueId:null},odometerExact:'1000.000',sourceReading:null,correctionMode:'legacy_unresolved',currentReading:null}};}
    if(path.includes('/odometer/page?')) {candidatePageCalls.push(path);return path.includes('cursor=next')?{ok:true,json:async()=>({readings:[{id:700,date:'2026-04-04',odometer:1000,odometerExact:'1000.000',unit:'km',note:'Record 40 <img src=x onerror=alert(1)>',revision:3,provenance:'legacy_unknown',sourceRecordId:null},{id:701,date:'2026-04-04',odometer:1000,odometerExact:'1000.000',unit:'mi',note:'falsche Einheit',revision:1,provenance:'legacy_unknown',sourceRecordId:null},{id:702,date:'2026-04-04',odometer:1000,odometerExact:'1000.000',unit:'km',note:'bereits verknüpft',revision:1,provenance:'record',sourceRecordId:3}],nextCursor:null})}:{ok:true,json:async()=>({readings:[{id:699,date:'2026-04-04',odometer:1000,odometerExact:'1000.001',unit:'km',revision:1,provenance:'legacy_unknown',sourceRecordId:null}],nextCursor:'next'})};}
    if(options.method==='PUT' && path.endsWith('/provenance')) {candidateWrites.push(JSON.parse(options.body));if(candidateWrites.length===1)return {ok:false,status:409};linkedResolution=true;return {ok:true,json:async()=>({reading:{id:700,revision:4,provenance:'record',sourceRecordId:40},record:{id:40,revision:6}})};}
    if(path==='/garage-api/vehicles/62/history') return {ok:true,json:async()=>({events:[{action:'odometer.provenance-confirmed',occurredAt:'2026-04-04T12:00:00Z',before:{odometerReading:{id:700,date:'2026-04-04',odometerExact:'1000.000',unit:'km',provenance:'legacy_unknown'}},after:{odometerReading:{id:700,date:'2026-04-04',odometerExact:'1000.000',unit:'km',provenance:'record',sourceRecordId:40},correctionReason:'Rechnung abgeglichen'}}]})};
    throw Error('Unexpected provenance resolution request: '+path);
  },{standalone:true,historyBrowsing:true,measurementCorrections:true});
  await nodes.services.querySelectorAll('button').find(button=>button.id==='record-measurement-edit-40').listeners.click();
  assert.equal(candidatePageCalls.length,2); assert.match(candidatePageCalls[0],/from=2026-04-04&to=2026-04-04/); assert.match(candidatePageCalls[1],/cursor=next/);
  const candidateSelect=nodes['own-fields'].querySelectorAll('select').find(field=>field.id==='entry-candidateReadingId');
  assert.ok(candidateSelect); assert.equal(candidateSelect.children.length,2,'only one exact same-day/unit legacy candidate is shown'); assert.equal(candidateSelect.value,'','no legacy match is preselected');
  assert.match(nodes['own-hint'].textContent,/nichts automatisch ausgewählt/); assert.match(nodes['own-fields'].textContent,/Record 40 <img src=x onerror=alert\(1\)>/,'API note is shown as literal text, not HTML');
  candidateSelect.value='700';
  measurementField('measurement-reason').value='Rechnung abgeglichen';
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.match(nodes['own-message'].textContent,/bestätige die Herkunft ausdrücklich/); assert.equal(candidateWrites.length,0);
  nodes['own-fields'].querySelectorAll('input').find(field=>field.id==='entry-provenanceConfirm').checked=true;
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.match(nodes['own-message'].textContent,/Messung oder Verknüpfung wurde inzwischen geändert/);
  const provenancePayload=candidateWrites[0]; assert.equal(provenancePayload.revision,3); assert.equal(provenancePayload.provenance,'record'); assert.equal(provenancePayload.sourceRecordId,40); assert.equal(provenancePayload.recordRevision,5); assert.match(provenancePayload.commandId,/^[0-9a-f-]{36}$/);
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(candidateWrites[1].commandId,provenancePayload.commandId); assert.equal(candidateWrites[1].revision,3); assert.equal(candidateWrites[1].recordRevision,5);
  assert.equal(measurementGets,2,'after explicit link, the record measurement form reloads verified linked facts');
  assert.equal(nodes['own-title'].textContent,'Datum / Stand korrigieren'); assert.equal(measurementField('measurement-odometer').value,'1000.000');

  // Legacy reading provenance can be declared independent only by explicit owner confirmation and never auto-links.
  const legacyReadingVehicle={id:63,name:'Altdaten-Stand',revision:1,status:{readiness:'ready',issues:[],revision:0}}; let provenanceManualWrites=[];
  nodes=await run(async(path,options={})=>{
    if(path==='/garage-api/vehicles') return {ok:true,json:async()=>({vehicles:[legacyReadingVehicle]})};
    if(path==='/garage-api/vehicles/63/summary') return {ok:true,json:async()=>({vehicle:{status:legacyReadingVehicle.status},reminders:[],services:[]})};
    if(path.includes('/records/page?')) return {ok:true,json:async()=>({records:[],nextCursor:null})};
    if(path.includes('/odometer/page?')) return {ok:true,json:async()=>({readings:[{id:90,date:'2026-02-01',odometer:0,odometerExact:'0.000',unit:'km',note:'Record 22',revision:1,provenance:provenanceManualWrites.length?'manual':'legacy_unknown',sourceRecordId:null}],nextCursor:null})};
    if(path==='/garage-api/vehicles/63/odometer/90' && !options.method) return {ok:true,json:async()=>({reading:{id:90,date:'2026-02-01',odometer:0,odometerExact:'0.000',unit:'km',note:'Record 22',revision:1,provenance:'legacy_unknown',sourceRecordId:null}})};
    if(options.method==='PUT' && path.endsWith('/provenance')) {provenanceManualWrites.push(JSON.parse(options.body));return {ok:true,json:async()=>({reading:{id:90,date:'2026-02-01',odometerExact:'0.000',unit:'km',revision:2,provenance:'manual',sourceRecordId:null},record:null})};}
    if(path==='/garage-api/vehicles/63/history') return {ok:true,json:async()=>({events:[]})};
    throw Error('Unexpected manual provenance request: '+path);
  },{standalone:true,historyBrowsing:true,measurementCorrections:true});
  nodes['logbook-toggle'].listeners.click(); await new Promise(resolve=>setTimeout(resolve,0)); nodes['logbook-type'].value='odometer'; nodes['logbook-type'].listeners.change(); await nodes['logbook-filters'].listeners.submit({preventDefault(){}});
  const resolution=nodes['logbook-records'].querySelectorAll('button').find(button=>button.id==='log-odometer-resolve-90'); assert.ok(resolution);
  await resolution.listeners.click(); assert.match(nodes['own-hint'].textContent,/nur, wenn du diesen Stand unabhängig/);
  assert.equal(nodes['own-fields'].querySelectorAll('input').find(field=>field.id==='entry-provenanceConfirm').checked,false);
  measurementField('measurement-reason').value='Alten Zettel geprüft';
  await nodes['own-form'].listeners.submit({preventDefault(){}}); assert.equal(provenanceManualWrites.length,0);
  nodes['own-fields'].querySelectorAll('input').find(field=>field.id==='entry-provenanceConfirm').checked=true; await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(provenanceManualWrites[0].provenance,'manual'); assert.equal(provenanceManualWrites[0].sourceRecordId,null); assert.equal(provenanceManualWrites[0].recordRevision,null); assert.equal(provenanceManualWrites[0].revision,1);
  assert.equal(nodes['logbook-records'].querySelectorAll('button').find(button=>button.id==='log-odometer-edit-90').focused,true,'after reload, the independent-reading correction action is offered and focused');

  // A new correction draft survives refresh, vehicle selection and attempts to open another editor.
  const guardedVehicles=[legacyReadingVehicle,{...legacyReadingVehicle,id:64,name:'Anderes Fahrzeug'}]; let vehicleListReads=0; const guardedSummaryReads=[];
  nodes=await run(async(path,options={})=>{
    if(path==='/garage-api/vehicles') {vehicleListReads++;return {ok:true,json:async()=>({vehicles:guardedVehicles})};}
    if(path==='/garage-api/vehicles/63/summary'||path==='/garage-api/vehicles/64/summary') {guardedSummaryReads.push(path);return {ok:true,json:async()=>({vehicle:{status:legacyReadingVehicle.status},reminders:[],services:[{id:91,date:'2026-02-01',description:'Korrekturgrundlage',kind:'service',odometer:5,odometerUnit:'km'}]})};}
    if(path==='/garage-api/vehicles/63/records/91/measurement') return {ok:true,json:async()=>({record:{id:91,revision:2,date:'2026-02-01',odometer:5,odometerUnit:'km',closedIssueId:null},odometerExact:'5.000',sourceReading:{id:92,date:'2026-02-01',odometer:5,odometerExact:'5.000',unit:'km',revision:3,provenance:'record',sourceRecordId:91},correctionMode:'linked',currentReading:null})};
    throw Error('Unexpected guarded correction request: '+path);
  },{standalone:true,measurementCorrections:true});
  await nodes.services.querySelectorAll('button').find(button=>button.id==='record-measurement-edit-91').listeners.click();
  const guardedField=name=>nodes['own-fields'].querySelectorAll('input').find(field=>field.id==='entry-'+name);
  guardedField('measurement-date').value='2026-02-02'; guardedField('measurement-odometer').value='6,125'; guardedField('measurement-reason').value='Entwurf nicht verlieren';
  const initialListReads=vehicleListReads;
  nodes.refresh.listeners.click();
  await nodes.vehicles.children.find(card=>card.getAttribute('aria-label').includes('Anderes Fahrzeug')).listeners.click();
  nodes['vehicle-add'].listeners.click();
  assert.equal(vehicleListReads,initialListReads,'refresh is blocked while a correction draft is open');
  assert.equal(guardedSummaryReads.includes('/garage-api/vehicles/64/summary'),false,'switching cards is blocked while a correction draft is open');
  assert.equal(nodes['own-title'].textContent,'Datum / Stand korrigieren'); assert.equal(nodes['own-panel'].hidden,false);
  assert.equal(guardedField('measurement-date').value,'2026-02-02'); assert.equal(guardedField('measurement-odometer').value,'6,125'); assert.equal(guardedField('measurement-reason').value,'Entwurf nicht verlieren');
  assert.match(nodes['own-message'].textContent,/Entwurf bleibt erhalten/);

  // Annual usage remains exact decimal text; unit changes without a real anchor clear it without converting.
  const mileageMetaVehicle={id:70,name:'Jahresnutzung',make:'Test',model:'Fahrzeug',odometerUnit:'km',annualUsage:'12000',readingPromptDays:30,mileageEstimate:{asOf:'2026-10-29',timeZone:'Europe/Berlin',state:'anchor_missing',annualUsage:'12000',unit:'km',anchor:null,elapsedDays:null,estimatedOdometer:null},readingPrompt:{asOf:'2026-10-29',timeZone:'Europe/Berlin',state:'needs_reading',intervalDays:30,dueDate:null,reason:null},revision:2,status:{readiness:'ready',issues:[],revision:1}};
  let mileageMetaPayload=null, mileageMetaWriteCount=0, mileageMetaListReads=0, mileageMetaState={...mileageMetaVehicle};
  nodes=await run(async(path,options={})=>{
    if(path==='/garage-api/vehicles' && !options.method) {mileageMetaListReads++;return {ok:true,json:async()=>({vehicles:[mileageMetaState]})};}
    if(path==='/garage-api/vehicles/70/summary') return {ok:true,json:async()=>({vehicle:{...mileageMetaState,status:mileageMetaState.status},reminders:[],services:[]})};
    if(path==='/garage-api/vehicles/70' && options.method==='PUT') {mileageMetaPayload=JSON.parse(options.body);mileageMetaWriteCount++;mileageMetaState={...mileageMetaState,...mileageMetaPayload,revision:3};return {ok:true,json:async()=>({vehicle:mileageMetaState})};}
    throw Error('Unexpected annual usage request: '+path);
  },{standalone:true,mileageForecast:true});
  nodes['vehicle-edit'].listeners.click();
  const mileageField=id=>nodes['own-fields'].querySelectorAll('input').concat(nodes['own-fields'].querySelectorAll('select')).find(field=>field.id===id);
  assert.equal(mileageField('entry-annualUsage').value,'12000'); assert.equal(mileageField('entry-annualUsage').placeholder,'z. B. 12000'); assert.match(nodes['own-fields'].querySelectorAll('p').find(element=>element.id==='annual-usage-hint').textContent,/Keine Tausendertrennzeichen/);
  assert.equal(mileageField('entry-readingPromptDays').value,'30'); assert.equal(mileageField('entry-readingPromptEnabled').checked,true);
  const readsWhileEditing=mileageMetaListReads; await nodes.__inspectionTick(); assert.equal(mileageMetaListReads,readsWhileEditing,'periodic vehicle projection refresh does not replace an open metadata draft'); assert.equal(mileageField('entry-annualUsage').value,'12000');
  const mileageUnit=mileageField('entry-odometerUnit'); mileageUnit.value='mi'; mileageUnit.listeners.change();
  assert.equal(mileageField('entry-annualUsage').value,''); assert.match(nodes['own-fields'].textContent,/nicht umgerechnet/);
  mileageField('entry-annualUsage').value='0,125';
  mileageField('entry-readingPromptEnabled').checked=false; mileageField('entry-readingPromptEnabled').listeners.change();
  assert.equal(mileageField('entry-readingPromptDays').disabled,true);
  await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(mileageMetaPayload.annualUsage,'0.125'); assert.equal(typeof mileageMetaPayload.annualUsage,'string'); assert.equal(mileageMetaPayload.readingPromptDays,null); assert.equal(mileageMetaPayload.odometerUnit,'mi');
  nodes['vehicle-edit'].listeners.click();
  mileageField('entry-annualUsage').value='1000000000.001'; mileageField('entry-readingPromptEnabled').checked=true; mileageField('entry-readingPromptEnabled').listeners.change(); mileageField('entry-readingPromptDays').value='0';
  await nodes['own-form'].listeners.submit({preventDefault(){}}); assert.equal(mileageMetaWriteCount,1); assert.match(nodes['own-message'].textContent,/0 bis 1\.000\.000\.000/);
  mileageField('entry-annualUsage').value='0'; mileageField('entry-readingPromptDays').value='3651';
  await nodes['own-form'].listeners.submit({preventDefault(){}}); assert.equal(mileageMetaWriteCount,1); assert.match(nodes['own-message'].textContent,/1 bis 3650 Tage/);
  nodes['own-cancel'].listeners.click();

  const forecastVehicle=(id,name,estimateState,promptState,promptReason=null)=>({id,name,make:'Test',model:'Auto',odometerUnit:'km',annualUsage:estimateState==='annual_usage_missing'?null:'12000',readingPromptDays:30,mileageEstimate:{asOf:'2026-10-29',timeZone:'Europe/Berlin',state:estimateState,annualUsage:estimateState==='annual_usage_missing'?null:'12000',unit:'km',anchor:estimateState==='anchor_missing'?null:{id:id*10,date:estimateState==='future_anchor'?'2026-11-01':'2026-10-01',odometer:'1000.000',unit:estimateState==='unit_mismatch'?'mi':'km'},elapsedDays:estimateState==='future_anchor'?-3:28,estimatedOdometer:estimateState==='estimated'?'1921.918':null},readingPrompt:{asOf:'2026-10-29',timeZone:'Europe/Berlin',state:promptState,intervalDays:30,dueDate:promptState==='due'?'2026-10-25':null,reason:promptReason},revision:1,status:{readiness:'ready',issues:[],revision:0}});
  const promptVehicles=[forecastVehicle(71,'Fällig', 'estimated','due'),forecastVehicle(72,'Stand fehlt','anchor_missing','needs_reading'),forecastVehicle(73,'Prüfen','future_anchor','needs_review','future_anchor'),forecastVehicle(74,'Noch nicht','estimated','not_due'),forecastVehicle(75,'Ausgeschaltet','annual_usage_missing','disabled')];
  let promptWrite=null, promptVehicleList=promptVehicles.slice(), promptSummaryReads=[];
  nodes=await run(async(path,options={})=>{
    if(path==='/garage-api/vehicles' && !options.method) return {ok:true,json:async()=>({vehicles:promptVehicleList})};
    const summaryMatch=path.match(/^\/garage-api\/vehicles\/(\d+)\/summary$/);
    if(summaryMatch) {promptSummaryReads.push(path);const selected=promptVehicleList.find(vehicle=>String(vehicle.id)===summaryMatch[1]);return {ok:true,json:async()=>({vehicle:selected,reminders:[],services:[]})};}
    if(path==='/garage-api/vehicles/71/odometer' && options.method==='POST') {promptWrite=JSON.parse(options.body);promptVehicleList=promptVehicleList.map(vehicle=>String(vehicle.id)==='71'?{...vehicle,readingPrompt:{...vehicle.readingPrompt,state:'not_due',dueDate:'2026-11-30'}}:vehicle);return {ok:true,json:async()=>({id:110,vehicleId:71,date:promptWrite.date,odometer:promptWrite.odometer,unit:'km',note:null})};}
    if(path==='/garage-api/vehicles/73/odometer/page?limit=25') return {ok:true,json:async()=>({readings:[],nextCursor:null})};
    throw Error('Unexpected mileage prompt request: '+path);
  },{standalone:true,mileageForecast:true,historyBrowsing:true});
  assert.equal(nodes['mileage-prompts'].hidden,false); assert.match(nodes['mileage-prompt-items'].textContent,/Fällig/); assert.match(nodes['mileage-prompt-items'].textContent,/Stand fehlt/); assert.match(nodes['mileage-prompt-items'].textContent,/Prüfen/); assert.doesNotMatch(nodes['mileage-prompt-items'].textContent,/Noch nicht|Ausgeschaltet/);
  assert.match(nodes['mileage-forecast'].textContent,/Geschätzt heute: ca\. 1\.921,918 km/); assert.match(nodes['mileage-forecast'].textContent,/letzter tatsächlicher Stand: 1\.000,000 km am 01\.10\.2026/);
  const promptReview=nodes['mileage-prompt-items'].querySelectorAll('button').find(button=>button.id==='mileage-prompt-action-73'); assert.equal(promptReview.textContent,'Verlauf prüfen'); await promptReview.listeners.click();
  assert.equal(nodes['own-panel'].hidden,true,'reviewing a future anchor does not open a blank-reading form'); assert.equal(nodes['logbook-panel'].hidden,false); assert.equal(nodes['logbook-type'].value,'odometer'); assert.match(nodes['mileage-forecast'].textContent,/liegt in der Zukunft/,'signed elapsed days keep the future-anchor estimate usable');
  nodes['logbook-close'].listeners.click();
  const missingPrompt=nodes['mileage-prompt-items'].querySelectorAll('button').find(button=>button.id==='mileage-prompt-action-72'); await missingPrompt.listeners.click();
  assert.equal(nodes['own-panel'].hidden,false); assert.equal(mileageField('entry-date').value,'2026-10-29'); assert.equal(mileageField('entry-odometer').value,''); assert.equal(mileageField('entry-odometer').placeholder,'Abgelesener Stand');
  nodes['own-cancel'].listeners.click(); assert.equal(promptWrite,null,'opening and cancelling a prompt performs no write');
  const duePrompt=nodes['mileage-prompt-items'].querySelectorAll('button').find(button=>button.id==='mileage-prompt-action-71'); await duePrompt.listeners.click();
  assert.equal(mileageField('entry-odometer').value,'','the forecast is never copied into the actual-reading form');
  mileageField('entry-odometer').value='1250'; await nodes['own-form'].listeners.submit({preventDefault(){}});
  assert.equal(promptWrite.date,'2026-10-29'); assert.equal(promptWrite.odometer,1250); assert.equal(nodes['mileage-prompt-items'].querySelectorAll('article').some(row=>row.id==='mileage-prompt-71'),false,'a refreshed not-due response removes the prompt after saving an actual reading');
  await nodes.vehicles.children.find(card=>card.getAttribute('aria-label').includes('Ausgeschaltet')).listeners.click();
  assert.match(nodes['mileage-forecast'].textContent,/Jährliche Nutzung hinterlegen/);
  await nodes['mileage-forecast'].querySelectorAll('button').find(button=>button.textContent==='Jahresnutzung eintragen').listeners.click();
  assert.equal(nodes['own-title'].textContent,'Fahrzeug bearbeiten'); assert.equal(mileageField('entry-annualUsage').value,''); nodes['own-cancel'].listeners.click();
  await nodes.vehicles.children.find(card=>card.getAttribute('aria-label').includes('Stand fehlt')).listeners.click();
  assert.match(nodes['mileage-forecast'].textContent,/tatsächlichen Stand erfassen/);
  await nodes['mileage-forecast'].querySelectorAll('button').find(button=>button.textContent==='Tatsächlichen Stand erfassen').listeners.click();
  assert.equal(mileageField('entry-date').value,'2026-10-29'); assert.equal(mileageField('entry-odometer').value,''); nodes['own-cancel'].listeners.click();

  const legacyWorkRequests=[];
  nodes=await run(async path=>{legacyWorkRequests.push(path);return path==='/garage-api/vehicles'?{ok:true,json:async()=>({vehicles:[{id:30,name:'Legacy Fahrzeug',status:{readiness:'ready',issues:[{id:1,text:'Nur Text'}],revision:1}}]})}:{ok:true,json:async()=>({vehicle:{status:{readiness:'ready',issues:[{id:1,text:'Nur Text'}],revision:1}},reminders:[],services:[{id:31,date:'2026-02-01',description:'Legacy service',kind:'service'}]})};});
  assert.equal(nodes['work-dashboard'].hidden,true);
  assert.equal(legacyWorkRequests.includes('/garage-api/work'),false);
  assert.equal(nodes['mileage-prompts'].hidden,true); assert.equal(nodes['mileage-forecast'].hidden,true);
  assert.equal(nodes.services.querySelectorAll('button').some(button=>button.id==='record-measurement-edit-31'),false,'measurement correction action remains hidden without the standalone capability');
  assert.equal(legacyWorkRequests.some(path=>path.includes('/measurement')),false,'legacy capability absence does not call measurement APIs');

  console.log('Frontend: Legacy-Anzeige, Standalone-Erfassung, Verlauf, Logbuchpagination und geplante offene Arbeiten bestanden.');
})().catch(err => { console.error(err); process.exitCode = 1; });
