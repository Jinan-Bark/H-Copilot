from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd
from datetime import date
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from pydantic import BaseModel
from datetime import datetime, timezone
from ml.forecast import predict_slot, predict_week
from ml.patient_type import predict_patient_type
from database import get_db
from ml.forecast import retrain_model


from database import get_db, engine
from models import Base, Ward, Bed, Patient, Nurse, Doctor, Assignment
from optimizer import run_optimizer

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="H-Copilot API", version="1.0.0")

# Allow React frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health check ──────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "H-Copilot API is running"}

# ── Get all wards ─────────────────────────────────────────────
@app.get("/wards")
def get_wards(db: Session = Depends(get_db)):
    return db.query(Ward).all()

# ── Get all beds ──────────────────────────────────────────────
@app.get("/beds")
def get_beds(db: Session = Depends(get_db)):
    return db.query(Bed).all()

# ── Get available beds ────────────────────────────────────────
@app.get("/beds/available")
def get_available_beds(db: Session = Depends(get_db)):
    return db.query(Bed).filter(Bed.bed_status == "Available").all()

# ── Get all patients ──────────────────────────────────────────
@app.get("/patients")
def get_patients(db: Session = Depends(get_db)):
    return db.query(Patient).all()

# ── Get waiting patients ──────────────────────────────────────
@app.get("/patients/waiting")
def get_waiting_patients(db: Session = Depends(get_db)):
    return db.query(Patient).filter(Patient.status == "waiting").all()

class PatientCreate(BaseModel):
    acuity         : int
    chiefcomplaint : str
    temperature    : Optional[float] = None
    heartrate      : Optional[int]   = None
    resprate       : Optional[int]   = None
    o2sat          : Optional[float] = None
    sbp            : Optional[int]   = None
    dbp            : Optional[int]   = None
    pain           : Optional[int]   = None

@app.post("/patients")
def add_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    # Auto-generate stay_id from timestamp
    stay_id = int(datetime.now().strftime('%Y%m%d%H%M%S'))
    
    new_patient = Patient(
        stay_id        = stay_id,
        acuity         = patient.acuity,
        chiefcomplaint = patient.chiefcomplaint,
        temperature    = patient.temperature,
        heartrate      = patient.heartrate,
        resprate       = patient.resprate,
        o2sat          = patient.o2sat,
        sbp            = patient.sbp,
        dbp            = patient.dbp,
        pain           = patient.pain,
        status         = "waiting"
    )
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    return new_patient

# ── Get all assignments ───────────────────────────────────────
@app.get("/assignments")
def get_assignments(db: Session = Depends(get_db)):
    assignments = db.query(Assignment).all()
    result = []
    for a in assignments:
        patient = db.query(Patient).filter(Patient.patient_id == a.patient_id).first()
        # Only include active (admitted) patients
        if not patient or patient.status != 'admitted':
            continue
        bed    = db.query(Bed).filter(Bed.bed_id == a.bed_id).first()
        rn     = db.query(Nurse).filter(Nurse.nurse_id == a.rn_id).first()
        pn     = db.query(Nurse).filter(Nurse.nurse_id == a.pn_id).first()
        doctor = db.query(Doctor).filter(Doctor.doctor_id == a.doctor_id).first()
        result.append({
            "assignment_id" : a.assignment_id,
            "patient_id"    : a.patient_id,
            "stay_id"       : patient.stay_id,
            "acuity"        : patient.acuity,
            "chiefcomplaint": patient.chiefcomplaint,
            "bed_number"    : bed.bed_number if bed else None,
            "ward_id"       : bed.ward_id if bed else None,
            "rn_id"         : rn.nurse_id if rn else None,
            "pn_id"         : pn.nurse_id if pn else None,
            "doctor_id"     : doctor.doctor_id if doctor else None,
            "is_intern"     : doctor.is_intern if doctor else None,
            "shift"         : a.shift,
            "date"          : str(a.date),
            "assigned_at"   : str(a.assigned_at),
        })
    return result

# ── Get all nurses ────────────────────────────────────────────
@app.get("/nurses")
def get_nurses(show_inactive: bool = False, db: Session = Depends(get_db)):
    if show_inactive:
        return db.query(Nurse).all()
    return db.query(Nurse).filter(Nurse.is_active == True).all()

