"""Recogida verificable GTFS de Cercanías (no confundir predicción con llegada real)."""
import os,io,csv,json,zipfile,hashlib,datetime as dt
from zoneinfo import ZoneInfo
from pathlib import Path
import requests
P=Path(__file__).parent/'data';P.mkdir(exist_ok=True)
now=dt.datetime.now(ZoneInfo('Europe/Madrid')); day=now.strftime('%Y%m%d')
session=requests.Session();session.headers['User-Agent']='Observatorio-C1-Cantabria/1.0'
API='https://data.renfe.com/api/3/action/package_show'
def fetch(url):
 r=session.get(url,timeout=35);r.raise_for_status();return r
def catalog(pkg):
 data=session.get(API,params={'id':pkg},timeout=35);data.raise_for_status()
 j=data.json()
 if not j.get('success'):raise RuntimeError('Catálogo Renfe sin respuesta')
 return j['result']['resources']
def resolve(pkg,kind):
 items=catalog(pkg)
 for r in items:
  desc=' '.join(str(r.get(k,'')) for k in ('name','format','url')).lower()
  if kind in desc:return r['url']
 raise RuntimeError('No se encontró recurso '+kind+' en '+pkg)
def rows(z,name):
 filename=next(x for x in z.namelist() if x.endswith(name))
 return list(csv.DictReader(io.TextIOWrapper(z.open(filename),encoding='utf-8-sig')))
def schedule():
 url=os.getenv('GTFS_STATIC_URL') or resolve('horarios-cercanias','.zip')
 blob=fetch(url).content
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  routes=rows(z,'routes.txt');trips=rows(z,'trips.txt');stops=rows(z,'stops.txt')
  stopnames={x['stop_id']:x.get('stop_name','') for x in stops}
  # Renfe puede publicar el identificador como C1 o C-1.
  def line_label(value):return ''.join(ch for ch in str(value).upper() if ch.isalnum())
  candidates={x['route_id'] for x in routes if line_label(x.get('route_short_name',''))=='C1'}
  trip_routes={t['trip_id']:t['route_id'] for t in trips if t['route_id'] in candidates}
  stop_times=rows(z,'stop_times.txt');rs={}
  for s in stop_times:
   if s['trip_id'] in trip_routes:rs.setdefault(trip_routes[s['trip_id']],set()).add(s['stop_id'])
  selected=set()
  for route,ids in rs.items():
   names=' '.join(stopnames.get(x,'').lower() for x in ids)
   if 'santander' in names and 'reinosa' in names:selected.add(route)
  if not selected:
   preview=[{'id':r.get('route_id'), 'short':r.get('route_short_name'), 'long':r.get('route_long_name')} for r in routes if r['route_id'] in candidates][:15]
   raise RuntimeError('No se puede acreditar ruta C1 Santander–Reinosa. Rutas candidatas: '+json.dumps(preview,ensure_ascii=False)+'; coincidencias con estaciones en dichas rutas: '+json.dumps({k:sorted({stopnames.get(s,'') for s in v if 'santander' in stopnames.get(s,'').lower() or 'reinosa' in stopnames.get(s,'').lower()}) for k,v in rs.items()},ensure_ascii=False))
  chosen={t['trip_id']:t for t in trips if t['route_id'] in selected}
  calendar={}
  try:
   for c in rows(z,'calendar.txt'):calendar[c['service_id']]=c
  except StopIteration:pass
  exceptions={}
  try:
   for e in rows(z,'calendar_dates.txt'):exceptions[(e['date'],e['service_id'])]=e['exception_type']
  except StopIteration:pass
  result={}
  for date in (now.date(),now.date()+dt.timedelta(days=1)):
   d=date.strftime('%Y%m%d');weekday=date.strftime('%A').lower()
   def active(service):
    override=exceptions.get((d,service))
    if override:return override=='1'
    c=calendar.get(service)
    return bool(c and c['start_date']<=d<=c['end_date'] and c.get(weekday)=='1')
   for tripid,t in chosen.items():
    if active(t['service_id']):result[d+'|'+tripid]={'day':d,'trip':tripid,'headsign':t.get('trip_headsign',''),'route':t['route_id'],'stops':[]}
   for s in stop_times:
    k=d+'|'+s['trip_id']
    if k in result:result[k]['stops'].append({'stop':stopnames.get(s['stop_id'],s['stop_id']),'id':s['stop_id'],'seq':int(s['stop_sequence']),'arrival':s.get('arrival_time',''),'departure':s.get('departure_time','')})
  for t in result.values():t['stops'].sort(key=lambda s:s['seq'])
  cache=P/'schedule.json'
  old=json.loads(cache.read_text()) if cache.exists() else {}
  for k,v in result.items():old.setdefault(k,v)
  cache.write_text(json.dumps(old,ensure_ascii=False))
  # Guardar huella y fuente; no versionar ZIP voluminosos cada cinco minutos
  (P/'schedule_source.json').write_text(json.dumps({'url':url,'sha256':hashlib.sha256(blob).hexdigest(),'checked_at':now.isoformat()},ensure_ascii=False))
  return old
def main():
 try:
  s=schedule() if not (P/'schedule.json').exists() or now.hour==3 else json.loads((P/'schedule.json').read_text())
  url=os.getenv('TRIP_UPDATES_JSON_URL') or resolve('horarios-viaje-cercanias','trip_updates.json')
  payload=fetch(url).json()
  entities=payload.get('entity',payload.get('entities',[]))
  if isinstance(entities,dict):entities=list(entities.values())
  results=[]
  for e in entities:
   update=e.get('tripUpdate',e.get('trip_update',{}))
   tr=update.get('trip',{});tid=tr.get('tripId',tr.get('trip_id',''))
   d=tr.get('startDate',tr.get('start_date',day));key=d+'|'+tid
   if key not in s:continue
   stops=update.get('stopTimeUpdate',update.get('stop_time_update',[]))
   delays=[]
   for v in stops:
    a=v.get('arrival') or v.get('departure') or {}
    if isinstance(a,dict) and isinstance(a.get('delay'),(int,float)):delays.append({'stop_id':v.get('stopId',v.get('stop_id')),'delay_seconds':a['delay']})
   results.append({'key':key,'captured_at':now.isoformat(),'status':tr.get('scheduleRelationship',tr.get('schedule_relationship','SCHEDULED')),'delays':delays,'kind':'GTFS-RT predicción'})
  folder=P/'observations';folder.mkdir(exist_ok=True)
  if results:
   with (folder/(day+'.jsonl')).open('a') as f:
    for result in results:f.write(json.dumps(result,ensure_ascii=False)+'\n')
  status={'checked_at':now.isoformat(),'feed_entities':len(entities),'c1_observations':len(results),'error':None}
  print(status)
 except Exception as exc:
  status={'checked_at':now.isoformat(),'error':str(exc)}
  (P/'status.json').write_text(json.dumps(status,ensure_ascii=False))
  raise
 (P/'status.json').write_text(json.dumps(status,ensure_ascii=False))
if __name__=='__main__':main()
