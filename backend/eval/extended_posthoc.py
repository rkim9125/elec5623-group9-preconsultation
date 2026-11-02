"""Blindly grade rejected raw summaries without changing delivered outcomes."""
import argparse,json,time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from common import read_json,read_jsonl,write_json
from grade import model_output
from extended_run import Capture,judge,prose
from app.product.config import get_settings

def assess(task):
    root,name,case=task;root=Path(root);p=root/name;out=read_json(p/'outcome.json')
    target=root/'raw_review'/name;target.mkdir(parents=True,exist_ok=True)
    responses=[r for r in read_jsonl(p/'responses.jsonl') if r.get('operation')=='preparation_synthesis' and r.get('status_code')==200]
    if not responses:return {'id':name,'status':'no_completed_synthesis'}
    data,_,issues=model_output(responses[-1]); result={'id':name,'source_call':responses[-1]['call_id'],'issues':issues}
    if not data:result['status']='unparseable';write_json(target/'result.json',result);return result
    candidate={**out,'final_text':prose(data)}
    recorder=Capture(target,base_url=get_settings().openai_base_url,live=True,max_calls=1,max_reserved_output_tokens=6000)
    with recorder.job(case_id=case['case_id'],job_id=name,operation='raw_judge'),recorder.installed():
        try:result.update(status='graded',judge=judge(case,candidate),raw_text=candidate['final_text'])
        except Exception as exc:result.update(status='error',error_type=type(exc).__name__)
    write_json(target/'result.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--corrected-grading',action='store_true');args=p.parse_args()
    if args.corrected_grading:
        from extended_grading import run
        run(args.run)
        raise SystemExit(0)
    manifest=read_json(args.run/'manifest.json');cases={c['case_id']:c for c in manifest['cases']};submitted=set();futures={}
    with ProcessPoolExecutor(max_workers=3) as pool:
        while len(submitted)<len(manifest['order']) or futures:
            for name in manifest['order']:
                if name in submitted or not (args.run/name/'outcome.json').exists():continue
                out=read_json(args.run/name/'outcome.json');submitted.add(name)
                if out.get('delivery') or out['variant']=='generic':continue
                if (args.run/'raw_review'/name/'result.json').exists():continue
                future=pool.submit(assess,(str(args.run.resolve()),name,cases[out['case_id']]))
                futures[future]=name
            for f in list(futures):
                if f.done():
                    print(json.dumps({k:v for k,v in f.result().items() if k in ('id','status','error_type')}),flush=True);del futures[f]
            if len(submitted)<len(manifest['order']) or futures:time.sleep(5)
