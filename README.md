# UK Wind Forecast Intelligence

This project builds a full-stack analytics dashboard for day-ahead wind-generation assessment in the UK. It supports a viewing and decision workflow for electricity procurement teams using the latest wind forecast available at a defined decision cutoff, while comparing that forecast against actual wind generation from Elexon.

## Business objective
The utility needs to understand the wind generation forecast that was available at its purchasing decision cutoff, compare it with actual generation, and quantify forecast error. This system does not determine total demand, supply-demand shortfall, target procurement, or optimal purchase cost; those require additional demand, price, and market inputs beyond wind generation data alone.

## Feature list
- UK-local decision cutoff configuration with Europe/London timezone conversion
- Elexon WINDFOR and FUELHH stream integration with explicit live-data validation and missing-data warnings
- Forecast selection based on `publishTime <= cutoff` for each delivery period
- MAE, RMSE and signed bias calculation over matched periods
- Data-quality warnings and missing-period coverage tracking
- Responsive dashboard with charts and period table
- CSV export for the selected date and cutoff

## Architecture and data flow
- Frontend: React + TypeScript + Vite + Recharts
- Backend: FastAPI + Pydantic + Pandas/NumPy + HTTPX
- Data source: Elexon dataset streams for `WINDFOR` and `FUELHH`
- Query flow: frontend requests `/api/overview` and `/api/forecast-history`; backend fetches upstream Elexon data, normalizes timestamps, applies cutoff logic, computes metrics, and responds with structured JSON.

## Directory structure
- `backend/app` – FastAPI app, analytics logic, services, routes
- `backend/tests` – backend unit tests
- `backend/scripts` – validation helpers
- `frontend/src` – React dashboard and service layer
- `docker-compose.yml` – local orchestration
- `.env.example` – environment template

## Tech stack
- React 18
- Vite
- TypeScript
- Tailwind CSS
- Recharts
- FastAPI
- Pandas
- NumPy
- HTTPX
- Pytest

## Local run
### Backend
Windows PowerShell:
```powershell
Set-Location backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

macOS/Linux:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
Windows PowerShell, macOS, or Linux:
```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## Docker
Docker Compose uses same-origin `/api` proxying from the frontend container to the backend container. It does not require a local `.env` file; copy `.env.example` to `.env` only when you want to override defaults.
```bash
docker compose up --build
```
Expected ports:
- Backend: http://localhost:8000
- Frontend: http://localhost:5173

## Environment variables
Copy `.env.example` to `.env` to override local defaults. `VITE_API_BASE_URL` is optional for local and Docker Compose use; set it to the backend origin when deploying the frontend as a separate static site.
```bash
ELEXON_BASE_URL=https://data.elexon.co.uk/bmrs/api/v1
DEFAULT_CUTOFF=11:00
CACHE_TTL_SECONDS=300
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
FRONTEND_URL=http://localhost:5173
```

## API endpoint documentation
- `GET /api/health` – health check
- `GET /api/overview?date=2026-01-15&cutoff=11:00` – overview and metrics for a delivery date
- `GET /api/forecast-history?date=2026-01-15&cutoff=11:00` – forecast revisions for the date
- `GET /api/export?date=2026-01-15&cutoff=11:00` – CSV export of normalized period records

## Forecast-selection methodology
For each January 2026 delivery period, the backend normalizes timestamps to timezone-aware datetimes in Europe/London, converts the configured decision cutoff into UTC, and selects the latest `WINDFOR` record with `publishTime <= cutoff`. Later revisions are excluded from decision-time accuracy calculations. If no eligible forecast exists, that period is marked missing. Actuals and forecasts are joined by delivery `startTime`, not by row position.

