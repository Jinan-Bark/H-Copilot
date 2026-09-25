import pandas as pd
import joblib
import os

MODELS_PATH = os.path.join(os.path.dirname(__file__), 'patient_type_models.pkl')
HISTORY_PATH = os.path.join(os.path.dirname(__file__), 'historical_patient_type.csv')

models = joblib.load(MODELS_PATH)
history = pd.read_csv(HISTORY_PATH, parse_dates=['date'])

categories = ['Medical/Internal', 'Musculoskeletal/Skin', 'Other/Administrative', 'Trauma/Injury']

def predict_patient_type(target_date: str, hour_slot: int):
    target_date = pd.to_datetime(target_date)
    day_of_week = target_date.dayofweek  # Monday=0 — matches this model's training, NOT the flow model's system

    past = history[
        (history['day_of_week'] == day_of_week) &
        (history['hour_slot_num'] == hour_slot) &
        (history['date'] < target_date)
    ].sort_values('date', ascending=False).head(4)

    if past.empty:
        return {"error": "Not enough historical data for this slot"}

    lag_avgs = {cat: past[cat].mean() for cat in categories}

    predictions = {}
    for cat in categories:
        if cat in models:
            X = pd.DataFrame({
                'hour_slot_num': [hour_slot],
                **{f'lag_4wk_{c}': [lag_avgs[c]] for c in categories}
            })
            pred = models[cat].predict(X)[0]
        else:
            # Medical/Internal — no trained model, use the lag average directly
            pred = lag_avgs[cat]
        predictions[cat] = round(float(pred), 1)

    return {
        "date": str(target_date.date()),
        "hour_slot": hour_slot,
        "predicted_breakdown": predictions
    }