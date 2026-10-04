# Integration contract (v1)

The production app extends the original FastAPI/React repository. Legacy engine and tests remain available; legacy unauthenticated APIs must be disabled in the deployed app.

## HTTP
Same-origin `/api/v1`, HttpOnly cookie authentication. JSON error `detail` readable by client. All product UI English.
- GET /config -> {models:[{id,label}],default_model,auth_configured,mail_configured,doctor_configured}
- POST /auth/request-code {email,role:"patient"|"doctor"} -> {message,expires_in}; no codes in response.
- POST /auth/verify {email,code,role} -> {user:{id,email,name,role}}
- GET /auth/me -> {user}; PATCH /auth/me {name} -> {user}; POST /auth/logout
- GET /workflows -> array of {id,title,category,description,questions:[{key,label,question,...}],...}
- GET /intakes -> array of session summaries/full session, owner only
- POST /intakes {consent:true,model?,workflow_ids:[],title?} -> full session
- GET /intakes/{id} -> full session
- POST /intakes/{id}/messages {text,action?:"answer"|"unknown"|"skip"} -> full session
- POST /intakes/{id}/review -> full session with draft summary
- PATCH /intakes/{id}/review {text} -> full session (patient correction, remains review)
- POST /intakes/{id}/approve {version:number,doctor_email?:string} -> full session
- POST /intakes/{id}/withdraw -> full session (revokes doctor visibility)
- DELETE /intakes/{id} -> 204
- GET /clinician/intakes -> only approved shared sessions assigned to authenticated allowlisted clinician
- GET /clinician/intakes/{id} -> full approved session
- POST /clinician/intakes/{id}/reviewed -> full session
- POST /intakes/{id}/attachments multipart file -> attachment
- GET /intakes/{id}/attachments/{attachment_id} -> authorized file download
- DELETE /intakes/{id}/attachments/{attachment_id} -> 204; only before approved
- POST /transcriptions multipart file -> {text}; authenticated, OpenAI only

## Session JSON
{id,title,patient_id,patient_email,patient_name,created_at,updated_at,status:"active"|"review"|"approved"|"interrupted"|"withdrawn",model,consent:true,concerns:[{id,workflow_id,title,slots:{key:{label,value,status:"FILLED"|"MISSING"|"UNCERTAIN"|"SKIPPED"|"NOT_APPLICABLE",evidence?}}}],shared_slots:{key:slot},messages:[{id,role:"assistant"|"patient",text,created_at}],plan:{workflow_ids:[],rationale,next_target,coverage,resolution,turns,max_turns},current_question:{key,question,concern_id?}|null,summary:{version,text,sections?:[],gaps:[],approved_at?}|null,attachments:[],doctor_email?,reviewed_at?,ai_status?:{mode:"live"|"unavailable",message?}}

## Python engine contract
`app.product.engine`: `new_intake(patient:dict,model:str,workflow_ids:list[str],title:str|None=None)->dict`, `process_message(session:dict,text:str,action:str='answer')->dict`, `build_review(session:dict,correction:str|None=None)->dict`. Engine pure state mutation/return; provider calls inside engine when appropriate. Routes own persistence, authorization, approval/withdraw/delete. IDs uuid hex. `app.product.workflows`: `WORKFLOWS` list and `get_workflow(id)`.
`app.product.database`: `get_connection()` sqlite3 context manager or direct connection (document); `load_intake(id)->dict|None`, `save_intake(session)->None`, `list_intakes()->list[dict]`, `init_db()`. Media will use these public helpers. `app.product.auth`: `require_user(request:Request)->dict` FastAPI dependency, raises 401. User {id,email,name,role}.
Root owns product media.py, app/core/main.py wiring and deployment. Auth agent owns product database.py, auth.py, routes.py, config.py; engine agent owns engine.py, workflows.py, provider.py; UI agent owns frontend.
