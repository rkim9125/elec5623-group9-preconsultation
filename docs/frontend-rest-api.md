# 환자 프론트엔드 REST API 연동 명세

작성일: 2026-09-17 · 기준 브랜치: `fr_hr` · 프론트엔드 기준 커밋: `589de65`

> **현재 프론트엔드는 업무용 HTTP API를 호출하지 않는다.** 인증·예약·문진은 브라우저 mock으로 동작한다. 이 문서는 현재 구현을 기록하고, 동일 화면을 서버와 연결하기 위한 **제안 계약 v0.1**을 정의한다. 아래 `/api/v1/patient` 엔드포인트, 서버 인증, ETag, 멱등성은 아직 구현되지 않았다. 기존 백엔드의 `/api/sessions` 계약은 별개이며 이 문서로 변경하지 않는다.

## 1. 구현 상태와 문서 범위

| 구분 | 현재 상태 | 근거 |
| --- | --- | --- |
| 계정·예약·문진 | 메모리/sessionStorage 기반 mock | [account/service.js](../frontend/src/account/service.js), [domain.js](../frontend/src/account/domain.js) |
| 요약·전달 시뮬레이션 | Promise 기반 mock, 외부 전송 없음 | [api/mock.js](../frontend/src/api/mock.js) |
| 답변·분기·검토 상태 | React와 순수 모델 함수에서 처리 | [model.js](../frontend/src/model.js), [App.jsx](../frontend/src/pages/patient/App.jsx) |
| 계정 화면·목록·상세 | 사용자 소유 데이터를 mock에서 받아 화면에서 분류 | [Portal.jsx](../frontend/src/account/Portal.jsx) |
| 영어·한국어 | 로컬 번역 리소스와 localStorage | [i18n/core.js](../frontend/src/i18n/core.js), [copy.js](../frontend/src/copy.js) |
| 기존 백엔드 | FastAPI 문진 세션 라우트 구현, 현재 UI와 미연결 | [sessions.py](../backend/app/api/sessions.py), [기존 API 계약](api-contract.md) |

범위는 가입·로그인·세션 확인·로그아웃, 본인의 예약 조회, 문진 생성·저장·검토·전달 시뮬레이션·조회, 비로그인 문진 가져오기다. 예약 생성/변경/취소, 프로필 수정, 비밀번호 재설정, 소셜 로그인, 관리자, 실제 병원 전송 API는 정의하지 않는다.

### 1.1 현재 mock 함수 계약

이 표는 **실제 코드에 존재하는 인터페이스**다. HTTP 상태 코드는 없다.

| 함수 | 반환/효과 | 호출 화면 |
| --- | --- | --- |
| `signup({name,email,password}, signal?)` | `Promise<User>`; 로그인은 별도로 수행 | 회원가입 |
| `login(email,password,signal?)` | `Promise<User>`; 인증 상태 갱신 | 로그인 |
| `restore()` | `Promise<void>`; 저장된 데모 세션을 읽고 상태 알림 | 앱 시작 |
| `getSnapshot()` / `subscribe(listener)` | 인증 상태 조회/구독 | 앱 전체 |
| `scope()` | `{userId,epoch}`; 클라이언트 요청 세대 확인용 | 보호된 화면 |
| `logout()` | 인증·메모리 조회 캐시 제거, 가상 기록은 유지 | 헤더·계정 |
| `load(scope)` | `Promise<{appointments: Appointment[], intakes: Intake[]}>` | 홈·모든 목록·상세 |
| `startIntake(scope, appointmentId=null)` | `Intake`; 같은 예약의 문진이 있으면 상태와 관계없이 기존 문진 반환 | 예약 상세·새 문진 |
| `saveIntake(scope,id,data,step)` | `{record:Intake,saved:boolean}`; `saved`는 브라우저 저장 성공 여부 | 문진 편집 |
| `importGuest(scope,data,step)` | `Intake`; 동일 사용자·동일 `JSON.stringify(data)`이면 기존 가져온 문진 반환 | 홈의 명시적 가져오기 |
| `mock.request("summary" \| "send", data)` | `Promise<{revision,sections,kind}>`; 복제한 입력을 기준으로 응답 | 검토 진입·전달 시뮬레이션 |

`signup/login/load`의 기본 지연은 400ms, 문진 mock은 650ms다. `failOnce()`, `slowOnce()`, `expire()`, `resetCurrent(scope)`는 데모 제어이며 운영 REST API로 공개할 기능이 아니다. `startIntake/saveIntake/importGuest/logout`은 현재 동기 함수다. 함수 이름만 HTTP 호출로 바꾸면 비동기 저장·오류 처리가 깨지므로 9절의 어댑터 변경이 필요하다.

현재 `mock.request()`는 요약을 반환하지만 `App`은 응답 내용을 상태에 덮어쓰지 않고 현재 답변으로 요약을 다시 만든다. 요청 세대와 답변 revision으로 늦은 결과의 화면 전환을 차단한다. `send` 자체는 서버나 병원으로 아무것도 전송하지 않는다.

### 1.2 현재 저장과 인증의 수명

| 저장 위치 | 키/내용 | 수명 |
| --- | --- | --- |
| sessionStorage | `maeum-intake-demo-v1`, `maeum-intake-demo-v1-step` | 같은 탭의 비로그인 답변·단계 |
| sessionStorage | `jinryo-account-demo-v1` | 가상 예약·계정별 문진 |
| sessionStorage | `jinryo-session-demo-v1`: 사용자 ID, 만료 시각(ms) | 기본 데모 계정의 1시간 로그인 |
| 메모리 | 신규 가입 사용자와 임시 비밀번호 검증 값 | 새로고침 전까지; 재로드 시 신규 계정의 기록도 정리 |
| localStorage | `visit-notes-language`: `en` 또는 `ko` | 로그아웃·데모 기록 초기화와 독립 |

비밀번호 원문과 검증 값은 브라우저 저장소에 기록하지 않는다. 현재의 메모리 SHA-256 검증 및 `scope()` 검사는 실제 서버 인증·권한 검증이 아니다. 서버 API에서는 요청 본문의 `userId`나 `epoch`를 신원으로 신뢰하지 않는다.

