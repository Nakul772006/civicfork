# CivicFork — Scoring & Simulation Mathematical Model

> **Version:** 0.1 · **Date:** 2026-11-05 · **Prerequisite:** Data Contracts v0.1 (locked)
> **Constraint:** Every formula is deterministic. AI/Gemini does not participate in any calculation.

---

## Notation

| Symbol | Meaning |
|--------|---------|
| $s$ | Scenario type (one of 7) |
| $d$ | Impact dimension (one of 6) |
| $B_{s,d}$ | Base score for scenario $s$ on dimension $d$ `[configured]` |
| $M_k$ | Context modifier $k$ value `[calculated]` |
| $w_k$ | Modifier weight (scaling factor) `[configured]` |
| $W_d$ | User-assigned priority weight for dimension $d$ `[supplied]` |
| $G_c$ | Gap severity for infrastructure category $c$ `[calculated]` |
| $R_{s,c}$ | Relevance of scenario $s$ to gap category $c$ `[configured]` |

---

## 1. Overall Scoring Framework

Every scenario receives a score on every dimension using the **base-plus-modifier** model:

$$\text{score}(s, d) = \text{clamp}\!\Big(B_{s,d} + \sum_{k} w_k \cdot M_k(s, d),\ \ 0,\ 100\Big)$$

Where:
- $B_{s,d}$ is a base score from YAML config representing the inherent impact profile of scenario type $s$ on dimension $d$ in an average urban context
- $M_k$ are context-dependent modifiers derived from the urban context analysis
- $w_k$ are modifier weights from YAML config controlling sensitivity
- The result is clamped to [0, 100]

> [!IMPORTANT]
> **Exception:** The **Gap Improvement** dimension uses a different formula (§3.5) because it depends directly on the gap analysis results, not on generic base scores.

### Convention: Higher Score = Better

All scores follow the convention that **higher is better**:

| Dimension | Interpretation of high score |
|-----------|------------------------------|
| Traffic | Less traffic disruption |
| Cost | More affordable |
| Environmental | More environmentally beneficial |
| Accessibility | More accessible to residents |
| Gap Improvement | Better closes infrastructure gaps |
| Social Utility | Greater community benefit |

Dimensions where the raw impact is "bad" (e.g., cost, traffic) are **inverted** during base score assignment so the convention holds uniformly.

---

## 2. Base Score Matrix

These values live in `config/scoring.yaml`. They represent each scenario type's inherent characteristics on each dimension, **assuming an average urban context**. Context modifiers then adjust these up or down.

| Scenario | Traffic | Cost | Environ. | Access. | Gap Impr.* | Social |
|----------|---------|------|----------|---------|------------|--------|
| **Park** | 80 | 75 | 90 | 55 | — | 65 |
| **Healthcare** | 45 | 30 | 45 | 65 | — | 85 |
| **Education** | 50 | 35 | 50 | 60 | — | 80 |
| **Parking** | 35 | 70 | 25 | 70 | — | 35 |
| **Commercial** | 30 | 50 | 30 | 50 | — | 55 |
| **Community Centre** | 65 | 60 | 55 | 65 | — | 80 |
| **Public Transport** | 70 | 40 | 65 | 85 | — | 70 |

*Gap Improvement is computed via §3.5, not from base scores.

> [!NOTE]
> These values encode domain assumptions. For example, a park has a high traffic score (80) because it generates minimal traffic, while commercial development has a low traffic score (30) because it generates substantial traffic. A park has a high environmental score (90) because it adds green space, while parking has a low one (25) because it adds impervious surface. These are tunable in YAML without code changes.

---

## 3. Dimension Scoring Formulas

### 3.1 Traffic Score

**What it captures:** How much local traffic disruption the scenario would cause.

**Raw calculation:**

$$\text{trip\_load} = \frac{\text{daily\_visitors}_s \times \text{trip\_rate}_s}{\text{reference\_daily\_trips}}$$

