# CivicFork 🏙️🍴

> **Urban Policy Impact Simulation and Counterfactual Decision-Support Platform**  
> *Smart City Decision Support for Municipal Urban Planners*  
> Demo City: **Mysuru, Karnataka, India**

---

## Overview

**CivicFork** is a municipality-only decision-support platform designed to help urban planners evaluate development choices on land parcels before committing public capital. 

Rather than relying on opaque AI predictions or uncalibrated intuition, CivicFork combines:
1. **Deterministic, explainable Python simulation** across 6 key urban impact dimensions.
2. **Context-aware infrastructure gap analysis** using OpenStreetMap geospatial data.
3. **Counterfactual decision comparison** (*e.g., "What if we build a park instead of commercial retail?"*).
4. **Targeted AI narrative synthesis (Gemini)** strictly for explaining precomputed results and generating formal decision-support reports (ReportLab PDF).

---

## 7 Standard Development Scenarios

CivicFork evaluates seven fixed scenarios for any selected land parcel:
1. **Parks & Recreational Space**
2. **Healthcare Facility**
3. **Educational Facility**
4. **Public Parking**
5. **Commercial Development**
6. **Community Centre**
7. **Public Transport Facility**

## 6 Impact Dimensions

Every scenario is deterministically scored (0–100, where higher is better):
* **Traffic:** Change in local traffic volume and street congestion.
* **Cost:** Capital and 5-year operating expenditure burden (inverted so higher = more affordable).
* **Environmental Impact:** Net green space delta, impervious surface delta, and emissions.
* **Accessibility:** Proximity to public transit, road network connectivity, and population density reach.
* **Infrastructure-Gap Improvement:** Direct closure of identified local amenity gaps.
* **Public & Social Utility:** Public community benefit, employment generation, and social cohesion.

---

## Key Architecture Principles

* **Monolithic Two-Tier Architecture:** Single FastAPI backend + React Vite SPA frontend.
* **Strict AI Boundary:** Python and NumPy/Pandas own **all** mathematical simulations, scoring, rankings, and counterfactual deltas. Gemini API is restricted to narrative explanation and report prose.
* **Zero Database:** Static cached OpenStreetMap GeoJSON + YAML configuration + in-memory session state. No SQL/NoSQL database overhead.
* **Offline-Ready:** Demo area (Mysuru city core) runs completely offline without external Overpass or GIS dependencies.
* **Cross-Platform:** Works identically on Ubuntu Linux and Windows.

---

## Repository Structure

```
civicfork/
├── backend/               # FastAPI backend, Python simulation, OSM service
│   ├── app/               # Application code (api, models, services)
│   ├── config/            # YAML configuration (scoring, scenarios, feasibility)
│   ├── data/mysuru/       # Cached OpenStreetMap GeoJSON data
│   └── tests/             # Pytest test suite
├── frontend/              # React + Vite + Tailwind + Leaflet frontend
│   ├── public/            # Static assets
│   └── src/               # React components, hooks, and API client
└── docs/                  # System specifications and documentation
```

---

## Documentation

Full architectural specifications and contracts are located in `docs/`:
- [`requirements.md`](docs/requirements.md) — Problem statement, user workflows, and MVP scope.
- [`architecture.md`](docs/architecture.md) — System topology, data flow, and locked decisions.
- [`folder-structure.md`](docs/folder-structure.md) — Exact repository organization and responsibilities.
- [`data-contracts.md`](docs/data-contracts.md) — Pydantic schemas and typed data contracts.
- [`scoring-model.md`](docs/scoring-model.md) — Deterministic mathematical models and worked calculations.
- [`api-contracts.md`](docs/api-contracts.md) — The 7 REST API endpoints and response envelopes.
- [`implementation-plan.md`](docs/implementation-plan.md) — 24-hour hackathon execution plan for 3 developers.

---

## License

This project is licensed under the [MIT License](LICENSE).