## 2. 현재 데이터 모델

필드 이름은 현재 JavaScript 객체와 동일한 camelCase를 사용한다. 아래 형식은 별도 언급이 없으면 현재 mock에도 존재한다.

### 2.1 User, Appointment, Intake

| 객체 | 필드 | 형식·의미 |
| --- | --- | --- |
| User | `id`, `name`, `email` | 문자열; 이름·이메일은 환자 입력 데이터 |
| Appointment | `id`, `userId` | 문자열 ID |
| Appointment | `hospital`, `department` | 문자열; 표시 데이터, 번역 키가 아님 |
| Appointment | `clinician` | 문자열 또는 `null` |
| Appointment | `startsAt` | ISO 8601 시각 |
| Appointment | `status` | `scheduled`, `completed`, `cancelled` |
| Intake | `id`, `userId` | 문자열 ID |
| Intake | `appointmentId` | 문자열 또는 `null`; 생성 후 UI에서 연결을 변경하지 않음 |
| Intake | `data` | 2.2절의 `IntakeData` |
| Intake | `step` | 2.3절의 단계 |
| Intake | `status` | `draft`, `completed`, `sent` |
| Intake | `updatedAt` | ISO 8601 시각 |
| Intake | `snapshot` | 전달 전에는 미존재; 전달 후 `{sections,data?,sentAt}` |
| Intake | `importedGuest` | mock 내부 중복 확인용 문자열; REST 응답·요청에는 사용하지 않음 |

`snapshot.sections`는 `{title:string, step?:string, text:string}[]`이다. `title`은 표시 문구이므로 ID로 사용하지 않는다. 현재 신규 snapshot에는 당시 `data` 사본도 저장한다. 이전 형식에는 사본이 없을 수 있다.

예약 목록의 분류는 상태와 시간을 함께 사용한다.

- `cancelled`: 시각과 무관하게 취소 목록.
- `upcoming`: `status === "scheduled"`이고 `startsAt >= now`.
- `past`: 위 두 조건에 해당하지 않는 예약. 시간이 지났다고 `completed`로 변경하지 않는다.
- 예정은 `startsAt` 오름차순, 지난 예약·취소는 내림차순. 문진은 `updatedAt` 내림차순이다.

### 2.2 IntakeData와 답변 상태

다음은 모든 활성 질문을 확인한 문진 예시다. 미확인 후속 질문 `frequency`는 현재 경과에서 비활성이므로 완료를 막지 않는다.

```json
{
  "version": 1,
  "revision": 8,
  "approved": false,
  "sent": false,
  "reasons": ["I would like to discuss my sleep."],
  "onset": {"status": "answered", "value": "며칠 전부터", "option": "며칠 전부터"},
  "course": {"status": "answered", "value": "비슷해요", "option": "비슷해요"},
  "frequency": {"status": "unasked", "value": ""},
  "severity": {"status": "unknown", "value": "", "option": null},
  "impact": {"status": "none", "value": "", "option": null},
  "history": {"status": "declined", "value": "", "option": null},
  "medicines": {"status": "answered", "value": "", "items": [{"name": "Demo medicine", "detail": ""}]},
  "allergies": {"status": "none", "value": "", "items": []},
  "questions": {"status": "answered", "value": "What should I keep track of?", "option": null},
  "completed": [0, 1, 2]
}
```

| 필드 | 의미 |
| --- | --- |
| `version` | 저장 형식 버전. 현재 정수 `1` |
| `revision` | 현재 UI의 답변 변경 번호. 승인 체크·단계 이동·언어 전환만으로는 증가하지 않음 |
| `approved` | 환자가 현재 요약을 읽고 확인했는지 |
| `sent` | 전달 **시뮬레이션** 완료 여부 |
| `reasons` | 우선순위 순서의 문자열 배열. 최초 상태는 `[""]` |
| `onset/course/frequency/severity/impact/history/questions` | 단일 답변 `{status,value,option?}` |
| `medicines/allergies` | 목록 답변 `{status,value,items:[{name,detail}],option?}`; 항목의 빈 이름·상세는 ‘모름’으로 표시 |
| `completed` | 기존 UI의 큰 단계 기록 배열 `0..3`; 화면은 `completedStages(data)`로 완료 여부를 다시 계산하므로 API 검증 기준으로 신뢰하지 않음 |

| `Answer.status` | 의미 | 완료 판단 |
| --- | --- | --- |
| `unasked` | 아직 질문하지 않음 | 활성 질문이면 완료 차단 |
| `unanswered` | 질문을 확인했으나 답하지 않고 계속함 | ‘없음’과 구분해 보존 |
| `answered` | 직접 입력 또는 준비된 선택지 | 값/목록 검증 필요 |
| `none` | 없음 | 의미 있는 명시적 답변 |
| `unknown` | 모름 | 미응답과 구분 |
| `declined` | 답변 원하지 않음 | 미응답과 구분 |

`none`은 현재 UI에서 `impact/history/medicines/allergies/questions`에 제공한다. `unknown/declined`는 관련 질문 전반에 제공한다. `reasons`는 이 상태 객체를 사용하지 않는다. 상태가 `answered`가 아니면 남아 있는 `value/items`를 활성 답변으로 해석하지 않는다. 목록을 수정하다 ‘없음’을 선택한 현재 mock에는 이전 items가 남을 수 있다.

`option`은 준비된 선택지를 선택했다는 표시다. `null`은 자유 입력, 미존재는 이전 저장 형식이다. `option`이 있고 `option === value`일 때만 표시 레이블을 번역한다. 같은 한국어 문장을 직접 입력했다는 이유로 선택형 답변으로 바꾸지 않는다.

현재 저장값은 다음과 같다. 영어 UI에서도 저장값을 영어 레이블로 치환하지 않는다.

