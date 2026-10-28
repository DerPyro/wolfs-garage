"use strict";

// Both backends use this presentation contract. Never insert API strings as HTML.
const $ = (id) => document.getElementById(id);
const state = { vehicles: [], selected: null, generation: 0, editingRevision: null, saving: false, standalone: false, recordCorrections: false, capabilitiesReady: false, entry: null };
const display = (value) => value === null || value === undefined ? "" : String(value).trim();
const el = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; };
function icon(name) { const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("aria-hidden", "true"); const use = document.createElementNS("http://www.w3.org/2000/svg", "use"); use.setAttribute("href", `#i-${name}`); svg.append(use); return svg; }
function readableDate(value) { const s = display(value); if (!s) return ""; const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s); if (!m) return s; return `${m[3]}.${m[2]}.${m[1]}`; }
function number(value) { const n = Number(value); return value !== null && value !== "" && value !== undefined && Number.isFinite(n) ? new Intl.NumberFormat("de-DE").format(n) : ""; }
function vehicleName(vehicle) { return display(vehicle.name) || [display(vehicle.make), display(vehicle.model)].filter(Boolean).join(" ") || "Fahrzeug"; }
function vehicleSubtitle(vehicle) { return [display(vehicle.licensePlate), display(vehicle.year)].filter(Boolean).join(" · "); }
// Types are explicitly maintained per vehicle; no classification based on make/model.
function vehicleIcon(type) {
  const value = display(type).toLocaleLowerCase("de-DE");
  if (/hochdach|high.?roof/.test(value)) return "highroof";
  if (/schrägheck|schraegheck|hatchback/.test(value)) return "hatchback";
  if (/cross|motocross|enduro/.test(value)) return "cross";
  if (/naked/.test(value)) return "naked";
  if (/motorrad|motorcycle/.test(value)) return "bike";
  if (/limousine|kombi|coupé|coupe|cabrio|suv|pkw|auto/.test(value)) return "sedan";
  return "vehicle";
}
function manufacturerMark(make) {
  const value = display(make); if (!value) return null;
  const mark = el("span", "manufacturer manufacturer-watermark"); mark.setAttribute("aria-hidden", "true");
  const logos = new Map([["peugeot","peugeot.svg"], ["yamaha","yamaha-motor.svg"], ["yamaha motor","yamaha-motor.svg"], ["yamaha motor corporation","yamaha-motor.svg"], ["opel","opel.svg"], ["suzuki","suzuki.svg"]]);
  const logo = logos.get(value.toLocaleLowerCase("de-DE"));
  if (logo) { mark.classList.add("has-logo"); const image = el("img", "manufacturer-logo"); image.src = `/garage-assets/brands/${logo}`; image.alt = ""; image.setAttribute("aria-hidden", "true"); mark.append(image); }
  mark.append(el("span", "manufacturer-name", value.toLocaleUpperCase("de-DE"))); return mark;
}
function distance(value, unit) { const n = number(value); if (!n) return ""; const u = display(unit); return u ? `${n} ${u}` : `Stand ${n} (Einheit unbekannt)`; }
function cost(value, currency) { const n = number(value); if (!n) return ""; const c = display(currency); return c ? `${n} ${c}` : `Kosten: ${n} (Währung unbekannt)`; }
function setStatus(id, message, error = false) { const node = $(id); node.textContent = message; node.classList.toggle("error", error); }
async function getJson(url) { const response = await fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" }); if (!response.ok) { const error = new Error(`HTTP ${response.status}`); error.status = response.status; throw error; } return response.json(); }
const readinessLabels = { ready: "Fahrbereit", not_ready: "Nicht fahrbereit", unknown: "Status nicht erfasst" };
function validCondition(condition) { return condition && Object.hasOwn(readinessLabels, condition.readiness) && Array.isArray(condition.issues) && Number.isInteger(condition.revision) && condition.revision >= 0; }
function conditionBadge(condition) { const known = validCondition(condition); const badge = el("span", `readiness-badge ${known ? condition.readiness : "unavailable"}`, known ? readinessLabels[condition.readiness] : "Status nicht verfügbar"); const dot = el("span", "readiness-dot"); dot.setAttribute("aria-hidden", "true"); badge.prepend(dot); return badge; }
function conditionIssueText(condition) { return validCondition(condition) ? condition.issues.filter(item => item && display(item.text)).map(item => display(item.text)) : []; }
// These indicators share the existing header row; the detailed state remains in the accessible card name and detail panel.
function cardIndicators(condition, issues) {
  const group = el("span", "card-indicators"); group.setAttribute("aria-hidden", "true");
  const readiness = validCondition(condition) ? condition.readiness : "unavailable";
  const symbols = {not_ready: "INOP", unknown: "?", unavailable: "!"};
  const label = validCondition(condition) ? readinessLabels[readiness] : "Status nicht verfügbar";
  if (symbols[readiness]) { const indicator = el("span", `card-readiness ${readiness}`, symbols[readiness]); indicator.setAttribute("title", label); group.append(indicator); }
  if (validCondition(condition) && issues.length) { const warning = el("span", "card-work"); warning.setAttribute("title", "Wartung ausstehend"); warning.append(icon("tool")); group.append(warning); }
  return group;
}

function renderCards() {
  const container = $("vehicles"); container.replaceChildren();
  for (const vehicle of state.vehicles) {
    const id = String(vehicle.id); const button = el("button", "vehicle-card"); button.type = "button"; button.setAttribute("aria-pressed", String(state.selected === id));
    const type = display(vehicle.vehicleType); const condition = vehicle.status; const issues = conditionIssueText(condition); const accessible = [vehicleName(vehicle), type && `Fahrzeugtyp ${type}`, display(vehicle.licensePlate) && `Kennzeichen ${display(vehicle.licensePlate)}`, display(vehicle.year), validCondition(condition) ? readinessLabels[condition.readiness] : "Status nicht verfügbar", ...issues.map(value => `Offen: ${value}`)].filter(Boolean).join(", "); button.setAttribute("aria-label", accessible);
    const top = el("div", "card-top"); const badge = el("span", "car-icon"); badge.append(icon(vehicleIcon(vehicle.vehicleType))); const arrow = el("span", "card-arrow"); arrow.append(icon("arrow")); top.append(badge, cardIndicators(condition, issues));
    const make = manufacturerMark(vehicle.make); top.append(arrow);
    const name = el("h3", "", vehicleName(vehicle)); const meta = el("div", "vehicle-meta");
    const plate = display(vehicle.licensePlate); if (plate) { const label = el("span", "license-plate", plate); label.setAttribute("role", "img"); label.setAttribute("aria-label", `Kennzeichen ${plate}`); meta.append(label); }
    const year = display(vehicle.year); if (year) meta.append(el("span", "vehicle-year", year));
    button.append(top, name); if (plate || year) button.append(meta);
    const mileage = distance(vehicle.odometer, vehicle.odometerUnit); if (mileage) button.append(el("p", "mileage", mileage));
    if (make) button.append(make);
    button.addEventListener("click", () => selectVehicle(id)); container.append(button);
  }
}
function closeConditionEditor(restoreFocus = false) { $("condition-form").hidden = true; $("condition-view").hidden = false; $("condition-edit").setAttribute("aria-expanded", "false"); $("condition-message").textContent = ""; state.editingRevision = null; if (restoreFocus) $("condition-edit").focus(); }
function renderCondition(condition) {
  $("condition-readiness").replaceChildren(conditionBadge(condition));
  const issues = conditionIssueText(condition); const list = $("condition-issues"); list.replaceChildren();
  if (validCondition(condition)) { if (!issues.length) list.append(el("p", "condition-empty", "Keine offenen Punkte hinterlegt.")); else { const heading=el("p", "condition-issues-title", "Offene Punkte"); const ul=el("ul", "condition-issue-list"); for (const item of issues) ul.append(el("li", "", item)); list.append(heading, ul); } }
  else list.append(el("p", "condition-empty", "Der aktuelle Zustand ist momentan nicht verfügbar."));
  $("condition-edit").disabled = !validCondition(condition) || state.saving;
}
function appendIssueEditor(issue = {}) {
  const editor = $("issue-editor"); if (editor.querySelectorAll("input").length >= 20) return;
  const row = el("div", "issue-row"); const input = el("input", "issue-input"); input.type = "text"; input.maxLength = 160; input.required = true; input.placeholder = "Was ist noch zu tun?"; input.value = display(issue.text); input._issueId = issue.id;
  input.setAttribute("aria-label", "Beschreibung des offenen Punkts");
  const remove = el("button", "issue-remove", "Entfernen"); remove.type = "button"; remove.setAttribute("aria-label", "Diesen offenen Punkt entfernen"); remove.addEventListener("click", () => { row.remove(); $("issue-add").disabled = editor.querySelectorAll("input").length >= 20; });
  row.append(input, remove); editor.append(row); $("issue-add").disabled = editor.querySelectorAll("input").length >= 20;
}
function openConditionEditor() {
  if (state.entry && state.entry.busy) return;
  if (state.entry) closeEntry();
  const vehicle = state.vehicles.find(v => String(v.id) === state.selected); const condition = vehicle && vehicle.status;
  if (!validCondition(condition) || state.saving) return;
  state.editingRevision = condition.revision; $("readiness-input").value = condition.readiness; $("issue-editor").replaceChildren();
  for (const item of condition.issues) if (item && display(item.text)) appendIssueEditor(item);
  $("issue-add").disabled = $("issue-editor").querySelectorAll("input").length >= 20;
  $("condition-view").hidden = true; $("condition-form").hidden = false; $("condition-edit").setAttribute("aria-expanded", "true"); $("condition-message").textContent = ""; $("readiness-input").focus();
}
async function saveCondition(event) {
  event.preventDefault(); if (state.saving || state.selected === null || state.editingRevision === null) return;
  const id = state.selected; const inputs = Array.from($("issue-editor").querySelectorAll("input"));
  const issues = inputs.map(input => { const item = {text: input.value.trim()}; if (input._issueId !== undefined && input._issueId !== null) item.id = input._issueId; return item; });
  if (issues.some(item => !item.text || item.text.length > 160 || /[\x00-\x1f\x7f]/.test(item.text))) { $("condition-message").textContent = "Bitte gib für jeden offenen Punkt eine Beschreibung mit höchstens 160 Zeichen ein."; return; }
  state.saving = true; $("condition-save").disabled = true; $("condition-cancel").disabled = true; $("condition-message").textContent = "Wird gespeichert …";
  try {
    const response = await fetch(`/garage-api/vehicles/${encodeURIComponent(id)}/status`, {method:"PUT", credentials:"same-origin", headers:{"Content-Type":"application/json", "X-Garage-Request":"1"}, body:JSON.stringify({readiness:$("readiness-input").value, issues, revision:state.editingRevision})});
    if (!response.ok) { if (response.status === 409) throw new Error("Dieser Zustand wurde inzwischen geändert. Bitte aktualisiere die Übersicht und versuche es erneut."); if (response.status === 503) throw new Error("Der Zustandsspeicher ist momentan nicht verfügbar. Bitte versuche es später erneut."); throw new Error("Der Zustand konnte nicht gespeichert werden. Bitte versuche es erneut."); }
    const updated = await response.json(); if (!validCondition(updated)) throw new Error("Der gespeicherte Zustand konnte nicht gelesen werden. Bitte aktualisiere die Übersicht.");
    const vehicle = state.vehicles.find(v => String(v.id) === id); if (vehicle) vehicle.status = updated;
    renderCards(); if (state.selected === id) { closeConditionEditor(true); renderCondition(updated); }
  } catch (error) { if (state.selected === id) $("condition-message").textContent = error instanceof TypeError ? "Der Zustand konnte nicht gespeichert werden. Bitte prüfe deine Verbindung." : error.message || "Der Zustand konnte nicht gespeichert werden."; }
  finally { state.saving = false; $("condition-save").disabled = false; $("condition-cancel").disabled = false; const selectedVehicle = state.vehicles.find(v => String(v.id) === state.selected); $("condition-edit").disabled = !validCondition(selectedVehicle && selectedVehicle.status); }
}
function renderRecords(target, items, kind) {
  const container = $(target); container.replaceChildren();
  if (!Array.isArray(items)) { container.append(el("p", "empty-panel", "Diese Informationen sind momentan nicht verfügbar.")); return; }
  if (items.length === 0) { container.append(el("p", "empty-panel", kind === "reminders" ? "Für dieses Fahrzeug sind keine Erinnerungen hinterlegt." : "Für dieses Fahrzeug sind keine Wartungseinträge hinterlegt.")); return; }
  for (const item of items.slice(0, 5)) {
    const row = el("div", "record"); const left = el("div"); const title = display(item.description) || (kind === "reminders" ? "Erinnerung" : "Wartung"); left.append(el("div", "record-title", title));
    const details = kind === "reminders" ? [readableDate(item.dueDate), distance(item.dueOdometer, item.odometerUnit)] : [readableDate(item.date), distance(item.odometer, item.odometerUnit)];
    if (details.filter(Boolean).length) left.append(el("p", "record-sub", details.filter(Boolean).join(" · ")));
    if (kind === "services" && item.documentUrl) { try { const url = new URL(item.documentUrl); if (url.protocol === "https:" && !url.username && !url.password) { const link = el("a", "record-document", "Beleg öffnen"); link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; left.append(link); } } catch (_) { /* untrusted invalid document links stay hidden */ } }
    row.append(left);
    if (kind === "reminders" && display(item.status)) { const label = el("span", "record-value", display(item.status)); if (item.status === "Überfällig") label.classList.add("overdue"); row.append(label); }
    if (kind === "services" && item.cost !== null && item.cost !== undefined && item.cost !== "") { const value = cost(item.cost, item.currency); if (value) row.append(el("span", "record-value", value)); }
    if (kind === "services" && state.recordCorrections && item.id !== null && item.id !== undefined) { const edit = el("button", "condition-edit record-edit", "Beleg korrigieren"); edit.type = "button"; edit.id = `record-edit-${String(item.id)}`; edit.setAttribute("aria-label", `Beleg korrigieren: ${title}`); edit.addEventListener("click", () => openRecordCorrection(item.id)); row.append(edit); }
    container.append(row);
  }
}
async function selectVehicle(id) {
  if (state.entry && state.entry.busy) return;
  if (state.entry) closeEntry();
  $("history-panel").hidden = true; $("history-toggle").setAttribute("aria-expanded", "false");
  state.selected = id; renderCards(); const vehicle = state.vehicles.find((v) => String(v.id) === id); if (!vehicle) return;
  closeConditionEditor(); renderCondition(vehicle.status);
  $("detail").hidden = false; $("detail-heading").textContent = vehicleName(vehicle); $("detail-meta").textContent = vehicleSubtitle(vehicle); $("detail-content").hidden = true; setStatus("detail-status", "Fahrzeugdaten werden geladen …");
  const generation = ++state.generation;
  try { const result = await getJson(`/garage-api/vehicles/${encodeURIComponent(id)}/summary`); if (generation !== state.generation) return; if (result.vehicle && validCondition(result.vehicle.status)) { vehicle.status = result.vehicle.status; if ($("condition-form").hidden) renderCondition(vehicle.status); renderCards(); } renderRecords("reminders", result.reminders, "reminders"); renderRecords("services", result.services, "services"); setStatus("detail-status", ""); $("detail-content").hidden = false; }
  catch (error) { if (generation === state.generation) setStatus("detail-status", error.status === 503 ? "Der Zustandsspeicher ist momentan nicht verfügbar. Bitte versuche es später erneut." : "Die Fahrzeugdaten konnten nicht geladen werden. Bitte versuche es erneut.", true); }
}
async function load(preferredId = null) {
  $("refresh").disabled = true; setStatus("status", "Fahrzeuge werden geladen …"); $("vehicle-count").hidden = true; $("detail").hidden = true; $("detail-content").hidden = true; state.selected = null; ++state.generation; $("vehicles").replaceChildren();
  try { const result = await getJson("/garage-api/vehicles"); if (!Array.isArray(result.vehicles)) throw new Error("invalid vehicles"); state.vehicles = result.vehicles.filter((v) => v && v.id !== null && v.id !== undefined); $("vehicle-count").textContent = state.vehicles.length; $("vehicle-count").hidden = false;
    if (!state.vehicles.length) { const status = $("status"); status.replaceChildren(document.createTextNode("Deine Garage ist noch leer. ")); if (state.standalone) { const button = el("button", "condition-edit", "Erstes Fahrzeug anlegen"); button.type = "button"; button.addEventListener("click", () => openEntry("vehicle-new")); status.append(button); } else { const link = el("a", "", "Erstes Fahrzeug in LubeLogger anlegen"); link.href = "/Home"; status.append(link); } return; }
    setStatus("status", ""); renderCards(); const selected = state.vehicles.find(v => String(v.id) === String(preferredId)) || state.vehicles[0]; await selectVehicle(String(selected.id));
  } catch (error) { setStatus("status", error.status === 503 ? "Der Zustandsspeicher ist momentan nicht verfügbar. Bitte versuche es später erneut." : "Die Fahrzeuge konnten nicht geladen werden. Bitte versuche es erneut.", true); }
  finally { $("refresh").disabled = false; }
}
$("refresh").addEventListener("click", () => state.capabilitiesReady ? load(state.selected) : initialize());
$("condition-edit").addEventListener("click", openConditionEditor);
$("condition-cancel").addEventListener("click", () => closeConditionEditor(true));
$("issue-add").addEventListener("click", () => appendIssueEditor());
$("condition-form").addEventListener("submit", saveCondition);

function selectedVehicle() { return state.vehicles.find(v => String(v.id) === state.selected); }
function localToday() { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`; }
function entryField(labelText, name, type, value = "", options = null) {
  const wrapper = el("div", "own-field"); const label = el("label", "", labelText); const field = el(options ? "select" : "input");
  field.id = `entry-${name}`; label.setAttribute("for", field.id); field.name = name;
  if (options) { for (const [key, text] of options) { const option = el("option", "", text); option.value = key; field.append(option); } }
  else field.type = type;
  field.value = value === null || value === undefined ? "" : String(value); wrapper.append(label, field); $("own-fields").append(wrapper); return field;
}
function readonlyRecordFacts(record) {
  const date = readableDate(record.date) || "Datum nicht verfügbar";
  const reading = record.odometer === null || record.odometer === undefined || record.odometer === "" ? "Stand nicht erfasst" : `${number(record.odometer)} ${display(record.odometerUnit) || "Einheit unbekannt"}`;
  $("record-edit-readonly-date").textContent = `Datum: ${date}`;
  $("record-edit-readonly-odometer").textContent = `Stand: ${reading}`;
  $("record-edit-readonly-closed-issue").textContent = record.closedIssueId === null || record.closedIssueId === undefined || record.closedIssueId === "" ? "Kein Punkt wurde mit diesem Beleg abgeschlossen." : "Punktabschluss bei der Erfassung bleibt unverändert.";
}
async function openRecordCorrection(recordId) {
  if (!state.standalone || !state.recordCorrections || state.saving || state.entry && state.entry.busy) return;
  const vehicle = selectedVehicle(); if (!vehicle || recordId === null || recordId === undefined) return;
  if (!globalThis.crypto || typeof globalThis.crypto.randomUUID !== "function") { $("own-notice").textContent = "Zum Korrigieren benötigst du HTTPS oder einen lokalen Zugriff über localhost."; return; }
  if (state.entry) closeEntry();
  closeConditionEditor(); $("own-notice").textContent = ""; $("own-fields").replaceChildren(); $("own-message").textContent = "Beleg wird geladen …";
  $("own-title").textContent = "Belegkorrektur"; $("own-hint").textContent = "Datum und Kilometerstand bleiben unverändert. Eine Korrektur von Datum oder Stand ist in dieser Version noch nicht verfügbar.";
  $("record-edit-readonly").hidden = false; $("record-edit-readonly-date").textContent = "Datum wird geladen …"; $("record-edit-readonly-odometer").textContent = "Stand wird geladen …";
  $("record-edit-readonly-closed-issue").textContent = "Abgeschlossener Punkt wird geladen …"; $("own-save").disabled = true; $("own-cancel").disabled = true;
  $("own-panel").hidden = false;
  const entry = {mode:"record-edit", vehicleId:String(vehicle.id), recordId:String(recordId), opener:`record-edit-${String(recordId)}`, busy:true, commandId:globalThis.crypto.randomUUID()}; state.entry = entry;
  try {
    const record = await getJson(`/garage-api/vehicles/${encodeURIComponent(entry.vehicleId)}/records/${encodeURIComponent(entry.recordId)}`);
    if (state.entry !== entry || state.selected !== entry.vehicleId) return;
    if (!record || String(record.id) !== entry.recordId || !Number.isInteger(record.revision)) throw new Error("Belegdaten konnten nicht gelesen werden.");
    entry.revision = record.revision; entry.record = record; entry.busy = false;
    readonlyRecordFacts(record);
    const description = entryField("Beschreibung", "description", "text", record.description); description.required = true; description.maxLength = 160;
    entryField("Art der Arbeit", "kind", "", record.kind, [["service","Wartung"],["repair","Reparatur"]]);
    const amount = entryField("Kosten (optional)", "cost", "text", record.cost); amount.inputMode = "decimal"; amount.placeholder = "z. B. 49,90"; amount.maxLength = 20;
    const currency = entryField("Währung bei Kostenangabe", "currency", "text", record.currency); currency.maxLength = 3; currency.placeholder = "z. B. EUR"; currency.autocapitalize = "characters";
    const link = entryField("Beleglink (optional, HTTPS)", "documentUrl", "url", record.documentUrl); link.maxLength = 2000; link.placeholder = "https://…";
    const reason = entryField("Grund der Korrektur", "correctionReason", "text"); reason.required = true; reason.maxLength = 1600; reason.setAttribute("aria-describedby", "own-hint");
    $("own-message").textContent = ""; $("own-title").focus(); description.focus();
  } catch (error) {
    if (state.entry === entry) { entry.busy = false; $("own-save").disabled = true; $("own-cancel").disabled = false; $("own-message").textContent = error.status === 404 ? "Dieser Beleg gehört nicht zu diesem Fahrzeug oder ist nicht mehr verfügbar." : error.status === 503 ? "Der Belegspeicher ist momentan nicht verfügbar. Bitte versuche es später erneut." : error.message || "Der Beleg konnte nicht geladen werden. Bitte versuche es erneut."; }
  }
  if (state.entry === entry && !entry.busy) { $("own-save").disabled = !entry.record; $("own-cancel").disabled = false; }
}
function closeEntry(restoreFocus = false) {
  if (state.entry && state.entry.busy) return;
  const opener = state.entry && state.entry.opener; state.entry = null; $("own-panel").hidden = true; $("own-message").textContent = ""; $("record-edit-readonly").hidden = true;
  if (restoreFocus && opener) $(opener).focus();
}
function openEntry(mode) {
  if (!state.standalone || state.saving || state.entry && state.entry.busy) return;
  const vehicle = selectedVehicle(); if (mode !== "vehicle-new" && !vehicle) return;
  const names = {"vehicle-new":"Fahrzeug hinzufügen", "vehicle-edit":"Fahrzeug bearbeiten", odometer:"Stand erfassen", record:"Arbeit dokumentieren"};
  const openers = {"vehicle-new":"vehicle-add", "vehicle-edit":"vehicle-edit", odometer:"odometer-add", record:"record-add"};
  $("own-notice").textContent = "";
  state.entry = {mode, vehicleId:vehicle && String(vehicle.id), revision:vehicle && vehicle.revision, statusRevision:vehicle && vehicle.status && vehicle.status.revision, opener:openers[mode], busy:false};
  $("record-edit-readonly").hidden = true;
  if (mode === "odometer" || mode === "record") {
    if (!globalThis.crypto || typeof globalThis.crypto.randomUUID !== "function") { state.entry = null; $("own-notice").textContent = "Zum Erfassen benötigst du HTTPS oder einen lokalen Zugriff über localhost."; return; }
    state.entry.commandId = globalThis.crypto.randomUUID();
  }
  closeConditionEditor(); $("own-fields").replaceChildren(); $("own-message").textContent = ""; $("own-save").disabled = false; $("own-cancel").disabled = false; $("own-cancel").textContent = "Abbrechen"; $("own-title").textContent = names[mode]; $("own-hint").textContent = "";
  if (mode.startsWith("vehicle-")) {
    const values = mode === "vehicle-edit" ? vehicle : {};
    const make = entryField("Marke", "make", "text", values.make); make.required = true; make.maxLength = 80;
    const model = entryField("Modell", "model", "text", values.model); model.required = true; model.maxLength = 120;
    const year = entryField("Baujahr (optional)", "year", "number", values.year); year.min = "1800"; year.max = "2100"; year.step = "1";
    const plate = entryField("Kennzeichen (optional)", "licensePlate", "text", values.licensePlate); plate.maxLength = 30;
    const types = [["","Nicht festgelegt"],["Limousine","Limousine"],["Schrägheck","Schrägheck"],["Kombi","Kombi"],["Hochdachkombi","Hochdachkombi"],["SUV","SUV"],["Cross-Motorrad","Cross-Motorrad"],["Naked Bike","Naked Bike"],["Motorrad","Motorrad"],["Sonstiges","Sonstiges"]];
    if (values.vehicleType && !types.some(([key]) => key === values.vehicleType)) types.push([values.vehicleType, values.vehicleType]);
    entryField("Fahrzeugtyp", "vehicleType", "", values.vehicleType || "", types);
    entryField("Einheit für den Stand", "odometerUnit", "", values.odometerUnit || "km", [["km","Kilometer"],["mi","Meilen"],["h","Betriebsstunden"]]);
    $("own-hint").textContent = "Die Fahrbereitschaft bleibt unabhängig von den Stammdaten. Eine Änderung der Einheit rechnet vorhandene Einträge nicht um.";
  } else {
    const date = entryField("Datum", "date", "date", localToday()); date.required = true;
    if (mode === "record") {
      entryField("Art der Arbeit", "kind", "", "service", [["service","Wartung"],["repair","Reparatur"]]);
      const description = entryField("Durchgeführte Arbeit", "description", "text"); description.required = true; description.maxLength = 160;
    }
    const reading = entryField(`${mode === "record" ? "Stand (optional)" : "Stand"} in ${vehicle.odometerUnit}`, "odometer", "number", mode === "odometer" ? vehicle.odometer : ""); reading.required = mode === "odometer"; reading.min = "0"; reading.step = "any";
    if (mode === "odometer") { const note = entryField("Notiz (optional)", "note", "text"); note.maxLength = 500; }
    else {
      const amount = entryField("Kosten (optional)", "cost", "text"); amount.inputMode = "decimal"; amount.placeholder = "z. B. 49,90"; amount.maxLength = 20;
      const currency = entryField("Währung bei Kostenangabe", "currency", "text"); currency.maxLength = 3; currency.placeholder = "z. B. EUR"; currency.autocapitalize = "characters";
      const link = entryField("Beleglink (optional, HTTPS)", "documentUrl", "url"); link.maxLength = 2000; link.placeholder = "https://…";
      const issues = validCondition(vehicle.status) ? vehicle.status.issues : [];
      entryField("Offenen Punkt als erledigt markieren (optional)", "closeIssueId", "", "", [["","Keinen Punkt abschließen"], ...issues.map(issue => [issue.id, issue.text])]);
      $("own-hint").textContent = "Dokumentiere eine tatsächlich durchgeführte Arbeit. Ein ausgewählter Punkt wird zusammen mit dem Beleg abgeschlossen. Andere offene Punkte und die Fahrbereitschaft bleiben bestehen.";
    }
  }
  $("own-panel").hidden = false; $("own-title").focus();
}
async function saveEntry(event) {
  event.preventDefault(); const entry = state.entry; if (!entry || entry.busy) return;
  const field = name => $(`entry-${name}`).value.trim(); let payload; let path; let method = "POST";
  if (entry.mode === "record-edit") {
    const description = field("description"), kind = field("kind"), rawCost = field("cost"), rawCurrency = field("currency"), documentUrl = field("documentUrl"), correctionReason = field("correctionReason");
    if (!description || description.length > 160 || !["service","repair"].includes(kind) || !correctionReason || correctionReason.length > 1600 || /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(correctionReason)) { $("own-message").textContent = "Bitte prüfe Beschreibung, Arbeitsart und Korrekturgrund (maximal 1.600 Zeichen)."; return; }
    let costValue = null, currencyValue = null;
    if (rawCost || rawCurrency) {
      if (!/^\d+(?:[.,]\d{1,2})?$/.test(rawCost) || !/^[A-Za-z]{3}$/.test(rawCurrency)) { $("own-message").textContent = "Bitte gib Kosten mit höchstens zwei Nachkommastellen und eine dreistellige Währung an, z. B. 49,90 EUR. Zum Entfernen beide Felder leeren."; return; }
      costValue = rawCost.replace(",", "."); currencyValue = rawCurrency.toUpperCase();
    }
    let documentValue = null;
    if (documentUrl) { try { const url = new URL(documentUrl); if (url.protocol !== "https:" || url.username || url.password) throw new Error(); documentValue = url.href; } catch (_) { $("own-message").textContent = "Der Beleglink muss eine HTTPS-Adresse ohne eingebettete Zugangsdaten sein."; return; } }
    payload = {revision:entry.revision, commandId:entry.commandId, description, kind, cost:costValue, currency:currencyValue, documentUrl:documentValue, correctionReason};
    path = `/garage-api/vehicles/${encodeURIComponent(entry.vehicleId)}/records/${encodeURIComponent(entry.recordId)}`; method = "PUT";
  } else if (entry.mode.startsWith("vehicle-")) {
    payload = {make:field("make"), model:field("model"), licensePlate:field("licensePlate"), vehicleType:field("vehicleType"), odometerUnit:field("odometerUnit")};
    if (field("year")) payload.year = Number(field("year"));
    else if (entry.mode === "vehicle-edit") payload.year = null;
    path = "/garage-api/vehicles"; if (entry.mode === "vehicle-edit") { method = "PUT"; path += `/${entry.vehicleId}`; payload.revision = entry.revision; }
  } else {
    payload = {date:field("date"), commandId:entry.commandId};
    path = `/garage-api/vehicles/${entry.vehicleId}/${entry.mode === "odometer" ? "odometer" : "records"}`;
    if (field("odometer")) payload.odometer = Number(field("odometer"));
    if (entry.mode === "odometer") { payload.unit = selectedVehicle().odometerUnit; if (field("note")) payload.note = field("note"); }
    else {
      payload.description = field("description"); payload.kind = field("kind");
      if (field("cost")) {
        if (!/^\d+(?:[.,]\d{1,2})?$/.test(field("cost")) || !/^[A-Za-z]{3}$/.test(field("currency"))) { $("own-message").textContent = "Bitte gib einen positiven Betrag mit höchstens zwei Nachkommastellen und eine dreistellige Währung an, z. B. EUR."; return; }
        payload.cost = field("cost").replace(",", "."); payload.currency = field("currency").toUpperCase();
      }
      if (field("documentUrl")) payload.documentUrl = field("documentUrl");
      if (field("closeIssueId")) { payload.closeIssueId = field("closeIssueId"); payload.statusRevision = entry.statusRevision; }
    }
  }
  entry.busy = true; $("own-save").disabled = true; $("own-cancel").disabled = true; $("own-message").textContent = "Wird gespeichert …";
  try {
    const response = await fetch(path, {method, credentials:"same-origin", headers:{"Content-Type":"application/json", "X-Garage-Request":"1"}, body:JSON.stringify(payload)});
    if (!response.ok) {
      if (response.status === 409) throw new Error(entry.mode === "record-edit" ? "Dieser Beleg wurde inzwischen geändert. Bitte lade ihn erneut und prüfe den Verlauf." : "Die Daten wurden inzwischen geändert oder dieser Auftrag wurde bereits anders gespeichert. Bitte aktualisiere die Übersicht und prüfe den Verlauf.");
      let message = "Die Angaben konnten nicht gespeichert werden. Bitte prüfe deine Eingaben.";
      try { const detail = await response.json(); if (typeof detail.error === "string") message = detail.error; } catch (_) { /* retain the useful fallback */ }
      throw new Error(message);
    }
    const result = await response.json(); const id = entry.mode === "vehicle-new" ? (result.vehicle || result).id : entry.vehicleId;
    entry.busy = false; closeEntry(); await load(id); $("own-notice").textContent = entry.mode === "record-edit" ? "Belegkorrektur gespeichert. Verlauf wurde aktualisiert." : "Gespeichert.";
    if (entry.mode === "record-edit") await showHistory(true);
    if (entry.mode === "record-edit") { const button = document.getElementById(`record-edit-${entry.recordId}`); if (button) button.focus(); }
  } catch (error) {
    if (error instanceof TypeError && entry.mode === "vehicle-new") { entry.uncertain = true; $("own-cancel").textContent = "Schließen und prüfen"; }
    $("own-message").textContent = error instanceof TypeError ? "Die Antwort konnte nicht empfangen werden. Prüfe den Verlauf, bevor du eine neue Erfassung startest. Bei Stand und Arbeit kannst du dieselben Angaben mit Speichern erneut senden." : error.message;
  } finally { entry.busy = false; $("own-save").disabled = Boolean(entry.uncertain); $("own-cancel").disabled = false; }
}
function historyFacts(value) {
  if (!value || typeof value !== "object") return [];
  const facts = [];
  if (value.make || value.model) facts.push([display(value.make), display(value.model)].filter(Boolean).join(" "));
  if (value.licensePlate) facts.push(`Kennzeichen ${display(value.licensePlate)}`);
  if (value.year) facts.push(`Baujahr ${display(value.year)}`);
  if (value.vehicleType) facts.push(display(value.vehicleType));
  if (value.text) facts.push(display(value.text));
  if (value.readiness && readinessLabels[value.readiness]) facts.push(readinessLabels[value.readiness]);
  if (Array.isArray(value.issues)) facts.push(value.issues.length ? `Offen: ${value.issues.map(item => display(item.text)).join("; ")}` : "Keine offenen Punkte");
  if (value.description) facts.push(display(value.description));
  if (value.kind) facts.push(value.kind === "repair" ? "Reparatur" : value.kind === "service" ? "Wartung" : display(value.kind));
  if (value.date) facts.push(readableDate(value.date));
  if (value.odometer !== null && value.odometer !== undefined) facts.push(distance(value.odometer, value.odometerUnit || value.unit));
  if (value.cost !== null && value.cost !== undefined && value.cost !== "") facts.push(cost(value.cost, value.currency));
  else if (Object.hasOwn(value, "cost")) facts.push("Kosten entfernt");
  if (Object.hasOwn(value, "documentUrl")) facts.push(value.documentUrl ? `Beleglink: ${display(value.documentUrl)}` : "Beleglink entfernt");
  if (Object.hasOwn(value, "closedIssueId")) facts.push(value.closedIssueId ? "Offener Punkt bei der Erfassung abgeschlossen" : "Kein Punktabschluss zugeordnet");
  if (value.correctionReason) facts.push(`Korrekturgrund: ${display(value.correctionReason)}`);
  if (value.note) facts.push(display(value.note));
  if (value.record) facts.push(...historyFacts(value.record));
  if (value.status) facts.push(...historyFacts(value.status));
  return facts.filter(Boolean);
}
async function showHistory(force = false) {
  if (!state.standalone || !state.selected) return;
  if (!$("history-panel").hidden && !force) { $("history-panel").hidden = true; $("history-toggle").setAttribute("aria-expanded", "false"); return; }
  const id = state.selected; $("history-panel").hidden = false; $("history-toggle").setAttribute("aria-expanded", "true"); $("history-events").replaceChildren(); $("history-message").textContent = "Verlauf wird geladen …";
  try {
    const result = await getJson(`/garage-api/vehicles/${id}/history`); if (state.selected !== id) return;
    if (!Array.isArray(result.events)) throw new Error("invalid history");
    const actions = {"vehicle.created":"Fahrzeug angelegt", "vehicle.updated":"Stammdaten geändert", "status.updated":"Zustand aktualisiert", "odometer.created":"Stand erfasst", "issue.completed":"Offenen Punkt abgeschlossen", "record.created":"Arbeit dokumentiert", "record.corrected":"Beleg korrigiert"};
    for (const item of result.events.slice().reverse()) {
      const row = el("div", "history-event"); row.append(el("h4", "", actions[item.action] || "Änderung gespeichert"));
      const instant = new Date(item.occurredAt); if (!Number.isNaN(instant.getTime())) row.append(el("p", "record-sub", new Intl.DateTimeFormat("de-DE", {dateStyle:"medium", timeStyle:"short"}).format(instant)));
      const after = historyFacts(item.after); row.append(el("p", "history-facts", after.join(" · ") || "Änderung gespeichert."));
      const before = historyFacts(item.before); if (before.length) { const details = el("details"); details.append(el("summary", "", "Vorherigen Stand anzeigen"), el("p", "history-facts", before.join(" · "))); row.append(details); }
      $("history-events").append(row);
    }
    $("history-message").textContent = result.events.length ? "" : "Noch keine Änderungen erfasst.";
  } catch (_) { if (state.selected === id) $("history-message").textContent = "Der Verlauf konnte nicht geladen werden. Bitte versuche es erneut."; }
}
async function initialize() {
  try {
    const capabilities = await getJson("/garage-api/capabilities");
    const required = ["vehicles", "status", "odometer", "records", "history"];
    if (capabilities.backend !== "standalone" || !Array.isArray(capabilities.features) || !required.every(feature => capabilities.features.includes(feature))) throw new Error("invalid capabilities");
    state.standalone = true;
    state.recordCorrections = capabilities.features.includes("recordCorrections");
  } catch (error) { if (error.status !== 404) { setStatus("status", "Die Fahrzeuge konnten nicht geladen werden. Bitte versuche es erneut.", true); return; } }
  state.capabilitiesReady = true;
  $("legacy-manage").hidden = state.standalone; $("legacy-banner").hidden = state.standalone;
  $("own-toolbar").hidden = !state.standalone; $("own-detail-actions").hidden = !state.standalone;
  $("reminders-panel").hidden = state.standalone; $("detail-content").classList.toggle("standalone-detail", state.standalone);
  await load();
}
$("vehicle-add").addEventListener("click", () => openEntry("vehicle-new"));
$("vehicle-edit").addEventListener("click", () => openEntry("vehicle-edit"));
$("odometer-add").addEventListener("click", () => openEntry("odometer"));
$("record-add").addEventListener("click", () => openEntry("record"));
$("history-toggle").addEventListener("click", showHistory);
$("own-cancel").addEventListener("click", () => closeEntry(true));
$("own-form").addEventListener("submit", saveEntry);
initialize();
