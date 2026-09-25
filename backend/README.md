
# H-Copilot — Data Engineering and Predictive Modeling for a Hospital Decision Support Platform

Research codebase for the M.Sc. Data Science thesis:
**"Data Engineering and Predictive Modeling for a Hospital Decision Support Platform (H-Copilot)"**
Jinan Bark — Lebanese University, Faculty of Sciences — 2026

H-Copilot is a **two-layer AI-powered ED bed and staff assignment platform** combining a proactive prediction layer with a reactive optimization layer. The prediction layer forecasts patient arrivals in upcoming **4-hour time slots** using a blended Random Forest / Neural Network ensemble; the optimization layer formulates bed, nurse, and doctor assignment as a **Binary Integer Program** solved with PuLP/CBC, re-optimizing automatically on every patient discharge.

---

## Key Results

| Metric | H-Copilot | Baseline |
|---|---|---|
| Prediction MAE | **3.09** | outperforms SARIMAX & NNAR-style baselines |
| Prediction WAPE | **20.70%** | modest, statistically-supported gain over naive (p = 0.0068) |
| Priority compliance (high demand) | **100%** | 6.7% (First-Come-First-Served) |
| Critical-patient starvation cases | **0** | 17 (First-Come-First-Served) |
| Low-acuity starvation (12h aging threshold) | **0** | — (critical-patient protection unaffected) |

The final prediction model is a blended Random Forest / Neural Network ensemble, validated through walk-forward (rolling-origin) evaluation with periodic retraining, multiple naive baselines, permutation testing, and cross-validation. The optimization layer's threshold-gated aging mechanism lets waiting time influence assignment priority indirectly, mitigating the starvation risk that strict acuity-based prioritization would otherwise introduce — without weakening critical-patient protection. A tested workload-balancing extension also reduces maximum individual staff caseload, within staffing constraints.

Both layers are integrated into an implemented, full-stack platform (**React**, **FastAPI**, **PostgreSQL**), with a manual retraining endpoint allowing the prediction model to be refreshed on demand as new real platform data accumulates.

---

## Where to Look First

| I want to... | Go to |
|---|---|
| **Run the flow prediction training** | `notebooks/` |
| **Understand the forecasting model** | Forecasting code / notebook |
| **Understand the resource optimizer** | `backend/optimizer/` |
| **Understand the workload-balancing extension** | `workload_balancing.py` |
| **Understand database integration** | `backend/database.py` |
| **Run the platform** | `backend/` and `frontend/` |

---

## Project Layout

```text
H-Copilot/
│
├── backend/                    FastAPI services and AI integration
│   ├── venv/                   Python virtual environment (not tracked)
│   ├── database.py             PostgreSQL / SQLAlchemy connection
│   ├── main.py                 FastAPI entry point
│   ├── forecasting/            Patient flow prediction
│   ├── optimizer/              Resource optimization (PuLP/CBC)
│   └── ...
│
├── frontend/                   React platform interface
│   └── ...
│
├── notebooks/                  Model development and training
│   └── ...
│
├── workload_balancing.py       Standalone workload-balancing component
├── .gitignore
├── .env.example
└── README.md
```

> **Note:** `backend/venv/`, `.env`, credentials, private clinical data, and other sensitive information are **not** included in the repository.

---

## Getting the Dataset

The patient-flow forecasting notebook uses:

```
ED_triage.csv
```

The prediction layer is trained on the Iranian ED dataset (Mashhad University of Medical Sciences). The deployed platform is designed to receive real hospital data through the database rather than sampled CSVs.

The preprocessing pipeline includes:

- Duplicate visit/re-triage removal
- Date construction
- 4-hour time-slot construction
- Patient-count aggregation
- Calendar feature engineering
- Historical flow features
- Historical acuity features
- Complaint-category features

---

## Patient Flow Prediction

The forecasting layer predicts the expected number of patients arriving in upcoming 4-hour time slots.

### Features

The final forecasting model uses **15 deployment-compatible features**:

| Feature Group | Features |
|---|---|
| Calendar | `hour_slot`, `day_of_week`, `month`, `week_of_year`, `is_weekend` |
| Historical Flow | `lag_2wk_avg`, `lag_4wk_avg`, `lag_8wk_avg`, `lag_12wk_avg` |
| Acuity | `lag_8wk_severity`, `lag_8wk_high_acuity` |
| Same-Day Demand | `daily_cumulative_avg` |
| Patient Characteristics | `lag_8wk_avg_PainGrade` |
| Complaint Categories | `lag_8wk_Medical/Internal`, `lag_8wk_Trauma/Injury` |

Historical features are constructed using previous observations to avoid using future information during forecasting.

### Models

| Branch | Configuration |
|---|---|
| Random Forest Regressor | 200 trees, max depth 6, absolute-error criterion |
| Neural Network (MLP) Regressor | 50 hidden neurons, standardized inputs, early stopping |

```
Final Prediction = (Random Forest Prediction + Neural Network Prediction) / 2
```

The neural network branch uses `StandardScaler`, while the Random Forest branch operates on the original feature values.

### Evaluation

| Setting | Value |
|---|---|
| Initial Training Fraction | 80% |
| Evaluation Strategy | Chronological walk-forward (rolling-origin) |
| Step Size | 126 observations |
| Scaling | Training data only |
| Prediction | RF + NN blended average |

Metrics: **MAE**, **RMSE**, **WAPE/MAPE**, **Peak MAE**.