| 질문 | 선택지의 저장값 |
| --- | --- |
| onset | `오늘부터`, `며칠 전부터`, `일주일 이상`, `한 달 이상` |
| course | `비슷해요`, `나아지고 있어요`, `더 불편해졌어요`, `반복돼요` |
| frequency | `하루에 여러 번`, `하루에 한 번 정도`, `며칠에 한 번`, `일정하지 않아요` |
| severity | `가벼워요`, `보통이에요`, `많이 불편해요` |
| impact | `수면이 어려워요`, `일·공부에 집중하기 어려워요`, `움직이기 불편해요` |

향후 언어 중립 option ID를 도입한다면 별도 버전과 데이터 변환이 필요하다. 현재 API 호환 계약에서 임의로 변경하지 않는다.

### 2.3 단계와 상태 전이

단계 순서: `start → reason → onset → course → frequency? → severity → impact → history → medicines → allergies → questions → review → done`.

- `course.value === "반복돼요"`일 때만 `frequency`가 활성화된다. 실제 조건은 `option`이 아닌 `value` 비교다.
- 경과 값이 바뀌면 빈도 답변을 `unasked`로 초기화한다. 비활성 빈도는 요약·완료 판단에서 제외한다.
- 첫 번째 방문 이유가 바뀌면 증상 관련 5개 답변을 초기화한다. 병력·복용약·알레르기·질문은 유지한다.
- 답변 변경은 `approved=false`, `sent=false`로 만든다. 계정의 이미 전달된 문진은 그 전에 편집 자체를 차단한다.
- `draft`: 작성 중, 또는 활성 질문 중 아직 `unasked`가 있음.
- `completed`: 방문 이유가 모두 채워지고 활성 질문을 확인했으며 단계가 `review/done`. 검토 승인을 뜻하지 않는다.
- `sent`: 전달 시뮬레이션 완료. 진료 완료나 의사 열람을 뜻하지 않는다.
- 문진 작성 완료 → 환자 검토 승인 → 전달 시뮬레이션은 서로 다른 전이다.

현재 `intakeStatus()`는 `reasons.every(...)`를 사용하므로 빈 배열 자체는 거부하지 않는다. UI는 방문 이유 한 개를 유지하지만, 제안 서버 계약은 `minItems:1`을 별도로 검증해야 한다.

## 3. REST 공통 규칙 — 제안, 미구현

| 항목 | 제안 계약 |
| --- | --- |
| Base path | `/api/v1/patient` |
| 형식 | JSON / UTF-8. 본문이 있는 요청에 `Content-Type: application/json` |
| ID | opaque string. UUID로 한정하지 않으며 현재 내부 복귀 경로와 호환되도록 `[A-Za-z0-9_-]+` 사용 |
| 시각 | 응답은 ISO 8601 UTC. 화면은 계속 `Asia/Seoul` 사용 |
| 언어 | `Accept-Language: en` 또는 `ko`; 미지원/미지정은 `en`. 요약 GET의 `locale` 쿼리가 있으면 우선 적용 |
| 성공 응답 | 아래 정의한 객체를 그대로 반환. 공통 `data` envelope로 추가 감싸지 않음 |
| 목록 | `{items:[], serverTime:"..."}`. 빈 목록은 200. 이 v0.1에는 검색·페이지네이션을 정의하지 않음 |
| 캐시 | 개인 정보 응답은 `Cache-Control: no-store`; 클라이언트 캐시는 사용자·세션 세대로 분리 |
| 인증 | 서버 세션 쿠키를 사용하는 제안. `HttpOnly`, HTTPS 환경의 `Secure`, `SameSite=Lax`; 브라우저 요청은 `credentials: "include"` |
| 요청 위조 방지 | 세션 확인 응답의 `csrfToken`을 변경 요청의 `X-CSRF-Token`으로 전송. 가입·로그인 전에도 익명 세션 토큰 발급. 현재 미구현 |
| 동시 수정 | 단일 문진 응답의 `ETag`와 변경 요청의 `If-Match` 사용. 아래 `recordVersion` 참조 |
| 재시도 | 생성·가져오기·전달 시뮬레이션에 `Idempotency-Key` 필수. 동일 작업 재시도 시 같은 키·본문 사용 |

인증 정보가 없거나 만료된 보호 API는 `401`이다. 존재하지 않거나 다른 사용자가 소유한 자료는 동일한 `404 NOT_FOUND`로 응답한다. `userId`는 서버 인증에서 결정하며 생성/변경 본문에 받지 않는다. 객체 접근마다 서버에서 소유권을 확인한다.

이 절의 인증 방식은 백엔드 구현을 위한 제안이다. 기존 mock에 쿠키 인증이 있다는 의미가 아니다. 실제 구현 시 세션 수명·쿠키 domain·CORS 허용 출처를 확정해야 한다. 기존 백엔드의 기본 CORS origin은 `http://localhost:5173`이므로 `http://127.0.0.1:5173`과 자동으로 같다고 취급하지 않는다.

### 3.1 서버 문진 버전과 UI revision의 구분

REST `Intake` 응답에는 현재 모델에 없는 `recordVersion: integer`를 추가한다. 예: `ETag: "intake-demo-01:v3"`.

- `recordVersion`은 답변·단계·검토 승인·snapshot 등 유효한 변경마다 증가한다. 본문이 완전히 동일한 저장은 증가시키지 않는다.
- 서버 응답의 `data.revision`은 답변 내용 변경 시 증가하는 서버 측 내용 버전으로 사용한다. 클라이언트가 보낸 숫자를 그대로 채택하지 않는다.
- 현재 프론트엔드의 `data.revision`은 로컬 타이핑 때도 증가한다. 연동 시 로컬 요청 세대와 마지막 저장 응답의 revision/ETag를 분리해야 한다. 이 변경은 아직 구현하지 않았다.
- `PUT` 저장, `PUT` 검토, `POST` 전달 시뮬레이션은 마지막으로 받은 `If-Match`를 요구한다. 헤더 누락은 `428`, 충돌은 `412`다.
- 충돌하면 서버 자료를 다시 조회해 차이를 보여주고 사용자의 재확인을 받는다. 기존 입력을 조용히 덮어쓰거나 최신 ETag만 붙여 같은 변경을 무조건 재전송하지 않는다.

## 4. 엔드포인트 목록 — 모두 제안, 미구현

