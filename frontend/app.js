"use strict";

// Both backends use this presentation contract. Never insert API strings as HTML.
const $ = (id) => document.getElementById(id);
const state = { vehicles: [], selected: null, generation: 0, loadGeneration: 0, loading: false, detailLoading: false, inspectionRefreshInFlight: false, issueRowCounter: 0, editingRevision: null, saving: false, standalone: false, recordCorrections: false, historyBrowsing: false, scheduledWork: false, dataExport: false, inspectionStatus: false, capabilitiesReady: false, entry: null, work: {generation:0, items:null, today:null, timeZone:null, status:"idle"}, issueFilter:"all", logbook: {open:false, generation:0, cursor:null, filter:null, type:"records", records:[]} };
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
const severityLabels = {observation:"Auffälligkeit", repair:"Reparaturbedürftig", critical:"Kritisch"};
const lifecycleLabels = {open:"Offen", observed:"Beobachten"};
const dueStateLabels = {overdue:"Überfällig", today:"Heute fällig", upcoming:"Noch nicht fällig", unscheduled:"Ohne Fälligkeitsdatum"};
const inspectionStateLabels = {unknown:"HU / TÜV nicht erfasst", upcoming:"HU / TÜV fällig in", due:"HU / TÜV diesen Monat fällig", overdue:"HU / TÜV überfällig", blocking:"INOP: HU / TÜV überfällig"};
function validIsoDate(value) { if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false; const date = new Date(`${value}T00:00:00Z`); return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value; }
function validInspectionMonth(value) { if (typeof value !== "string" || !/^(\d{4})-(0[1-9]|1[0-2])$/.test(value)) return false; const year = Number(value.slice(0, 4)); return year >= 1 && year <= 9998; }
function validInspection(vehicle) {
  const inspection = vehicle && vehicle.inspection;
  if (!inspection || !validIsoDate(inspection.asOf) || inspection.timeZone !== "Europe/Berlin" || inspection.scaleMonths !== 12) return false;
  if (!(inspection.dueMonth === null || validInspectionMonth(inspection.dueMonth)) || inspection.dueMonth !== (vehicle.inspectionDueMonth ?? null)) return false;
  if (!(inspection.validUntil === null || validIsoDate(inspection.validUntil)) || !(inspection.blockingFrom === null || validIsoDate(inspection.blockingFrom))) return false;
  if (!(inspection.monthsUntilDue === null || Number.isInteger(inspection.monthsUntilDue)) || !(inspection.batteryLevel === null || Number.isInteger(inspection.batteryLevel) && inspection.batteryLevel >= 0 && inspection.batteryLevel <= 12)) return false;
  if (!Object.hasOwn(inspectionStateLabels, inspection.state) || typeof inspection.blocksReadiness !== "boolean") return false;
  if ((inspection.state === "unknown") !== (inspection.dueMonth === null) || (inspection.state === "blocking") !== inspection.blocksReadiness) return false;
  if (inspection.state === "unknown") return inspection.monthsUntilDue === null && inspection.batteryLevel === null && inspection.validUntil === null && inspection.blockingFrom === null;
  if (inspection.monthsUntilDue === null || inspection.batteryLevel === null || !inspection.validUntil || !inspection.blockingFrom) return false;
  return true;
}
function effectiveReadiness(vehicle) {
  if (!validCondition(vehicle && vehicle.status)) return "unavailable";
  if (!state.inspectionStatus) return vehicle.status.readiness;
  if (!validInspection(vehicle) || !Object.hasOwn(readinessLabels, vehicle.effectiveReadiness)) return "unavailable";
  if (vehicle.inspection.blocksReadiness && vehicle.effectiveReadiness !== "not_ready") return "unavailable";
  return vehicle.effectiveReadiness;
}
function inspectionMonthLabel(value) { if (!validInspectionMonth(value)) return ""; const names = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]; return `${names[Number(value.slice(5, 7)) - 1]} ${value.slice(0, 4)}`; }
function inspectionSummary(vehicle) {
  if (!state.inspectionStatus) return "";
  if (!validInspection(vehicle)) return "HU / TÜV Status nicht verfügbar";
  const value = vehicle.inspection;
  if (value.state === "unknown") return "HU / TÜV nicht erfasst";
  const month = inspectionMonthLabel(value.dueMonth);
  if (value.state === "upcoming") return `HU / TÜV ${month}, noch ${value.monthsUntilDue} ${value.monthsUntilDue === 1 ? "Monat" : "Monate"}; gültig bis ${readableDate(value.validUntil)}`;
  if (value.state === "due") return `HU / TÜV ${month}, diesen Monat fällig; gültig bis ${readableDate(value.validUntil)}`;
  return `HU / TÜV ${month}, überfällig; automatisch INOP ab ${readableDate(value.blockingFrom)}`;
}
function validWorkItem(item) { return item && (typeof item.vehicleId === "number" || typeof item.vehicleId === "string") && item.id !== null && item.id !== undefined && typeof item.text === "string" && (item.dueDate === null || validIsoDate(item.dueDate)) && (item.severity === null || Object.hasOwn(severityLabels, item.severity)) && Object.hasOwn(lifecycleLabels, item.lifecycle) && Object.hasOwn(dueStateLabels, item.dueState); }
function validCondition(condition) { return condition && Object.hasOwn(readinessLabels, condition.readiness) && Array.isArray(condition.issues) && Number.isInteger(condition.revision) && condition.revision >= 0; }
function conditionBadge(condition, readiness = validCondition(condition) ? condition.readiness : "unavailable") { const known = validCondition(condition) && Object.hasOwn(readinessLabels, readiness); const badge = el("span", `readiness-badge ${known ? readiness : "unavailable"}`, known ? readinessLabels[readiness] : "Status nicht verfügbar"); const dot = el("span", "readiness-dot"); dot.setAttribute("aria-hidden", "true"); badge.prepend(dot); return badge; }
function conditionIssueText(condition) { return validCondition(condition) ? condition.issues.filter(item => item && display(item.text)).map(item => display(item.text)) : []; }
function conditionIssueItems(condition) { return validCondition(condition) ? condition.issues.filter(item => item && display(item.text)) : []; }
function normalizedIssueField(issue, key) { if (key === "lifecycle") return issue.lifecycle || "open"; return issue[key] || null; }
function workItemMatchesIssue(item, vehicleId, issue) {
  if (!item || String(item.vehicleId) !== String(vehicleId) || String(item.id) !== String(issue.id) || display(item.text) !== display(issue.text)) return false;
  return ["dueDate", "severity", "lifecycle"].every(key => normalizedIssueField(item, key) === normalizedIssueField(issue, key));
}
function currentWorkProjection(vehicleId, issue) {
  if (!state.scheduledWork || state.work.status !== "ready" || !Array.isArray(state.work.items)) return null;
  const projection = state.work.items.find(item => String(item.vehicleId) === String(vehicleId) && String(item.id) === String(issue.id));
  return projection && workItemMatchesIssue(projection, vehicleId, issue) ? projection : null;
}
function issueSeverityText(issue) { return issue.severity ? severityLabels[issue.severity] || display(issue.severity) : "Nicht eingestuft"; }
function issueLifecycleText(issue) { return lifecycleLabels[issue.lifecycle || "open"] || display(issue.lifecycle); }
function issueReason(issue, vehicleId) {
  const projection = currentWorkProjection(vehicleId, issue);
  return [issue.severity === "critical" ? "Kritisch" : "", projection && dueStateLabels[projection.dueState] || "", issue.dueDate ? `fällig ${readableDate(issue.dueDate)}` : ""].filter(Boolean).join(", ");
}
function inspectionVisualLevel(vehicle) {
  if (!state.inspectionStatus || !validInspection(vehicle) || vehicle.inspection.monthsUntilDue === null) return null;
  return Math.max(0, Math.min(24, vehicle.inspection.monthsUntilDue));
}
function inspectionBarCells(level, className) {
  return Array.from({length:24}, (_, index) => {
    const cell = el("span", `${className}-cell${level !== null && index >= 24 - level ? " filled" : ""}`);
    cell.setAttribute("aria-hidden", "true"); return cell;
  });
}
function cardInspectionProgress(vehicle) {
  const valid = validInspection(vehicle), value = valid ? vehicle.inspection : null;
  let level = inspectionVisualLevel(vehicle), stateClass = level === null ? "unavailable" : `level-${level}`, marker = "";
  if (!valid) { level = 24; stateClass = "unavailable"; marker = "!"; }
  else if (value.state === "unknown") { level = 24; stateClass = "unknown"; marker = "?"; }
  else if (value.state === "overdue" || value.state === "blocking") { level = 24; stateClass = "expired"; marker = "!"; }
  else if (value.state === "due") { level = 24; stateClass = "due"; }
  const bar = el("span", `card-inspection-progress ${stateClass}`);
  bar.setAttribute("title", inspectionSummary(vehicle)); bar.setAttribute("aria-hidden", "true");
  const cells = inspectionBarCells(level, "card-inspection");
  if (marker) { const badge = el("span", "card-inspection-marker", marker); badge.setAttribute("aria-hidden", "true"); cells.push(badge); }
  bar.replaceChildren(...cells); return bar;
}
// These indicators share the existing header row; the detailed state remains in the accessible card name and detail panel.
function cardIndicators(condition, issues, vehicleId, vehicle) {
  const group = el("span", "card-indicators"); group.setAttribute("aria-hidden", "true");
  const readiness = effectiveReadiness(vehicle);
  const symbols = {not_ready: "INOP", unknown: "?", unavailable: "!"};
  const label = Object.hasOwn(readinessLabels, readiness) ? readinessLabels[readiness] : "Status nicht verfügbar";
  if (symbols[readiness]) { const indicator = el("span", `card-readiness ${readiness}`, symbols[readiness]); indicator.setAttribute("title", label); group.append(indicator); }
  if (validCondition(condition) && issues.length) { const warning = el("span", "card-work"); const reasons = issues.slice(0, 2).map(issue => `${display(issue.text)}${issueReason(issue, vehicleId) ? ` (${issueReason(issue, vehicleId)})` : ""}`); warning.setAttribute("title", state.scheduledWork && reasons.length ? `Offene Arbeit: ${reasons.join("; ")}` : "Wartung ausstehend"); warning.append(icon("tool")); group.append(warning); }
  return group;
}

