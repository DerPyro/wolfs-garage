#!/usr/bin/env python3
"""WP02 synthetic browser exploration. Docker-only sandbox, no external product calls."""
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/wp01'))
from helpers import Client, api_add

COMPOSE=ROOT/'tests/lubelogger/compose.sandbox.yaml'
LOCK=json.loads((ROOT/'tests/lubelogger/target.lock.json').read_text())
# This is the official Playwright browser test image, not an application service.
# Its bundled Chromium is driven via CDP using the included Node runtime.
BROWSER_IMAGE='mcr.microsoft.com/playwright@sha256:b27e719ecbfef153e13fd24e8341736733bf2658b229677eb21ff57ff5d7fb29'
PROJECT='wolfs-wp02ui-'+secrets.token_hex(5)
BROWSER_NAME=PROJECT+'-chromium'
OUT=ROOT/'.sandbox'/PROJECT
OUT.mkdir(parents=True,mode=0o700)
os.chmod(OUT,0o700)
RESULT={'project':PROJECT,'startedAt':datetime.now().astimezone().isoformat(),
 'lubeloggerImage':LOCK['image'],'sourceRevision':LOCK['sourceRevision'],'steps':[]}


def dc(*args):
 return subprocess.check_output(['docker','compose','-p',PROJECT,'-f',str(COMPOSE),*args],text=True).strip()


def step(name,condition):
 RESULT['steps'].append({'name':name,'pass':bool(condition)})
 print(('PASS: ' if condition else 'FAIL: ')+name,flush=True)
 if not condition:raise AssertionError(name)


