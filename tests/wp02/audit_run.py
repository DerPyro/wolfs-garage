#!/usr/bin/env python3
"""Isolated synthetic audit assessment. No external provider/account changes.
Uses only a fresh random Docker project with existing pinned internal-only sandbox compose.
All self-created containers are stopped in finally; volumes retained for diagnosis.
"""
import http.server
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/wp01'))
from helpers import Client, login
COMPOSE=ROOT/'tests/lubelogger/compose.sandbox.yaml'
LOCK=json.loads((ROOT/'tests/lubelogger/target.lock.json').read_text())
PROJECT='wolfs-wp02-audit-'+secrets.token_hex(5)
EVENTS=[]
RESULT={'scope':'single synthetic root administrator, no Cloudflare/OIDC test','project':PROJECT,
 'sourceRevision':LOCK['sourceRevision'],'image':LOCK['image'],'startedAt':datetime.now(timezone.utc).isoformat(),'checks':[]}
SERVER=None

def dc(*args):
 return subprocess.check_output(['docker','compose','-p',PROJECT,'-f',str(COMPOSE),*args],text=True).strip()

def check(name,yes,details=None):
 RESULT['checks'].append({'name':name,'status':'pass' if yes else 'fail','details':details})
 print(('PASS' if yes else 'FAIL')+': '+name,flush=True)
 assert yes,name

