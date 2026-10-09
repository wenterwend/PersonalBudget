import os
from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy.engine import Engine
from sqlalchemy import event

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./budget.db")

# Enable WAL mode and foreign keys for SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.close()

def backup_database_if_exists():
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
            import shutil, datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{db_path}.bak_{timestamp}"
            shutil.copy2(db_path, backup_path)

def init_db():
    backup_database_if_exists()
    SQLModel.metadata.create_all(engine)


    # Light schema migration for SQLite databases
    if DATABASE_URL.startswith("sqlite"):
        with engine.connect() as conn:
            cat_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(categories)").fetchall()]
            if cat_cols and "is_fixed" not in cat_cols:
                conn.exec_driver_sql("ALTER TABLE categories ADD COLUMN is_fixed BOOLEAN DEFAULT 0")
                conn.commit()

            rules_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(rules)").fetchall()]
            if rules_cols:
                if "amount_condition" not in rules_cols:
                    conn.exec_driver_sql("ALTER TABLE rules ADD COLUMN amount_condition VARCHAR DEFAULT 'any'")
                if "secondary_match_field" not in rules_cols:
                    conn.exec_driver_sql("ALTER TABLE rules ADD COLUMN secondary_match_field VARCHAR")
                if "secondary_match_type" not in rules_cols:
                    conn.exec_driver_sql("ALTER TABLE rules ADD COLUMN secondary_match_type VARCHAR")
                if "secondary_match_value" not in rules_cols:
                    conn.exec_driver_sql("ALTER TABLE rules ADD COLUMN secondary_match_value VARCHAR")

                # Normalize any legacy uppercase Enum strings in rules table
                conn.exec_driver_sql("UPDATE rules SET amount_condition = LOWER(amount_condition) WHERE amount_condition IS NOT NULL")
                conn.exec_driver_sql("UPDATE rules SET match_field = LOWER(match_field) WHERE match_field IS NOT NULL")
                conn.exec_driver_sql("UPDATE rules SET match_type = LOWER(match_type) WHERE match_type IS NOT NULL")
                conn.commit()

def get_session():
    with Session(engine) as session:
        yield session
