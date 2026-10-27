# H-Copilot, Data Engineering and Predictive Modeling for a Hospital Decision Support Platform

Research codebase for the M.Sc. Data Science thesis:
**"Data Engineering and Predictive Modeling for a Hospital Decision Support Platform (H-Copilot)"**
Jinan Bark, Lebanese University, Faculty of Sciences, 2026

GitHub repository: https://github.com/Jinan-Bark/H-Copilot

H-Copilot is a **two-layer AI-powered ED bed and staff assignment platform** combining a proactive prediction layer with a reactive optimization layer. The prediction layer forecasts patient arrivals in upcoming **4-hour time slots** using a blended Random Forest / Neural Network ensemble; the optimization layer formulates bed, nurse, and doctor assignment as a **Binary Integer Program** solved with PuLP/CBC, re-optimizing automatically on every patient discharge.

---

## Key Results

| Metric | H-Copilot | Baseline |
|---|---|---|
| Prediction MAE | **3.09** | outperforms SARIMAX & NNAR-style baselines |
| Prediction WAPE | **20.62%** | modest, statistically-supported gain over naive (sign flip permutation test, p < 0.001) |
| Priority compliance (high demand) | **100%** | 6.7% (First-Come-First-Served) |
| Critical-patient starvation cases | **0** | 17 (First-Come-First-Served) |
| Low-acuity starvation (12h aging evaluation window) | **0** | not applicable (critical-patient protection unaffected) |

The final prediction model is a blended Random Forest / Neural Network ensemble, validated through walk-forward (rolling-origin) evaluation with periodic retraining, multiple naive baselines, permutation testing, and cross-validation. The optimization layer's threshold-gated aging mechanism lets waiting time influence assignment priority indirectly, mitigating the starvation risk that strict acuity-based prioritization would otherwise introduce, without weakening critical-patient protection. A tested workload-balancing extension also reduces maximum individual staff caseload, within staffing constraints.

Both layers are integrated into an implemented, full-stack platform (**React**, **FastAPI**, **PostgreSQL**), with a manual retraining endpoint allowing the prediction model to be refreshed on demand as new real platform data accumulates.

All results come from the Iranian ED dataset and simulated patient flow and load, not from a live hospital trial.

---

## Where to Look First

| I want to... | Go to |
|---|---|
| **Run the platform with Docker** | "How to run" below |
| **Rebuild the forecasting model** | `notebooks/1_Final_Model_Clean_Build.ipynb` |
| **See the final evaluation, permutation test and model comparison** | `notebooks/2_Final_Evaluation_and_Model_Comparison.ipynb` |
| **Understand the forecasting code** | `backend/ml/forecast.py` |
| **Understand the resource optimizer** | `backend/optimizer.py` |
| **Reproduce the simulations** | `backend/simulate_or_aging_30min.py` and `backend/simulate_or_aging_30min_loadsweep.py` |
| **Understand the workload-balancing extension** | `backend/workload_balancing.py` |
| **Understand database integration** | `backend/database.py` |
| **See the datasets and preprocessing** | `METADATA.md` |

---

## Project Layout

```text
5_Source_Code_and_Data/  (the repository root)
│
├── backend/                    FastAPI services and AI integration
│   ├── database.py             PostgreSQL / SQLAlchemy connection
│   ├── main.py                 FastAPI entry point
│   ├── models.py               Database models
│   ├── optimizer.py            Resource optimization (PuLP/CBC)
│   ├── evaluate_or.py          OR vs. FCFS evaluation
│   ├── simulate_or.py          Multi-round starvation simulation
│   ├── simulate_or_aging.py    Multi-round simulation with aging
│   ├── simulate_or_aging_30min.py            30 minute round simulation (200 trials)
│   ├── simulate_or_aging_30min_loadsweep.py  same at 70, 85 and 100 percent load
│   ├── workload_balancing.py   Workload-balancing extension
│   ├── seed.py                 Database seed data (reads data/raw)
│   └── ml/                     Trained models and forecasting code
│
├── frontend/                   React platform interface
├── notebooks/                  Model development, evaluation and exploration (Google Colab)
├── data/
│   ├── raw/                    Original data before preprocessing
│   └── processed/              Cleaned data ready for modelling
├── results/                    Simulation output files used in the thesis
├── METADATA.md                 Dataset description, sources and preprocessing
├── Dockerfile, docker-compose.yml, requirements.txt, .env.example
├── .gitignore
└── README.md
```

