# Sepsis Risk Decision Support System

This repository contains a Streamlit application, a PostgreSQL database schema, and a machine learning model for sepsis risk prediction.

## Prerequisites

- Python 3.8 or higher
- PostgreSQL installed and running locally
- The `psql` command-line tool available in your PATH

## Repository Contents

- `app.py`: Streamlit application code
- `setup.sql`: SQL script to create the database, tables, and seed sample users
- `requirements.txt`: Python dependencies
- `sepsis_model.pkl`: Pre-trained and pickled machine learning model

## 1. Initialize the Database

Run the following command from the project root to create the database and load schema and seed data:

```bash
psql -U postgres -f setup.sql
```

Note: If your PostgreSQL superuser is not `postgres`, replace `-U postgres` with your username.

## 2. Create Application User (Optional)

If the role `sepsis_tool_admin` does not exist, create it and grant privileges:

```sql
CREATE ROLE sepsis_tool_admin WITH LOGIN PASSWORD 'sepsis';
GRANT ALL PRIVILEGES ON DATABASE sepsis_dss TO sepsis_tool_admin;
```

The application code uses these credentials:

```python
def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="sepsis_dss",
        user="sepsis_tool_admin",
        password="sepsis"
    )
```

## 3. Install Python Dependencies

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# .\venv\Scripts\activate # Windows
pip install -r requirements.txt
```

## 4. Run the Application

Start the Streamlit app:

```bash
streamlit run app.py
```

Open a browser and go to `http://localhost:8501`.

## 5. Application Workflow

1. Log in as `nurse1` or `physician1` (password: `sepsis`).
2. View the All Admitted Patients dashboard by default.
3. Use the sidebar or main page to look up patients, enter or update vitals and labs, and calculate risk scores.
4. Edit patient and visit details as needed.

## Troubleshooting

- If port 8501 is in use, run `streamlit run app.py --server.port <port>`.
- Ensure the database `sepsis_dss` exists and `setup.sql` ran without errors.
- Verify the virtual environment is activated and dependencies are installed.

