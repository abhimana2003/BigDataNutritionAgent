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

echo "Applying schema migration for account fields"
psql nutrition_ai <<EOF
ALTER TABLE IF EXISTS user_profiles ADD COLUMN IF NOT EXISTS username VARCHAR;
ALTER TABLE IF EXISTS user_profiles ADD COLUMN IF NOT EXISTS email VARCHAR;
ALTER TABLE IF EXISTS user_profiles ADD COLUMN IF NOT EXISTS full_name VARCHAR;
ALTER TABLE IF EXISTS user_profiles ADD COLUMN IF NOT EXISTS password_hash VARCHAR;
ALTER TABLE IF EXISTS user_profiles ADD COLUMN IF NOT EXISTS password_salt VARCHAR;
UPDATE user_profiles SET username = 'user_' || id WHERE username IS NULL OR username = '';
UPDATE user_profiles SET goal = 'maintenance' WHERE goal IS NULL OR goal NOT IN ('weight loss', 'maintenance', 'high protein');
UPDATE user_profiles SET cooking_time = 'medium (30-60 min)' WHERE cooking_time IS NULL OR cooking_time NOT IN ('short (<30 mins)', 'medium (30-60 min)', 'long (>60 mins)');
CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profiles_username ON user_profiles (username);
ALTER TABLE IF EXISTS user_profiles ALTER COLUMN username SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profiles_email ON user_profiles (email);
ALTER TABLE IF EXISTS recipes ADD COLUMN IF NOT EXISTS username VARCHAR;
EOF


echo "Clearing port 8000"

if command -v lsof >/dev/null 2>&1; then
    lsof -ti:8000 | xargs kill -9 2>/dev/null
elif command -v fuser >/dev/null 2>&1; then
    fuser -k 8000/tcp 2>/dev/null
fi

echo "Initializing database"
python3 init_db.py
python3 populate_users.py
python3 pipelines/ingest_recipes.py


echo "Starting FastAPI"
uvicorn main:app --reload &
sleep 3


echo "Starting Streamlit frontend"
streamlit run app.py
