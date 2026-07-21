# Simulation Agent & Models — Statistical Approximations

This document outlines the scope, abstractions, and design boundaries of the Simulation Agent and its underlying models.

---

## 1. Scope Boundary: Statistical vs. Physics Engines

In accordance with Section 3.10 of the Frozen Architecture:
- **What they are:** Coarse statistical and empirical models representing approximate projections of environmental hazards.
- **What they are not:** Full physics engines, structural solvers, fluid dynamics engines, or heavy numerical systems. 

This separation prevents scope-creep and ensures execution times remain fast, cost-effective, and resource-friendly. Any future improvements or replacements to the models must fit behind the same `SimulationModel` protocol.

---

## 2. Shared Abstraction: `SimulationModel` Protocol

The simulation engine is architected around a decoupled protocol pattern. Every simulation model must implement:

```python
class SimulationModel(Protocol):
    @property
    def model_name(self) -> str: ...
    def run(self, parameters: dict) -> SimulationResult: ...
```

By isolating specialized model logic into independent, registry-wired classes, we can support registering additional models without modifying the `SimulationAgent` core logic.

---

## 3. Registered Simulation Models

### 3.1 Plume Dispersion Model (`PlumeDispersionModel`)
- **Category:** Statistical approximation of gas plume dispersion distance.
- **Inputs:** `wind_speed` (m/s or km/h).
- **Sanity Bounds:** `0.5 <= wind_speed <= 50.0`.
- **Outputs:** Proposes approximate downwind distance.

### 3.2 Flood Extent Model (`FloodExtentModel`)
- **Category:** Empirical rainfall-to-flooded-area baseline multiplier.
- **Inputs:** `rainfall` (mm).
- **Sanity Bounds:** `5.0 <= rainfall <= 500.0`.
- **Outputs:** Proposes total flooded square kilometers.

### 3.3 Wildfire Spread Model (`WildfireSpreadModel`)
- **Category:** Combined temperature and wind speed propagation rate projection.
- **Inputs:** `wind_speed` (km/h), `temperature` (°C).
- **Sanity Bounds:** `0.0 <= wind_speed <= 80.0`, `10.0 <= temperature <= 55.0`.
- **Outputs:** Propagating speed in meters per minute.

### 3.4 ENSO Forecast Model (`ENSOForecastModel`)
- **Category:** Niño 3.4 Sea Surface Temperature anomaly classification.
- **Inputs:** `sst_anomaly` (°C).
- **Sanity Bounds:** `-4.0 <= sst_anomaly <= 4.0`.
- **Outputs:** Classifies conditions into El Niño, La Niña, or Neutral.

---

## 4. Robustness and Failure Modes

- **Missing Parameters:** If a simulation is triggered but a required parameter cannot be parsed from prior agent evidence or query text, it raises an explicit error and halts.
- **Sanity Bound Violations:** If a parameter is provided but falls outside the scientifically plausible sanity range listed above, the checker flags the results as unreliable. The agent captures this and reports `errors=["simulation inconclusive"]`, refusing to pass garbage or fabricated projections into the Synthesis stage.
