# Conversational Banking Mock

A local, synthetic-data demonstration of the conversational banking architecture. Natural-language requests create one durable workflow containing one or more work items; each financial item is bound to its own consent challenge. Only the deterministic transaction worker calls the mock Commit Gateway. This is not a banking product and all customer, account, balance, transaction, and bank-reference data are synthetic.

## Run locally

Requirements: Python 3.12+, Node.js 20+, npm.

```bash
# Terminal 1 — backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

```bash
# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The API and generated OpenAPI documentation are at <http://localhost:8000> and <http://localhost:8000/docs>. The presentation runs independently: open `presentation/index.html` in a browser or serve the repository root with `python -m http.server 9000` and visit `/presentation/`.

## Tests and build

```bash
cd backend && pytest
cd frontend && npm test
cd frontend && npm run build
cd frontend && npx playwright install chromium && npm run test:e2e
```

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The frontend is available on port 5173 and the API on port 8000. SQLite data is stored in the `backend_data` volume.

## Demo scenarios

Use the sample requests in the UI to try balance inquiry, a transfer, and the dependent multi-intent request. Consent buttons submit structured challenge decisions rather than chat messages. The developer panel can simulate policy denial, consent rejection/expiry, bank failures, unknown outcomes with status reconciliation, delayed events, and duplicate events.

See [docs/demo-script.md](docs/demo-script.md), [docs/api-contracts.md](docs/api-contracts.md), and [docs/architecture-decision.md](docs/architecture-decision.md). A standalone explorable architecture presentation is under `presentation/`.

## Production boundary

All identities and controls in this project are mock demonstrations. A production deployment would replace them with OAuth 2.0/OIDC user and service authorization, workload identity, mTLS, managed secrets/keys, a durable event backbone, and bank-owned APIs and status reconciliation.
