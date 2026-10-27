# H-Copilot: Source Code and Data

H-Copilot is a decision support platform for Emergency Department (ED) bed and staff assignment. It has two layers:

1. **Prediction layer.** Forecasts patient arrivals for the next 4 hour slot. The final model averages a Random Forest and a Neural Network (MLP) 50/50 and uses 15 features.
2. **Optimization layer.** A Binary Integer Program (PuLP with the CBC solver) that assigns beds, nurses and doctors to waiting patients. It weights patients by ESI level and adds an aging bonus so low acuity patients do not wait forever. It is compared with a first come first served (FCFS) baseline in a Monte Carlo simulation.

The platform also has a FastAPI backend with a PostgreSQL database and a React frontend.

Author: Jinan Bark, Master in Data Science, Lebanese University, Faculty of Sciences.
GitHub repository: https://github.com/Jinan-Bark/H-Copilot

## Folder content

```
5_Source_Code_and_Data/
  README.md                 this file
  METADATA.md               description of the datasets (sources, columns, preprocessing)
  Dockerfile                execution environment of the backend
  docker-compose.yml        starts PostgreSQL and the backend together
  requirements.txt          Python packages (exact versions)
  .env.example              example of the database setting (copy to .env)
  backend/                  FastAPI service and the platform code
    main.py                 API endpoints
    database.py, models.py  PostgreSQL connection and tables
    optimizer.py            optimization layer (Binary Integer Program)
    evaluate_or.py          FCFS baseline and single run evaluation
    simulate_or.py, simulate_or_aging.py             4 hour round simulations
    simulate_or_aging_30min.py                       30 minute round simulation, 200 trials
    simulate_or_aging_30min_loadsweep.py             same at 70, 85 and 100 percent load
    workload_balancing.py   staff workload balancing
    seed.py                 fills the database with wards, beds, staff and patients (reads data/raw)
    ml/                     prediction layer
      forecast.py           patient flow forecasting (loads the trained model)
      flow_prediction_model.pkl     trained Random Forest and MLP
      historical_flow_raw.csv       slot table used by the forecast
      patient_type.py, patient_type_models.pkl, historical_patient_type.csv   EXPERIMENTAL, see below
  frontend/                 React web interface (Vite)
  notebooks/                Google Colab notebooks (see the table below)
  data/raw/                 original data before preprocessing
  data/processed/           cleaned data ready for modelling
  results/                  output files of the simulations used in the thesis
```

## Notebooks

| Notebook | What it contains |
|---|---|
| `1_Final_Model_Clean_Build.ipynb` | Rebuilds the final 15 feature model from `ED_triage.csv`: cleaning, slot table, features, walk forward evaluation, saving the model, and the data exploration figures. |
| `2_Final_Evaluation_and_Model_Comparison.ipynb` | Final evaluation of the blend (walk forward), the sign flip permutation test and bootstrap interval, cross validation, feature importance, error statistics, and the comparison of the forecasting methods. Sections 6 to 9 at the end are an older 18 feature version, not the final model. |
| `3_Exploration_History.ipynb` | Full exploration history: data checks, the rejected models and feature ideas, and the early patient type model. Kept for transparency. It is not meant to be run from top to bottom. |

The notebooks were run on Google Colab. Extra packages are listed in `notebooks/requirements_notebooks.txt`.
Each notebook asks for `ED_triage.csv` (in `data/raw/`) when it starts.

## Experimental part: patient type prediction

An initial implementation for predicting the type of patients (complaint group) in upcoming time slots was started
(`backend/ml/patient_type.py`, `patient_type_models.pkl`, `historical_patient_type.csv`, and the `/patient-type` endpoint).
It is **not complete, not evaluated, and not connected to the frontend or to the forecasting results in the thesis.**
The Medical/Internal group has no trained model (it uses the 4 week average). Completing, evaluating and integrating it is future work.

## Software and hardware used

- Operating system: Windows (development), Linux inside Docker
- Python 3.13 (the Docker image uses 3.13)
- Main packages: FastAPI, SQLAlchemy, pandas, numpy, scikit-learn 1.9.0, PuLP (CBC solver). Exact versions are in `requirements.txt`.
- Database: PostgreSQL 16
- Frontend: Node.js 20 or newer, React, Vite
- Hardware: AMD A4-9125 RADEON R3 processor (2 cores, 2.30 GHz), 8 GB RAM, 477 GB SSD, AMD Radeon R3 integrated graphics, Windows 64 bit. No GPU is needed.
- The model file was saved with scikit-learn 1.9.0, so use that exact version.
- Time: the 200 trial simulation takes a long time (use `N_TRIALS = 3` first). The walk forward blend evaluation in notebook 2 takes about 20 minutes.

## How to run

### Option A: Docker (recommended)

You need Docker and Docker Compose. From inside the `5_Source_Code_and_Data` folder:

```
docker compose up --build
```

This builds the image and starts PostgreSQL and the backend. Open http://localhost:8000/docs to see the API.
In a second terminal, fill the database once:

```
docker compose exec backend python seed.py
```

To run only the Docker image (without the database), for example to run a script:

```
docker build -t h-copilot .
docker run --rm -it h-copilot bash
```

To run the frontend (needs Node.js 20 or newer):

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
```

### Reproduce the simulation results

The simulation scripts read the raw files in `data/raw/`. They do not need the database.

```
cd backend
python simulate_or_aging_30min.py
python simulate_or_aging_30min_loadsweep.py
```

1. Open the script and set `N_TRIALS = 3` to time a first run, then `N_TRIALS = 200` (load sweep: 100) for the full run.
2. Each trial uses a fixed random seed, so the same trial gives the same result.
3. Output files: `or_30min_raw.csv`, `or_30min_summary.csv` and the load sweep equivalents.
   The outputs of the runs used in the thesis are already in `results/`.

To use another folder for the raw files, set the environment variable `HCOPILOT_DATA_DIR`.

### Rebuild the prediction model

Open `notebooks/1_Final_Model_Clean_Build.ipynb` in Google Colab or Jupyter and run all cells (upload `data/raw/ED_triage.csv` when asked).
The model is trained on the first 80 percent of the slots (5,060) and tested on the last 20 percent (1,265) in chronological order, with walk forward retraining.

## Retraining on the live platform

The `/admin/retrain` endpoint of the backend reads new patient records from the database, rebuilds the features, retrains both models, saves them, and swaps them in without restarting the service.

## Notes

- All results are from simulated patient flow and simulated load, not from a live hospital trial.
- The Docker steps were written for this project but have not been tested on the final folder in the preparation environment.