# ── Get all doctors ───────────────────────────────────────────
@app.get("/doctors")
def get_doctors(show_inactive: bool = False, db: Session = Depends(get_db)):
    if show_inactive:
        return db.query(Doctor).all()
    return db.query(Doctor).filter(Doctor.is_active == True).all()

# ── Discharge patient (free up bed) ──────────────────────────
@app.put("/patients/{patient_id}/discharge")
def discharge_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Get assignment to find the bed
    assignment = db.query(Assignment).filter(Assignment.patient_id == patient_id).first()
    freed_shift = None
    freed_date  = None

    if assignment:
        bed = db.query(Bed).filter(Bed.bed_id == assignment.bed_id).first()
        if bed:
            bed.bed_status = "Available"
        freed_shift = assignment.shift
        freed_date  = assignment.date

    patient.status         = "discharged"
    patient.discharge_time = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    # ── Auto re-optimize if there are waiting patients ────────
    waiting = db.query(Patient).filter(Patient.status == "waiting").all()
    if waiting and freed_shift and freed_date:
        assignments_df = pd.DataFrame()
        try:
            patients_df = pd.read_sql(
                db.query(Patient).filter(Patient.status == "waiting").statement,
                db.bind
            )
            beds_df    = pd.read_sql(db.query(Bed).statement, db.bind)
            nurses_df  = pd.read_sql(db.query(Nurse).filter(Nurse.is_active == True).statement, db.bind)
            doctors_df = pd.read_sql(db.query(Doctor).filter(Doctor.is_active == True).statement, db.bind)

            # Determine group from date
            group = 1 if freed_date.weekday() < 4 else 2

            assignments_df, _ = run_optimizer(
                patients_df, beds_df, nurses_df, doctors_df,
                shift=freed_shift,
                group=group,
                date=str(freed_date)
            )

            for _, row in assignments_df.iterrows():
                p   = db.query(Patient).filter(Patient.stay_id == row['stay_id']).first()
                bed = db.query(Bed).filter(Bed.bed_number == str(row['bed_number'])).first()
                if p and bed:
                    bed.bed_status = "Occupied"
                    p.status       = "admitted"
                    new_assignment = Assignment(
                        patient_id = p.patient_id,
                        bed_id     = bed.bed_id,
                        rn_id      = row['rn_id'],
                        pn_id      = row['pn_id'],
                        doctor_id  = row['doctor_id'],
                        shift      = freed_shift,
                        date       = freed_date
                    )
                    db.add(new_assignment)
            db.commit()

        except Exception as e:
            print(f"Auto re-optimize failed: {e}")

    newly_assigned = assignments_df['stay_id'].tolist() if len(waiting) > 0 and not assignments_df.empty else []

    return {
        "message"        : f"Patient {patient_id} discharged successfully",
        "reoptimized"    : len(waiting) > 0,
        "newly_assigned" : newly_assigned
    }

# ── Run optimizer ─────────────────────────────────────────────
@app.post("/optimize")
def optimize(shift: str, group: int, date_str: str, db: Session = Depends(get_db)):
    # Load data from database into DataFrames
    patients_df = pd.read_sql(
        db.query(Patient).filter(Patient.status == "waiting").statement, 
        db.bind
    )
    beds_df     = pd.read_sql(db.query(Bed).statement, db.bind)
    nurses_df   = pd.read_sql(db.query(Nurse).filter(Nurse.is_active == True).statement, db.bind)
    doctors_df  = pd.read_sql(db.query(Doctor).filter(Doctor.is_active == True).statement, db.bind)

    if patients_df.empty:
        raise HTTPException(status_code=400, detail="No waiting patients found")

    # Run optimizer
    assignments_df, waiting_df = run_optimizer(
        patients_df, beds_df, nurses_df, doctors_df,
        shift=shift, group=group, date=date_str
    )

    if assignments_df.empty:
        return {"assigned": 0, "waiting": len(waiting_df), "assignments": []}

    # Save assignments to database
    for _, row in assignments_df.iterrows():
        # Get patient_id from stay_id
        patient = db.query(Patient).filter(Patient.stay_id == row['stay_id']).first()
        bed     = db.query(Bed).filter(Bed.bed_number == str(row['bed_number'])).first()

        if patient and bed:
            # Update bed status
            bed.bed_status = "Occupied"
            # Update patient status
            patient.status = "admitted"
            # Create assignment record
            new_assignment = Assignment(
                patient_id  = patient.patient_id,
                bed_id      = bed.bed_id,
                rn_id       = row['rn_id'],
                pn_id       = row['pn_id'],
                doctor_id   = row['doctor_id'],
                shift       = shift,
                date        = date.fromisoformat(date_str)
            )
            db.add(new_assignment)

    db.commit()

    return {
        "assigned"   : len(assignments_df),
        "waiting"    : len(waiting_df),
        "assignments": assignments_df.to_dict(orient="records"),
        "waiting_list": waiting_df.to_dict(orient="records")
    }