Peak MAE evaluates the model on the busiest 10% of evaluation slots, based on actual patient counts. MAPE excludes zero actual patient counts to avoid division by zero. Validation also includes multiple naive baselines, permutation testing, and cross-validation across independent train/test splits.

After walk-forward evaluation, the final deployable models are retrained using all available historical observations. A manual retraining endpoint allows the model to be refreshed on demand as real platform data accumulates.

---

## Resource Optimization

The optimization layer formulates bed, nurse, and doctor assignment as a **Binary Integer Program**, solved with **PuLP/CBC**, minimizing a priority-weighted count of unassigned patients subject to ward, shift, and role-matching constraints. It re-optimizes automatically on every patient discharge.

Current optimization scope:

- Nurses
- Doctors
- Beds

`SHIFT` and `GROUP` are passed dynamically by the platform rather than being permanently hardcoded inside the optimization engine.

### Aging Mechanism

Waiting time influences assignment priority indirectly through a **threshold-gated aging mechanism** (12-hour threshold tested), mitigating the starvation risk that strict acuity-based prioritization would otherwise introduce for low-acuity patients — without weakening critical-patient protection.

### Workload Balancing

A separate workload-balancing extension (`workload_balancing.py`) demonstrates a measurable, though staffing-constrained, reduction in maximum individual caseload across staff members.

---

## Database Integration

H-Copilot uses PostgreSQL with SQLAlchemy. The database supports operational information related to:

- Patients
- Nurses
- Doctors
- Beds
- Shifts
- Groups
- Predictions
- Assignments

During deployment, the platform retrieves current hospital information from the database rather than relying on sampled CSV files.

### Architecture

```text
Hospital Database
       ↓
Current Patient / Resource Data
       ↓
Patient Flow Prediction
       ↓
Predicted Demand
       ↓
Resource Optimizer (PuLP/CBC)
       ↓
Generated Assignments
       ↓
Assignments Table
       ↓
Frontend
```

---

## Milestones

| # | Milestone | Exit Criterion |
|---|---|---|
| M1 | Patient Flow Preprocessing | Clean 4-hour slot-level patient counts |
| M2 | Forecasting Features | 15 deployment-compatible features |
| M3 | Walk-Forward Evaluation | Chronological evaluation completed |
| M4 | Forecasting Model | RF + NN blended model exported |
| M5 | Resource Optimization | Nurse, doctor, and bed assignments generated |
| M6 | Aging & Workload Balancing | Starvation-risk mitigation and caseload balancing validated |
| M7 | Platform Integration | Prediction and optimization connected to database |

---

## Running the Platform

### Virtual Environment

```bash
backend\venv\Scripts\activate
```

### Full Startup Flow

```bash
# 1. Start PostgreSQL
#    (must be running before the backend connects)

# 2. Activate the virtual environment
backend\venv\Scripts\activate

# 3. Start the backend (FastAPI, default port 8000)
cd backend
uvicorn main:app --reload

# 4. Start the frontend (React)
cd frontend
npm run dev

# 5. Run workload balancing when needed
python workload_balancing.py
```

> **Note:** The backend reads `DATABASE_URL` from `.env` via SQLAlchemy. The exact frontend port is not fixed and depends on your local Vite/CRA configuration. A confirmed `requirements.txt`, database migration step, and seed-data step are not yet established for this repository.

### Running the Forecasting Notebook

The forecasting notebook can be executed in Google Colab.

```bash
# upload the dataset
ED_triage.csv
```

The notebook performs:

```text
Data Cleaning
      ↓
4-Hour Slot Construction
      ↓
Feature Engineering
      ↓
Walk-Forward Evaluation
      ↓
Final Model Training
      ↓
Model Export
```

Generated artifacts:

- `flow_prediction_model.pkl` — Random Forest model, Neural Network model, StandardScaler
- `historical_flow_raw.csv` — historical flow information used by the prediction component

---

## Deployment Workflow

1. Retrieve current hospital data from the database
2. Construct forecasting features
3. Generate patient-flow predictions
4. Pass demand information to the optimizer
5. Generate nurse, doctor, and bed assignments (re-optimized on every discharge)
6. Store predictions and assignments in the database
7. Display results through the frontend

The forecasting models are trained offline and loaded by the platform during deployment. They are not retrained for every prediction — a manual retraining endpoint is available instead.

---

## Environment

| Category | Technology |
|---|---|
| Programming | Python, JavaScript |
| Machine Learning | Scikit-learn |
| Data Processing | Pandas, NumPy |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Optimization | Binary Integer Programming — PuLP / CBC |
| Backend | FastAPI |
| Frontend | React |
| Model Development | Google Colab |
| Model Serialization | Joblib |

---

## Repository

https://github.com/Jinan-Bark/H-Copilot

---

## Notes

- The final forecasting model uses exactly 15 deployment-compatible features, blending Random Forest and Neural Network predictions.
- Forecasting is evaluated using chronological walk-forward (rolling-origin) validation with periodic retraining, naive baselines, permutation testing, and cross-validation.
- The optimization layer re-optimizes automatically on every patient discharge and includes a threshold-gated aging mechanism to mitigate starvation risk.
- The deployment architecture uses database data rather than CSV sampling.
- Predictions and optimization assignments are integrated with the database.
- `SHIFT` and `GROUP` are passed dynamically by the platform.
- Credentials, API keys, and private clinical data must not be committed.
- Extended validation with real-world hospital data is required before production deployment.