function renderCards() {
  const container = $("vehicles"); container.replaceChildren();
  for (const vehicle of state.vehicles) {
    const id = String(vehicle.id); const button = el("button", "vehicle-card"); button.type = "button"; button.setAttribute("aria-pressed", String(state.selected === id));
    const type = display(vehicle.vehicleType); const condition = vehicle.status; const issues = conditionIssueItems(condition); const accessible = [vehicleName(vehicle), type && `Fahrzeugtyp ${type}`, display(vehicle.licensePlate) && `Kennzeichen ${display(vehicle.licensePlate)}`, display(vehicle.year), readinessLabels[effectiveReadiness(vehicle)] || "Status nicht verfügbar", inspectionSummary(vehicle), ...issues.map(item => `Offen: ${display(item.text)}${state.scheduledWork && issueReason(item, id) ? `, ${issueReason(item, id)}` : ""}`)].filter(Boolean).join(", "); button.setAttribute("aria-label", accessible);
    const top = el("div", "card-top"); const badge = el("span", "car-icon"); badge.append(icon(vehicleIcon(vehicle.vehicleType))); const arrow = el("span", "card-arrow"); arrow.append(icon("arrow")); top.append(badge, cardIndicators(condition, issues, id, vehicle));
    const make = manufacturerMark(vehicle.make); top.append(arrow);
    const name = el("h3", "", vehicleName(vehicle)); const meta = el("div", "vehicle-meta");
    const plate = display(vehicle.licensePlate); if (plate) { const label = el("span", "license-plate", plate); label.setAttribute("role", "img"); label.setAttribute("aria-label", `Kennzeichen ${plate}`); meta.append(label); }
    const year = display(vehicle.year); if (year) meta.append(el("span", "vehicle-year", year));
    button.append(top, name); if (plate || year) button.append(meta);
    const mileage = distance(vehicle.odometer, vehicle.odometerUnit); if (mileage) button.append(el("p", "mileage", mileage));
    if (make) button.append(make);
    if (state.inspectionStatus) button.append(cardInspectionProgress(vehicle));
    button.addEventListener("click", () => selectVehicle(id)); container.append(button);
  }
}
function closeConditionEditor(restoreFocus = false) { $("condition-form").hidden = true; $("condition-view").hidden = false; $("condition-edit").setAttribute("aria-expanded", "false"); $("condition-message").textContent = ""; state.editingRevision = null; if (restoreFocus) $("condition-edit").focus(); }
function conditionIssueRow(issue, vehicleId) {
  const row = el("div", "condition-issue-row"); row.append(el("p", "condition-issue-text", display(issue.text)));
  const projection = currentWorkProjection(vehicleId, issue);
  const facts = [`Schweregrad: ${issueSeverityText(issue)}`, `Status: ${issueLifecycleText(issue)}`];
  if (issue.dueDate) facts.push(`Fällig am ${readableDate(issue.dueDate)}`);
  if (projection && dueStateLabels[projection.dueState]) facts.push(dueStateLabels[projection.dueState]);
  row.append(el("p", "condition-issue-meta", facts.join(" · "))); return row;
}
function renderInspection(vehicle) {
  const panel = $("inspection-panel"); panel.hidden = !state.inspectionStatus;
  if (!state.inspectionStatus) return;
  const message = $("inspection-message"), asOf = $("inspection-asof"), meterWrap = $("inspection-meter-wrap"), meter = $("inspection-meter");
  if (!validInspection(vehicle)) { message.className = "inspection-message"; message.textContent = "HU-Status momentan nicht verfügbar."; asOf.textContent = ""; meterWrap.hidden = true; meter.replaceChildren(); return; }
  const value = vehicle.inspection; message.className = `inspection-message state-${value.state}`; message.textContent = inspectionSummary(vehicle);
  asOf.textContent = `Stand: ${readableDate(value.asOf)} (Europe/Berlin).`;
  meterWrap.hidden = false;
  const level = inspectionVisualLevel(vehicle);
  meter.className = `inspection-meter ${level === null ? "unknown" : `level-${level}`}`;
  meter.setAttribute("role", "img");
  meter.setAttribute("aria-label", level === null ? "HU-Vorlauf unbekannt; Darstellung neutral." : `HU-Vorlauf: ${value.monthsUntilDue} Monate; visuelle Darstellung auf 24 Monate begrenzt.`);
  meter.replaceChildren(...inspectionBarCells(level, "inspection-meter"));
}
function renderCondition(condition) {
  const vehicle = selectedVehicle();
  $("condition-readiness").replaceChildren(conditionBadge(condition, effectiveReadiness(vehicle)));
  renderInspection(vehicle);
  $("condition-work-asof").hidden = !state.scheduledWork;
  if (state.scheduledWork) $("condition-work-asof").textContent = state.work.status === "ready" ? `Fälligkeitsstand: ${readableDate(state.work.today)} (${display(state.work.timeZone)}).` : state.work.status === "error" ? "Fälligkeitsstatus momentan nicht verfügbar." : "Fälligkeitsstatus wird geladen …";
  const issues = conditionIssueItems(condition); const list = $("condition-issues"); list.replaceChildren();
  $("issue-filter-wrap").hidden = !state.scheduledWork || (issues.length < 2 && state.issueFilter === "all");
  if (validCondition(condition)) {
    if (!issues.length) list.append(el("p", "condition-empty", "Keine offenen Punkte hinterlegt."));
    else if (state.scheduledWork) {
      const needsProjection = state.issueFilter === "overdue" || state.issueFilter === "today";
      const projectionIncomplete = needsProjection && (state.work.status !== "ready" || issues.some(issue => !currentWorkProjection(state.selected, issue)));
      if (projectionIncomplete) { list.append(el("p", "condition-empty", state.work.status === "loading" ? "Fälligkeitsstatus wird geladen …" : "Fälligkeitsstatus momentan nicht verfügbar.")); for (const issue of issues) list.append(conditionIssueRow(issue, state.selected)); }
      else {
      const visible = issues.filter(issue => issueMatchesFilter(issue, state.selected));
      if (state.work.status === "ready" && Array.isArray(state.work.items)) {
        const rank = new Map(state.work.items.filter(item => String(item.vehicleId) === String(state.selected)).map((item, index) => [String(item.id), index]));
        visible.sort((left, right) => (rank.get(String(left.id)) ?? Number.MAX_SAFE_INTEGER) - (rank.get(String(right.id)) ?? Number.MAX_SAFE_INTEGER));
      }
      if (!visible.length) list.append(el("p", "condition-empty", "Keine offenen Punkte für diesen Filter."));
      else for (const issue of visible) list.append(conditionIssueRow(issue, state.selected));
      }
    } else {
      const heading=el("p", "condition-issues-title", "Offene Punkte"); const ul=el("ul", "condition-issue-list"); for (const item of issues) ul.append(el("li", "", display(item.text))); list.append(heading, ul);
    }
  } else list.append(el("p", "condition-empty", "Der aktuelle Zustand ist momentan nicht verfügbar."));
  $("condition-edit").disabled = !validCondition(condition) || state.saving;
}
function issueMatchesFilter(issue, vehicleId) {
  switch (state.issueFilter) {
    case "overdue": return currentWorkProjection(vehicleId, issue)?.dueState === "overdue";
    case "today": return currentWorkProjection(vehicleId, issue)?.dueState === "today";
    case "critical": return issue.severity === "critical";
    case "observed": return (issue.lifecycle || "open") === "observed";
    default: return true;
  }
}
function appendIssueEditor(issue = {}) {
  const editor = $("issue-editor"); if (editor.children.length >= 20) return;
  const row = el("div", "issue-row"); const rowId = ++state.issueRowCounter;
  const field = (labelText, name, type, value, options = null) => {
    const wrapper = el("div", `own-field issue-field issue-field-${name}`); const label = el("label", "", labelText); const control = el(options ? "select" : "input");
    control.id = `issue-${rowId}-${name}`; label.setAttribute("for", control.id);
    if (options) for (const [optionValue, optionText] of options) { const option = el("option", "", optionText); option.value = optionValue; control.append(option); }
    else control.type = type;
    control.value = value === null || value === undefined ? "" : String(value); wrapper.append(label, control); row.append(wrapper); return control;
  };
  const input = field("Beschreibung", "text", "text", issue.text); input.className = "issue-input"; input.maxLength = 160; input.required = true; input.placeholder = "Was ist noch zu tun?"; input._issueId = issue.id; input.setAttribute("aria-label", "Beschreibung des offenen Punkts");
  if (state.scheduledWork) {
    field("Fällig am (optional)", "due-date", "date", issue.dueDate);
    field("Schweregrad", "severity", "", issue.severity || "", [["", "Nicht eingestuft"], ["observation", "Auffälligkeit"], ["repair", "Reparaturbedürftig"], ["critical", "Kritisch"]]);
    field("Status", "lifecycle", "", issue.lifecycle || "open", [["open", "Offen"], ["observed", "Beobachten"]]);
  }
  const remove = el("button", "issue-remove", "Punkt entfernen"); remove.type = "button"; remove.setAttribute("aria-label", "Diesen offenen Punkt entfernen"); remove.addEventListener("click", () => { row.remove(); $("issue-add").disabled = editor.children.length >= 20; });
  row.append(remove); editor.append(row); $("issue-add").disabled = editor.children.length >= 20;
}
function openConditionEditor() {
  if (state.entry && state.entry.busy) return;
  if (state.entry) closeEntry();
  const vehicle = state.vehicles.find(v => String(v.id) === state.selected); const condition = vehicle && vehicle.status;
  if (!validCondition(condition) || state.saving) return;
  state.editingRevision = condition.revision; $("readiness-input").value = condition.readiness; $("issue-editor").replaceChildren();
  for (const item of condition.issues) if (item && display(item.text)) appendIssueEditor(item);
  $("issue-add").disabled = $("issue-editor").children.length >= 20;
  $("condition-view").hidden = true; $("condition-form").hidden = false; $("condition-edit").setAttribute("aria-expanded", "true"); $("condition-message").textContent = ""; $("readiness-input").focus();
}
async function saveCondition(event) {
  event.preventDefault(); if (state.saving || state.selected === null || state.editingRevision === null) return;
  const id = state.selected; const rows = Array.from($("issue-editor").children);
  const issues = rows.map(row => { const input = row.querySelectorAll("input")[0]; const item = {text: input.value.trim()}; if (input._issueId !== undefined && input._issueId !== null) item.id = input._issueId; if (state.scheduledWork) { const fields = row.querySelectorAll("select"); const date = row.querySelectorAll("input")[1].value; item.dueDate = date || null; item.severity = fields[0].value || null; item.lifecycle = fields[1].value || "open"; } return item; });
  if (issues.some(item => !item.text || item.text.length > 160 || /[\x00-\x1f\x7f]/.test(item.text))) { $("condition-message").textContent = "Bitte gib für jeden offenen Punkt eine Beschreibung mit höchstens 160 Zeichen ein."; return; }
  state.saving = true; $("condition-save").disabled = true; $("condition-cancel").disabled = true; $("condition-message").textContent = "Wird gespeichert …";
  try {
    const response = await fetch(`/garage-api/vehicles/${encodeURIComponent(id)}/status`, {method:"PUT", credentials:"same-origin", headers:{"Content-Type":"application/json", "X-Garage-Request":"1"}, body:JSON.stringify({readiness:$("readiness-input").value, issues, revision:state.editingRevision})});
    if (!response.ok) { if (response.status === 409) throw new Error("Dieser Zustand wurde inzwischen geändert. Bitte aktualisiere die Übersicht und versuche es erneut."); if (response.status === 503) throw new Error("Der Zustandsspeicher ist momentan nicht verfügbar. Bitte versuche es später erneut."); throw new Error("Der Zustand konnte nicht gespeichert werden. Bitte versuche es erneut."); }
    const updated = await response.json(); if (!validCondition(updated)) throw new Error("Der gespeicherte Zustand konnte nicht gelesen werden. Bitte aktualisiere die Übersicht.");
    const vehicle = state.vehicles.find(v => String(v.id) === id); if (vehicle) { vehicle.status = updated; if (state.inspectionStatus) { vehicle.inspection = null; vehicle.effectiveReadiness = null; } }
    renderCards(); if (state.selected === id) { closeConditionEditor(true); renderCondition(updated); }
    if (state.inspectionStatus && state.selected === id) {
      try { await refreshVehicleSummaryProjection(id); if (state.selected === id) setStatus("detail-status", ""); }
      catch (_) { if (state.selected === id) setStatus("detail-status", "HU-Status momentan nicht verfügbar. Bitte aktualisiere die Übersicht.", true); }
    }
    await refreshWork();
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
    if (kind === "services" && state.recordCorrections && item.id !== null && item.id !== undefined) { const edit = el("button", "condition-edit record-edit"); edit.type = "button"; edit.textContent = "Beleg korrigieren"; edit.id = `record-edit-${String(item.id)}`; edit.setAttribute("aria-label", `Beleg korrigieren: ${title}`); edit.addEventListener("click", () => openRecordCorrection(item.id, edit.id)); row.append(edit); }
    container.append(row);
  }
}
function renderWorkDashboard() {
  $("work-dashboard").hidden = !state.scheduledWork;
  const container = $("work-items"); container.replaceChildren();
  if (!state.scheduledWork) return;
  if (state.work.status === "error") { setStatus("work-status", "Fälligkeiten momentan nicht verfügbar.", true); return; }
  if (state.work.status !== "ready") { setStatus("work-status", "Fälligkeiten werden geladen …"); return; }
  setStatus("work-status", `Stand: ${readableDate(state.work.today)} (${display(state.work.timeZone)}).`);
  if (!state.work.items.length) { container.append(el("p", "condition-empty", "Keine offenen Punkte erfasst.")); return; }
  for (const item of state.work.items) {
    const row = el("article", "work-item"); const vehicle = state.vehicles.find(candidate => String(candidate.id) === String(item.vehicleId));
    row.append(el("h3", "work-item-vehicle", vehicle ? vehicleName(vehicle) : "Fahrzeug"));
    row.append(el("p", "work-item-text", display(item.text)));
    const facts = [`Schweregrad: ${item.severity ? severityLabels[item.severity] || display(item.severity) : "Nicht eingestuft"}`, `Status: ${lifecycleLabels[item.lifecycle] || display(item.lifecycle)}`, dueStateLabels[item.dueState] || "Fälligkeitsstatus nicht verfügbar"];
    if (item.dueDate) facts.push(`Fällig am ${readableDate(item.dueDate)}`);
    row.append(el("p", "work-item-meta", facts.join(" · "))); container.append(row);
  }
}
async function refreshWork() {
  if (!state.standalone || !state.scheduledWork) return;
  const generation = ++state.work.generation; const loadGeneration = state.loadGeneration;
  state.work.items = null; state.work.today = null; state.work.timeZone = null; state.work.status = "loading";
  renderCards(); renderWorkDashboard();
  const vehicle = selectedVehicle(); if (vehicle && $("condition-form").hidden) renderCondition(vehicle.status);
  try {
    const result = await getJson("/garage-api/work");
    if (generation !== state.work.generation || loadGeneration !== state.loadGeneration) return;
    if (!result || !validIsoDate(result.today) || result.timeZone !== "Europe/Berlin" || !Array.isArray(result.items) || !result.items.every(validWorkItem)) throw new Error("invalid work projection");
    const expected = state.vehicles.flatMap(vehicle => conditionIssueItems(vehicle.status).map(issue => ({vehicleId:vehicle.id, issue})));
    if (expected.length !== result.items.length || expected.some(({vehicleId, issue}) => result.items.filter(item => String(item.vehicleId) === String(vehicleId) && String(item.id) === String(issue.id)).length !== 1 || !result.items.some(item => workItemMatchesIssue(item, vehicleId, issue)))) throw new Error("work projection does not match current status");
    state.work.items = result.items; state.work.today = result.today; state.work.timeZone = result.timeZone; state.work.status = "ready";
  } catch (_) {
    if (generation !== state.work.generation || loadGeneration !== state.loadGeneration) return;
    state.work.items = null; state.work.status = "error";
  }
  renderCards(); renderWorkDashboard();
  const selected = selectedVehicle(); if (selected && $("condition-form").hidden) renderCondition(selected.status);
}
function invalidateWork() {
  if (!state.scheduledWork) return;
  state.work.generation++; state.work.items = null; state.work.today = null; state.work.timeZone = null; state.work.status = "loading";
  renderCards(); renderWorkDashboard();
  const vehicle = selectedVehicle(); if (vehicle && $("condition-form").hidden) renderCondition(vehicle.status);
}
function mergeSummaryVehicle(vehicle, projected) {
  if (!projected || String(projected.id) !== String(vehicle.id) || !validCondition(projected.status)) return false;
  vehicle.status = projected.status;
  if (Number.isInteger(projected.revision)) vehicle.revision = projected.revision;
  if (state.inspectionStatus) {
    vehicle.inspectionDueMonth = projected.inspectionDueMonth ?? null;
    vehicle.inspection = projected.inspection;
    vehicle.effectiveReadiness = projected.effectiveReadiness;
  }
  return true;
}
async function refreshVehicleSummaryProjection(id) {
  const generation = state.generation;
  const result = await getJson(`/garage-api/vehicles/${encodeURIComponent(id)}/summary`);
  if (generation !== state.generation || state.selected !== id) return false;
  const vehicle = state.vehicles.find(candidate => String(candidate.id) === id);
  if (!vehicle || !mergeSummaryVehicle(vehicle, result.vehicle)) throw new Error("Der Fahrzeugstatus konnte nicht aktualisiert werden.");
  renderCards(); if ($("condition-form").hidden) renderCondition(vehicle.status);
  return true;
}
async function selectVehicle(id, refreshProjection = true) {
  if (state.entry && state.entry.busy) return;
  if (state.entry) closeEntry();
  $("history-panel").hidden = true; $("history-toggle").setAttribute("aria-expanded", "false"); closeLogbook(false);
  state.issueFilter = "all"; $("issue-filter").value = "all";
  state.selected = id; renderCards(); const vehicle = state.vehicles.find((v) => String(v.id) === id); if (!vehicle) return;
  closeConditionEditor(); renderCondition(vehicle.status);
  $("detail").hidden = false; $("detail-heading").textContent = vehicleName(vehicle); $("detail-meta").textContent = vehicleSubtitle(vehicle); $("detail-content").hidden = true; setStatus("detail-status", "Fahrzeugdaten werden geladen …");
  const generation = ++state.generation; state.detailLoading = true;
  try { const result = await getJson(`/garage-api/vehicles/${encodeURIComponent(id)}/summary`); if (generation !== state.generation) return; if (mergeSummaryVehicle(vehicle, result.vehicle)) { if ($("condition-form").hidden) renderCondition(vehicle.status); renderCards(); } renderRecords("reminders", result.reminders, "reminders"); renderRecords("services", result.services, "services"); setStatus("detail-status", ""); $("detail-content").hidden = false; }
  catch (error) { if (generation === state.generation) setStatus("detail-status", error.status === 503 ? "Der Zustandsspeicher ist momentan nicht verfügbar. Bitte versuche es später erneut." : "Die Fahrzeugdaten konnten nicht geladen werden. Bitte versuche es erneut.", true); }
  finally { if (generation === state.generation) state.detailLoading = false; }
  if (refreshProjection && generation === state.generation) await refreshWork();
}
async function load(preferredId = null) {
  const loadGeneration = ++state.loadGeneration; state.loading = true;
  $("refresh").disabled = true; setStatus("status", "Fahrzeuge werden geladen …"); $("vehicle-count").hidden = true; $("detail").hidden = true; $("detail-content").hidden = true; state.selected = null; state.vehicles = []; ++state.generation; $("vehicles").replaceChildren(); invalidateWork();
  try { const result = await getJson("/garage-api/vehicles"); if (loadGeneration !== state.loadGeneration) return; if (!Array.isArray(result.vehicles)) throw new Error("invalid vehicles"); state.vehicles = result.vehicles.filter((v) => v && v.id !== null && v.id !== undefined); $("vehicle-count").textContent = state.vehicles.length; $("vehicle-count").hidden = false;
    if (!state.vehicles.length) { const status = $("status"); status.replaceChildren(document.createTextNode("Deine Garage ist noch leer. ")); if (state.standalone) { const button = el("button", "condition-edit", "Erstes Fahrzeug anlegen"); button.type = "button"; button.addEventListener("click", () => openEntry("vehicle-new")); status.append(button); } else { const link = el("a", "", "Erstes Fahrzeug in LubeLogger anlegen"); link.href = "/Home"; status.append(link); } await refreshWork(); return; }
    setStatus("status", ""); renderCards(); const selected = state.vehicles.find(v => String(v.id) === String(preferredId)) || state.vehicles[0]; await selectVehicle(String(selected.id), false); if (loadGeneration === state.loadGeneration) await refreshWork();
  } catch (error) { if (loadGeneration === state.loadGeneration) { setStatus("status", error.status === 503 ? "Der Zustandsspeicher ist momentan nicht verfügbar. Bitte versuche es später erneut." : "Die Fahrzeuge konnten nicht geladen werden. Bitte versuche es erneut.", true); if (state.scheduledWork) { state.work.status = "error"; state.work.items = null; renderWorkDashboard(); } } }
  finally { if (loadGeneration === state.loadGeneration) { state.loading = false; $("refresh").disabled = false; } }
}
async function refreshInspectionVehicles() {
  if (!state.inspectionStatus || document.visibilityState !== "visible" || state.loading || state.detailLoading || state.saving || state.entry || !$("condition-form").hidden || state.inspectionRefreshInFlight) return false;
  const loadGeneration = state.loadGeneration, generation = state.generation, selected = state.selected;
  state.inspectionRefreshInFlight = true;
  try {
    const result = await getJson("/garage-api/vehicles");
    if (loadGeneration !== state.loadGeneration || generation !== state.generation || selected !== state.selected || state.loading || state.saving || state.entry || !$("condition-form").hidden) return false;
    if (!Array.isArray(result.vehicles)) throw new Error("invalid vehicles");
    const vehicles = result.vehicles.filter(vehicle => vehicle && vehicle.id !== null && vehicle.id !== undefined);
    if (selected !== null && !vehicles.some(vehicle => String(vehicle.id) === selected)) return false;
    state.vehicles = vehicles;
    $("vehicle-count").textContent = vehicles.length; $("vehicle-count").hidden = false;
    renderCards();
    const vehicle = selectedVehicle();
    if (vehicle) renderCondition(vehicle.status);
    if (state.scheduledWork) await refreshWork();
    if (selected !== null && loadGeneration === state.loadGeneration && generation === state.generation && selected === state.selected) setStatus("detail-status", "");
    return true;
  } catch (_) {
    if (loadGeneration === state.loadGeneration && generation === state.generation && selected === state.selected && selected !== null) setStatus("detail-status", "HU-Status momentan nicht verfügbar. Bitte aktualisiere die Übersicht.", true);
    return false;
  } finally { state.inspectionRefreshInFlight = false; }
}
$("refresh").addEventListener("click", () => state.capabilitiesReady ? load(state.selected) : initialize());
$("condition-edit").addEventListener("click", openConditionEditor);
$("condition-cancel").addEventListener("click", () => closeConditionEditor(true));
$("issue-add").addEventListener("click", () => appendIssueEditor());
$("issue-filter").addEventListener("change", () => { state.issueFilter = $("issue-filter").value; const vehicle = selectedVehicle(); if (vehicle) renderCondition(vehicle.status); });
$("condition-form").addEventListener("submit", saveCondition);

