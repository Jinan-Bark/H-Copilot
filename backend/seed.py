import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import Ward, Bed, Nurse, Doctor, Patient, Assignment

def seed_data():
    db = SessionLocal()
    try:
        # ── Clear existing data (order matters due to foreign keys) ──
        db.query(Assignment).delete()
        db.query(Patient).delete()
        db.query(Bed).delete()
        db.query(Nurse).delete()
        db.query(Doctor).delete()
        db.query(Ward).delete()
        db.commit()
        print("✅ Cleared existing data")

        # ── Seed Wards ─────────────────────────────────────────
        # ── Seed Wards ─────────────────────────────────────────────
        wards = [
            Ward(ward_id=1, ward_type="general", capacity=3),
            Ward(ward_id=2, ward_type="general", capacity=11),
            Ward(ward_id=3, ward_type="general", capacity=11),
        ]
        db.add_all(wards)
        db.commit()
        db.flush()
        print(f"✅ Seeded {len(wards)} wards")

        # ── Seed Beds ──────────────────────────────────────────
        beds_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\EDbeds.csv")
        for _, row in beds_df.iterrows():
            bed = Bed(
                bed_number = str(row['bed_number']),
                bed_status = row['bed_status'],
                ward_id    = int(row['ward_id'])
            )
            db.add(bed)
        db.commit()
        print(f"✅ Seeded {len(beds_df)} beds")

        # ── Seed Nurses ────────────────────────────────────────
        nurses_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\Nurses.csv")
        for _, row in nurses_df.iterrows():
            nurse = Nurse(
                ward  = str(row['ward']).replace('"', ''),
                role  = row['role'],
                shift = row['shift'],
                grp   = int(row['group'])
            )
            db.add(nurse)
        db.commit()
        print(f"✅ Seeded {len(nurses_df)} nurses")

        # ── Seed Doctors ───────────────────────────────────────
        doctors_df = pd.read_csv(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\Doctors.csv")
        for _, row in doctors_df.iterrows():
            doctor = Doctor(
                ward      = str(row['ward']).replace('"', ''),
                is_intern = row['intern_or_not'] == 'intern',
                shift     = row['shift'],
                work_days = int(row['work_days'])
            )
            db.add(doctor)
        db.commit()
        print(f"✅ Seeded {len(doctors_df)} doctors")

        # ── Seed Patients ──────────────────────────────────────
        triage_df = pd.read_excel(r"C:\Users\FuJiTsu\Desktop\hcopilot\backend\data\triage.xlsx")
        triage_df = triage_df.dropna(subset=['acuity'])
        triage_df['acuity'] = triage_df['acuity'].astype(int)

        # Sample realistic distribution
        acuity_sample = {1: 2, 2: 12, 3: 19, 4: 2, 5: 0}
        sampled = []
        for acuity_level, count in acuity_sample.items():
            if count == 0:
                continue
            pool = triage_df[triage_df['acuity'] == acuity_level]
            n = min(count, len(pool))
            sampled.append(pool.sample(n=n, random_state=42))

        patients_df = pd.concat(sampled).reset_index(drop=True)

        for _, row in patients_df.iterrows():
            patient = Patient(
                stay_id        = int(row['stay_id']),
                temperature    = float(row['temperature']) if pd.notna(row['temperature']) else None,
                heartrate      = int(row['heartrate']) if pd.notna(row['heartrate']) else None,
                resprate       = int(row['resprate']) if pd.notna(row['resprate']) else None,
                o2sat          = float(row['o2sat']) if pd.notna(row['o2sat']) else None,
                sbp            = int(row['sbp']) if pd.notna(row['sbp']) else None,
                dbp            = int(row['dbp']) if pd.notna(row['dbp']) else None,
                pain           = int(float(row['pain'])) if pd.notna(row['pain']) and str(row['pain']).replace('.','').isdigit() else None,
                acuity         = int(row['acuity']),
                chiefcomplaint = str(row['chiefcomplaint']) if pd.notna(row['chiefcomplaint']) else None,
                status         = "waiting"
            )
            db.add(patient)
        db.commit()
        print(f"✅ Seeded {len(patients_df)} patients")
        print("\n🎉 Database seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()