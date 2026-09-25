"""
H-Copilot OR Multi-Round Simulation
Simulates several waves of patient arrivals and discharges over time, to test:
  1. Whether waiting patients ever get "stuck" for many rounds (starvation)
  2. Bed utilization over time
  3. Whether auto-re-optimization on discharge actually helps waiting patients

This is a SIMULATION, not a live-platform test: it reuses your real
run_optimizer / run_fcfs logic, but "time passing" is simulated in code
(no real database, no waiting in real time).

Run this from backend/ (same folder as optimizer.py).
"""

import numpy as np
import pandas as pd

from optimizer import run_optimizer, acuity_weight
from evaluate_or import run_fcfs, compute_objective

N_ROUNDS = 6
NEW_ARRIVALS_PER_ROUND = {1: 1, 2: 5, 3: 7, 4: 1, 5: 0}  # per-round acuity mix (~14/round: genuinely busy, but close to the ED's ~12.5/round sustainable throughput at 25 beds and ~8hr avg stay -- not permanently double it)
STARVATION_THRESHOLD = 1  # rounds waited before flagging as a starvation case


def build_round_arrivals(triage_df, acuity_counts, round_num, seed=42):
    triage_df = triage_df.dropna(subset=['acuity']).copy()
    triage_df['acuity'] = triage_df['acuity'].astype(int)
    sampled = []
    for level, count in acuity_counts.items():
        if count == 0:
            continue
        pool = triage_df[triage_df['acuity'] == level]
        n = min(count, len(pool))
        sampled.append(pool.sample(n=n, random_state=seed + round_num))
    batch = pd.concat(sampled).reset_index(drop=True)
    # Keep stay_id numeric (optimizer.py casts it with int()) while still unique
    # per round: original_id * 1000 + round_num
    batch['stay_id'] = batch['stay_id'].astype(int) * 1000 + round_num
    return batch.sample(frac=1, random_state=seed + round_num).reset_index(drop=True)


def run_simulation(beds_df, nurses_df, doctors_df, triage_df, method_fn, method_name,
                    shift='morning', group=1, date='2026-09-17', seed=42):
    rng = np.random.default_rng(seed)

    all_beds = beds_df.copy()
    all_beds['bed_status'] = 'Available'
    occupied = {}  # bed_number -> (stay_id, rounds_remaining_in_bed)
    waiting_pool = pd.DataFrame()  # patients not yet assigned, carried across rounds
    wait_counters = {}  # stay_id -> rounds waited so far

    round_log = []
    starvation_cases = []

    for round_num in range(1, N_ROUNDS + 1):
        # --- Discharge patients whose stay is over, freeing their beds ---
        newly_freed = []
        for bed_num, (stay_id, rounds_left) in list(occupied.items()):
            rounds_left -= 1
            if rounds_left <= 0:
                newly_freed.append(bed_num)
                del occupied[bed_num]
            else:
                occupied[bed_num] = (stay_id, rounds_left)

        current_beds = all_beds.copy()
        current_beds['bed_status'] = current_beds['bed_number'].apply(
            lambda b: 'Available' if (b not in occupied) else 'Occupied')

        # --- New arrivals this round, added to whoever's still waiting ---
        new_arrivals = build_round_arrivals(triage_df, NEW_ARRIVALS_PER_ROUND, round_num, seed)
        for sid in new_arrivals['stay_id']:
            wait_counters[sid] = 0
        pool = pd.concat([waiting_pool, new_arrivals], ignore_index=True) if not waiting_pool.empty else new_arrivals

        # --- Run the assignment method on the combined pool ---
        assignments_df, waiting_df = method_fn(pool, current_beds, nurses_df, doctors_df, shift, group, date)

        assigned_ids = assignments_df['stay_id'].astype(str).tolist() if not assignments_df.empty else []

        # Assign a random length-of-stay (1-3 rounds) to each newly admitted patient
        for _, row in assignments_df.iterrows():
            los = rng.integers(1, 4)
            occupied[row['bed_number']] = (str(row['stay_id']), los)
            wait_counters.pop(str(row['stay_id']), None)

        # --- Update wait counters for anyone still waiting ---
        still_waiting = pool[~pool['stay_id'].astype(str).isin(assigned_ids)].copy()
        for sid in still_waiting['stay_id'].astype(str):
            wait_counters[sid] = wait_counters.get(sid, 0) + 1
            if wait_counters[sid] >= STARVATION_THRESHOLD:
                acuity = still_waiting[still_waiting['stay_id'].astype(str) == sid]['acuity'].values[0]
                starvation_cases.append({'stay_id': sid, 'acuity': int(acuity), 'rounds_waited': wait_counters[sid], 'round': round_num})

        waiting_pool = still_waiting

        occupied_count = sum(1 for b in current_beds['bed_number'] if b in occupied or b in newly_freed) 
        utilization = round(100 * len(occupied) / len(all_beds), 1)

        round_log.append({
            'Method': method_name, 'Round': round_num,
            'New Arrivals': len(new_arrivals), 'Still Waiting (end of round)': len(waiting_pool),
            'Bed Utilization %': utilization,
            'Max Rounds Waited (any patient)': max(wait_counters.values()) if wait_counters else 0,
        })

    return pd.DataFrame(round_log), pd.DataFrame(starvation_cases)


if __name__ == '__main__':
    beds_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\EDbeds.csv")
    nurses_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\Nurses.csv")
    nurses_df = nurses_df.rename(columns={'group': 'grp'})
    nurses_df['nurse_id'] = range(1, len(nurses_df) + 1)
    doctors_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\Doctors.csv")
    doctors_df = doctors_df.rename(columns={'intern_or_not': 'is_intern'})
    doctors_df['is_intern'] = doctors_df['is_intern'] == 'intern'
    doctors_df['doctor_id'] = range(1, len(doctors_df) + 1)
    triage_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\ED_triage.csv")
    triage_df = triage_df.rename(columns={'triage_code': 'stay_id', 'TriageGrade': 'acuity', 'ChiefComplaint': 'chiefcomplaint'})
    
    print("=== Running simulation: OR (ESI-weighted) ===")
    or_log, or_starvation = run_simulation(beds_df, nurses_df, doctors_df, triage_df, run_optimizer, 'OR')
    print(or_log.to_string(index=False))
    print(f"\nStarvation cases (waited >= {STARVATION_THRESHOLD} rounds): {len(or_starvation)}")
    if not or_starvation.empty:
        print(or_starvation.to_string(index=False))

    print("\n=== Running simulation: FCFS baseline ===")
    fcfs_log, fcfs_starvation = run_simulation(beds_df, nurses_df, doctors_df, triage_df, run_fcfs, 'FCFS')
    print(fcfs_log.to_string(index=False))
    print(f"\nStarvation cases (waited >= {STARVATION_THRESHOLD} rounds): {len(fcfs_starvation)}")
    if not fcfs_starvation.empty:
        print(fcfs_starvation.to_string(index=False))

    pd.concat([or_log, fcfs_log]).to_csv('or_simulation_results.csv', index=False)
    pd.concat([or_starvation, fcfs_starvation]).to_csv('or_starvation_cases.csv', index=False)
    print("\nSaved: or_simulation_results.csv, or_starvation_cases.csv")
