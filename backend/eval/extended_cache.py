"""Sequential matched cache trials after content runs and their grading finish."""
import argparse,copy,json,time,uuid,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from common import read_json,read_jsonl,write_json
from extended_run import Capture as Recorder
from app.product.config import get_settings

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();root=args.run
    while not (root/'outcomes.json').exists():time.sleep(5)
    outcomes=read_json(root/'outcomes.json')
    pending=[r['id'] for r in outcomes if not r.get('delivery') and r['variant']!='generic' and any(x.get('operation')=='preparation_synthesis' and x.get('status_code')==200 for x in read_jsonl(root/r['id']/'responses.jsonl'))]
    while any(not (root/'raw_review'/name/'result.json').exists() for name in pending):time.sleep(5)
    out=root/'cache';out.mkdir(exist_ok=True);settings=get_settings();chosen=[]
    for name in ('E11-full-1','E12-full-1','E13-full-1'):
        requests=read_jsonl(root/name/'requests.jsonl')
        for operation in ('preconsultation_extraction','preparation_synthesis'):
            chosen.append((name,operation,next(r['body_json'] for r in requests if r['operation']==operation)))
    recorder=Recorder(out,base_url=settings.openai_base_url,live=True,max_calls=66,max_reserved_output_tokens=1000000)
    results=[]
    with recorder.installed():
        for index,(name,operation,payload) in enumerate(chosen):
            payload=copy.deepcopy(payload)
            # Same namespace in all conditions in this block; unique to this block.
            namespace='Evaluation namespace '+uuid.uuid4().hex+' (metadata only; ignore).\n'
            payload['input'][0]['content'][0]['text']=namespace+payload['input'][0]['content'][0]['text']
            plain=copy.deepcopy(payload)
            for message in plain['input']:
                for part in message.get('content',[]):
                    if isinstance(part,dict):part.pop('prompt_cache_breakpoint',None)
            conditions=[('cold',payload)]+[(label,body) for _ in range(5) for label,body in [('unmarked',plain),('warm',payload)]]
            for n,(condition,body) in enumerate(conditions):
                started=time.perf_counter()
                with recorder.job(case_id=name,job_id=f'cache-{index}-{n}',operation=operation):
                    try:
                        response=httpx.post(settings.openai_base_url.rstrip('/')+'/responses',headers={'Authorization':'Bearer '+settings.openai_api_key},json=body,timeout=90)
                        data=response.json();row={'block':index,'source_trial':name,'operation':operation,'condition':condition,'status_code':response.status_code,'provider_status':data.get('status'),'usage':data.get('usage'),'seconds':time.perf_counter()-started}
                    except Exception as exc:row={'block':index,'condition':condition,'error_type':type(exc).__name__,'seconds':time.perf_counter()-started}
                results.append(row);write_json(out/'results.json',results);print(json.dumps({k:row.get(k) for k in ('block','condition','status_code','seconds')}),flush=True)
                if recorder.quota_marker.exists():return
if __name__=='__main__':main()