Where:
- $\text{daily\_visitors}_s$ is the scenario's estimated daily visitors `[modelled]`
- $\text{trip\_rate}_s$ is trips per visitor (from config, e.g., hospital=2.5, park=1.2) `[configured]`
- $\text{reference\_daily\_trips}$ is a normalisation constant from config `[configured]`

**Context modifiers applied to base score:**

| Modifier | Formula | Effect |
|----------|---------|--------|
| Road capacity bonus | $+\min\!\left(\dfrac{\text{road\_density}}{\text{ref\_road\_density}},\; 1.5\right) \times 10$ | Dense road network absorbs traffic better |
| Major road proximity bonus | $+10$ if nearest major road < 500 m, $+5$ if < 1000 m, $0$ otherwise | Nearby major road diverts through-traffic |
| Existing congestion penalty | $-\dfrac{\text{commercial\_pct}}{100} \times 15$ | Already-congested commercial areas penalised |
| Visitor load penalty | $-\text{trip\_load} \times 20$ | Higher visitor traffic penalises the score |

**Final formula:**

$$\text{traffic\_score}(s) = \text{clamp}\Big(B_{s,\text{traffic}} + \text{road\_cap} + \text{major\_road} - \text{congestion} - \text{visitor\_load},\ 0,\ 100\Big)$$

---

### 3.2 Cost Score

**What it captures:** Financial burden on the municipality. Higher score = more affordable.

**Raw cost calculation:**

$$\text{capital\_cost} = \text{proposed\_area} \times \text{cost\_per\_sqm}_s$$

$$\text{annual\_operating} = \text{capital\_cost} \times \text{operating\_ratio}_s$$

$$\text{total\_5yr\_cost} = \text{capital\_cost} + 5 \times \text{annual\_operating}$$

Where:
- $\text{cost\_per\_sqm}_s$ is from config (e.g., park=₹5,000, hospital=₹45,000) `[configured]`
- $\text{operating\_ratio}_s$ is from config (e.g., park=0.05, hospital=0.25) `[configured]`

**Context modifiers:**

| Modifier | Formula | Effect |
|----------|---------|--------|
| Area scaling penalty | $-\min\!\left(\dfrac{\text{proposed\_area} - \text{ref\_area}_s}{\text{ref\_area}_s},\ 1.0\right) \times 15$ | Larger plot = higher cost = lower score |
| Revenue offset bonus (commercial only) | $+15$ if scenario generates revenue | Commercial/parking partially offset costs |

**Final formula:**

$$\text{cost\_score}(s) = \text{clamp}\Big(B_{s,\text{cost}} - \text{area\_scaling} + \text{revenue\_offset},\ 0,\ 100\Big)$$

> [!NOTE]
> The base scores already encode relative cost rankings (park is cheap → 75, hospital is expensive → 30). Modifiers adjust for plot-specific factors. The raw `total_5yr_cost` value is stored in the `Scenario` object for display but does not directly set the score — it influences the base score design.

---

### 3.3 Environmental Score

**What it captures:** Net environmental effect — green space change, surface permeability, emission characteristics.

**Raw environmental factors:**

$$\text{green\_ratio} = \frac{\text{green\_space\_delta\_sqm}}{\text{proposed\_area\_sqm}}$$

$$\text{impervious\_ratio} = \frac{\text{impervious\_surface\_delta\_sqm}}{\text{proposed\_area\_sqm}}$$

Where:
- $\text{green\_ratio}$ ranges from -1.0 (all green space removed) to +1.0 (all area becomes green) `[calculated]`
- $\text{impervious\_ratio}$ ranges from 0 (no new impervious surface) to +1.0 (fully paved) `[calculated]`

**Context modifiers:**

