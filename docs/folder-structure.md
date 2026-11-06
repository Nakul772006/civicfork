# CivicFork — Project Folder Structure

> **Version:** 0.1 · **Date:** 2026-11-05 · **Prerequisite:** Architecture v0.2 (locked)

---

## Repository Root

```
civicfork/
│
├── backend/                    # Python · FastAPI · all server-side logic
├── frontend/                   # React · Vite · Tailwind · all client-side code
├── docs/                       # Project documentation
│
├── .gitignore
├── .gitattributes
├── README.md
└── LICENSE
```

> [!IMPORTANT]
> Two top-level directories: `backend/` and `frontend/`. Each is self-contained with its own dependency manifest. A developer can `cd` into either and start working independently.

---

## Backend

```
backend/
│
├── app/                        # Python package — all application code
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory, lifespan, CORS, middleware
│   │
│   ├── api/                    # REST API layer
│   │   ├── __init__.py
│   │   ├── routes.py           # All 7 endpoints + health check
│   │   └── dependencies.py     # FastAPI dependencies (session lookup, config injection)
│   │
│   ├── models/                 # Pydantic models + domain types
│   │   ├── __init__.py
│   │   ├── requests.py         # Request body schemas (AnalyzeRequest, RankRequest, etc.)
│   │   ├── responses.py        # Response body schemas (AnalysisResponse, RankResponse, etc.)
│   │   └── domain.py           # Internal domain dataclasses (PlotContext, Gap, Scenario, ScoreMatrix, etc.)
│   │
│   ├── services/               # Core business logic — one file per module
│   │   ├── __init__.py
│   │   ├── osm_service.py      # OSM abstraction (base class + CachedOSMService)
│   │   ├── context_analyzer.py # Urban context analysis from OSM data
│   │   ├── gap_analyzer.py     # Infrastructure gap identification
│   │   ├── scenario_generator.py   # Seven fixed scenario definitions
│   │   ├── impact_simulator.py     # Deterministic scoring engine (6 dimensions)
│   │   ├── ranking_engine.py       # Weighted composite scoring + ranking
│   │   ├── feasibility_checker.py  # Constraint validation per scenario
│   │   ├── counterfactual_engine.py # Pairwise scenario delta computation
│   │   ├── narrative_service.py    # Gemini API integration (prompt construction + calling)
│   │   └── report_generator.py     # ReportLab PDF assembly
│   │
│   ├── session.py              # In-memory session store (dict[str, SessionData])
│   ├── exceptions.py           # Custom exception hierarchy (CivicForkError, etc.)
│   └── settings.py             # App settings from env vars (pydantic-settings)
│
├── data/                       # Static data files — loaded at startup, read-only
│   └── mysuru/
│       ├── pois.geojson        # Points of interest (hospitals, schools, parks, markets, etc.)
│       ├── roads.geojson       # Road network
│       ├── landuse.geojson     # Land use polygons (residential, commercial, industrial, etc.)
│       ├── transport.geojson   # Bus stops, transit routes, railway stations
│       └── buildings.geojson   # Building footprints (optional — include if useful)
│
├── config/                     # YAML configuration — scoring rules, scenario templates
│   ├── scoring.yaml            # Scoring formulas, thresholds, scaling factors per dimension
│   ├── scenarios.yaml          # Seven scenario type definitions (name, attributes, defaults)
│   └── feasibility.yaml       # Feasibility constraints (min area, proximity rules, saturation)
│
├── tests/                      # Backend tests
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures (sample plot, mock context, test config)
│   ├── test_context_analyzer.py
│   ├── test_gap_analyzer.py
│   ├── test_impact_simulator.py
│   ├── test_ranking_engine.py
│   ├── test_counterfactual.py
│   ├── test_feasibility.py
│   └── test_api.py             # Integration tests for REST endpoints
│
├── requirements.txt            # Pinned Python dependencies
└── .env.example                # Template for environment variables
```

---

## Frontend

