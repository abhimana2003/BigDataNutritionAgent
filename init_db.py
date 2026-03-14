from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from database import engine
from models import Base

Base.metadata.create_all(bind=engine)


def run_migrations() -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS username VARCHAR"))
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS email VARCHAR"))
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS full_name VARCHAR"))
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS password_hash VARCHAR"))
            conn.execute(text("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS password_salt VARCHAR"))

            conn.execute(
                text(
                    "UPDATE user_profiles "
                    "SET username = 'user_' || id "
                    "WHERE username IS NULL OR username = ''"
                )
            )
            conn.execute(
                text(
                    "UPDATE user_profiles "
                    "SET goal = 'maintenance' "
                    "WHERE goal IS NULL OR goal NOT IN ('weight loss', 'maintenance', 'high protein')"
                )
            )
            conn.execute(
                text(
                    "UPDATE user_profiles "
                    "SET cooking_time = 'medium (30-60 min)' "
                    "WHERE cooking_time IS NULL OR cooking_time NOT IN "
                    "('short (<30 mins)', 'medium (30-60 min)', 'long (>60 mins)')"
                )
            )

            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profiles_username "
                    "ON user_profiles (username)"
                )
            )
            conn.execute(text("ALTER TABLE user_profiles ALTER COLUMN username SET NOT NULL"))
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profiles_email "
                    "ON user_profiles (email)"
                )
            )
            conn.execute(text("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS username VARCHAR"))
            conn.execute(text("ALTER TABLE meal_plan_history ADD COLUMN IF NOT EXISTS meal_plan JSON"))
    except ProgrammingError:
        # Some environments connect with a non-owner DB user; run_project.sh applies the same SQL via psql owner context.
        pass


run_migrations()
