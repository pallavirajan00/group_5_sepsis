# app.py - Streamlit Sepsis DSS starter template

import streamlit as st
import psycopg2
import hashlib
from datetime import datetime
import joblib
import pandas as pd

# Load ML model (with preprocessing pipeline included)
model = joblib.load("ML_model_development/sepsis_model.pkl")

def calculate_risk(visit_id):
    """
    Pull features for a given visit_id, preprocess, and predict sepsis risk probability.
    """
    # SQL to fetch latest vitals/labs and metadata
    conn_calc = get_connection()
    conn_calc = get_connection()
    df = pd.read_sql_query(
        """
        WITH latest_vital AS (
          SELECT *
          FROM Vitals
          WHERE visit_id = %s
          ORDER BY timestamp DESC
          LIMIT 1
        ), latest_lab AS (
          SELECT *
          FROM Labs
          WHERE visit_id = %s
          ORDER BY timestamp DESC
          LIMIT 1
        )
        SELECT
          (EXTRACT(EPOCH FROM v.timestamp - vi.visit_date) / 3600)::int AS "HourOfObservation",
          p.age AS "PatientAge",
          vi.iculos AS "ICULengthOfStay",
          p.gender AS "PatientGender",
          vi.hosp_adm_time AS "TimeSinceHospitalAdmission",
          v.hr AS "HeartRate",
          v.map AS "MeanArterialPressure",
          v.o2sat AS "OxygenSaturation",
          v.resp AS "RespiratoryRate",
          v.sbp AS "SystolicBloodPressure",
          v.dbp AS "DiastolicBloodPressure",
          v.temp AS "Temperature",
          l.wbc AS "WhiteBloodCellCount",
          l.creatinine AS "CreatinineLevel",
          l.bilirubin_total AS "TotalBilirubin",
          l.platelets AS "PlateletCount",
          l.lactate AS "LactateLevel"
        FROM Visits vi
        JOIN Patients p ON vi.patient_id = p.patient_id
        LEFT JOIN latest_vital v ON vi.visit_id = v.visit_id
        LEFT JOIN latest_lab l ON vi.visit_id = l.visit_id
        WHERE vi.visit_id = %s
        """,
        conn_calc,
        params=(visit_id, visit_id, visit_id)
    )
    conn_calc.close()
    # If no data returned, cannot calculate risk
    if df.empty:
        return None

    # Ensure correct feature order
    FEATURES = [
        "HourOfObservation","PatientAge","ICULengthOfStay","PatientGender",
        "TimeSinceHospitalAdmission","HeartRate","MeanArterialPressure","OxygenSaturation",
        "RespiratoryRate","SystolicBloodPressure","DiastolicBloodPressure",
        "Temperature","WhiteBloodCellCount","CreatinineLevel",
        "TotalBilirubin","PlateletCount","LactateLevel"
    ]
    X = df[FEATURES]

    # Predict probability
    proba = model.predict_proba(X)[0,1]
    #st.session_state.debug_X = X
    return float(proba)


# ------------------------------
# Config: DB Connection
# ------------------------------
def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="sepsis_dss",
        user="sepsis_tool_admin",
        password="sepsis"
    )

# ------------------------------
# Helpers
# ------------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_login(username, password):
    password = password.strip()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT password_hash, role FROM Users WHERE username = %s", (username,))
    result = cur.fetchone()
    conn.close()
    if result and result[0] == hash_password(password):
        return True, result[1]
    return False, None

# ------------------------------
# Login Form
# ------------------------------
st.title("Sepsis Risk Decision Support System")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.patient_exists = None
    st.session_state.last_patient_id = None
    st.session_state.current_visit_id = None
    st.session_state.latest_risk_score = None
    st.session_state.show_entry_form = False
    st.session_state.patient_status = None

# Logout button (shows only when logged in)
if st.session_state.logged_in:
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

# ------------------------------
# Navigation: Home Button
# ------------------------------
if st.session_state.logged_in:
    if st.sidebar.button("Patient Lookup"):
        st.session_state.show_all_patients = False
        st.rerun()

    if st.sidebar.button("All Admitted Patients"):
        st.session_state.show_all_patients = True
        st.rerun()



