import subprocess,sys,json,time,urllib.error,secrets,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests/wp01'))
network=os.environ.get('GARAGE_TEST_NETWORK')
if not network:
 raise SystemExit('Set GARAGE_TEST_NETWORK to an empty internal sandbox network')
netinfo=json.loads(subprocess.check_output(['docker','network','inspect',network],text=True))[0]
if not netinfo.get('Internal') or netinfo.get('Containers'):
 raise SystemExit('Test network must be internal and empty')
from helpers import Client,api_add
name='wolfs-reminder-check-'+secrets.token_hex(4)
image='ghcr.io/hargata/lubelogger@sha256:483a9d7582c4e6258615fd822b3de4193b4fcc4230d0a92432c6d407faf75af2'
started=False
try:
 subprocess.run(['docker','run','-d','--name',name,'--network',network,'-e','TZ=Europe/Berlin','-e','LUBELOGGER_LOCALE_OVERRIDE=de-DE',image],check=True,stdout=subprocess.DEVNULL)
 started=True
 info=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
 assert not info['HostConfig'].get('PortBindings')
 ip=next(iter(info['NetworkSettings']['Networks'].values()))['IPAddress'];c=Client('http://'+ip+':8080')
 for _ in range(80):
  try:
   if c.call('/')[0]==200:break
  except (OSError,urllib.error.URLError):pass
  time.sleep(.25)
 else:raise Exception('startup timeout')
 result=c.ok('/api/vehicles/add',method='POST',data={'Year':2020,'Make':'Synthetic','Model':'ReminderCheck','LicensePlate':'SYNTH-CHECK'})
 v=result['additionalData']['vehicleId']
 api_add(c,'odometerrecords',v,{'Date':'26.10.2026','Odometer':12345,'InitialOdometer':12000,'Notes':'synthetic-reading'})
 api_add(c,'reminders',v,{'Metric':'Both','Description':'synthetic reminder','DueDate':'20.11.2026','DueOdometer':15000})
 def checksums():
  return subprocess.check_output(['docker','exec',name,'sh','-c','find /App/data -type f ! -name "*.log" -exec sha256sum {} + | sort'],text=True)
 time.sleep(2);before=checksums()
 assert before.strip(), 'no application data files found for comparison'
 print('Data files compared:',len(before.splitlines()))
 for i in range(5):
  status,data,_=c.call('/api/vehicle/reminders?vehicleId='+str(v));assert status==200 and len(data)==1
 time.sleep(2);after=checksums()
 print('Test container:',name)
 print('Synthetic vehicle and odometer seeded; five reminder GETs returned 200 with one reminder')
 print('Data-file checksums unchanged:',before==after)
 if before!=after:
  print('Differing paths:', [line.split('  ',1)[-1] for line in set(before.splitlines())^set(after.splitlines())])
  raise SystemExit(1)
 print('Runtime scope: one synthetic instance, current default settings; no backup/restore or live data tested')
finally:
 if started:
  subprocess.run(['docker','stop','-t','3',name],check=False,stdout=subprocess.DEVNULL)
  print('Test container stopped; synthetic resources retained')
