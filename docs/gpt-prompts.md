# GPT API 프롬프트 구성과 위치

이 문서는 현재 제품이 GPT API에 전달하는 프롬프트의 정의 위치, 역할, 입력 데이터와 조합 방식을 정리한다. 프롬프트 원문은 `backend/app/product/`의 Python 코드에 정의되어 있다. [7절](#7-prompt-caching을-통한-비용-절감-검토)은 프롬프트 캐싱의 적용 내용, 설정과 비용 예시를 다룬다.

확인 기준: 2026-10-28, HEAD `2d01506`의 로컬 작업 트리. 아래 소스 링크의 줄 번호는 확인 당시 기준이다.

## 1. 프롬프트 위치

| 기능 | 정의 위치 | 이름 또는 형태 |
| --- | --- | --- |
| 환자 답변에서 증상·약물 등 사실 추출 | [provider.py:65](../backend/app/product/provider.py#L65) | `_SYSTEM` |
| 추가 문진 질문 생성 | [intelligence.py:72](../backend/app/product/intelligence.py#L72) | `_PLAN_PROMPT` |
| 환자용·의사용 사실 요약 생성 | [intelligence.py:105](../backend/app/product/intelligence.py#L105) | `_SYNTHESIS_PROMPT` |
| AI 진단·상담 가이드 보고서 생성 | [assessment.py:84](../backend/app/product/assessment.py#L84) | `PROMPT` |
| 보고서 생성 전 대용량 첨부파일 개별 읽기 | [assessment.py:126](../backend/app/product/assessment.py#L126) | `FILE_PROMPT` |
| 환자가 요청한 PDF·이미지 내용 읽기 | [media.py:227](../backend/app/product/media.py#L227) | 요청 본문에 직접 작성한 `instructions` |
| 기존 화면 문구 번역 | [intelligence.py:475](../backend/app/product/intelligence.py#L475) | `translate_presentation()` 내부의 `prompt` |

공통 지침은 [intelligence.py:51](../backend/app/product/intelligence.py#L51)의 `_COMMON_PROMPT`, 언어 지침은 [locales.py:24](../backend/app/product/locales.py#L24)의 `language_instruction()`에 있다.

## 2. 실제 API 요청 구성

현재 제품의 텍스트·보고서·첨부파일 읽기 코드는 `{OPENAI_BASE_URL}/responses`로 요청을 보낸다. 기본 URL은 [config.py:59](../backend/app/product/config.py#L59)에 정의된 `https://api.openai.com/v1`이다.

| 요청 필드 | 담기는 내용 |
| --- | --- |
| `model` | 해당 문진에 저장된 모델 ID |
| `instructions` | 추가 문진·번역·첨부파일 단독 읽기의 지시문. 이전 모델·별도 엔드포인트·캐시 정책 비활성화 시에도 사용 |
| `input` | 캐시 적용 작업의 고정 `developer` 지시문과 환자별 `user` 데이터 |
| `prompt_cache_options` | 지원 모델의 캐시 정책. 적용값은 `{"mode": "explicit", "ttl": "30m"}` |
| `text.format` | 구조화 작업의 응답 JSON Schema와 `strict: True` 설정 |
| `store` | 현재 Responses 요청에서 `False`로 설정 |

지원 모델에서 추가 문진 요청의 핵심 구성은 다음과 같다. `schema`는 `plan()`이 생성한 응답 스키마다. 환자별 후보 ID가 스키마에 포함되므로 명시적 경계 없이 일회성 입력의 캐시 저장 비용을 피한다.

```python
instructions = _PLAN_PROMPT + language_instruction(locale)
data = {
    "locale": locale,
    "sources": sources,
    "concerns": concerns,
    "eligible_targets": targets,
}
payload = {
    "model": model,
    "store": False,
    "prompt_cache_options": {"mode": "explicit", "ttl": "30m"},
    "instructions": instructions,
    "input": json.dumps(data, ensure_ascii=False),
    "text": {
        "format": {
            "type": "json_schema",
            "name": "preparation_followup_batch",
            "schema": schema,
            "strict": True,
        }
    },
}
```

실제 전송 코드는 [OpenAIProvider.extract()](../backend/app/product/provider.py#L126), [OpenAIIntelligence._request()](../backend/app/product/intelligence.py#L399), [OpenAIAssessment._request()](../backend/app/product/assessment.py#L402)에서 확인할 수 있다. 첨부파일 단독 읽기는 [media.py:225](../backend/app/product/media.py#L225)에서 요청을 만들며, 구조화 JSON 대신 일반 텍스트 초안을 요청한다.

## 3. 기능별 지시 내용과 입력 데이터

### 사실 추출 — `_SYSTEM`

- 역할: 환자가 명시한 내용을 증상, 약물, 검사, 측정값, 정정·삭제 요청 등으로 구조화한다. 진단, 치료 제안, 환자 질문 생성은 금지한다.
- 근거: 추출값은 근거 문구의 원문 일부여야 하며, 근거는 `CURRENT_MESSAGE`의 연속된 원문이어야 한다. 빠진 정보로부터 음성 소견이나 사실을 추론하지 않도록 지시한다.
- 입력: `CURRENT_MESSAGE`와 환자별 `context`는 `user` 데이터로 전달한다. 캐시 적용 시 워크플로 질문 목록, 공통 질문과 활성화 신호는 고정 `developer` 블록의 참고 데이터로 분리한다.
- 출력: [EXTRACTION_SCHEMA](../backend/app/product/provider.py#L42)의 JSON. 최종 지시문은 `_SYSTEM + language_instruction(locale, verbatim=True)`다.

폼 답변도 추출 입력이 될 수 있다. [pipeline.py:319](../backend/app/product/pipeline.py#L319)의 `_prepare_baseline()`은 저장된 답변을 소유 증상·필드 정보와 함께 텍스트로 조합해 같은 추출기를 호출한다.

### 추가 문진 — `_PLAN_PROMPT`

- 역할: 백엔드가 허용한 `eligible_targets`에서 유용한 질문을 골라 한 번에 최대 5개를 만든다. 이미 답했거나 거절한 내용을 반복하지 않도록 지시한다.
- 질문 범위: 등록된 `target_id`와 작성된 질문 범위를 유지한다. 필요한 경우 중립적인 예시 답변을 2~3개 제안하며, 자유 응답이 적합하면 선택지를 비워 둔다.
- 입력: `locale`, `sources`, `concerns`, `eligible_targets`.
- 출력: `questions`, `overview`, `suggested_concern_ids`. 조합과 스키마는 [plan()](../backend/app/product/intelligence.py#L452)에 있다.

질문 후보는 [pipeline.py:161](../backend/app/product/pipeline.py#L161)의 `eligible_followups()`에서 결정한다. 프롬프트와 함께 전달되는 후보의 내용도 질문 범위에 영향을 준다.

### 사실 요약 — `_SYNTHESIS_PROMPT`

- 역할: 환자 검토용 개요, 의사용 요약, 증상별 요약, 진료 의제, 불확실한 정보를 작성한다. 진단적 판단을 작성하지 않도록 지시한다.
- 근거: 각 항목은 직접 뒷받침하는 `source_ids`를 인용한다. 모름, 응답 거절, 미수집을 구분하고, 증상·약물의 독립된 기록을 유지한다.
- 입력: `locale`, `sources`, `concerns`.
- 출력: `patient_overview`, `clinician_brief`, `concern_summaries`, `appointment_agenda`, `uncertainties`. 조합은 [synthesize()](../backend/app/product/intelligence.py#L462)에 있다.

### AI 진단·상담 보고서 — `PROMPT`

- 역할: 가능한 진단과 근거, 불확실성, 진료 시점, 다음 단계와 경고 증상을 별도 보고서로 작성한다. 확정 진단, 처방, 개인별 약물 용량 지시는 금지한다.
- 입력: 현재 `sources`, `concerns`, `factual_summary`, 첨부파일 목록과 언어. 입력 조립은 [assessment_input()](../backend/app/product/assessment.py#L280), 파일 결합은 [generate()](../backend/app/product/assessment.py#L447)에 있다.
- 근거: 환자별 사실과 가설은 직접 관련된 출처를 인용하며, 제공된 모든 첨부파일에 대한 검토 항목을 포함하도록 지시한다.
- 최종 지시문: `PROMPT + language_instruction(locale)`. 출력은 `AssessmentOutput` JSON Schema를 따른다.

사실 추출·요약과 진단 보고서는 역할이 다르다. 진단 보고서는 별도의 `assessment.py` 경로에서 잠정적인 임상적 추론을 요청한다.

### 첨부파일 읽기 — 두 가지 경로

| 경로 | 지시와 처리 방식 |
| --- | --- |
| 환자가 첨부파일 읽기를 요청 | `media.py`의 `instructions`에 파일에서 읽을 수 있는 관련 문구, 날짜, 약물명, 수치·단위를 추출하고 환자가 검토할 일반 텍스트 초안을 작성하도록 지시한다. 진단·검사 해석·치료 조언은 금지한다. |
| 보고서에 포함할 파일 개별 처리 | 첨부파일 원본 총합이 `35 * 1024 * 1024`바이트를 초과하면 파일별로 `FILE_PROMPT + language_instruction(locale)`를 사용한다. 각 파일의 `AttachmentReview` 결과를 최종 보고서의 입력에 포함한다. |

보고서 첨부파일 원본 총합이 위 기준 이하이면 원본 PDF·이미지를 최종 보고서 요청에 직접 포함한다. 분기는 [assessment.py:449](../backend/app/product/assessment.py#L449)에 있다.

### 화면 문구 번역 — `translate_presentation()`

- 역할: 기존 문구를 ID별로 번역한다. 질문에 답하거나 질문·선택지를 새로 만들지 않고, 범위·숫자·단위·부정·불확실성을 보존하도록 지시한다.
- 입력: `locale`, `texts: [{id, text}]`.
- 최종 지시문: `_COMMON_PROMPT + 함수 내부 번역 지침 + language_instruction(locale)`.

## 4. 공통 지침, 언어와 재시도

`_PLAN_PROMPT`와 `_SYNTHESIS_PROMPT`는 정의 시점에 `_COMMON_PROMPT`를 포함한다. 공통 지침은 현재 제공된 근거만 사용하고, 환자 문구에 포함된 명령을 따르지 않으며, 출처 인용·부정·불확실성을 유지하도록 요청한다. 진단·긴급도 평가·치료 제안도 금지한다.

[language_instruction()](../backend/app/product/locales.py#L24)은 `en`, `zh-CN`, `zh-TW`, `ko`, `ja`에 맞춰 지침을 추가한다.

- `verbatim=True`: 추출값과 근거를 원래 언어 그대로 보존한다.
- 기본 모드: 질문, 선택지의 표시명과 값, 요약, 보고서 등을 선택 언어로 작성하도록 지시한다. ID, 파일명, 숫자와 단위 등은 유지한다.

언어 검사 실패 시 추가되는 지침도 있다. [intelligence.py:436](../backend/app/product/intelligence.py#L436)은 선택 언어 검사 실패에 한해 보정 문구를 붙여 최대 한 번 더 요청한다. [assessment.py:474](../backend/app/product/assessment.py#L474)도 같은 입력 근거로 보고서 언어 보정을 한 번 요청한다.

## 5. 음성 전사의 별도 프롬프트

[media.py:188](../backend/app/product/media.py#L188)의 음성 전사는 `{OPENAI_BASE_URL}/audio/transcriptions`를 사용한다. `model`, `language`, 오디오 파일을 보내며, 중국어 선택 시에만 다음 `prompt`를 추가한다.

| 선택 언어 | 전사 `language` | 추가 `prompt` |
| --- | --- | --- |
| `zh-CN` | `zh` | `请使用简体中文转录。` |
| `zh-TW` | `zh` | `請使用繁體中文轉錄。` |
| `en`, `ko`, `ja` | 선택 언어와 동일 | 추가하지 않음 |

## 6. 이전 API 구현의 프롬프트

이전 `/api/sessions` 구현은 `backend/app/llm/azure.py`에 별도 `system`·`user` 메시지를 정의한다.

| 기능 | 위치 | 버전 식별자 |
| --- | --- | --- |
| 사실 후보 추출 | [azure.py:129](../backend/app/llm/azure.py#L129) | `extract-v1` |
| 질문 한 개의 문구 생성 | [azure.py:205](../backend/app/llm/azure.py#L205) | `question-v1` |
| 요약 생성 | [azure.py:263](../backend/app/llm/azure.py#L263) | `summary-v1` |

이전 API는 [main.py:33](../backend/app/core/main.py#L33)의 `enable_legacy=True` 또는 `ENABLE_LEGACY_API=1`로 활성화된다. 해당 경로에서 실제 LLM 구현을 선택하는 조건은 [deps.py:17](../backend/app/api/deps.py#L17)의 `LLM_PROVIDER=azure`이며, 기본값은 `fake`다. 현재 제품의 `/api/v1` 프롬프트를 확인하거나 수정할 때는 위의 `backend/app/product/` 경로를 기준으로 본다.

## 7. Prompt Caching을 통한 비용 절감 검토

검토·구현 기준: 2026-10-28 OpenAI 공식 문서와 현재 로컬 코드. 사실 추출의 고정 참고자료와 요약·진단 보고서의 지침에 명시적 30분 캐시 경계를 적용했다. 호출별 토큰 사용량과 예상 요금을 서버 로그에 기록한다. 실제 적중률과 절감률은 운영 응답의 사용량으로 확인해야 한다.

### 캐싱 조건과 비용 적용 범위

프롬프트 캐싱은 요청 앞부분의 동일한 접두부를 재사용해 해당 입력 토큰에 할인 단가를 적용한다. 출력 토큰은 별도 과금된다. GPT-5.6 이후의 최소 캐시 가능 접두부는 **1,024토큰**이다. [OpenAI 공식 Prompt Caching 문서](https://developers.openai.com/api/docs/guides/prompt-caching#how-caching-works)

캐싱은 지원 모델에서 기본 활성화되지만, 고정 지침 뒤에 환자별 입력이 바뀌면 적중이 보장되지 않는다. GPT-5.6 이후의 암시적 캐싱은 마지막 적격 메시지 끝까지 저장하므로, 고정 부분 뒤에 명시적 경계를 두었다. 최상위 `instructions`에는 경계를 붙일 수 없어 `developer` 메시지의 `input_text` 블록을 사용한다. [캐시 모드와 경계 설정](https://developers.openai.com/api/docs/guides/prompt-caching#how-caching-works)

| Responses API 설정 | 최소 유지 시간 | 캐시 저장 단가 |
| --- | --- | --- |
| `prompt_cache_options.ttl: "30m"` — 기본값 | 30분 | 일반 입력 단가의 1.25배 |
| `prompt_cache_options.ttl: "12h"` | 12시간 | 일반 입력 단가의 2.5배 |

저장 단가는 일반 입력 비용에 더하는 추가 요금이 아니라, 해당 토큰에 적용하는 전체 단가다. 유지 시간에 따른 캐시 읽기 단가는 동일하다. [캐시 유지 시간과 과금](https://developers.openai.com/api/docs/guides/prompt-caching#cache-lifetime)

### 적용한 호출별 캐시 정책

| 부분 | 현재 구현과 판단 |
| --- | --- |
| **사실 추출** | [provider.py](../backend/app/product/provider.py)의 고정 `catalogue`, `session_fields`, `activation_signals`를 지침과 함께 `developer` 블록에 옮겼다. 이 참고 데이터는 기존 JSON 직렬화로 105,308문자이며, 현재는 공백을 줄이고 키 순서를 고정해 직렬화한다. 환자별 문맥과 `CURRENT_MESSAGE`는 캐시 경계 뒤의 `user` 메시지에 둔다. 이 문자 수는 토큰 수가 아니다. |
| **추가 문진·번역** | [intelligence.py](../backend/app/product/intelligence.py)의 환자별 후보·문구 ID가 스키마에 들어가는 구조를 유지한다. 명시적 모드에서 경계를 두지 않아 재사용하기 어려운 입력의 캐시 저장 과금을 피한다. |
| **사실 요약·진단 보고서** | 고정 지침의 `developer` 블록 끝에 경계를 두고, 환자 기록과 첨부파일은 뒤의 `user` 메시지에 둔다. 보고서의 개별 첨부파일 전처리에도 같은 방식을 적용한다. |
| **첨부파일 단독 읽기** | [media.py](../backend/app/product/media.py)의 짧은 지침과 매번 다른 파일에는 경계를 두지 않는다. 명시적 모드로 일회성 파일 입력의 캐시 저장 비용을 피한다. 음성 전사는 기존 전용 API를 사용한다. |
| **공통 정책·계측** | [prompt_cache.py](../backend/app/product/prompt_cache.py)가 요청 형식과 호출별 사용량을 처리한다. `openai_usage` 구조화 로그는 입력·출력·캐시 읽기·쓰기 토큰 및 산출 가능한 예상 요금을 기록한다. |

캐시는 렌더링된 접두부 전체가 일치해야 한다. 모델, 응답 스키마인 `text.format`, 추론 설정 등도 영향을 준다. 추출 → 추가 문진 → 요약 → 진단의 연속 호출을 모두 같은 캐시의 재사용으로 계산할 수는 없다. [캐시 일치에 영향을 주는 설정](https://developers.openai.com/api/docs/guides/prompt-caching#what-is-the-prompt-cache)

### 현재 모델의 단가

확인 당시 로컬 설정의 모델은 `gpt-6-sol`이며, 코드 기본값도 [config.py:58](../backend/app/product/config.py#L58)에 정의되어 있다. 실제 요청은 문진에 저장된 모델 ID를 사용하므로 다른 모델을 선택한 문진은 해당 모델 단가로 계산한다.

다음은 표준 처리, 입력 272K토큰 이하, **100만 토큰당 USD** 기준이다. [GPT-6 Sol 공식 가격](https://developers.openai.com/api/docs/models/gpt-6-sol)

| 모델 | 일반 입력 | 캐시 읽기 | 30분 캐시 저장 | 출력 |
| --- | --- | --- | --- | --- |
| `gpt-6-sol` | $2.00 | $0.20 | $2.50 | $10.00 |

이 모델에서 캐시에 적중한 입력 토큰의 할인율은 **90%**다. `gpt-6.1-sol`의 캐시 읽기 단가인 $0.10과 구분해야 한다. [공식 모델별 요금표](https://developers.openai.com/api/docs/pricing)

### 가정에 따른 절감 예시

다음 조건으로 계산한 예시이며, 실제 서비스에서 측정한 결과가 아니다.

- 동일 모델·작업·스키마로 총 10회 호출한다.
- 매회 고정 입력 2,000토큰, 변경 입력 1,000토큰, 출력 500토큰을 사용한다.
- 고정 부분을 30분 캐시에 한 번 저장하고, 이후 9회 모두 해당 부분에 적중한다.
- 변경 입력은 일반 입력으로 처리하며, 캐시 적용 전후 출력 토큰 수는 같다.

| 비용 | 캐싱 없이 | 30분 캐싱 적용 |
| --- | --- | --- |
| 입력 | $0.0600 | $0.0286 |
| 출력 | $0.0500 | $0.0500 |
| **합계** | **$0.1100** | **$0.0786** |

캐싱 적용 입력 비용은 저장 $0.0050 + 읽기 $0.0036 + 변경 입력 $0.0200이다. 입력 비용은 약 **52.3%**, 출력까지 포함한 전체 비용은 약 **28.5%** 줄어든다. 캐시 적중 입력의 90% 할인을 전체 호출 비용의 할인율로 적용해서는 안 된다.

### 설정과 운영 확인

`OPENAI_PROMPT_CACHE`는 기본적으로 `1`로 동작하며, `backend/.env`에서 설정할 수 있다. 공식 OpenAI 엔드포인트와 [지원 모델 목록](../backend/app/product/prompt_cache.py)의 정확한 모델 ID에 적용한다. `OPENAI_PROMPT_CACHE=0`은 기존 요청 형식과 제공자의 기본 캐싱 동작으로 되돌린다. 이전 모델, 목록에 없는 모델 ID와 별도 엔드포인트도 기존 요청 형식을 사용한다.

현재 구현은 30분 유지 시간을 사용한다. 12시간 설정은 실제 호출 간격과 쓰기 비용을 측정한 후 검토할 항목이다.

로컬 서버를 다시 시작한 뒤 실제 요청을 실행하면 `.local/server.log`에서 다음과 같이 사용량을 확인할 수 있다.

```bash
rg 'openai_usage ' .local/server.log
```

- 로그 항목: `operation`, `model`, `input_tokens`, `output_tokens`, `cached_tokens`, `cache_write_tokens`, `estimated_standard_cost_usd`.
- 응답이 사용량을 제공하면 불완전한 출력과 언어 보정 재시도도 호출별로 기록한다. 환자 입력, 출력 본문, 첨부파일, API 키는 이 로그에 포함하지 않는다.
- 예상 요금은 2026-10-28 기준 표준·글로벌 처리, 입력 272K토큰 이하의 알려진 모델 단가로 계산한다. 일반 입력과 캐시 읽기·쓰기를 중복 계산하지 않는다. 계정 할인·크레딧을 반영한 청구서 금액은 아니다.
- 사용량 필드가 없거나 모순되거나, 가격·처리 등급·엔드포인트를 지원하지 않으면 예상 요금을 `null`로 남긴다. 모델별 기록을 합산해 입력 대비 캐시 읽기 비율과 전체 비용을 비교한다.

회귀 테스트는 서로 다른 환자의 고정 접두부 일치, 환자 데이터 분리, 전체 질문 목록 보존, 질문 ID 검증, 파일 전달, 이전 요청 형식 복원과 비용 계산을 확인한다. 외부 API는 모킹하므로 테스트 통과가 실제 캐시 적중이나 특정 절감률을 의미하지는 않는다. 운영 요청의 사용량으로 효과를 확인한다. [캐시 최적화와 성능 측정](https://developers.openai.com/api/docs/guides/prompt-caching#how-to-optimize-prompt-caching)
