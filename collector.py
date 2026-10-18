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
  # Identificar primero por recorrido real; la etiqueta comercial C1 puede
  # no aparecer como route_short_name en el GTFS.
  def normalise(value):
   import unicodedata
   return ''.join(ch for ch in unicodedata.normalize('NFKD',str(value).upper()) if ch.isalnum() and not unicodedata.combining(ch))
  stop_times=rows(z,'stop_times.txt')
  # Normalizar secuencia GTFS incluso si el campo falta o viene vacío.
  for i,st in enumerate(stop_times):
   try: st['_safe_sequence']=int(st.get('stop_sequence') or i)
   except (TypeError,ValueError): st['_safe_sequence']=i
  trip_route={t['trip_id']:t['route_id'] for t in trips}
  route_stops={}
  for s in stop_times:
   route=trip_route.get(s['trip_id'])
   if route is not None:route_stops.setdefault(route,set()).add(s['stop_id'])
  route_names={r['route_id']:r for r in routes}
  selected=set()
  for route,ids in route_stops.items():
   names={normalise(stopnames.get(x,'')) for x in ids}
   if 'SANTANDER' in names and 'REINOSA' in names:
    selected.add(route)
  if not selected:
   preview=[{'id':r.get('route_id'),'short':r.get('route_short_name'),'long':r.get('route_long_name')} for r in routes if 'C1' in normalise(' '.join(str(r.get(k,'')) for k in ('route_id','route_short_name','route_long_name')))][:30]
   near={str(route): sorted({stopnames.get(s,'') for s in ids if 'SANTANDER' in normalise(stopnames.get(s,'')) or 'REINOSA' in normalise(stopnames.get(s,''))}) for route,ids in route_stops.items()}
   near={k:v for k,v in near.items() if v}
   raise RuntimeError('GTFS sin recorrido acreditado Santander–Reinosa; no se guardan datos de otra línea. Rutas C1: '+json.dumps(preview,ensure_ascii=False)+'; rutas con estaciones relevantes: '+json.dumps(near,ensure_ascii=False))
  print('Rutas Santander–Reinosa identificadas por paradas: '+json.dumps([{'id':r,'short':route_names.get(r,{}).get('route_short_name'),'long':route_names.get(r,{}).get('route_long_name')} for r in sorted(selected)],ensure_ascii=False))
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
    return bool(c and c.get('start_date') and c.get('end_date') and c['start_date']<=d<=c['end_date'] and c.get(weekday)=='1')
   for tripid,t in chosen.items():
    if active(t['service_id']):result[d+'|'+tripid]={'day':d,'trip':tripid,'headsign':t.get('trip_headsign',''),'route':t['route_id'],'stops':[]}
   for s in stop_times:
    k=d+'|'+s['trip_id']
    if k in result:result[k]['stops'].append({'stop':stopnames.get(s['stop_id'],s['stop_id']),'id':s['stop_id'],'seq':s['_safe_sequence'],'arrival':s.get('arrival_time',''),'departure':s.get('departure_time','')})
  for t in result.values():t['stops'].sort(key=lambda s:s['seq'])
  if not result:
   samples=[{'service_id':k,'fields':list(v.keys()),'start_date':v.get('start_date'),'end_date':v.get('end_date')} for k,v in list(calendar.items())[:5]]
   print('AVISO: calendario GTFS sin servicios activos para hoy/mañana. Se conservará el catálogo de rutas/trenes C1 y solo se recogerán observaciones identificadas por el GTFS; NO se considerará una ausencia como supresión. Diagnóstico: '+json.dumps({'calendar_records':len(calendar),'calendar_dates_records':len(exceptions),'selected_trips':len(chosen),'calendar_sample':samples},ensure_ascii=False))
  # Índice verificable por viaje, incluida la sucesión real de paradas.
  trip_stops={}
  for s in stop_times:
   tid=s['trip_id']
   if tid in chosen:trip_stops.setdefault(tid,[]).append(s)
  trip_info={}
  for tid,t in chosen.items():
   ss=sorted(trip_stops.get(tid,[]),key=lambda x:x['_safe_sequence'])
   trip_info[tid]={'route':t['route_id'],'service_id':t['service_id'],'headsign':t.get('trip_headsign',''),'origin':stopnames.get(ss[0]['stop_id'],'') if ss else '', 'destination':stopnames.get(ss[-1]['stop_id'],'') if ss else '', 'stops':[{'id':s['stop_id'],'name':stopnames.get(s['stop_id'],''),'seq':s['_safe_sequence'],'arrival':s.get('arrival_time',''),'departure':s.get('departure_time','')} for s in ss]}
  (P/'c1_index.json').write_text(json.dumps({'route_ids':sorted(selected),'trip_ids':sorted(chosen),'trips':trip_info,'calendar_covered':bool(result)},ensure_ascii=False))
  cache=P/'schedule.json'
  old=json.loads(cache.read_text()) if cache.exists() else {}
  for k,v in result.items():old.setdefault(k,v)
  cache.write_text(json.dumps(old,ensure_ascii=False))
  # Guardar huella y fuente; no versionar ZIP voluminosos cada cinco minutos
  (P/'schedule_source.json').write_text(json.dumps({'url':url,'sha256':hashlib.sha256(blob).hexdigest(),'checked_at':now.isoformat()},ensure_ascii=False))
  return old