class ManualAssignment(BaseModel):
    patient_id : int
    bed_id     : int
    rn_id      : int
    pn_id      : int
    doctor_id  : int
    shift      : str
    date_str   : str

@app.post("/assign-manual")
def manual_assign(data: ManualAssignment, db: Session = Depends(get_db)):
    # Validate patient is waiting
    patient = db.query(Patient).filter(Patient.patient_id == data.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.status != "waiting":
        raise HTTPException(status_code=400, detail="Patient is not waiting")

    # Validate bed is available
    bed = db.query(Bed).filter(Bed.bed_id == data.bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    if bed.bed_status != "Available":
        raise HTTPException(status_code=400, detail="Bed is not available")

    # Create assignment
    new_assignment = Assignment(
        patient_id = data.patient_id,
        bed_id     = data.bed_id,
        rn_id      = data.rn_id,
        pn_id      = data.pn_id,
        doctor_id  = data.doctor_id,
        shift      = data.shift,
        date       = date.fromisoformat(data.date_str)
    )
    db.add(new_assignment)

    # Update statuses
    bed.bed_status = "Occupied"
    patient.status = "admitted"
    db.commit()

    return {"message": "Patient manually assigned successfully"}

@app.get("/staff/workload")
def get_staff_workload(db: Session = Depends(get_db)):
    nurses  = db.query(Nurse).filter(Nurse.is_active == True).all()
    doctors = db.query(Doctor).filter(Doctor.is_active == True).all()

    nurse_workload = []
    for n in nurses:
        # Count active assignments for this nurse as RN or PN
        rn_count = db.query(Assignment).join(Patient).filter(
            Assignment.rn_id == n.nurse_id,
            Patient.status == 'admitted'
        ).count()
        pn_count = db.query(Assignment).join(Patient).filter(
            Assignment.pn_id == n.nurse_id,
            Patient.status == 'admitted'
        ).count()
        count = rn_count + pn_count
        nurse_workload.append({
            "nurse_id" : n.nurse_id,
            "ward"     : n.ward,
            "role"     : n.role,
            "shift"    : n.shift,
            "grp"      : n.grp,
            "patients" : count
        })

    doctor_workload = []
    for d in doctors:
        count = db.query(Assignment).join(Patient).filter(
            Assignment.doctor_id == d.doctor_id,
            Patient.status == 'admitted'
        ).count()
        doctor_workload.append({
            "doctor_id" : d.doctor_id,
            "ward"      : d.ward,
            "is_intern" : d.is_intern,
            "shift"     : d.shift,
            "work_days" : d.work_days,
            "patients"  : count
        })

    return {"nurses": nurse_workload, "doctors": doctor_workload}

class BedTransfer(BaseModel):
    new_bed_id: int

@app.put("/assignments/{assignment_id}/transfer-bed")
def transfer_bed(assignment_id: int, data: BedTransfer, db: Session = Depends(get_db)):
    # Get assignment
    assignment = db.query(Assignment).filter(
        Assignment.assignment_id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Validate new bed is available
    new_bed = db.query(Bed).filter(Bed.bed_id == data.new_bed_id).first()
    if not new_bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    if new_bed.bed_status != "Available":
        raise HTTPException(status_code=400, detail="Bed is not available")

    # Free old bed
    old_bed = db.query(Bed).filter(Bed.bed_id == assignment.bed_id).first()
    if old_bed:
        old_bed.bed_status = "Available"

    # Assign new bed
    new_bed.bed_status = "Occupied"
    assignment.bed_id  = data.new_bed_id

    db.commit()
    return {"message": "Patient transferred successfully"}

    # ── Staff Pydantic Models ─────────────────────────────────────
class NurseCreate(BaseModel):
    ward  : str
    role  : str
    shift : str
    grp   : int

class DoctorCreate(BaseModel):
    ward      : str
    is_intern : bool
    shift     : str
    work_days : int

# ── Add Nurse ─────────────────────────────────────────────────
@app.post("/nurses")
def add_nurse(nurse: NurseCreate, db: Session = Depends(get_db)):
    new_nurse = Nurse(
        ward  = nurse.ward,
        role  = nurse.role,
        shift = nurse.shift,
        grp   = nurse.grp,
        is_active = True
    )
    db.add(new_nurse)
    db.commit()
    db.refresh(new_nurse)
    return new_nurse

# ── Add Doctor ────────────────────────────────────────────────
@app.post("/doctors")
def add_doctor(doctor: DoctorCreate, db: Session = Depends(get_db)):
    new_doctor = Doctor(
        ward      = doctor.ward,
        is_intern = doctor.is_intern,
        shift     = doctor.shift,
        work_days = doctor.work_days,
        is_active = True
    )
    db.add(new_doctor)
    db.commit()
    db.refresh(new_doctor)
    return new_doctor

# ── Edit Nurse ────────────────────────────────────────────────
@app.put("/nurses/{nurse_id}")
def edit_nurse(nurse_id: int, nurse: NurseCreate, db: Session = Depends(get_db)):
    existing = db.query(Nurse).filter(Nurse.nurse_id == nurse_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Nurse not found")
    existing.ward  = nurse.ward
    existing.role  = nurse.role
    existing.shift = nurse.shift
    existing.grp   = nurse.grp
    db.commit()
    return existing

# ── Edit Doctor ───────────────────────────────────────────────
@app.put("/doctors/{doctor_id}")
def edit_doctor(doctor_id: int, doctor: DoctorCreate, db: Session = Depends(get_db)):
    existing = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Doctor not found")
    existing.ward      = doctor.ward
    existing.is_intern = doctor.is_intern
    existing.shift     = doctor.shift
    existing.work_days = doctor.work_days
    db.commit()
    return existing

# ── Deactivate Nurse ──────────────────────────────────────────
@app.put("/nurses/{nurse_id}/deactivate")
def deactivate_nurse(nurse_id: int, db: Session = Depends(get_db)):
    nurse = db.query(Nurse).filter(Nurse.nurse_id == nurse_id).first()
    if not nurse:
        raise HTTPException(status_code=404, detail="Nurse not found")
    nurse.is_active = False
    db.commit()
    return {"message": "Nurse deactivated"}

# ── Reactivate Nurse ──────────────────────────────────────────
@app.put("/nurses/{nurse_id}/reactivate")
def reactivate_nurse(nurse_id: int, db: Session = Depends(get_db)):
    nurse = db.query(Nurse).filter(Nurse.nurse_id == nurse_id).first()
    if not nurse:
        raise HTTPException(status_code=404, detail="Nurse not found")
    nurse.is_active = True
    db.commit()
    return {"message": "Nurse reactivated"}

# ── Deactivate Doctor ─────────────────────────────────────────
@app.put("/doctors/{doctor_id}/deactivate")
def deactivate_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    doctor.is_active = False
    db.commit()
    return {"message": "Doctor deactivated"}

# ── Reactivate Doctor ─────────────────────────────────────────
@app.put("/doctors/{doctor_id}/reactivate")
def reactivate_doctor(doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.doctor_id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    doctor.is_active = True
    db.commit()
    return {"message": "Doctor reactivated"}


# --- forecast ---------------------------------------------
@app.get("/forecast")
def get_forecast(date: str, hour_slot: int):
    return predict_slot(date, hour_slot)

@app.get("/forecast/week")
def get_forecast_week(start_date: str):
    return predict_week(start_date)    

# ---- diagnosis -----------------------------------------------------
@app.get("/patient-type")
def get_patient_type(date: str, hour_slot: int):
    return predict_patient_type(date, hour_slot)


@app.post("/admin/retrain")
def trigger_retrain(db: Session = Depends(get_db)):
    return retrain_model(db)