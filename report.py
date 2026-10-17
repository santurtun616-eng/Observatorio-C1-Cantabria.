import json,datetime as dt
from collections import defaultdict
from pathlib import Path
P=Path(__file__).parent/'data'
def load(filename,default):
 try:return json.loads((P/filename).read_text())
 except (OSError,ValueError):return default
schedule=load('schedule.json',{})
days=defaultdict(dict)
for filename in sorted((P/'observations').glob('*.jsonl')) if (P/'observations').exists() else []:
 for line in filename.read_text().splitlines():
  try:o=json.loads(line)
  except ValueError:continue
  k=o['key']; day=k.split('|')[0];delays=[x['delay_seconds'] for x in o.get('delays',[]) if isinstance(x.get('delay_seconds'),(int,float))]
  prev=days[day].get(k)
  # Máxima demora observada por circulación, no demora final certificada
  if delays:
   mx=max(delays)
   if prev is None or mx>prev['max_delay_seconds']:
    s=schedule.get(k,{})
    stops=s.get('stops',[])
    days[day][k]={'trip':k.split('|',1)[1],'origin':stops[0]['stop'] if stops else '?','destination':stops[-1]['stop'] if stops else s.get('headsign','?'),'max_delay_seconds':mx,'captured_at':o['captured_at']}
daily=[]
for day,trains in sorted(days.items()):
 expected=sum(1 for k in schedule if k.startswith(day+'|'))
 ranked=sorted(trains.values(),key=lambda t:t['max_delay_seconds'],reverse=True)
 daily.append({'day':day,'scheduled':expected,'observed_with_delay':len(trains),'coverage_pct':round(100*len(trains)/expected,1) if expected else None,'ranking':ranked,'over_5min':sum(t['max_delay_seconds']>300 for t in ranked)})
(P/'dashboard.json').write_text(json.dumps({'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'days':daily,'status':load('status.json',{})},ensure_ascii=False))