| Modifier | Formula | Effect |
|----------|---------|--------|
| Green space change | $+\text{green\_ratio} \times 20$ | Adding green boosts score; removing it penalises |
| Impervious penalty | $-\text{impervious\_ratio} \times 15$ | More paving penalises |
| Green deficit bonus | $+\max\!\left(1 - \dfrac{\text{green\_space\_pct}}{15},\ 0\right) \times 10$ | Area with <15% green space gets bonus for green-positive scenarios |
| Industrial adjacency penalty | $-5$ if $\text{industrial\_pct} > 20\%$ | Polluted areas reduce environmental benefit |

**Final formula:**

$$\text{env\_score}(s) = \text{clamp}\Big(B_{s,\text{env}} + \text{green\_change} - \text{impervious} + \text{deficit\_bonus} - \text{industrial},\ 0,\ 100\Big)$$

---

### 3.4 Accessibility Score

**What it captures:** How easily surrounding residents can reach and use the proposed development.

**Context modifiers:**

| Modifier | Formula | Effect |
|----------|---------|--------|
| Transit proximity bonus | $+\min\!\left(\dfrac{1000}{\text{nearest\_transit\_m} + 1},\ 1.0\right) \times 15$ | Closer transit = better access |
| Transit coverage bonus | $+\min\!\left(\dfrac{\text{transit\_stop\_count}}{5},\ 1.0\right) \times 10$ | More stops = better coverage |
| Road connectivity bonus | $+\min\!\left(\dfrac{\text{road\_density}}{\text{ref\_road\_density}},\ 1.0\right) \times 10$ | Dense road network improves access |
| Population density bonus | $+\min\!\left(\dfrac{\text{pop\_density\_est}}{10000},\ 1.0\right) \times 10$ | More people live nearby = more can access |
| Remoteness penalty | $-10$ if $\text{nearest\_transit\_m} > 2000$ AND $\text{road\_density} < 0.5 \times \text{ref}$ | Very remote plots penalised |

**Final formula:**

$$\text{access\_score}(s) = \text{clamp}\Big(B_{s,\text{access}} + \text{transit\_prox} + \text{transit\_cov} + \text{road\_conn} + \text{pop\_dens} - \text{remote},\ 0,\ 100\Big)$$

---

### 3.5 Gap Improvement Score (Special Dimension)

**What it captures:** How effectively the scenario closes identified infrastructure gaps. This dimension is **not** based on base scores — it is computed directly from the gap analysis.

**Gap-to-scenario relevance matrix** `[configured]`:

| Scenario | healthcare | education | parks | transport | parking | commercial | community |
|----------|-----------|-----------|-------|-----------|---------|------------|-----------|
| Park | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.2 |
| Healthcare | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 |
| Education | 0.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 |
| Parking | 0.0 | 0.0 | 0.0 | 0.1 | 1.0 | 0.1 | 0.0 |
| Commercial | 0.0 | 0.0 | 0.0 | 0.0 | 0.1 | 1.0 | 0.1 |
| Community Ctr | 0.1 | 0.1 | 0.2 | 0.0 | 0.0 | 0.0 | 1.0 |
| Public Transport | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.1 | 0.0 |

> Values > 0 and < 1 represent **partial relevance** (e.g., a community centre partly addresses parks needs through recreational programming).

**Formula:**

$$\text{weighted\_gap\_fill}(s) = \sum_{c \in \text{categories}} G_c \times R_{s,c}$$

$$\text{max\_possible} = \sum_{c \in \text{categories}} G_c$$

$$\text{gap\_score}(s) = \begin{cases} \dfrac{\text{weighted\_gap\_fill}(s)}{\text{max\_possible}} \times 100 & \text{if max\_possible} > 0 \\ 50 & \text{if no gaps identified} \end{cases}$$

Where:
- $G_c$ is the gap severity (0–1) for category $c$ from the gap analysis `[calculated]`
- $R_{s,c}$ is the relevance weight from the matrix above `[configured]`
- If no gaps are found, all scenarios receive a neutral score of 50

---

### 3.6 Social Utility Score