아래 경로는 `/api/v1/patient` 기준 상대 경로다. ‘보호’는 로그인 필요 여부이며 변경 요청에는 3절의 CSRF 검증도 적용한다.

| Method | 경로 | 보호 | 성공 | 목적/대응 함수 |
| --- | --- | --- | --- | --- |
| POST | `/auth/signup` | 아니오 | 201 | 가입 / `signup` |
| POST | `/auth/login` | 아니오 | 200 | 로그인 / `login` |
| GET | `/auth/session` | 아니오 | 200 | 세션 복원·본인 정보 / `restore` |
| POST | `/auth/logout` | 아니오 | 204 | 현재 세션 종료 / `logout` |
| GET | `/overview` | 예 | 200 | 본인 예약·문진 전체 묶음 / `load` |
| GET | `/appointments` | 예 | 200 | 예약 목록 |
| GET | `/appointments/{appointmentId}` | 예 | 200 | 예약 상세·연결 문진 |
| GET | `/intakes` | 예 | 200 | 문진 목록 |
| POST | `/intakes` | 예 | 201 또는 200 | 생성 또는 예약의 기존 문진 재사용 / `startIntake` |
| GET | `/intakes/{intakeId}` | 예 | 200 | 문진 전체 및 당시 snapshot |
| PUT | `/intakes/{intakeId}` | 예 | 200 | 답변 전체·현재 단계 저장 / `saveIntake` |
| POST | `/intakes/import` | 예 | 201 또는 200 | 명시적 비로그인 답변 가져오기 / `importGuest` |
| GET | `/intakes/{intakeId}/summary` | 예 | 200 | 현재 저장 답변의 요약 또는 전달 당시 요약 |
| PUT | `/intakes/{intakeId}/review` | 예 | 200 | 현재 저장 버전에 대한 검토 승인/해제 |
| POST | `/intakes/{intakeId}/handoff-simulation` | 예 | 200 | 승인한 요약의 전달 시뮬레이션, 읽기 전용으로 전환 |

별도 `GET /me`, 문진 항목별 약·알레르기 CRUD, 언어 설정 API는 필요하지 않다. 현재 계정 정보는 세션 응답을 재사용하고, 약·알레르기는 문진 저장에 포함한다. `/overview`와 목록·상세는 반드시 동일한 서버 데이터 원본을 사용한다.

## 5. 요청·응답 상세 — 제안

### 5.1 가입: `POST /auth/signup`

```json
{"name":"Demo Patient","email":"patient@example.test","password":"Example123"}
```

201 응답:

```json
{"user":{"id":"patient-demo-01","name":"Demo Patient","email":"patient@example.test"}}
```

이름은 trim 후 비어 있지 않아야 하고 최대 80자다. 이메일은 trim/lowercase로 정규화하고 최대 254자이며 현재 폼의 `^\S+@\S+\.\S+$` 조건을 기본으로 검증한다. 데모 비밀번호 정책은 영문자·숫자를 각각 포함한 8자 이상, UI 최대 254자다. 이 데모 조건을 운영 보안 정책으로 확정한 것은 아니다.

`confirm`은 프론트엔드의 일치 확인용이며 전송하지 않는다. 비밀번호를 응답하지 않는다. 가입 성공은 자동 로그인·이메일 인증 완료를 뜻하지 않는다. 중복 이메일은 `409 EMAIL_EXISTS`, 형식 오류는 `422 VALIDATION_FAILED`다.

### 5.2 로그인·세션·로그아웃

`POST /auth/login` 요청:

```json
{"email":"patient@example.test","password":"Example123"}
```

성공 시 세션 쿠키를 설정하고 다음 형식을 반환한다. `GET /auth/session`도 같은 형식이다.

```json
{
  "status":"authenticated",
  "user":{"id":"patient-demo-01","name":"Demo Patient","email":"patient@example.test"},
  "expiresAt":"2026-09-17T06:00:00Z",
  "csrfToken":"example-csrf-token",
  "messageCode":null
}
```

익명 세션 확인도 200이며 보호된 사용자 데이터는 포함하지 않는다.

```json
{"status":"anonymous","user":null,"expiresAt":null,"csrfToken":"example-anonymous-csrf-token","messageCode":null}
```

만료 후 복원이면 `messageCode:"SESSION_EXPIRED"`로 구분할 수 있다. 현재 mock의 만료 시각은 epoch milliseconds지만 제안 REST 응답은 ISO 문자열이므로 어댑터에서 변환한다. `checking`은 프론트엔드 로딩 상태이며 서버 응답 상태가 아니다.

로그인 실패는 `401 LOGIN_FAILED`, 보호 요청 중 만료는 `401 SESSION_EXPIRED`다. `returnTo`는 API가 아니라 `safeReturn()`으로 검사하는 앱 내부 복귀 경로다. 서버가 받은 외부 URL로 임의 리다이렉트하지 않는다.

`POST /auth/logout`은 요청 본문 없이 현재 세션을 폐기하고 빈 본문의 204를 반환한다. 이미 로그아웃된 경우에도 204다. 전송 실패 시에도 화면과 사용자별 캐시는 즉시 비우되, 서버 세션까지 종료됐다고 표시하지 말고 종료 요청 재시도를 처리한다. 저장된 문진을 삭제하지 않는다.

### 5.3 홈과 예약 조회

`GET /overview`는 현재 `load()`를 대체할 묶음 조회다.

```json
{"appointments":[],"intakes":[],"serverTime":"2026-09-17T05:00:00Z"}
```

배열 요소는 2절 모델이고 문진에는 `recordVersion`도 포함한다. 새 계정에는 가짜 예약·문진을 자동 생성하지 않는다. 프론트엔드는 이 배열에서 다음 예약, 작성 중 문진, 최근 문진을 계산할 수 있다. 날짜 분류의 기준은 `serverTime`으로 통일한다.

`GET /appointments?group=upcoming`:

- `group`: `all`(기본), `upcoming`, `past`, `cancelled`.
- 응답: `{items:Appointment[], serverTime:string}`. 분류/정렬은 2.1절과 같다. `all`은 `startsAt` 내림차순으로 반환한다.
- 유효하지 않은 group은 `422 VALIDATION_FAILED`.

