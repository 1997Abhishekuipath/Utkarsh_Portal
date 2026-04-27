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

    # ── Sprint C content seed ────────────────────────────────────────────────
    _seed_content(engine)

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


# ═════════════════════════════════════════════════════════════════════════════
#  Sprint C — Content seeds (Pillars, Icons, EDM, Quotes)
# ═════════════════════════════════════════════════════════════════════════════
def _seed_content(engine):
    from server import PillarDB, PillarIconDB, EdmSlideDB, QuoteDB  # noqa
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()

    pillars_seed = [
        ('customer',    'Customer',    'Listen, measure, and act on customer signals.',
         '#CC0000', '#7A0000', 'Heart',     1),
        ('innovator',   'Innovator',   'Practices, tech days, and ideas worth replicating.',
         '#F97316', '#9A3412', 'Lightbulb', 2),
        ('employee',    'Employee',    'Productivity, learning, recognition, and well-being.',
         '#2563EB', '#1E3A8A', 'Users',     3),
        ('shareholder', 'Shareholder', 'Operations, governance, finance, and analytics.',
         '#059669', '#064E3B', 'TrendingUp',4),
    ]
    pillar_ids = {}
    for slug, name, tagline, gf, gt, icon, pos in pillars_seed:
        existing = db.query(PillarDB).filter(PillarDB.slug == slug).first()
        if existing:
            pillar_ids[slug] = existing.id
            continue
        p = PillarDB(id=str(uuid.uuid4()), slug=slug, name=name, tagline=tagline,
                     gradient_from=gf, gradient_to=gt, icon_name=icon, position=pos,
                     is_published=True)
        db.add(p)
        db.flush()
        pillar_ids[slug] = p.id

    icons_seed = [
        # Customer pillar — includes the existing NPS/CSAT and Action Intelligence pages
        ('customer', 'NPS & CSAT',           'Real-time satisfaction & loyalty', 'Smile',       '/apps/nps-csat',         'hot', 1),
        ('customer', 'Action Intelligence',  'Meetings, follow-ups, surveys',     'Target',      '/apps/survey-builder',   'new', 2),
        ('customer', 'Service Desk',         'Tickets, SLAs, escalations',        'Headphones',  '/apps/service-desk',     None,  3),
        ('customer', 'Help Desk',            'Internal support requests',         'LifeBuoy',    '/apps/help-desk',        None,  4),
        ('customer', 'CRM',                  'Pipeline, leads, accounts',         'Contact',     '/apps/crm',              None,  5),
        ('customer', 'Customer Voice',       'Feedback collection',               'MessageSquare','/apps/customer-voice',  None,  6),

        # Innovator pillar
        ('innovator','Best Practices',       'Proven solutions to replicate',     'Award',       '/apps/best-practices',   'hot', 1),
        ('innovator','Tech Days',            'Showcase innovations & demos',      'Presentation','/apps/tech-days',        None,  2),
        ('innovator','Replications',         'Adopt practices in your account',   'CopyCheck',   '/apps/replications',     None,  3),
        ('innovator','Certifications',       'Skills & knowledge badges',         'GraduationCap','/apps/certifications', None,  4),
        ('innovator','Workflow Automation',  'No-code workflows',                 'Zap',         '/apps/workflow',         'new', 5),
        ('innovator','Innovation Hub',       'Ideas board',                       'Sparkles',    '/apps/innovation',       None,  6),

        # Employee pillar
        ('employee', 'Productivity Hub',     'Tasks, focus, & time tracking',     'CheckSquare', '/apps/productivity',     None,  1),
        ('employee', 'Learning & Development','Courses & paths',                  'BookOpen',    '/apps/learning',         None,  2),
        ('employee', 'Visitor Management',   'Pre-register & host visitors',      'UserCheck',   '/apps/visitors',         None,  3),
        ('employee', 'Email Campaigns',      'Internal comms & campaigns',        'Mail',        '/apps/campaigns',        None,  4),
        ('employee', 'Recognition',          'Kudos, awards, leaderboard',        'Trophy',      '/apps/recognition',      'hot', 5),
        ('employee', 'Wellness',             'Health & well-being',               'Activity',    '/apps/wellness',         None,  6),

        # Shareholder pillar
        ('shareholder','Analytics',          'Cross-org KPIs',                    'BarChart3',   '/apps/analytics',        None,  1),
        ('shareholder','Access Rights',      'Permissions & reviews',             'Shield',      '/apps/access',           None,  2),
        ('shareholder','Finance Reports',    'Revenue, margin, payout',           'IndianRupee', '/apps/finance',          None,  3),
        ('shareholder','Compliance',         'Audits & policies',                 'FileCheck',   '/apps/compliance',       None,  4),
        ('shareholder','Risk Register',      'Operational risks',                 'AlertTriangle','/apps/risk',            None,  5),
        ('shareholder','Board Pack',         'Quarterly reports',                 'FileText',    '/apps/board',            'new', 6),
    ]
    for slug, name, desc, icon, route, badge, pos in icons_seed:
        pid = pillar_ids.get(slug)
        if not pid:
            continue
        if db.query(PillarIconDB).filter(PillarIconDB.pillar_id == pid,
                                         PillarIconDB.name == name).first():
            continue
        db.add(PillarIconDB(id=str(uuid.uuid4()), pillar_id=pid, name=name,
                            description=desc, lucide_icon=icon, route=route,
                            badge=badge, position=pos, is_published=True))

    edm_seed = [
        ('home', 'Q1 Incentives Paid',
         'Total payout ₹2.04 cr — congratulations to 312 contributors',
         '#CC0000', '#7A0000', None, '/apps/recognition', 1),
        ('home', 'New: Workflow Automation Beta',
         'Enrol now for early access — limited to 200 seats',
         '#F97316', '#9A3412', None, '/apps/workflow', 2),
        ('home', 'Tech Day — Bangalore GEC',
         'Apr 30 · 9 AM · 2-hour innovation showcase',
         '#2563EB', '#1E3A8A', None, '/apps/tech-days', 3),

        ('customer', '30 NPS Drives Launched',
         'See which surveys are running & their response rates',
         '#CC0000', '#7A0000', None, '/apps/nps-csat', 1),
        ('innovator','80+ Best Practices Live',
         'Replicate proven solutions in your account',
         '#F97316', '#9A3412', None, '/apps/best-practices', 1),
        ('employee', 'Wellness Week — May',
         '5 days of mindfulness, fitness & nutrition challenges',
         '#2563EB', '#1E3A8A', None, '/apps/wellness', 1),
        ('shareholder','FY26 Q1 Board Pack',
         'Revenue, margin & strategic milestones',
         '#059669', '#064E3B', None, '/apps/board', 1),
    ]
    for scope, title, subtitle, gf, gt, img, link, pos in edm_seed:
        if db.query(EdmSlideDB).filter(EdmSlideDB.scope == scope,
                                       EdmSlideDB.title == title).first():
            continue
        db.add(EdmSlideDB(id=str(uuid.uuid4()), scope=scope, title=title,
                          subtitle=subtitle, gradient_from=gf, gradient_to=gt,
                          image_url=img, link=link, position=pos, is_published=True))

    quotes_seed = [
        ("The best way to predict the future is to build it.", "Alan Kay", 1),
        ("Innovation distinguishes between a leader and a follower.", "Steve Jobs", 2),
        ("Quality is not an act, it is a habit.", "Aristotle", 3),
        ("Customers don't expect you to be perfect. They do expect you to fix things when they go wrong.", "Donald Porter", 4),
        ("Alone we can do so little; together we can do so much.", "Helen Keller", 5),
    ]
    for text, author, pos in quotes_seed:
        if db.query(QuoteDB).filter(QuoteDB.text == text).first():
            continue
        db.add(QuoteDB(id=str(uuid.uuid4()), text=text, author=author,
                       position=pos, is_published=True))

    db.commit()
    n_pillars = db.query(PillarDB).count()
    n_icons   = db.query(PillarIconDB).count()
    n_edm     = db.query(EdmSlideDB).count()
    n_quotes  = db.query(QuoteDB).count()
    db.close()
    print(f"[seed] Content: {n_pillars} pillars, {n_icons} icons, {n_edm} EDM slides, {n_quotes} quotes",
          flush=True)


if __name__ == '__main__':
    run_seed()