```
frontend/
│
├── public/
│   └── favicon.ico
│
├── src/
│   ├── main.jsx                # React entry point
│   ├── App.jsx                 # Root component, layout, routing (if any)
│   ├── index.css               # Tailwind directives + global styles
│   │
│   ├── api/                    # Backend API client
│   │   └── client.js           # Axios/fetch wrapper — one function per endpoint
│   │
│   ├── components/             # React components — grouped by workflow area
│   │   ├── map/
│   │   │   ├── MapView.jsx         # React-Leaflet map with click-to-select
│   │   │   └── PlotMarker.jsx      # Selected plot marker/polygon overlay
│   │   │
│   │   ├── analysis/
│   │   │   ├── ContextPanel.jsx    # Urban context summary display
│   │   │   └── GapPanel.jsx        # Infrastructure gap list/table
│   │   │
│   │   ├── scenarios/
│   │   │   ├── ScenarioCards.jsx   # Grid of seven scenario cards with scores
│   │   │   ├── ScoreTable.jsx      # 7 × 6 score matrix table
│   │   │   └── ScoreChart.jsx      # Recharts radar/bar chart for scores
│   │   │
│   │   ├── comparison/
│   │   │   ├── WeightSliders.jsx   # Municipal priority weight sliders
│   │   │   ├── RankingList.jsx     # Ranked scenario list
│   │   │   └── CounterfactualView.jsx  # Side-by-side delta comparison
│   │   │
│   │   ├── report/
│   │   │   └── ExplanationPanel.jsx    # AI-generated narrative display
│   │   │
│   │   └── common/
│   │       ├── Layout.jsx          # Page layout shell (header, sidebar, main)
│   │       ├── LoadingSpinner.jsx  # Shared loading indicator
│   │       └── ErrorBanner.jsx     # Shared error display
│   │
│   ├── hooks/                  # Custom React hooks
│   │   └── useSession.js       # Session state management (session_id, analysis data)
│   │
│   └── utils/                  # Frontend utilities
│       └── formatters.js       # Number formatting, score display helpers
│
├── index.html                  # Vite HTML entry
├── vite.config.js              # Vite config (proxy /api → backend)
├── tailwind.config.js          # Tailwind config
├── postcss.config.js           # PostCSS config (Tailwind plugin)
├── package.json                # npm dependencies + scripts
└── .env.example                # Template for frontend env vars (API URL, etc.)
```

---

## Documentation

```
docs/
├── requirements.md             # Requirements spec v0.2 (locked)
├── architecture.md             # Technical architecture v0.2 (locked)
├── folder-structure.md         # This document
├── api-reference.md            # Endpoint request/response examples
└── scoring-methodology.md      # How each dimension is scored (formulas, rationale)
```

---

## File Responsibilities

### Backend — Key Files

| File | Responsibility |
|------|---------------|
| `app/main.py` | Create FastAPI app, register routes, configure CORS, load data + config in lifespan event |
| `app/api/routes.py` | Define all REST endpoints; validate input, call services, wrap responses |
| `app/api/dependencies.py` | FastAPI `Depends()` callables: get session store, get OSM service, get config |
| `app/models/requests.py` | Pydantic models for every request body (`AnalyzeRequest`, `RankRequest`, `CounterfactualRequest`, etc.) |
| `app/models/responses.py` | Pydantic models for every response body (`AnalysisResponse`, `ScoreMatrix`, `CounterfactualResult`, etc.) |
| `app/models/domain.py` | Internal dataclasses not exposed via API: `PlotContext`, `Gap`, `Scenario`, `DimensionScore`, `SessionData` |
| `app/services/osm_service.py` | Abstract `OSMServiceBase` + `CachedOSMService` that loads GeoJSON and queries by radius |
| `app/services/context_analyzer.py` | Takes plot + radius, queries OSM service, returns structured `PlotContext` |
| `app/services/gap_analyzer.py` | Takes `PlotContext`, checks infrastructure coverage thresholds, returns `list[Gap]` |
| `app/services/scenario_generator.py` | Reads scenario templates from YAML config, produces 7 `Scenario` objects for the plot |
| `app/services/impact_simulator.py` | Core scoring engine: takes plot + context + gaps + scenarios + rules, returns 7×6 score matrix with explanations |
| `app/services/ranking_engine.py` | Applies weight vector to score matrix, returns weighted composites + sorted ranking |
| `app/services/feasibility_checker.py` | Validates scenarios against constraints from YAML, returns feasibility verdicts |
| `app/services/counterfactual_engine.py` | Computes per-dimension deltas between two scenarios, returns structured comparison |
| `app/services/narrative_service.py` | Builds prompts from computed data, calls Gemini API, returns narrative text; handles fallback |
| `app/services/report_generator.py` | Assembles PDF using ReportLab from all computed data + narrative text |
| `app/session.py` | `SessionStore` class: `create()`, `get()`, `update()` — backed by a plain Python dict |
| `app/exceptions.py` | `CivicForkError` hierarchy + FastAPI exception handlers |
| `app/settings.py` | `Settings` class (pydantic-settings): reads `GEMINI_API_KEY`, data paths, config paths from `.env` |

### Backend — Config Files (YAML)

| File | Contents |
|------|----------|
| `config/scoring.yaml` | Per-dimension scoring rules: formula type, input weights, thresholds, normalisation ranges, scaling factors |
| `config/scenarios.yaml` | Seven scenario definitions: name, description, default attributes (typical area, typical cost range, category tags) |
| `config/feasibility.yaml` | Constraints per scenario type: minimum plot area, proximity conflict rules, saturation thresholds |

### Backend — Data Files (GeoJSON)

| File | Contents |
|------|----------|
| `data/mysuru/pois.geojson` | OSM points of interest with `amenity`, `name`, `coordinates` — hospitals, schools, parks, markets, government offices, etc. |
| `data/mysuru/roads.geojson` | Road network with `highway` classification — for traffic scoring context |
| `data/mysuru/landuse.geojson` | Land use polygons with `landuse` tag — residential, commercial, industrial, etc. |
| `data/mysuru/transport.geojson` | Bus stops, auto stands, railway stations with routes if available |
| `data/mysuru/buildings.geojson` | Building footprints — optional, include only if useful for density scoring |

