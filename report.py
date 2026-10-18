"""Informes diarios y mensuales: predicciones, nunca llegadas reales certificadas."""
import json, datetime as dt, re
from pathlib import Path
from collections import defaultdict
P=Path(__file__).parent/'data'
def load(name, default):
 try:return json.loads((P/name).read_text(encoding='utf-8'))
 except (OSError,ValueError):return default
schedule=load('schedule.json',{})
index=load('c1_index.json',{})
known=index.get('trips',{})
days=defaultdict(dict)
folder=P/'observations'
for filename in sorted(folder.glob('*.jsonl')) if folder.exists() else []:
 for line in filename.read_text(encoding='utf-8').splitlines():
  try:o=json.loads(line)
  except (ValueError,TypeError):continue
  key=o.get('key','')
  if '|' not in key:continue
  day,tid=key.split('|',1)
  if len(day)!=8 or not day.isdigit():continue
  vals=[v.get('delay_seconds') for v in o.get('delays',[]) if isinstance(v.get('delay_seconds'),(int,float))]
  previous=days[day].get(key)
  if not previous:
   si=schedule.get(key,{})
   meta=known.get(tid,{})
   stops=si.get('stops',[])
   previous={'theoretical_departure':(stops[0].get('departure') if stops else None) or (meta.get('stops',[{}])[0].get('departure') if meta.get('stops') else None),'theoretical_arrival':(stops[-1].get('arrival') if stops else None) or (meta.get('stops',[{}])[-1].get('arrival') if meta.get('stops') else None),'max_delay_stop':'','max_delay_event':'','trip':tid,'train':(re.search(r'269[0-9]{2}',tid).group(0) if re.search(r'269[0-9]{2}',tid) else tid),'origin':(stops[0].get('stop') if stops else meta.get('origin')) or 'Sin determinar','destination':(stops[-1].get('stop') if stops else meta.get('destination')) or 'Sin determinar','max_delay_seconds':None,'latest_delay_seconds':None,'captured_at':o.get('captured_at',''),'observations':0,'calendar_matched':bool(o.get('calendar_matched')),'cancelled_reported':False}
   days[day][key]=previous
  previous['observations']+=1
  previous['calendar_matched']=previous['calendar_matched'] or bool(o.get('calendar_matched'))
  if o.get('status','').upper() in ('CANCELED','CANCELLED'):previous['cancelled_reported']=True
  if vals:
   mx=max(vals)
   if previous['max_delay_seconds'] is None or mx>previous['max_delay_seconds']:
    previous['max_delay_seconds']=mx
    ev=next((v for v in o.get('delays',[]) if v.get('delay_seconds')==mx),{})
    known_stops={v.get('id'):v.get('name') for v in known.get(tid,{}).get('stops',[])}
    previous['max_delay_stop']=known_stops.get(ev.get('stop_id'),ev.get('stop_id') or '')
    previous['max_delay_event']=ev.get('event','')
   if o.get('captured_at','')>=previous['captured_at']:previous['latest_delay_seconds']=mx
  if o.get('captured_at','')>previous['captured_at']:previous['captured_at']=o['captured_at']
daily=[]
for day,trains in sorted(days.items()):
 ranked=sorted(trains.values(),key=lambda t:t['max_delay_seconds'] if t['max_delay_seconds'] is not None else -999999,reverse=True)
 expected=sum(k.startswith(day+'|') for k in schedule)
 delay_known=[t for t in ranked if t['max_delay_seconds'] is not None]
 basis_values={v.get('basis','GTFS calendar') for k,v in schedule.items() if k.startswith(day+'|')}
 verified=bool(expected and basis_values=={'GTFS calendar'})
 inferred=bool(expected and 'GTFS calendar' not in basis_values)
 daily.append({'day':day,'scheduled':expected if expected else None,'scheduled_basis':'GTFS con calendario acreditado' if verified else 'Grupo de servicios deducido de GTFS-RT; no es calendario verificado' if inferred else 'Datos incompletos','observed_trains':len(ranked),'observed_with_delay':len(delay_known),'coverage_pct':round(100*len(ranked)/expected,1) if verified else None,'sample_coverage_pct':round(100*len(ranked)/expected,1) if inferred else None,'ranking':ranked,'over_5min':sum(t['max_delay_seconds']>300 for t in delay_known),'over_15min':sum(t['max_delay_seconds']>900 for t in delay_known),'mean_peak_delay_minutes':round(sum(t['max_delay_seconds'] for t in delay_known)/60/len(delay_known),1) if delay_known else None,'cancelled_reported':sum(t['cancelled_reported'] for t in ranked)})
months=defaultdict(list)
for d in daily:months[d['day'][:6]].append(d)
monthly=[]
for month,arr in sorted(months.items()):
 unique=defaultdict(lambda:{'days':set(),'max_delay_seconds':None,'over_5min_days':0})
 for d in arr:
  for t in d['ranking']:
   a=unique[t['trip']]
   a['days'].add(d['day'])
   mx=t['max_delay_seconds']
   if mx is not None and (a['max_delay_seconds'] is None or mx>a['max_delay_seconds']):a['max_delay_seconds']=mx
   if mx is not None and mx>300:a['over_5min_days']+=1
 worst=sorted(({'trip':tid,'observed_days':len(v['days']),'max_delay_seconds':v['max_delay_seconds'],'days_over_5min':v['over_5min_days']} for tid,v in unique.items()),key=lambda r:(r['days_over_5min'],r['max_delay_seconds'] if r['max_delay_seconds'] is not None else -1),reverse=True)
 monthly.append({'month':month,'days_observed':len(arr),'trains_observed':sum(d['observed_trains'] for d in arr),'over_5min':sum(d['over_5min'] for d in arr),'over_15min':sum(d['over_15min'] for d in arr),'cancelled_reported':sum(d['cancelled_reported'] for d in arr),'worst_trains':worst[:30]})
(P/'dashboard.json').write_text(json.dumps({'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'days':daily,'months':monthly,'status':load('status.json',{}),'methodology':'GTFS-RT Renfe: máxima demora prevista observada, no llegada real acreditada. Los grupos de servicios inferidos de GTFS-RT no son un calendario completo verificado. La ausencia de datos no demuestra puntualidad ni supresión.'},ensure_ascii=False),encoding='utf-8')