**What it captures:** Overall benefit to the community — jobs, services, health, recreation, social cohesion.

**Context modifiers:**

| Modifier | Formula | Effect |
|----------|---------|--------|
| Population reach bonus | $+\min\!\left(\dfrac{\text{pop\_density\_est}}{10000},\ 1.0\right) \times 15$ | More residents served = more utility |
| Employment bonus | $+\min\!\left(\dfrac{\text{jobs\_created}}{50},\ 1.0\right) \times 10$ | Job creation adds social value |
| Service gap bonus | $+\max(\text{matching\_gap\_severities}) \times 10$ | Addressing a critical gap boosts social value |
| Underserved area bonus | $+5$ if $\text{total\_pois} < \text{ref\_poi\_count} \times 0.5$ | Underserved areas benefit more from any development |

**Final formula:**

$$\text{social\_score}(s) = \text{clamp}\Big(B_{s,\text{social}} + \text{pop\_reach} + \text{employ} + \text{gap\_bonus} + \text{underserved},\ 0,\ 100\Big)$$

---

## 4. Scenario Impact Estimation

Before scoring, the system estimates key characteristics for each scenario. These are `[modelled]` values — deterministic approximations, not measurements.

### 4.1 Estimated Daily Visitors

$$\text{daily\_visitors}_s = \text{base\_visitors}_s \times \frac{\text{proposed\_area\_sqm}}{\text{ref\_area}_s} \times \text{pop\_density\_factor}$$

Where:
- $\text{base\_visitors}_s$ from config (e.g., park=200, hospital=500, school=400) `[configured]`
- $\text{ref\_area}_s$ is the reference area for this scenario type `[configured]`
- $\text{pop\_density\_factor} = \min\!\left(\dfrac{\text{pop\_density\_est}}{5000},\ 2.0\right)$ `[calculated]`

### 4.2 Estimated Jobs Created

$$\text{jobs}_s = \text{jobs\_per\_1000sqm}_s \times \frac{\text{proposed\_area\_sqm}}{1000}$$

Where $\text{jobs\_per\_1000sqm}_s$ from config (e.g., park=2, hospital=25, commercial=15) `[configured]`

### 4.3 Green Space & Impervious Surface Deltas

| Scenario | Green space delta | Impervious delta |
|----------|------------------|------------------|
| Park | $+0.85 \times \text{area}$ | $+0.10 \times \text{area}$ |
| Healthcare | $-0.10 \times \text{area}$ | $+0.70 \times \text{area}$ |
| Education | $+0.10 \times \text{area}$ | $+0.55 \times \text{area}$ |
| Parking | $-0.05 \times \text{area}$ | $+0.90 \times \text{area}$ |
| Commercial | $-0.05 \times \text{area}$ | $+0.80 \times \text{area}$ |
| Community Centre | $+0.15 \times \text{area}$ | $+0.50 \times \text{area}$ |
| Public Transport | $0.00 \times \text{area}$ | $+0.60 \times \text{area}$ |

Ratios from config `[configured]`. Parks are mostly green; parking is mostly paved.

### 4.4 Traffic Change Estimate

$$\text{traffic\_change\_pct}_s = \text{base\_traffic\_pct}_s \times \text{pop\_density\_factor}$$

Where $\text{base\_traffic\_pct}_s$ from config (e.g., park=+5%, hospital=+25%, commercial=+40%) `[configured]`

---

## 5. Infrastructure Gap Severity Calculation

Before scoring begins, the Gap Analyser computes severity for each infrastructure category.

### 5.1 Categories Assessed

Seven categories, matching the seven scenario types:
`healthcare`, `education`, `parks`, `transport`, `parking`, `commercial`, `community`

### 5.2 Gap Severity Formula

For each category $c$:

$$\text{coverage\_score}_c = \min\!\left(\frac{\text{facilities\_in\_radius}_c}{\text{expected\_facilities}_c},\ 1.0\right)$$