# ------------------------------
# Show Login Form (only if not logged in)
# ------------------------------
if not st.session_state.logged_in:
    st.subheader("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_submitted = st.form_submit_button("Login")

    if login_submitted:
        valid, role = verify_login(username, password)
        if valid:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.role = role
            st.session_state.show_all_patients = True
            st.success(f"Logged in as {username} ({role})")
            st.rerun()
        else:
            st.error("Invalid username or password")
            st.stop()

# ------------------------------
# All Admitted Patients Page
# ------------------------------
if st.session_state.logged_in and st.session_state.get("show_all_patients"):
    st.header("All Admitted Patients")
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (p.patient_id) p.patient_id, p.firstname, p.lastname, p.age, p.gender, r.score, v.location
            FROM Patients p
            JOIN Visits v ON p.patient_id = v.patient_id
            JOIN RiskScores r ON v.visit_id = r.visit_id
            WHERE p.status = 'admitted'
            AND r.score IS NOT NULL
            ORDER BY p.patient_id, r.generated_at DESC
        """)
        rows = cur.fetchall()
        # Sort patients by descending risk score
        rows = sorted(rows, key=lambda row: row[5], reverse=True)
        # KPI summaries for risk categories
        low_count = sum(1 for r in rows if r[5] < 0.20)
        med_count = sum(1 for r in rows if 0.20 <= r[5] < 0.80)
        high_count = sum(1 for r in rows if r[5] >= 0.80)
        col1, col2, col3 = st.columns(3)
        col1.metric("Low Risk (<20%)", low_count)
        col2.metric("Medium Risk (20-80%)", med_count)
        col3.metric("High Risk (>=80%)", high_count)
        cur.close()
        conn.close()

        if rows:
            # Build table of patients
            import pandas as pd
            table_data = []
            for row in rows:
                pid, fn, ln, age, gender, score, location = row
                # Check for sepsis diagnosis
                conn_diag = get_connection()
                cur_diag = conn_diag.cursor()
                cur_diag.execute(
                    "SELECT sepsis FROM Diagnosis WHERE visit_id = (SELECT visit_id FROM Visits WHERE patient_id = %s ORDER BY diagnosis_datetime DESC LIMIT 1)",
                    (pid,)
                )
                diag_res = cur_diag.fetchone()
                cur_diag.close()
                conn_diag.close()
                sepsis_label = 'Sepsis' if diag_res and diag_res[0] else ''
                table_data.append({
                    'Patient ID': pid,
                    'Name': f"{fn} {ln}",
                    'Room': location,
                    'Age': age,
                    'Gender': gender,
                    'Risk Score': f"{score:.2%}",
                    'Sepsis': sepsis_label
                })
            df_patients = pd.DataFrame(table_data)

            # Apply color styling to Risk Score and Sepsis columns
            def color_score_str(val):
                num = float(val.strip('%'))/100
                if num < 0.20:
                    return 'color: green'
                elif num < 0.80:
                    return 'color: orange'
                else:
                    return 'color: red'

            def color_sepsis(val):
                return 'color: purple' if val == 'Sepsis' else ''

            styled_df = df_patients.style.applymap(color_score_str, subset=['Risk Score']) \
                                         .applymap(color_sepsis, subset=['Sepsis'])
            # Set DataFrame index to ID and remove index column
            df_patients_indexed = styled_df.data.copy()
            df_patients_indexed.set_index('Patient ID', inplace=True)
            st.dataframe(df_patients_indexed.style.applymap(color_score_str, subset=['Risk Score']).applymap(color_sepsis, subset=['Sepsis']))


            # Histogram of risk scores with formatted bins
            import numpy as np
            scores = [row[5] for row in rows]
            # Define 10 bins from 0 to 1
            bins = np.linspace(0, 1, 11)
            labels = [f"{bins[i]:.1f}-{bins[i+1]:.1f}" for i in range(len(bins)-1)]
            categories = pd.cut(scores, bins=bins, labels=labels, include_lowest=True)
            count_series = categories.value_counts().sort_index()
            st.bar_chart(count_series)
        else:
            st.info("No admitted patients with risk scores found.")

    except Exception as e:
        st.error(f"An error occurred: {e}")



# ------------------------------
# Main App Content
# ------------------------------
if st.session_state.logged_in:

    st.sidebar.write(f"Logged in as: {st.session_state.username} ({st.session_state.role})")
    st.header("Patient Lookup")
    if st.button("View All Admitted Patients", key="main_all_patients_button"):
        st.session_state.show_all_patients = True
        st.rerun()



    with st.form("patient_search_form"):
        patient_id = st.text_input("Enter Patient ID")
        submitted = st.form_submit_button("Search", type="primary")

    if submitted:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT firstname, lastname, age, gender FROM Patients WHERE patient_id = %s", (patient_id,))
        result = cur.fetchone()

        st.session_state.last_patient_id = patient_id
        st.session_state.patient_exists = result is not None
        st.session_state.show_entry_form = False
        st.session_state.current_visit_id = None

        if result:
            st.session_state.firstname = result[0]
            st.session_state.lastname = result[1]
            st.session_state.age = result[2]
            st.session_state.gender = result[3]
            st.success(f"Patient {patient_id} ({result[0]} {result[1]}) found: Age {result[2]}, Gender {result[3]}")

            # Fetch patient status
            cur.execute("SELECT status FROM Patients WHERE patient_id = %s", (patient_id,))
            status_result = cur.fetchone()
            if status_result:
                st.session_state.patient_status = status_result[0]
                st.markdown(f"**Status:** `{st.session_state.patient_status}`")

            # Show early sepsis diagnosis info if it exists
            conn_check = get_connection()
            cur_check = conn_check.cursor()
            cur_check.execute("SELECT visit_id FROM Visits WHERE patient_id = %s ORDER BY visit_date DESC LIMIT 1", (patient_id,))
            recent_visit = cur_check.fetchone()
            if recent_visit:
                st.session_state.current_visit_id = recent_visit[0]
                cur_check.execute("SELECT sepsis, diagnosis_datetime FROM Diagnosis WHERE visit_id = %s ORDER BY diagnosis_datetime DESC LIMIT 1", (recent_visit[0],))
                diag_result = cur_check.fetchone()
                if diag_result and diag_result[0]:
                    st.markdown(f"<span style='color:orange'><b>Diagnosis: Sepsis</b> (Diagnosed at {diag_result[1].strftime('%Y-%m-%d %H:%M:%S')})</span>", unsafe_allow_html=True)
            cur_check.close()
            conn_check.close()
            # Check if there's already a visit today
            cur.execute("SELECT visit_id FROM Visits WHERE patient_id = %s AND visit_date = %s",
                        (patient_id, datetime.now()))
            visit_result = cur.fetchone()
            if visit_result:
                st.session_state.current_visit_id = visit_result[0]
        else:
            st.warning("Patient not found. Please enter details to add a new patient.")

        cur.close()
        conn.close()

    if st.session_state.patient_exists is False and st.session_state.last_patient_id:
        with st.form("new_patient_form", clear_on_submit=False):
            new_firstname = st.text_input("First Name", key="new_firstname")
            new_lastname = st.text_input("Last Name", key="new_lastname")
            new_age = st.number_input("Age", min_value=0, max_value=120, key="new_age")
            new_gender = st.selectbox("Gender", ["male", "female", "other"], key="new_gender")
            visit_date = st.date_input("Visit Date", key="new_visit_date")
            hosp_adm_time = st.number_input("Hospital Admission Time (hours since arrival)", min_value=0, key="new_hosp_adm_time")
            location = st.text_input("Room Number", key="new_location")
            add_patient = st.form_submit_button("Add Patient")

        if add_patient:
            try:
                conn = get_connection()
                cur = conn.cursor()

                cur.execute("INSERT INTO Patients (patient_id, firstname, lastname, age, gender, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                            (st.session_state.last_patient_id, new_firstname, new_lastname, new_age, new_gender, datetime.now()))

                cur.execute("INSERT INTO Visits (patient_id, created_by, visit_date, hosp_adm_time, iculos, location) VALUES (%s, %s, %s, %s, %s, %s) RETURNING visit_id",
                            (st.session_state.last_patient_id, st.session_state.username, visit_date, hosp_adm_time, 0, location))
                st.session_state.current_visit_id = cur.fetchone()[0]

                conn.commit()
                cur.close()
                conn.close()
                st.success("New patient created. Please enter vitals and labs.")
                st.session_state.patient_exists = True
                st.session_state.show_entry_form = True
            except Exception as e:
                st.error(f"An error occurred: {e}")

# Create buttons for Edit Patient Details and Edit Visit Details
    if st.session_state.patient_exists and not st.session_state.show_entry_form:
        
        # Edit Patient Details (all users)
        if st.button("Edit Patient Details", key="edit_patient_button"):
            st.session_state.show_edit_form = True
            st.session_state.edit_firstname = st.session_state.get("firstname", "")
            st.session_state.edit_lastname = st.session_state.get("lastname", "")
            st.session_state.edit_age = st.session_state.get("age", 0)
            st.session_state.edit_gender = st.session_state.get("gender", "male")
            st.rerun()
        
        # Edit Visit Details (all users)
        if st.button("Edit Visit Details", key="edit_visit_button"):
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT visit_date, hosp_adm_time, location FROM Visits WHERE visit_id = %s", 
                    (st.session_state.current_visit_id,))
            visit_info = cur.fetchone()
            cur.close()
            conn.close()
            if visit_info:
                st.session_state.edit_visit_date = visit_info[0]
                st.session_state.edit_hosp_adm_time = visit_info[1]
                st.session_state.edit_location = visit_info[2]
                st.session_state.show_edit_visit_form = True
                st.rerun()

        if st.session_state.patient_status == 'discharged':
            st.warning("This patient is currently discharged. You cannot enter new vitals or labs.")
        else:
            st.header("Sepsis Risk Dashboard")

        # Compute dynamic ICU Length of Stay in days
        conn_ilos = get_connection()
        cur_ilos = conn_ilos.cursor()
        cur_ilos.execute("SELECT visit_date FROM Visits WHERE visit_id = %s", (st.session_state.current_visit_id,))
        ilos_row = cur_ilos.fetchone()
        cur_ilos.close()
        conn_ilos.close()
        if ilos_row and ilos_row[0]:
            # calculate in days
            from datetime import time
            visit_datetime = datetime.combine(ilos_row[0], time.min)
            dynamic_iculos = (datetime.now() - visit_datetime).total_seconds() / 86400
            st.write(f"ICU Length of Stay: {dynamic_iculos:.2f} days")
            # Update ICULOS in the database
            conn_upd = get_connection()
            cur_upd = conn_upd.cursor()
            cur_upd.execute("UPDATE Visits SET iculos = %s WHERE visit_id = %s", (dynamic_iculos, st.session_state.current_visit_id))
            conn_upd.commit()
            cur_upd.close()
            conn_upd.close()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT visit_id FROM Visits WHERE patient_id = %s ORDER BY visit_date DESC LIMIT 1", (st.session_state.last_patient_id,))
        visit_result = cur.fetchone()
        if visit_result:
            st.session_state.current_visit_id = visit_result[0]

        cur.execute("SELECT score FROM RiskScores WHERE visit_id = %s ORDER BY generated_at DESC LIMIT 1", (st.session_state.current_visit_id,))
        score_result = cur.fetchone()
        cur.close()
        conn.close()

        if score_result:
            st.metric("Current Risk Score", f"{score_result[0]:.2%}")
            st.session_state.latest_risk_score = score_result[0]
        else:
            st.info("No risk score found. Please enter vitals and labs.")

        if st.session_state.role == "nurse":
            st.button("Notify Physician")
        st.caption("Since this is a prototype, we have not integrated with your organization's internal messaging system. Please notify the physician outside of this app.")

        if st.session_state.patient_status == 'admitted' and st.session_state.current_visit_id:
            if st.button("Update Labs and Vitals"):
                st.session_state.show_entry_form = True
                st.rerun()

    # Admit/Discharge Controls (all users)
    if st.session_state.patient_exists and st.session_state.last_patient_id:
        if st.session_state.patient_status == 'admitted':
            if st.button("Discharge Patient"):
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE Patients SET status = 'discharged' WHERE patient_id = %s", (st.session_state.last_patient_id,))
                    # Clear location on discharge
                    cur.execute("UPDATE Visits SET location = NULL WHERE visit_id = %s", (st.session_state.current_visit_id,))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("Patient discharged.")
                    st.rerun()
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        elif st.session_state.patient_status == 'discharged':
            if st.button("Admit Patient"):
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE Patients SET status = 'admitted' WHERE patient_id = %s", (st.session_state.last_patient_id,))
                    cur.execute("INSERT INTO Visits (patient_id, created_by, visit_date, hosp_adm_time, iculos) VALUES (%s, %s, %s, %s, %s) RETURNING visit_id",
                                (st.session_state.last_patient_id, st.session_state.username, datetime.now(), 0, 0))
                    st.session_state.current_visit_id = cur.fetchone()[0]
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("Patient readmitted. New visit created.")
                    st.rerun()
                except Exception as e:
                    st.error(f"An error occurred: {e}")

    # Diagnosis already displayed earlier in the dashboard — removed duplicate display

    # Physician-only actions — only if a patient is selected and visit_id exists
    if st.session_state.role == "physician" and st.session_state.patient_exists and st.session_state.current_visit_id:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT sepsis FROM Diagnosis WHERE visit_id = %s ORDER BY diagnosis_datetime DESC LIMIT 1", (st.session_state.current_visit_id,))
        diag_result = cur.fetchone()
        cur.close()
        conn.close()

        if not diag_result or not diag_result[0]:
            if st.button("Diagnose with Sepsis"):
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("INSERT INTO Diagnosis (visit_id, sepsis, diagnosed_by, diagnosis_datetime) VALUES (%s, %s, %s, %s)",
                                (st.session_state.current_visit_id, True, st.session_state.username, datetime.now()))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("Diagnosis recorded: Sepsis")
                    st.rerun()
                except Exception as e:
                    st.error(f"An error occurred: {e}")
        elif diag_result[0]:
            if st.button("Remove Sepsis Diagnosis"):
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("DELETE FROM Diagnosis WHERE visit_id = %s AND sepsis = TRUE", (st.session_state.current_visit_id,))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.warning("Sepsis diagnosis removed.")
                    st.rerun()
                except Exception as e:
                    st.error(f"An error occurred: {e}")

# Edit Patient Details Form
if st.session_state.get("show_edit_form"):
    with st.form("edit_patient_form"):
        ef = st.text_input("First Name", value=st.session_state.edit_firstname, key="ef")
        el = st.text_input("Last Name", value=st.session_state.edit_lastname, key="el")
        ea = st.number_input("Age", min_value=0, max_value=120, value=int(st.session_state.edit_age), key="ea")
        eg = st.selectbox("Gender", ["male", "female", "other"], 
                          index=["male", "female", "other"].index(st.session_state.edit_gender), key="eg")
        save = st.form_submit_button("Update Patient Details")
    
    if save:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE Patients SET firstname=%s, lastname=%s, age=%s, gender=%s WHERE patient_id = %s",
                (ef, el, ea, eg, st.session_state.last_patient_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            # Update session
            st.session_state.firstname = ef
            st.session_state.lastname = el
            st.session_state.age = ea
            st.session_state.gender = eg
            st.session_state.show_edit_form = False
            st.success("Patient details updated successfully.")
            st.rerun()
        except Exception as e:
            st.error(f"Update failed: {e}")

# Edit Visit Details Form
if st.session_state.get("show_edit_visit_form"):
    with st.form("edit_visit_form"):
        new_visit_date = st.date_input("Visit Date", value=st.session_state.edit_visit_date, key="evd")
        hosp_adm_time_val = st.session_state.edit_hosp_adm_time or 0.0
        new_hosp_adm_time = st.number_input("Hospital Admission Time (hours since arrival)", 
                                            min_value=0.0, 
                                            value=float(hosp_adm_time_val), 
                                            key="ehat")
        new_location = st.text_input("Room Number", value=st.session_state.edit_location, key="ev_location")
        submit_visit = st.form_submit_button("Update Visit Details")
    
    if submit_visit:
        try:
            conn = get_connection()
            cur = conn.cursor()
            # Update visit details
            cur.execute(
                "UPDATE Visits SET visit_date=%s, hosp_adm_time=%s, location=%s WHERE visit_id=%s",
                (new_visit_date, new_hosp_adm_time, new_location, st.session_state.current_visit_id)
            )
            # Update dynamic ICU Length of Stay
            dynamic_iculos = (datetime.now() - datetime.combine(new_visit_date, datetime.min.time())).total_seconds() / 86400
            cur.execute(
                "UPDATE Visits SET iculos=%s WHERE visit_id=%s",
                (dynamic_iculos, st.session_state.current_visit_id)
            )
            conn.commit()
            cur.close()
            conn.close()
            st.session_state.show_edit_visit_form = False
            st.success("Visit details updated successfully.")
            st.rerun()
        except Exception as e:
            st.error(f"Update failed: {e}")

# Vitals and Labs Entry Form
if st.session_state.get("show_entry_form"):
    st.header("Enter Vitals and Lab Results")

    if not st.session_state.current_visit_id:
        st.error("No active visit ID. Please select or create a visit before entering vitals.")
    else:
        with st.form("vitals_labs_form", clear_on_submit=False):
            st.subheader("Vitals")
            temp = st.number_input("Temperature (°C)")
            hr = st.number_input("Heart Rate (bpm)")
            sbp = st.number_input("Systolic BP (mm Hg)")
            dbp = st.number_input("Diastolic BP (mm Hg)")
            map_ = st.number_input("MAP (mm Hg)")
            resp = st.number_input("Respiration Rate (breaths/min)")
            o2sat = st.number_input('Oxygen Saturation (%)', min_value=0.0, max_value=100.0)

            st.subheader("Labs")
            wbc = st.number_input("White Blood Cell Count")
            creatinine = st.number_input("Creatinine")
            bilirubin_total = st.number_input("Total Bilirubin")
            bilirubin_direct = st.number_input("Direct Bilirubin")
            platelets = st.number_input("Platelets")
            lactate = st.number_input("Lactate")

            submit_vitals_labs = st.form_submit_button("Submit Vitals and Labs")

        if submit_vitals_labs:
            try:
                conn = get_connection()
                cur = conn.cursor()
                timestamp = datetime.now()

                cur.execute("INSERT INTO Vitals (visit_id, entered_by, temp, hr, sbp, dbp, map, resp, o2sat, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (st.session_state.current_visit_id, st.session_state.username, temp, hr, sbp, dbp, map_, resp, o2sat, timestamp))

                cur.execute("INSERT INTO Labs (visit_id, entered_by, wbc, creatinine, bilirubin_total, bilirubin_direct, platelets, lactate, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (st.session_state.current_visit_id, st.session_state.username, wbc, creatinine, bilirubin_total, bilirubin_direct, platelets, lactate, timestamp))

                                    # Compute sepsis risk via ML model
                risk_score = calculate_risk(st.session_state.current_visit_id)
                if risk_score is None:
                    st.error("Cannot calculate risk: please ensure both vitals and labs are submitted.")
                else:
                    cur.execute(
                        "INSERT INTO RiskScores (visit_id, score, generated_at) VALUES (%s, %s, %s)",
                        (st.session_state.current_visit_id, risk_score, timestamp)
                    )
                    conn.commit()
                cur.close()
                conn.close()

                st.success("Vitals, labs, and risk score submitted successfully.")
                st.session_state.latest_risk_score = risk_score
                st.session_state.show_entry_form = False
                st.rerun()

            except Exception as e:
                st.error(f"An error occurred: {e}")

# uncomment line 79 to see this
if "debug_X" in st.session_state:
    st.subheader("DEBUG: Model Input to Predict")
    st.dataframe(st.session_state.debug_X)