The documented `WINDFOR` stream filters by `publishDateTimeFrom` and `publishDateTimeTo`; this app queries the 14 days before delivery through two days after delivery to retrieve both decision-time candidates and later revisions for display. Analytics independently excludes publications after the configured cutoff. The two-day history lookahead is an application query window, not an Elexon completeness guarantee. The documented `FUELHH` stream filters by `settlementDateFrom`, `settlementDateTo`, and `fuelType=WIND`. Returned records are then filtered to the selected delivery date and joined on `startTime`. These endpoints document no pagination parameters; the app does not assume undocumented pagination.

Official endpoint documentation:
- [WINDFOR stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream)
- [FUELHH stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream)

## Metric definitions
- MAE = mean absolute error, in MW
- RMSE = root mean square error, in MW
- Signed bias = mean forecast minus actual error, in MW
- Valid matched periods only; missing periods are not silently replaced with zero
- Coverage = matched forecast/actual periods divided by 48 expected half-hour delivery periods for the selected January date. The denominator is fixed at 48; unavailable values remain null.

## Tests
```bash
cd backend
python -m pytest -q
cd ../frontend
npm run build
```
The backend tests cover selection boundaries, Europe/London conversion, upstream failures, documented Elexon query parameters, missing/duplicate records, metrics, and CSV consistency. The frontend build performs TypeScript checking and produces the Vite production bundle.

Latest verification in this workspace:
- From the backend directory, `..\.venv\Scripts\python.exe -m pytest -q` — 18 passed.
- From the frontend directory, `npm run build` — TypeScript check and Vite production build succeeded. Vite printed a non-failing chunk-size advisory for the 553 kB minified JavaScript bundle.
- `GET /api/overview?date=2026-01-15&cutoff=11:00` — HTTP 200; 48 actual periods, 24 eligible forecasts, 24 matches, 24 missing forecasts, 0 missing actuals, 50% coverage, MAE 1093.625 MW.
- `GET /api/forecast-history?date=2026-01-15&cutoff=11:00` — HTTP 200; 584 January 15 revisions, including 312 published after the cutoff. Those later revisions are available to the revision chart but excluded from selected-forecast metrics.
- `GET /api/export?date=2026-01-15&cutoff=11:00` — HTTP 200; 48 period rows. CSV consistency is also covered by an automated test.
- The local Vite `/api/health` proxy returned HTTP 200, and a browser reload showed live records with no browser console errors.
- Docker image build/run was not tested because Docker is not installed in the environment. Public deployment remains unverified.

## Data limitations and missing-data handling
- The public stream endpoint is queried using its documented parameters. `WINDFOR` is publication-time filtered and `FUELHH` is settlement-date filtered; response records are independently filtered by the requested delivery timestamp.
- WINDFOR is not guaranteed to provide a forecast at every FUELHH half-hourly timestamp. Unmatched periods remain missing; the dashboard does not interpolate or duplicate hourly forecasts into half-hourly periods.
- No synthetic or demo data is used to populate live analytics. Missing eligible forecasts, missing actuals, and out-of-window records remain null or flagged, rather than being invented.
- Data gaps reduce coverage and reveal uncertainty instead of hiding it.

## Deployment
### Render backend and Vercel frontend
1. Import the repository into Render using the root [`render.yaml`](./render.yaml) blueprint. It builds the backend Dockerfile and uses `/api/health` for its health check.
2. Deploy the `frontend` directory as a Vercel Vite project (the directory contains [`vercel.json`](./frontend/vercel.json)).
3. In Vercel, set `VITE_API_BASE_URL` to the deployed Render backend origin, without a trailing slash, then redeploy.
4. In Render, update `CORS_ORIGINS` to include the actual Vercel origin (and remove the local origins if no longer needed).
5. Verify the public frontend and backend health URL, then test overview and CSV export before describing the deployment as complete.

No public deployment URL is currently configured or verified. Docker is also not installed in the development environment, so the Compose stack has not been built or run here.

### Docker Compose deployment
For local or self-hosted use, `docker compose up --build` builds the API and nginx frontend. The frontend proxies `/api` through the Compose service network, so the browser does not attempt to resolve the private Docker hostname.

## AI assistance disclosure
This project was created with AI assistance during implementation and verification.
