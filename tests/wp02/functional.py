#!/usr/bin/env python3
"""Synthetic single-admin functional characterization; never targets real data."""
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests/wp01'))
from helpers import Client, api_add, items

LOCK = json.loads((ROOT/'tests/lubelogger/target.lock.json').read_text())
COMPOSE = ROOT/'tests/lubelogger/compose.sandbox.yaml'
PROJECT = 'wolfs-wp02-' + secrets.token_hex(5)
OUT = ROOT/'.sandbox'/PROJECT
OUT.mkdir(parents=True,mode=0o700)
os.chmod(OUT,0o700)
RESULT = {'project':PROJECT,'startedAt':datetime.now().astimezone().isoformat(),
          'image':LOCK['image'],'sourceRevision':LOCK['sourceRevision'],
          'tests':[],'observations':{}}


def dc(*args):
    return subprocess.check_output(['docker','compose','-p',PROJECT,'-f',str(COMPOSE),*args],text=True).strip()


def start():
    dc('up','-d','lubelogger')
    cid=dc('ps','-q','lubelogger')
    meta=json.loads(subprocess.check_output(['docker','inspect',cid]))[0]
    image=json.loads(subprocess.check_output(['docker','image','inspect',LOCK['image']]))[0]
    assert meta['Image']==image['Id'] and not meta['HostConfig'].get('PortBindings')
    net=next(iter(meta['NetworkSettings']['Networks'].values()))
    network=json.loads(subprocess.check_output(['docker','network','inspect',net['NetworkID']]))[0]
    assert network['Internal'] is True
    base='http://'+net['IPAddress']+':8080'
    for _ in range(60):
        try:
            if Client(base).call('/')[0]==200:
                return base
        except (OSError,urllib.error.URLError):
            pass
        time.sleep(0.3)
    raise AssertionError('startup timeout')


def check(name,condition,detail=None,gap=False):
    state=('gap' if gap else 'pass') if condition else 'fail'
    RESULT['tests'].append({'name':name,'status':state,'detail':detail})
    print(state.upper()+': '+name,flush=True)
    if not condition:raise AssertionError(name)


