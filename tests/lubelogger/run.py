#!/usr/bin/env python3
"""Disposable local contract probe. Python standard library + Docker Compose only.
Never accepts a remote target, existing project name, credentials or real data.
"""
import hashlib
import http.server
import http.cookiejar
import io
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMAGE = 'ghcr.io/hargata/lubelogger@sha256:483a9d7582c4e6258615fd822b3de4193b4fcc4230d0a92432c6d407faf75af2'
SOURCE = '63fa5cd267497ba01c29f4888c65efbbdd4b94bf'
PROJECT = 'wolfs-b02-' + secrets.token_hex(5)
OUT = ROOT / '.sandbox' / PROJECT
OUT.mkdir(parents=True, mode=0o700)
os.chmod(OUT, 0o700)
COLLECTORS = []
RESULT = {'project': PROJECT, 'startedAt': datetime.now().astimezone().isoformat(),
          'image': IMAGE, 'sourceRevision': SOURCE, 'tests': [], 'observations': {}}


def dc(*args):
    return subprocess.check_output(['docker', 'compose', '-p', PROJECT, '-f',
                                    str(HERE/'compose.sandbox.yaml'), *args], text=True).strip()


def inspect(service):
    return json.loads(subprocess.check_output(['docker', 'inspect', dc('ps', '-q', service)]))[0]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, base, key=None):
        self.base = base
        self.key = key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())

    def call(self, path, method='GET', data=None, form=None, invariant=True, upload=None):
        headers = {}
        if invariant:
            headers['culture-invariant'] = ''
        if self.key:
            headers['x-api-key'] = self.key
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        if form is not None:
            body = urllib.parse.urlencode(form, doseq=True).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        if upload:
            field, name, content = upload
            boundary = 'wolfs-' + secrets.token_hex(12)
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\n'
                    'Content-Type: application/octet-stream\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
            headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
        req = urllib.request.Request(self.base+path, body, headers, method=method)
        try:
            response = self.opener.open(req, timeout=20)
        except urllib.error.HTTPError as e:
            response = e
        raw = response.read()
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            value = None
        return response.code, value, raw

    def ok(self, path, **kwargs):
        code, value, _ = self.call(path, **kwargs)
        assert code == 200 and isinstance(value, dict) and value.get('success') is True, (path, code, 'unexpected operation result; response omitted')
        return value

    def get(self, path, **kwargs):
        code, value, _ = self.call(path, **kwargs)
        assert code == 200, (path, code)
        return value


def check(name, condition, detail=None, gap=False):
    status = ('gap' if gap else 'pass') if condition else 'fail'
    RESULT['tests'].append({'name': name, 'status': status, 'detail': detail})
    print(status.upper()+': '+name, flush=True)
    if not condition:
        raise AssertionError(name)


def start(service):
    dc('--profile', 'restore', 'up', '-d', service)
    meta = inspect(service)
    assert not meta['NetworkSettings']['Ports'].get('8080/tcp'), 'No published port allowed'
    networks = meta['NetworkSettings']['Networks']
    assert len(networks) == 1
    net = next(iter(networks.values()))
    nmeta = json.loads(subprocess.check_output(['docker', 'network', 'inspect', net['NetworkID']]))[0]
    assert nmeta['Internal'] is True
    base = 'http://' + net['IPAddress'] + ':8080'
    for _ in range(60):
        try:
            if Client(base).call('/')[0] in (200, 302):
                return base
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.5)
    raise RuntimeError('Sandbox readiness timeout')


def login(base, username, password):
    c = Client(base)
    # Upstream reloads JSON configuration asynchronously after initial setup/restore.
    for _ in range(30):
        code, value, _ = c.call('/Login/Login', method='POST', form={'UserName': username, 'Password': password})
        if code == 200 and isinstance(value, dict) and value.get('success') is True:
            return c
        time.sleep(0.2)
    raise AssertionError('Login failed after bounded configuration reload wait')


