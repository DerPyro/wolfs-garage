#!/usr/bin/env python3
"""WP01 runtime spike; synthetic fixtures and self-created Docker projects only.
No production configuration or persistent gateway is supplied.
"""
import hashlib
import hmac
import http.client
import http.server
import io
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

from helpers import Client, login, user, key, api_add, items, denied

ROOT=Path(__file__).resolve().parents[2]
COMPOSE=ROOT/'tests/lubelogger/compose.sandbox.yaml'
LOCK=json.loads((ROOT/'tests/lubelogger/target.lock.json').read_text())
PROJECT='wolfs-wp01-'+secrets.token_hex(5)
OUT=ROOT/'.sandbox'/PROJECT
OUT.mkdir(parents=True,mode=0o700)
os.chmod(OUT,0o700)
SERVERS=[]
RESULT={'project':PROJECT,'startedAt':datetime.now().astimezone().isoformat(),
 'image':LOCK['image'],'sourceRevision':LOCK['sourceRevision'],'tests':[],'observations':{}}


def dc(*args):
 return subprocess.check_output(['docker','compose','-p',PROJECT,'-f',str(COMPOSE),*args],text=True).strip()


def inspect(service):
 return json.loads(subprocess.check_output(['docker','inspect',dc('ps','-q',service)]))[0]


def start(service):
 dc('--profile','restore','up','-d',service)
 meta=inspect(service)
 expected_image=json.loads(subprocess.check_output(['docker','image','inspect',LOCK['image']]))[0]['Id']
 assert meta['Image']==expected_image, 'running container image does not match pinned image'
 assert not meta['HostConfig'].get('PortBindings')
 nets=meta['NetworkSettings']['Networks']
 assert len(nets)==1
 net=next(iter(nets.values()))
 config=json.loads(subprocess.check_output(['docker','network','inspect',net['NetworkID']]))[0]
 assert config['Internal']
 base='http://'+net['IPAddress']+':8080'
 for _ in range(60):
  try:
   if Client(base).call('/')[0] in (200,302):return base
  except (OSError,urllib.error.URLError):pass
  time.sleep(0.3)
 raise AssertionError('readiness timeout')


def check(name,condition,detail=None,gap=False):
 status=('gap' if gap else 'pass') if condition else 'fail'
 RESULT['tests'].append({'name':name,'status':status,'detail':detail})
 print(status.upper()+': '+name,flush=True)
 if not condition:raise AssertionError(name)


def describe(response):
 code,value,body=response
 result={'http':code,'bytes':len(body)}
 if isinstance(value,dict) and 'success' in value:result['success']=value['success']
 return result


def userids(root):
 # Admin HTML is parsed only in memory, never persisted: no API password/hash endpoint.
 html=root.call('/Admin/GetUserPartialView')[2].decode('utf-8-sig')
 result={}
 for name in ('sandbox-owner','sandbox-reader','sandbox-outsider'):
  # user row contains reset/admin buttons whose numeric id is stable.
  for row in re.findall(r'<tr.*?</tr>',html,re.S):
   if name in row:
    match=re.search(r'(?:deleteUser|updateUserAdminStatus|showUserHouseholdModal|revokeUserPassword|resetUserPassword)\((\d+)',row)
    if match:result[name]=int(match.group(1))
 return result


def raw(client,method,target,body=None,headers=None):
 url=urllib.parse.urlsplit(client.base)
 request=urllib.request.Request(client.base+'/')
 for handler in client.opener.handlers:
  if isinstance(handler,urllib.request.HTTPCookieProcessor):handler.cookiejar.add_cookie_header(request)
 hs=dict(headers or {})
 if request.has_header('Cookie'):hs['Cookie']=request.get_header('Cookie')
 if client.key:hs['x-api-key']=client.key
 hs['culture-invariant']=''
 conn=http.client.HTTPConnection(url.hostname,url.port,timeout=15)
 conn.request(method,target,body=body,headers=hs)
 response=conn.getresponse()
 data=response.read()
 selected={k.lower():v for k,v in response.getheaders() if k.lower() in ('content-type','content-length','location')}
 code=response.status
 conn.close()
 return code,data,selected


def odometers(admin,vehicle):
 # The per-vehicle GET itself can persist legacy conversions! Use non-converting all-reader as observer.
 return [x for x in admin.get('/api/vehicle/odometerrecords/all') if x['vehicleId']==vehicle]


