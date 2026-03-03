#!/usr/bin/env bash

echo "Starting Nutrition AI Project"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "Project directory: $PROJECT_DIR"


if [ ! -d "venv" ]; then
    echo "Creating virtual environment"
    python3 -m venv venv
fi

echo "Activating virtual environment"
source venv/bin/activate

echo "Installing dependencies"
pip install --upgrade pip
pip install -r requirements.txt


echo "Checking PostgreSQL"

if [[ "$OSTYPE" == "darwin"* ]]; then
    brew services start postgresql 2>/dev/null
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo systemctl start postgresql 2>/dev/null
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "⚠️ Please ensure PostgreSQL service is running on Windows."
fi


echo "Ensuring database user exists"

psql postgres <<EOF
DO
\$do\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE rolname = 'nutrition_user'
   ) THEN
      CREATE ROLE nutrition_user WITH LOGIN PASSWORD 'nutrition_pass';
      ALTER ROLE nutrition_user CREATEDB;
   END IF;
END
\$do\$;
EOF


echo "Ensuring database exists"

psql postgres <<EOF
DO
\$do\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_database WHERE datname = 'nutrition_ai'
   ) THEN
      CREATE DATABASE nutrition_ai OWNER nutrition_user;
   END IF;
END
\$do\$;
EOF


echo "Clearing port 8000"

if command -v lsof >/dev/null 2>&1; then
    lsof -ti:8000 | xargs kill -9 2>/dev/null
elif command -v fuser >/dev/null 2>&1; then
    fuser -k 8000/tcp 2>/dev/null
fi

echo "Initializing database"
python3 populate_users.py
python3 pipelines/ingest_recipes.py


echo "Starting FastAPI"
uvicorn main:app --reload &
sleep 3


echo "Starting Streamlit frontend"
streamlit run app.py