`GET /appointments/apt-demo-01` 응답:

```json
{
  "appointment":{
    "id":"apt-demo-01","userId":"patient-demo-01",
    "hospital":"Demo Clinic","department":"General practice","clinician":null,
    "startsAt":"2026-09-19T01:00:00Z","status":"scheduled"
  },
  "intake":null
}
```

연결 문진이 있으면 `intake`에 전체 `Intake`를 반환한다. `null`은 문진이 없다는 뜻이며 의료진이 미정인 것과 별개다. 취소 예약도 조회할 수 있지만 신규 문진 생성은 거절한다. 현재 UI에는 예약 상태를 변경하는 기능이 없다.

### 5.4 문진 목록·상세·생성

`GET /intakes?status=draft`의 status는 `all`(기본), `draft`, `completed`, `sent`다. `{items:Intake[],serverTime:string}`을 반환하고 `updatedAt` 내림차순으로 정렬한다. 필터 결과가 없으면 빈 items로 200을 반환한다. 유효하지 않은 status는 422다.

`GET /intakes/{intakeId}`는 전체 `Intake`와 해당 버전의 `ETag`를 반환한다. snapshot이 있으면 프론트엔드는 편집 대신 읽기 전용 상세로 이동한다. 작성 중인 문진을 조회하는 것은 새 문진을 만들지 않는다.

`POST /intakes` 요청:

```json
{"appointmentId":"apt-demo-01"}
```

예약 없이 작성할 때는 `{"appointmentId":null}`을 전송한다. `Idempotency-Key`가 필요하다.

- 새로 생성: 201, 전체 `Intake`, `ETag`, `Location: /api/v1/patient/intakes/{id}`. 초기 `step="reason"`, `status="draft"`, `data=initial()`.
- 같은 예약의 기존 문진이 있으면 상태와 관계없이 200으로 기존 문진 반환. 데이터는 수정하지 않는다. 같은 예약에 대한 동시 생성도 서버 고유 제약/트랜잭션으로 하나만 만든다.
- 현재 mock 순서와 같이 취소 예약에 이미 문진이 있으면 그 기록은 반환할 수 있다. 문진이 없는 취소 예약에 신규 생성하면 `409 CANCELLED`다.
- 예약 없는 신규 문진은 서로 다른 작업 키라면 별개로 생성한다. 같은 작업 키의 재시도만 중복 제거한다.

생성 성공의 전체 응답 예시 (`ETag: "intake-demo-01:v1"`):

```json
{
  "id": "intake-demo-01",
  "userId": "patient-demo-01",
  "appointmentId": "apt-demo-01",
  "data": {
    "version": 1,
    "revision": 0,
    "approved": false,
    "sent": false,
    "reasons": [
      ""
    ],
    "onset": {
      "status": "unasked",
      "value": ""
    },
    "course": {
      "status": "unasked",
      "value": ""
    },
    "frequency": {
      "status": "unasked",
      "value": ""
    },
    "impact": {
      "status": "unasked",
      "value": ""
    },
    "severity": {
      "status": "unasked",
      "value": ""
    },
    "history": {
      "status": "unasked",
      "value": ""
    },
    "medicines": {
      "status": "unasked",
      "value": "",
      "items": []
    },
    "allergies": {
      "status": "unasked",
      "value": "",
      "items": []
    },
    "questions": {
      "status": "unasked",
      "value": ""
    },
    "completed": []
  },
  "step": "reason",
  "status": "draft",
  "updatedAt": "2026-09-17T05:00:00Z",
  "recordVersion": 1
}
```

### 5.5 문진 저장: `PUT /intakes/{intakeId}`

`If-Match` 필수. 본문은 `{step,answers}`다. `answers`는 2.2절 예시의 `reasons`, 9개 답변 필드만 포함한 **전체 답변 객체**이며 부분 patch가 아니다. `version/revision/approved/sent/completed/userId/appointmentId/snapshot`은 받지 않는다. 서버는 현재 문진 형식 버전에 맞춰 응답 `data`를 조립한다.

```json
{
  "step":"course",
  "answers":{
    "reasons":["I would like to discuss my sleep."],
    "onset":{"status":"answered","value":"며칠 전부터","option":"며칠 전부터"},
    "course":{"status":"unasked","value":""},
    "frequency":{"status":"unasked","value":""},
    "severity":{"status":"unasked","value":""},
    "impact":{"status":"unasked","value":""},
    "history":{"status":"unasked","value":""},
    "medicines":{"status":"unasked","value":"","items":[]},
    "allergies":{"status":"unasked","value":"","items":[]},
    "questions":{"status":"unasked","value":""}
  }
}
```

200으로 갱신된 전체 `Intake`와 새 `ETag`를 반환한다.**아래 검증 단계는 저장과 전달을 구분한다.**

- 자동 저장은 빈 방문 이유, 입력 중인 빈 문자열·목록을 허용하여 초안을 잃지 않게 한다. 이를 `none`으로 정규화하지 않는다.
- 각 방문 이유/단일 value는 최대 3,000자, 약·알레르기의 name/detail은 각각 최대 300자. 현재 UI는 이유 개수와 목록 개수에 상한을 두지 않는다. 운영 서버의 전체 본문·항목 개수 제한은 별도 합의 사항이다.
- 상태 enum, 필드 자료형, 단계 enum, `option`이 해당 질문의 유효한 선택지인지 검증한다. `option`이 있으면 `option === value`여야 한다. 자유 입력은 그대로 보존한다.
- 본문 필드 누락/잘못된 형식은 422. 서버 관리 필드를 답변 저장으로 변경하려는 요청도 422.
- 답변이 변경되면 승인 해제, 데이터 revision 증가, 후속 질문 무효화를 적용한다. 서버가 상위 답변 변경을 적용한 응답을 받은 뒤에 새 후속 답변을 저장한다. 초기화 전의 오래된 후속 답변을 같은 변경으로 되살리지 않는다.
- 비활성 frequency가 요청에 남아 있으면 서버는 `unasked`로 비우고 요약에서 제외한다. 현재 단계가 비활성이 되면 `review`로 정규화해 미확인 질문을 다시 안내한다.
- `done`은 전달 시뮬레이션으로만 만들 수 있다. 일반 저장에서는 422.
- 전달된 문진 저장은 `409 READ_ONLY`다. 현재 mock은 같은 경우 기존 record를 반환하고 무시한다는 차이가 있다.