$$\text{proximity\_score}_c = \begin{cases} \max\!\left(1 - \dfrac{\text{nearest\_distance}_c}{\text{coverage\_threshold}_c},\ 0\right) & \text{if facilities} > 0 \\ 0 & \text{if no facilities found} \end{cases}$$

$$G_c = 1 - \left(0.6 \times \text{coverage\_score}_c + 0.4 \times \text{proximity\_score}_c\right)$$

Where:
- $\text{facilities\_in\_radius}_c$ = count of OSM POIs matching category $c$ within the analysis radius `[calculated]`
- $\text{expected\_facilities}_c$ = expected count from config, scaled by estimated population `[configured]`
- $\text{nearest\_distance}_c$ = distance to nearest facility of category $c$ in metres `[calculated]`
- $\text{coverage\_threshold}_c$ = acceptable service distance from config (e.g., hospital=3000 m, school=1500 m) `[configured]`
- $G_c$ ranges from 0.0 (fully served) to 1.0 (critical gap) `[calculated]`

### 5.3 Gap Classification

| $G_c$ range | gap_type | Interpretation |
|-------------|----------|----------------|
| 0.0 – 0.2 | `adequate` | Well-served; no gap |
| 0.2 – 0.5 | `distant` | Facilities exist but are far or few |
| 0.5 – 0.8 | `insufficient` | Noticeably underserved |
| 0.8 – 1.0 | `absent` | Critical gap; little or no coverage |

---

## 6. Weighted Composite & Ranking

### 6.1 Weight Normalisation

User-supplied weights $W_d$ are normalised so they sum to 1:

$$\hat{W}_d = \frac{W_d}{\sum_{d'} W_{d'}}$$

Default weights (if user has not adjusted): all equal at $\frac{1}{6} \approx 0.167$.

### 6.2 Weighted Composite Score

$$\text{composite}(s) = \sum_{d} \hat{W}_d \times \text{score}(s, d)$$

Range: 0–100 (since individual scores are 0–100 and weights sum to 1).

### 6.3 Ranking

Scenarios are sorted by $\text{composite}(s)$ in descending order. Rank 1 = highest composite score.

$$\text{rank}(s) = \text{position of } s \text{ in descending sort of composite scores}$$

Ties are broken by: Gap Improvement score (higher wins) → then alphabetical scenario ID.

### 6.4 Dimension Contributions

For explainability, each scenario's composite is decomposed:

$$\text{contribution}(s, d) = \hat{W}_d \times \text{score}(s, d)$$

This shows how much each dimension contributed to the final composite, enabling the user to see, for example, that a scenario ranked highly primarily because of its gap improvement score.

### 6.5 Delta from Top

$$\text{delta\_from\_top}(s) = \text{composite}(s_{\text{rank}=1}) - \text{composite}(s)$$

---

## 7. Feasibility Checks

Feasibility checks are **boolean rules** — each returns pass/fail with a severity level. They do **not** produce numerical scores.

### 7.1 Check Definitions

| Check | Rule | Severity | Config source |
|-------|------|----------|---------------|
| **Minimum area** | $\text{proposed\_area} \geq \text{min\_area}_s$ | blocker | `feasibility.yaml` |
| **Proximity conflict** | No facility of same type within $\text{conflict\_radius}_s$ metres | warning | `feasibility.yaml` |
| **Service saturation** | $\text{facilities\_in\_radius}_c < \text{saturation\_limit}_c$ | warning | `feasibility.yaml` |
| **Zoning compatibility** | $\text{dominant\_landuse} \notin \text{incompatible\_zones}_s$ | warning | `feasibility.yaml` |

### 7.2 Feasibility Verdict

$$\text{feasible}(s) = \text{True if no blocker-severity checks failed}$$

Warnings are informational — they surface in the UI and report but do not block a scenario from being ranked.

### 7.3 Sample Configuration Values