class CostTable(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.footer=False
        self.cell=None
        self.cells=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='tfoot':self.footer=True
        if tag=='td' and self.footer and 'report-year' in attrs:
            self.cell={'year':int(attrs['report-year']),'kind':attrs.get('report-data'),'text':''}
    def handle_data(self,data):
        if self.cell is not None:self.cell['text']+=data
    def handle_endtag(self,tag):
        if tag=='td' and self.cell is not None:
            self.cell['text']=self.cell['text'].strip()
            self.cells.append(self.cell)
            self.cell=None
        if tag=='tfoot':self.footer=False


def report(client,vehicle,metrics,year=0):
    response=client.call('/Vehicle/GetCostByMonthAndYearByVehicle',method='POST',
                         form={'vehicleId':vehicle,'selectedMetrics':metrics,'year':year})
    assert response[0]==200,('report HTTP',response[0])
    parser=CostTable()
    parser.feed(response[2].decode())
    return parser.cells


def costs(cells):
    result={}
    for c in cells:
        if c['kind']=='cost':
            s=c['text'].replace('\xa0','').replace('€','').replace(' ','').replace('.','').replace(',','.')
            result[c['year']]=str(Decimal(s))
    return result


def settings(client,use_mpg):
    value=client.get('/Home/WriteToSettings',method='POST',form={'UseMPG':str(use_mpg).lower(),
        'EnableAutoReminderRefresh':'false','EnableAutoOdometerInsert':'false','EnableAuth':'false'})
    assert value is True
    time.sleep(0.6)  # root settings are read through the asynchronously reloaded configuration.


def run():
    base=start()
    client=Client(base)
    check('isolated admin baseline has five-vehicle setup capability',client.call('/api/vehicles')[0]==200,
          {'note':'Auth-disabled isolated upstream baseline; NOT a Cloudflare test'})
    settings(client,False)
    vehicles=[]
    for n in range(1,6):
        body={'Year':2020,'Make':'Synthetic','Model':'WP02-Car-'+str(n),
              'LicensePlate':'SYNTH-WP02-'+str(n),'UseEngineHours':n==5,
              'ExtraFields':[{'Name':'Motorisierung','Value':'synthetic-engine-'+str(n)}]}
        result=client.ok('/api/vehicles/add',method='POST',data=body)
        vehicles.append(result['additionalData']['vehicleId'])
    v,other,recurring,zero_km,hours=vehicles
    rows=client.get('/api/vehicles')
    check('five synthetic vehicles and configurable powertrain field returned',len(rows)==5 and
          all(x['extraFields'][0]['value']=='synthetic-engine-'+str(n) for n,x in enumerate(rows,1)),
          {'vehicleIds':vehicles})
    check('hours flag stored per vehicle',rows[4]['useHours'] is True and all(not x['useHours'] for x in rows[:4]))
    status,_,html=client.call('/Home/Garage')
    check('fleet partial HTML contains all five vehicle models',status==200 and all(('WP02-Car-'+str(n)).encode() in html for n in range(1,6)),
          {'http':status,'modelsFound':5,'visualBrowserTest':False})
    for vid in vehicles:
        status,_,html=client.call('/Vehicle/Index?vehicleId='+str(vid))
        check('vehicle detail HTML renders',status==200 and b'Synthetic' in html,{'vehicleId':vid,'http':status,'visualBrowserTest':False})
    # Explicit service/repair/tax amounts in different years and a second vehicle.
    sid=api_add(client,'servicerecords',v,{'Date':'31.12.2025','Odometer':9000,'Description':'WP02-2025-service','Cost':100})
    api_add(client,'servicerecords',v,{'Date':'01.03.2026','Odometer':10100,'Description':'WP02-2026-service','Cost':30})
    api_add(client,'repairrecords',v,{'Date':'01.01.2026','Odometer':10000,'Description':'WP02-2026-repair','Cost':40})
    api_add(client,'taxrecords',v,{'Date':'20.02.2026','Description':'WP02-2026-tax','Cost':20})
    api_add(client,'servicerecords',other,{'Date':'01.03.2026','Odometer':1,'Description':'WP02-other-car','Cost':9999})
    supply=api_add(client,'supplyrecords',v,{'Date':'20.02.2026','Description':'WP02-part',
                   'PartNumber':'WP02-PART','PartQuantity':2,'Cost':20})
    client.ok('/Vehicle/SaveServiceRecordToVehicleId',method='POST',form={'VehicleId':v,'Date':'20.03.2026','Mileage':10200,
         'Description':'WP02-part-install','Cost':'15,00','Supplies[0].SupplyId':supply,'Supplies[0].Quantity':1})
    remaining=items(client,'supplyrecords',v)[0]
    installed=next(x for x in items(client,'servicerecords',v) if x['description']=='WP02-part-install')
    check('native requisition reduces stock and retains explicit total',remaining['partQuantity']==1 and
          remaining['cost']==10 and installed['cost']==15,{'quantityRemaining':remaining['partQuantity'],
          'stockCostRemaining':remaining['cost'],'explicitServiceCost':installed['cost']})
    report_rows=report(client,v,['ServiceRecord','RepairRecord','TaxRecord'])
    year_costs=costs(report_rows)
    RESULT['observations']['costFooter']=report_rows
    check('yearly cost report groups vehicle services repairs taxes without stock duplication',
          year_costs.get(2025)=='100.00' and year_costs.get(2026)=='105.00',year_costs)
    # The native garage bell requires default metric AND a non-zero last odometer.
    # All data and past-due dates are deliberately synthetic.
    for vid,n in ((other,2),(zero_km,4)):
        client.ok('/Vehicle/SaveVehicle',method='POST',form={'Id':vid,'Year':2020,'Make':'Synthetic',
                  'Model':'WP02-Car-'+str(n),'LicensePlate':'SYNTH-WP02-'+str(n),'DashboardMetrics':['Default']})
        api_add(client,'reminders',vid,{'Description':'WP02-past-due','Metric':'Date','DueDate':'01.01.2020'})
    info=client.get('/api/vehicle/info')
    byid={x['vehicleData']['id']:x for x in info}
    page=client.call('/Home/Garage')[2]
    def card(vid):
        marker=('id="gridVehicle_'+str(vid)+'"').encode()
        return page.split(marker,1)[1].split(b'id="gridVehicle_',1)[0]
    check('native garage bell appears for overdue reminder with nonzero mileage',
          byid[other]['pastDueReminderCount']>=1 and b'bi-bell-fill' in card(other))
    check('native garage bell absent for overdue reminder when mileage zero',
          byid[zero_km]['pastDueReminderCount']>=1 and b'bi-bell-fill' not in card(zero_km),
          {'vehicleId':zero_km,'pastDueCount':byid[zero_km]['pastDueReminderCount'],'lastOdometer':byid[zero_km]['lastReportedOdometer']},gap=True)
    # Stock purchase cannot be inferred from that report; explicit selection of SupplyRecord is ignored by this report.
    supply_only=costs(report(client,v,['SupplyRecord']))
    check('selected supplies are not standalone cash spending in cost report',supply_only.get(2026,'0') in ('0','0.00'),
          {'supplyOnly2026':supply_only.get(2026),'scope':'cost report; payment ledger not proven'},gap=True)
    # Odometer/history retained across global display unit changes; useHours per vehicle.
    for vid in (v,hours):
        api_add(client,'odometerrecords',vid,{'Date':'01.02.2026','InitialOdometer':100,'Odometer':500,'Notes':'WP02-unit-fixture'})
    before=items(client,'odometerrecords',v)
    kmcells=report(client,v,['OdometerRecord'],2026)
    hourcells=report(client,hours,['OdometerRecord'],2026)
    check('metric and engine-hours labels are different in rendered report',
          any(c['kind']=='distance' and c['text'].endswith('km') for c in kmcells) and
          any(c['kind']=='distance' and c['text'].endswith('h') for c in hourcells),
          {'metricFooter':kmcells,'hoursFooter':hourcells})
    settings(client,True)
    micells=report(client,v,['OdometerRecord'],2026)
    after=items(client,'odometerrecords',v)
    check('switching global display to miles leaves stored odometer numbers unchanged',before==after and
          any(c['kind']=='distance' and c['text'].endswith('mi.') for c in micells),
          {'readingBefore':before,'readingAfter':after,'milesFooter':micells},gap=True)
    settings(client,False)
    # Native UI JavaScript automatically calls tax check when opening vehicle page; plain HTTP does not run JS.
    today=datetime.now(ZoneInfo('Europe/Berlin')).date()
    client.ok('/Vehicle/SaveTaxRecordToVehicleId',method='POST',form={'VehicleId':recurring,
        'Date':(today+timedelta(days=20)).strftime('%d.%m.%Y'),'Description':'WP02-recurring-fee','Cost':'10,00',
        'IsRecurring':'true','RecurringInterval':'OneMonth'})
    tax=items(client,'taxrecords',recurring)[0]
    client.ok('/api/vehicle/taxrecords/update',method='PUT',data={'Id':tax['id'],
        'Date':(today-timedelta(days=65)).strftime('%d.%m.%Y'),'Description':'WP02-recurring-fee','Cost':10})
    before_tax=items(client,'taxrecords',recurring)
    code,_,page=client.call('/Vehicle/Index?vehicleId='+str(recurring))
    assert code==200
    after_html=items(client,'taxrecords',recurring)
    code,value,_=client.call('/Vehicle/CheckRecurringTaxRecords?vehicleId='+str(recurring),method='POST',form={})
    after_tax=items(client,'taxrecords',recurring)
    check('tax recurrence check adds cost records without a separate payment confirmation',
          b'checkRecurringTaxes();' in page and len(before_tax)==len(after_html)==1 and code==200 and len(after_tax)>1,
          {'before':len(before_tax),'afterHtmlWithoutJs':len(after_html),'afterDirectCheck':len(after_tax),
           'jsWasExecuted':False,'directCheckReturn':value},gap=True)
    # Single record update preserves only current API data; do not imply no other history exists.
    client.ok('/api/vehicle/servicerecords/update',method='PUT',data={'Id':sid,'Date':'31.12.2025',
        'Odometer':9000,'Description':'WP02-2025-service-corrected','Cost':110})
    current=items(client,'servicerecords',v)
    updated=[x for x in current if x['id']==sid]
    check('service API returns current corrected record, not previous values',len(updated)==1 and
          updated[0]['cost']==110 and updated[0]['description']=='WP02-2025-service-corrected' and
          not any(x['description']=='WP02-2025-service' for x in current),
          {'oldValueIncludedInCurrentApiList':False,'fullAuditElsewhereRuledOut':False},gap=True)
    updated_report=costs(report(client,v,['ServiceRecord','RepairRecord','TaxRecord']))
    check('correction updates prior-year cost total without duplicate',updated_report.get(2025)=='110.00' and updated_report.get(2026)=='105.00',updated_report)


if __name__=='__main__':
    failed=False
    try:
        run()
    except Exception as exc:
        failed=True
        RESULT['error']={'type':type(exc).__name__,'message':str(exc)}
        print('FAIL: '+str(exc),file=sys.stderr)
    finally:
        try:
            dc('stop')
            RESULT['containersStopped']=True
        except Exception:
            RESULT['containersStopped']=False
            failed=True
        RESULT['finishedAt']=datetime.now().astimezone().isoformat()
        RESULT['scriptSha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        RESULT['helperSha256']=hashlib.sha256((ROOT/'tests/wp01/helpers.py').read_bytes()).hexdigest()
        RESULT['composeSha256']=hashlib.sha256(COMPOSE.read_bytes()).hexdigest()
        (OUT/'results.json').write_text(json.dumps(RESULT,indent=2,ensure_ascii=False)+'\n')
        print('Results: '+str(OUT/'results.json'))
        print('Stopped synthetic project: '+PROJECT)
    sys.exit(1 if failed else 0)