function selectedVehicle() { return state.vehicles.find(v => String(v.id) === state.selected); }
function localToday() { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`; }
function entryField(labelText, name, type, value = "", options = null) {
  const wrapper = el("div", "own-field"); const label = el("label", "", labelText); const field = el(options ? "select" : "input");
  field.id = `entry-${name}`; label.setAttribute("for", field.id); field.name = name;
  if (options) { for (const [key, text] of options) { const option = el("option", "", text); option.value = key; field.append(option); } }
  else field.type = type;
  field.value = value === null || value === undefined ? "" : String(value);
  if (name === "inspectionDueMonth") {
    const labelRow = el("div", "own-field-label-row"), help = el("details", "inspection-help"), summary = el("summary", "", "i");
    summary.setAttribute("aria-label", "Information zum Ablesen des HU-Monats");
    const content = el("div", "inspection-help-content");
    content.append(el("p", "", "Auf dem hinteren Kennzeichen zeigt die Zahl ganz oben den Monat der nächsten HU. Die zweistellige Zahl in der Mitte ist das Jahr. Beispiel: oben 9 und Mitte 28 bedeutet September 2028. Alternativ findest du den Termin im letzten HU-Bericht."));
    const source = el("a", "", "Hinweise beim TÜV NORD"); source.href = "https://www.tuev-nord.de/de/dienstleistungen/pruefung-und-gutachten/hauptuntersuchung/"; source.target = "_blank"; source.rel = "noopener noreferrer";
    content.append(source); help.append(summary, content); labelRow.append(label, help); wrapper.append(labelRow, field);
  } else wrapper.append(label, field);
  $("own-fields").append(wrapper); return field;
}
function readonlyRecordFacts(record) {
  const date = readableDate(record.date) || "Datum nicht verfügbar";
  const reading = record.odometer === null || record.odometer === undefined || record.odometer === "" ? "Stand nicht erfasst" : `${number(record.odometer)} ${display(record.odometerUnit) || "Einheit unbekannt"}`;
  $("record-edit-readonly-date").textContent = `Datum: ${date}`;
  $("record-edit-readonly-odometer").textContent = `Stand: ${reading}`;
  $("record-edit-readonly-closed-issue").textContent = record.closedIssueId === null || record.closedIssueId === undefined || record.closedIssueId === "" ? "Kein Punkt wurde mit diesem Beleg abgeschlossen." : "Punktabschluss bei der Erfassung bleibt unverändert.";
}
async function openRecordCorrection(recordId, openerId = `record-edit-${String(recordId)}`) {
  if (!state.standalone || !state.recordCorrections || state.saving || state.entry && state.entry.busy) return;
  const vehicle = selectedVehicle(); if (!vehicle || recordId === null || recordId === undefined) return;
  if (!globalThis.crypto || typeof globalThis.crypto.randomUUID !== "function") { $("own-notice").textContent = "Zum Korrigieren benötigst du HTTPS oder einen lokalen Zugriff über localhost."; return; }
  if (state.entry) closeEntry();
  closeConditionEditor(); $("own-notice").textContent = ""; $("own-fields").replaceChildren(); $("own-message").textContent = "Beleg wird geladen …";
  $("own-title").textContent = "Belegkorrektur"; $("own-hint").textContent = "Datum und Kilometerstand bleiben unverändert. Eine Korrektur von Datum oder Stand ist in dieser Version noch nicht verfügbar.";
  $("record-edit-readonly").hidden = false; $("record-edit-readonly-date").textContent = "Datum wird geladen …"; $("record-edit-readonly-odometer").textContent = "Stand wird geladen …";
  $("record-edit-readonly-closed-issue").textContent = "Abgeschlossener Punkt wird geladen …"; $("own-save").disabled = true; $("own-cancel").disabled = true;
  $("own-panel").hidden = false;
  const entry = {mode:"record-edit", vehicleId:String(vehicle.id), recordId:String(recordId), opener:openerId, fromLogbook:openerId.startsWith("log-record-edit-"), busy:true, commandId:globalThis.crypto.randomUUID()}; state.entry = entry;
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
  const entry = state.entry; const opener = entry && $(entry.opener); state.entry = null; $("own-panel").hidden = true; $("own-message").textContent = ""; $("record-edit-readonly").hidden = true;
  if (restoreFocus) { if (opener) opener.focus(); else if (entry && entry.fromLogbook) $("logbook-title").focus(); else $("record-add").focus(); }
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
    if (state.inspectionStatus) { const inspection = entryField("HU / TÜV gültig bis", "inspectionDueMonth", "month", values.inspectionDueMonth || ""); inspection.min = "0001-01"; inspection.max = "9998-12"; }
    $("own-hint").textContent = state.inspectionStatus ? "Der HU-Monat steuert die automatische INOP-Regel. Deine manuelle Einschätzung bleibt erhalten." : "Die Fahrbereitschaft bleibt unabhängig von den Stammdaten. Eine Änderung der Einheit rechnet vorhandene Einträge nicht um.";
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
    if (state.inspectionStatus) payload.inspectionDueMonth = field("inspectionDueMonth") || null;
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
    entry.busy = false; closeEntry(); if (entry.mode === "record-edit" && entry.fromLogbook) { state.logbook.filter = readLogbookFilter(); state.logbook.records = []; state.logbook.cursor = null; }
    await load(id); $("own-notice").textContent = entry.mode === "record-edit" ? "Belegkorrektur gespeichert. Verlauf wurde aktualisiert." : "Gespeichert.";
    if (entry.mode === "record-edit") await showHistory(true);
    if (entry.mode === "record-edit" && entry.fromLogbook) { await openLogbook(true); const button = document.getElementById(`log-record-edit-${entry.recordId}`); if (button) button.focus(); else $("logbook-title").focus(); }
    else if (entry.mode === "record-edit") { const button = document.getElementById(entry.opener); if (button) button.focus(); }
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
  if (Array.isArray(value.issues)) facts.push(value.issues.length ? `Offen: ${value.issues.map(item => {
    const details = [display(item.text)];
    if (Object.hasOwn(item, "dueDate")) details.push(item.dueDate ? `Fälligkeit ${readableDate(item.dueDate)}` : "Keine Fälligkeit");
    if (Object.hasOwn(item, "severity")) details.push(`Schweregrad ${issueSeverityText(item)}`);
    if (Object.hasOwn(item, "lifecycle")) details.push(`Status ${issueLifecycleText(item)}`);
    return details.filter(Boolean).join(", ");
  }).join("; ")}` : "Keine offenen Punkte");
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
function readLogbookFilter() {
  return {type:$("logbook-type").value === "odometer" ? "odometer" : "records", from:$("logbook-from").value, to:$("logbook-to").value, kind:$("logbook-kind").value};
}
function closeLogbook(reset = true) {
  state.logbook.open = false; state.logbook.busy = false; state.logbook.needsReload = false; state.logbook.generation++;
  $("logbook-panel").hidden = true; $("logbook-toggle").setAttribute("aria-expanded", "false");
  if (reset) { state.logbook.cursor = null; state.logbook.records = []; }
}
function logbookDistance(value, unit) {
  const n = number(value); if (n === "") return "";
  const u = display(unit); return u ? `${n} ${u}` : `Stand ${n} (Einheit unbekannt)`;
}
function renderLogbookRows(type, rows) {
  const container = $("logbook-records"); container.replaceChildren();
  for (const item of rows) {
    const row = el("div", "logbook-row"); const main = el("div", "logbook-row-main");
    if (type === "odometer") {
      const value = item.odometer === null || item.odometer === undefined || item.odometer === "" ? "Kilometerstand nicht erfasst" : logbookDistance(item.odometer, item.unit);
      main.append(el("div", "logbook-row-title", value || "Kilometerstand nicht erfasst"));
      main.append(el("p", "logbook-row-meta", readableDate(item.date) || "Datum nicht verfügbar"));
      if (display(item.note)) main.append(el("p", "logbook-row-note", display(item.note)));
      row.append(main);
    } else {
      const title = display(item.description) || "Arbeit ohne Beschreibung";
      main.append(el("div", "logbook-row-title", title));
      const facts = [readableDate(item.date), logbookDistance(item.odometer, item.odometerUnit), cost(item.cost, item.currency)].filter(Boolean);
      main.append(el("p", "logbook-row-meta", facts.join(" · ") || "Keine weiteren Angaben"));
      if (item.documentUrl) { try { const url = new URL(item.documentUrl); if (url.protocol === "https:" && !url.username && !url.password) { const link = el("a", "record-document", "Beleg öffnen"); link.href = url.href; link.target = "_blank"; link.rel = "noopener noreferrer"; main.append(link); } } catch (_) { /* Invalid document URLs remain hidden. */ } }
      if (state.recordCorrections && item.id !== null && item.id !== undefined) {
        const edit = el("button", "condition-edit record-edit", "Beleg korrigieren"); edit.type = "button"; edit.id = `log-record-edit-${String(item.id)}`; edit.setAttribute("aria-label", `Beleg korrigieren: ${title}`); edit.addEventListener("click", () => openRecordCorrection(item.id, edit.id)); row.append(main, edit);
      } else row.append(main);
    }
    const kind = type === "records" ? item.kind === "repair" ? "Reparatur" : item.kind === "service" ? "Wartung" : display(item.kind) : "Kilometerstand";
    if (kind) row.append(el("span", "logbook-kind", kind));
    container.append(row);
  }
}
async function loadLogbookPage(append, generation) {
  const logbook = state.logbook; if (logbook.busy || !logbook.open || logbook.needsReload) return;
  const vehicleId = state.selected; const selectionGeneration = state.generation; const filter = logbook.filter;
  if (!vehicleId || !filter) return;
  logbook.busy = true; $("logbook-apply").disabled = true; $("logbook-more").disabled = true;
  if (!append) { $("logbook-records").replaceChildren(); setStatus("logbook-message", "Logbuch wird geladen …"); }
  else setStatus("logbook-message", "Weitere Einträge werden geladen …");
  const params = ["limit=25"];
  if (filter.from) params.push(`from=${encodeURIComponent(filter.from)}`);
  if (filter.to) params.push(`to=${encodeURIComponent(filter.to)}`);
  if (filter.type === "records" && filter.kind) params.push(`kind=${encodeURIComponent(filter.kind)}`);
  if (append && logbook.cursor) params.push(`cursor=${encodeURIComponent(logbook.cursor)}`);
  const path = `/garage-api/vehicles/${encodeURIComponent(vehicleId)}/${filter.type}/page?${params.join("&")}`;
  try {
    const result = await getJson(path);
    if (!logbook.open || generation !== logbook.generation || state.selected !== vehicleId || state.generation !== selectionGeneration) return;
    const rows = filter.type === "records" ? result.records : result.readings;
    if (!Array.isArray(rows) || !(result.nextCursor === null || typeof result.nextCursor === "string")) throw new Error("invalid page");
    logbook.records = append ? logbook.records.concat(rows) : rows.slice(); logbook.cursor = result.nextCursor;
    renderLogbookRows(filter.type, logbook.records);
    setStatus("logbook-message", logbook.records.length ? "" : filter.type === "records" ? "Keine erledigten Arbeiten für diese Filter." : "Keine Kilometerstände für diese Filter.");
    $("logbook-more").hidden = !logbook.cursor; $("logbook-more").disabled = !logbook.cursor;
  } catch (error) {
    if (!logbook.open || generation !== logbook.generation || state.selected !== vehicleId || state.generation !== selectionGeneration) return;
    if (append && error.status === 409) {
      logbook.cursor = null; logbook.needsReload = true; $("logbook-more").hidden = true;
      setStatus("logbook-message", "Das Fahrzeug wurde seit der letzten Seite geändert. Lade den Verlauf neu, um fortzufahren.", true); $("logbook-reload").hidden = false;
    } else {
      setStatus("logbook-message", append ? "Weitere Einträge konnten nicht geladen werden. Du kannst es erneut versuchen." : "Das Logbuch konnte nicht geladen werden. Filter erneut anwenden, um es erneut zu versuchen.", true);
      $("logbook-more").hidden = !logbook.cursor;
    }
  } finally {
    if (generation === logbook.generation) { logbook.busy = false; $("logbook-apply").disabled = false; $("logbook-more").disabled = !logbook.cursor || logbook.needsReload; }
  }
}
async function openLogbook(force = false) {
  if (!state.standalone || !state.historyBrowsing || !state.selected) return;
  if (state.logbook.open && !force) { closeLogbook(); return; }
  state.logbook.open = true; state.logbook.busy = false; state.logbook.needsReload = false;
  const generation = ++state.logbook.generation;
  $("logbook-panel").hidden = false; $("logbook-toggle").setAttribute("aria-expanded", "true");
  if (!state.logbook.filter || force) state.logbook.filter = readLogbookFilter();
  $("logbook-type").value = state.logbook.filter.type; $("logbook-from").value = state.logbook.filter.from; $("logbook-to").value = state.logbook.filter.to; $("logbook-kind").value = state.logbook.filter.kind || "";
  $("logbook-kind-field").hidden = state.logbook.filter.type !== "records";
  state.logbook.cursor = null; state.logbook.records = []; $("logbook-more").hidden = true; $("logbook-reload").hidden = true;
  await loadLogbookPage(false, generation);
}
async function applyLogbookFilters(event) {
  event.preventDefault(); if (!state.logbook.open || state.logbook.busy) return;
  const filter = readLogbookFilter();
  if (filter.from && filter.to && filter.from > filter.to) { setStatus("logbook-message", "Das Von-Datum muss vor dem Bis-Datum liegen.", true); $("logbook-from").focus(); return; }
  state.logbook.filter = filter; state.logbook.cursor = null; state.logbook.records = []; state.logbook.needsReload = false;
  $("logbook-more").hidden = true; $("logbook-reload").hidden = true;
  const generation = ++state.logbook.generation; await loadLogbookPage(false, generation);
}
async function initialize() {
  try {
    const capabilities = await getJson("/garage-api/capabilities");
    const required = ["vehicles", "status", "odometer", "records", "history"];
    if (capabilities.backend !== "standalone" || !Array.isArray(capabilities.features) || !required.every(feature => capabilities.features.includes(feature))) throw new Error("invalid capabilities");
    state.standalone = true;
    state.recordCorrections = capabilities.features.includes("recordCorrections");
    state.historyBrowsing = capabilities.features.includes("historyBrowsing");
    state.scheduledWork = capabilities.features.includes("scheduledWork");
    state.dataExport = capabilities.features.includes("dataExport");
    state.inspectionStatus = capabilities.features.includes("inspectionStatus");
  } catch (error) { if (error.status !== 404) { setStatus("status", "Die Fahrzeuge konnten nicht geladen werden. Bitte versuche es erneut.", true); return; } }
  state.capabilitiesReady = true;
  $("legacy-manage").hidden = state.standalone; $("legacy-banner").hidden = state.standalone;
  $("own-toolbar").hidden = !state.standalone; $("own-detail-actions").hidden = !state.standalone;
  $("logbook-toggle").hidden = !state.historyBrowsing;
  $("work-dashboard").hidden = !state.scheduledWork; renderWorkDashboard();
  $("data-export-wrap").hidden = !state.dataExport;
  $("reminders-panel").hidden = state.standalone; $("detail-content").classList.toggle("standalone-detail", state.standalone);
  await load();
}
document.addEventListener("visibilitychange", () => {
  if (state.inspectionStatus && document.visibilityState === "visible") return refreshInspectionVehicles();
});
if (typeof setInterval === "function") setInterval(() => refreshInspectionVehicles(), 60000);
$("vehicle-add").addEventListener("click", () => openEntry("vehicle-new"));
$("vehicle-edit").addEventListener("click", () => openEntry("vehicle-edit"));
$("odometer-add").addEventListener("click", () => openEntry("odometer"));
$("record-add").addEventListener("click", () => openEntry("record"));
$("history-toggle").addEventListener("click", showHistory);
$("logbook-toggle").addEventListener("click", () => openLogbook());
$("logbook-close").addEventListener("click", () => closeLogbook());
$("logbook-filters").addEventListener("submit", applyLogbookFilters);
$("logbook-type").addEventListener("change", () => { $("logbook-kind-field").hidden = $("logbook-type").value !== "records"; });
$("logbook-more").addEventListener("click", () => loadLogbookPage(true, state.logbook.generation));
$("logbook-reload").addEventListener("click", () => openLogbook(true));
$("own-cancel").addEventListener("click", () => closeEntry(true));
$("own-form").addEventListener("submit", saveEntry);
initialize();