| Scenario | min_area (m²) | conflict_radius (m) | saturation_limit | incompatible_zones |
|----------|---------------|---------------------|-------------------|--------------------|
| Park | 500 | 300 | 5 | [industrial] |
| Healthcare | 2000 | 1500 | 3 | [industrial] |
| Education | 1500 | 1000 | 4 | [industrial] |
| Parking | 400 | 500 | 4 | [] |
| Commercial | 500 | 200 | 8 | [] |
| Community Centre | 800 | 1500 | 2 | [industrial] |
| Public Transport | 300 | 800 | 5 | [] |

---

## 8. Counterfactual Comparison

Given two scenarios $A$ and $B$ with computed scores:

### 8.1 Per-Dimension Delta

$$\delta_d = \text{score}(A, d) - \text{score}(B, d)$$

### 8.2 Direction

$$\text{direction}_d = \begin{cases} \text{"a\_better"} & \text{if } \delta_d > 2 \\ \text{"b\_better"} & \text{if } \delta_d < -2 \\ \text{"neutral"} & \text{otherwise} \end{cases}$$

The ±2 threshold prevents noise from appearing as a meaningful difference.

### 8.3 Magnitude Classification

| $|\delta_d|$ | Magnitude |
|-------|-----------|
| 0 – 5 | negligible |
| 5 – 15 | minor |
| 15 – 30 | moderate |
| 30 – 50 | significant |
| > 50 | major |

### 8.4 Net Advantage

$$\text{net\_delta} = \sum_{d} \delta_d$$

$$\text{net\_advantage} = \begin{cases} A & \text{if net\_delta} > 5 \\ B & \text{if net\_delta} < -5 \\ \text{"balanced"} & \text{otherwise} \end{cases}$$

### 8.5 Dimension Win Count

$$\text{A\_wins} = |\{d : \text{direction}_d = \text{"a\_better"}\}|$$
$$\text{B\_wins} = |\{d : \text{direction}_d = \text{"b\_better"}\}|$$

---

## 9. Worked Example

### Setup

**Selected plot:** Mysuru, near Saraswathipuram
- Lat: 12.3100, Lng: 76.6500
- Radius: 2000 m
- Plot area: 3000 m²

### Step 1 — Urban Context (from cached OSM)

| Metric | Value | Tag |
|--------|-------|-----|
| total_pois | 45 | `[calculated]` |
| road_density (m/km²) | 12,000 | `[calculated]` |
| ref_road_density | 10,000 | `[configured]` |
| nearest_major_road_m | 350 | `[calculated]` |
| commercial_pct | 18% | `[calculated]` |
| green_space_pct | 8% | `[calculated]` |
| industrial_pct | 5% | `[calculated]` |
| transit_stop_count | 3 | `[calculated]` |
| nearest_transit_m | 600 | `[calculated]` |
| population_density_est | 7,500 /km² | `[modelled]` |

### Step 2 — Gap Analysis

| Category | Facilities | Expected | Nearest (m) | Threshold (m) | Coverage | Proximity | $G_c$ | Type |
|----------|-----------|----------|-------------|---------------|----------|-----------|-------|------|
| healthcare | 2 | 3 | 800 | 3000 | 0.67 | 0.73 | 0.11 | adequate |
| education | 4 | 4 | 400 | 1500 | 1.00 | 0.73 | 0.11 | adequate |
| parks | 1 | 3 | 1800 | 1500 | 0.33 | 0.00 | 0.60 | insufficient |
| transport | 3 | 5 | 600 | 2000 | 0.60 | 0.70 | 0.12 | adequate |
| parking | 1 | 3 | 1200 | 1000 | 0.33 | 0.00 | 0.60 | insufficient |
| commercial | 5 | 4 | 200 | 1000 | 1.00 | 0.80 | 0.08 | adequate |
| community | 0 | 2 | — | 2000 | 0.00 | 0.00 | 1.00 | absent |

**Key gaps:** Community (1.00), Parks (0.60), Parking (0.60).

