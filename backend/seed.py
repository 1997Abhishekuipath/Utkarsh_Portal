"""
Standalone seed runner — idempotent.
Run manually:   docker-compose exec backend python seed.py
Run in-process: imported by server.py on startup as a fallback.
"""
from dotenv import load_dotenv
load_dotenv()

import os, sys, uuid, time, bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def wait_for_db(url: str, attempts: int = 30, delay: int = 2):
    """Block until Postgres accepts connections (docker-compose depends_on
    only waits for pg_isready on the db container — in some environments that
    still races ahead of us). Cap at ~60s then fail loudly."""
    engine = create_engine(url, pool_pre_ping=True)
    for i in range(1, attempts + 1):
        try:
            with engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            print(f"[seed] DB reachable on attempt {i}", flush=True)
            return engine
        except OperationalError as e:
            print(f"[seed] DB not ready (attempt {i}/{attempts}): {e.__class__.__name__}", flush=True)
            time.sleep(delay)
    print("[seed] ERROR: Database never became reachable", flush=True)
    sys.exit(1)


def run_seed():
    # Import here so the module works standalone AND imported
    from server import UserDB, Base  # noqa

    url = os.environ.get(
        'DATABASE_URL',
        'postgresql://hsi_user:hsi_password123@localhost:5432/hsi_portal'
    )
    engine = wait_for_db(url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()

    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@hsi.com')
    admin_pw    = os.environ.get('ADMIN_PASSWORD', 'Admin@123')

    seeds = [
        ('Admin User',      admin_email,         admin_pw,         'admin',    None,          5000),
        ('Rohan Kumar',     'manager@hsi.com',   'Manager@123',    'manager',  'Sales',       4625),
        ('Arjun Mehta',     'employee@hsi.com',  'Employee@123',   'employee', 'Engineering', 2840),
        ('Priya Krishnan',  'priya@hsi.com',     'Employee@123',   'employee', 'Design',      4318),
        ('Kiran Shah',      'kiran@hsi.com',     'Employee@123',   'employee', 'Engineering', 3986),
        ('Ananya Singh',    'ananya@hsi.com',    'Employee@123',   'employee', 'Marketing',   2786),
    ]

    created, skipped = [], []
    for name, email, pw, role, dept, xp in seeds:
        existing = db.query(UserDB).filter(UserDB.email == email).first()
        if existing:
            skipped.append(email)
            continue
        db.add(UserDB(
            id=str(uuid.uuid4()),
            name=name, email=email,
            password_hash=hash_pw(pw),
            role=role, department=dept, xp_points=xp,
        ))
        created.append(email)

    db.commit()
    db.close()

    print("\n" + "=" * 68, flush=True)
    print(" HSI Enterprise Portal — Seed Report", flush=True)
    print("=" * 68, flush=True)
    print(f" Created:  {len(created)}  {created or '(none)'}", flush=True)
    print(f" Skipped:  {len(skipped)}  (already existed)", flush=True)
    print("-" * 68, flush=True)
    print(f" Admin login:    {admin_email} / {admin_pw}", flush=True)
    print(f" Manager login:  manager@hsi.com / Manager@123", flush=True)
    print(f" Employee login: employee@hsi.com / Employee@123", flush=True)
    print("=" * 68 + "\n", flush=True)


if __name__ == '__main__':
    run_seed()