class Hook(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  if self.headers.get('Transfer-Encoding','').lower()=='chunked':
   chunks=[]
   while True:
    size=int(self.rfile.readline().split(b';',1)[0].strip(),16)
    if not size:
     while self.rfile.readline() not in (b'\r\n',b'\n',b''):pass
     break
    chunks.append(self.rfile.read(size));self.rfile.read(2)
   body=b''.join(chunks)
  else:body=self.rfile.read(int(self.headers.get('Content-Length','0')))
  data=json.loads(body)
  EVENTS.append(data)
  self.send_response(204);self.end_headers()

def wait_events(n):
 for _ in range(100):
  if len(EVENTS)>=n:return
  time.sleep(.05)
 raise AssertionError('local webhook wait timeout')

def main():
 global SERVER
 dc('up','-d','lubelogger')
 meta=json.loads(subprocess.check_output(['docker','inspect',dc('ps','-q','lubelogger')]))[0]
 assert meta['Config']['Image']==LOCK['image']
 assert meta['Image']==json.loads(subprocess.check_output(['docker','image','inspect',LOCK['image']]))[0]['Id']
 assert not meta['HostConfig']['PortBindings']
 assert len(meta['NetworkSettings']['Networks'])==1
 net=next(iter(meta['NetworkSettings']['Networks'].values()))
 network=json.loads(subprocess.check_output(['docker','network','inspect',net['NetworkID']]))[0]
 assert network['Internal']
 base='http://'+net['IPAddress']+':8080'
 gateway=network['IPAM']['Config'][0]['Gateway']
 for _ in range(100):
  try:
   if Client(base).call('/')[0] in (200,302):break
  except OSError:pass
  time.sleep(.2)
 else:raise AssertionError('readiness timeout')
 initial=Client(base);password=secrets.token_urlsafe(24)
 assert initial.get('/Login/CreateLoginCreds',method='POST',form={'UserName':'synthetic-admin','Password':password}) is True
 root=login(base,'synthetic-admin',password)
 SERVER=http.server.ThreadingHTTPServer((gateway,0),Hook)
 threading.Thread(target=SERVER.serve_forever,daemon=True).start()
 assert root.get('/Home/WriteServerConfiguration',method='POST',form={'WebHookURL':f'http://{gateway}:{SERVER.server_port}/audit'}) is True
 time.sleep(.6)
 vehicle=root.ok('/api/vehicles/add',method='POST',data={'Year':2020,'Make':'Synthetic','Model':'Audit','LicensePlate':'SYN-AUDIT'})['additionalData']['vehicleId']
 wait_events(1);EVENTS.clear()
 record=root.ok('/api/vehicle/servicerecords/add?vehicleId='+str(vehicle),method='POST',data={'Date':'26.10.2026','Odometer':1000,'Description':'synthetic-audit-api-original','Cost':12.34})['additionalData']['recordId']
 before=root.get('/api/vehicle/servicerecords?vehicleId='+str(vehicle))
 check('service API exposes business date but no creation/modification timestamp',len(before)==1 and 'date' in before[0] and 'dateCreated' not in before[0] and 'dateModified' not in before[0],{'keys':sorted(before[0])})
 root.ok('/api/vehicle/servicerecords/update',method='PUT',data={'Id':record,'Date':'26.10.2026','Odometer':1000,'Description':'synthetic-audit-api-corrected','Cost':22.34})
 after=root.get('/api/vehicle/servicerecords?vehicleId='+str(vehicle))
 check('API correction replaces current service description and cost',len(after)==1 and after[0]['description']=='synthetic-audit-api-corrected' and after[0]['cost']==22.34)
 history=root.call('/Vehicle/GetVehicleHistory?vehicleId='+str(vehicle))[2].decode('utf-8-sig')
 check('native vehicle history shows corrected current record, not prior description','synthetic-audit-api-corrected' in history and 'synthetic-audit-api-original' not in history)
 root.ok('/api/vehicle/servicerecords/delete?id='+str(record),method='DELETE')
 check('deleted service absent from API current records',root.get('/api/vehicle/servicerecords?vehicleId='+str(vehicle))==[])
 history=root.call('/Vehicle/GetVehicleHistory?vehicleId='+str(vehicle))[2].decode('utf-8-sig')
 check('deleted service absent from native vehicle history','synthetic-audit-api-corrected' not in history)
 wait_events(3)
 check('local webhook records API add/update/delete actions',[x['type'] for x in EVENTS[:3]]==['servicerecord.add.api','servicerecord.update.api','servicerecord.delete.api'])
 check('generic events include actor vehicle action time and short new/current fields',all(x['username']=='synthetic-admin' and x['vehicleId']==str(vehicle) and x.get('timestamp') and x['data'].get('description') for x in EVENTS[:3]))
 check('generic event fields omit record identity and correction reason',all('recordId' not in x and 'recordId' not in x.get('data',{}) and 'notes' not in x.get('data',{}) for x in EVENTS[:3]),{'payloadKeys':sorted(EVENTS[0]),'dataKeys':sorted(EVENTS[0]['data'])})
 # Exercise native MVC writes separately; do not use private MVC routes as future integration contracts.
 form={'VehicleId':vehicle,'Date':'26.10.2026','Mileage':1100,'Description':'synthetic-audit-ui-original','Cost':'10,00'}
 root.ok('/Vehicle/SaveServiceRecordToVehicleId',method='POST',form=form)
 current=root.get('/api/vehicle/servicerecords?vehicleId='+str(vehicle));rid=current[0]['id']
 form.update(Id=rid,Description='synthetic-audit-ui-corrected',Cost='11,00')
 root.ok('/Vehicle/SaveServiceRecordToVehicleId',method='POST',form=form)
 root.ok('/Vehicle/DeleteServiceRecordById',method='POST',form={'serviceRecordId':rid})
 wait_events(6)
 check('local webhook records native add/update/delete actions',[x['type'] for x in EVENTS[3:6]]==['servicerecord.add','servicerecord.update','servicerecord.delete'])
 plan=root.ok('/api/vehicle/planrecords/add?vehicleId='+str(vehicle),method='POST',data={'Description':'synthetic-audit-plan','Cost':0,'Type':'ServiceRecord','Priority':'Normal','Progress':'Backlog'})['additionalData']['recordId']
 plans=root.get('/api/vehicle/planrecords?vehicleId='+str(vehicle));p=next(x for x in plans if x['id']==plan)
 check('planner API exposes created and modified dates',len(p['dateCreated'])==10 and len(p['dateModified'])==10,{'dateCreated':p['dateCreated'],'dateModified':p['dateModified']})
 ui_before=root.call('/Vehicle/GetPlanRecordForEditById?planRecordId='+str(plan))[2].decode('utf-8-sig')
 time.sleep(1.1)
 root.ok('/api/vehicle/planrecords/update',method='PUT',data={'Id':plan,'Description':'synthetic-audit-plan-edited','Cost':1,'Type':'ServiceRecord','Priority':'Normal','Progress':'Testing'})
 ui_after=root.call('/Vehicle/GetPlanRecordForEditById?planRecordId='+str(plan))[2].decode('utf-8-sig')
 import re
 labels=lambda s:re.findall(r'<label>([^<]*(?:Date Created|Last Modified)[^<]*)</label>',s)
 lb,la=labels(ui_before),labels(ui_after)
 check('planner native edit modal shows changed last-modified time',len(lb)==2 and len(la)==2 and lb[0]==la[0] and lb[1]!=la[1],{'beforeLabels':lb,'afterLabels':la})
 check('planner API returns only current stage',next(x for x in root.get('/api/vehicle/planrecords?vehicleId='+str(vehicle)) if x['id']==plan)['progress']=='Testing')
 RESULT['webhooks']=EVENTS[:6]
 RESULT['limits']=['single synthetic root user; no Cloudflare or provider account changes','webhooks only local success delivery tested; outage/restart retention not established','current API/UI state observed, no forensic recovery or adversarial immutable storage test','planner intermediate-stage history not exposed by inspected contracts; not a complete frontend screen audit']

if __name__=='__main__':
 failed=False
 try:main()
 except Exception as e:
  failed=True;RESULT['error']={'type':type(e).__name__,'message':str(e)};print('FAIL:',str(e),file=sys.stderr)
 finally:
  try:dc('stop','lubelogger');RESULT['containersStopped']=True
  except Exception:failed=True;RESULT['containersStopped']=False
  if SERVER:SERVER.shutdown();SERVER.server_close()
  RESULT['finishedAt']=datetime.now(timezone.utc).isoformat()
  out=ROOT/'tests/wp02/audit-results.json';out.write_text(json.dumps(RESULT,indent=2,ensure_ascii=False)+'\n')
  print('Sanitized results:',out)
 sys.exit(1 if failed else 0)