### Frontend — Key Files

| File | Responsibility |
|------|---------------|
| `src/api/client.js` | One async function per backend endpoint; handles errors, returns parsed JSON |
| `src/hooks/useSession.js` | React hook managing `session_id` + all analysis state; provides data + actions to components |
| `src/components/map/MapView.jsx` | Leaflet map with OSM tiles, click handler emitting coordinates, context radius circle |
| `src/components/analysis/ContextPanel.jsx` | Displays urban context: land use breakdown, POI counts, density indicators |
| `src/components/analysis/GapPanel.jsx` | Table of identified infrastructure gaps with distances |
| `src/components/scenarios/ScenarioCards.jsx` | Grid of 7 cards, each showing scenario name, summary, feasibility status, scores |
| `src/components/scenarios/ScoreTable.jsx` | 7×6 matrix table with colour-coded cells |
| `src/components/scenarios/ScoreChart.jsx` | Recharts radar or grouped bar chart comparing scenario scores |
| `src/components/comparison/WeightSliders.jsx` | Six sliders for municipal priority weights; triggers re-ranking on change |
| `src/components/comparison/RankingList.jsx` | Sorted list of scenarios by weighted composite score |
| `src/components/comparison/CounterfactualView.jsx` | Pick two scenarios, display per-dimension deltas with direction arrows |
| `src/components/report/ExplanationPanel.jsx` | Renders AI-generated narrative text; shows fallback if unavailable |
| `src/components/common/Layout.jsx` | Page shell: header with logo, sidebar for controls, main area for map + panels |

---

## Team Parallelism

The structure is designed for three developers to work simultaneously with minimal merge conflicts:

| Person | Primary directories | Touches |
|--------|-------------------|---------|
| **Dev 1 — Frontend** | `frontend/src/` | `frontend/*` |
| **Dev 2 — Backend core** | `backend/app/api/`, `backend/app/services/` (simulation, ranking, counterfactual, feasibility), `backend/app/models/` | `backend/config/`, `backend/tests/` |
| **Dev 3 — Data + integration** | `backend/data/`, `backend/app/services/` (osm_service, context_analyzer, gap_analyzer, narrative_service, report_generator) | `backend/config/`, `backend/tests/` |

> [!TIP]
> The only shared contention points are `routes.py` (all three may add/modify endpoints) and `models/` (shared schemas). Coordinate on these via clear Pydantic model contracts defined early.

---

## .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/
env/

# Node
node_modules/
frontend/dist/

# Environment
.env
backend/.env
frontend/.env

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# ReportLab output (generated PDFs)
backend/output/
```

### What IS committed

| Item | Why |
|------|-----|
| `backend/data/mysuru/*.geojson` | Demo data — must ship with the repo for offline demo |
| `backend/config/*.yaml` | Scoring rules and scenario definitions — core to the system |
| `.env.example` files | Templates so team members know which vars to set |
| `docs/*` | All documentation |
| `requirements.txt` / `package.json` | Dependency manifests |

### What is NOT committed

| Item | Why |
|------|-----|
| `.env` | Contains `GEMINI_API_KEY` and other secrets |
| `node_modules/`, `.venv/` | Installed dependencies — reconstructed from manifests |
| `__pycache__/` | Python bytecode |
| `frontend/dist/` | Build output |
| `backend/output/` | Generated PDF reports |

---

## .gitattributes

```gitattributes
# Normalise line endings for cross-platform (Ubuntu + Windows)
* text=auto

# Force LF for source code
*.py text eol=lf
*.js text eol=lf
*.jsx text eol=lf
*.json text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.md text eol=lf
*.css text eol=lf
*.html text eol=lf

# Binary files — do not modify
*.geojson binary
*.ico binary
*.png binary
*.pdf binary
```

> [!NOTE]
> GeoJSON files are marked as binary to prevent Git from mangling large coordinate arrays with line-ending conversions. They are still human-readable JSON — just not subject to `text=auto` normalisation.

---

## Environment Variables

### `backend/.env.example`

```env
# Gemini API
GEMINI_API_KEY=your-gemini-api-key-here

# Data paths (defaults work if running from backend/)
OSM_DATA_DIR=data/mysuru
CONFIG_DIR=config

# Server
HOST=0.0.0.0
PORT=8000
```

### `frontend/.env.example`

```env
# Backend API URL (Vite proxies /api in dev; this is for production builds)
VITE_API_URL=http://localhost:8000
```

---

## Conventions

| Convention | Rule |
|------------|------|
| **Python imports** | Always use absolute imports from `app`: `from app.services.osm_service import CachedOSMService` |
| **File paths** | Always use `pathlib.Path` — never string concatenation with `/` or `\\` |
| **One service per file** | Each backend service is a single `.py` file — no sub-packages under `services/` |
| **One component per file** | Each React component is a single `.jsx` file |
| **YAML for config, not code** | Scoring rules live in YAML; Python reads them. No hardcoded magic numbers. |
| **Tests mirror services** | `test_impact_simulator.py` tests `impact_simulator.py` — 1:1 mapping |
