import os
DATA_DIR = os.getenv("HCOPILOT_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw"))  # folder with the raw csv files
"""
H-Copilot OR evaluation with 30-minute rounds.

Same three methods as simulate_or_aging.py (FCFS, OR without aging, OR + Aging),
but the simulation clock ticks every 30 minutes instead of every 4 hours, so the
per-acuity wait limits (0/10/30/60/120 min) can actually be resolved.

Self-contained: it does NOT import from simulate_or.py or simulate_or_aging.py,
so your existing scripts and their results stay untouched.

LOAD SWEEP VERSION: repeats the same simulation at several arrival rates
(LOAD_FACTORS, as a fraction of the current rate) to show how the results change
as the ED goes from lightly loaded to overloaded. LOAD_FACTORS = [1.00] reproduces
simulate_or_aging_30min.py exactly (same trials, same numbers).

Put this file in backend/ (next to optimizer.py and evaluate_or.py) and run:
    python simulate_or_aging_30min_loadsweep.py
Set N_TRIALS = 3 first to time it, then raise it (e.g. 100).
Writes NEW files only (or_30min_loadsweep_raw.csv, or_30min_loadsweep_summary.csv);
your earlier result files are not touched.
"""

import numpy as np
import pandas as pd
import pulp
from tqdm import tqdm

from optimizer import acuity_weight, max_wait_minutes, parse_wards, covers_ward, run_optimizer
from evaluate_or import run_fcfs

N_TRIALS = 100                       # PER LOAD LEVEL. Test with 3 first, then raise (e.g. 100 or 200)
LOAD_FACTORS = [0.70, 0.85, 1.00]    # fraction of the current arrival rate; 1.00 = the run you already did
MINUTES_PER_ROUND = 30
HOURS_PER_ROUND = MINUTES_PER_ROUND / 60          # 0.5
ROUNDS_PER_4H = int(240 / MINUTES_PER_ROUND)      # 8
N_ROUNDS = 48                      # 24 simulated hours (same horizon as 6 x 4h)
ARRIVALS_PER_4H = {1: 1, 2: 5, 3: 7, 4: 1, 5: 0}  # same mean load as before (~14 per 4h)
LOS_MIN_ROUNDS, LOS_MAX_ROUNDS = 8, 24            # 4-12 hours, mean 8h (same as before)
AGING_RATE_PER_HOUR = 3.75         # same rate as the deployed optimizer.py

METHOD_NOAGING = 'OR without aging (ESI weights only)'
METHOD_AGING = 'OR + Aging (proposed, NOT deployed)'


# ---------------------------------------------------------------------------
# Arrivals: real triage records, sampled per acuity level.
# seed * 1000 + round_num never collides between trials (round_num <= 48).
# ---------------------------------------------------------------------------
def build_round_arrivals(triage_df, acuity_counts, round_num, seed):
    sampled = []
    for level, count in acuity_counts.items():
        if count == 0:
            continue
        pool = triage_df[triage_df['acuity'] == level]
        n = min(count, len(pool))
        sampled.append(pool.sample(n=n, random_state=seed * 1000 + round_num))
    batch = pd.concat(sampled).reset_index(drop=True)
    batch['stay_id'] = batch['stay_id'].astype(int) * 1000 + round_num
    return batch.sample(frac=1, random_state=seed * 1000 + round_num).reset_index(drop=True)


