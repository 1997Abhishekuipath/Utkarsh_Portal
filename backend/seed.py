"""
Standalone idempotent seed runner.
Run manually:   docker-compose exec backend python seed.py
Run in entrypoint: backend/entrypoint.sh calls this before uvicorn.

Sprint A:
- All seed emails moved to @hitachi-systems.com (PRD-compliant domain).
- Migrates legacy @hsi.com users to @hitachi-systems.com on first run.
- Seeded users are pre-approved (is_active=True) so the team can log in immediately.
"""
from dotenv import load_dotenv
load_dotenv()

import os, sys, uuid, time, bcrypt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError


BCRYPT_ROUNDS = int(os.environ.get('BCRYPT_ROUNDS', '12'))


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def wait_for_db(url: str, attempts: int = 30, delay: int = 2):
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
    # Late import so server's Base.metadata.create_all runs first
    from server import UserDB, Base  # noqa

    url = os.environ.get(
        'DATABASE_URL',
        'postgresql://hsi_user:hsi_password123@localhost:5432/hsi_portal',
    )
    engine = wait_for_db(url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()

    # ── Migrate legacy @hsi.com → @hitachi-systems.com (one-time) ────────────
    migrated = 0
    legacy = db.query(UserDB).filter(UserDB.email.like('%@hsi.com')).all()
    for u in legacy:
        new_email = u.email.replace('@hsi.com', '@hitachi-systems.com')
        # avoid collision with already-seeded new email
        if not db.query(UserDB).filter(UserDB.email == new_email).first():
            u.email = new_email
            u.is_active = True
            u.is_verified = True
            migrated += 1
        else:
            db.delete(u)        # duplicate after migration target exists; remove legacy
    if migrated or legacy:
        db.commit()
        print(f"[seed] Legacy domain migration: {migrated} updated, {len(legacy) - migrated} duplicates removed", flush=True)

    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@hitachi-systems.com').lower()
    admin_pw    = os.environ.get('ADMIN_PASSWORD', 'Admin@123')

    seeds = [
        # (name,           email,                              password,        role,         dept,         designation,           xp)
        ('Super Admin',    'superadmin@hitachi-systems.com',   'SuperAdmin@123', 'super_admin', 'Platform',   'Platform Owner',     6000),
        ('Admin User',     admin_email,                        admin_pw,         'admin',       None,         'HR Manager',         5000),
        ('Rohan Kumar',    'manager@hitachi-systems.com',      'Manager@123',    'manager',     'Sales',      'Sales Manager',      4625),
        ('Arjun Mehta',    'employee@hitachi-systems.com',     'Employee@123',   'employee',    'Engineering','Senior Engineer',    2840),
        ('Priya Krishnan', 'priya@hitachi-systems.com',        'Employee@123',   'employee',    'Design',     'UX Lead',            4318),
        ('Kiran Shah',     'kiran@hitachi-systems.com',        'Employee@123',   'employee',    'Engineering','Engineer',           3986),
        ('Ananya Singh',   'ananya@hitachi-systems.com',       'Employee@123',   'employee',    'Marketing',  'Marketing Lead',     2786),
    ]

    created, skipped = [], []
    for name, email, pw, role, dept, designation, xp in seeds:
        if db.query(UserDB).filter(UserDB.email == email).first():
            skipped.append(email); continue
        db.add(UserDB(
            id=str(uuid.uuid4()), name=name, email=email,
            password_hash=hash_pw(pw), role=role, department=dept,
            designation=designation, xp_points=xp,
            is_active=True, is_verified=True, art_tags=[],
        ))
        created.append(email)

    db.commit(); db.close()

    print("\n" + "=" * 72, flush=True)
    print(" HSI Enterprise Portal — Seed Report", flush=True)
    print("=" * 72, flush=True)
    print(f" Created:  {len(created)}  {created or '(none)'}", flush=True)
    print(f" Skipped:  {len(skipped)}  (already existed)", flush=True)
    print("-" * 72, flush=True)
    print(f" Super Admin:  superadmin@hitachi-systems.com / SuperAdmin@123", flush=True)
    print(f" Admin:        {admin_email} / {admin_pw}", flush=True)
    print(f" Manager:      manager@hitachi-systems.com / Manager@123", flush=True)
    print(f" Employee:     employee@hitachi-systems.com / Employee@123", flush=True)
    print("=" * 72 + "\n", flush=True)


if __name__ == '__main__':
    run_seed()
