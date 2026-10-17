# Economic Indicators Dashboard

A React and FastAPI dashboard for viewing Indian economic indicators, NSE market prices, historical trends, source details, and collection freshness. The browser requests only this project's FastAPI API; it never calls or scrapes upstream providers directly.

## Architecture

```text
React + Vite frontend  →  FastAPI API  →  PostgreSQL
                              ↓
                     scheduled collectors
                              ↓
             NSE, World Bank, GST Portal, MoSPI,
             Department of Commerce, Union Budget
```

The frontend requests the authenticated dashboard API on load, every 60 seconds by default, and when the user selects **Refresh data**. The API returns the latest validated PostgreSQL snapshot. Scheduled collectors run server-side, so frontend refreshes never call the upstream providers directly. The polling interval is configurable with `VITE_DASHBOARD_POLL_SECONDS` (minimum 15 seconds); polling is the documented update mechanism instead of SSE.

## Included dashboard panels

1. GDP Growth — India and World
2. Debt to GDP Ratio — India
3. Imports, Exports and Trade Balance
4. GST Tax Collection
5. Inflation — India
6. Government Expenditure, including capital expenditure

Every panel stays visible. If its source has no valid result, the value is shown as `—` with an unavailable state rather than a made-up or fixture value. A development fixture is available only for local development and is not presented by the frontend as live data.

## Data sources and transformations

| Dashboard data | Public source | Transformation | Important limitation |
| --- | --- | --- | --- |
| Market ticker | NSE `allIndices` | Direct index level and change | NSE endpoint availability and response shape can change. |
| GDP growth, India and World | World Bank GDP Growth API (`NY.GDP.MKTP.KD.ZG`) | Annual percentage values; six latest published values retained | Annual figures can be revised and have publication lag. |
| Debt to GDP | World Bank Central Government Debt API (`GC.DOD.TOTL.GD.ZS`) | Annual central-government-debt percentage; six latest published values retained | India’s currently published values have material publication lag. The UI displays the observation year. |
| Trade | Department of Commerce monthly trade report | Up to six recent monthly reports are collected; USD million is converted to USD billion and balance verified as exports minus imports | The official Livewire report can be temporarily unavailable or revised. |
| GST collection | GST Portal monthly release PDF | Up to six recent official releases are collected; gross GST revenue is converted from ₹ crore to ₹ lakh crore | Values are provisional and may be revised. The monthly average is calculated only from retained live monthly releases. |
| Inflation | MoSPI CPI release PDF | Up to six recent CPI releases are collected; the all-India combined year-on-year rate is compared with RBI’s 4% target | CPI releases may be provisional or revised. |
| Government expenditure | Union Budget at a Glance PDF | Total and capital expenditure converted from ₹ crore to ₹ lakh crore | This is the Budget Estimate, not final actual expenditure. |

The authenticated `/api/v1/sources` endpoint exposes each source URL, refresh frequency, freshness state, and source-specific limitation. Every dashboard card displays its source and as-of date.

## Local setup