### 5.6 요약: `GET /intakes/{intakeId}/summary?locale=en`

`locale` 쿼리는 `en/ko`만 허용하며 다른 값은 422다. 생략하면 3절의 언어 헤더/기본값을 사용한다. 저장된 답변으로 결정적으로 구성한다. 질문을 미리 보지 않았거나 답변이 비어 있어도 요약 조회는 가능하며 `unasked/unanswered/unknown/declined`를 구분해 표시한다. 의료적 추론을 추가하지 않는다.

200 응답 예시(활성 질문을 모두 확인한 경우):

```json
{
  "intakeId":"intake-demo-01",
  "revision":8,
  "recordVersion":3,
  "locale":"en",
  "readOnly":false,
  "sections":[
    {"title":"Reason for visit","step":"reason","text":"1. I would like to discuss my sleep."},
    {"title":"Symptom history","step":"onset","text":"Started: A few days ago\nChanges: About the same\nDiscomfort: Not sure\nDaily impact: None"},
    {"title":"Medical history","step":"history","text":"Prefer not to answer"},
    {"title":"Medicines","step":"medicines","text":"Demo medicine · Details unknown"},
    {"title":"Allergies","step":"allergies","text":"None"},
    {"title":"Concerns and questions","step":"questions","text":"What should I keep track of?"},
    {"title":"Unconfirmed information","text":"Discomfort: Not sure\nMedical history: Prefer not to answer\nMedicines: Demo medicine · Details unknown"}
  ]
}
```

`sections`는 현재 모델과 같은 형태다. 읽기 전용일 때 `step`은 분류 정보일 뿐 편집 권한이 아니다. 전달된 문진이면 snapshot에서 생성하고 `readOnly=true`로 반환한다. 현재 문진이 아닌 다른 입력 버전으로 요약을 만들지 않는다. 요약 조회는 승인·단계·updatedAt을 변경하지 않는다.

언어를 바꿀 때마다 요약을 저장하거나 요청하지 않는다. 현재 UI는 받은 구조화 답변으로 `summary(data,locale)`를 다시 그린다. 서버 번역 요약은 초기 조회/명시적 갱신 시 사용할 수 있지만, 현재 프로토타입처럼 언어 선택 자체는 로컬 동작으로 유지한다.

### 5.7 검토: `PUT /intakes/{intakeId}/review`

마지막 저장 성공 후 받은 `If-Match`와 서버 내용 revision을 사용한다.

```json
{"approved":true,"revision":8}
```

승인 해제는 `approved:false`다. 200으로 전체 `Intake`와 새 ETag를 반환한다. 승인만 바뀌면 `recordVersion`은 바뀌지만 내용 revision은 바뀌지 않는다. 이미 같은 승인 상태에 대한 동일 요청은 상태를 다시 변경하지 않는다.

승인/전달에 필요한 검증:

1. 방문 이유가 한 개 이상이고 각 항목이 trim 후 비어 있지 않다.
2. 모든 활성 질문이 `unasked`가 아니다. 명시적 `unanswered/none/unknown/declined`는 각각의 의미를 유지하며 허용한다.
3. `answered`인 단일 답변은 비어 있지 않다. `answered`인 목록에는 항목이 한 개 이상 있어야 한다. 항목 이름·상세의 빈 값은 ‘모름’으로 허용한다.
4. 해당 revision의 검토 화면까지 진행했고 전달 snapshot이 없다.

미확인/빈 답변은 `422 VALIDATION_FAILED`, 내용 revision 불일치는 `409 REVISION_MISMATCH`, 이미 전달한 기록은 `409 READ_ONLY`다. 현재 UI의 체크박스 자체는 별도 서버 검증 없이 변경되므로 이 엄격한 승인 API는 어댑터와 함께 구현해야 한다.

### 5.8 전달 체험: `POST /intakes/{intakeId}/handoff-simulation`

`If-Match`와 `Idempotency-Key`가 필요하다.

```json
{"revision":8}
```

서버가 현재 버전의 `approved=true`와 5.7절 검증을 확인한다. 승인 누락은 `409 REVIEW_REQUIRED`다. 검증, snapshot 생성, `data.sent=true`, `status="sent"`, `step="done"` 전환은 한 트랜잭션으로 처리한다. 200으로 snapshot을 포함한 전체 `Intake`와 새 ETag를 반환한다.

제안 REST snapshot은 현재 snapshot 필드에 `simulated:true`를 추가한다. `sentAt`은 서버에서 만든 UTC 시각이다. `deliveredAt`, `doctorReadAt`, 접수번호 등 구현되지 않은 실제 전달/열람 정보를 만들지 않는다. snapshot은 이후 수정할 수 없다.

동일 작업 키/동일 본문 재시도는 첫 성공 응답과 같은 snapshot을 반환한다. 새 작업 키로 이미 전달된 문진을 다시 요청하면 `409 ALREADY_SENT`이며 상세 조회로 이동한다. 실패했다고 새 문진을 생성하지 않는다.

### 5.9 비로그인 답변 가져오기: `POST /intakes/import`

사용자가 ‘내 계정으로 가져오기’를 명시적으로 선택한 경우에만 요청한다. 요청 형식은 5.5절과 같은 `{step,answers}`에 `importId:string`을 추가한다. `importId`는 한 로컬 초안의 가져오기 작업에 발급한 안정적인 ID이며 재시도 중 유지한다. `Idempotency-Key`도 같은 작업에서 유지한다. `appointmentId`는 항상 `null`이다.

새 생성은 201, 같은 사용자·importId의 동일 입력 재시도는 기존 문진으로 200이다. 같은 importId에 다른 입력이면 `409 IMPORT_CONFLICT`. 다른 사용자의 같은 importId는 별도 범위다. 최소 한 개의 비어 있지 않은 방문 이유가 없으면 `422 EMPTY`다.

