# Metadata: datasets

## 1. Raw data (`data/raw/`)

### ED_triage.csv (main dataset)

- **Source:** Bani, Z. "An open-access dataset of emergency department admissions at a large teaching hospital in Iran", Mendeley Data, V1, published 10 November 2023.
  Link: https://data.mendeley.com/datasets/vhzyyktrz5/1 (license: CC BY 4.0)
- **Content:** one row per triage record of an ED visit. 143,582 rows and 28 columns (143,346 distinct visits; repeated triage codes are re-triage records of the same visit).
- **Period:** March 2017 to 2022.
- **Main columns:** `triage_code` (visit code), `gender`, `age`, `admission_year`, `admission_month`, `admission_day`, `admission_weekday`, `admission_hour`,
  `ChiefComplaint` (ICD style code), `NeedFastExecute`, `CriticalStatus`, `StuporStatus`, `PainGrade`, `MentalDistress`, `MaterialDistress`, `Source`,
  vital signs (`BlooddpressurSystol`, `BlooddpressurDiastol`, `PulseRate`, `RespiratoryRate`, `Temperature`, `O2Saturation`, `AVPU`),
  `TriageGrade` (acuity, 1 most urgent to 5), `operational_patient`, `ref_specialist`.
- The file is the original dataset without changes. It has missing values (for example `Source`, blood pressure, `PainGrade`).

### EDbeds.csv, Nurses.csv, Doctors.csv (created by the author)

Beds, nurses and doctors of the ED with their ward coverage, used by the optimizer, the simulations and the database seed (25 beds, 40 nurses, 17 doctors).
They are not part of the Mendeley dataset. They are synthetic data created by Jinan Bark and Hussein Omeis, based on information collected by asking several hospitals and nurses about how their beds and staff are organized. They are final example files and do not contain real records.

## 2. Processed data (`data/processed/`)

### historical_flow_raw.csv (used by the final forecasting model)

The visit level data was grouped into 4 hour slots (6 slots per day) and feature columns were added.

- Rows: 6,368 (6,367 slots from 2017-03-21 to 2020-02-21, plus 1 slot dated 2026-07-05 that was added while testing the platform. The model code removes it.)
- Target: `patient_count`, the number of arrivals in the slot

| Column | Meaning |
|---|---|
| date | Calendar date of the slot |
| day_of_week | 0 to 6 (0 is Sunday) |
| hour_slot | 0 to 5 (each slot is 4 hours) |
| patient_count | Arrivals in the slot (the value to predict) |
| severity | Mean acuity (TriageGrade) of the patients in the slot |
| high_acuity | Share of patients with TriageGrade 1 or 2 |
| avg_PainGrade | Mean pain grade |
| Medical/Internal, Trauma/Injury | Number of patients by complaint group |
| lag_2wk_avg, lag_4wk_avg, lag_8wk_avg, lag_12wk_avg | Average arrivals in the same weekday and slot over the previous 2, 4, 8 and 12 occurrences |
| lag_8wk_severity, lag_8wk_high_acuity, lag_8wk_avg_PainGrade, lag_8wk_Medical/Internal, lag_8wk_Trauma/Injury | Same slot averages over the previous 8 occurrences |
| month, week_of_year, is_weekend | Calendar features |
| daily_cumulative_avg | Average arrivals so far today |

The model uses 15 features: hour_slot, day_of_week, month, week_of_year, is_weekend, lag_2wk_avg, lag_4wk_avg, lag_8wk_avg, lag_12wk_avg,
lag_8wk_severity, lag_8wk_high_acuity, daily_cumulative_avg, lag_8wk_avg_PainGrade, lag_8wk_Medical/Internal, lag_8wk_Trauma/Injury.

### historical_patient_type.csv (experimental, patient type model)

Number of patients per complaint group (Medical/Internal, Musculoskeletal/Skin, Other/Administrative, Trauma/Injury) per 4 hour slot,
2017-03-21 to 2022-03-20, 9,841 rows. Used only by the unfinished patient type model (see the README).

### Preprocessing steps (notebook 1)

1. Remove repeated `triage_code` rows (re-triage records of the same visit), keeping the first one: 143,582 rows become 143,346.
2. Build the date from the admission year, month and day. Build `day_of_week` and the 4 hour `hour_slot` (admission hour divided by 4).
3. Keep only the COVID free range up to 2020-02-21 (arrivals dropped sharply after 22 February 2020). This leaves 91,490 visits.
4. Group by date and slot: count patients (`patient_count`) and compute the mean acuity, mean pain grade and the share of TriageGrade 1 and 2.
5. Group `ChiefComplaint` by its first letter (ICD chapter) into four groups: Trauma/Injury, Medical/Internal, Musculoskeletal/Skin and Other/Administrative.
6. Compute lag features from earlier weeks only, so no future information is used.
7. Drop rows without enough history. This leaves 6,325 slots.
8. Split in chronological order: first 80 percent for training (5,060 slots), last 20 percent for testing (1,265 slots).
9. Scale inputs with a standard scaler fitted on the training part only (used by the MLP).

## 3. Results (`results/`)

| File | Description |
|---|---|
| or_30min_raw.csv, or_30min_summary.csv | 200 simulated days, 30 minute rounds, FCFS vs OR vs OR with aging (raw rows and means) |
| or_30min_loadsweep_raw.csv, or_30min_loadsweep_summary.csv | 100 trials per method at 70, 85 and 100 percent load |
| or_multi_trial_raw.csv, or_multi_trial_summary.csv | multi trial simulation runs (FCFS vs OR) with starvation and backlog statistics |
| or_simulation_results.csv, or_evaluation_results.csv | single run results of the simulation and the evaluation |
| or_starvation_cases.csv | starvation cases of the single run |
| or_extended_round_logs.csv, or_extended_summary.csv | extended run logs and summary |

## 4. Trained models (`backend/ml/`)

- `flow_prediction_model.pkl`: dictionary with the Random Forest (`rf`), the MLP (`mlp`) and the scaler. Predictions are the 50/50 average of the two models. Saved with scikit-learn 1.9.0.
- `patient_type_models.pkl`: experimental patient type models (see the README).