def user(root, base, name):
    email = name.removeprefix('sandbox-')+'@example.invalid'
    root.ok('/Admin/GenerateNewToken', method='POST', form={'emailAddress': email, 'autoNotify': 'false'})
    rows = root.call('/Admin/GetTokenPartialView')[2].decode('utf-8-sig')
    token = None
    for row in re.findall(r'<tr.*?</tr>', rows, re.S):
        if email in row:
            token = re.search(r'copyToClipboard\(this\)">(.*?)</td>', row).group(1)
    assert token, 'Registration token missing'
    password = secrets.token_urlsafe(24)
    Client(base).ok('/Login/Register', method='POST', form={'UserName': name, 'Password': password,
                       'EmailAddress': email, 'Token': token})
    return login(base, name, password)


def key(session, base, name, permissions):
    result = session.ok('/Home/CreateAPIKeyForUser', method='POST',
                        form={'keyName': name, 'permissions': permissions})
    return Client(base, result['additionalData']['apiKey'])


def api_add(client, resource, vehicle, data):
    return client.ok('/api/vehicle/'+resource+'/add?vehicleId='+str(vehicle), method='POST', data=data)['additionalData']['recordId']


def items(client, resource, vehicle):
    return client.get('/api/vehicle/'+resource+'?vehicleId='+str(vehicle))


def denied(result):
    code, value, _ = result
    return code in (401,403) or (code == 200 and isinstance(value,dict) and value.get('success') is False)


