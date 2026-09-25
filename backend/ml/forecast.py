import pandas as pd
import time
import joblib
import os
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'flow_prediction_model.pkl')
TRIAGE_PATH = os.path.join(os.path.dirname(__file__), 'historical_flow_raw.csv')

saved = joblib.load(MODEL_PATH)
rf_model = saved['rf']
mlp_model = saved['mlp']
scaler = saved['scaler']

triage_data = pd.read_csv(TRIAGE_PATH, parse_dates=['date'])

AVG_UNDERPREDICTION = 3.10

FEATURE_COLS = [
    'hour_slot', 'day_of_week', 'month', 'week_of_year', 'is_weekend',
    'lag_2wk_avg', 'lag_4wk_avg', 'lag_8wk_avg', 'lag_12wk_avg',
    'lag_8wk_severity', 'lag_8wk_high_acuity', 'daily_cumulative_avg',
    'lag_8wk_avg_PainGrade',
    'lag_8wk_Medical/Internal', 'lag_8wk_Trauma/Injury'
]

def _recent_avg(df, value_col, day_of_week, hour_slot, target_date, weeks):
    if value_col not in df.columns:
        return 0
    past = df[
        (df['day_of_week'] == day_of_week) &
        (df['hour_slot'] == hour_slot) &
        (df['date'] < target_date)
    ].sort_values('date', ascending=False).head(weeks)
    return past[value_col].mean() if not past.empty else 0

def _daily_cumulative(df, target_date, hour_slot):
    same_day = df[(df['date'] == target_date) & (df['hour_slot'] < hour_slot)]
    if same_day.empty:
        return 0
    val = same_day['patient_count'].mean()
    return val if pd.notna(val) else 0

def predict_slot(target_date: str, hour_slot: int):
    target_date = pd.to_datetime(target_date)
    day_of_week = (target_date.dayofweek + 1) % 7
    daily_cum = _daily_cumulative(triage_data, target_date, hour_slot)

    features = {
        'hour_slot': hour_slot,
        'day_of_week': day_of_week,
        'month': target_date.month,
        'week_of_year': target_date.isocalendar()[1],
        'is_weekend': int(day_of_week in [0, 6]),
        'lag_2wk_avg': _recent_avg(triage_data, 'patient_count', day_of_week, hour_slot, target_date, 2),
        'lag_4wk_avg': _recent_avg(triage_data, 'patient_count', day_of_week, hour_slot, target_date, 4),
        'lag_8wk_avg': _recent_avg(triage_data, 'patient_count', day_of_week, hour_slot, target_date, 8),
        'lag_12wk_avg': _recent_avg(triage_data, 'patient_count', day_of_week, hour_slot, target_date, 12),
        'lag_8wk_severity': _recent_avg(triage_data, 'severity', day_of_week, hour_slot, target_date, 8),
        'lag_8wk_high_acuity': _recent_avg(triage_data, 'high_acuity', day_of_week, hour_slot, target_date, 8),
        'daily_cumulative_avg': daily_cum,
        'lag_8wk_avg_PainGrade': _recent_avg(triage_data, 'avg_PainGrade', day_of_week, hour_slot, target_date, 8),
        'lag_8wk_Medical/Internal': _recent_avg(triage_data, 'Medical/Internal', day_of_week, hour_slot, target_date, 8),
        'lag_8wk_Trauma/Injury': _recent_avg(triage_data, 'Trauma/Injury', day_of_week, hour_slot, target_date, 8),
    }

    X = pd.DataFrame([features])[FEATURE_COLS]
    X_scaled = scaler.transform(X)

    pred_rf = rf_model.predict(X)[0]
    pred_mlp = mlp_model.predict(X_scaled)[0]
    predicted = (pred_rf + pred_mlp) / 2

    return {
        "date": str(target_date.date()),
        "hour_slot": hour_slot,
        "predicted_arrivals": round(float(predicted), 1),
        "recommended_staffing_buffer": round(float(predicted) + AVG_UNDERPREDICTION, 1)
    }

def predict_week(start_date: str):
    start = pd.to_datetime(start_date)
    results = []
    for day_offset in range(7):
        current_date = start + pd.Timedelta(days=day_offset)
        day_slots = [predict_slot(str(current_date.date()), h) for h in range(6)]
        daily_total = sum(s['predicted_arrivals'] for s in day_slots if 'predicted_arrivals' in s)
        results.append({"date": str(current_date.date()), "slots": day_slots, "daily_total_predicted": round(daily_total, 1)})
    return results


# ICD-chapter-style mapping — only works if chiefcomplaint follows the training data's coded format.
# Real intake likely uses free text; entries that don't match simply won't count toward these 2 features.
CATEGORY_MAP = {
    'S': 'Trauma/Injury', 'T': 'Trauma/Injury', 'W': 'Trauma/Injury',
}

def _classify_complaint(text):
    if not text or len(text) == 0:
        return None
    first = text.strip()[0].upper()
    return CATEGORY_MAP.get(first)

