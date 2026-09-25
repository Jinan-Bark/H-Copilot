"""
H-Copilot OR: Dynamic Workload Balancing (TESTED, NOT deployed)

Adds a per-staff-member patient cap that automatically scales with how many
staff of that role are actually on duty:

    cap = ceil(number_of_patients_in_batch / number_of_staff_in_that_role)

This is deliberately dynamic rather than a fixed number (e.g. "max 4 patients"):
  - With only 1 PN on duty (the platform's current real staffing), the cap
    equals the full patient count -- i.e. no artificial restriction, since
    there is no alternative to redistribute to. Nothing breaks.
  - If more PNs/RNs are added to the roster later, the cap automatically
    tightens and real balancing begins, with no code changes required.

Run from backend/ (same folder as optimizer.py, evaluate_or.py, simulate_or.py).
"""

import math
import numpy as np
import pandas as pd
import pulp

from optimizer import acuity_weight, parse_wards, covers_ward
from evaluate_or import run_fcfs
from simulate_or import build_round_arrivals, N_ROUNDS, NEW_ARRIVALS_PER_ROUND, STARVATION_THRESHOLD, run_simulation


def compute_ward_aware_caps(staff_df, avail_beds):
    """For each staff member, cap = sum over their covered wards of
    ceil(beds_in_that_ward / number_of_staff_of_this_role_covering_that_ward).
    This ties the cap to REAL physical bed capacity per ward, instead of a
    single global number that ignores which staff actually cover which ward
    -- the naive global version could block patients in wards with few
    qualified staff, even while other wards had spare capacity."""
    beds_per_ward = avail_beds.groupby('ward_id').size().to_dict()
    caps = {}
    for idx, row in staff_df.iterrows():
        total_cap = 0
        for w in row['ward_list']:
            try:
                w_int = int(w)
            except ValueError:
                continue
            beds_here = beds_per_ward.get(w_int, 0)
            staff_here = sum(1 for _, srow in staff_df.iterrows() if str(w_int) in srow['ward_list'])
            if staff_here > 0 and beds_here > 0:
                total_cap += math.ceil(beds_here / staff_here)
        caps[idx] = max(total_cap, 1)
    return caps


def run_optimizer_balanced(patients_df, beds_df, nurses_df, doctors_df, shift, group, date, fairness_weight=0.01):
    """Same core assignment as the real optimizer, but adds a SECONDARY goal:
    minimize the largest workload any single RN/PN/doctor ends up with.

    This is deliberately a SOFT preference, not a hard cap: patient care is
    never blocked to keep things even (unlike a fixed per-person cap, which
    can leave real patients unassigned if a ward has few qualified staff).
    Given a choice between two equally good patient-priority outcomes, the
    solver picks the more evenly-spread one. If patients can be split evenly
    across staff, it will; if not, one staff member simply takes the one
    extra patient that can't be evenly divided -- exactly matching how a
    human charge nurse would actually do it."""
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

    model = pulp.LpProblem('ED_Assignment_Balanced', pulp.LpMinimize)
    x = pulp.LpVariable.dicts('bed', [(i, j) for i in P for j in B], cat='Binary')
    y_rn = pulp.LpVariable.dicts('rn', [(i, n) for i in P for n in RN], cat='Binary')
    y_pn = pulp.LpVariable.dicts('pn', [(i, n) for i in P for n in PN], cat='Binary')
    z = pulp.LpVariable.dicts('doc', [(i, d) for i in P for d in D], cat='Binary')

    # NEW: continuous variables representing "the busiest staff member's load"
    max_rn_load = pulp.LpVariable('max_rn_load', lowBound=0)
    max_pn_load = pulp.LpVariable('max_pn_load', lowBound=0)
    max_doc_load = pulp.LpVariable('max_doc_load', lowBound=0)

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

    # NEW: "busiest staff member" tracking -- each individual's load can never
    # exceed the max_*_load variable, which the objective tries to minimize
    for n in RN:
        model += pulp.lpSum(y_rn[i, n] for i in P) <= max_rn_load
    for n in PN:
        model += pulp.lpSum(y_pn[i, n] for i in P) <= max_pn_load
    for d in D:
        model += pulp.lpSum(z[i, d] for i in P) <= max_doc_load

    # Objective: PRIMARY = same ESI-weighted care priority as the real system
    #            SECONDARY (small weight) = keep the busiest staff member's
    #            load as low as possible -- never allowed to outweigh patient care
    model += (
        pulp.lpSum(
            acuity_weight.get(int(patients.loc[i, 'acuity']), 1) * (1 - pulp.lpSum(x[i, j] for j in B))
            for i in P
        )
        + fairness_weight * (max_rn_load + max_pn_load + max_doc_load)
    )
    # Hard time limit -- essential for real-time ED use. The minimax fairness
    # terms make this a much harder problem to solve to full optimality than
    # the base assignment problem; capping solve time means the system always
    # returns a good (if not perfectly optimal) answer quickly, rather than
    # potentially hanging.
    model.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=10))

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


def staff_spread(assignments_df, role_col):
    """How many DISTINCT staff members (of one role) were used, out of how many assignments."""
    if assignments_df.empty:
        return "0/0"
    counts = assignments_df[role_col].value_counts()
    return f"{len(counts)} distinct staff used | max patients on one staff member: {counts.max()}"


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

    print("=== Single-round comparison: does balancing spread the workload? ===")
    for name, fn in [('OR (current)', run_optimizer), ('OR + Dynamic Workload Balancing', run_optimizer_balanced)]:
        assignments_df, waiting_df = fn(triage_df.dropna(subset=['acuity']).astype({'acuity': int}).sample(20, random_state=1),
                                          beds_df, nurses_df, doctors_df, 'morning', 1, '2026-09-17')
        print(f"\n{name}:")
        print(f"  RN spread:  {staff_spread(assignments_df, 'rn_id')}")
        print(f"  PN spread:  {staff_spread(assignments_df, 'pn_id')}")
        print(f"  Doctor spread: {staff_spread(assignments_df, 'doctor_id')}")
        print(f"  Assigned: {len(assignments_df)} / 20")
