"""
H-Copilot OR Evaluation Script
Compares the real optimizer (ESI-weighted BIP) against a First-Come-First-Served
baseline across 3 load scenarios (low / medium / high), using the platform's
actual seed data sources.

Run this from backend/ (same folder as optimizer.py, database.py, models.py).
"""

import time
import pandas as pd
import pulp

from optimizer import run_optimizer, acuity_weight, parse_wards, covers_ward

# ---------------------------------------------------------------------------
# 1. FCFS baseline — same hard constraints (ward matching, 1 bed/patient, one
#    RN+PN+doctor per patient), but assigns in arrival order with NO acuity
#    weighting. This isolates priority-awareness as the one variable that
#    differs from the real optimizer.
# ---------------------------------------------------------------------------
def run_fcfs(patients_df, beds_df, nurses_df, doctors_df, shift, group, date):
    nurses_df = nurses_df.copy()
    doctors_df = doctors_df.copy()
    nurses_df['ward_list'] = nurses_df['ward'].apply(parse_wards)
    doctors_df['ward_list'] = doctors_df['ward'].apply(parse_wards)

    avail_beds = beds_df[beds_df['bed_status'] == 'Available'].reset_index(drop=True)
    on_duty_rn = nurses_df[(nurses_df['role'] == 'RN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)].reset_index(drop=True)
    on_duty_pn = nurses_df[(nurses_df['role'] == 'PN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)].reset_index(drop=True)
    on_duty_doc = doctors_df[(doctors_df['shift'] == shift) & (doctors_df['work_days'] == group)].reset_index(drop=True)
    patients = patients_df.reset_index(drop=True)  # kept in ORIGINAL (arrival) order — no acuity sort

    # Only BEDS are exclusive (one patient each), matching the real optimizer:
    # staff (RN/PN/doctor) have no per-person patient cap in the actual system,
    # so they are NOT tracked as "used up" here either — fair, matched comparison.
    used_beds = set()
    assignments, waiting = [], []

    for i, patient in patients.iterrows():
        assigned = False
        for j, bed in avail_beds.iterrows():
            if j in used_beds:
                continue
            rn_match = next((n for n, nrow in on_duty_rn.iterrows() if covers_ward(nrow['ward_list'], bed['ward_id'])), None)
            pn_match = next((n for n, nrow in on_duty_pn.iterrows() if covers_ward(nrow['ward_list'], bed['ward_id'])), None)
            doc_match = next((d for d, drow in on_duty_doc.iterrows() if covers_ward(drow['ward_list'], bed['ward_id'])), None)
            if rn_match is not None and pn_match is not None and doc_match is not None:
                used_beds.add(j)
                assignments.append({
                    'stay_id': int(patient['stay_id']), 'acuity': int(patient['acuity']),
                    'chiefcomplaint': patient['chiefcomplaint'], 'bed_number': bed['bed_number'],
                    'ward_id': int(bed['ward_id']),
                    'rn_id': int(on_duty_rn.loc[rn_match, 'nurse_id']),
                    'pn_id': int(on_duty_pn.loc[pn_match, 'nurse_id']),
                    'doctor_id': int(on_duty_doc.loc[doc_match, 'doctor_id']),
                    'shift': shift, 'date': date
                })
                assigned = True
                break
        if not assigned:
            waiting.append({'stay_id': int(patient['stay_id']), 'acuity': int(patient['acuity']),
                             'chiefcomplaint': patient['chiefcomplaint']})

    return pd.DataFrame(assignments), pd.DataFrame(waiting)


# ---------------------------------------------------------------------------
# 2. Shared post-hoc objective (ESI-weighted unassigned sum) — computed the
#    SAME way for both methods so they're compared on identical footing.
# ---------------------------------------------------------------------------
def compute_objective(all_patients_df, assigned_stay_ids):
    unassigned = all_patients_df[~all_patients_df['stay_id'].isin(assigned_stay_ids)]
    return sum(acuity_weight.get(int(a), 1) for a in unassigned['acuity'])


def priority_compliance(all_patients_df, assigned_stay_ids):
    """% of cases with NO priority inversion: no unassigned patient has a
    LOWER (more urgent) acuity number than any assigned patient."""
    assigned = all_patients_df[all_patients_df['stay_id'].isin(assigned_stay_ids)]
    unassigned = all_patients_df[~all_patients_df['stay_id'].isin(assigned_stay_ids)]
    if unassigned.empty or assigned.empty:
        return 100.0
    worst_assigned_acuity = assigned['acuity'].max()  # higher number = less urgent
    best_unassigned_acuity = unassigned['acuity'].min()  # lower number = more urgent
    inversions = (unassigned['acuity'] < worst_assigned_acuity).sum()
    return round(100 * (1 - inversions / len(unassigned)), 1)


def esi_breakdown(all_patients_df, assigned_stay_ids):
    """For each ESI level, how many patients of that severity were assigned vs left waiting."""
    rows = []
    for esi in sorted(all_patients_df['acuity'].unique()):
        subset = all_patients_df[all_patients_df['acuity'] == esi]
        n_total = len(subset)
        n_assigned = subset['stay_id'].isin(assigned_stay_ids).sum()
        rows.append(f"ESI{esi}: {n_assigned}/{n_total}")
    return ' | '.join(rows)


def ward_match_compliance(assignments_df, beds_df, nurses_df, doctors_df):
    if assignments_df.empty:
        return 100.0
    nurses_df = nurses_df.copy(); doctors_df = doctors_df.copy()
    nurses_df['ward_list'] = nurses_df['ward'].apply(parse_wards)
    doctors_df['ward_list'] = doctors_df['ward'].apply(parse_wards)
    correct = 0
    for _, row in assignments_df.iterrows():
        rn = nurses_df[nurses_df['nurse_id'] == row['rn_id']]
        doc = doctors_df[doctors_df['doctor_id'] == row['doctor_id']]
        ward_ok = (not rn.empty and covers_ward(rn.iloc[0]['ward_list'], row['ward_id'])) and \
                  (not doc.empty and covers_ward(doc.iloc[0]['ward_list'], row['ward_id']))
        correct += int(ward_ok)
    return round(100 * correct / len(assignments_df), 1)


# ---------------------------------------------------------------------------
# 3. Load scenarios — same acuity proportions as seed.py (2:12:19:2:0),
#    scaled to 3 volumes: low (below bed capacity), medium (~= capacity),
#    high (above capacity, forces waiting list)
# ---------------------------------------------------------------------------
SCENARIOS = {
    'Low load (15 patients)':    {1: 1, 2: 5,  3: 8,  4: 1, 5: 0},
    'Medium load (25 patients)': {1: 2, 2: 12, 3: 9,  4: 2, 5: 0},
    'High load (40 patients)':   {1: 3, 2: 17, 3: 17, 4: 3, 5: 0},
}

def build_patient_batch(triage_df, acuity_counts, seed=42):
    triage_df = triage_df.dropna(subset=['acuity']).copy()
    triage_df['acuity'] = triage_df['acuity'].astype(int)
    sampled = []
    for level, count in acuity_counts.items():
        if count == 0:
            continue
        pool = triage_df[triage_df['acuity'] == level]
        n = min(count, len(pool))
        sampled.append(pool.sample(n=n, random_state=seed))
    batch = pd.concat(sampled).reset_index(drop=True)
    # Shuffle to simulate realistic mixed-severity arrival order (NOT grouped by
    # ESI level) -- this matters because FCFS processes patients in the order
    # given, so a batch already sorted by severity would make FCFS look
    # identical to a priority-aware method by pure coincidence.
    return batch.sample(frac=1, random_state=seed).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. Run everything
# ---------------------------------------------------------------------------
def evaluate(beds_df, nurses_df, doctors_df, triage_df, shift='morning', group=1, date='2026-09-17'):
    results = []
    for name, acuity_counts in SCENARIOS.items():
        patients_df = build_patient_batch(triage_df, acuity_counts)

        for method_name, method_fn in [('OR (ESI-weighted)', run_optimizer), ('FCFS baseline', run_fcfs)]:
            fresh_beds = beds_df.copy()
            fresh_beds['bed_status'] = 'Available'

            start = time.time()
            assignments_df, waiting_df = method_fn(patients_df, fresh_beds, nurses_df, doctors_df, shift, group, date)
            solve_time = time.time() - start

            assigned_ids = assignments_df['stay_id'].tolist() if not assignments_df.empty else []
            n_total = len(patients_df)
            n_assigned = len(assigned_ids)

            results.append({
                'Scenario': name,
                'Method': method_name,
                'Assignment Rate %': round(100 * n_assigned / n_total, 1),
                'Priority Compliance %': priority_compliance(patients_df, assigned_ids),
                'ESI Breakdown (assigned/total)': esi_breakdown(patients_df, assigned_ids),
                'Ward Match Compliance %': ward_match_compliance(assignments_df, fresh_beds, nurses_df, doctors_df),
                'Objective Value': compute_objective(patients_df, assigned_ids),
                'Solve Time (s)': round(solve_time, 3),
            })

    return pd.DataFrame(results)


if __name__ == '__main__':
    beds_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\EDbeds.csv")
    nurses_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\Nurses.csv")
    nurses_df = nurses_df.rename(columns={'group': 'grp'})
    nurses_df['nurse_id'] = range(1, len(nurses_df) + 1)
    doctors_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\Doctors.csv")
    doctors_df = doctors_df.rename(columns={'intern_or_not': 'is_intern', 'work_days': 'work_days'})
    doctors_df['is_intern'] = doctors_df['is_intern'] == 'intern'
    doctors_df['doctor_id'] = range(1, len(doctors_df) + 1)
    triage_df = pd.read_excel(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\triage.xlsx")

    results_df = evaluate(beds_df, nurses_df, doctors_df, triage_df)
    print(results_df.to_string(index=False))
    results_df.to_csv('or_evaluation_results.csv', index=False)
    print('\nSaved to or_evaluation_results.csv')