def run():
 global COMPOSE
 # Prefer an empty, internal network created by an earlier run of THIS test only.
 # This avoids exhausting Docker subnet pools without deleting any resources.
 names=subprocess.check_output(['docker','network','ls','--format','{{.Name}}'],text=True).splitlines()
 for name in names:
  if not (name.startswith('wolfs-wp02ui-') and name.endswith('_isolated')):continue
  meta=json.loads(subprocess.check_output(['docker','network','inspect',name]))[0]
  if not meta['Internal'] or meta.get('Containers'):continue
  template=COMPOSE.read_text()
  original='  isolated:\n    internal: true\n'
  assert original in template
  generated=OUT/'ui-compose.yaml'
  generated.write_text(template.replace(original,'  isolated:\n    external: true\n    name: '+name+'\n'))
  COMPOSE=generated
  RESULT['reusedEmptySyntheticNetwork']=name
  break
 dc('up','-d','lubelogger')
 container=json.loads(subprocess.check_output(['docker','inspect',dc('ps','-q','lubelogger')]))[0]
 image=json.loads(subprocess.check_output(['docker','image','inspect',LOCK['image']]))[0]
 assert container['Image']==image['Id']
 assert not container['HostConfig'].get('PortBindings')
 nets=container['NetworkSettings']['Networks']
 assert len(nets)==1
 net=next(iter(nets.values()))
 netmeta=json.loads(subprocess.check_output(['docker','network','inspect',net['NetworkID']]))[0]
 assert netmeta['Internal']
 base='http://'+net['IPAddress']+':8080'
 for _ in range(80):
  try:
   if Client(base).call('/api/vehicles')[0]==200:break
  except (OSError,urllib.error.URLError):pass
  time.sleep(0.25)
 else:raise AssertionError('Local LubeLogger readiness timeout')
 c=Client(base)
 # New empty local test container, authentication default off. No published ports or real data.
 settings={'UseMPG':'false','EnableAutoReminderRefresh':'false','EnableAutoOdometerInsert':'false',
   'VisibleTabs':['Dashboard','PlanRecord','OdometerRecord','ServiceRecord','RepairRecord','UpgradeRecord','SupplyRecord','TaxRecord','ReminderRecord','NoteRecord']}
 step('local root test settings saved',c.get('/Home/WriteToSettings',method='POST',form=settings) is True)
 vids=[]
 for n,name in enumerate(('UI-A','UI-B','UI-C','UI-D','UI-E')):
  result=c.ok('/api/vehicles/add',method='POST',data={'Year':2020+n,'Make':'Synthetic','Model':name,'LicensePlate':'UI-FAKE-'+str(n)})
  vids.append(result['additionalData']['vehicleId'])
 step('five synthetic vehicles created',len(c.get('/api/vehicles'))==5)
 v=vids[0]
 api_add(c,'odometerrecords',v,{'Date':'01.10.2026','InitialOdometer':10000,'Odometer':12000,'Notes':'UI-SYNTHETIC-ODO'})
 api_add(c,'servicerecords',v,{'Date':'20.10.2026','Odometer':12000,'Description':'UI-SERVICE-ALPHA','Cost':123.45,'Notes':'UI-SYNTHETIC-NOTE'})
 api_add(c,'repairrecords',v,{'Date':'01.09.2026','Odometer':11000,'Description':'UI-REPAIR-ALPHA','Cost':67.89})
 api_add(c,'supplyrecords',v,{'Date':'02.10.2026','Description':'UI-PART-ALPHA','PartNumber':'UI-PART-001','PartQuantity':2,'Cost':20})
 today=datetime.now(ZoneInfo('Europe/Berlin')).date()
 c.ok('/Vehicle/SaveReminderRecordToVehicleId',method='POST',form={'VehicleId':v,
   'Date':(today+timedelta(days=7)).strftime('%d.%m.%Y'),'Mileage':15000,'Description':'UI-REMINDER-ALPHA',
   'Metric':'Both','IsRecurring':'true','FixedIntervals':'true','ReminderMonthInterval':'OneYear',
   'ReminderMileageInterval':'FiveThousandMiles'})
 step('synthetic maintenance, part and reminder persisted',
      len(c.get('/api/vehicle/servicerecords?vehicleId='+str(v)))==1 and
      len(c.get('/api/vehicle/supplyrecords?vehicleId='+str(v)))==1 and
      len(c.get('/api/vehicle/reminders?vehicleId='+str(v)))==1)
 browser_image=json.loads(subprocess.check_output(['docker','image','inspect',BROWSER_IMAGE]))[0]
 RESULT['browserImageId']=browser_image['Id']
 RESULT['browserRepoDigests']=browser_image['RepoDigests']
 RESULT['browserVersionRequested']='v1.55.0-noble'
 browser_script=ROOT/'tests/wp02/ui_browser.js'
 cmd=['docker','create','--name',BROWSER_NAME,'--network',netmeta['Name'],'--init','--user',str(os.getuid())+':'+str(os.getgid()),
      '--cap-drop','ALL','--security-opt','no-new-privileges','--memory','1g','--pids-limit','256','--shm-size','512m',
      '--mount','type=bind,src='+str(browser_script)+',dst=/work/ui_browser.js,readonly',
      '--mount','type=bind,src='+str(OUT)+',dst=/artifacts',BROWSER_IMAGE,'node','/work/ui_browser.js']
 subprocess.check_output(cmd,text=True)
 browser=json.loads(subprocess.check_output(['docker','inspect',BROWSER_NAME]))[0]
 assert browser['Image']==browser_image['Id'] and not browser['HostConfig'].get('PortBindings')
 assert len(browser['NetworkSettings']['Networks'])==1
 run=subprocess.run(['docker','start','-a',BROWSER_NAME],capture_output=True,text=True,timeout=180)
 if run.returncode:
  data=(OUT/'ui-result.json')
  message=json.loads(data.read_text()).get('error','browser failed') if data.exists() else 'browser failed without result'
  raise AssertionError(message)
 observations=json.loads((OUT/'ui-result.json').read_text())
 step('Chromium reached all three viewports',observations.get('ok') and len(observations['viewports'])==3)
 services=c.get('/api/vehicle/servicerecords?vehicleId='+str(v))
 step('three UI-created synthetic services persisted',all(any(x['description']=='UI-NEW-'+str(w) and x['cost']==5 for x in services) for w in (320,768,1280)))
 RESULT['observations']=observations
 # Only synthetic, non-secret browser content is copied into reviewable artifacts.
 shots=ROOT/'tests/wp02/ui-shots'
 shots.mkdir(exist_ok=True)
 RESULT['screenshots']={}
 for p in sorted(OUT.glob('ui-*.png')):
  target=shots/p.name
  shutil.copyfile(p,target)
  RESULT['screenshots'][str(target.relative_to(ROOT))]=hashlib.sha256(target.read_bytes()).hexdigest()
 print('Synthetic screenshots copied:',len(RESULT['screenshots']),flush=True)


if __name__=='__main__':
 failed=False
 try:run()
 except Exception as e:
  failed=True
  RESULT['error']={'type':type(e).__name__,'message':str(e)}
  print('FAIL: '+str(e),file=sys.stderr)
 finally:
  # Stop only containers created under this randomly selected test project.
  browser_stopped=True
  if subprocess.run(['docker','inspect',BROWSER_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
   subprocess.run(['docker','stop',BROWSER_NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   browser_stopped=json.loads(subprocess.check_output(['docker','inspect',BROWSER_NAME]))[0]['State']['Running'] is False
  try:
   dc('stop')
   app_id=dc('ps','-a','-q','lubelogger')
   app_stopped=not app_id or not json.loads(subprocess.check_output(['docker','inspect',app_id]))[0]['State']['Running']
   RESULT['containersStopped']=bool(browser_stopped and app_stopped)
   if not RESULT['containersStopped']:failed=True
  except Exception:
   RESULT['containersStopped']=False;failed=True
  RESULT['finishedAt']=datetime.now().astimezone().isoformat()
  (OUT/'ui-run.json').write_text(json.dumps(RESULT,indent=2,ensure_ascii=False)+'\n')
  print('Local synthetic evidence:',OUT/'ui-run.json')
  print('Stopped sandbox project; synthetic volumes retained:',PROJECT)
 sys.exit(1 if failed else 0)