**현재 mock과의 명시적 차이:** mock은 로컬 `data.approved/sent`도 복사하고 JSON 문자열로 중복을 확인한다. 제안 서버 계약은 클라이언트의 완료 플래그를 서버 승인·전달 증거로 채택하지 않는다. 답변과 진행 위치만 가져오고 `approved=false`, `sent=false`로 시작한다. 로컬 `done` 단계는 `review`로 바꿔 다시 확인한다. 이 정책은 실제 연동 시 화면 안내에도 반영해야 하며, 현재 코드는 변경하지 않았다.

가져오기가 성공한 뒤에만 해당 로컬 초안을 제거한다. 실패·시간 초과에는 원본과 importId를 유지한다. 로그인만으로 자동 가져오지 않는다.

## 6. 오류·재시도·오래된 응답

제안 오류 형식은 기존 백엔드의 `error` envelope를 유지하고 필드 오류의 `code`를 추가한다. 기존 `/api/sessions`가 이미 아래 추가 코드를 반환한다는 뜻은 아니다.

```json
{
  "error":{
    "code":"VALIDATION_FAILED",
    "message":"Check the highlighted fields.",
    "details":[{"field":"answers.reasons.0","code":"REQUIRED","issue":"Enter a reason for your visit."}],
    "request_id":"req-example-01"
  }
}
```

| HTTP | 제안 코드 | 프론트엔드 처리 |
| --- | --- | --- |
| 401 | `LOGIN_FAILED` | 이메일 보존, 비밀번호 비움, 재입력 안내 |
| 401 | `AUTH_REQUIRED`, `SESSION_EXPIRED` | 보호 데이터·요청 세대 정리, 유효한 내부 경로만 보관하고 로그인으로 이동 |
| 403 | `CSRF_FAILED` | 변경 중단, 세션/CSRF 토큰 재확인; 입력 유지 |
| 404 | `NOT_FOUND` | 없는 ID·다른 소유자 ID에 같은 기록 없음 화면 |
| 409 | `EMAIL_EXISTS` | 이메일 필드 옆 오류 |
| 409 | `CANCELLED`, `READ_ONLY`, `ALREADY_SENT` | 현재 예약/문진 재조회, 허용되는 조회 행동만 제공 |
| 409 | `REVIEW_REQUIRED`, `REVISION_MISMATCH` | 최신 요약을 확인하고 다시 승인 |
| 409 | `IDEMPOTENCY_CONFLICT`, `IMPORT_CONFLICT` | 다른 본문으로 같은 작업 키를 재사용하지 않음 |
| 412 | `VERSION_CONFLICT` | ETag 충돌; 입력을 유지하고 최신 기록과 비교 |
| 422 | `VALIDATION_FAILED`, `EMPTY` | 필드별 이유·해결 방법, 첫 오류로 포커스 |
| 428 | `PRECONDITION_REQUIRED` | 저장 버전 먼저 조회; 임의 덮어쓰기 금지 |
| 429 | `RATE_LIMITED` | `Retry-After`를 존중하고 중복 제출 차단 |
| 503 | `SERVICE_UNAVAILABLE` | 입력·단계 유지, 명시적 재시도 |
| 500 | `INTERNAL` | 일반 오류와 request ID, 재시도 안내 |

현재 mock의 `LOAD_FAILED`는 제안 HTTP 어댑터에서 503에 대응할 수 있고, `INVALID`는 422로 매핑한다. `STALE`은 화면을 떠난 요청 등 클라이언트 취소 처리이며 서버 오류로 보여주지 않는다. 현재 오류의 `message`는 번역 키 문자열인 경우가 많지만 HTTP 계약에서 그 키를 고정하지 않는다. 프론트엔드가 안정적인 `error.code/details[].code`를 로컬 메시지에 매핑하고, 미지원 코드는 해당 언어의 일반 오류로 처리한다.

멱등성 키는 **인증 사용자 + HTTP method + 경로 + 키** 범위로 관리하고 본문 fingerprint와 최초 상태 코드/응답을 저장한다. 재시도 보장 기간은 이 제안에서 최소 24시간이다. 이미 완료된 동일 요청의 재전송은 소유권/인증 확인 후 멱등성 응답을 먼저 찾아야 한다. 이전 성공으로 오래된 If-Match를 가지고 있더라도 단순 412로 바꾸지 않는다. 같은 키에 다른 본문은 409다. 동시 실행 중인 같은 키의 요청도 한 번만 수행한다.

네트워크 오류는 서버 처리 여부를 확정하지 못한다. 생성·가져오기·전달은 같은 작업 키로 재시도한다. PUT 저장의 응답이 유실되면 최신 문진을 읽어 이미 반영됐는지 확인한다. 로그아웃/계정 변경 전 시작한 응답은 완료되어도 새 계정 화면에 반영하지 않는다. 요청 취소가 서버 작업 취소를 보장한다고 가정하지 않는다.

## 7. 서버로 보내지 않는 동작

| 동작 | 현재 처리 및 연동 원칙 |
| --- | --- |
| 언어 선택 | localStorage + React 구독. 서버 저장/제출/조회 없음 |
| 날짜 표시 | 저장된 ISO 시각을 선택 언어로 표시, `Asia/Seoul` 유지 |
| 비로그인 문진 | 기존 sessionStorage와 로컬 mock 유지. 별도 익명 REST 계약은 이번 문서 범위 밖 |
| 질문 선택·분기·도움말 | 현재 질문 정의/모델 사용. 질문 총수·완료 백분율 API 없음 |
| 요약 텍스트 다운로드 | 현재 화면 데이터로 Blob 생성. 다운로드 서버 API 없음 |
| 약·알레르기 추가/수정/삭제 | 로컬 배열 변경 후 문진 전체 저장. 개별 항목 endpoint 없음 |
| ‘데모 초기화’, 실패·지연·만료 체험 | mock 전용. 운영의 계정 삭제/예약 취소 API로 연결하지 않음 |

## 8. 기존 백엔드 API와의 관계

