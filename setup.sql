-- setup.sql
-- Usage: psql -U <your_pg_user> -f setup.sql

-- 1) Create the database (will error if it already exists; you can wrap in a DROP if you like)
CREATE DATABASE sepsis_dss;

-- 2) Switch into the new database
\connect sepsis_dss

-- 3) Schema
CREATE TABLE Users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE Patients (
    patient_id TEXT PRIMARY KEY,
    firstname TEXT,
    lastname TEXT,
    age INTEGER,
    gender TEXT,
    created_at TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'admitted' CHECK (status IN ('admitted','discharged'))
);

CREATE TABLE Visits (
    visit_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    patient_id TEXT NOT NULL REFERENCES Patients(patient_id),
    created_by TEXT NOT NULL REFERENCES Users(username),
    visit_date TIMESTAMP NOT NULL,
    hosp_adm_time REAL NOT NULL,
    iculos REAL NOT NULL,
    location TEXT
);

CREATE TABLE Vitals (
    vitals_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    visit_id INTEGER NOT NULL REFERENCES Visits(visit_id),
    entered_by TEXT NOT NULL REFERENCES Users(username),
    temp REAL, hr REAL, sbp REAL, dbp REAL, map REAL,
    resp REAL, o2sat REAL,
    timestamp TIMESTAMP NOT NULL
);

CREATE TABLE Labs (
    lab_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    visit_id INTEGER NOT NULL REFERENCES Visits(visit_id),
    entered_by TEXT NOT NULL REFERENCES Users(username),
    wbc REAL, creatinine REAL,
    bilirubin_total REAL, bilirubin_direct REAL,
    platelets REAL, lactate REAL,
    timestamp TIMESTAMP NOT NULL
);

CREATE TABLE RiskScores (
    score_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    visit_id INTEGER NOT NULL REFERENCES Visits(visit_id),
    score REAL NOT NULL,
    generated_at TIMESTAMP NOT NULL
);

CREATE TABLE Diagnosis (
    diagnosis_id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    visit_id INTEGER NOT NULL REFERENCES Visits(visit_id),
    sepsis BOOLEAN NOT NULL,
    diagnosed_by TEXT NOT NULL REFERENCES Users(username),
    diagnosis_datetime TIMESTAMP NOT NULL
);

-- 4) Seed Users
INSERT INTO Users (username, password_hash, role) VALUES
  ('nurse1',  'ea560944f08cca0c2ab2cb4ce3e59a6558c852759ea4054ec886809ad6a3b3a1', 'nurse'),
  ('physician1','ea560944f08cca0c2ab2cb4ce3e59a6558c852759ea4054ec886809ad6a3b3a1', 'physician');
