"""Package frozen test scores into a self-contained offline classroom HTML."""
from pathlib import Path
from collections import defaultdict
import argparse,csv,hashlib,json
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
COLUMNS=['minute','valid','voltage_residual_v','channel_difference_v','temperature_residual_c','rule_score','logistic_score','isolation_score','class_prediction','class_confidence','label']
def build(results):
    m=json.loads((results/'metrics.json').read_text(encoding='utf-8'));cases=defaultdict(list)
    with (results/'test_scores.csv').open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            vals=[]
            for k in COLUMNS:
                if k=='minute':v=int(r[k])
                elif k=='valid':v=r[k]=='True'
                elif k in ['class_prediction','label']:v=r[k]
                else:v=float(r[k]) if r[k] else None
                vals.append(v)
            cases[r['session_id']].append(vals)
    with (results/'events.csv').open(encoding='utf-8',newline='') as f:events=[dict(session_id=r['session_id'],start_min=int(r['start_min']),end_min=int(r['end_min']),kind=r['kind']) for r in csv.DictReader(f) if r['split']=='test']
    data=dict(columns=COLUMNS,cases=dict(cases),events=events,selected=m['selected'],metrics=m['metrics'],source_sha256={n:hashlib.sha256((results/n).read_bytes()).hexdigest() for n in ['test_scores.csv','events.csv','metrics.json']})
    dest=REPO/'demo/ch03';(dest/'data.js').write_text('window.CH03_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False)+';\n',encoding='utf-8')
    html=(dest/'index.html').read_text(encoding='utf-8')
    for name in ['data.js','math.js','app.js']:html=html.replace(f'<script src="{name}"></script>','<script>'+(dest/name).read_text(encoding='utf-8').replace('</script',r'<\/script')+'</script>')
    html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+(dest/'style.css').read_text(encoding='utf-8')+'</style>')
    (dest/'教学演示.html').write_text(html,encoding='utf-8');print(f'Offline demo: {len(cases)} test sessions, {sum(map(len,cases.values()))} frozen score rows');return data
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=ROOT/'reference_results');a=p.parse_args();build(a.results)