아래만 현재 FastAPI 코드에 구현되어 있다. 이번 문서 작업에서는 서버를 실행하거나 HTTP 호출 성공을 검증하지 않았다.

| Method | 실제 코드의 경로 | 현재 기능 |
| --- | --- | --- |
| GET | `/api/health` | `{"status":"ok"}` |
| POST | `/api/sessions` | `{patient_ref?,locale?}`로 문진 세션 생성, 201 |
| GET | `/api/sessions/{session_id}` | 슬롯·대화 기록을 포함한 세션 상태 |
| POST | `/api/sessions/{session_id}/messages` | `{text}` 입력·후속 프롬프트 |
| POST | `/api/sessions/{session_id}/slots/{slot_id}` | `{action:"confirm"\|"edit"\|"skip",value?}` |
| POST | `/api/sessions/{session_id}/complete` | 요약 생성 후 `completed` |
| GET | `/api/sessions/{session_id}/summary` | 완료 후 의료진용 구조화 요약 |

주요 차이:

- 기존 backend의 `patient_ref`는 인증된 소유권을 보장하지 않는다. 계정 인증·예약·사용자별 문진 목록 라우트가 없다.
- backend 슬롯 상태는 `empty/candidate/confirmed/skipped`로, UI의 여섯 답변 상태와 일대일 대응하지 않는다. ‘없음·모름·답변 거절’을 모두 skipped로 축약하면 정보가 손실된다.
- backend의 `symptom_duration_days`는 숫자지만 UI onset은 자유 서술/범위 선택이다. ‘며칠 전부터’를 임의의 일수로 변환하지 않는다.
- UI course/frequency/impact와 우선순위가 있는 복수 방문 이유·질문은 기존 슬롯에 그대로 대응하지 않는다.
- backend `complete`는 환자 요약 승인 게이트가 없으며 UI의 전달 시뮬레이션이나 의사 열람과 동의어가 아니다.
- 기존 기본 locale은 `en-AU`, 새 UI 언어는 `en/ko`다. 언어 지원을 확인하지 않은 채 새 UI의 한국어 지원이 backend에도 있다고 가정하지 않는다.
- 기존 summary는 `sections:Record<string,string>`이고 UI는 배열+수정 step을 사용한다. 별도 어댑터나 backend 모델 확장이 필요하다.

따라서 `/api/sessions`를 새 `/intakes`의 단순 URL 별칭으로 연결하지 않는다. 기존 세션 엔진을 재사용할지는 답변 상태·추가 필드·승인·소유권 계약을 확정한 뒤 결정한다. 기존 API 상세는 [api-contract.md](api-contract.md)를 참조한다.

## 9. 실제 연동 시 프론트엔드 변경 지점

1. `account/service.js`의 mock과 별도로 HTTP 어댑터를 추가한다. 성공 응답 스키마·오류 envelope를 검증하고 credentials, CSRF, 세션 세대, 취소 신호를 처리한다.
2. 현재 `Portal`의 `onAccountSave()`는 즉시 boolean을 반환한다. Promise 기반 자동 저장 큐로 바꾸고 저장 중/실패/재시도 상태를 분리한다. ‘저장하고 목록으로’는 최신 저장 성공 후 이동한다.
3. 입력마다 동기 저장하던 동작을 최신 초안 중심으로 병합하고 동일 문진의 쓰기를 직렬화한다. 매 응답의 ETag를 다음 쓰기에 사용하며 오래된 응답으로 최신 입력을 덮어쓰지 않는다. 방문 이유·경과 변경의 저장과 서버 측 초기화를 완료한 뒤 새 후속 질문의 답변을 저장한다.
4. 저장 → 저장된 버전의 요약 → 승인 → 전달 순서를 보장한다. 현재처럼 클라이언트 `data.sent=true` 저장만으로 서버의 전달 상태를 바꾸지 않는다.
5. `/overview`를 현재 `load()` 형식으로 연결하거나 목록·상세 API를 이용하도록 화면을 조정한다. 후자의 경우 서버 필터/시각 기준과 홈 상태를 일치시킨다.
6. 가져오기의 importId/작업 키를 성공 전까지 유지하고, 5.9절의 서버 재검토 정책을 안내한다. 이름·답변을 자동 번역하거나 전체 비로그인 기록을 자동 귀속하지 않는다.
7. 현재 프론트엔드에는 업무 API base URL 설정이나 HTTP 클라이언트가 없다. 환경별 base URL과 개발 프록시/CORS를 추가할 때 3절의 경로·쿠키 정책과 맞춘다.

### 연동 수용 기준

- 가입 → 로그인 → 본인 홈 → 로그아웃과 로그인 후 내부 경로 복귀.
- 다른 소유자 ID/없는 ID/만료된 세션, 늦은 A 계정 응답이 B에 노출되지 않음.
- 같은 예약·같은 작업의 중복 요청이 한 문진만 생성.
- `none/unknown/declined/unanswered/unasked`를 JSON 왕복 후에도 구분.
- 상위 답변 수정에 따른 후속 답변 제거, 승인 해제, 수정되지 않은 다른 정보 보존.
- 동시 수정의 412, 응답 유실 후 같은 키 재시도, 실패 후 원문·단계 보존.
- 승인된 저장 버전만 전달 시뮬레이션 가능, 전달 snapshot 불변.
- 언어 전환 시 현재 화면·입력·필터·로그인·저장 버전이 유지되고 쓰기 요청이 발생하지 않음.

## 10. 이 문서의 검증 범위

현행 함수·필드·enum·입력 길이·분기·저장 수명·실제 backend 라우트를 소스와 대조했다. 문서 내 JSON 예시 15개와 관련 문서의 상대 링크 29개를 검사했고, backend 라우트 7개를 소스 decorator와 대조했다. 초기 문진 예시·완료 상태·영문 요약 예시·선택지 저장값도 현재 모델 함수 결과와 일치함을 확인했다. 애플리케이션 동작은 변경하지 않았으며 빌드·브라우저 회귀 테스트는 다시 실행하지 않았다. 제안 endpoint의 HTTP 통합 테스트, 서버 인증/영속 저장/동시성 검증은 구현 후 수행해야 한다.
