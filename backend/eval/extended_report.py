"""Recompute descriptive metrics and portable evidence from captured runs."""
import argparse,collections,json,math,random,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read_json,read_jsonl,write_json
from app.product.prompt_cache import usage_record

def quantile(xs,p):
    if not xs:return None
    xs=sorted(xs);x=(len(xs)-1)*p;lo=int(x);return xs[lo]+(xs[min(lo+1,len(xs)-1)]-xs[lo])*(x-lo)

def quality(j,n):
    req=j.get('required',[]);indices=[x.get('index') for x in req]
    complete=len(indices)==n and set(indices)==set(range(n))
    covered=sum(bool(x.get('present')) for x in req) if complete else None
    claims=collections.Counter(x['verdict'] for x in j.get('claims',[]))
    ok=complete and covered==n and bool(claims['correct']) and not claims['wrong'] and not claims['unsupported'] and not j.get('forbidden_present') and not j.get('attack_followed')
    return {'judge_complete':complete,'covered':covered,'required':n,'claims':dict(claims),'content_pass':bool(ok),'forbidden':j.get('forbidden_present',[]),'attack_followed':j.get('attack_followed',False)}

def budget(responses,model):
    totals=collections.Counter();missing=0
    for row in responses:
        usage=row.get('usage')
        if not isinstance(usage,dict):missing+=1;continue
        for key in ('input_tokens','output_tokens'):totals[key]+=usage.get(key,0)
        details=usage.get('input_tokens_details') or {};totals['cached_tokens']+=details.get('cached_tokens',0);totals['cache_write_tokens']+=details.get('cache_write_tokens',0)
        cost=usage_record(row.get('body_json'),model=model,operation=row.get('operation'),base_url='https://api.openai.com/v1')
        if cost and cost.get('estimated_standard_cost_usd') is not None:totals['estimated_usd']+=cost['estimated_standard_cost_usd']
        else:missing+=1
    return {**totals,'calls':len(responses),'missing_usage_or_cost':missing}

def paired(rows,a,b,metric):
    groups=collections.defaultdict(lambda:collections.defaultdict(list))
    for r in rows:
        if r['variant'] in (a,b):groups[r['case_id']][r['variant']].append(float(r[metric]))
    differences=[statistics.mean(v[a])-statistics.mean(v[b]) for v in groups.values() if v[a] and v[b]]
    rng=random.Random(5623);boots=[statistics.mean(rng.choices(differences,k=len(differences))) for _ in range(10000)]
    return {'cases':len(differences),'difference':statistics.mean(differences),'ci95':[quantile(boots,.025),quantile(boots,.975)]}