def main():
 try:
  cache=P/'schedule.json'
  index=P/'c1_index.json'
  # Migración: reconstruir un índice antiguo sin horas previstas de las paradas.
  missing_times = True
  if index.exists():
   oldidx=json.loads(index.read_text())
   sample=next(iter(oldidx.get('trips',{}).values()),{})
   missing_times=bool(sample.get('stops')) and 'arrival' not in sample['stops'][0]
  s=schedule() if not cache.exists() or cache.stat().st_size < 5 or not index.exists() or missing_times or now.hour==3 else json.loads(cache.read_text())
  if not index.exists():raise RuntimeError('Índice de rutas C1 inexistente; no se guardarán observaciones de otras líneas')
  allowed=json.loads(index.read_text())
  allowed_trips=set(allowed.get('trip_ids',[]))
  allowed_routes=set(allowed.get('route_ids',[]))
  if not allowed_trips or not allowed_routes:raise RuntimeError('Índice C1 sin identificadores verificables')
  url=os.getenv('TRIP_UPDATES_JSON_URL') or resolve('horarios-viaje-cercanias','trip_updates.json')
  payload=fetch(url).json()
  entities=payload.get('entity',payload.get('entities',[]))
  if isinstance(entities,dict):entities=list(entities.values())
  results=[]
  for e in entities:
   update=e.get('tripUpdate',e.get('trip_update',{}))
   tr=update.get('trip',{});tid=tr.get('tripId',tr.get('trip_id',''))
   d=tr.get('startDate',tr.get('start_date',day));key=d+'|'+tid
   rid=tr.get('routeId',tr.get('route_id',''))
   # La ruta y el trip_id deben estar acreditados por el recorrido; route_id por sí solo no demuestra el itinerario completo.
   if key not in s and tid not in allowed_trips:continue
   if rid and rid not in allowed_routes:continue
   stops=update.get('stopTimeUpdate',update.get('stop_time_update',[]))
   delays=[]
   events=[]
   for v in stops:
    sid=v.get('stopId',v.get('stop_id'))
    for kind in ('arrival','departure'):
     a=v.get(kind) or {}
     if not isinstance(a,dict):continue
     event={'stop_id':sid,'event':kind}
     for name in ('delay','time','uncertainty'):
      value=a.get(name)
      if isinstance(value,(int,float)):event[name]=value
     if len(event)>2:
      events.append(event)
      if isinstance(event.get('delay'),(int,float)):delays.append({'stop_id':sid,'event':kind,'delay_seconds':event['delay']})
   results.append({'key':key,'captured_at':now.isoformat(),'status':tr.get('scheduleRelationship',tr.get('schedule_relationship','SCHEDULED')),'delays':delays,'kind':'GTFS-RT estimación/no llegada real','calendar_matched':key in s and 'basis' not in s[key],'schedule_linked':key in s,'source':'Renfe GTFS-RT','trip_id':tid,'events':events,'feed_timestamp':update.get('timestamp')})
  folder=P/'observations';folder.mkdir(exist_ok=True)
  # El calendario del GTFS de Renfe puede faltar o no abarcar la fecha actual.
  # Un trip_id exacto publicado por GTFS-RT permite identificar su service_id
  # en GTFS estático. La relación prueba el servicio observado, pero NO acredita
  # que todos los viajes del grupo circularan ni su puntualidad final.
  inferred_file=P/'inferred_services.json'
  inferred=json.loads(inferred_file.read_text()) if inferred_file.exists() else {}
  weekday_codes=('L','M','X','J','V','S','D')
  newly_inferred=0
  for result in results:
   obs_day,tid=result['key'].split('|',1)
   meta=allowed['trips'].get(tid,{})
   sid=meta.get('service_id','')
   try: correct_day=sid.endswith(weekday_codes[dt.datetime.strptime(obs_day,'%Y%m%d').weekday()])
   except ValueError: correct_day=False
   if not correct_day:continue
   if sid not in inferred.setdefault(obs_day,[]):inferred[obs_day].append(sid)
  for obs_day,services in inferred.items():
   for tid,meta in allowed['trips'].items():
    if meta.get('service_id') not in services:continue
    key=obs_day+'|'+tid
    if key in s:continue
    stops=meta.get('stops',[])
    if not stops or 'arrival' not in stops[0]:continue
    s[key]={'day':obs_day,'trip':tid,'headsign':meta.get('headsign',''),'route':meta['route'],'stops':[{'stop':v['name'],'id':v['id'],'seq':v.get('seq',i),'arrival':v.get('arrival',''),'departure':v.get('departure','')} for i,v in enumerate(stops)],'basis':'servicio deducido de trip_id GTFS-RT; calendario no acreditado'}
    newly_inferred+=1
  if newly_inferred:
   cache.write_text(json.dumps(s,ensure_ascii=False))
  inferred_file.write_text(json.dumps(inferred,ensure_ascii=False))
  if results:
   with (folder/(day+'.jsonl')).open('a') as f:
    for result in results:f.write(json.dumps(result,ensure_ascii=False)+'\n')
  status={'checked_at':now.isoformat(),'feed_entities':len(entities),'c1_observations':len(results),'calendar_matched':sum(1 for v in results if v['calendar_matched']),'calendar_unmatched':sum(1 for v in results if not v['calendar_matched']),'schedule_linked':sum(1 for v in results if v['schedule_linked']),'inferred_services_today':inferred.get(day,[]),'inferred_scheduled_candidates':sum(1 for k in s if k.startswith(day+'|')),'schedule_basis':'calendario GTFS oficial o, si no existe, grupo de servicio acreditado por GTFS-RT; no equivalen','error':None}
  print(status)
 except Exception as exc:
  status={'checked_at':now.isoformat(),'error':str(exc)}
  (P/'status.json').write_text(json.dumps(status,ensure_ascii=False))
  raise
 (P/'status.json').write_text(json.dumps(status,ensure_ascii=False))
if __name__=='__main__':main()
