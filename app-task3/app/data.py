"""Seed data for CareWell Hospital (in-memory, demo only - a real system would use a database).

Dates are relative to today so the dashboard always shows recent admissions and
today's appointments. Phone numbers are fake.
"""
from datetime import date, timedelta

TODAY = date.today()


def days_ago(n):
    return (TODAY - timedelta(days=n)).isoformat()


WARDS = ["General", "Cardiology", "Orthopedics", "Paediatrics", "Neurology", "ICU"]

# Beds per ward (drives the ward-occupancy bars on the dashboard)
WARD_BEDS = {"General": 6, "Cardiology": 3, "Orthopedics": 3, "Paediatrics": 3,
             "Neurology": 2, "ICU": 2}
TOTAL_BEDS = sum(WARD_BEDS.values())
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
GENDERS = ["Female", "Male", "Other"]
STATUSES = ["Admitted", "Critical", "Discharged"]

DOCTORS = {
    1: {"id": 1, "name": "Dr. Meera Iyer", "department": "Cardiology", "availability": "On duty"},
    2: {"id": 2, "name": "Dr. Vikram Singh", "department": "Orthopedics", "availability": "On duty"},
    3: {"id": 3, "name": "Dr. Priya Nair", "department": "Paediatrics", "availability": "On call"},
    4: {"id": 4, "name": "Dr. Sanjay Gupta", "department": "General Medicine",
        "availability": "On duty"},
    5: {"id": 5, "name": "Dr. Kavita Reddy", "department": "Neurology", "availability": "Off duty"},
    6: {"id": 6, "name": "Dr. Arjun Desai", "department": "Critical Care", "availability": "On duty"},
}


def _patient(pid, name, age, gender, blood, phone, ward, diagnosis, doctor_id, status,
             admitted_days_ago, vitals, visits):
    return {
        "id": pid, "name": name, "age": age, "gender": gender, "blood_group": blood,
        "phone": phone, "ward": ward, "diagnosis": diagnosis, "doctor_id": doctor_id,
        "status": status, "admitted": days_ago(admitted_days_ago),
        "vitals": {"bp": vitals[0], "pulse": vitals[1], "temp": vitals[2]},
        "visits": [{"date": days_ago(d), "note": note} for d, note in visits],
    }


PATIENTS = {p["id"]: p for p in [
    _patient(1, "Asha Sharma", 34, "Female", "B+", "9876543210", "Cardiology",
             "Atrial fibrillation", 1, "Admitted", 3, ("128/84", 92, 37.1),
             [(3, "Admitted via OPD with palpitations"), (1, "ECG reviewed, started on beta blockers")]),
    _patient(2, "Rohan Mehta", 52, "Male", "O+", "9823456781", "Orthopedics",
             "Fractured left femur", 2, "Admitted", 5, ("132/86", 78, 36.9),
             [(5, "Admitted after road accident"), (4, "Surgery - internal fixation"),
              (1, "Physiotherapy started")]),
    _patient(3, "Kavya Pillai", 8, "Female", "A+", "9845123456", "Paediatrics",
             "Dengue fever", 3, "Admitted", 2, ("100/65", 104, 38.4),
             [(2, "Admitted with high fever, platelets 85k"), (0, "Platelets improving")]),
    _patient(4, "Imran Qureshi", 67, "Male", "AB+", "9810987654", "ICU",
             "Acute myocardial infarction", 6, "Critical", 1, ("92/60", 118, 37.6),
             [(1, "Brought to emergency, shifted to ICU"), (0, "On ventilator support")]),
    _patient(5, "Sunita Joshi", 45, "Female", "O-", "9898989898", "General",
             "Type 2 diabetes - uncontrolled", 4, "Admitted", 4, ("138/88", 82, 36.8),
             [(4, "Admitted with HbA1c 11.2%"), (2, "Insulin dose adjusted")]),
    _patient(6, "Harpreet Kaur", 29, "Female", "B-", "9779012345", "General",
             "Appendicitis", 4, "Discharged", 9, ("118/76", 74, 36.7),
             [(9, "Laparoscopic appendectomy"), (6, "Discharged, review in 1 week")]),
    _patient(7, "Venkatesh Rao", 71, "Male", "A-", "9440123456", "Neurology",
             "Ischemic stroke", 5, "Critical", 2, ("168/98", 96, 37.2),
             [(2, "Admitted with left-side weakness"), (1, "MRI confirms right MCA infarct")]),
    _patient(8, "Neha Banerjee", 38, "Female", "O+", "9830567890", "Cardiology",
             "Hypertension", 1, "Discharged", 12, ("124/80", 72, 36.6),
             [(12, "Admitted for BP control"), (8, "Discharged on medication")]),
    _patient(9, "Aditya Kulkarni", 23, "Male", "B+", "9822334455", "Orthopedics",
             "ACL tear - right knee", 2, "Admitted", 1, ("120/78", 70, 36.8),
             [(1, "Admitted for ACL reconstruction")]),
    _patient(10, "Fatima Sheikh", 56, "Female", "A+", "9867001122", "General",
             "Pneumonia", 4, "Admitted", 3, ("126/82", 88, 38.1),
             [(3, "Admitted with cough and fever"), (1, "Chest X-ray shows improvement")]),
    _patient(11, "Arnav Chatterjee", 5, "Male", "O+", "9903112233", "Paediatrics",
             "Acute bronchiolitis", 3, "Discharged", 7, ("98/62", 110, 37.0),
             [(7, "Admitted with wheezing"), (4, "Discharged, nebulisation at home")]),
    _patient(12, "Lakshmi Menon", 63, "Female", "AB-", "9447556677", "Neurology",
             "Parkinson's disease review", 5, "Admitted", 0, ("130/84", 76, 36.7),
             [(0, "Admitted for medication review")]),
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
    {"id": 8, "patient_id": 6, "doctor_id": 4, "date": _today, "time": "15:30", "status": "Scheduled"},
    {"id": 9, "patient_id": 2, "doctor_id": 2, "date": _tomorrow, "time": "10:00", "status": "Scheduled"},
    {"id": 10, "patient_id": 11, "doctor_id": 3, "date": _tomorrow, "time": "11:30", "status": "Scheduled"},
]

# Allergies + emergency contact per patient (contact phone is PHI: masked in the UI)
_EXTRA = {
    1: (["Penicillin"], ("Rahul Sharma", "Husband", "9876500011")),
    2: ([], ("Pooja Mehta", "Wife", "9823400022")),
    3: (["Peanuts", "Ibuprofen"], ("Anil Pillai", "Father", "9845100033")),
    4: (["Aspirin"], ("Sana Qureshi", "Daughter", "9810900044")),
    5: ([], ("Ravi Joshi", "Son", "9898900055")),
    6: (["Latex"], ("Gurpreet Kaur", "Sister", "9779000066")),
    7: (["Sulfa drugs"], ("Lakshmi Rao", "Wife", "9440100077")),
    8: ([], ("Amit Banerjee", "Husband", "9830500088")),
    9: ([], ("Sneha Kulkarni", "Mother", "9822300099")),
    10: (["Codeine"], ("Zoya Sheikh", "Daughter", "9867000101")),
    11: (["Eggs"], ("Rina Chatterjee", "Mother", "9903100112")),
    12: ([], ("Suresh Menon", "Husband", "9447500123")),
}
for _pid, (_allergies, (_name, _relation, _phone)) in _EXTRA.items():
    PATIENTS[_pid]["allergies"] = _allergies
    PATIENTS[_pid]["emergency_contact"] = {"name": _name, "relation": _relation, "phone": _phone}