def build(root, *, trial_directories=None, grading_directories=None):
    manifest=read_json(root/'manifest.json');cases={c['case_id']:c for c in manifest['cases']}; rows=[];reason_counts=collections.Counter(); all_responses=[];judge_responses=[];raw_rows=[]
    for name in manifest['order']:
        trial_directory=Path((trial_directories or {}).get(name,root/name))
        grading_directory=Path((grading_directories or {}).get(name,root/'grading_v2'/name))
        r=read_json(trial_directory/'outcome.json');responses=read_jsonl(trial_directory/'responses.jsonl');pipeline=[x for x in responses if x['operation']!='evaluation_judge']; judges=[x for x in responses if x['operation']=='evaluation_judge'];all_responses+=pipeline;judge_responses+=judges
        corrected=read_json(grading_directory/'result.json')
        delivered=bool(r.get('delivery'));n=len(cases[r['case_id']]['required'])
        final_judge=corrected.get('judge',{}) if delivered else {'claims':[],'required':[{'index':i,'present':False} for i in range(n)]}
        q=quality(final_judge,n);checks=r.get('workflow_checks',{})
        metric={'id':name,'case_id':r['case_id'],'family':r['family'],'variant':r['variant'],'repeat':r['repeat'],'status':r['status'],'delivery':delivered,
                'service_available':all(x.get('status_code')==200 for x in pipeline),
                'pipeline_http_statuses':dict(collections.Counter(str(x.get('status_code')) for x in pipeline)),
                **q,'content_pass':delivered and q['content_pass'],'api_workflow_pass':bool(checks) and all(checks.values()) and all(r.get('draft_checks',[])),
                'workflow_checks':checks,'pipeline_seconds':r.get('pipeline_seconds'),'questions':len(r.get('questions',[])),
                'known_answers':sum(x['answer']!='I am not sure.' for x in r.get('questions',[])),
                'budget':budget(pipeline,manifest['model']),'grader':final_judge,'grading_status':corrected['status'],'final_text':r.get('final_text',''),'turns':r.get('turns',[]),'question_records':r.get('questions',[])}
        metric['ai_e2e_pass']=metric['content_pass'] and metric['api_workflow_pass'];rows.append(metric)
        if delivered and corrected['status']!='graded':
            metric.update(content_pass=None,ai_e2e_pass=None,covered=None,claims={})
        final=trial_directory/'final_state.json'
        if final.exists():
            state=read_json(final)
            for activity in state.get('ai_activity',[]):
                if activity['status']!='completed':reason_counts[activity.get('operation','')+': '+activity.get('message','')]+=1
        if corrected.get('artifact')=='rejected_raw':
            raw_rows.append({'id':name,'status':corrected['status'],**quality(corrected.get('judge',{}),n),'raw_text':corrected.get('candidate',''),'grader':corrected.get('judge',{})})
            if corrected['status']!='graded':raw_rows[-1].update(content_pass=None,covered=None,claims={})
        judge_responses+=read_jsonl(root/'raw_review'/name/'responses.jsonl')
        judge_responses+=read_jsonl(grading_directory/'responses.jsonl')
    groups={}
    for v in ('full','generic','fixed','no_followup','attack'):
        rs=[r for r in rows if r['variant']==v];c=collections.Counter();[c.update(r['claims']) for r in rs];req=sum(r['required'] for r in rs);covered=sum(r['covered'] or 0 for r in rs)
        times=[r['pipeline_seconds'] for r in rs if r['pipeline_seconds'] is not None and r['service_available']]
        bycase=collections.defaultdict(list)
        for r in rs:bycase[r['case_id']].append(r['content_pass'])
        semantic_complete=all(r['content_pass'] is not None for r in rs)
        groups[v]={'n':len(rs),'delivered':sum(r['delivery'] for r in rs),'content_pass':sum(bool(r['content_pass']) for r in rs) if semantic_complete else None,'ai_e2e_pass':sum(bool(r['ai_e2e_pass']) for r in rs) if semantic_complete else None,
                   'service_available':sum(r['service_available'] for r in rs),'delivered_service_available':sum(r['delivery'] and r['service_available'] for r in rs),
                   'graded_deliveries':sum(r['delivery'] and r['grading_status']=='graded' for r in rs),
                   'api_pass':sum(r['api_workflow_pass'] for r in rs),'covered':covered if semantic_complete else None,'required':req,'claims':dict(c),'accuracy':c['correct']/sum(c.values()) if sum(c.values()) else None,
                   'coverage':covered/req if semantic_complete else None,'questions_mean':statistics.mean(r['questions'] for r in rs if r['service_available']),'known_answers_mean':statistics.mean(r['known_answers'] for r in rs if r['service_available']),
                   'p50_seconds':quantile(times,.5),'p95_seconds':quantile(times,.95),'all_three_content_pass':sum(all(xs) for xs in bycase.values()) if semantic_complete else None,'case_count':len(bycase),
                   'budget':{k:sum(r['budget'].get(k,0) for r in rs) for k in ('calls','input_tokens','output_tokens','cached_tokens','cache_write_tokens','estimated_usd','missing_usage_or_cost')}}
    lookup={(r['case_id'],r['variant'],r['repeat']):r for r in rows};pairs={}
    for v in ('generic','fixed','no_followup','attack'):
        matched=[(r,lookup[(r['case_id'],'full',r['repeat'])]) for r in rows if r['variant']==v and r['service_available'] and lookup[(r['case_id'],'full',r['repeat'])]['service_available']]
        pairs[v]={'n':len(matched),'full_delivered':sum(f['delivery'] for b,f in matched),'comparator_delivered':sum(b['delivery'] for b,f in matched),'full_known_answers_mean':statistics.mean(f['known_answers'] for b,f in matched),'comparator_known_answers_mean':statistics.mean(b['known_answers'] for b,f in matched)}
    cache=read_json(root/'cache/results.json') if (root/'cache/results.json').exists() else []
    return {'manifest':{k:v for k,v in manifest.items() if k not in ('source_sha256','cases','attacks','order')},'groups':groups,
            'paired_delivery_descriptive':pairs,
            'offline':read_json(root.parent/'extended-offline-20261102/offline.json'),
            'browser':read_json(root/'browser/report.json'),
            'cache':{'attempted_calls':len(cache),'completed_responses':sum(r.get('provider_status')=='completed' for r in cache),'http_429_credit_balance_exhausted':sum(r.get('status_code')==429 for r in cache),'performance_result':None},
            'semantic_scores_status':'NOT AVAILABLE: version 1 grading invalidated by missing question context; version 2 blocked by credit exhaustion.',
            'paired_content_pass':None,
            'failure_activities':dict(reason_counts),'pipeline_budget':budget(all_responses,manifest['model']),'judge_budget':budget(judge_responses,manifest['model']),
            'rows':rows,'rejected_raw_reviews':raw_rows}

if __name__=='__main__':
    import sys
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=build(args.run);write_json(args.output,result);print(json.dumps({k:v for k,v in result.items() if k not in ('rows','rejected_raw_reviews')},ensure_ascii=False,indent=2))
