"""Seed data for CareWell Hospital v2 (in-memory, demo only).

Dates are relative to today so the dashboard always shows recent admissions and
today's appointments.
"""
from datetime import date, timedelta

TODAY = date.today()


def days_ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


TOTAL_BEDS = 40

DOCTORS = {
    1: {"id": 1, "name": "Dr. Meera Iyer", "department": "Cardiology", "availability": "On duty"},
    2: {"id": 2, "name": "Dr. Vikram Singh", "department": "Orthopedics", "availability": "On duty"},
    3: {"id": 3, "name": "Dr. Priya Nair", "department": "Paediatrics", "availability": "On call"},
    4: {"id": 4, "name": "Dr. Sanjay Gupta", "department": "General Medicine",
        "availability": "On duty"},
    5: {"id": 5, "name": "Dr. Kavita Reddy", "department": "Neurology", "availability": "Off duty"},
    6: {"id": 6, "name": "Dr. Arjun Desai", "department": "Critical Care", "availability": "On duty"},
}


def _patient(pid, name, age, blood, ward, diagnosis, doctor_id, status, admitted_days_ago):
    return {"id": pid, "name": name, "age": age, "blood_group": blood, "ward": ward,
            "diagnosis": diagnosis, "doctor_id": doctor_id, "status": status,
            "admitted": days_ago(admitted_days_ago)}


PATIENTS = {p["id"]: p for p in [
    _patient(1, "Asha Sharma", 34, "B+", "Cardiology", "Atrial fibrillation", 1, "Admitted", 3),
    _patient(2, "Rohan Mehta", 52, "O+", "Orthopedics", "Fractured left femur", 2, "Admitted", 5),
    _patient(3, "Kavya Pillai", 8, "A+", "Paediatrics", "Dengue fever", 3, "Admitted", 2),
    _patient(4, "Imran Qureshi", 67, "AB+", "ICU", "Acute myocardial infarction", 6, "Critical", 1),
    _patient(5, "Sunita Joshi", 45, "O-", "General", "Type 2 diabetes - uncontrolled", 4,
             "Admitted", 4),
    _patient(6, "Harpreet Kaur", 29, "B-", "General", "Appendicitis", 4, "Discharged", 9),
    _patient(7, "Venkatesh Rao", 71, "A-", "Neurology", "Ischemic stroke", 5, "Critical", 2),
    _patient(8, "Neha Banerjee", 38, "O+", "Cardiology", "Hypertension", 1, "Discharged", 12),
    _patient(9, "Aditya Kulkarni", 23, "B+", "Orthopedics", "ACL tear - right knee", 2,
             "Admitted", 1),
    _patient(10, "Fatima Sheikh", 56, "A+", "General", "Pneumonia", 4, "Admitted", 3),
]}

_today = TODAY.isoformat()
_tomorrow = (TODAY + timedelta(days=1)).isoformat()

APPOINTMENTS = [
    {"id": 1, "patient_id": 1, "doctor_id": 1, "date": _today, "time": "09:00", "status": "Completed"},
    {"id": 2, "patient_id": 5, "doctor_id": 4, "date": _today, "time": "09:30", "status": "Completed"},
    {"id": 3, "patient_id": 9, "doctor_id": 2, "date": _today, "time": "10:15", "status": "Checked in"},
    {"id": 4, "patient_id": 3, "doctor_id": 3, "date": _today, "time": "11:00", "status": "Scheduled"},
    {"id": 5, "patient_id": 8, "doctor_id": 1, "date": _today, "time": "11:45", "status": "Scheduled"},
    {"id": 6, "patient_id": 7, "doctor_id": 5, "date": _today, "time": "12:30", "status": "Cancelled"},
    {"id": 7, "patient_id": 10, "doctor_id": 4, "date": _today, "time": "14:00", "status": "Scheduled"},
    {"id": 8, "patient_id": 2, "doctor_id": 2, "date": _tomorrow, "time": "10:00", "status": "Scheduled"},
]
