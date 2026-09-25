from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from datetime import timezone

class Ward(Base):
    __tablename__ = "wards"
    ward_id   = Column(Integer, primary_key=True, index=True)
    ward_type = Column(String(50), nullable=False)
    capacity  = Column(Integer, nullable=False)
    beds      = relationship("Bed", back_populates="ward")

class Bed(Base):
    __tablename__ = "beds"
    bed_id     = Column(Integer, primary_key=True, index=True)
    bed_number = Column(String(20), nullable=False)
    bed_status = Column(String(20), default="Available")
    ward_id    = Column(Integer, ForeignKey("wards.ward_id"))
    ward       = relationship("Ward", back_populates="beds")

class Patient(Base):
    __tablename__ = "patients"
    patient_id     = Column(Integer, primary_key=True, index=True)
    stay_id        = Column(BigInteger, unique=True, nullable=False)
    temperature    = Column(Float)
    heartrate      = Column(Integer)
    resprate       = Column(Integer)
    o2sat          = Column(Float)
    sbp            = Column(Integer)
    dbp            = Column(Integer)
    pain           = Column(Integer)
    acuity         = Column(Integer, nullable=False)
    chiefcomplaint = Column(String(255))
    status         = Column(String(20), default="waiting")
    arrival_time   = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    discharge_time = Column(DateTime, nullable=True)
    assignment     = relationship("Assignment", back_populates="patient")

class Nurse(Base):
    __tablename__ = "nurses"
    nurse_id = Column(Integer, primary_key=True, index=True)
    ward     = Column(String(20), nullable=False)
    role     = Column(String(20), nullable=False)
    shift    = Column(String(20), nullable=False)
    grp      = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)

class Doctor(Base):
    __tablename__ = "doctors"
    doctor_id = Column(Integer, primary_key=True, index=True)
    ward      = Column(String(20), nullable=False)
    is_intern = Column(Boolean, nullable=False)
    shift     = Column(String(20), nullable=False)
    work_days = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)

class Assignment(Base):
    __tablename__ = "assignments"
    assignment_id = Column(Integer, primary_key=True, index=True)
    patient_id    = Column(Integer, ForeignKey("patients.patient_id"))
    bed_id        = Column(Integer, ForeignKey("beds.bed_id"))
    rn_id         = Column(Integer, ForeignKey("nurses.nurse_id"))
    pn_id         = Column(Integer, ForeignKey("nurses.nurse_id"))
    doctor_id     = Column(Integer, ForeignKey("doctors.doctor_id"))
    assigned_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    shift         = Column(String(20), nullable=False)
    date          = Column(Date, nullable=False)
    patient       = relationship("Patient", back_populates="assignment")