> **Note:** `backend/venv/`, `.env`, credentials, and other sensitive information are **not** included. The two processed files `historical_flow_raw.csv` and `historical_patient_type.csv` exist in `data/processed/` and also in `backend/ml/`, because the forecasting code reads the copy next to it.

---

## Notebooks

| Notebook | What it contains |
|---|---|
| `1_Final_Model_Clean_Build.ipynb` | Rebuilds the final 15 feature model from `ED_triage.csv`: cleaning, slot table, features, walk-forward evaluation, saving the model, and the data exploration figures. |
| `2_Final_Evaluation_and_Model_Comparison.ipynb` | Final evaluation of the blend, the sign flip permutation test and bootstrap interval, cross-validation, feature importance, error statistics, and the comparison of the forecasting methods. Sections 6 to 9 at the end are an older 18 feature version, not the final model. |
| `3_Exploration_History.ipynb` | Full exploration history: data checks, rejected models and feature ideas, and the early patient type model. Kept for transparency. It is not meant to be run from top to bottom. |

The notebooks were run on Google Colab. Extra packages are listed in `notebooks/requirements_notebooks.txt`. Each notebook asks for `ED_triage.csv` (in `data/raw/`) when it starts.

---

## Dataset

The prediction layer is trained on the Iranian ED dataset (Mashhad University of Medical Sciences), `ED_triage.csv`, an open access dataset (Mendeley Data, CC BY 4.0). The source link, columns and preprocessing steps are in `METADATA.md`. `EDbeds.csv`, `Nurses.csv` and `Doctors.csv` are synthetic files created by Jinan Bark and Hussein Omeis from information collected from several hospitals and nurses.

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

The final forecasting model uses **15 platform-compatible features**:

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

After walk-forward evaluation, the final models are retrained using all available historical observations. A manual retraining endpoint (`/admin/retrain`) allows the model to be refreshed on demand as real platform data accumulates.

### Experimental part: patient type prediction

An initial implementation for predicting the type of patients (complaint group) in upcoming time slots was started (`backend/ml/patient_type.py`, `patient_type_models.pkl`, `historical_patient_type.csv`, and the `/patient-type` endpoint). It is **not complete, not evaluated, and not connected to the frontend or to the forecasting results in the thesis.** The Medical/Internal group has no trained model (it uses the 4 week average). Completing, evaluating and integrating it is future work.

---

## Resource Optimization

The optimization layer formulates bed, nurse, and doctor assignment as a **Binary Integer Program**, solved with **PuLP/CBC**, minimizing a priority-weighted count of unassigned patients subject to ward, shift, and role-matching constraints. It re-optimizes automatically on every patient discharge.

Current optimization scope: nurses, doctors, beds. `SHIFT` and `GROUP` are passed dynamically by the platform rather than being hardcoded inside the optimization engine.

### Aging Mechanism

Waiting time influences assignment priority indirectly through a **threshold-gated aging mechanism**, using per-acuity wait thresholds (0/10/30/60/120 minutes for ESI 1 through 5, from the Australasian Triage Scale), mitigating the starvation risk that strict acuity-based prioritization would otherwise introduce for low-acuity patients, without weakening critical-patient protection. Low-acuity starvation was evaluated using a 12-hour simulation window.

### Workload Balancing

A separate workload-balancing extension (`workload_balancing.py`) demonstrates a measurable, though staffing-constrained, reduction in maximum individual caseload across staff members. This extension is tested and validated, but not part of the live system.

---

## Database Integration

H-Copilot uses PostgreSQL with SQLAlchemy. The database supports operational information related to patients, nurses, doctors, beds, shifts, groups, predictions and assignments. `backend/seed.py` populates the database with sample data for local development and testing.

