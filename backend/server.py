from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Boolean
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
import os, logging, uuid, bcrypt, jwt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional
from pathlib import Path

ROOT_DIR = Path(__file__).parent

# ── PostgreSQL ────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://hsi_user:hsi_password123@localhost:5432/hsi_portal'
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

# ── JWT ───────────────────────────────────────────────────────────────────────
JWT_SECRET = os.environ.get('JWT_SECRET', 'hsi-change-me-in-production')
JWT_ALGO   = 'HS256'

# ── DB Models ─────────────────────────────────────────────────────────────────
class UserDB(Base):
    __tablename__ = 'users'
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name          = Column(String, nullable=False)
    email         = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role          = Column(String, default='employee')  # admin|manager|employee
    department    = Column(String, nullable=True)
    xp_points     = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class RegisterReq(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = 'employee'
    department: Optional[str] = None

class LoginReq(BaseModel):
    email: EmailStr
    password: str

# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_pw(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def make_token(user_id: str, email: str, role: str) -> str:
    return jwt.encode(
        {'sub': user_id, 'email': email, 'role': role,
         'exp': datetime.now(timezone.utc) + timedelta(hours=24), 'type': 'access'},
        JWT_SECRET, algorithm=JWT_ALGO
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> UserDB:
    token = request.cookies.get('access_token')
    if not token:
        hdr = request.headers.get('Authorization', '')
        if hdr.startswith('Bearer '):
            token = hdr[7:]
    if not token:
        raise HTTPException(status_code=401, detail='Not authenticated')
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get('type') != 'access':
            raise HTTPException(status_code=401, detail='Invalid token type')
        user = db.query(UserDB).filter(UserDB.id == payload['sub']).first()
        if not user:
            raise HTTPException(status_code=401, detail='User not found')
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expired')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail='Invalid token')

def user_to_dict(u: UserDB) -> dict:
    return {'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role,
            'department': u.department, 'xp_points': u.xp_points}

# ── Seed ──────────────────────────────────────────────────────────────────────
def seed_users():
    db = SessionLocal()
    seeds = [
        ('Admin User',  os.environ.get('ADMIN_EMAIL', 'admin@hsi.com'),
         os.environ.get('ADMIN_PASSWORD', 'Admin@123'), 'admin', None, 5000),
        ('Arjun Mehta', 'employee@hsi.com', 'Employee@123', 'employee', 'Engineering', 2840),
        ('Rohan Kumar',  'manager@hsi.com',  'Manager@123',  'manager',  'Sales', 4625),
        ('Priya Krishnan', 'priya@hsi.com', 'Employee@123', 'employee', 'Design', 4318),
        ('Kiran Shah',   'kiran@hsi.com',   'Employee@123', 'employee', 'Engineering', 3986),
        ('Ananya Singh', 'ananya@hsi.com',  'Employee@123', 'employee', 'Marketing', 2786),
    ]
    for name, email, pw, role, dept, xp in seeds:
        if not db.query(UserDB).filter(UserDB.email == email).first():
            db.add(UserDB(id=str(uuid.uuid4()), name=name, email=email,
                          password_hash=hash_pw(pw), role=role, department=dept, xp_points=xp))
    db.commit()
    db.close()

# In Docker production, seeding runs via entrypoint.sh → seed.py (before uvicorn).
# For local dev / supervisor-managed runs, seed on import as well (idempotent).
if os.environ.get('SKIP_SEED_ON_IMPORT') != '1':
    try:
        seed_users()
    except Exception as e:
        logging.warning(f"Seed-on-import failed (safe to ignore in Docker): {e}")

# ── FastAPI ───────────────────────────────────────────────────────────────────
app    = FastAPI(title='HSI Enterprise Portal')
router = APIRouter(prefix='/api')

# ── Auth endpoints ────────────────────────────────────────────────────────────
@router.post('/auth/register')
def register(data: RegisterReq, db: Session = Depends(get_db)):
    if db.query(UserDB).filter(UserDB.email == data.email.lower()).first():
        raise HTTPException(400, 'Email already registered')
    if data.role not in ('admin', 'manager', 'employee'):
        raise HTTPException(400, 'Invalid role. Must be admin, manager, or employee')
    u = UserDB(id=str(uuid.uuid4()), name=data.name, email=data.email.lower(),
               password_hash=hash_pw(data.password), role=data.role,
               department=data.department, xp_points=0)
    db.add(u); db.commit(); db.refresh(u)
    return {'access_token': make_token(u.id, u.email, u.role),
            'token_type': 'bearer', 'user': user_to_dict(u)}

@router.post('/auth/login')
def login(data: LoginReq, db: Session = Depends(get_db)):
    u = db.query(UserDB).filter(UserDB.email == data.email.lower()).first()
    if not u or not verify_pw(data.password, u.password_hash):
        raise HTTPException(401, 'Invalid email or password')
    return {'access_token': make_token(u.id, u.email, u.role),
            'token_type': 'bearer', 'user': user_to_dict(u)}

@router.post('/auth/logout')
def logout(_u: UserDB = Depends(get_current_user)):
    return {'message': 'Logged out successfully'}

@router.get('/auth/me')
def me(u: UserDB = Depends(get_current_user)):
    return user_to_dict(u)

# ── Dashboard endpoints (static mock data) ────────────────────────────────────
@router.get('/dashboard/stats')
def stats(u: UserDB = Depends(get_current_user)):
    return {
        'best_practices': {'count': 80,   'trend': '+5%',  'label': 'BEST PRACTICES',  'sub': 'Applications Submitted'},
        'efforts':        {'count': u.xp_points, 'trend': '+12%', 'label': 'EFFORTS (XP)', 'sub': 'LPSubmissions-Run.in'},
        'xp_incentive':   {'amount': 8400,'trend': '+8%',  'label': 'XP INCENTIVE',     'sub': 'Payout in Q1'},
        'tech_days':      {'count': 8,    'trend': 'New',  'label': 'TECH DAYS',        'sub': '10 days'},
        'pending_actions':{'count': 3,    'trend': 'Due',  'label': 'PENDING ACTIONS',  'sub': 'Action needed'}
    }

@router.get('/dashboard/activities')
def activities(_u: UserDB = Depends(get_current_user)):
    return [
        {'id':'1','user':'Kiran Shah','action':'submitted new best practice — API Unified Base Stability Platform. 185 XP pending approval.','category':'Best Practices','time':'2 hours ago','type':'submission','color':'red'},
        {'id':'2','user':'You','action':'approved Forms: final record submission: Registration. Forwarded to HBS Villiers Singh.','category':'Best Practices','time':'1 day ago','type':'approval','color':'green'},
        {'id':'3','user':'Nikhil Patil','action':'tagged Tech Day — GandyFor/Pharma with 3 prospects. 35 XP submitted.','category':'Tech Days','time':'2 days ago','type':'tag','color':'blue'},
        {'id':'4','user':'Visitor pre-registration','action':'Piyami recently 20 guests/participants for Apr 30. 4,500 XP.','category':'Visitors','time':'3 days ago','type':'visitor','color':'teal'},
        {'id':'5','user':'Sundar Vs','action':'completed in Productivity Hub, 678 tasks delivered. Yesterday 42 XP.','category':'Productivity','time':'4 days ago','type':'task','color':'amber'},
        {'id':'6','user':'Access review','action':'completed for 500 users — 96 accounts verified, 2 flagged for review.','category':'Access Rights','time':'Yesterday','type':'review','color':'gray'}
    ]

@router.get('/dashboard/leaderboard')
def leaderboard(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(UserDB).order_by(UserDB.xp_points.desc()).limit(10).all()
    return [{'rank': i+1, 'name': usr.name, 'role': usr.role.capitalize(),
             'xp': usr.xp_points, 'is_current_user': usr.id == u.id,
             'initials': ''.join(p[0].upper() for p in usr.name.split()[:2])}
            for i, usr in enumerate(users)]

@router.get('/dashboard/announcements')
def announcements(_u: UserDB = Depends(get_current_user)):
    return [
        {'id':'1','title':'Incentives Paid','body':'Q1-2025 incentives paid. Total payout: ₹2,04,000. Check your statement.','date':'Apr 17','color':'green'},
        {'id':'2','title':'New Module: Workflow Automation — Beta','body':'Workflow Automation module live for testing. Enrollment needed for early access.','date':'Apr 15','color':'blue'},
        {'id':'3','title':'Best Practices — 30 Active Practices','body':'Active practices reached 30 this quarter. Congratulations to all contributors.','date':'Apr 11','color':'red'},
        {'id':'4','title':'Visitor Management Go-Live','body':'Visitor Management module is now live. Please update all visitor registrations.','date':'Apr 9','color':'teal'}
    ]

@router.get('/dashboard/pending-actions')
def pending(_u: UserDB = Depends(get_current_user)):
    return [
        {'id':'1','title':'Approve Resubmission: Replication','category':'Best Practices','priority':'high'},
        {'id':'2','title':'Confirm Trip/Rider/Visitor - Apr 30','category':'Visitors','priority':'medium'},
        {'id':'3','title':'Submit Tech Day attendance proof','category':'Tech Days','priority':'high'}
    ]

@router.get('/dashboard/upcoming')
def upcoming(_u: UserDB = Depends(get_current_user)):
    return [
        {'id':'1','title':'Tech Day — All For SPTS','description':'Bangalore, GEC • 2 Hrs','date':'Apr 30, 9:00 AM','color':'red'},
        {'id':'2','title':'Visitor — Bajaj Finance','description':'6 Guests','date':'Apr 30, 2:00 PM','color':'blue'},
        {'id':'3','title':'365 Incentive Payout','description':'Finance Dept','date':'May 1','color':'green'}
    ]

@router.get('/dashboard/score')
def score(u: UserDB = Depends(get_current_user)):
    return {
        'percentage': 65,
        'total_xp': u.xp_points,
        'breakdown': [
            {'label': 'Practices',    'value': 7, 'bar': 70},
            {'label': 'Publications', 'value': 4, 'bar': 40},
            {'label': 'Tech Days',    'value': 8, 'bar': 80}
        ]
    }

# ── Admin endpoints ───────────────────────────────────────────────────────────
@router.get('/admin/users')
def get_users(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    if u.role != 'admin':
        raise HTTPException(403, 'Admin access required')
    return [{'id': usr.id, 'name': usr.name, 'email': usr.email, 'role': usr.role,
             'xp_points': usr.xp_points, 'department': usr.department,
             'created_at': usr.created_at.isoformat() if usr.created_at else None,
             'is_active': usr.is_active}
            for usr in db.query(UserDB).order_by(UserDB.created_at.desc()).all()]

@router.delete('/admin/users/{user_id}')
def delete_user(user_id: str, u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    if u.role != 'admin':
        raise HTTPException(403, 'Admin access required')
    target = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not target:
        raise HTTPException(404, 'User not found')
    if target.id == u.id:
        raise HTTPException(400, 'Cannot delete your own account')
    db.delete(target); db.commit()
    return {'message': 'User deleted successfully'}

@router.put('/admin/users/{user_id}/role')
def update_role(user_id: str, body: dict, u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    if u.role != 'admin':
        raise HTTPException(403, 'Admin access required')
    target = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not target:
        raise HTTPException(404, 'User not found')
    new_role = body.get('role')
    if new_role not in ('admin', 'manager', 'employee'):
        raise HTTPException(400, 'Invalid role')
    target.role = new_role
    db.commit()
    return {'message': 'Role updated', 'role': new_role}

@router.get('/')
def root():
    return {'message': 'HSI Enterprise Portal API v1.0', 'status': 'running'}

# ── Mount & Middleware ────────────────────────────────────────────────────────
app.include_router(router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
