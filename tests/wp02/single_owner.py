#!/usr/bin/env python3
"""Isolated LubeLogger auth-disabled characterization; no Access account or real data."""
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error
import zipfile
import io

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/wp01'))
from helpers import Client

COMPOSE=ROOT/'tests/lubelogger/compose.sandbox.yaml'
LOCK=json.loads((ROOT/'tests/lubelogger/target.lock.json').read_text())
PROJECT='wolfs-single-owner-'+secrets.token_hex(5)
OUT=ROOT/'.sandbox'/PROJECT
OUT.mkdir(parents=True,mode=0o700)
os.chmod(OUT,0o700)
RESULT={'project':PROJECT,'startedAt':datetime.now().astimezone().isoformat(),
        'image':LOCK['image'],'sourceRevision':LOCK['sourceRevision'],'checks':[]}


def dc(*args):
 return subprocess.check_output(['docker','compose','-p',PROJECT,'-f',str(COMPOSE),*args],text=True).strip()


def check(name,condition,observed):
 RESULT['checks'].append({'name':name,'passed':bool(condition),'observed':observed})
 print(('PASS: ' if condition else 'FAIL: ')+name,flush=True)
 if not condition:raise AssertionError(name)


def run():
 dc('up','-d','lubelogger')
 container=dc('ps','-q','lubelogger')
 meta=json.loads(subprocess.check_output(['docker','inspect',container]))[0]
 img=json.loads(subprocess.check_output(['docker','image','inspect',LOCK['image']]))[0]
 network=next(iter(meta['NetworkSettings']['Networks'].values()))
 network_info=json.loads(subprocess.check_output(['docker','network','inspect',network['NetworkID']]))[0]
 check('isolated image and network',meta['Image']==img['Id'] and network_info['Internal'] and not meta['HostConfig'].get('PortBindings'),
       {'internalNetwork':True,'publishedPorts':[],'imageRevision':img['Config']['Labels']['org.opencontainers.image.revision']})
 base='http://'+network['IPAddress']+':8080'
 client=Client(base)
 for _ in range(60):
  try:
   if client.call('/')[0]==200:break
  except (OSError,urllib.error.URLError):pass
  time.sleep(0.3)
 else:raise AssertionError('readiness timeout')
 status,_,page=client.call('/')
 check('native home loads without login redirect when auth is disabled',status==200 and len(page)>0,{'http':status})
 who=client.get('/api/whoami')
 check('uncredentialed internal caller receives root principal',str(who.get('isRoot')).lower()=='true',
       {'isRoot':who.get('isRoot'),'isAdmin':who.get('isAdmin')})
 check('internal API responds without a credential',client.get('/api/vehicles')==[],{'initialVehicleCount':0})
 result=client.ok('/api/vehicles/add',method='POST',data={'Year':2020,'Make':'Synthetic','Model':'AccessOnly','LicensePlate':'SYNTH-SINGLE'})
 vid=result['additionalData']['vehicleId']
 check('uncredentialed internal caller can create vehicle',len(client.get('/api/vehicles'))==1,{'syntheticVehicleId':vid})
 # With auth disabled, sending an invalid key does not enforce API-key roles.
 wrong=Client(base,'synthetic-invalid-key')
 status,data,_=wrong.call('/api/vehicles')
 check('invalid API key does not restrict an auth-disabled origin',status==200 and len(data)==1,
       {'http':status,'visibleSyntheticVehicles':len(data)})
 document=b'SINGLE-OWNER SYNTHETIC TEST ONLY\n'
 uploaded=client.call('/api/documents/upload',method='POST',upload=('documents','synthetic.txt',document))
 assert uploaded[0]==200 and isinstance(uploaded[1],list)
 location=uploaded[1][0]['location']
 getfile=Client(base).call(location)
 check('uncredentialed internal caller can upload and read document',getfile[0]==200 and getfile[2]==document,
       {'uploadHttp':uploaded[0],'readHttp':getfile[0],'matchesSyntheticBytes':getfile[2]==document})
 backup=Client(base).call('/api/makebackup?output=download')
 check('uncredentialed internal caller can request root backup',backup[0]==200 and zipfile.is_zipfile(io.BytesIO(backup[2])),
       {'http':backup[0],'validSyntheticZip':zipfile.is_zipfile(io.BytesIO(backup[2]))})
 # Confirm direct Host -> origin reachability; Access/Tunnel are intentionally absent here.
 check('host reaches origin directly in this sandbox topology',Client(base).call('/api/vehicles')[0]==200,
       {'cloudflareAccessOrTunnelTested':False,'directHostReachable':True})


if __name__=='__main__':
 failed=False
 try:run()
 except Exception as e:
  failed=True
  RESULT['error']={'type':type(e).__name__,'message':str(e)}
  print('FAIL: '+str(e),file=sys.stderr)
 finally:
  try:dc('stop');RESULT['containerStopped']=True
  except Exception:RESULT['containerStopped']=False;failed=True
  RESULT['finishedAt']=datetime.now().astimezone().isoformat()
  RESULT['summary']=dict(Counter('pass' if c['passed'] else 'fail' for c in RESULT['checks']))
  (OUT/'results.json').write_text(json.dumps(RESULT,indent=2,ensure_ascii=False)+'\n')
  print('Results: '+str(OUT/'results.json'))
  print('Stopped isolated sandbox; synthetic volumes retained: '+PROJECT)
 sys.exit(1 if failed else 0)
