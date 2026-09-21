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
uvicorn app.core.main:app --reload
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

### LLM provider

The backend defaults to the deterministic `FakeLLM`, so local development and
tests do not require network access or credentials:

```dotenv
LLM_PROVIDER=fake
```

To use the Azure-hosted OpenAI-compatible endpoint, configure all four values in
the local `backend/.env` file:

```dotenv
LLM_PROVIDER=azure
LLM_API_KEY=<secret>
LLM_BASE_URL=https://<resource>.services.ai.azure.com/openai/v1/
LLM_MODEL=<deployment-name>
```

`LLM_MODEL` is the Azure deployment name. Never commit the real API key. The
adapter uses a 30-second timeout, at most two SDK retries, structured Pydantic
outputs and deterministic fallbacks. API tests explicitly override the provider
with `FakeLLM`, even when a developer's local `.env` selects Azure.