```text
Hospital Database -> Current Patient / Resource Data -> Patient Flow Prediction
-> Predicted Demand -> Resource Optimizer (PuLP/CBC) -> Generated Assignments
-> Assignments Table -> Frontend
```

---

## Software and hardware used

- Operating system: Windows 64 bit (development), Linux inside Docker
- Python 3.13 (the Docker image uses 3.13)
- Main packages: FastAPI, SQLAlchemy, pandas, numpy, scikit-learn 1.9.0, PuLP (CBC solver). Exact versions are in `requirements.txt`.
- Database: PostgreSQL 16
- Frontend: Node.js 20 or newer, React, Vite
- Hardware: AMD A4-9125 RADEON R3 processor (2 cores, 2.30 GHz), 8 GB RAM, 477 GB SSD, AMD Radeon R3 integrated graphics. No GPU is needed.
- The model file was saved with scikit-learn 1.9.0, so use that exact version.
- Time: the 200 trial simulation takes a long time (use `N_TRIALS = 3` first). The walk-forward blend evaluation in notebook 2 takes about 20 minutes.

---

## How to run

### Option A: Docker (recommended)

You need Docker and Docker Compose. From the repository root:

```
docker compose up --build
```

This builds the image and starts PostgreSQL and the backend. Open http://localhost:8000/docs to see the API. In a second terminal, fill the database once:

```
docker compose exec backend python seed.py
```

To start only the image, for example to run a script:

```
docker build -t h-copilot .
docker run --rm -it h-copilot bash
```

Frontend (needs Node.js 20 or newer):

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The frontend talks to the backend at http://127.0.0.1:8000.

### Option B: local Python

```
python -m venv venv
venv\Scripts\activate          (Windows)   or   source venv/bin/activate   (Linux, Mac)
pip install -r requirements.txt
```

Install PostgreSQL, create a database called `hcopilot`, copy `.env.example` to `.env` and put your own user and password in `DATABASE_URL`.

```
cd backend
python seed.py                 (fills the database once)
uvicorn main:app --reload
python workload_balancing.py   (when needed)
```

### Reproduce the simulation results

The simulation scripts read the raw files in `data/raw/` and do not need the database.

```
cd backend
python simulate_or_aging_30min.py
python simulate_or_aging_30min_loadsweep.py
```

1. Open the script and set `N_TRIALS = 3` to time a first run, then `N_TRIALS = 200` (load sweep: 100) for the full run.
2. Each trial uses a fixed random seed, so the same trial gives the same result.
3. Output files: `or_30min_raw.csv`, `or_30min_summary.csv` and the load sweep equivalents. The outputs of the runs used in the thesis are already in `results/`.

To use another folder for the raw files, set the environment variable `HCOPILOT_DATA_DIR`.

### Rebuild the prediction model

Open `notebooks/1_Final_Model_Clean_Build.ipynb` in Google Colab or Jupyter and run all cells (upload `data/raw/ED_triage.csv` when asked). The model is trained on the first 80 percent of the slots (5,060) and tested on the last 20 percent (1,265) in chronological order, with walk-forward retraining.

---

## Implementation workflow

1. Retrieve current hospital data from the database
2. Construct forecasting features
3. Generate patient-flow predictions
4. Pass demand information to the optimizer
5. Generate nurse, doctor, and bed assignments (re-optimized on every discharge)
6. Store predictions and assignments in the database
7. Display results through the frontend

The forecasting models are trained offline and loaded by the platform. They are not retrained for every prediction; the manual retraining endpoint is available instead.

---

## Notes

- The final forecasting model uses exactly 15 features, blending Random Forest and Neural Network predictions.
- Forecasting is evaluated with chronological walk-forward validation, naive baselines, permutation testing and cross-validation.
- Credentials, API keys, and private clinical data must not be committed. Never upload the real `.env` file; it contains the database password.
- All results are from simulated patient flow and simulated load, not from a live hospital trial. Extended validation with real hospital data is required before real use.
- The Docker steps were written for this project but have not been tested on the final folder in the preparation environment.