# ---------------------------------------------------------------------------
# OR + Aging: same structure as the real optimizer; the objective weight adds a
# threshold-gated aging bonus based on rounds already waited.
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

    # Effective weight = base ESI weight + threshold-gated aging bonus (same
    # formula as optimizer.py). Rounds waited -> minutes via MINUTES_PER_ROUND.
    def effective_weight(patient):
        acuity = int(patient['acuity'])
        base = acuity_weight.get(acuity, 1)
        rounds_waited = wait_counters.get(str(int(patient['stay_id'])), 0)
        minutes_waited = rounds_waited * MINUTES_PER_ROUND
        threshold_min = max_wait_minutes.get(acuity, 60)
        if minutes_waited <= threshold_min:
            return base
        overshoot_hours = (minutes_waited - threshold_min) / 60
        return base + overshoot_hours * AGING_RATE_PER_HOUR

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
# One simulation run (24 h in 30-minute rounds) for one method and one seed.
# ---------------------------------------------------------------------------
def run_simulation(beds_df, nurses_df, doctors_df, triage_df, method_name, method_fn,
                   use_aging=False, shift='morning', group=1, date='2026-09-17', seed=0, load_factor=1.0):
    rng = np.random.default_rng(seed)          # used only for length of stay
    all_beds = beds_df.copy()
    all_beds['bed_status'] = 'Available'
    occupied = {}        # bed_number -> (stay_id, rounds_left, total_los)
    bed_staff = {}       # bed_number -> {(role, id)} tied up with that bed
    waiting_pool = pd.DataFrame()
    wait_counters = {}   # stay_id (str) -> rounds waited so far
    completed_los = []
    starved = {}         # stay_id -> acuity; each patient counted once
    waits_at_bed = {'crit': [], 'esi3': [], 'low': []}   # minutes waited when bedded
    round_log = []
    n_arrivals = 0

    total_on_duty_staff = (
        len(nurses_df[(nurses_df['role'] == 'RN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)]) +
        len(nurses_df[(nurses_df['role'] == 'PN') & (nurses_df['shift'] == shift) & (nurses_df['grp'] == group)]) +
        len(doctors_df[(doctors_df['shift'] == shift) & (doctors_df['work_days'] == group)])
    )

    def wait_group(acuity):
        return 'crit' if acuity <= 2 else ('esi3' if acuity == 3 else 'low')

    for round_num in range(1, N_ROUNDS + 1):
        # --- discharges ---
        for bed_num, (stay_id, rounds_left, total_los) in list(occupied.items()):
            rounds_left -= 1
            if rounds_left <= 0:
                completed_los.append(total_los)
                del occupied[bed_num]
                bed_staff.pop(bed_num, None)
            else:
                occupied[bed_num] = (stay_id, rounds_left, total_los)

        current_beds = all_beds.copy()
        current_beds['bed_status'] = current_beds['bed_number'].apply(
            lambda b: 'Available' if (b not in occupied) else 'Occupied')

        # --- arrivals: Poisson counts, same mean load as the 4-hour version.
        # Seeded by (trial, round) only, so all 3 methods see identical arrivals. ---
        round_rng = np.random.default_rng(seed * 1000 + round_num)
        counts = {lvl: int(round_rng.poisson(n * load_factor / ROUNDS_PER_4H)) for lvl, n in ARRIVALS_PER_4H.items()}
        if sum(counts.values()) > 0:
            new_arrivals = build_round_arrivals(triage_df, counts, round_num, seed)
        else:
            new_arrivals = pd.DataFrame(columns=triage_df.columns)
        for sid in new_arrivals['stay_id']:
            wait_counters[str(int(sid))] = 0
        n_arrivals += len(new_arrivals)

        if waiting_pool.empty:
            pool = new_arrivals
        elif new_arrivals.empty:
            pool = waiting_pool
        else:
            pool = pd.concat([waiting_pool, new_arrivals], ignore_index=True)

        # --- run the assignment method on the pool ---
        if pool.empty:
            assignments_df, waiting_df = pd.DataFrame(), pd.DataFrame()
        elif use_aging:
            assignments_df, waiting_df = method_fn(pool, current_beds, nurses_df, doctors_df, shift, group, date, wait_counters)
        else:
            assignments_df, waiting_df = method_fn(pool, current_beds, nurses_df, doctors_df, shift, group, date)

        assigned_ids = assignments_df['stay_id'].astype(int).astype(str).tolist() if not assignments_df.empty else []
        acuity_of = {str(int(s)): int(a) for s, a in zip(pool['stay_id'], pool['acuity'])} if not pool.empty else {}

        for _, row in assignments_df.iterrows():
            sid = str(int(row['stay_id']))
            los = int(rng.integers(LOS_MIN_ROUNDS, LOS_MAX_ROUNDS + 1))
            occupied[row['bed_number']] = (sid, los, los)
            bed_staff[row['bed_number']] = {(k, int(row[k])) for k in ('rn_id', 'pn_id', 'doctor_id')
                                            if pd.notna(row.get(k))}
            rounds_waited = wait_counters.pop(sid, 0)
            waits_at_bed[wait_group(acuity_of.get(sid, 5))].append(rounds_waited * MINUTES_PER_ROUND)

        # --- starvation: flagged once per patient, against THEIR OWN acuity threshold ---
        still_waiting = pool[~pool['stay_id'].astype(int).astype(str).isin(assigned_ids)].copy() if not pool.empty else pd.DataFrame()
        for _, prow in still_waiting.iterrows():
            sid = str(int(prow['stay_id']))
            acuity = int(prow['acuity'])
            wait_counters[sid] = wait_counters.get(sid, 0) + 1
            minutes_waited = wait_counters[sid] * MINUTES_PER_ROUND
            if minutes_waited > max_wait_minutes.get(acuity, 60) and sid not in starved:
                starved[sid] = acuity
        waiting_pool = still_waiting

        # --- staff utilization: staff currently tied up with admitted patients ---
        staff_in_use = set()
        for s in bed_staff.values():
            staff_in_use.update(s)
        staff_util = round(100 * len(staff_in_use) / total_on_duty_staff, 1) if total_on_duty_staff else 0

        round_log.append({
            'Round': round_num,
            'Bed Utilization %': round(100 * len(occupied) / len(all_beds), 1),
            'Staff Utilization %': staff_util,
            'Backlog (hrs)': sum(wait_counters.values()) * HOURS_PER_ROUND,
            'Max Wait (hrs)': (max(wait_counters.values()) if wait_counters else 0) * HOURS_PER_ROUND,
            'Still Waiting': len(waiting_pool),
        })

    log = pd.DataFrame(round_log)

    # Waits that ALSO include patients still unbedded at the end (their wait so far).
    # Without this, a policy that never beds its low-acuity patients looks like it has
    # short waits, because the patients it never bedded are simply missing from the mean.
    all_waits = {k: list(v) for k, v in waits_at_bed.items()}
    for _, prow in waiting_pool.iterrows():
        sid = str(int(prow['stay_id']))
        all_waits[wait_group(int(prow['acuity']))].append(wait_counters.get(sid, 0) * MINUTES_PER_ROUND)

    def mean_or_nan(v):
        return round(float(np.mean(v)), 1) if v else float('nan')

    summary = {
        'Method': method_name,
        'Load factor': load_factor,
        'Arrivals (24h)': n_arrivals,
        'Starved Patients Total': len(starved),
        'Starved Patients ESI1-2': sum(1 for a in starved.values() if a <= 2),
        'Starved Patients ESI3': sum(1 for a in starved.values() if a == 3),
        'Starved Patients ESI4-5': sum(1 for a in starved.values() if a >= 4),
        'Mean Wait ESI1-2 (min)': mean_or_nan(waits_at_bed['crit']),
        'Mean Wait ESI3 (min)': mean_or_nan(waits_at_bed['esi3']),
        'Mean Wait ESI4-5 (min)': mean_or_nan(waits_at_bed['low']),
        'Wait incl. unbedded ESI1-2 (min)': mean_or_nan(all_waits['crit']),
        'Wait incl. unbedded ESI3 (min)': mean_or_nan(all_waits['esi3']),
        'Wait incl. unbedded ESI4-5 (min)': mean_or_nan(all_waits['low']),
        'Patients ESI4-5 (bedded + unbedded)': len(all_waits['low']),
        'Critical patients ESI1-2 (bedded + unbedded)': len(all_waits['crit']),
        'Max Wait ESI1-2 (min)': round(float(max(all_waits['crit'])), 1) if all_waits['crit'] else float('nan'),
        'Bedded Patients': sum(len(v) for v in waits_at_bed.values()),
        'Unbedded at End': int(log['Still Waiting'].iloc[-1]),
        'Mean Backlog (hrs)': round(log['Backlog (hrs)'].mean(), 1),
        'Final Max Wait (hrs)': float(log['Max Wait (hrs)'].iloc[-1]),
        'Final Bed Utilization %': float(log['Bed Utilization %'].iloc[-1]),
        'Mean Bed Utilization %': round(float(log['Bed Utilization %'].mean()), 1),
        'Mean Staff Utilization % (2nd half)': round(float(log['Staff Utilization %'].iloc[N_ROUNDS // 2:].mean()), 1),
    }
    return log, summary


if __name__ == '__main__':
    beds_df = pd.read_csv(os.path.join(DATA_DIR, "EDbeds.csv"))
    nurses_df = pd.read_csv(os.path.join(DATA_DIR, "Nurses.csv"))
    nurses_df = nurses_df.rename(columns={'group': 'grp'})
    nurses_df['nurse_id'] = range(1, len(nurses_df) + 1)
    doctors_df = pd.read_csv(os.path.join(DATA_DIR, "Doctors.csv"))
    doctors_df = doctors_df.rename(columns={'intern_or_not': 'is_intern'})
    doctors_df['is_intern'] = doctors_df['is_intern'] == 'intern'
    doctors_df['doctor_id'] = range(1, len(doctors_df) + 1)
    triage_df = pd.read_csv(os.path.join(DATA_DIR, "ED_triage.csv"))
    triage_df = triage_df.rename(columns={'triage_code': 'stay_id', 'TriageGrade': 'acuity', 'ChiefComplaint': 'chiefcomplaint'})
    triage_df = triage_df.dropna(subset=['acuity']).copy()
    triage_df['acuity'] = triage_df['acuity'].astype(int)

    METHODS = [
        ('FCFS baseline', False, run_fcfs),
        (METHOD_NOAGING, False, run_optimizer),
        (METHOD_AGING, True, run_optimizer_aging),
    ]

    n_beds = len(beds_df)
    mean_los_hours = (LOS_MIN_ROUNDS + LOS_MAX_ROUNDS) / 2 * HOURS_PER_ROUND
    bed_capacity_per_day = n_beds * 24 / mean_los_hours     # admissions per day if every bed is always full

    all_summaries = []
    with tqdm(total=len(LOAD_FACTORS) * N_TRIALS, desc="Simulating (load level x trial)") as bar:
        for load in LOAD_FACTORS:
            for trial in range(N_TRIALS):
                for method_name, use_aging, method_fn in METHODS:
                    _, summary = run_simulation(beds_df, nurses_df, doctors_df, triage_df, method_name,
                                                method_fn, use_aging=use_aging, seed=trial, load_factor=load)
                    summary['trial'] = trial
                    all_summaries.append(summary)
                bar.update(1)

    results_df = pd.DataFrame(all_summaries)
    # share of critical patients (ESI1-2) who were bedded within THEIR OWN acuity limit; makes loads comparable
    results_df['Critical within own limit (%)'] = 100 * (1 - results_df['Starved Patients ESI1-2'] /
                                                       results_df['Critical patients ESI1-2 (bedded + unbedded)'].replace(0, np.nan))
    results_df.to_csv('or_30min_loadsweep_raw.csv', index=False)

    key_cols = ['Arrivals (24h)', 'Critical patients ESI1-2 (bedded + unbedded)',
                'Starved Patients ESI1-2', 'Critical within own limit (%)',
                'Mean Wait ESI1-2 (min)', 'Wait incl. unbedded ESI1-2 (min)', 'Max Wait ESI1-2 (min)',
                'Starved Patients ESI3', 'Starved Patients ESI4-5',
                'Wait incl. unbedded ESI3 (min)', 'Wait incl. unbedded ESI4-5 (min)',
                'Mean Backlog (hrs)', 'Final Max Wait (hrs)', 'Unbedded at End',
                'Mean Bed Utilization %']
    mean_df = results_df.groupby(['Load factor', 'Method'])[key_cols].mean().round(2)
    zero_pct = (results_df.assign(z=results_df['Starved Patients ESI1-2'] == 0)
                .groupby(['Load factor', 'Method'])['z'].mean().mul(100).round(1))
    mean_df['Trials with zero critical starved (%)'] = zero_pct
    mean_df.to_csv('or_30min_loadsweep_summary.csv')

    for load in LOAD_FACTORS:
        arrivals = results_df.loc[results_df['Load factor'] == load, 'Arrivals (24h)'].mean()
        print(f"\n=== LOAD {load:.0%} of the current arrival rate: {arrivals:.0f} arrivals per 24 h = "
              f"{arrivals / bed_capacity_per_day:.2f} x bed capacity ({bed_capacity_per_day:.0f} admissions per day) "
              f"| mean over {N_TRIALS} trials ===")
        print(mean_df.xs(load, level='Load factor').T.to_string())

    print("\n=== PAIRED COMPARISONS PER LOAD (same arrivals in each trial for all 3 methods) ===")
    for load in LOAD_FACTORS:
        sub = results_df[results_df['Load factor'] == load]
        piv = lambda col: sub.pivot(index='trial', columns='Method', values=col)
        w = piv('Wait incl. unbedded ESI1-2 (min)')
        ok = w['FCFS baseline'].notna() & w[METHOD_NOAGING].notna()
        d = (w[METHOD_NOAGING] - w['FCFS baseline'])[ok]
        c = piv('Starved Patients ESI1-2')
        b = piv('Mean Backlog (hrs)')
        e3 = piv('Starved Patients ESI3')
        low = piv('Wait incl. unbedded ESI4-5 (min)')
        okl = low[METHOD_AGING].notna() & low[METHOD_NOAGING].notna()
        print(f"Load {load:.0%}  OR vs FCFS: critical wait lower in {(d < 0).sum()}, tied in {(d == 0).sum()}, "
              f"higher in {(d > 0).sum()} of {int(ok.sum())} trials (mean difference {d.mean():+.1f} min); "
              f"critical starved lower in {(c[METHOD_NOAGING] < c['FCFS baseline']).sum()} of {len(c)}")
        print(f"          Aging vs no aging: backlog lower in {(b[METHOD_AGING] < b[METHOD_NOAGING]).sum()} of {len(b)} | "
              f"ESI4-5 wait lower in {(low[METHOD_AGING] < low[METHOD_NOAGING])[okl].sum()} of {int(okl.sum())} | "
              f"ESI3 starved higher in {(e3[METHOD_AGING] > e3[METHOD_NOAGING]).sum()} of {len(e3)} | "
              f"critical starved higher in {(c[METHOD_AGING] > c[METHOD_NOAGING]).sum()} of {len(c)}")
    print("\nSaved: or_30min_loadsweep_raw.csv, or_30min_loadsweep_summary.csv")
