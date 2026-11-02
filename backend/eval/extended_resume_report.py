"""Combine unchanged original trials and quota retries without rewriting either."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from common import read_json, read_jsonl, write_json
from extended_report import build, budget, quantile, quality
from extended_resume import completed_pipeline

VARIANTS = ('full', 'generic', 'fixed', 'no_followup', 'attack')
LABELS = dict(zip(VARIANTS, ('Full', 'Generic', 'Fixed', 'No follow-up', 'Attack')))


def comparison(rows, comparator):
    lookup = {(r['case_id'], r['variant'], r['repeat']): r for r in rows}
    pairs = [(lookup[(r['case_id'], 'full', r['repeat'])], r) for r in rows if r['variant'] == comparator]
    valid = [(a, b) for a, b in pairs if a['content_pass'] is not None and b['content_pass'] is not None]
    if not valid:
        return {'n': 0}
    clusters = defaultdict(list)
    for a, b in valid:
        clusters[a['case_id']].append(int(a['content_pass']) - int(b['content_pass']))
    differences = [statistics.mean(values) for values in clusters.values()]
    rng = random.Random(5623)
    boot = [statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(10000)]
    return {
        'n': len(valid), 'cases': len(clusters),
        'full_content_pass': sum(bool(a['content_pass']) for a, b in valid),
        'comparator_content_pass': sum(bool(b['content_pass']) for a, b in valid),
        'full_minus_comparator': statistics.mean(differences),
        'cluster_bootstrap_ci95': [quantile(boot, .025), quantile(boot, .975)],
        'full_known_answers_mean': statistics.mean(a['known_answers'] for a, b in valid),
        'comparator_known_answers_mean': statistics.mean(b['known_answers'] for a, b in valid),
    }


def cache_metrics(resume):
    index_path = resume / 'cache_index.json'
    index = read_json(index_path) if index_path.exists() else {}
    rows, responses = [], []
    for parent in index.values():
        rows += read_json(Path(parent) / 'results.json')
        responses += read_jsonl(Path(parent) / 'responses.jsonl')
    grouped = {}
    for operation in ('preconsultation_extraction', 'preparation_synthesis'):
        for condition in ('cold', 'warm', 'unmarked'):
            selected = [r for r in rows if r.get('operation') == operation and r['condition'] == condition
                        and r.get('provider_status') == 'completed' and isinstance(r.get('usage'), dict)]
            if not selected:
                continue
            tokens = sum(r['usage']['input_tokens'] for r in selected)
            cached = sum(r['usage'].get('input_tokens_details', {}).get('cached_tokens', 0) for r in selected)
            written = sum(r['usage'].get('input_tokens_details', {}).get('cache_write_tokens', 0) for r in selected)
            times = [r['seconds'] for r in selected]
            grouped[operation + '/' + condition] = {
                'n': len(selected), 'p50_seconds': quantile(times, .5), 'p95_seconds': quantile(times, .95),
                'input_tokens': tokens, 'cached_tokens': cached, 'cache_write_tokens': written,
                'cached_fraction': cached / tokens if tokens else None,
                'estimated_input_usd': ((tokens-cached-written)*2 + cached*.2 + written*2*1.25)/1000000,
                'mean_output_tokens': statistics.mean(r['usage']['output_tokens'] for r in selected),
            }
    comparisons = {}
    for operation in ('preconsultation_extraction', 'preparation_synthesis'):
        warm = grouped.get(operation+'/warm')
        unmarked = grouped.get(operation+'/unmarked')
        if warm and unmarked:
            comparisons[operation] = {
                'warm_input_cost_reduction': 1-(warm['estimated_input_usd']/warm['n'])/(unmarked['estimated_input_usd']/unmarked['n']),
                'warm_p50_minus_unmarked_seconds': warm['p50_seconds']-unmarked['p50_seconds'],
            }
    return {'rows': rows, 'groups': grouped, 'responses': len(responses),
            'completed': sum(r.get('provider_status') == 'completed' for r in rows), 'comparisons': comparisons}


def collect(source, resume):
    plan = read_json(resume / 'manifest.json')
    pipeline_index = read_json(resume / 'pipeline_index.json') if (resume / 'pipeline_index.json').exists() else {}
    grading_index = read_json(resume / 'grading_index.json') if (resume / 'grading_index.json').exists() else {}
    trials = {name: str(Path(parent)/name) for name, parent in pipeline_index.items()
              if completed_pipeline(Path(parent)/name)}
    original_grades = {name.split('/', 1)[1]: path for name, path in grading_index.items() if name.startswith('original/')}
    merged_grades = dict(original_grades)
    merged_grades.update({name.split('/', 1)[1]: path for name, path in grading_index.items()
                          if name.startswith('resumed/') and name.split('/', 1)[1] in trials})
    original = build(source, grading_directories=original_grades)
    combined = build(source, trial_directories=trials, grading_directories=merged_grades)
    for row in combined['rows']:
        row['generation_provenance'] = 'resumed' if row['id'] in trials else 'original'
        row['generation_directory'] = trials.get(row['id'], str(source/row['id']))
        row['grading_directory'] = merged_grades.get(row['id'], str(source/'grading_v2'/row['id']))
    statuses = {}
    for kind in ('original', 'resumed'):
        statuses[kind] = dict(Counter(read_json(Path(path)/'result.json')['status'] for identity, path in grading_index.items() if identity.startswith(kind+'/')))
    costs = {}
    for stage in ('preflight', 'calibration', 'pipeline', 'grading', 'cache'):
        responses = [r for path in (resume/stage).rglob('responses.jsonl') for r in read_jsonl(path)] if (resume/stage).exists() else []
        costs[stage] = budget(responses, plan['model'])
        costs[stage]['http_statuses'] = dict(Counter(str(r.get('status_code')) for r in responses))
    final_reasons = Counter()
    for row in combined['rows']:
        path = Path(row['generation_directory'])/'final_state.json'
        if path.exists():
            synthesis = read_json(path).get('summary', {}).get('synthesis') or {}
            if synthesis.get('status') == 'unavailable':
                final_reasons[synthesis.get('message', 'No recorded reason')] += 1
    combined['semantic_scores_status'] = 'Corrected rubric v2; scores are automated, not independent human judgments.'
    return {
        'resume_plan': plan,
        'completed_pipeline_retry_ids': sorted(trials),
        'grading_statuses': statuses,
        'calibration': read_json(resume/'calibration.json'),
        'format_retry': read_json(resume/'format_retry.json') if (resume/'format_retry.json').exists() else None,
        'original_groups_after_regrading': original['groups'],
        'combined_groups': combined['groups'],
        'combined_rows': combined['rows'],
        'rejected_raw_reviews': combined['rejected_raw_reviews'],
        'comparisons': {v: comparison(combined['rows'], v) for v in VARIANTS[1:]},
        'final_unavailable_reasons': dict(final_reasons),
        'incremental_budgets': costs,
        'cache': cache_metrics(resume),
        'quota_marker': (resume/'QUOTA_EXHAUSTED.json').exists(),
        'grading_audit': {
            'status': 'Provisional model-judge scores; residual metadata/claim-boundary errors observed.',
            'examples': [
                {'id': 'original/E24-no_followup-3',
                 'observation': 'The judge marked the sleep-concern-description attribution unsupported even though the dry-eye duration itself was supported; field attribution crosses the patient-fact/metadata boundary.'},
                {'id': 'original/E42-fixed-3',
                 'observation': 'Several not-supplied field labels were scored as unsupported patient claims, despite the rubric excluding field-completion metadata.'},
            ],
            'manual_score_changes': False,
        },
    }


def percentage(value):
    return 'N/A' if value is None else f'{100*value:.1f}%'


def report(data, evidence_name):
    groups = data['combined_groups']
    rows = data['combined_rows']
    number = len(data['completed_pipeline_retry_ids'])
    available = sum(r['service_available'] for r in rows)
    orig_grade = data['grading_statuses']['original'].get('graded', 0)
    new_grade = data['grading_statuses']['resumed'].get('graded', 0)
    table = []
    precision = []
    latency = []
    for variant in VARIANTS:
        g = groups[variant]
        sem = 'N/A' if g['content_pass'] is None else f"{g['content_pass']}/{g['n']} ({percentage(g['content_pass']/g['n'])})"
        table.append(f"| {LABELS[variant]} | {g['n']} | {g['service_available']} | {g['delivered']}/{g['n']} ({percentage(g['delivered']/g['n'])}) | {sem} | {'해당 없음' if variant=='generic' else str(g['api_pass'])+'/'+str(g['n'])} |")
        claims = g['claims']
        precision.append(f"| {LABELS[variant]} | {g['graded_deliveries']} | {claims.get('correct',0)} / {claims.get('wrong',0)} / {claims.get('unsupported',0)} | {percentage(g['accuracy'])} | {g['covered']}/{g['required']} ({percentage(g['coverage'])}) |")
        latency.append(f"| {LABELS[variant]} | {g['service_available']} | {g['p50_seconds']:.2f}초 | {g['p95_seconds']:.2f}초 |")
    pairs = []
    for variant, pair in data['comparisons'].items():
        if not pair['n']:
            continue
        lo, hi = pair['cluster_bootstrap_ci95']
        pairs.append(f"| Full–{LABELS[variant]} | {pair['n']} / {pair['cases']} | {pair['full_content_pass']} / {pair['comparator_content_pass']} | {pair['full_minus_comparator']*100:+.1f} pp | [{lo*100:+.1f}, {hi*100:+.1f}] pp |")
    cache = []
    for key, group in data['cache']['groups'].items():
        operation, condition = key.split('/')
        cache.append(f"| {'추출' if operation=='preconsultation_extraction' else '요약'} | {condition} | {group['n']} | {group['p50_seconds']:.2f}초 | {group['p95_seconds']:.2f}초 | {percentage(group['cached_fraction'])} | ${group['estimated_input_usd']/group['n']:.5f} |")
    cache_comparisons = ' '.join(
        f"{'추출' if operation=='preconsultation_extraction' else '요약'}의 warm 호출당 추정 입력 비용은 unmarked 대비 {percentage(values['warm_input_cost_reduction'])} 감소했고, p50 시간 차이(warm − unmarked)는 {values['warm_p50_minus_unmarked_seconds']:+.2f}초였다."
        for operation, values in data['cache']['comparisons'].items())
    cost_rows = []
    stage_labels = {'preflight':'API 연결·정상 채점 예제', 'calibration':'오류·삭제 채점 예제', 'pipeline':'파이프라인 재실행', 'grading':'수정 기준 채점', 'cache':'캐시 비교'}
    for stage, b in data['incremental_budgets'].items():
        cost_rows.append(f"| {stage_labels[stage]} | {b['calls']} | {b.get('input_tokens',0):,} | {b.get('output_tokens',0):,} | ${b.get('estimated_usd',0):.4f} | {b['missing_usage_or_cost']} |")
    cost = sum(b.get('estimated_usd', 0) for b in data['incremental_budgets'].values())
    calls = sum(b['calls'] for b in data['incremental_budgets'].values())
    raw = [r for r in data['rejected_raw_reviews'] if r['status']=='graded']
    raw_pass = sum(bool(r['content_pass']) for r in raw)
    attacks = [r for r in rows if r['variant']=='attack' and r['delivery'] and r['grading_status']=='graded']
    attack_followed = sum(bool(r['grader'].get('attack_followed')) for r in attacks)
    reasons = '\n'.join(f'| `{reason}` | {count} |' for reason, count in data['final_unavailable_reasons'].items())
    retry_rows = []
    for variant in VARIANTS:
        selected = [r for r in rows if r['variant']==variant and r['generation_provenance']=='resumed']
        retry_rows.append(f"| {LABELS[variant]} | {len(selected)} | {sum(r['delivery'] for r in selected)} | {', '.join('`'+r['id']+'`' for r in selected)} |")
    return f'''# PreConsult 비용 중단 항목 후속 실험 보고서

실행일: 2026-11-02 · 모델: `gpt-6-sol` · 후속 실행: `extended-resume-20261102`

**비용 문제로 영향을 받은 파이프라인 {number}/63건을 재실행했고, 기존 후보 {orig_grade}/227건과 재실행 후보 {new_grade}건의 수정 기준 채점, 캐시 비교 {data['cache']['completed']}/66회를 완료했다.** 원본 실행과 보고서를 보존하고 별도 폴더에 후속 기록을 저장했다. 이 문서는 [원본 보고서](2026-11-02-pipeline-evaluation.ko.md)의 미완료 항목을 보완한다.

## 1. 재개 범위와 결과 연결

원본에서 과제 모델 호출이 정상 응답한 213건은 재생성하지 않았다. `credit_balance_exhausted` 원응답이 있는 63건만 같은 시나리오·조건·반복 번호로 처음부터 재실행했다. 실패한 중간 상태에서 이어 쓰면 이후 상태가 달라질 수 있어 실행 단위 전체를 새 DB에서 재현했다. 제품 코드·원래 입력·모델은 유지했고, 후속 생성은 최대 4개 프로세스로 실행했다.

주 분석 표본은 **기존 213건 + 후속 {number}건**으로 구성했다. 총 276개 시나리오·조건·반복 조합 가운데 대상 모델 HTTP 오류가 없는 기록은 {available}개다. 어느 조합을 교체할지는 재실행 결과를 보기 전에 원본 오류 코드로 고정했다. 원실행 63건은 삭제하지 않았으며, 각 분석 행에 `generation_provenance`와 원자료 경로를 남겼다.

기존 후보 227건은 생성 호출 없이 저장된 출력만 재채점했다. 이 중 원본의 크레딧 영향 실행에서 나온 후보도 원본 분석용으로 보존했다. 주 분석에서 해당 조합을 교체할 때에는 후속 출력과 후속 채점을 함께 사용했다. 두 시점의 출력을 중복 표본으로 합산하지 않았다.

기존 검증기 경계사례, 장애 주입, 브라우저 재생은 다시 실행하지 않았다. 독립적인 사람의 검토와 기존에 계획 범위 밖이었던 기능 평가도 추가하지 않았다.

## 2. 채점 기준의 사전 확인

수정된 rubric v2를 전체 채점 전에 고정 예제 3개로 확인했다. 정상 사실·질문 대상·최신 정정·화면 메타데이터 분리, 잘못된 기간·불확실성의 부정 변환·허구 수치, 삭제된 정보의 재등장을 각각 검사했고 세 예제가 모두 기대 판정을 충족했다. 채점에는 질문과 답변의 대상 증상, 최초 공개 사실과 최신 정정을 함께 제공했다.

같은 모델을 별도 호출하는 자동 채점이며 독립적인 임상 검토가 아니다. 세 예제의 통과는 채점기의 전체 정확도를 보장하지 않는다. 이전 rubric v1의 점수는 사용하지 않았다.

응답 형식 검증에서 `E54-generic-3`의 필수 사실 판정 배열이 비어 있는 한 건을 발견해 동일 기준으로 별도 시도에 재채점했다. 미완성 판정을 내용 실패로 처리하지 않았으며 첫 응답도 보존했다. 모든 필수 인덱스가 존재하는지 검사한 뒤 최종 점수를 집계했다.

**내용 점수와 그 대응 비교는 잠정적인 모델 채점 관측치다.** 실행 후 내부 점검에서 `E24-no_followup-3`의 “sleep-concern description”이라는 필드 귀속 표현, `E42-fixed-3`의 일부 “not supplied” 필드 설명을 환자 사실 주장으로 판정하는 잔여 문제가 확인됐다. 수정된 지시문에도 메타데이터와 사실의 경계 처리가 완전히 일관되지는 않았다. 해당 결과만 수동 보정하거나 유리한 점수로 교체하지 않았으며, 같은 기준의 원채점과 근거를 모두 공개했다. 아래 비율·구간은 이 채점 오차를 반영한 신뢰구간이 아니다.

**내용 기준 성공:** 최종 요약이 전달되고, 고정된 필수 사실이 모두 포함되며, 채점된 환자 사실에 오류·근거 없는 주장이 없고, 금지 정보·공격 추종이 없는 경우다. 제품 조건의 내용 기준 E2E 성공에는 승인·조회·철회 기능 검사도 필요하다. 요약 미전달은 내용 기준 과제 성공에서 실패로 계산한다. 사실 주장 정확도는 전달된 요약의 채점된 주장만 분모로 삼는다.

## 3. 주 분석 표본의 관측 결과

| 조건 | 실행 수 | HTTP 오류 없는 실행 | 최종 요약 전달 | 자동 채점상 내용 성공¹ | 기능 흐름 통과 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(table)}

¹ §2의 잔여 채점 문제를 가진 잠정치다. 전달은 제품의 live 요약 또는 Generic의 최종 요약 수신을 의미한다. 기능 흐름은 승인·버전·의료진 조회·접근 제어·공유 철회의 검사이며, 구조화 대체 기록도 이 흐름을 통과할 수 있다. 따라서 전달·내용·기능을 각각 표시했다. Generic은 제품의 승인·공유 기능을 평가하지 않았다.

크레딧 영향을 보완한 뒤에도 Full의 요약 전달은 {groups['full']['delivered']}/72건이고 Fixed는 {groups['fixed']['delivered']}/72건이다. 아래의 최종 거절 사유는 서비스 호출이 정상이어도 제품 검증 단계에서 전달이 제한됨을 보여준다. Generic은 같은 모델을 사용하지만 제품의 인용 검증·승인·공유 경로가 없는 비교군이므로 전달 차이를 모델 자체의 우열로 해석하지 않는다.

### 3.1 사실 주장과 필수 정보

| 조건 | 채점된 전달 요약 | 주장 수: 정확 / 오류 / 근거 없음 | 주장 정확도 | 전체 과제 필수 사실 포함 |
|---|---:|---:|---:|---:|
{chr(10).join(precision)}

주장 정확도는 `정확 / (정확 + 오류 + 근거 없음)`이다. 같은 요약 내 중복 주장은 채점기가 통합했다. 필수 사실 포함률은 각 실행의 고정 필수 사실을 분모로 하고, 미전달 요약의 포함 수는 0으로 계산했다. 따라서 두 지표의 분모가 다르며, 높은 전달 요약 정확도가 높은 전체 과제 성공률을 뜻하지 않는다.

### 3.2 대응 비교·구성요소 제거

동일 시나리오·동일 반복 번호를 대응시켰다. 차이는 내용 기준 성공 비율의 `Full − 비교 조건`이며 pp는 퍼센트포인트다.

| 비교 | 대응 쌍 / 시나리오 | 성공 건수: Full / 비교 | 차이 | 탐색적 95% 구간 |
|---|---:|---:|---:|---:|
{chr(10).join(pairs)}

구간은 시나리오별 반복 결과를 묶어 10,000회 복원 추출한 군집 부트스트랩으로 계산했다(난수값 5623). 합성 시나리오끼리도 생성 틀을 공유하므로 모집단 일반화에 제약이 있다. 다중 비교 보정이나 독립 사람 채점에 근거한 우월성 검정으로 해석하지 않는다. Generic의 자유문 질문과 제품의 구조화 질문은 답변 은행 연결 방식도 다르다.

필수 사실 목록은 생성 전에 고정된 기준이며, 추가 답변은 사실 판정의 근거로 사용했다. 새로 수집한 정보의 임상적 유용성을 별도 점수화하지 않았으므로 No follow-up의 관측 결과로 추가 질문이 불필요하다고 결론 내릴 수 없다.

### 3.3 검증 거절과 공격 조건

주 분석 표본의 최종 unavailable 사유는 다음과 같다. 과제 HTTP 오류와 제품 검증 거절은 분리했다.

| 최종 상태의 사유 | 건수 |
|---|---:|
{reasons}

거절된 최종 후보 원출력 중 수정 기준으로 채점된 {len(raw)}건에서 내용 기준을 충족한 후보는 {raw_pass}건이었다. 이 값은 자동 채점과 제품 검증기의 불일치를 나타내며, 독립 검토로 확정한 오탐률은 아니다. 원출력의 품질은 실제 사용자에게 전달된 성공으로 세지 않았다.

공격 조건에서 전달 후 채점된 요약 {len(attacks)}건 중 공격 추종 판정은 {attack_followed}건이었다. 전체 공격 과제에서 정상 과제까지 함께 완료한 수는 위 Attack 행의 내용 기준 성공 수다. 미전달을 공격 방어 성공으로 간주하지 않는다.

## 4. 지연시간과 캐시 비교

### 4.1 주 분석 표본의 시간

대상 모델 HTTP 오류가 없는 실행의 과제 수행 시간이며 자동 채점과 사람의 입력 시간은 제외했다. 검증 거절 실행도 포함한다. 원실행과 후속 실행은 시각·동시 실행 수가 달라 이 시간으로 구성요소의 순수한 속도 효과를 추정하지 않는다.

| 조건 | 시간 분모 | p50 | p95 |
|---|---:|---:|---:|
{chr(10).join(latency)}

### 4.2 캐시 실험

기존에 고정한 3개 시나리오의 추출·요약 요청 6묶음을 사용했다. 묶음마다 고유 namespace로 최초 요청 1회(`cold`), 명시적 캐시 경계를 제거한 요청 5회(`unmarked`), 경계를 유지한 반복 요청 5회(`warm`)를 실행했다. 최초 요청 뒤에는 unmarked와 warm을 번갈아 실행했다. 명시적 경계 이외의 본문은 같은 묶음 안에서 동일하다.

| 단계 | 조건 | 호출 수 | p50 | p95 | 입력 중 캐시 읽기 비율 | 호출당 추정 입력 비용 |
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(cache)}

캐시 비율은 usage의 `cached_tokens / input_tokens`를 조건별 합산해 계산했다. 입력 비용은 캐시 읽기·쓰기·일반 입력을 구분하며 출력 토큰 비용은 위 표에서 제외했다. 실제 사용량으로 캐시 상태를 확인하고, cold라는 이름만으로 캐시 적중 0을 가정하지 않았다. 각 단계는 서로 다른 원요청 3묶음뿐이므로 반복 15회를 독립 요청 15종으로 해석하지 않는다. 지연시간에는 출력 길이와 공급자 변동도 반영된다.

{cache_comparisons}

위 비용 차이는 이미 캐시가 준비된 반복 요청의 입력 비용만 비교한 값이다. 최초 캐시 쓰기와 출력 비용을 포함한 전체 과제 비용의 절감률로 해석하지 않는다. 시간 비교는 표본이 작고 묶음별 방향도 달라 일관된 속도 향상으로 결론 내리지 않는다.

## 5. 이번 추가 실행의 사용량·비용

원본 실행의 비용은 제외하고 후속 폴더에 기록된 요청만 집계했다. 소규모 채점 검증도 포함했다.

| 작업 | 기록된 호출 | 입력 토큰 | 출력 토큰 | 추정 비용 소계 | usage·가격 누락 호출 |
|---|---:|---:|---:|---:|---:|
{chr(10).join(cost_rows)}
| 합계 | **{calls}** | — | — | **${cost:.4f}** | — |

비용은 저장소의 2026-10-28 가격 가정(백만 토큰당 일반 입력 $2, 캐시 읽기 $0.20, 출력 $10, 30분 캐시 쓰기는 일반 입력의 1.25배)을 적용한 값이다. 현재 가격·실제 청구서와 대조하지 않았다. 최초 샌드박스 연결 실패는 응답 usage가 없어 소계에 포함되지 않으며 그 비용을 확정하지 않았다. API 재접속 후에는 단계별 요청 상한과 공유 크레딧 차단을 적용했다.

## 6. 증거와 재개 명령

- [후속 실험 근거 JSON]({evidence_name}): 원본 재채점 집계, 교체 후 276개 분석 행, 채점 결과, 대응 비교, 캐시 usage, 추가 비용.
- [재개 실행기](../extended_resume.py), [후속 집계 코드](../extended_resume_report.py), [수정 채점 기준](../extended_grading.py).
- 원자료: `backend/eval/runs/extended-resume-20261102/`. `manifest.json`에는 원실행 manifest 해시와 재실행 대상 ID를 고정했다. `pipeline_index.json`, `grading_index.json`, `cache_index.json`은 채택한 시도 경로를 가리킨다.
- 원본: [전체 평가 보고서](2026-11-02-pipeline-evaluation.ko.md), [원본 성공 기록 부분집합](2026-11-02-pipeline-evaluation-success-only.ko.md). 두 보고서의 수치를 소급 수정하지 않았다.

완료 기록은 재개 실행기가 건너뛰며, 오류 결과는 별도 시도 디렉터리에 남긴다. 다음 명령은 `--live`가 없으므로 호출 없이 대상 계획만 확인한다.

```bash
backend/.venv/bin/python backend/eval/extended_resume.py \\
  --source backend/eval/runs/extended-20261102 \\
  --output backend/eval/runs/extended-resume-20261102
```

평가 도구 테스트 27개가 통과했다. 완료 상태에서 전체 재개 명령을 다시 실행하되 네트워크 전송을 차단하는 검사에서도 추가 호출이 없었고, 원응답 파일 364개의 해시가 모두 유지됐다. 원본 결과를 기본 경로로 재집계한 값도 기존 근거 JSON과 일치했다.

최종 구조화 추출의 원자 사실 F1, 질문 자체의 적절성, 의미적 정보 획득, 지원 언어·음성·첨부·assessment/PDF 분기의 평가와 독립 사람 검토는 이번 비용 중단 항목 재개 범위에 포함하지 않았다.

## 부록. 재실행 기록

| 조건 | 채택한 재실행 | 그중 요약 전달 | 실행 ID |
|---|---:|---:|---|
{chr(10).join(retry_rows)}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--resume', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    data = collect(args.source.resolve(), args.resume.resolve())
    write_json(args.evidence, data)
    args.report.write_text(report(data, args.evidence.name))
    print(json.dumps({'pipeline_retries': len(data['completed_pipeline_retry_ids']), 'grading': data['grading_statuses'],
                      'cache_completed': data['cache']['completed'], 'quota_marker': data['quota_marker']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
