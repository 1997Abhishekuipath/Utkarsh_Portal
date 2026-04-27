"""
HSI Enterprise Portal — Backend API
Stack: FastAPI + SQLAlchemy 2.0 + PostgreSQL + JWT (access + refresh rotation)

Sprint A — Auth foundation hardened:
- bcrypt cost 12
- Domain-locked registration (ALLOWED_DOMAIN env)
- 4 roles: employee | manager | admin | super_admin
- Pending admin approval before is_active=True
- Account lockout: 5 failed attempts → 15 min
- Sessions table with refresh-token rotation (15min access / 30d refresh)
- Audit log for all auth + admin actions
- otp_codes table (Sprint B will wire SMTP delivery)
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import (
    create_engine, Column, String, DateTime, Date, Integer, BigInteger,
    Boolean, ForeignKey, CheckConstraint, Index, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
import os, logging, uuid, bcrypt, jwt, hashlib, secrets, random, re
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from pathlib import Path

from services.email import send_otp as ses_send_otp, is_configured as ses_is_configured
from services.rate_limit import check_or_raise as rl_check, is_redis_active

ROOT_DIR = Path(__file__).parent

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL    = os.environ.get('DATABASE_URL',
                                 'postgresql://hsi_user:hsi_password123@localhost:5432/hsi_portal')
JWT_SECRET      = os.environ.get('JWT_SECRET', 'hsi-change-me-in-production')
JWT_REFRESH_SECRET = os.environ.get('JWT_REFRESH_SECRET', JWT_SECRET + '-refresh')
JWT_ALGO        = 'HS256'
ALLOWED_DOMAIN  = os.environ.get('ALLOWED_DOMAIN', 'hitachi-systems.com').lower().lstrip('@')
BCRYPT_ROUNDS   = int(os.environ.get('BCRYPT_ROUNDS', '12'))
ACCESS_TTL_MIN  = int(os.environ.get('ACCESS_TTL_MIN', '15'))
REFRESH_TTL_DAY = int(os.environ.get('REFRESH_TTL_DAY', '30'))
LOCKOUT_FAILS   = int(os.environ.get('LOCKOUT_FAILS', '5'))
LOCKOUT_MIN     = int(os.environ.get('LOCKOUT_MIN', '15'))
MFA_ENABLED     = os.environ.get('MFA_ENABLED', 'false').lower() in ('1', 'true', 'yes')
OTP_LENGTH      = int(os.environ.get('OTP_LENGTH', '6'))
OTP_TTL_MIN     = int(os.environ.get('OTP_TTL_MIN', '10'))
OTP_MAX_ATTEMPTS = int(os.environ.get('OTP_MAX_ATTEMPTS', '3'))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ── DB Models ─────────────────────────────────────────────────────────────────
class UserDB(Base):
    __tablename__ = 'users'
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name            = Column(String, nullable=False)              # PRD: full_name
    display_name    = Column(String, nullable=True)
    employee_id     = Column(String, unique=True, nullable=True)
    email           = Column(String, unique=True, index=True, nullable=False)
    password_hash   = Column(String, nullable=False)
    role            = Column(String, default='employee', nullable=False)
    department      = Column(String, nullable=True)
    practice        = Column(String, nullable=True)
    designation     = Column(String, nullable=True)
    art_tags        = Column(ARRAY(String), nullable=True, default=list)
    avatar_url      = Column(String, nullable=True)
    phone           = Column(String, nullable=True)
    date_of_birth   = Column(Date, nullable=True)
    date_joined     = Column(Date, default=lambda: datetime.now(timezone.utc).date())
    xp_points       = Column(Integer, default=0)                  # legacy total; will move to xp_ledger
    is_active       = Column(Boolean, default=False)              # requires admin approval
    is_verified     = Column(Boolean, default=False)              # email verified via OTP (Sprint B)
    approved_by     = Column(String, ForeignKey('users.id'), nullable=True)
    approved_at     = Column(DateTime(timezone=True), nullable=True)
    last_login_at   = Column(DateTime(timezone=True), nullable=True)
    failed_attempts = Column(Integer, default=0)
    locked_until    = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime(timezone=True),
                             default=lambda: datetime.now(timezone.utc),
                             onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("role IN ('employee','manager','admin','super_admin')", name='chk_user_role'),
        CheckConstraint("email ILIKE '%@hitachi-systems.com'", name='chk_user_email_domain'),
    )


class SessionDB(Base):
    """Refresh-token store with device/IP tracking. Access tokens reference sess id."""
    __tablename__ = 'sessions'
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id       = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    refresh_hash  = Column(String, unique=True, nullable=False, index=True)  # SHA-256 of refresh token
    device_type   = Column(String, nullable=True)   # mobile|web|admin
    ip_address    = Column(String, nullable=True)
    user_agent    = Column(String, nullable=True)
    is_active     = Column(Boolean, default=True)
    expires_at    = Column(DateTime(timezone=True), nullable=False)
    last_used_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    revoked_at    = Column(DateTime(timezone=True), nullable=True)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OtpCodeDB(Base):
    """Email OTP store. SMTP delivery wired in Sprint B (AWS SES)."""
    __tablename__ = 'otp_codes'
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id     = Column(String, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    email       = Column(String, nullable=False, index=True)
    code_hash   = Column(String, nullable=False)                  # SHA-256 of 6-digit code
    purpose     = Column(String, nullable=False)                  # login|register|reset_password|admin_action
    attempts    = Column(Integer, default=0)
    is_used     = Column(Boolean, default=False)
    expires_at  = Column(DateTime(timezone=True), nullable=False)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "purpose IN ('login','register','reset_password','admin_action')",
            name='chk_otp_purpose'),
    )


class AuditLogDB(Base):
    """Append-only audit trail. PRD §4.4 — all auth events + admin actions."""
    __tablename__ = 'audit_log'
    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id       = Column(String, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    actor_email   = Column(String, nullable=True)
    action        = Column(String, nullable=False, index=True)
    target_type   = Column(String, nullable=True)
    target_id     = Column(String, nullable=True)
    ip_address    = Column(String, nullable=True)
    user_agent    = Column(String, nullable=True)
    details       = Column(JSONB, nullable=True)
    status        = Column(String, nullable=True)                 # success|failure
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


Base.metadata.create_all(bind=engine)


# ── Idempotent post-migrate steps ─────────────────────────────────────────────
def _ensure_domain_check_constraint():
    """SQLAlchemy create_all does not retro-add CHECK constraints to existing
    tables. This adds the email-domain CHECK on first run if missing."""
    domain = ALLOWED_DOMAIN.replace("'", "''")
    sql = f"""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'chk_user_email_domain'
        ) THEN
            BEGIN
                ALTER TABLE users
                ADD CONSTRAINT chk_user_email_domain
                CHECK (email ILIKE '%@{domain}');
            EXCEPTION WHEN check_violation THEN
                RAISE NOTICE 'Some existing users violate domain check; skipping';
            END;
        END IF;
    END$$;
    """
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
    except Exception as e:                                          # noqa: BLE001
        logging.warning(f"[migration] domain CHECK setup skipped: {e}")


_ensure_domain_check_constraint()


# ── Pydantic Schemas ──────────────────────────────────────────────────────────
class RegisterReq(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Optional[str] = 'employee'
    department: Optional[str] = None
    employee_id: Optional[str] = None
    designation: Optional[str] = None


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class RefreshReq(BaseModel):
    refresh_token: str


class CheckEmailReq(BaseModel):
    email: EmailStr


class ApproveUserReq(BaseModel):
    role: Optional[str] = None        # optional override on approval


class VerifyOtpReq(BaseModel):
    email: EmailStr
    code: str
    purpose: str = 'login'            # login|register|reset_password


class ResendOtpReq(BaseModel):
    email: EmailStr
    purpose: str = 'login'


class ForgotPasswordReq(BaseModel):
    email: EmailStr


class ResetPasswordReq(BaseModel):
    email: EmailStr
    code: str
    new_password: str


# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_pw(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def validate_domain(email: str) -> None:
    if ALLOWED_DOMAIN and not email.lower().endswith(f"@{ALLOWED_DOMAIN}"):
        raise HTTPException(400, f"Email must end with @{ALLOWED_DOMAIN}")


def make_access_token(user_id: str, email: str, role: str, sess_id: str) -> str:
    return jwt.encode(
        {'sub': user_id, 'email': email, 'role': role, 'sess': sess_id,
         'exp': datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TTL_MIN),
         'iat': datetime.now(timezone.utc), 'iss': 'hsi-platform', 'type': 'access'},
        JWT_SECRET, algorithm=JWT_ALGO,
    )


# ── OTP helpers ───────────────────────────────────────────────────────────────
def _generate_otp() -> str:
    return ''.join(secrets.choice('0123456789') for _ in range(OTP_LENGTH))


def _create_and_send_otp(db: Session, email: str, purpose: str,
                         user_id: Optional[str] = None) -> dict:
    """Generate, store, and email an OTP. Invalidates prior OTPs for the same
    email+purpose. Returns {'otp_id': str, 'expires_in_sec': int, 'email_sent': bool}.
    """
    # Invalidate any active OTPs for this email+purpose
    now = datetime.now(timezone.utc)
    db.query(OtpCodeDB).filter(
        OtpCodeDB.email == email,
        OtpCodeDB.purpose == purpose,
        OtpCodeDB.is_used == False,                                # noqa: E712
    ).update({'is_used': True})
    db.commit()

    code = _generate_otp()
    rec = OtpCodeDB(
        id=str(uuid.uuid4()), user_id=user_id, email=email,
        code_hash=sha256_hex(code), purpose=purpose,
        expires_at=now + timedelta(minutes=OTP_TTL_MIN),
    )
    db.add(rec); db.commit(); db.refresh(rec)

    sent, _ = ses_send_otp(email, code, purpose=purpose)
    return {'otp_id': rec.id, 'expires_in_sec': OTP_TTL_MIN * 60, 'email_sent': sent}


def _verify_otp(db: Session, email: str, code: str, purpose: str) -> OtpCodeDB:
    now = datetime.now(timezone.utc)
    rec = (db.query(OtpCodeDB)
             .filter(OtpCodeDB.email == email, OtpCodeDB.purpose == purpose,
                     OtpCodeDB.is_used == False)                   # noqa: E712
             .order_by(OtpCodeDB.created_at.desc())
             .first())
    if not rec or rec.expires_at <= now:
        raise HTTPException(400, 'OTP expired or not found. Request a new code.')
    if rec.attempts >= OTP_MAX_ATTEMPTS:
        rec.is_used = True; db.commit()
        raise HTTPException(429, 'Too many attempts. Request a new code.')
    rec.attempts += 1
    if rec.code_hash != sha256_hex(code):
        db.commit()
        remaining = OTP_MAX_ATTEMPTS - rec.attempts
        raise HTTPException(400, f"Invalid code. {remaining} attempt(s) remaining.")
    rec.is_used = True
    db.commit()
    return rec


def make_refresh_token() -> str:
    return secrets.token_urlsafe(48)   # opaque token; we hash + store in sessions


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def client_meta(request: Request) -> dict:
    fwd = request.headers.get('x-forwarded-for', '')
    ip = fwd.split(',')[0].strip() if fwd else (request.client.host if request.client else None)
    return {'ip': ip, 'ua': request.headers.get('user-agent', '')[:300]}


def audit(db: Session, *, user_id: Optional[str], actor_email: Optional[str],
          action: str, status: str, request: Request,
          target_type: Optional[str] = None, target_id: Optional[str] = None,
          details: Optional[dict] = None):
    meta = client_meta(request)
    db.add(AuditLogDB(
        user_id=user_id, actor_email=actor_email, action=action, status=status,
        target_type=target_type, target_id=target_id,
        ip_address=meta['ip'], user_agent=meta['ua'], details=details or {},
    ))
    db.commit()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> UserDB:
    token = request.cookies.get('access_token')
    if not token:
        hdr = request.headers.get('Authorization', '')
        if hdr.startswith('Bearer '):
            token = hdr[7:]
    if not token:
        raise HTTPException(401, 'Not authenticated')
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get('type') != 'access':
            raise HTTPException(401, 'Invalid token type')
        # Verify session is still active
        sess_id = payload.get('sess')
        if sess_id:
            sess = db.query(SessionDB).filter(SessionDB.id == sess_id).first()
            if not sess or not sess.is_active:
                raise HTTPException(401, 'Session revoked')
        user = db.query(UserDB).filter(UserDB.id == payload['sub']).first()
        if not user or not user.is_active:
            raise HTTPException(401, 'User not found or inactive')
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, 'Token expired')
    except jwt.InvalidTokenError:
        raise HTTPException(401, 'Invalid token')


def require_role(*allowed):
    def _dep(u: UserDB = Depends(get_current_user)) -> UserDB:
        if u.role not in allowed:
            raise HTTPException(403, f"Requires role: {', '.join(allowed)}")
        return u
    return _dep


def user_to_dict(u: UserDB) -> dict:
    return {
        'id': u.id, 'name': u.name, 'display_name': u.display_name,
        'email': u.email, 'role': u.role, 'department': u.department,
        'practice': u.practice, 'designation': u.designation,
        'employee_id': u.employee_id, 'avatar_url': u.avatar_url,
        'art_tags': list(u.art_tags or []), 'xp_points': u.xp_points,
        'is_active': u.is_active, 'is_verified': u.is_verified,
        'last_login_at': u.last_login_at.isoformat() if u.last_login_at else None,
    }


# ── FastAPI ───────────────────────────────────────────────────────────────────
app    = FastAPI(title='HSI Enterprise Portal API', version='1.0.0')
router = APIRouter(prefix='/api')


# ── Auth endpoints ────────────────────────────────────────────────────────────
@router.post('/auth/check-email')
def check_email(data: CheckEmailReq, db: Session = Depends(get_db)):
    """Pre-flight check: domain valid + does user exist + is_active."""
    email = data.email.lower()
    try:
        validate_domain(email)
    except HTTPException:
        return {'domain_ok': False, 'exists': False, 'is_active': False}
    u = db.query(UserDB).filter(UserDB.email == email).first()
    return {'domain_ok': True, 'exists': u is not None,
            'is_active': bool(u and u.is_active)}


@router.post('/auth/register')
def register(data: RegisterReq, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    validate_domain(email)
    if data.role not in ('employee', 'manager'):
        # Public registration only allows employee or manager. Admins are seeded.
        raise HTTPException(400, 'Role must be employee or manager')
    if db.query(UserDB).filter(UserDB.email == email).first():
        raise HTTPException(400, 'Email already registered')

    u = UserDB(
        id=str(uuid.uuid4()), name=data.name, email=email,
        password_hash=hash_pw(data.password), role=data.role,
        department=data.department, employee_id=data.employee_id,
        designation=data.designation,
        is_active=False, is_verified=False,                       # awaiting admin approval
    )
    db.add(u); db.commit(); db.refresh(u)
    audit(db, user_id=u.id, actor_email=u.email, action='register',
          status='success', request=request)
    return {
        'message': 'Registration submitted. Your account is pending admin approval.',
        'user': user_to_dict(u),
        'pending_approval': True,
    }


def _create_session(db: Session, user: UserDB, request: Request) -> tuple[str, str]:
    """Create a session row + return (access_token, refresh_token_plain)."""
    refresh = make_refresh_token()
    refresh_h = sha256_hex(refresh)
    meta = client_meta(request)
    sess = SessionDB(
        id=str(uuid.uuid4()), user_id=user.id, refresh_hash=refresh_h,
        device_type='web', ip_address=meta['ip'], user_agent=meta['ua'],
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAY),
    )
    db.add(sess); db.commit(); db.refresh(sess)
    access = make_access_token(user.id, user.email, user.role, sess.id)
    return access, refresh


@router.post('/auth/login')
def login(data: LoginReq, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    validate_domain(email)

    # Rate limit: 10 login attempts per minute per IP (PRD §4.4)
    meta = client_meta(request)
    rl_check('login', meta['ip'] or 'unknown', 10, 60,
             detail='Too many login attempts. Try again in a minute.')

    u = db.query(UserDB).filter(UserDB.email == email).first()

    # Lockout check (PRD §4.4)
    now = datetime.now(timezone.utc)
    if u and u.locked_until and u.locked_until > now:
        audit(db, user_id=u.id, actor_email=email, action='login_locked',
              status='failure', request=request,
              details={'locked_until': u.locked_until.isoformat()})
        raise HTTPException(423, f'Account locked until {u.locked_until.isoformat()}')

    if not u or not verify_pw(data.password, u.password_hash):
        if u:
            u.failed_attempts = (u.failed_attempts or 0) + 1
            if u.failed_attempts >= LOCKOUT_FAILS:
                u.locked_until = now + timedelta(minutes=LOCKOUT_MIN)
            db.commit()
        audit(db, user_id=u.id if u else None, actor_email=email,
              action='login_failed', status='failure', request=request)
        raise HTTPException(401, 'Invalid email or password')

    if not u.is_active:
        audit(db, user_id=u.id, actor_email=email, action='login_inactive',
              status='failure', request=request)
        raise HTTPException(403, 'Account pending admin approval')

    # Password OK + active. Reset lockout counters early.
    u.failed_attempts = 0
    u.locked_until = None
    db.commit()

    if MFA_ENABLED:
        # Rate limit OTP issuance: 5 per hour per email (PRD §4.4)
        rl_check('otp_send', email, 5, 3600,
                 detail='Too many OTP requests. Try again later.')
        info = _create_and_send_otp(db, email, purpose='login', user_id=u.id)
        audit(db, user_id=u.id, actor_email=email, action='login_otp_sent',
              status='success', request=request,
              details={'otp_id': info['otp_id'], 'email_sent': info['email_sent']})
        return {
            'requires_otp': True,
            'message': 'Verification code sent to your email.',
            'email': email,
            'otp_id': info['otp_id'],
            'expires_in_sec': info['expires_in_sec'],
            'email_sent': info['email_sent'],
        }

    # MFA disabled — issue tokens immediately (current default; switch off in prod)
    u.last_login_at = now
    db.commit()
    access, refresh = _create_session(db, u, request)
    audit(db, user_id=u.id, actor_email=email, action='login_success',
          status='success', request=request, details={'mfa': False})
    return {
        'access_token': access, 'refresh_token': refresh,
        'token_type': 'bearer', 'user': user_to_dict(u),
    }


@router.post('/auth/verify-otp')
def verify_otp(data: VerifyOtpReq, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    validate_domain(email)
    purpose = data.purpose
    if purpose not in ('login', 'register', 'reset_password'):
        raise HTTPException(400, 'Invalid purpose')

    # Rate limit verify: 5/min per email
    rl_check('otp_verify', email, 5, 60,
             detail='Too many verification attempts. Slow down.')

    rec = _verify_otp(db, email, data.code, purpose)

    u = db.query(UserDB).filter(UserDB.email == email).first()
    if not u or not u.is_active:
        raise HTTPException(403, 'User not found or inactive')

    if purpose == 'login':
        u.last_login_at = datetime.now(timezone.utc)
        db.commit()
        access, refresh = _create_session(db, u, request)
        audit(db, user_id=u.id, actor_email=email, action='login_success',
              status='success', request=request, details={'mfa': True, 'otp_id': rec.id})
        return {'access_token': access, 'refresh_token': refresh,
                'token_type': 'bearer', 'user': user_to_dict(u)}

    if purpose == 'register':
        u.is_verified = True
        db.commit()
        audit(db, user_id=u.id, actor_email=email, action='email_verified',
              status='success', request=request)
        return {'message': 'Email verified', 'user': user_to_dict(u)}

    # reset_password: caller must use /auth/reset-password (which re-verifies + sets pw)
    raise HTTPException(400, 'Use /auth/reset-password to complete password reset')


@router.post('/auth/resend-otp')
def resend_otp(data: ResendOtpReq, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    validate_domain(email)
    if data.purpose not in ('login', 'register', 'reset_password'):
        raise HTTPException(400, 'Invalid purpose')

    # Rate limit: 5/hour/email + 1/30s/email throttle
    rl_check('otp_send', email, 5, 3600,
             detail='Too many OTP requests. Try again later.')
    rl_check('otp_resend', email, 1, 30,
             detail='Please wait before requesting another code.')

    u = db.query(UserDB).filter(UserDB.email == email).first()
    # Don't leak existence on resend; always return generic success
    if u and u.is_active:
        info = _create_and_send_otp(db, email, purpose=data.purpose, user_id=u.id)
        audit(db, user_id=u.id, actor_email=email, action=f'{data.purpose}_otp_resent',
              status='success', request=request, details={'otp_id': info['otp_id']})
    return {'message': 'If the account exists, a new code has been sent.',
            'expires_in_sec': OTP_TTL_MIN * 60}


@router.post('/auth/forgot-password')
def forgot_password(data: ForgotPasswordReq, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    validate_domain(email)
    rl_check('otp_send', email, 5, 3600,
             detail='Too many reset requests. Try again later.')
    u = db.query(UserDB).filter(UserDB.email == email).first()
    if u and u.is_active:
        _create_and_send_otp(db, email, purpose='reset_password', user_id=u.id)
        audit(db, user_id=u.id, actor_email=email, action='reset_password_otp_sent',
              status='success', request=request)
    # generic response — don't leak existence
    return {'message': 'If the account exists, a reset code has been sent.',
            'expires_in_sec': OTP_TTL_MIN * 60}


@router.post('/auth/reset-password')
def reset_password(data: ResetPasswordReq, request: Request, db: Session = Depends(get_db)):
    email = data.email.lower()
    validate_domain(email)
    if len(data.new_password) < 6:
        raise HTTPException(400, 'Password must be at least 6 characters')
    rl_check('reset_pw', email, 5, 3600,
             detail='Too many password resets. Try again later.')

    rec = _verify_otp(db, email, data.code, purpose='reset_password')
    u = db.query(UserDB).filter(UserDB.email == email).first()
    if not u:
        raise HTTPException(404, 'User not found')

    u.password_hash = hash_pw(data.new_password)
    u.failed_attempts = 0
    u.locked_until = None
    # Revoke ALL active sessions on password reset (security best practice)
    revoked = (db.query(SessionDB)
                 .filter(SessionDB.user_id == u.id, SessionDB.is_active == True)  # noqa: E712
                 .update({'is_active': False, 'revoked_at': datetime.now(timezone.utc)}))
    db.commit()
    audit(db, user_id=u.id, actor_email=email, action='password_reset',
          status='success', request=request,
          details={'sessions_revoked': revoked, 'otp_id': rec.id})
    return {'message': 'Password reset successful. Please login again.'}


@router.post('/auth/refresh')
def refresh_token(data: RefreshReq, request: Request, db: Session = Depends(get_db)):
    refresh_h = sha256_hex(data.refresh_token)
    sess = db.query(SessionDB).filter(
        SessionDB.refresh_hash == refresh_h,
        SessionDB.is_active == True,                             # noqa: E712
    ).first()
    if not sess or sess.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(401, 'Invalid or expired refresh token')
    u = db.query(UserDB).filter(UserDB.id == sess.user_id).first()
    if not u or not u.is_active:
        sess.is_active = False; sess.revoked_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(401, 'User no longer active')

    # Rotate refresh token (one-time-use)
    new_refresh = make_refresh_token()
    sess.refresh_hash = sha256_hex(new_refresh)
    sess.last_used_at = datetime.now(timezone.utc)
    db.commit()
    access = make_access_token(u.id, u.email, u.role, sess.id)
    audit(db, user_id=u.id, actor_email=u.email, action='token_refresh',
          status='success', request=request)
    return {'access_token': access, 'refresh_token': new_refresh, 'token_type': 'bearer'}


@router.post('/auth/logout')
def logout(request: Request, u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    # Revoke current session (extracted from access token)
    token = request.cookies.get('access_token')
    if not token:
        hdr = request.headers.get('Authorization', '')
        if hdr.startswith('Bearer '):
            token = hdr[7:]
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            sess_id = payload.get('sess')
            if sess_id:
                sess = db.query(SessionDB).filter(SessionDB.id == sess_id).first()
                if sess:
                    sess.is_active = False
                    sess.revoked_at = datetime.now(timezone.utc)
                    db.commit()
        except jwt.PyJWTError:
            pass
    audit(db, user_id=u.id, actor_email=u.email, action='logout',
          status='success', request=request)
    return {'message': 'Logged out successfully'}


@router.post('/auth/logout-all')
def logout_all(request: Request, u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(SessionDB).filter(SessionDB.user_id == u.id, SessionDB.is_active == True).all()  # noqa: E712
    for s in sessions:
        s.is_active = False
        s.revoked_at = datetime.now(timezone.utc)
    db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='logout_all',
          status='success', request=request, details={'sessions_revoked': len(sessions)})
    return {'message': 'All sessions revoked', 'count': len(sessions)}


@router.get('/auth/me')
def me(u: UserDB = Depends(get_current_user)):
    return user_to_dict(u)


# ── Dashboard endpoints (mock data — Sprint C onwards will replace) ──────────
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
    users = db.query(UserDB).filter(UserDB.is_active == True).order_by(UserDB.xp_points.desc()).limit(10).all()  # noqa: E712
    return [{'rank': i+1, 'name': usr.name, 'role': usr.role.replace('_', ' ').capitalize(),
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
            {'label': 'Tech Days',    'value': 8, 'bar': 80},
        ],
    }


# ── Admin endpoints ───────────────────────────────────────────────────────────
@router.get('/admin/users/pending')
def pending_users(u: UserDB = Depends(require_role('admin', 'super_admin')), db: Session = Depends(get_db)):
    rows = db.query(UserDB).filter(UserDB.is_active == False).order_by(UserDB.created_at.desc()).all()  # noqa: E712
    return [{'id': r.id, 'name': r.name, 'email': r.email, 'role': r.role,
             'department': r.department, 'employee_id': r.employee_id,
             'designation': r.designation,
             'created_at': r.created_at.isoformat() if r.created_at else None}
            for r in rows]


@router.post('/admin/users/{user_id}/approve')
def approve_user(user_id: str, body: ApproveUserReq, request: Request,
                 admin: UserDB = Depends(require_role('admin', 'super_admin')),
                 db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not target:
        raise HTTPException(404, 'User not found')
    if body.role:
        if body.role not in ('employee', 'manager', 'admin', 'super_admin'):
            raise HTTPException(400, 'Invalid role')
        # Only super_admin may grant super_admin
        if body.role == 'super_admin' and admin.role != 'super_admin':
            raise HTTPException(403, 'Only super_admin can grant super_admin')
        target.role = body.role
    target.is_active = True
    target.is_verified = True
    target.approved_by = admin.id
    target.approved_at = datetime.now(timezone.utc)
    db.commit()
    audit(db, user_id=admin.id, actor_email=admin.email, action='approve_user',
          status='success', request=request, target_type='user', target_id=user_id,
          details={'new_role': target.role})
    return {'message': 'User approved', 'role': target.role}


@router.post('/admin/users/{user_id}/reject')
def reject_user(user_id: str, request: Request,
                admin: UserDB = Depends(require_role('admin', 'super_admin')),
                db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not target:
        raise HTTPException(404, 'User not found')
    if target.is_active:
        raise HTTPException(400, 'User is already active; use delete instead')
    db.delete(target); db.commit()
    audit(db, user_id=admin.id, actor_email=admin.email, action='reject_user',
          status='success', request=request, target_type='user', target_id=user_id)
    return {'message': 'User rejected and deleted'}


@router.get('/admin/users')
def get_users(u: UserDB = Depends(require_role('admin', 'super_admin')),
              db: Session = Depends(get_db)):
    return [{'id': usr.id, 'name': usr.name, 'email': usr.email, 'role': usr.role,
             'xp_points': usr.xp_points, 'department': usr.department,
             'created_at': usr.created_at.isoformat() if usr.created_at else None,
             'is_active': usr.is_active, 'is_verified': usr.is_verified}
            for usr in db.query(UserDB).order_by(UserDB.created_at.desc()).all()]


@router.delete('/admin/users/{user_id}')
def delete_user(user_id: str, request: Request,
                u: UserDB = Depends(require_role('admin', 'super_admin')),
                db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not target:
        raise HTTPException(404, 'User not found')
    if target.id == u.id:
        raise HTTPException(400, 'Cannot delete your own account')
    if target.role == 'super_admin' and u.role != 'super_admin':
        raise HTTPException(403, 'Only super_admin can delete super_admin')
    db.delete(target); db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='delete_user',
          status='success', request=request, target_type='user', target_id=user_id)
    return {'message': 'User deleted successfully'}


@router.put('/admin/users/{user_id}/role')
def update_role(user_id: str, body: dict, request: Request,
                u: UserDB = Depends(require_role('admin', 'super_admin')),
                db: Session = Depends(get_db)):
    target = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not target:
        raise HTTPException(404, 'User not found')
    new_role = body.get('role')
    if new_role not in ('employee', 'manager', 'admin', 'super_admin'):
        raise HTTPException(400, 'Invalid role')
    if new_role == 'super_admin' and u.role != 'super_admin':
        raise HTTPException(403, 'Only super_admin can grant super_admin')
    old = target.role
    target.role = new_role
    db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='change_role',
          status='success', request=request, target_type='user', target_id=user_id,
          details={'from': old, 'to': new_role})
    return {'message': 'Role updated', 'role': new_role}


@router.get('/admin/audit-log')
def audit_log_list(u: UserDB = Depends(require_role('admin', 'super_admin')),
                   db: Session = Depends(get_db),
                   limit: int = 100):
    rows = db.query(AuditLogDB).order_by(AuditLogDB.created_at.desc()).limit(limit).all()
    return [{'id': r.id, 'user_id': r.user_id, 'actor_email': r.actor_email,
             'action': r.action, 'status': r.status,
             'target_type': r.target_type, 'target_id': r.target_id,
             'ip_address': r.ip_address, 'details': r.details,
             'created_at': r.created_at.isoformat() if r.created_at else None}
            for r in rows]


@router.get('/')
def root():
    return {
        'message': 'HSI Enterprise Portal API v1.0',
        'status': 'running',
        'allowed_domain': ALLOWED_DOMAIN,
        'mfa_enabled': MFA_ENABLED,
        'ses_configured': ses_is_configured(),
        'redis_active': is_redis_active(),
    }


# ── Mount & Middleware ────────────────────────────────────────────────────────
app.include_router(router)

cors_origins = [o.strip() for o in os.environ.get('CORS_ORIGINS', '*').split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=cors_origins or ['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)
logger.info(f"HSI API ready · domain=@{ALLOWED_DOMAIN} · bcrypt={BCRYPT_ROUNDS} rounds · "
            f"mfa={'on' if MFA_ENABLED else 'off'} · ses={'on' if ses_is_configured() else 'off (dev fallback)'} · "
            f"redis={'on' if is_redis_active() else 'in-memory'}")