def run():
    base = start('lubelogger')
    RESULT['runtime'] = {'docker': subprocess.check_output(['docker','version','--format','{{.Server.Version}}'],text=True).strip(),
                         'timezone': 'Europe/Berlin', 'locale': 'de-DE', 'publishedPorts': [], 'networkInternal': True}
    meta = json.loads(subprocess.check_output(['docker', 'image', 'inspect', IMAGE]))[0]
    labels = meta['Config']['Labels']
    check('image revision and version', labels['org.opencontainers.image.revision'] == SOURCE and
          labels['org.opencontainers.image.version'] == 'v1.7.4', {'imageId':meta['Id'],'architecture':meta['Architecture']})
    password = secrets.token_urlsafe(24)
    assert Client(base).get('/Login/CreateLoginCreds', method='POST', form={'UserName':'sandbox-root','Password':password}) is True
    root = login(base, 'sandbox-root', password)
    # Store no password, session cookie, registration token or API key in evidence.
    check('auth required after setup', Client(base).call('/api/vehicles')[0] == 401)
    check('invalid API key denied', Client(base,'invalid-synthetic-key').call('/api/vehicles')[0] == 401)
    info=root.get('/api/info')
    check('actual application locale is de-DE', info['locale']=='de-DE', info)
    routes=subprocess.check_output(['docker','exec',dc('ps','-q','lubelogger'),'cat','/proc/net/route'],text=True)
    check('isolated application has no default IPv4 route', not any(line.split()[1]=='00000000' for line in routes.splitlines()[1:]))
    owner = user(root,base,'sandbox-owner')
    outsider = user(root,base,'sandbox-outsider')
    owner.get('/Home/WriteToSettings', method='POST', form={'UseMPG':'false','EnableAuth':'true',
                  'EnableAutoReminderRefresh':'false','EnableAutoOdometerInsert':'true'})
    viewer = key(owner,base,'viewer',[])
    editor = key(owner,base,'editor',['Edit'])
    other = key(outsider,base,'outsider',['Edit'])
    check('viewer can read empty vehicle list', viewer.get('/api/vehicles') == [])
    vehicle_input = {'Year':2020,'Make':'Synthetic','Model':'Car-1','LicensePlate':'SYNTHETIC-1',
                     'ExtraFields':[{'Name':'Motorisierung','Value':'synthetic-engine-1'}]}
    check('viewer cannot create vehicle', denied(viewer.call('/api/vehicles/add',method='POST',data=vehicle_input)))
    vehicles=[]
    for n in range(1,6):
        data = dict(vehicle_input, Model=('Motorcycle' if n==5 else 'Car')+'-'+str(n), LicensePlate='SYNTHETIC-'+str(n))
        vehicles.append(editor.ok('/api/vehicles/add',method='POST',data=data)['additionalData']['vehicleId'])
    v=vehicles[0]
    vs=viewer.get('/api/vehicles')
    check('five synthetic vehicles and engine extra field', len(vs)==5 and
          vs[0]['extraFields'][0]['value']=='synthetic-engine-1', {'vehicleIds':vehicles})
    check('outsider list does not leak vehicles', other.get('/api/vehicles')==[])
    check('outsider cannot read vehicle odometer', denied(other.call('/api/vehicle/odometerrecords?vehicleId='+str(v))))
    check('viewer cannot delete vehicle', denied(viewer.call('/api/vehicles/delete?id='+str(v),method='DELETE')))
    check('editor cannot delete vehicle', denied(editor.call('/api/vehicles/delete?id='+str(v),method='DELETE')))
    reading={'Date':'26.10.2026','Odometer':12345,'InitialOdometer':12000,'Notes':'synthetic-reading'}
    check('viewer cannot create odometer', denied(viewer.call('/api/vehicle/odometerrecords/add?vehicleId='+str(v),method='POST',data=reading)))
    check('outsider cannot write vehicle', denied(other.call('/api/vehicle/odometerrecords/add?vehicleId='+str(v),method='POST',data=reading)))
    check('denied writes have no effects', items(viewer,'odometerrecords',v)==[])
    rid=api_add(editor,'odometerrecords',v,reading)
    rs=items(viewer,'odometerrecords',v)
    RESULT['observations']['odometerInvariant']=rs
    check('odometer JSON roundtrip, number types and invariant date', rs[0]['id']==rid and rs[0]['odometer']==12345 and
          isinstance(rs[0]['odometer'],int) and rs[0]['date'].startswith('2026-10-26'), rs)
    raw=viewer.get('/api/vehicle/odometerrecords?vehicleId='+str(v),invariant=False)
    check('German locale differs from invariant', isinstance(raw[0]['odometer'],str) and raw[0]['date']=='26.10.2026', raw)
    editor.ok('/api/vehicle/odometerrecords/update',method='PUT',data=dict(reading,Id=rid,Odometer=12400))
    api_add(editor,'odometerrecords',v,dict(reading,Date='01.10.2026',Odometer=11000,InitialOdometer=10000))
    protected = dict(reading, Id=rid, Odometer=99999)
    check('viewer cannot update existing record', denied(viewer.call('/api/vehicle/odometerrecords/update',method='PUT',data=protected)))
    check('outsider cannot update foreign record ID', denied(other.call('/api/vehicle/odometerrecords/update',method='PUT',data=protected)))
    check('outsider all-record list is filtered', other.get('/api/vehicle/odometerrecords/all')==[])
    check('viewer and editor cannot delete odometer record', all(denied(c.call('/api/vehicle/odometerrecords/delete?id='+str(rid),method='DELETE')) for c in (viewer,editor)))
    check('odometer correction and backdated history retained', sorted(x['odometer'] for x in items(viewer,'odometerrecords',v))==[11000,12400])
    for resource,cost in [('servicerecords',123.45),('repairrecords',67.89)]:
        record={'Date':'26.10.2026','Odometer':12500,'Description':'synthetic-'+resource,'Cost':cost,
                'ExtraFields':[{'Name':'Arbeitsart','Value':'Eigenarbeit'},{'Name':'DauerMinuten','Value':'60'}]}
        api_add(editor,resource,v,record)
        result=items(viewer,resource,v)
        check(resource+' numeric cost and extra fields', result[0]['cost']==cost and len(result[0]['extraFields'])==2,result)
    check('service automatically adds odometer history', any(x['odometer']==12500 for x in items(viewer,'odometerrecords',v)))
    owner.get('/Home/WriteToSettings',method='POST',form={'UseMPG':'false','EnableAutoReminderRefresh':'false','EnableAutoOdometerInsert':'false'})
    api_add(editor,'servicerecords',vehicles[4],{'Date':'2026-10-02','Odometer':12000,'Description':'synthetic-ISO-and-string-cost','Cost':'123,45'})
    parsed=items(viewer,'servicerecords',vehicles[4])[0]
    check('ISO date and German decimal string roundtrip', parsed['date']=='2026-10-02' and parsed['cost']==123.45, parsed)
    check('auto odometer insert can be disabled', items(viewer,'odometerrecords',vehicles[4])==[])
    owner.get('/Home/WriteToSettings',method='POST',form={'UseMPG':'false','EnableAutoReminderRefresh':'false','EnableAutoOdometerInsert':'true'})
    invalid=editor.call('/api/vehicle/reminders/add?vehicleId='+str(v),method='POST',data={'Metric':'Both','Description':'invalid'})
    check('HTTP 200 does not imply write success', invalid[0]==200 and invalid[1]['success'] is False,{'http':invalid[0],'body':invalid[1]})
    today=datetime.now(ZoneInfo('Europe/Berlin')).date()
    for days in (0,7,30):
        api_add(editor,'reminders',v,{'Metric':'Date','Description':'synthetic-day-'+str(days),
                'DueDate':(today+timedelta(days=days)).strftime('%d.%m.%Y')})
    for label,due,km in [('km-first',today+timedelta(days=90),12000),('date-first',today-timedelta(days=1),99999)]:
        api_add(editor,'reminders',v,{'Metric':'Both','Description':'synthetic-'+label,'DueDate':due.strftime('%d.%m.%Y'),'DueOdometer':km})
    reminders=items(viewer,'reminders',v)
    RESULT['observations']['reminderBoundaries']=reminders
    byname={x['description']:x for x in reminders}
    check('Both km-first and date-first become overdue', all(byname['synthetic-'+x]['urgency']=='PastDue' for x in ('km-first','date-first')))
    check('calendar-day boundary discrepancy reproduced', byname['synthetic-day-30']['dueDays']==29 and
          byname['synthetic-day-7']['dueDays']==6 and byname['synthetic-day-0']['urgency']=='PastDue',
          {n:{k:r[k] for k in ('dueDate','dueDays','urgency')} for n,r in byname.items() if n.startswith('synthetic-day')},gap=True)
    # UI-only provisioning/interaction: explicitly not a public integration contract.
    form={'VehicleId':vehicles[1],'Date':'31.01.2028','Mileage':20000,'Description':'synthetic-recurring',
          'Metric':'Both','IsRecurring':'true','FixedIntervals':'true',
          'ReminderMonthInterval':'OneMonth','ReminderMileageInterval':'OneThousandMiles'}
    owner.ok('/Vehicle/SaveReminderRecordToVehicleId',method='POST',form=form)
    rr=items(viewer,'reminders',vehicles[1])[0]
    check('public reminder export omits recurrence', not any(k in rr for k in ('isRecurring','fixedIntervals','reminderMonthInterval')),rr,gap=True)
    editor.ok('/api/vehicle/reminders/update',method='PUT',data={'Id':rr['id'],'Metric':'Both','Description':'synthetic-recurring-updated',
                  'DueDate':'31.01.2028','DueOdometer':20000})
    owner.ok('/Vehicle/PushbackRecurringReminderRecord',method='POST',form={'reminderRecordId':rr['id']})
    pushed=items(viewer,'reminders',vehicles[1])[0]
    check('API update preserves existing recurrence and UI advances leap month', pushed['dueDate'].startswith('2028-02-29') and pushed['dueOdometer']==21000,pushed)
    owner.ok('/Vehicle/SaveServiceRecordToVehicleId',method='POST',form={'VehicleId':vehicles[1],'Date':'29.02.2028',
                  'Mileage':21000,'Cost':'10,00','Description':'synthetic-confirmed-maintenance','ReminderRecordId':rr['id']})
    pushed=items(viewer,'reminders',vehicles[1])[0]
    check('UI maintenance completion advances fixed recurrence', pushed['dueDate'].startswith('2028-03-29') and pushed['dueOdometer']==22000,pushed)
    # Flexible recurrence uses confirmed completion, not original due date.
    flex=dict(form, VehicleId=vehicles[1], Date='31.01.2028', Description='synthetic-flexible', FixedIntervals='false')
    owner.ok('/Vehicle/SaveReminderRecordToVehicleId',method='POST',form=flex)
    flexid=next(x['id'] for x in items(viewer,'reminders',vehicles[1]) if x['description']=='synthetic-flexible')
    owner.ok('/Vehicle/SaveServiceRecordToVehicleId',method='POST',form={'VehicleId':vehicles[1],'Date':'15.02.2028',
                  'Mileage':20500,'Cost':'0','Description':'synthetic-flexible-done','ReminderRecordId':flexid})
    flexresult=next(x for x in items(viewer,'reminders',vehicles[1]) if x['id']==flexid)
    check('flexible recurrence advances from confirmed completion', flexresult['dueDate']=='2028-03-15' and flexresult['dueOdometer']==21500,flexresult)
    # Public API ignores unknown recurrence fields; it cannot configure a repeating rule.
    ignored=api_add(editor,'reminders',vehicles[1],{'Metric':'Date','Description':'synthetic-ignored-recurrence',
                'DueDate':'31.01.2028','IsRecurring':True,'ReminderMonthInterval':'OneMonth'})
    rejected=owner.call('/Vehicle/PushbackRecurringReminderRecord',method='POST',form={'reminderRecordId':ignored})
    check('public API silently ignores recurrence input', rejected[1].get('success') is False,{'http':rejected[0],'response':rejected[1]},gap=True)
    prior=items(viewer,'reminders',vehicles[1])
    api_add(editor,'servicerecords',vehicles[1],{'Date':'15.03.2028','Odometer':21500,'Description':'synthetic-api-no-completion',
                 'Cost':0,'ReminderRecordId':[flexid]})
    afterapi=items(viewer,'reminders',vehicles[1])
    check('API maintenance does not advance selected reminder', [(x['id'],x['dueDate'],x['dueOdometer']) for x in prior]==
           [(x['id'],x['dueDate'],x['dueOdometer']) for x in afterapi],gap=True)
    for date,months,expected in [('29.02.2028','OneYear','2029-02-28'),('28.03.2026','Other','2026-03-30'),('24.10.2026','Other','2026-10-26')]:
        special=dict(form,VehicleId=vehicles[1],Metric='Date',Date=date,Description='synthetic-calendar-'+date,
                     ReminderMonthInterval=months,CustomMonthInterval=2,CustomMonthIntervalUnit='Days')
        owner.ok('/Vehicle/SaveReminderRecordToVehicleId',method='POST',form=special)
        specid=next(x['id'] for x in items(viewer,'reminders',vehicles[1]) if x['description']==special['Description'])
        owner.ok('/Vehicle/PushbackRecurringReminderRecord',method='POST',form={'reminderRecordId':specid})
        result=next(x for x in items(viewer,'reminders',vehicles[1]) if x['id']==specid)
        check('recurrence calendar arithmetic '+date, result['dueDate']==expected,result)
    # Side-effectful native GET: only enable for this synthetic case, then disable again.
    old=(today-timedelta(days=10)).strftime('%d.%m.%Y')
    owner.ok('/Vehicle/SaveReminderRecordToVehicleId',method='POST',form=dict(form,VehicleId=vehicles[1],Date=old,
               Description='synthetic-autorefresh',Metric='Date',ReminderMonthInterval='OneMonth'))
    autoid=next(x['id'] for x in items(viewer,'reminders',vehicles[1]) if x['description']=='synthetic-autorefresh')
    owner.get('/Home/WriteToSettings',method='POST',form={'UseMPG':'false','EnableAutoReminderRefresh':'true','EnableAutoOdometerInsert':'true'})
    owner.get('/Vehicle/GetVehicleHaveUrgentOrPastDueReminders?vehicleId='+str(vehicles[1]))
    autonext=next(x for x in items(viewer,'reminders',vehicles[1]) if x['id']==autoid)
    check('native GET can advance due date without completion', autonext['dueDate']!=datetime.strptime(old,'%d.%m.%Y').date().isoformat(),autonext,gap=True)
    owner.get('/Home/WriteToSettings',method='POST',form={'UseMPG':'false','EnableAutoReminderRefresh':'false','EnableAutoOdometerInsert':'true'})
    # Detect custom threshold leaking into a subsequent standard reminder.
    standard=api_add(editor,'reminders',vehicles[2],{'Metric':'Date','Description':'synthetic-standard-before',
                        'DueDate':(today+timedelta(days=60)).strftime('%d.%m.%Y')})
    owner.ok('/Vehicle/SaveReminderRecordToVehicleId',method='POST',form=dict(form,VehicleId=vehicles[2],
             Description='synthetic-custom',Date=(today+timedelta(days=60)).strftime('%d.%m.%Y'),Metric='Date',IsRecurring='false',
             UseCustomThresholds='true', **{'CustomThresholds.UrgentDays':100,'CustomThresholds.VeryUrgentDays':90}))
    api_add(editor,'reminders',vehicles[2],{'Metric':'Date','Description':'synthetic-standard-after',
                         'DueDate':(today+timedelta(days=60)).strftime('%d.%m.%Y')})
    thresholds=items(viewer,'reminders',vehicles[2])
    beforestandard=next(x for x in thresholds if x['description']=='synthetic-standard-before')
    afterstandard=next(x for x in thresholds if x['description']=='synthetic-standard-after')
    check('custom threshold affects subsequent standard reminder', beforestandard['urgency']!=afterstandard['urgency'],thresholds,gap=True)

    # Supply purchase and UI requisition: inventory cost is NOT annual expenditure until used.
    sid=api_add(editor,'supplyrecords',vehicles[2],{'Date':'26.10.2026','Description':'synthetic-part','PartNumber':'SYNTH-PART',
                 'PartQuantity':2,'Cost':20.00})
    owner.ok('/Vehicle/SaveServiceRecordToVehicleId',method='POST',form={'VehicleId':vehicles[2],'Date':'26.10.2026',
               'Mileage':1000,'Description':'synthetic-part-install','Cost':'15,00','Supplies[0].SupplyId':sid,'Supplies[0].Quantity':1})
    supply=items(viewer,'supplyrecords',vehicles[2])[0]
    service=items(viewer,'servicerecords',vehicles[2])[0]
    check('supply requisition decreases stock; explicit total includes used part', supply['partQuantity']==1 and supply['cost']==10 and service['cost']==15,
          {'remainingSupply':supply,'service':service})
    # Attachment is synthetic plain text; byte equality checked again after restore.
    doc=b'Wolfs Garage synthetic B02 attachment. No personal data.\n'
    upload=editor.call('/api/documents/upload',method='POST',upload=('documents','synthetic.txt',doc))
    assert upload[0]==200 and isinstance(upload[1],list)
    attachment=upload[1][0]
    did=api_add(editor,'servicerecords',vehicles[3],{'Date':'26.10.2026','Odometer':100,'Description':'synthetic-document',
                    'Cost':0,'Files':[attachment]})
    before_supply=items(viewer,'supplyrecords',vehicles[2])
    api_add(editor,'servicerecords',vehicles[2],{'Date':'26.10.2026','Odometer':1010,'Description':'synthetic-api-ignored-supplies',
                  'Cost':0,'Supplies':[{'SupplyId':sid,'Quantity':1}]})
    check('public API ignores Supplies and does not decrease stock', items(viewer,'supplyrecords',vehicles[2])==before_supply,gap=True)
    check('document linked to record and authenticated download', items(viewer,'servicerecords',vehicles[3])[0]['files'][0]['location']==attachment['location'] and
          owner.call(attachment['location'])[2]==doc)
    foreigndoc=outsider.call(attachment['location'])
    check('document scope for authenticated outsider', denied(foreigndoc) or foreigndoc[2]==doc,
          {'http':foreigndoc[0],'bytesDisclosedToOutsider':foreigndoc[2]==doc},gap=not denied(foreigndoc))
    check('anonymous document access denied', Client(base).call(attachment['location'])[0] in (302,401,403))
    check('normal integration account cannot create backup', denied(viewer.call('/api/makebackup?output=download')))
    # Forward once, wait for upstream commit, then close without ANY response headers.
    # The client sees a transport failure; reconciliation finds the committed record.
    completed=[]
    class DropResponse(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            length=int(self.headers.get('Content-Length','0'))
            value=json.loads(self.rfile.read(length))
            status, result, _=editor.call(self.path,method='POST',data=value)
            completed.append(status==200 and result.get('success') is True)
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
        def log_message(self,*args):pass
    drop=http.server.ThreadingHTTPServer(('127.0.0.1',0),DropResponse)
    COLLECTORS.append(drop)
    threading.Thread(target=drop.serve_forever,daemon=True).start()
    transport_failed=False
    try:
        Client('http://127.0.0.1:'+str(drop.server_port)).call('/api/vehicle/odometerrecords/add?vehicleId='+str(vehicles[4]),
              method='POST',data=dict(reading,Notes='synthetic-response-lost'))
    except (OSError,urllib.error.URLError):
        transport_failed=True
    reconciled=[x for x in items(viewer,'odometerrecords',vehicles[4]) if x['notes']=='synthetic-response-lost']
    check('transport response loss reconciled without retry or duplicate', transport_failed and completed==[True] and len(reconciled)==1,
          {'connectionClosedBeforeResponseHeaders':True,'clientTransportFailure':transport_failed,'upstreamCommitted':completed,'reconciledCount':len(reconciled)})
    # Duplicate POST demonstrates absent upstream idempotency, using a separate tagged fixture.
    duplicate=dict(reading,Notes='synthetic-no-idempotency')
    for _ in range(2): api_add(editor,'odometerrecords',vehicles[4],duplicate)
    check('identical POST is not deduplicated upstream', len([x for x in items(viewer,'odometerrecords',vehicles[4]) if x['notes']=='synthetic-no-idempotency'])==2,gap=True)
    # Cookie-based UI change observed by a fresh API read; no production DB access.
    before=items(viewer,'repairrecords',vehicles[3])
    owner.ok('/Vehicle/SaveCollisionRecordToVehicleId',method='POST',form={'VehicleId':vehicles[3],'Date':'26.10.2026',
                      'Mileage':120,'Description':'synthetic-ui-repair','Cost':'12,50'})
    after=items(viewer,'repairrecords',vehicles[3])
    check('reconciliation sees direct UI write', len(before)==0 and len(after)==1 and after[0]['cost']==12.5,after)
    # Docs are supplied by the running image; capture bytes and compare pinned source.
    schema=root.call('/defaults/api.json')[2]
    expected=(HERE/'upstream/api.v1.7.4.json').read_bytes()
    check('running image API documentation matches pinned source', schema==expected,
          {'sha256':hashlib.sha256(schema).hexdigest(),'bytes':len(schema)})
    check('authenticated /api documentation renders', root.call('/api')[0]==200)
    # Local recorder bound only to the Docker bridge address. No public listener.
    meta=inspect('lubelogger')
    netid=next(iter(meta['NetworkSettings']['Networks'].values()))['NetworkID']
    nmeta=json.loads(subprocess.check_output(['docker','network','inspect',netid]))[0]
    hostip=nmeta['IPAM']['Config'][0]['Gateway']
    events=[]
    fail_remaining=[0]
    class Recorder(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            if self.headers.get('Transfer-Encoding','').lower()=='chunked':
                chunks=[]
                while True:
                    size=int(self.rfile.readline().split(b';',1)[0].strip(),16)
                    if size==0:
                        while self.rfile.readline().strip():pass
                        break
                    chunks.append(self.rfile.read(size))
                    assert self.rfile.read(2)==b'\r\n'
                raw=b''.join(chunks)
            else:
                raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
            payload=json.loads(raw)
            events.append(payload)
            code=500 if fail_remaining[0]>0 else 200
            fail_remaining[0]=max(0,fail_remaining[0]-1)
            self.send_response(code); self.end_headers()
        def log_message(self,*args):pass
    server=http.server.ThreadingHTTPServer((hostip,0),Recorder)
    COLLECTORS.append(server)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    assert root.get('/Home/WriteServerConfiguration',method='POST',form={'WebHookURL':'http://'+hostip+':'+str(server.server_port)+'/events'}) is True
    time.sleep(0.8)  # Wait for upstream JSON-config file watcher; no external dependency.
    fail_remaining[0]=2
    api_add(editor,'repairrecords',vehicles[3],{'Date':'26.10.2026','Odometer':130,'Description':'synthetic-webhook-api','Cost':0})
    for _ in range(30):
        if len(events)>=3:break
        time.sleep(0.1)
    check('webhook retries after two local HTTP 500 responses', len(events)==3,{'attempts':len(events)})
    owner.ok('/Vehicle/SaveCollisionRecordToVehicleId',method='POST',form={'VehicleId':vehicles[3],'Date':'26.10.2026',
                'Mileage':140,'Description':'synthetic-webhook-ui','Cost':'0'})
    for _ in range(30):
        if len(events)>=4:break
        time.sleep(0.1)
    RESULT['observations']['webhooks']=events
    check('webhook contains API and native UI event types',len(events)==4 and events[0]['type'].endswith('.api') and not events[-1]['type'].endswith('.api'),events)
    check('webhook lacks stable event ID and complete before-after data', all('eventId' not in e and 'before' not in e and 'after' not in e for e in events),gap=True)
    assert root.get('/Home/WriteServerConfiguration',method='POST',form={'WebHookURL':''}) is True
    time.sleep(0.5)

    # Save sanitized snapshots, then full upstream export; private backup remains ignored.
    snapshots={str(vid):{r:items(viewer,r,vid) for r in ('odometerrecords','servicerecords','repairrecords','supplyrecords','reminders')} for vid in vehicles}
    backup=root.call('/api/makebackup?output=download')
    assert backup[0]==200
    (OUT/'backup.zip').write_bytes(backup[2])
    z=zipfile.ZipFile(io.BytesIO(backup[2]))
    names=z.namelist()
    RESULT['observations']['backup']={'sha256':hashlib.sha256(backup[2]).hexdigest(),
                     'includesDataProtectionKeys':any('DataProtection' in n for n in names),'entries':len(names)}
    check('backup excludes DataProtection keys (separate backup needed)', not RESULT['observations']['backup']['includesDataProtectionKeys'],gap=True)
    restorebase=start('restore')
    recovery=Client(restorebase)
    # Fresh isolated instance has auth disabled by upstream default. Upload and restore before any other user access.
    restoredfile=recovery.call('/Files/HandleFileUpload',method='POST',upload=('file','backup.zip',backup[2]))
    assert restoredfile[0]==200 and isinstance(restoredfile[1],str)
    code,value,_=recovery.call('/Files/RestoreBackup',method='POST',form={'fileName':restoredfile[1]})
    assert code==200 and value is True,(code,value)
    dc('restart','restore')
    for _ in range(40):
        try:
            if Client(restorebase).call('/api/vehicles')[0]==401:break
        except (OSError,urllib.error.URLError):pass
        time.sleep(0.5)
    recovered=Client(restorebase,viewer.key)
    check('restored native authentication remains enabled', Client(restorebase).call('/api/vehicles')[0]==401)
    check('restored API key and vehicle identities', recovered.get('/api/vehicles')==vs)
    recovered_snapshots={str(vid):{r:items(recovered,r,vid) for r in snapshots[str(vid)]} for vid in vehicles}
    check('restore preserves records, amounts, IDs and references', recovered_snapshots==snapshots)
    # New keys change cookies; re-login is expected after application-export-only restore.
    recoveredroot=login(restorebase,'sandbox-root',password)
    restoredother=Client(restorebase,other.key)
    restorededitor=Client(restorebase,editor.key)
    check('restored outsider rights and editor delete restriction', restoredother.get('/api/vehicles')==[] and
          denied(restoredother.call('/api/vehicle/odometerrecords?vehicleId='+str(v))) and
          denied(restorededitor.call('/api/vehicles/delete?id='+str(v),method='DELETE')))
    # API keys cannot authenticate native file routes; check an anonymous browser here.
    check('restored anonymous document access denied', Client(restorebase).call(attachment['location'])[0] in (302,401,403))
    check('restored root login and attachment byte equality' , recoveredroot.call(attachment['location'])[2]==doc)
    print('Evidence: '+str(OUT/'results.json'),flush=True)


if __name__ == '__main__':
    failed=False
    try:
        run()
    except Exception as e:
        failed=True
        # Assertion messages may contain only test fixtures, never login/key responses.
        RESULT['error']={'type':type(e).__name__,'message':str(e)}
        print('FAIL: '+str(e),file=sys.stderr)
    finally:
        for server in COLLECTORS:
            server.shutdown()
            server.server_close()
        try:
            dc('--profile','restore','stop')
            RESULT['containersStopped']=True
        except Exception:
            RESULT['containersStopped']=False
            failed=True
        RESULT['finishedAt']=datetime.now().astimezone().isoformat()
        (OUT/'results.json').write_text(json.dumps(RESULT,indent=2,ensure_ascii=False)+'\n')
        print('Sanitized results: '+str(OUT/'results.json'))
        print('Stopped sandbox project (volumes retained locally): '+PROJECT)
    sys.exit(1 if failed else 0)
