# Setup

## Prerequisites

- Python 3.11+ (the code uses 3.10+ typing syntax; macOS system Python 3.9 will
  not work — use e.g. `python3.11`)
- Node.js 20+

## Backend

```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in values
uvicorn app.core.main:app --reload   # entrypoint TBD
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Running tests

```bash
cd backend
pytest
```

## Environment variables

See [../backend/.env.example](../backend/.env.example). Copy it to `backend/.env`
and fill in values. Never commit `.env`.