def fingerprint(admin,vehicles):
 return {'vehicles':[x for x in admin.get('/api/vehicles') if x['id'] in vehicles],
   'records':{str(v):{r:(odometers(admin,v) if r=='odometerrecords' else items(admin,r,v))
    for r in ('servicerecords','repairrecords','odometerrecords','taxrecords','reminders','supplyrecords')} for v in vehicles}}


def run():
 base=start('lubelogger')
 meta=inspect('lubelogger')
 image=json.loads(subprocess.check_output(['docker','image','inspect',LOCK['image']]))[0]
 check('pinned image revision and isolated network without host ports',image['Config']['Labels']['org.opencontainers.image.revision']==LOCK['sourceRevision'],
       {'publishedPorts':[],'internalNetwork':True,'platform':image['Architecture']})
 password=secrets.token_urlsafe(24)
 assert Client(base).get('/Login/CreateLoginCreds',method='POST',form={'UserName':'sandbox-root','Password':password}) is True
 root=login(base,'sandbox-root',password)
 owner=user(root,base,'sandbox-owner')
 reader=user(root,base,'sandbox-reader')
 outsider=user(root,base,'sandbox-outsider')
 ids=userids(root)
 assert len(ids)==3,'admin user-id parsing failed (HTML omitted)'
 root.ok('/Admin/AddUserToHousehold',method='POST',form={'parentUserId':ids['sandbox-owner'],'username':'sandbox-reader'})
 assert root.get('/Admin/ModifyUserHouseholdPermissions',method='POST',form={'parentUserId':ids['sandbox-owner'],'childUserId':ids['sandbox-reader'],'permissions':[]}) is True
 for c in (owner,reader):
  assert c.get('/Home/WriteToSettings',method='POST',form={'UseMPG':'false','EnableAutoReminderRefresh':'false','EnableAutoOdometerInsert':'false'}) is True
 writer=key(owner,base,'writer',['Edit'])
 readkey=key(reader,base,'read',[])
 vehicles=[]
 for n in range(2):
  vehicles.append(writer.ok('/api/vehicles/add',method='POST',data={'Year':2020,'Make':'Synthetic','Model':'WP01-'+str(n),'LicensePlate':'SYNTH-WP01-'+str(n)})['additionalData']['vehicleId'])
 v,v2=vehicles
 sid=api_add(writer,'servicerecords',v,{'Date':'27.10.2026','Odometer':12000,'Description':'WP01-synthetic-service','Cost':15})
 for day,km in [('01.10.2026',10000),('20.10.2026',11000)]:
  rid=api_add(writer,'odometerrecords',v,{'Date':day,'Odometer':km,'InitialOdometer':0})
  # Add auto-fills previous mileage; explicit official update establishes a legacy all-zero fixture.
  writer.ok('/api/vehicle/odometerrecords/update',method='PUT',data={'Id':rid,'Date':day,'Odometer':km,'InitialOdometer':0})
 check('household View can list parent vehicles',len(reader.get('/api/vehicles'))==2)
 check('outsider cannot list or read parent vehicle',outsider.get('/api/vehicles')==[] and denied(outsider.call('/api/vehicle/servicerecords?vehicleId='+str(v))))
 for route in ['/Vehicle/Index?vehicleId='+str(v),'/Vehicle/GetServiceRecordsByVehicleId?vehicleId='+str(v),'/Vehicle/GetReminderRecordsByVehicleId?vehicleId='+str(v)]:
  response=reader.call(route)
  check('household View native page '+route.split('?')[0],response[0]==200 and len(response[2])>0,describe(response))
 # Representative normal/bulk paths must reject View and leave all seeded vehicle data intact.
 attempts=[('/Vehicle/SaveServiceRecordToVehicleId',{'VehicleId':v,'Date':'27.10.2026','Mileage':12345,'Description':'DENIED-WP01','Cost':'999,00'}),
  ('/Vehicle/SaveOdometerRecordToVehicleId',{'VehicleId':v,'Date':'27.10.2026','Mileage':99999}),
  ('/Vehicle/SaveVehicle',{'Id':v,'Year':2020,'Make':'DENIED-WP01','Model':'Denied','LicensePlate':'DENIED'}),
  ('/Vehicle/DeleteServiceRecordById',{'serviceRecordId':sid}),
  ('/Vehicle/DuplicateRecords',{'recordIds':[sid],'importMode':'ServiceRecord'}),
  ('/Vehicle/EditMultipleRecords',{'DataType':'ServiceRecord','RecordIds':[sid],'EditRecord.Description':'DENIED-WP01'})]
 for route,form in attempts:
  before=fingerprint(writer,vehicles)
  response=reader.call(route,method='POST',form=form)
  after=fingerprint(writer,vehicles)
  check('View normal write rejected '+route,denied(response) and after==before,describe(response))
 # Critical counterexample: native GET recomputes and PERSISTS initial odometers under View.
 before=odometers(writer,v)
 response=reader.call('/Vehicle/GetOdometerRecordsByVehicleId?vehicleId='+str(v))
 after=odometers(writer,v)
 check('household View GET mutates odometer history',response[0]==200 and before!=after and
       all(x['initialOdometer']==0 for x in before) and all(x['initialOdometer']>0 for x in after),
       {'before':before,'after':after},gap=True)
 # Repeat with the PUBLIC per-vehicle API reader. Inspect only through /all.
 for record in after:
  writer.ok('/api/vehicle/odometerrecords/update',method='PUT',data={'Id':record['id'],'Date':record['date'],'Odometer':record['odometer'],'InitialOdometer':0})
 beforeapi=odometers(writer,v)
 readkey.call('/api/vehicle/odometerrecords?vehicleId='+str(v))
 afterapi=odometers(writer,v)
 check('public Viewer-key GET also persists legacy odometer conversion',beforeapi!=afterapi and all(x['initialOdometer']==0 for x in beforeapi),
       {'before':beforeapi,'after':afterapi},gap=True)
 # Another read-only mutation: native tax repeat-check, seeded by legitimate native+API writes.
 today=datetime.now(ZoneInfo('Europe/Berlin')).date()
 owner.ok('/Vehicle/SaveTaxRecordToVehicleId',method='POST',form={'VehicleId':v2,'Date':(today+timedelta(days=20)).strftime('%d.%m.%Y'),
           'Description':'WP01-synthetic-recurring-tax','Cost':'10,00','IsRecurring':'true','RecurringInterval':'OneMonth'})
 tax=items(writer,'taxrecords',v2)[0]
 writer.ok('/api/vehicle/taxrecords/update',method='PUT',data={'Id':tax['id'],'Date':(today-timedelta(days=65)).strftime('%d.%m.%Y'),
        'Description':'WP01-synthetic-recurring-tax','Cost':10})
 before=items(writer,'taxrecords',v2)
 response=reader.call('/Vehicle/CheckRecurringTaxRecords?vehicleId='+str(v2),method='POST',form={})
 after=items(writer,'taxrecords',v2)
 check('household View tax check creates recurring cost records',response[0]==200 and len(after)>len(before),
       {'http':response[0],'beforeCount':len(before),'afterCount':len(after),'before':before,'after':after},gap=True)
 # View is not a global role: child can create its OWN vehicle and write it.
 prior=reader.get('/api/vehicles')
 response=reader.call('/Vehicle/SaveVehicle',method='POST',form={'Year':2021,'Make':'Synthetic','Model':'Child-owned','LicensePlate':'SYNTH-CHILD'})
 aftervehicles=reader.get('/api/vehicles')
 added=[x for x in aftervehicles if x['id'] not in {v['id'] for v in prior}]
 check('household View user can create directly owned vehicle',response[1].get('success') is True and len(added)==1,{'newOwnedVehicleId':added[0]['id'] if added else None},gap=True)
 newv=added[0]['id']
 reader.ok('/Vehicle/SaveServiceRecordToVehicleId',method='POST',form={'VehicleId':newv,'Date':'27.10.2026','Mileage':1,'Description':'WP01-direct-owned','Cost':'1,00'})
 check('child writes directly owned vehicle outside parent View restriction',len(items(reader,'servicerecords',newv))==1,gap=True)
 # Synthetically sourced file and temp leaks; no personal content or raw credentials in evidence.
 doc=b'WP01-SYNTHETIC-DOCUMENT\n'
 upload=writer.call('/api/documents/upload',method='POST',upload=('documents','synthetic.txt',doc))
 assert upload[0]==200 and isinstance(upload[1],list)
 location=upload[1][0]['location']
 writer.ok('/api/vehicle/servicerecords/update',method='PUT',data={'Id':sid,'Date':'27.10.2026','Odometer':12000,
       'Description':'WP01-synthetic-service','Cost':15,'Files':upload[1]})
 for role,actor in [('owner',owner),('household-view',reader),('outsider',outsider)]:
  response=actor.call(location)
  check('native document bytes accessible '+role,response[0]==200 and response[2]==doc,
        {'role':role,'http':response[0],'matchesSyntheticBytes':response[2]==doc},gap=(role=='outsider'))
 check('anonymous native document denied',Client(base).call(location)[0] in (302,401,403))
 viewerupload=readkey.call('/api/documents/upload',method='POST',upload=('documents','viewer-synthetic.txt',b'WP01-VIEWER-UPLOAD'))
 check('public Viewer key can upload document without Edit permission',viewerupload[0]==200 and isinstance(viewerupload[1],list) and owner.call(viewerupload[1][0]['location'])[2]==b'WP01-VIEWER-UPLOAD',{'http':viewerupload[0],'persistedSyntheticBytes':True},gap=True)
 # Captured raw-target variants avoid client URL normalization.
 filename=location.rsplit('/',1)[1]
 variants=[location,'/Documents/'+filename,'//documents/'+filename,'/documents//'+filename,
    '/%64ocuments/'+filename,'/documents/%2e/'+filename,'/documents/../documents/'+filename,
    '/documents/%252e%252e/documents/'+filename,'/Files/GetStaticFile?fileName='+filename,
    '/Files/PreviewFile?fileName=synthetic.txt&fileLocation='+urllib.parse.quote(location,safe='')]
 variant_results=[]
 for target in variants:
  status,body,headers=raw(outsider,'GET',target)
  variant_results.append({'target':target,'http':status,'matchesDocumentBytes':body==doc,'previewReferencesDocument':location.encode() in body})
 RESULT['observations']['directFileVariants']=variant_results
 check('direct-path variations characterized',any(x['matchesDocumentBytes'] for x in variant_results),{'cases':len(variant_results)},gap=True)
 status,body,head=raw(outsider,'HEAD',location)
 RESULT['observations']['fileHead']={'http':status,'contentLength':head.get('content-length'),'bodyBytes':len(body)}
 check('known document HEAD characterized without claiming byte read',len(body)==0,RESULT['observations']['fileHead'])
 temp=outsider.call('/Files/HandleFileUpload',method='POST',upload=('file','synthetic.txt',b'WP01-TEMP-MARKER'))
 assert temp[0]==200 and isinstance(temp[1],str)
 temp_path=temp[1]
 check('unrelated authenticated user can upload temp file',reader.call(temp_path)[2]==b'WP01-TEMP-MARKER',{'http':temp[0]},gap=True)
 coordinates=reader.call('/Files/UploadCoordinates?coordinates=WP01-GET-WRITE')
 coord_path=coordinates[1].get('location') if isinstance(coordinates[1],dict) else None
 check('household View GET creates temporary file',coordinates[0]==200 and coord_path and b'WP01-GET-WRITE' in outsider.call(coord_path)[2],
       {'http':coordinates[0],'syntheticFileCreated':bool(coord_path)},gap=True)
 backup=root.call('/api/makebackup?output=download')
 assert backup[0]==200
 (OUT/'backup.zip').write_bytes(backup[2])
 for actor in (reader,outsider):
  check('non-root backup operation denied',denied(actor.call('/api/makebackup?output=download')))
 # File delete is intentionally only attempted against our own ephemeral synthetic temp fixture.
 status,_,headers=raw(reader,'POST','/Files/DeleteFiles',body=urllib.parse.urlencode({'fileLocation':temp_path}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
 check('View cannot execute root file deletion',status==302 and headers.get('location')=='/Error/403' and outsider.call(temp_path)[2]==b'WP01-TEMP-MARKER',{'http':status,'redirectToForbidden':headers.get('location')=='/Error/403','fileUnchanged':True})
 # Server-side origin check characterization, NOT proof of browser CSRF exploitability.
 count=len(items(writer,'servicerecords',v))
 status,body,_=raw(owner,'POST','/Vehicle/SaveServiceRecordToVehicleId',body=urllib.parse.urlencode({'VehicleId':v,'Date':'27.10.2026','Mileage':12100,'Description':'WP01-foreign-origin-form','Cost':'3,00'}).encode(),headers={'Content-Type':'application/x-www-form-urlencoded','Origin':'https://foreign.invalid','Referer':'https://foreign.invalid/form'})
 check('native form accepts foreign Origin with injected owner cookie and no antiforgery token',status==200 and json.loads(body).get('success') is True and len(items(writer,'servicerecords',v))==count+1,
       {'http':status,'serverAcceptedForeignOrigin':True,'browserCookieDeliveryTested':False},gap=True)
 # Revocation: remove parent View grant. API access goes away but direct files remain readable.
 assert root.get('/Admin/RemoveUserFromHousehold',method='POST',form={'parentUserId':ids['sandbox-owner'],'childUserId':ids['sandbox-reader']}) is True
 check('revoking household denies parent vehicle API',denied(reader.call('/api/vehicle/servicerecords?vehicleId='+str(v))))
 check('revoked household still reads known parent document',reader.call(location)[2]==doc,gap=True)
 # A narrow test-only API read gate: no native browser UI, no files, no writes.
 gate_token=secrets.token_urlsafe(24)
 forwarded=[]
 class Gate(http.server.BaseHTTPRequestHandler):
  def do_GET(self):self.dispatch()
  def do_HEAD(self):self.dispatch()
  def do_POST(self):self.dispatch()
  def do_PUT(self):self.dispatch()
  def do_DELETE(self):self.dispatch()
  def do_OPTIONS(self):self.dispatch()
  def do_PATCH(self):self.dispatch()
  def dispatch(self):
   rawtarget=self.raw_requestline.split()[1].decode('ascii')
   allowed=False
   if hmac.compare_digest(self.headers.get('X-WP01-Session','').encode('utf-8'),gate_token.encode('utf-8')) and self.command=='GET':
    target=urllib.parse.urlsplit(rawtarget)
    if rawtarget=='/api/vehicles':allowed=True
    elif target.path in ('/api/vehicle/servicerecords',):
     # Strict canonical raw query, explicit tracked IDs. No %, slash variants, duplicates or method override.
     allowed=rawtarget in [target.path+'?vehicleId='+str(vid) for vid in vehicles]
   if not allowed:
    self.send_response(403);self.send_header('Content-Length','0');self.end_headers();return
   forwarded.append({'method':self.command,'target':rawtarget})
   result=readkey.call(rawtarget)
   if rawtarget=='/api/vehicles' and isinstance(result[1],list):
    filtered=[x for x in result[1] if x['id'] in vehicles]
    result=(result[0],filtered,json.dumps(filtered).encode())
   self.send_response(result[0]);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(result[2])));self.end_headers()
   self.wfile.write(result[2])
  def log_message(self,*args):pass
 gate=http.server.ThreadingHTTPServer(('127.0.0.1',0),Gate)
 SERVERS.append(gate)
 threading.Thread(target=gate.serve_forever,daemon=True).start()
 gateclient=Client('http://127.0.0.1:'+str(gate.server_port))
 # No actor-bound grant now: restore grant for genuine allowed API reads.
 root.ok('/Admin/AddUserToHousehold',method='POST',form={'parentUserId':ids['sandbox-owner'],'username':'sandbox-reader'})
 hs={'X-WP01-Session':gate_token}
 status,body,_=raw(gateclient,'GET','/api/vehicle/servicerecords?vehicleId='+str(v),headers=hs)
 check('narrow local API gate allows scoped read',status==200 and b'WP01-synthetic-service' in body)
 status,body,_=raw(gateclient,'GET','/api/vehicles',headers=hs)
 listed=json.loads(body)
 check('narrow gate vehicle list excludes child-owned untracked vehicle',status==200 and sorted(x['id'] for x in listed)==sorted(vehicles) and newv not in [x['id'] for x in listed],{'listedVehicleIds':[x['id'] for x in listed],'untrackedChildId':newv})
 check('narrow gate denies missing authentication marker',raw(gateclient,'GET','/api/vehicles')[0]==403)
 gate_attempts=[('GET',p) for p in variants+[temp_path,coord_path,'/Files/UploadCoordinates?coordinates=BLOCKED',
  '/Vehicle/GetOdometerRecordsByVehicleId?vehicleId='+str(v),'/api/vehicle/odometerrecords?vehicleId='+str(v),'/api/makebackup?output=download',
  '/API/vehicles','//api/vehicles','/api//vehicles','/%61pi/vehicles','/api/vehicles?apiKey=BLOCKED',
  '/api/vehicle/servicerecords?vehicleId='+str(v)+'&vehicleId='+str(newv),
  '/api/vehicle/servicerecords?vehicleId='+str(newv),'/api/vehicle/servicerecords?vehicleId=%31']]
 gate_attempts +=[(verb,path) for verb,path in [('HEAD',location),('POST','/Vehicle/SaveVehicle'),('POST','/api/vehicles/add'),
  ('GET','/Vehicle/MoveRecord?recordId='+str(sid)+'&source=ServiceRecord&destination=RepairRecord'),
  ('POST','/Files/HandleFileUpload'),('PUT','/api/vehicle/servicerecords/update'),('OPTIONS',location)]]
 before_forward=len(forwarded);before_state=fingerprint(writer,vehicles)
 blocked=[]
 for method,target in gate_attempts:
  status,_,_=raw(gateclient,method,target,headers=hs)
  blocked.append({'method':method,'target':target,'http':status})
 RESULT['observations']['gateBlockedRequests']=blocked
 check('narrow API gate rejects variant, write, file and unsupported-native paths',all(x['http']==403 for x in blocked),{'blockedCount':len(blocked)})
 check('rejected gate requests never forwarded and data unchanged',len(forwarded)==before_forward and fingerprint(writer,vehicles)==before_state)
 # Direct native origin is STILL reachable by the harness, so this gate is not a complete topology/security solution.
 check('direct origin bypass exists in sandbox topology',outsider.call(location)[2]==doc,gap=True)
 RESULT['observations']['gateScope']={'kind':'test-only exact API allowlist','nativeUiSupported':False,'productionAuthImplemented':False,'originExcludedFromUntrustedClients':False,'forwardedRequests':forwarded}
 # Restore preserves the same unsafe object-level file semantics: do not mistake restore for a fix.
 restored=start('restore')
 recovery=Client(restored)
 uploaded=recovery.call('/Files/HandleFileUpload',method='POST',upload=('file','backup.zip',backup[2]))
 assert uploaded[0]==200 and isinstance(uploaded[1],str)
 assert recovery.get('/Files/RestoreBackup',method='POST',form={'fileName':uploaded[1]}) is True
 dc('restart','restore')
 for _ in range(60):
  try:
   if Client(restored).call('/api/vehicles')[0]==401:break
  except (OSError,urllib.error.URLError):pass
  time.sleep(0.3)
 else:raise AssertionError('restore auth readiness timeout')
 restoredroot=login(restored,'sandbox-root',password)
 restoredoutsider=login(restored,*outsider.test_credentials)
 restoredreader=login(restored,*reader.test_credentials)
 check('restore keeps document bytes and root login',restoredroot.call(location)[2]==doc)
 check('restore retains unauthorized authenticated file access',restoredoutsider.call(location)[2]==doc,gap=True)
 check('restore remains blocked to anonymous file access',Client(restored).call(location)[0] in (302,401,403))
 # Backup was BEFORE revocation, so View grant should be back; records are shared read-only apart from findings.
 check('restore retains household View for vehicle read',restoredreader.call('/api/vehicle/servicerecords?vehicleId='+str(v))[0]==200)
 print('WP01 evidence: '+str(OUT/'results.json'),flush=True)


if __name__=='__main__':
 failed=False
 try:run()
 except Exception as e:
  failed=True
  RESULT['error']={'type':type(e).__name__,'message':str(e)}
  print('FAIL: '+str(e),file=sys.stderr)
 finally:
  for server in SERVERS:server.shutdown();server.server_close()
  try:
   dc('--profile','restore','stop')
   RESULT['containersStopped']=True
  except Exception:
   RESULT['containersStopped']=False;failed=True
  RESULT['finishedAt']=datetime.now().astimezone().isoformat()
  (OUT/'results.json').write_text(json.dumps(RESULT,indent=2,ensure_ascii=False)+'\n')
  print('Results: '+str(OUT/'results.json'))
  print('Stopped sandbox; synthetic volumes retained: '+PROJECT)
 sys.exit(1 if failed else 0)