### Step 3 — Score Calculation for "Park" Scenario

**Scenario estimates (park on 3000 m² plot):**
- proposed_area: 3000 m²
- daily_visitors: $200 \times \frac{3000}{2000} \times \min(\frac{7500}{5000}, 2.0) = 200 \times 1.5 \times 1.5 = 450$
- jobs_created: $2 \times \frac{3000}{1000} = 6$
- green_space_delta: $+0.85 \times 3000 = +2550$ m²
- impervious_delta: $+0.10 \times 3000 = +300$ m²
- trip_rate (park): 1.2 `[configured]`
- trip_load: $\frac{450 \times 1.2}{5000} = 0.108$
- traffic_change_pct: $5\% \times 1.5 = 7.5\%$

#### 3a. Traffic Score

| Component | Formula | Value |
|-----------|---------|-------|
| Base | $B_{\text{park, traffic}}$ | 80 |
| Road capacity bonus | $\min(12000/10000, 1.5) \times 10$ | +12.0 |
| Major road bonus | nearest = 350 m < 500 m | +10.0 |
| Congestion penalty | $(18/100) \times 15$ | −2.7 |
| Visitor load penalty | $0.108 \times 20$ | −2.2 |
| **Raw** | | **97.1** |
| **Clamped** | | **97.1** |

#### 3b. Cost Score

| Component | Formula | Value |
|-----------|---------|-------|
| Base | $B_{\text{park, cost}}$ | 75 |
| Area scaling | $\min((3000-2000)/2000, 1.0) \times 15$ | −7.5 |
| Revenue offset | park generates no revenue | +0 |
| **Clamped** | | **67.5** |

#### 3c. Environmental Score

| Component | Formula | Value |
|-----------|---------|-------|
| Base | $B_{\text{park, env}}$ | 90 |
| Green change | $(2550/3000) \times 20$ | +17.0 |
| Impervious penalty | $(300/3000) \times 15$ | −1.5 |
| Green deficit bonus | $\max(1 - 8/15, 0) \times 10$ | +4.7 |
| Industrial penalty | 5% < 20% | −0 |
| **Raw** | | **110.2** |
| **Clamped** | | **100.0** |

#### 3d. Accessibility Score

| Component | Formula | Value |
|-----------|---------|-------|
| Base | $B_{\text{park, access}}$ | 55 |
| Transit proximity | $\min(1000/601, 1.0) \times 15$ | +15.0 |
| Transit coverage | $\min(3/5, 1.0) \times 10$ | +6.0 |
| Road connectivity | $\min(12000/10000, 1.0) \times 10$ | +10.0 |
| Population density | $\min(7500/10000, 1.0) \times 10$ | +7.5 |
| Remoteness penalty | transit < 2000 m | −0 |
| **Clamped** | | **93.5** |

#### 3e. Gap Improvement Score

| Gap | $G_c$ | $R_{\text{park}, c}$ | Contribution |
|-----|-------|---------------------|-------------|
| healthcare | 0.11 | 0.0 | 0 |
| education | 0.11 | 0.0 | 0 |
| parks | 0.60 | 1.0 | 0.60 |
| transport | 0.12 | 0.0 | 0 |
| parking | 0.60 | 0.0 | 0 |
| commercial | 0.08 | 0.0 | 0 |
| community | 1.00 | 0.2 | 0.20 |
| **Total** | | | **0.80** |

$$\text{max\_possible} = 0.11 + 0.11 + 0.60 + 0.12 + 0.60 + 0.08 + 1.00 = 2.62$$

$$\text{gap\_score} = \frac{0.80}{2.62} \times 100 = 30.5$$

#### 3f. Social Utility Score

