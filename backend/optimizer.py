import pandas as pd
import pulp
from datetime import datetime, timezone

acuity_weight    = {1: 100, 2: 50, 3: 20, 4: 5, 5: 1}
max_wait_minutes = {1: 0, 2: 15, 3: 30, 4: 60, 5: 120}

def covers_ward(ward_list, ward_id):
    return str(ward_id) in ward_list

def parse_wards(ward_str):
    return [w.strip() for w in str(ward_str).replace('"', '').split(',')]

def run_optimizer(patients_df, beds_df, nurses_df, doctors_df, shift, group, date):
    """
    H-Copilot ED Assignment Optimizer
    
    Parameters:
    -----------
    patients_df : DataFrame — patients to assign
    beds_df     : DataFrame — all beds
    nurses_df   : DataFrame — all nurses
    doctors_df  : DataFrame — all doctors
    shift       : str — 'morning' or 'night'
    group       : int — 1 or 2
    date        : str — date label

    Returns:
    --------
    assignments_df : DataFrame — assigned patients
    waiting_df     : DataFrame — waiting patients
    """

    # Parse ward lists
    nurses_df  = nurses_df.copy()
    doctors_df = doctors_df.copy()
    nurses_df['ward_list']  = nurses_df['ward'].apply(parse_wards)
    doctors_df['ward_list'] = doctors_df['ward'].apply(parse_wards)

    # Filter resources
    avail_beds  = beds_df[beds_df['bed_status'] == 'Available'].reset_index(drop=True)
    on_duty_rn  = nurses_df[(nurses_df['role'] == 'RN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)].reset_index(drop=True)
    on_duty_pn  = nurses_df[(nurses_df['role'] == 'PN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)].reset_index(drop=True)
    on_duty_doc = doctors_df[(doctors_df['shift'] == shift) & (doctors_df['work_days'] == group)].reset_index(drop=True)
    patients    = patients_df.reset_index(drop=True)

    # Validate resources
    if len(avail_beds) == 0:
        return pd.DataFrame(), patients_df.assign(reason='No available beds')
    if len(on_duty_rn) == 0:
        return pd.DataFrame(), patients_df.assign(reason='No RNs on duty')
    if len(on_duty_pn) == 0:
        return pd.DataFrame(), patients_df.assign(reason='No PNs on duty')
    if len(on_duty_doc) == 0:
        return pd.DataFrame(), patients_df.assign(reason='No doctors on duty')

    P  = list(patients.index)
    B  = list(avail_beds.index)
    RN = list(on_duty_rn.index)
    PN = list(on_duty_pn.index)
    D  = list(on_duty_doc.index)

    # Build model
    model = pulp.LpProblem('ED_Assignment', pulp.LpMinimize)
    x    = pulp.LpVariable.dicts('bed', [(i,j) for i in P for j in B], cat='Binary')
    y_rn = pulp.LpVariable.dicts('rn',  [(i,n) for i in P for n in RN], cat='Binary')
    y_pn = pulp.LpVariable.dicts('pn',  [(i,n) for i in P for n in PN], cat='Binary')
    z    = pulp.LpVariable.dicts('doc', [(i,d) for i in P for d in D], cat='Binary')

    # Constraints
    for i in P:
        model += pulp.lpSum(x[i,j] for j in B) <= 1
    for j in B:
        model += pulp.lpSum(x[i,j] for i in P) <= 1
    for i in P:
        for n in RN:
            vb = [j for j in B if covers_ward(on_duty_rn.loc[n,'ward_list'], avail_beds.loc[j,'ward_id'])]
            model += y_rn[i,n] <= (pulp.lpSum(x[i,j] for j in vb) if vb else 0)
        model += pulp.lpSum(y_rn[i,n] for n in RN) == pulp.lpSum(x[i,j] for j in B)
        model += pulp.lpSum(y_pn[i,n] for n in PN) == pulp.lpSum(x[i,j] for j in B)
        for d in D:
            vb = [j for j in B if covers_ward(on_duty_doc.loc[d,'ward_list'], avail_beds.loc[j,'ward_id'])]
            model += z[i,d] <= (pulp.lpSum(x[i,j] for j in vb) if vb else 0)
        model += pulp.lpSum(z[i,d] for d in D) == pulp.lpSum(x[i,j] for j in B)

    # Objective — ESI priority + aging bonus, only after each patient
    # crosses their own max_wait_minutes threshold
    AGING_RATE_PER_HOUR = 3.75
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    def _calculate_priority(patient):
        acuity = int(patient['acuity'])
        base_weight = acuity_weight.get(acuity, 1)

        arrival = patient.get('arrival_time')
        if arrival is None or pd.isna(arrival):
            return base_weight

        minutes_waited = max((now - arrival).total_seconds() / 60, 0)
        threshold_min = max_wait_minutes.get(acuity, 60)

        if minutes_waited <= threshold_min:
            return base_weight
        else:
            overshoot_hours = (minutes_waited - threshold_min) / 60
            return base_weight + overshoot_hours * AGING_RATE_PER_HOUR

    model += pulp.lpSum(
        _calculate_priority(patients.loc[i]) * (1 - pulp.lpSum(x[i,j] for j in B))
        for i in P
    )

    model.solve(pulp.PULP_CBC_CMD(msg=0))

    # Extract results
    assignments, waiting = [], []
    for i in P:
        patient  = patients.loc[i]
        assigned = False
        for j in B:
            if pulp.value(x[i,j]) == 1:
                bed      = avail_beds.loc[j]
                rn_id    = next((on_duty_rn.loc[n,'nurse_id']  for n in RN if pulp.value(y_rn[i,n]) == 1), None)
                pn_id    = next((on_duty_pn.loc[n,'nurse_id']  for n in PN if pulp.value(y_pn[i,n]) == 1), None)
                doc_id   = next((on_duty_doc.loc[d,'doctor_id'] for d in D  if pulp.value(z[i,d])   == 1), None)
                doc_type = on_duty_doc[on_duty_doc['doctor_id'] == doc_id]['is_intern'].values[0] if doc_id else None
                assignments.append({
                    'stay_id'       : int(patient['stay_id']),
                    'acuity'        : int(patient['acuity']),
                    'chiefcomplaint': patient['chiefcomplaint'],
                    'bed_number'    : bed['bed_number'],
                    'ward_id'       : int(bed['ward_id']),
                    'rn_id'         : int(rn_id) if rn_id else None,
                    'pn_id'         : int(pn_id) if pn_id else None,
                    'doctor_id'     : int(doc_id) if doc_id else None,
                    'is_intern'     : bool(doc_type) if doc_type is not None else None,
                    'shift'         : shift,
                    'date'          : date
                })
                assigned = True
                break
        if not assigned:
            waiting.append({
                'stay_id'        : int(patient['stay_id']),
                'acuity'         : int(patient['acuity']),
                'chiefcomplaint' : patient['chiefcomplaint'],
                'max_wait_min'   : max_wait_minutes.get(int(patient['acuity']), 60)
            })

    return pd.DataFrame(assignments), pd.DataFrame(waiting)