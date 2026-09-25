"""
H-Copilot OR Extended Evaluation: Aging Mechanism + Full Metric Set

Compares 3 methods across the same multi-round simulation:
  1. FCFS baseline (no priority awareness)
  2. Current OR (ESI-weighted, as actually deployed)
  3. OR + Aging (a TESTED enhancement, NOT deployed to the live platform --
     increases a waiting patient's effective priority the longer they wait,
     to prevent the low-acuity starvation found in the earlier simulation)

Adds the metrics used across the 5 reviewed OR papers that were not yet
covered: total waiting time (hours), average length of stay (hours),
throughput, and staff utilization.

Run from backend/ (same folder as optimizer.py, evaluate_or.py, simulate_or.py).
"""

import numpy as np
import pandas as pd
import pulp

from optimizer import acuity_weight, parse_wards, covers_ward
from evaluate_or import run_fcfs
from simulate_or import build_round_arrivals, N_ROUNDS, NEW_ARRIVALS_PER_ROUND, STARVATION_THRESHOLD

HOURS_PER_ROUND = 4  # matches the platform's 4-hour flow-prediction slot convention
AGING_FACTOR = 15    # weight added per round already waited


# ---------------------------------------------------------------------------
# OR + Aging: same structure as the real optimizer, but the objective weight
# for each patient includes an "aging bonus" based on rounds already waited.
# ---------------------------------------------------------------------------
def run_optimizer_aging(patients_df, beds_df, nurses_df, doctors_df, shift, group, date, wait_counters=None):
    wait_counters = wait_counters or {}
    nurses_df = nurses_df.copy()
    doctors_df = doctors_df.copy()
    nurses_df['ward_list'] = nurses_df['ward'].apply(parse_wards)
    doctors_df['ward_list'] = doctors_df['ward'].apply(parse_wards)

    avail_beds = beds_df[beds_df['bed_status'] == 'Available'].reset_index(drop=True)
    on_duty_rn = nurses_df[(nurses_df['role'] == 'RN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)].reset_index(drop=True)
    on_duty_pn = nurses_df[(nurses_df['role'] == 'PN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)].reset_index(drop=True)
    on_duty_doc = doctors_df[(doctors_df['shift'] == shift) & (doctors_df['work_days'] == group)].reset_index(drop=True)
    patients = patients_df.reset_index(drop=True)

    if len(avail_beds) == 0 or len(on_duty_rn) == 0 or len(on_duty_pn) == 0 or len(on_duty_doc) == 0:
        return pd.DataFrame(), patients_df

    P, B, RN, PN, D = list(patients.index), list(avail_beds.index), list(on_duty_rn.index), list(on_duty_pn.index), list(on_duty_doc.index)

    model = pulp.LpProblem('ED_Assignment_Aging', pulp.LpMinimize)
    x = pulp.LpVariable.dicts('bed', [(i, j) for i in P for j in B], cat='Binary')
    y_rn = pulp.LpVariable.dicts('rn', [(i, n) for i in P for n in RN], cat='Binary')
    y_pn = pulp.LpVariable.dicts('pn', [(i, n) for i in P for n in PN], cat='Binary')
    z = pulp.LpVariable.dicts('doc', [(i, d) for i in P for d in D], cat='Binary')

    for i in P:
        model += pulp.lpSum(x[i, j] for j in B) <= 1
    for j in B:
        model += pulp.lpSum(x[i, j] for i in P) <= 1
    for i in P:
        for n in RN:
            vb = [j for j in B if covers_ward(on_duty_rn.loc[n, 'ward_list'], avail_beds.loc[j, 'ward_id'])]
            model += y_rn[i, n] <= (pulp.lpSum(x[i, j] for j in vb) if vb else 0)
        model += pulp.lpSum(y_rn[i, n] for n in RN) == pulp.lpSum(x[i, j] for j in B)
        model += pulp.lpSum(y_pn[i, n] for n in PN) == pulp.lpSum(x[i, j] for j in B)
        for d in D:
            vb = [j for j in B if covers_ward(on_duty_doc.loc[d, 'ward_list'], avail_beds.loc[j, 'ward_id'])]
            model += z[i, d] <= (pulp.lpSum(x[i, j] for j in vb) if vb else 0)
        model += pulp.lpSum(z[i, d] for d in D) == pulp.lpSum(x[i, j] for j in B)

    # --- Effective weight = base ESI weight + aging bonus for time already waited ---
    def effective_weight(patient):
        base = acuity_weight.get(int(patient['acuity']), 1)
        bonus = wait_counters.get(str(int(patient['stay_id'])), 0) * AGING_FACTOR
        return base + bonus

    model += pulp.lpSum(
        effective_weight(patients.loc[i]) * (1 - pulp.lpSum(x[i, j] for j in B))
        for i in P
    )
    model.solve(pulp.PULP_CBC_CMD(msg=0))

    assignments, waiting = [], []
    for i in P:
        patient = patients.loc[i]
        assigned = False
        for j in B:
            if pulp.value(x[i, j]) == 1:
                bed = avail_beds.loc[j]
                rn_id = next((on_duty_rn.loc[n, 'nurse_id'] for n in RN if pulp.value(y_rn[i, n]) == 1), None)
                pn_id = next((on_duty_pn.loc[n, 'nurse_id'] for n in PN if pulp.value(y_pn[i, n]) == 1), None)
                doc_id = next((on_duty_doc.loc[d, 'doctor_id'] for d in D if pulp.value(z[i, d]) == 1), None)
                assignments.append({
                    'stay_id': int(patient['stay_id']), 'acuity': int(patient['acuity']),
                    'chiefcomplaint': patient['chiefcomplaint'], 'bed_number': bed['bed_number'],
                    'ward_id': int(bed['ward_id']), 'rn_id': int(rn_id) if rn_id else None,
                    'pn_id': int(pn_id) if pn_id else None, 'doctor_id': int(doc_id) if doc_id else None,
                    'shift': shift, 'date': date
                })
                assigned = True
                break
        if not assigned:
            waiting.append({'stay_id': int(patient['stay_id']), 'acuity': int(patient['acuity']),
                             'chiefcomplaint': patient['chiefcomplaint']})

    return pd.DataFrame(assignments), pd.DataFrame(waiting)


# ---------------------------------------------------------------------------
# Extended simulation — same round structure as simulate_or.py, plus the
# additional metrics: total waiting time, avg LOS, throughput, staff utilization
# ---------------------------------------------------------------------------
def run_extended_simulation(beds_df, nurses_df, doctors_df, triage_df, method_name,
                             use_aging=False, method_fn=None,
                             shift='morning', group=1, date='2026-09-17', seed=42):
    rng = np.random.default_rng(seed)
    all_beds = beds_df.copy()
    all_beds['bed_status'] = 'Available'
    occupied = {}
    waiting_pool = pd.DataFrame()
    wait_counters = {}
    completed_los = []  # LOS (in rounds) of each patient once discharged

    round_log = []
    starvation_cases = []

    for round_num in range(1, N_ROUNDS + 1):
        newly_freed = []
        for bed_num, (stay_id, rounds_left, total_los) in list(occupied.items()):
            rounds_left -= 1
            if rounds_left <= 0:
                newly_freed.append(bed_num)
                completed_los.append(total_los)
                del occupied[bed_num]
            else:
                occupied[bed_num] = (stay_id, rounds_left, total_los)

        current_beds = all_beds.copy()
        current_beds['bed_status'] = current_beds['bed_number'].apply(
            lambda b: 'Available' if (b not in occupied) else 'Occupied')

        new_arrivals = build_round_arrivals(triage_df, NEW_ARRIVALS_PER_ROUND, round_num, seed)
        for sid in new_arrivals['stay_id']:
            wait_counters[str(sid)] = 0
        pool = pd.concat([waiting_pool, new_arrivals], ignore_index=True) if not waiting_pool.empty else new_arrivals

        if use_aging:
            assignments_df, waiting_df = method_fn(pool, current_beds, nurses_df, doctors_df, shift, group, date, wait_counters)
        else:
            assignments_df, waiting_df = method_fn(pool, current_beds, nurses_df, doctors_df, shift, group, date)

        assigned_ids = assignments_df['stay_id'].astype(str).tolist() if not assignments_df.empty else []

        staff_used = set()
        for _, row in assignments_df.iterrows():
            los = int(rng.integers(1, 4))
            occupied[row['bed_number']] = (str(row['stay_id']), los, los)
            wait_counters.pop(str(row['stay_id']), None)
            staff_used.update([row.get('rn_id'), row.get('pn_id'), row.get('doctor_id')])

        still_waiting = pool[~pool['stay_id'].astype(str).isin(assigned_ids)].copy()
        for sid in still_waiting['stay_id'].astype(str):
            wait_counters[sid] = wait_counters.get(sid, 0) + 1
            if wait_counters[sid] >= STARVATION_THRESHOLD:
                acuity = still_waiting[still_waiting['stay_id'].astype(str) == sid]['acuity'].values[0]
                starvation_cases.append({'stay_id': sid, 'acuity': int(acuity), 'rounds_waited': wait_counters[sid], 'round': round_num})
        waiting_pool = still_waiting

        total_on_duty_staff = (
            len(nurses_df[(nurses_df['role'] == 'RN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)]) +
            len(nurses_df[(nurses_df['role'] == 'PN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)]) +
            len(doctors_df[(doctors_df['shift'] == shift) & (doctors_df['work_days'] == group)])
        )
        staff_utilization = round(100 * len(staff_used) / total_on_duty_staff, 1) if total_on_duty_staff else 0

        total_waiting_hours = sum(wait_counters.values()) * HOURS_PER_ROUND

        round_log.append({
            'Method': method_name, 'Round': round_num,
            'Throughput (admitted)': len(assignments_df),
            'Still Waiting': len(waiting_pool),
            'Bed Utilization %': round(100 * len(occupied) / len(all_beds), 1),
            'Staff Utilization %': staff_utilization,
            'Total Waiting Time (hrs, backlog)': total_waiting_hours,
            'Max Rounds Waited': max(wait_counters.values()) if wait_counters else 0,
        })

    avg_los_hours = round(np.mean(completed_los) * HOURS_PER_ROUND, 1) if completed_los else None
    summary = {
        'Method': method_name,
        'Total Starvation Cases': len(starvation_cases),
        'Starvation Cases Involving Critical (ESI1-2) Patients': sum(1 for c in starvation_cases if c['acuity'] <= 2),
        'Avg Length of Stay (hrs)': avg_los_hours,
        'Final Bed Utilization %': round_log[-1]['Bed Utilization %'],
        'Final Staff Utilization %': round_log[-1]['Staff Utilization %'],
    }

    return pd.DataFrame(round_log), pd.DataFrame(starvation_cases), summary


if __name__ == '__main__':
    beds_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\EDbeds.csv")
    nurses_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\Nurses.csv")
    nurses_df = nurses_df.rename(columns={'group': 'grp'})
    nurses_df['nurse_id'] = range(1, len(nurses_df) + 1)
    doctors_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\Doctors.csv")
    doctors_df = doctors_df.rename(columns={'intern_or_not': 'is_intern'})
    doctors_df['is_intern'] = doctors_df['is_intern'] == 'intern'
    doctors_df['doctor_id'] = range(1, len(doctors_df) + 1)
    triage_df = pd.read_excel(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\triage.xlsx")

    from optimizer import run_optimizer

    all_summaries = []
    for method_name, use_aging, method_fn in [
        ('FCFS baseline', False, run_fcfs),
        ('OR (current, deployed)', False, run_optimizer),
        ('OR + Aging (proposed, NOT deployed)', True, run_optimizer_aging),
    ]:
        print(f"\n=== {method_name} ===")
        log_df, starv_df, summary = run_extended_simulation(beds_df, nurses_df, doctors_df, triage_df, method_name, use_aging, method_fn)
        print(log_df.to_string(index=False))
        all_summaries.append(summary)

    print("\n\n=== SUMMARY COMPARISON ===")
    print(pd.DataFrame(all_summaries).to_string(index=False))
    pd.DataFrame(all_summaries).to_csv('or_extended_summary.csv', index=False)
    print("\nSaved: or_extended_summary.csv")