def _build_slots_from_db(db_session):
    """Pull real patients from the platform DB and aggregate into slot-level rows,
    matching the exact structure of historical_flow_raw.csv."""
    from models import Patient  # adjust import path if needed

    patients = db_session.query(Patient).filter(Patient.arrival_time.isnot(None)).all()

    rows = []
    for p in patients:
        rows.append({
            'date': p.arrival_time.date(),
            'day_of_week': (p.arrival_time.weekday() + 1) % 7,
            'hour_slot': p.arrival_time.hour // 4,
            'acuity': p.acuity,
            'pain': p.pain,
            'complaint_macro': _classify_complaint(p.chiefcomplaint),
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    slots = (
        df.groupby(['date', 'day_of_week', 'hour_slot'])
        .agg(
            patient_count=('acuity', 'count'),
            severity=('acuity', 'mean'),
            high_acuity=('acuity', lambda x: (x <= 2).mean()),
            avg_PainGrade=('pain', 'mean'),
        )
        .reset_index()
    )
    for cat in ['Medical/Internal', 'Trauma/Injury']:
        counts = df[df['complaint_macro'] == cat].groupby(['date', 'hour_slot']).size()
        slots[cat] = slots.set_index(['date', 'hour_slot']).index.map(counts).fillna(0).values

    return slots

def retrain_model(db_session):
    """Pulls real accumulated patient data, merges with historical baseline,
    retrains rf+mlp+scaler, and overwrites the saved model + raw data file."""
    global rf_model, mlp_model, scaler, triage_data
    start_time = time.time()
    print("[RETRAIN] Starting retrain...")

    new_slots = _build_slots_from_db(db_session)
    print(f"[RETRAIN] Pulled {len(new_slots) if new_slots is not None else 0} new slot-rows from database")

    combined = triage_data.copy()
    if new_slots is not None and len(new_slots) > 0:
        combined = pd.concat([combined, new_slots], ignore_index=True)
        combined = combined.drop_duplicates(subset=['date', 'hour_slot'], keep='last')

    print(f"[RETRAIN] Combined dataset: {len(combined)} total rows")


    combined['date'] = pd.to_datetime(combined['date'])
    combined = combined.sort_values(['date', 'hour_slot']).reset_index(drop=True)

    for weeks in [2, 4, 8, 12]:
        combined[f'lag_{weeks}wk_avg'] = combined.groupby(['day_of_week', 'hour_slot'])['patient_count'].transform(
            lambda x: x.shift(1).rolling(weeks, min_periods=1).mean())
    for col, name in [('severity', 'lag_8wk_severity'), ('high_acuity', 'lag_8wk_high_acuity'),
                       ('avg_PainGrade', 'lag_8wk_avg_PainGrade'),
                       ('Medical/Internal', 'lag_8wk_Medical/Internal'), ('Trauma/Injury', 'lag_8wk_Trauma/Injury')]:
        combined[name] = combined.groupby(['day_of_week', 'hour_slot'])[col].transform(
            lambda x: x.shift(1).rolling(8, min_periods=1).mean())

    combined['month'] = combined['date'].dt.month
    combined['week_of_year'] = combined['date'].dt.isocalendar().week.astype(int)
    combined['is_weekend'] = combined['day_of_week'].isin([0, 6]).astype(int)
    combined['daily_cumulative_avg'] = combined.groupby('date')['patient_count'].transform(
        lambda x: x.expanding().mean().shift(1)).fillna(combined['lag_8wk_avg'])

    X = combined.dropna(subset=FEATURE_COLS)[FEATURE_COLS]
    y = combined.dropna(subset=FEATURE_COLS)['patient_count']

    new_scaler = StandardScaler()
    X_scaled = new_scaler.fit_transform(X)

    new_rf = RandomForestRegressor(n_estimators=200, max_depth=6, criterion='absolute_error', random_state=42)
    print("[RETRAIN] Training Random Forest...")
    new_rf.fit(X, y)
    new_mlp = MLPRegressor(hidden_layer_sizes=(50,), alpha=0.0001, learning_rate_init=0.01,
                            max_iter=2000, random_state=42, early_stopping=True)
    print("[RETRAIN] Training Neural Network...")
    new_mlp.fit(X_scaled, y)
    print("[RETRAIN] Saving updated model...")
    joblib.dump({'rf': new_rf, 'mlp': new_mlp, 'scaler': new_scaler}, MODEL_PATH)
    combined.to_csv(TRIAGE_PATH, index=False)

    rf_model, mlp_model, scaler = new_rf, new_mlp, new_scaler
    triage_data = combined

    elapsed = time.time() - start_time
    print(f"[RETRAIN] Done in {elapsed:.1f} seconds.")
    return {"status": "retrained", "rows_used": len(combined), "new_rows_added": len(new_slots) if new_slots is not None else 0, "seconds_taken": round(elapsed, 1)}