| Component | Formula | Value |
|-----------|---------|-------|
| Base | $B_{\text{park, social}}$ | 65 |
| Population reach | $\min(7500/10000, 1.0) \times 15$ | +11.3 |
| Employment | $\min(6/50, 1.0) \times 10$ | +1.2 |
| Gap bonus | $\max(0.60) \times 10$ (parks gap) | +6.0 |
| Underserved | 45 POIs, $45 < \text{ref} \times 0.5$? Assume ref=100 → yes | +5.0 |
| **Clamped** | | **88.5** |

### Step 4 — Park Scenario Score Summary

| Dimension | Score |
|-----------|-------|
| Traffic | 97.1 |
| Cost | 67.5 |
| Environmental | 100.0 |
| Accessibility | 93.5 |
| Gap Improvement | 30.5 |
| Social Utility | 88.5 |

**Unweighted composite:** $(97.1 + 67.5 + 100.0 + 93.5 + 30.5 + 88.5) / 6 = 79.5$

### Step 5 — Weighted Composite (with example weights)

User sets: Traffic=0.2, Cost=0.3, Env=0.1, Access=0.15, Gap=0.15, Social=0.1

Normalised (sum = 1.0): same values (already sum to 1.0).

$$\text{composite}_{\text{park}} = 0.2(97.1) + 0.3(67.5) + 0.1(100.0) + 0.15(93.5) + 0.15(30.5) + 0.1(88.5)$$

$$= 19.42 + 20.25 + 10.00 + 14.03 + 4.58 + 8.85 = 77.1$$

### Step 6 — Counterfactual: Park vs Commercial

Suppose commercial scores on the same plot are:

| Dimension | Park | Commercial | $\delta$ | Direction | Magnitude |
|-----------|------|------------|----------|-----------|-----------|
| Traffic | 97.1 | 42.0 | +55.1 | park better | major |
| Cost | 67.5 | 55.0 | +12.5 | park better | minor |
| Environmental | 100.0 | 38.0 | +62.0 | park better | major |
| Accessibility | 93.5 | 68.0 | +25.5 | park better | moderate |
| Gap Improvement | 30.5 | 12.0 | +18.5 | park better | moderate |
| Social Utility | 88.5 | 72.0 | +16.5 | park better | moderate |

**Net delta:** +190.1 → **Park is strongly better overall**
**Park wins:** 6 of 6 dimensions
**Headline:** "Park wins on all 6 dimensions vs Commercial Development"

> [!TIP]
> This extreme result reflects the specific context: the area has a parks gap (0.60), a community gap (1.00), low green space (8%), and good road connectivity. In a different context (e.g., high unemployment, commercial gap), the result would differ. The model adapts to context — it does not universally prefer any scenario type.

---

## 10. Configuration Reference Summary

All magic numbers live in YAML config files. No hardcoded constants in scoring code.

| Config file | What it controls | Example keys |
|-------------|-----------------|--------------|
| `scoring.yaml` | Base score matrix, modifier weights, reference values, normalisation constants | `base_scores.park.traffic: 80`, `modifiers.road_capacity.weight: 10`, `reference.road_density: 10000` |
| `scenarios.yaml` | Scenario type definitions, cost factors, visitor estimates, green/impervious ratios, trip rates | `park.cost_per_sqm: 5000`, `park.base_visitors: 200`, `park.green_ratio: 0.85` |
| `feasibility.yaml` | Feasibility check thresholds per scenario type | `park.min_area: 500`, `healthcare.conflict_radius: 1500` |

---

## Model Limitations (Disclosed)

| Limitation | Mitigation |
|------------|-----------|
| Population density is estimated from building/residential ratios, not census data | Clearly labelled `[modelled]` in all outputs |
| Cost estimates use per-sqm factors, not real construction quotes | Presented as relative comparisons, not budgets |
| Traffic impact uses simplified trip generation, not traffic microsimulation | Disclosed in methodology note; sufficient for comparative ranking |
| Gap analysis uses Euclidean distance, not walking/driving distance | Acceptable for comparative purposes at 2 km scale |
| All scores are relative to the configured reference values | Changing config changes all scores — document the reference baseline |
