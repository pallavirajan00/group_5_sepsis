# Sepsis DSS - Project Setup Instructions

## Prerequisites

- Python 3.8 or higher
- PostgreSQL installed and running
- pgAdmin or psql command line tool available

## Repository Contents

- `app.py`: Streamlit application code
- `setup.sql`: SQL script to create the database, tables, and sample users
- `requirements.txt`: Python dependencies
- `sepsis_model.pkl`: Pre-trained machine learning model
- `ML_model_development/`: Project folder containing our machine learning model development code (for TA review only; users do not need to open or modify these files)

## 1. Initialize the Database

First, create the database:

```bash
createdb sepsis_dss
```

Then load the schema and seed data:

```bash
psql -U postgres -d sepsis_dss -f setup.sql
```

> Note: Replace `-U postgres` if your superuser is different.

## 2. Create Application User

Create and grant access to `sepsis_tool_admin`:

```sql
CREATE ROLE sepsis_tool_admin WITH LOGIN PASSWORD 'sepsis';
GRANT ALL PRIVILEGES ON DATABASE sepsis_dss TO sepsis_tool_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO sepsis_tool_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO sepsis_tool_admin;
```

## 3. Install Python Dependencies

(Optionally inside a virtual environment)

```bash
pip install -r requirements.txt
```

> Dependencies like `numpy` install automatically via pandas, scikit-learn, and xgboost.

## 4. Run the Application

Start the Streamlit app:

```bash
streamlit run app.py
```

Access the app via your browser at `http://localhost:8501`.

## 5. Login Credentials

- Nurse: `nurse1` / `sepsis`
- Physician: `physician1` / `sepsis`

## Troubleshooting

- Ensure PostgreSQL is running.
- Ensure you created the `sepsis_dss` database.
- Ensure `setup.sql` completed without errors.
- Ensure `sepsis_tool_admin` has all table and sequence privileges.