The fastest path is `docker compose up --build` (see
[Docker Compose (local/evaluation)](#docker-compose-localevaluation) below),
which starts Postgres, the API and the frontend together, with Postgres bound
to `127.0.0.1` only. The steps below are the manual, no-Docker path.

### Prerequisites

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 or newer
- PostgreSQL 17 or newer

### 1. Configure PostgreSQL

Create a local database and user, then copy the backend environment template:

```bash
cd backend
cp .env.example .env
```

Set at least these values in `backend/.env`:

```dotenv
DATABASE_URL=postgresql://your_user:your_password@localhost:5432/economic_dashboard
JWT_SECRET_KEY=use_a_random_secret_of_at_least_32_characters
CORS_ORIGINS=http://localhost:5173
COLLECTOR_ENABLED=true
```

Keep `.env` private. It is ignored by Git and must never contain a committed password, token, or production signing key.

### 2. Install backend dependencies and migrate

```bash
cd backend
uv sync
uv run python -m app.migrate
```

### 3. Create an evaluation account

```bash
cd backend
uv run python -m app.create_user panel@example.com --role viewer
```

The command securely prompts for the password twice. Share the resulting email and password with evaluators separately; do not put them in the repository or this README.

### 4. Collect live snapshots

The API scheduler performs this automatically when `COLLECTOR_ENABLED=true`. To run individual collectors while developing:

```bash
cd backend
uv run python -m app.collect_nse
uv run python -m app.collect_world_bank
uv run python -m app.collect_debt
uv run python -m app.collect_trade
uv run python -m app.collect_gst
uv run python -m app.collect_inflation
uv run python -m app.collect_expenditure
```

If an upstream provider fails, the collector keeps the most recent validated value and marks it stale. If no valid value has ever been collected, it records the source as unavailable.

### 5. Run the API

```bash
cd backend
uv run uvicorn app.main:app --reload
```

API documentation is available locally at `http://localhost:8000/docs` and the health endpoint is `http://localhost:8000/health`.

### 6. Run the frontend

In a second terminal:

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173` and sign in using the separately created account. `VITE_API_BASE_URL` is the frontend’s configurable API base URL and defaults to `http://localhost:8000/api/v1`.

## API routes

| Method | Route | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | No | API and PostgreSQL health check. |
| `POST` | `/api/v1/auth/login` | No | Exchange email/password for a JWT. |
| `GET` | `/api/v1/auth/me` | Bearer JWT | Return the signed-in user. |
| `GET` | `/api/v1/dashboard` | Bearer JWT | Return ticker, indicator values, comparison data, source status, and history. |
| `GET` | `/api/v1/indicators` | Bearer JWT | List active indicators. |
| `GET` | `/api/v1/indicators/{indicator_id}` | Bearer JWT | Return one indicator’s metadata. |
| `GET` | `/api/v1/indicators/{indicator_id}/history` | Bearer JWT | Return the indicator’s validated history. |
| `GET` | `/api/v1/sources` | Bearer JWT | Return sources, refresh intervals, status, and limitations. |

Login request:

```json
{"email":"panel@example.com","password":"your-private-password"}
```

Login response:

```json
{"access_token":"<jwt>","token_type":"bearer","expires_in":3600}
```

The frontend sends the token as `Authorization: Bearer <jwt>`, retains it in browser local storage for the active local session, and clears it after logout or an API `401` response. The expiry is controlled by `ACCESS_TOKEN_EXPIRE_MINUTES`.

## Environment variables

Backend variables are defined in [backend/.env.example](backend/.env.example). Key values are:

- `APP_ENV`, `API_PREFIX`, `DATABASE_URL`
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ORIGINS`
- `COLLECTOR_ENABLED`, `COLLECTOR_INTERVAL_MINUTES`, `COLLECTOR_RUN_ON_STARTUP`
- `NSE_BASE_URL`, `WORLD_BANK_BASE_URL`, `TRADE_BASE_URL`, `GST_BASE_URL`, `MOSPI_BASE_URL`, `EXPENDITURE_BASE_URL`
- source cache/refresh settings and `REQUEST_TIMEOUT_SECONDS`

Frontend variables are defined in [frontend/.env.example](frontend/.env.example):

- `VITE_API_BASE_URL`
- `VITE_DASHBOARD_POLL_SECONDS`

## Database and validation

PostgreSQL stores users, indicators, source metadata, observations, collection runs, and refresh status. Schema migrations are in `backend/migrations/`. The backend uses parameterized psycopg queries only; no SQL statement is built from user-controlled input.

Each collector validates identifier, units, range, finite numeric values, dates, comparisons, and JSON payload serializability before an observation can be stored. A failed refresh does not overwrite the last valid observation.

## Docker Compose (local/evaluation)

[docker-compose.yml](docker-compose.yml) runs Postgres, the API and the frontend together on one machine, for local development or panel evaluation — it is not the required production topology (see below).

```bash
cp .env.example .env    # set POSTGRES_PASSWORD and JWT_SECRET_KEY
docker compose up --build
docker compose exec api uv run python -m app.create_user panel@example.com --role viewer
```

Postgres publishes to `127.0.0.1:5432` only (not `0.0.0.0`), so it is not reachable from outside the host; the API reaches it over the compose network by service name. The frontend is served at `http://localhost:8080`, the API at `http://localhost:8000`.

## Production deployment

The API and frontend are separate deployables: [backend/Dockerfile](backend/Dockerfile) packages FastAPI on port 8000, while [frontend/Dockerfile](frontend/Dockerfile) produces the independently hosted static site on port 8080. The production deployment procedure, private-database requirements, required secrets, release checks, and URL-submission checklist are in [deployment/README.md](deployment/README.md).

Set `APP_ENV=production`, a unique `JWT_SECRET_KEY`, an HTTPS-only frontend origin in `CORS_ORIGINS`, and a private PostgreSQL connection string. The API rejects wildcard CORS origins and HTTP origins in production. Do not publish the database port or place an HTTP proxy in front of it.

## Tests

```bash
cd backend
uv run pytest -q tests

cd ../frontend
npm run build
npm run lint
```

## Assumptions and known limitations

- The dashboard is designed around the supplied Figma at desktop width and includes a responsive mobile layout.
- The Department of Commerce trade report site (`tradestat.commerce.gov.in`) renders its monthly data through a server-side Livewire component; the page itself loads, but its AJAX "update" endpoint (used to request a specific month) currently returns HTTP 404, so no exports/imports/trade-balance observation can be collected from it right now. This is an upstream change on the government site, not a bug in the collector — the UI correctly shows an unavailable panel rather than fixture or fabricated data.
- World Bank debt-to-GDP is used because it is a public documented series, but its currently published India observations are delayed relative to the US series. The panel explicitly displays each country's own published period (e.g. "India (2018)" vs "US (2024)") rather than implying they are the same year.
- The Figma design's second Debt to GDP card is labelled "Ind vs US". The dashboard fetches both India's and the US's central government debt-to-GDP from the same World Bank indicator (`GC.DOD.TOTL.GD.ZS`, countries `IND;USA`) and shows the real, independently-sourced value for each — no figure is fabricated or copied from one country to the other.
- GST’s average becomes available after two or more retained live monthly releases. It is not calculated from development fixture data.
- Public frontend/API/health URLs, portfolio URL/project links, the separately shared evaluation credentials, and the required screen-recording must be supplied by the deployment owner after they choose a hosting account and publish the application. No credentials, public URLs, or portfolio details were present in this repository, so none are fabricated here.
