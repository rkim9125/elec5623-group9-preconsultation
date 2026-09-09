# API Contract

> Draft skeleton. Keep this in sync with `backend/app/api/` and `frontend/src/api/`.

## Conventions

- Base URL: `/api`
- Content type: `application/json`
- Auth: (TBD)
- Errors: `{ "detail": "<message>" }` with appropriate HTTP status

## Endpoints

### Health

`GET /api/health`

- **Response 200:** `{ "status": "ok" }`

### (Intake — TBD)

`POST /api/intake`

- **Request:** (TBD)
- **Response:** (TBD)

### (Summary — TBD)

`GET /api/intake/{id}/summary`

- **Request:** (TBD)
- **Response:** (TBD)

## Shared types

- (TBD)
