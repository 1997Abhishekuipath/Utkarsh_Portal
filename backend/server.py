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


# ═════════════════════════════════════════════════════════════════════════════
#  Sprint C — Content Models (Pillars, Icons, EDM slides, Quotes)
# ═════════════════════════════════════════════════════════════════════════════
class PillarDB(Base):
    __tablename__ = 'pillars'
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    slug          = Column(String, unique=True, nullable=False, index=True)  # customer|innovator|employee|shareholder
    name          = Column(String, nullable=False)
    tagline       = Column(String, nullable=True)
    gradient_from = Column(String, nullable=False, default='#CC0000')
    gradient_to   = Column(String, nullable=False, default='#7A0000')
    icon_name     = Column(String, nullable=True)              # lucide-react icon name
    position      = Column(Integer, default=0)
    is_published  = Column(Boolean, default=True)
    updated_by    = Column(String, ForeignKey('users.id'), nullable=True)
    updated_at    = Column(DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PillarIconDB(Base):
    __tablename__ = 'pillar_icons'
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pillar_id     = Column(String, ForeignKey('pillars.id', ondelete='CASCADE'), nullable=False, index=True)
    name          = Column(String, nullable=False)
    description   = Column(String, nullable=True)
    lucide_icon   = Column(String, nullable=True)              # icon name from lucide-react
    route         = Column(String, nullable=True)              # frontend route this icon links to
    badge         = Column(String, nullable=True)              # 'hot' | 'new' | null
    position      = Column(Integer, default=0)
    is_published  = Column(Boolean, default=True)
    updated_at    = Column(DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EdmSlideDB(Base):
    __tablename__ = 'edm_slides'
    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scope          = Column(String, nullable=False, index=True)   # 'home' or pillar slug
    title          = Column(String, nullable=False)
    subtitle       = Column(String, nullable=True)
    gradient_from  = Column(String, default='#CC0000')
    gradient_to    = Column(String, default='#7A0000')
    image_url      = Column(String, nullable=True)
    link           = Column(String, nullable=True)
    position       = Column(Integer, default=0)
    starts_at      = Column(DateTime(timezone=True), nullable=True)
    ends_at        = Column(DateTime(timezone=True), nullable=True)
    is_published   = Column(Boolean, default=True)
    updated_at     = Column(DateTime(timezone=True),
                            default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "scope IN ('home','customer','innovator','employee','shareholder')",
            name='chk_edm_scope'),
    )


class QuoteDB(Base):
    __tablename__ = 'motivational_quotes'
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    text         = Column(String, nullable=False)
    author       = Column(String, nullable=True)
    position     = Column(Integer, default=0)
    is_published = Column(Boolean, default=True)
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PublishHistoryDB(Base):
    """Each admin 'Publish All' click = one row. WebSocket clients are notified."""
    __tablename__ = 'publish_history'
    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    scope         = Column(String, nullable=False)             # 'all' | 'home' | pillar slug
    published_by  = Column(String, ForeignKey('users.id'), nullable=True)
    actor_email   = Column(String, nullable=True)
    note          = Column(String, nullable=True)
    published_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


# ── Sprint D — XP & Incentive Engine Models ──────────────────────────────────

class BestPracticeDB(Base):
    __tablename__ = 'best_practices'
    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    author_id      = Column(String, ForeignKey('users.id'), nullable=False)
    title          = Column(String, nullable=False)
    summary        = Column(String, nullable=False)
    why_content    = Column(String, nullable=True)
    how_content    = Column(String, nullable=True)
    what_content   = Column(String, nullable=True)
    impact_content = Column(String, nullable=True)
    difficulty     = Column(String, default='medium')
    pillar         = Column(String, nullable=True)
    art_tag        = Column(String, nullable=True)
    tags           = Column(ARRAY(String), default=list)
    status         = Column(String, default='pending')
    reviewer_id    = Column(String, ForeignKey('users.id'), nullable=True)
    reviewed_at    = Column(DateTime(timezone=True), nullable=True)
    reject_reason  = Column(String, nullable=True)
    xp_awarded     = Column(Integer, default=0)
    replication_cnt= Column(Integer, default=0)
    is_featured    = Column(Boolean, default=False)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        CheckConstraint("difficulty IN ('easy','medium','hard','expert')", name='chk_bp_difficulty'),
        CheckConstraint("pillar IN ('customer','innovator','employee','shareholder')", name='chk_bp_pillar'),
        CheckConstraint("art_tag IN ('accelerate','retain','transform')", name='chk_bp_art'),
        CheckConstraint("status IN ('draft','pending','approved','rejected')", name='chk_bp_status'),
    )


class ReplicationDB(Base):
    __tablename__ = 'replications'
    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    practice_id    = Column(String, ForeignKey('best_practices.id'), nullable=False)
    replicator_id  = Column(String, ForeignKey('users.id'), nullable=False)
    client_name    = Column(String, nullable=False)
    po_number      = Column(String, nullable=True)
    po_value_inr   = Column(String, nullable=True)
    deal_closed_at = Column(Date, nullable=True)
    xp_awarded     = Column(Integer, default=0)
    referral_xp    = Column(Integer, default=0)
    status         = Column(String, default='pending')
    approved_by    = Column(String, ForeignKey('users.id'), nullable=True)
    approved_at    = Column(DateTime(timezone=True), nullable=True)
    notes          = Column(String, nullable=True)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected')", name='chk_rep_status'),
    )


class XpLedgerDB(Base):
    __tablename__ = 'xp_ledger'
    id           = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id      = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    xp_delta     = Column(Integer, nullable=False)
    xp_balance   = Column(Integer, nullable=False)
    source_type  = Column(String, nullable=False)
    source_id    = Column(String, nullable=True)
    art_multiplier = Column(String, default='1.00')
    quarter      = Column(String, nullable=False, index=True)
    description  = Column(String, nullable=True)
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('original_practice','replication','tech_day','certification',"
            "'birthday','referral','seasonal_bonus','admin_adjustment')",
            name='chk_xp_source'),
    )


class IncentiveCalcDB(Base):
    __tablename__ = 'incentive_calculations'
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id         = Column(String, ForeignKey('users.id'), nullable=False)
    quarter         = Column(String, nullable=False)
    xp_original     = Column(Integer, default=0)
    xp_replication  = Column(Integer, default=0)
    xp_tech_day     = Column(Integer, default=0)
    xp_other        = Column(Integer, default=0)
    rate_original   = Column(String, default='50.00')
    rate_replication= Column(String, default='75.00')
    rate_tech_day   = Column(String, default='19.00')
    amount_inr      = Column(String, nullable=True)
    status          = Column(String, default='draft')
    approved_by     = Column(String, ForeignKey('users.id'), nullable=True)
    approved_at     = Column(DateTime(timezone=True), nullable=True)
    payout_date     = Column(Date, nullable=True)
    payroll_ref     = Column(String, nullable=True)
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        CheckConstraint("status IN ('draft','approved','paid','on_hold')", name='chk_inc_status'),
        Index('idx_inc_user_quarter', 'user_id', 'quarter', unique=True),
    )


class TechDayDB(Base):
    __tablename__ = 'tech_days'
    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conductor_id   = Column(String, ForeignKey('users.id'), nullable=False)
    title          = Column(String, nullable=False)
    description    = Column(String, nullable=True)
    client_name    = Column(String, nullable=True)
    attendee_count = Column(Integer, default=0)
    conducted_on   = Column(Date, nullable=False)
    xp_awarded     = Column(Integer, default=0)
    status         = Column(String, default='pending')
    approved_by    = Column(String, ForeignKey('users.id'), nullable=True)
    evidence_url   = Column(String, nullable=True)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected')", name='chk_td_status'),
    )


class CertificationDB(Base):
    __tablename__ = 'certifications'
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id      = Column(String, ForeignKey('users.id'), nullable=False)
    cert_name    = Column(String, nullable=False)
    provider     = Column(String, nullable=True)
    cert_id      = Column(String, nullable=True)
    issued_on    = Column(Date, nullable=True)
    expires_on   = Column(Date, nullable=True)
    xp_awarded   = Column(Integer, default=50)
    verified     = Column(Boolean, default=False)
    evidence_url = Column(String, nullable=True)
    created_at   = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Sprint E — Notifications Models ──────────────────────────────────────────

class NotificationDB(Base):
    __tablename__ = 'notifications'
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title       = Column(String, nullable=False)
    body        = Column(String, nullable=False)
    category    = Column(String, nullable=True)
    target_type = Column(String, default='all')
    target_id   = Column(String, nullable=True)
    is_urgent   = Column(Boolean, default=False)
    deep_link   = Column(String, nullable=True)
    sent_at     = Column(DateTime(timezone=True), nullable=True)
    send_email  = Column(Boolean, default=False)
    created_by  = Column(String, ForeignKey('users.id'), nullable=True)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        CheckConstraint(
            "category IN ('incentive','birthday','approved','replication','reminder',"
            "'new_practice','award','announcement')",
            name='chk_notif_category'),
        CheckConstraint(
            "target_type IN ('all','user','role','practice','department')",
            name='chk_notif_target'),
    )


class UserNotificationDB(Base):
    __tablename__ = 'user_notifications'
    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    notification_id = Column(String, ForeignKey('notifications.id'), nullable=False)
    user_id         = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    is_read         = Column(Boolean, default=False)
    read_at         = Column(DateTime(timezone=True), nullable=True)
    is_dismissed    = Column(Boolean, default=False)
    delivered_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        Index('idx_un_user_notif', 'notification_id', 'user_id', unique=True),
    )


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


# ── Sprint C — content schemas ────────────────────────────────────────────────
class PillarUpsertReq(BaseModel):
    slug: str
    name: str
    tagline: Optional[str] = None
    gradient_from: str = '#CC0000'
    gradient_to: str = '#7A0000'
    icon_name: Optional[str] = None
    position: int = 0
    is_published: bool = True


class PillarIconUpsertReq(BaseModel):
    pillar_id: str
    name: str
    description: Optional[str] = None
    lucide_icon: Optional[str] = None
    route: Optional[str] = None
    badge: Optional[str] = None         # 'hot' | 'new' | None
    position: int = 0
    is_published: bool = True


class EdmSlideUpsertReq(BaseModel):
    scope: str                          # home | customer | innovator | employee | shareholder
    title: str
    subtitle: Optional[str] = None
    gradient_from: str = '#CC0000'
    gradient_to: str = '#7A0000'
    image_url: Optional[str] = None
    link: Optional[str] = None
    position: int = 0
    is_published: bool = True


class QuoteUpsertReq(BaseModel):
    text: str
    author: Optional[str] = None
    position: int = 0
    is_published: bool = True


class PublishReq(BaseModel):
    scope: str = 'all'                  # 'all' | 'home' | pillar slug
    note: Optional[str] = None


# ── Sprint D — XP & Incentive Schemas ────────────────────────────────────────
class PracticeSubmitReq(BaseModel):
    title: str
    summary: str
    why_content: Optional[str] = None
    how_content: Optional[str] = None
    what_content: Optional[str] = None
    impact_content: Optional[str] = None
    difficulty: str = 'medium'          # easy|medium|hard|expert
    pillar: Optional[str] = None
    art_tag: Optional[str] = None
    tags: Optional[List[str]] = []
    status: str = 'pending'             # draft → pending on submit


class ReplicationSubmitReq(BaseModel):
    practice_id: str
    client_name: str
    po_number: Optional[str] = None
    po_value_inr: Optional[str] = None
    deal_closed_at: Optional[str] = None
    notes: Optional[str] = None


class TechDaySubmitReq(BaseModel):
    title: str
    description: Optional[str] = None
    client_name: Optional[str] = None
    attendee_count: int = 0
    conducted_on: str                   # ISO date string
    evidence_url: Optional[str] = None


class CertSubmitReq(BaseModel):
    cert_name: str
    provider: Optional[str] = None
    cert_id: Optional[str] = None
    issued_on: Optional[str] = None
    expires_on: Optional[str] = None
    evidence_url: Optional[str] = None


class AdminPracticeActionReq(BaseModel):
    reject_reason: Optional[str] = None


# ── Sprint E — Notification Schemas ──────────────────────────────────────────
class SendNotificationReq(BaseModel):
    title: str
    body: str
    category: str = 'announcement'
    target_type: str = 'all'            # all|user|role|practice|department
    target_id: Optional[str] = None
    is_urgent: bool = False
    deep_link: Optional[str] = None
    send_email: bool = False


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


# ── XP Engine helpers ─────────────────────────────────────────────────────────
XP_MATRIX = {
    'original_practice': {'easy': 80, 'medium': 100, 'hard': 120, 'expert': 130},
    'replication_no_po': {'easy': 0, 'medium': 90, 'hard': 120, 'expert': 150},
    'replication_with_po': {'easy': 0, 'medium': 120, 'hard': 165, 'expert': 195},
}
ART_MULT    = {'accelerate': 1.2, 'retain': 1.0, 'transform': 1.5}
INR_RATE    = {'original_practice': 50.0, 'replication': 75.0,
               'replication_no_po': 60.0, 'tech_day': 19.0}
CERT_XP     = 50
BIRTHDAY_XP = 50
REFERRAL_XP = 25


def current_quarter() -> str:
    now = datetime.now(timezone.utc)
    q = (now.month - 1) // 3 + 1
    return f"{now.year}-Q{q}"


def calc_practice_xp(difficulty: str, art_tag: Optional[str]) -> tuple:
    base = XP_MATRIX['original_practice'].get(difficulty or 'medium', 100)
    mult = ART_MULT.get(art_tag or 'retain', 1.0)
    return round(base * mult), mult


def calc_replication_xp(difficulty: str, has_po: bool, art_tag: Optional[str]) -> tuple:
    """Returns (replicator_xp, referral_xp, multiplier)"""
    key = 'replication_with_po' if has_po else 'replication_no_po'
    base = XP_MATRIX[key].get(difficulty or 'medium', 90)
    mult = ART_MULT.get(art_tag or 'retain', 1.0)
    return round(base * mult), REFERRAL_XP, mult


def calc_tech_day_xp(attendee_count: int = 0) -> int:
    return min(25 + attendee_count * 2, 75)


def add_xp(db: Session, user_id: str, xp_delta: int, source_type: str,
           source_id: Optional[str] = None, art_multiplier: float = 1.0,
           quarter: Optional[str] = None, description: Optional[str] = None) -> int:
    """Append to xp_ledger and sync user.xp_points. Returns new balance."""
    last = (db.query(XpLedgerDB)
            .filter(XpLedgerDB.user_id == user_id)
            .order_by(XpLedgerDB.id.desc()).first())
    prev_balance = last.xp_balance if last else 0
    new_balance  = max(0, prev_balance + xp_delta)
    db.add(XpLedgerDB(
        user_id=user_id, xp_delta=xp_delta, xp_balance=new_balance,
        source_type=source_type, source_id=source_id,
        art_multiplier=str(art_multiplier),
        quarter=quarter or current_quarter(),
        description=description,
    ))
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user:
        user.xp_points = new_balance
    db.flush()
    return new_balance


def _dispatch_notification(db: Session, *, title: str, body: str, category: str,
                           target_type: str = 'all', target_id: Optional[str] = None,
                           is_urgent: bool = False, deep_link: Optional[str] = None,
                           created_by: Optional[str] = None):
    """Create notification + fan-out user_notification rows."""
    notif = NotificationDB(
        id=str(uuid.uuid4()), title=title, body=body, category=category,
        target_type=target_type, target_id=target_id,
        is_urgent=is_urgent, deep_link=deep_link,
        sent_at=datetime.now(timezone.utc), created_by=created_by,
    )
    db.add(notif)
    db.flush()
    if target_type == 'all':
        rids = [r for (r,) in db.query(UserDB.id).filter(UserDB.is_active == True).all()]  # noqa: E712
    elif target_type == 'user' and target_id:
        rids = [target_id]
    elif target_type == 'role' and target_id:
        rids = [r for (r,) in db.query(UserDB.id).filter(
            UserDB.role == target_id, UserDB.is_active == True).all()]  # noqa: E712
    elif target_type == 'department' and target_id:
        rids = [r for (r,) in db.query(UserDB.id).filter(
            UserDB.department == target_id, UserDB.is_active == True).all()]  # noqa: E712
    else:
        rids = []
    for rid in rids:
        try:
            db.add(UserNotificationDB(notification_id=notif.id, user_id=rid))
            db.flush()
        except Exception:  # noqa: BLE001
            db.rollback()
    db.commit()
    return notif


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
def stats(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    q = current_quarter()
    # Live XP from ledger
    total_xp = u.xp_points or 0
    # Live practice count (approved)
    practice_cnt = db.query(BestPracticeDB).filter(
        BestPracticeDB.status == 'approved').count()
    # Live tech day count (approved, current quarter)
    td_cnt = db.query(TechDayDB).filter(
        TechDayDB.conductor_id == u.id, TechDayDB.status == 'approved').count()
    # Live pending: practices + replications submitted by user awaiting review
    pending_cnt = (
        db.query(BestPracticeDB).filter(
            BestPracticeDB.author_id == u.id, BestPracticeDB.status == 'pending').count() +
        db.query(ReplicationDB).filter(
            ReplicationDB.replicator_id == u.id, ReplicationDB.status == 'pending').count()
    )
    # Incentive amount from current quarter calc
    inc = db.query(IncentiveCalcDB).filter(
        IncentiveCalcDB.user_id == u.id, IncentiveCalcDB.quarter == q).first()
    incentive_amt = int(float(inc.amount_inr or 0)) if inc else 0
    return {
        'best_practices': {'count': practice_cnt, 'trend': '+5%', 'label': 'BEST PRACTICES', 'sub': 'Total Approved'},
        'efforts':        {'count': total_xp, 'trend': '+12%', 'label': 'EFFORTS (XP)', 'sub': 'Total XP Earned'},
        'xp_incentive':   {'amount': incentive_amt, 'trend': '+8%', 'label': 'XP INCENTIVE', 'sub': f'Payout in {q}'},
        'tech_days':      {'count': td_cnt, 'trend': 'New', 'label': 'TECH DAYS', 'sub': 'Approved'},
        'pending_actions':{'count': pending_cnt, 'trend': 'Due', 'label': 'PENDING', 'sub': 'Awaiting review'}
    }


@router.get('/dashboard/activities')
def activities(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    # Live: recent practices + replications
    items = []
    practices = (db.query(BestPracticeDB, UserDB)
                 .join(UserDB, UserDB.id == BestPracticeDB.author_id)
                 .order_by(BestPracticeDB.created_at.desc()).limit(4).all())
    for bp, author in practices:
        items.append({
            'id': bp.id, 'user': author.name,
            'action': f'submitted best practice — {bp.title}. {bp.xp_awarded} XP.',
            'category': 'Best Practices',
            'time': _rel_time(bp.created_at), 'type': 'submission', 'color': 'red'
        })
    reps = (db.query(ReplicationDB, UserDB)
            .join(UserDB, UserDB.id == ReplicationDB.replicator_id)
            .order_by(ReplicationDB.created_at.desc()).limit(3).all())
    for rep, replicator in reps:
        items.append({
            'id': rep.id, 'user': replicator.name,
            'action': f'submitted replication for client {rep.client_name}. {rep.xp_awarded} XP.',
            'category': 'Replications',
            'time': _rel_time(rep.created_at), 'type': 'replication', 'color': 'blue'
        })
    items.sort(key=lambda x: x['time'])
    return items[:6]


@router.get('/dashboard/leaderboard')
def leaderboard(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(UserDB).filter(UserDB.is_active == True).order_by(UserDB.xp_points.desc()).limit(10).all()  # noqa: E712
    return [{'rank': i+1, 'name': usr.name, 'role': usr.role.replace('_', ' ').capitalize(),
             'xp': usr.xp_points, 'is_current_user': usr.id == u.id,
             'initials': ''.join(p[0].upper() for p in usr.name.split()[:2])}
            for i, usr in enumerate(users)]


@router.get('/dashboard/announcements')
def announcements(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    """Live announcements from notifications table (category=announcement)."""
    notifs = (db.query(NotificationDB)
              .filter(NotificationDB.category == 'announcement')
              .order_by(NotificationDB.created_at.desc()).limit(4).all())
    if notifs:
        return [{'id': n.id, 'title': n.title, 'body': n.body,
                 'date': n.created_at.strftime('%b %d') if n.created_at else '',
                 'color': 'red' if n.is_urgent else 'blue'}
                for n in notifs]
    # Fallback mock data when no announcements created yet
    return [
        {'id': '1', 'title': 'Incentives Paid', 'body': 'Q1-2025 incentives paid. Check your statement.', 'date': 'Apr 17', 'color': 'green'},
        {'id': '2', 'title': 'New Module: Workflow Automation', 'body': 'Beta live for testing. Enrol for early access.', 'date': 'Apr 15', 'color': 'blue'},
    ]


@router.get('/dashboard/pending-actions')
def pending(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    items = []
    # User's own pending practices
    pending_bp = db.query(BestPracticeDB).filter(
        BestPracticeDB.author_id == u.id, BestPracticeDB.status == 'pending').limit(2).all()
    for bp in pending_bp:
        items.append({'id': bp.id, 'title': f'Practice review pending: {bp.title}', 'category': 'Best Practices', 'priority': 'high'})
    # User's pending replications
    pending_rep = db.query(ReplicationDB).filter(
        ReplicationDB.replicator_id == u.id, ReplicationDB.status == 'pending').limit(2).all()
    for rep in pending_rep:
        items.append({'id': rep.id, 'title': f'Replication pending: {rep.client_name}', 'category': 'Replications', 'priority': 'high'})
    if not items:
        items = [{'id': '1', 'title': 'No pending actions', 'category': 'All clear', 'priority': 'low'}]
    return items[:4]


@router.get('/dashboard/upcoming')
def upcoming(_u: UserDB = Depends(get_current_user)):
    return [
        {'id': '1', 'title': 'Tech Day — All For SPTS', 'description': 'Bangalore, GEC • 2 Hrs', 'date': 'Apr 30, 9:00 AM', 'color': 'red'},
        {'id': '2', 'title': 'Visitor — Bajaj Finance',  'description': '6 Guests',               'date': 'Apr 30, 2:00 PM', 'color': 'blue'},
        {'id': '3', 'title': '365 Incentive Payout',     'description': 'Finance Dept',            'date': 'May 1',           'color': 'green'}
    ]


@router.get('/dashboard/score')
def score(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    q = current_quarter()
    xp_prac = sum(r.xp_delta for r in db.query(XpLedgerDB).filter(
        XpLedgerDB.user_id == u.id, XpLedgerDB.source_type == 'original_practice').all())
    xp_rep  = sum(r.xp_delta for r in db.query(XpLedgerDB).filter(
        XpLedgerDB.user_id == u.id, XpLedgerDB.source_type == 'replication').all())
    xp_td   = sum(r.xp_delta for r in db.query(XpLedgerDB).filter(
        XpLedgerDB.user_id == u.id, XpLedgerDB.source_type == 'tech_day').all())
    total   = u.xp_points or 0
    pct     = min(100, int(total / 50)) if total else 0
    max_val = max(xp_prac, xp_rep, xp_td, 1)
    return {
        'percentage': pct,
        'total_xp': total,
        'quarter': q,
        'breakdown': [
            {'label': 'Practices',    'value': xp_prac, 'bar': round(xp_prac / max_val * 100)},
            {'label': 'Replications', 'value': xp_rep,  'bar': round(xp_rep  / max_val * 100)},
            {'label': 'Tech Days',    'value': xp_td,   'bar': round(xp_td   / max_val * 100)},
        ],
    }


def _rel_time(dt) -> str:
    if not dt:
        return 'recently'
    diff = datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else datetime.now(timezone.utc) - dt
    s = diff.total_seconds()
    if s < 3600:   return f"{int(s/60) or 1} min ago"
    if s < 86400:  return f"{int(s/3600)} hour{'s' if s >= 7200 else ''} ago"
    if s < 604800: return f"{int(s/86400)} day{'s' if s >= 172800 else ''} ago"
    return dt.strftime('%b %d')


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


# ═════════════════════════════════════════════════════════════════════════════
#  Sprint C — Content (Pillars, Icons, EDM, Quotes) + Publish + WebSocket
# ═════════════════════════════════════════════════════════════════════════════
from services.ws import manager as ws_manager
from fastapi import WebSocket, WebSocketDisconnect


def _pillar_to_dict(p: PillarDB) -> dict:
    return {
        'id': p.id, 'slug': p.slug, 'name': p.name, 'tagline': p.tagline,
        'gradient_from': p.gradient_from, 'gradient_to': p.gradient_to,
        'icon_name': p.icon_name, 'position': p.position,
        'is_published': p.is_published,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
    }


def _icon_to_dict(i: PillarIconDB) -> dict:
    return {
        'id': i.id, 'pillar_id': i.pillar_id, 'name': i.name,
        'description': i.description, 'lucide_icon': i.lucide_icon,
        'route': i.route, 'badge': i.badge, 'position': i.position,
        'is_published': i.is_published,
    }


def _edm_to_dict(s: EdmSlideDB) -> dict:
    return {
        'id': s.id, 'scope': s.scope, 'title': s.title, 'subtitle': s.subtitle,
        'gradient_from': s.gradient_from, 'gradient_to': s.gradient_to,
        'image_url': s.image_url, 'link': s.link, 'position': s.position,
        'starts_at': s.starts_at.isoformat() if s.starts_at else None,
        'ends_at':   s.ends_at.isoformat()   if s.ends_at   else None,
        'is_published': s.is_published,
    }


def _quote_to_dict(q: QuoteDB) -> dict:
    return {'id': q.id, 'text': q.text, 'author': q.author,
            'position': q.position, 'is_published': q.is_published}


def _published_edm(db: Session, scope: str) -> List[dict]:
    now = datetime.now(timezone.utc)
    rows = (db.query(EdmSlideDB)
              .filter(EdmSlideDB.scope == scope, EdmSlideDB.is_published == True)  # noqa: E712
              .order_by(EdmSlideDB.position.asc(), EdmSlideDB.created_at.desc())
              .all())
    out = []
    for s in rows:
        if s.starts_at and s.starts_at > now:    # not yet visible
            continue
        if s.ends_at and s.ends_at < now:        # expired
            continue
        out.append(_edm_to_dict(s))
    return out


# ── Public read-only content (any logged-in user) ─────────────────────────────
@router.get('/content/home')
def content_home(_u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    pillars = (db.query(PillarDB)
                 .filter(PillarDB.is_published == True)             # noqa: E712
                 .order_by(PillarDB.position.asc())
                 .all())
    quotes = (db.query(QuoteDB)
                .filter(QuoteDB.is_published == True)              # noqa: E712
                .order_by(QuoteDB.position.asc(), QuoteDB.created_at.desc())
                .all())
    return {
        'edm':     _published_edm(db, 'home'),
        'pillars': [_pillar_to_dict(p) for p in pillars],
        'quotes':  [_quote_to_dict(q) for q in quotes],
    }


@router.get('/content/pillars/{slug}')
def content_pillar(slug: str,
                   _u: UserDB = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    p = db.query(PillarDB).filter(PillarDB.slug == slug, PillarDB.is_published == True).first()  # noqa: E712
    if not p:
        raise HTTPException(404, 'Pillar not found')
    icons = (db.query(PillarIconDB)
               .filter(PillarIconDB.pillar_id == p.id, PillarIconDB.is_published == True)  # noqa: E712
               .order_by(PillarIconDB.position.asc(), PillarIconDB.created_at.desc())
               .all())
    return {
        'pillar': _pillar_to_dict(p),
        'edm':    _published_edm(db, slug),
        'icons':  [_icon_to_dict(i) for i in icons],
    }


# ── Admin content CRUD ────────────────────────────────────────────────────────
def _admin_role(u: UserDB = Depends(require_role('admin', 'super_admin'))) -> UserDB:
    return u


@router.get('/admin/pillars')
def admin_pillars(u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    return [_pillar_to_dict(p) for p in
            db.query(PillarDB).order_by(PillarDB.position.asc()).all()]


@router.post('/admin/pillars')
def admin_pillar_create(body: PillarUpsertReq, request: Request,
                        u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    if body.slug not in ('customer', 'innovator', 'employee', 'shareholder'):
        raise HTTPException(400, 'Slug must be one of: customer|innovator|employee|shareholder')
    if db.query(PillarDB).filter(PillarDB.slug == body.slug).first():
        raise HTTPException(409, 'Pillar with this slug already exists')
    p = PillarDB(id=str(uuid.uuid4()), updated_by=u.id, **body.dict())
    db.add(p); db.commit(); db.refresh(p)
    audit(db, user_id=u.id, actor_email=u.email, action='pillar_create',
          status='success', request=request, target_type='pillar', target_id=p.id,
          details={'slug': p.slug})
    return _pillar_to_dict(p)


@router.put('/admin/pillars/{pillar_id}')
def admin_pillar_update(pillar_id: str, body: PillarUpsertReq, request: Request,
                        u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    p = db.query(PillarDB).filter(PillarDB.id == pillar_id).first()
    if not p:
        raise HTTPException(404, 'Pillar not found')
    for k, v in body.dict().items():
        setattr(p, k, v)
    p.updated_by = u.id
    db.commit(); db.refresh(p)
    audit(db, user_id=u.id, actor_email=u.email, action='pillar_update',
          status='success', request=request, target_type='pillar', target_id=p.id)
    return _pillar_to_dict(p)


@router.delete('/admin/pillars/{pillar_id}')
def admin_pillar_delete(pillar_id: str, request: Request,
                        u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    p = db.query(PillarDB).filter(PillarDB.id == pillar_id).first()
    if not p:
        raise HTTPException(404, 'Pillar not found')
    db.delete(p); db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='pillar_delete',
          status='success', request=request, target_type='pillar', target_id=pillar_id)
    return {'message': 'Pillar deleted'}


@router.get('/admin/pillar-icons')
def admin_icons(u: UserDB = Depends(_admin_role), db: Session = Depends(get_db),
                pillar_id: Optional[str] = None):
    q = db.query(PillarIconDB)
    if pillar_id:
        q = q.filter(PillarIconDB.pillar_id == pillar_id)
    return [_icon_to_dict(i) for i in q.order_by(PillarIconDB.position.asc()).all()]


@router.post('/admin/pillar-icons')
def admin_icon_create(body: PillarIconUpsertReq, request: Request,
                      u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    if not db.query(PillarDB).filter(PillarDB.id == body.pillar_id).first():
        raise HTTPException(404, 'Pillar not found')
    i = PillarIconDB(id=str(uuid.uuid4()), **body.dict())
    db.add(i); db.commit(); db.refresh(i)
    audit(db, user_id=u.id, actor_email=u.email, action='icon_create',
          status='success', request=request, target_type='icon', target_id=i.id,
          details={'name': i.name, 'pillar_id': i.pillar_id})
    return _icon_to_dict(i)


@router.put('/admin/pillar-icons/{icon_id}')
def admin_icon_update(icon_id: str, body: PillarIconUpsertReq, request: Request,
                      u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    i = db.query(PillarIconDB).filter(PillarIconDB.id == icon_id).first()
    if not i:
        raise HTTPException(404, 'Icon not found')
    for k, v in body.dict().items():
        setattr(i, k, v)
    db.commit(); db.refresh(i)
    audit(db, user_id=u.id, actor_email=u.email, action='icon_update',
          status='success', request=request, target_type='icon', target_id=icon_id)
    return _icon_to_dict(i)


@router.delete('/admin/pillar-icons/{icon_id}')
def admin_icon_delete(icon_id: str, request: Request,
                      u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    i = db.query(PillarIconDB).filter(PillarIconDB.id == icon_id).first()
    if not i:
        raise HTTPException(404, 'Icon not found')
    db.delete(i); db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='icon_delete',
          status='success', request=request, target_type='icon', target_id=icon_id)
    return {'message': 'Icon deleted'}


@router.get('/admin/edm-slides')
def admin_edm(u: UserDB = Depends(_admin_role), db: Session = Depends(get_db),
              scope: Optional[str] = None):
    q = db.query(EdmSlideDB)
    if scope:
        q = q.filter(EdmSlideDB.scope == scope)
    return [_edm_to_dict(s) for s in q.order_by(EdmSlideDB.position.asc()).all()]


@router.post('/admin/edm-slides')
def admin_edm_create(body: EdmSlideUpsertReq, request: Request,
                     u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    if body.scope not in ('home', 'customer', 'innovator', 'employee', 'shareholder'):
        raise HTTPException(400, 'Invalid scope')
    s = EdmSlideDB(id=str(uuid.uuid4()), **body.dict())
    db.add(s); db.commit(); db.refresh(s)
    audit(db, user_id=u.id, actor_email=u.email, action='edm_create',
          status='success', request=request, target_type='edm_slide', target_id=s.id,
          details={'scope': s.scope, 'title': s.title})
    return _edm_to_dict(s)


@router.put('/admin/edm-slides/{slide_id}')
def admin_edm_update(slide_id: str, body: EdmSlideUpsertReq, request: Request,
                     u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    s = db.query(EdmSlideDB).filter(EdmSlideDB.id == slide_id).first()
    if not s:
        raise HTTPException(404, 'Slide not found')
    for k, v in body.dict().items():
        setattr(s, k, v)
    db.commit(); db.refresh(s)
    audit(db, user_id=u.id, actor_email=u.email, action='edm_update',
          status='success', request=request, target_type='edm_slide', target_id=slide_id)
    return _edm_to_dict(s)


@router.delete('/admin/edm-slides/{slide_id}')
def admin_edm_delete(slide_id: str, request: Request,
                     u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    s = db.query(EdmSlideDB).filter(EdmSlideDB.id == slide_id).first()
    if not s:
        raise HTTPException(404, 'Slide not found')
    db.delete(s); db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='edm_delete',
          status='success', request=request, target_type='edm_slide', target_id=slide_id)
    return {'message': 'Slide deleted'}


@router.get('/admin/quotes')
def admin_quotes(u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    return [_quote_to_dict(q) for q in
            db.query(QuoteDB).order_by(QuoteDB.position.asc()).all()]


@router.post('/admin/quotes')
def admin_quote_create(body: QuoteUpsertReq, request: Request,
                       u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    q = QuoteDB(id=str(uuid.uuid4()), **body.dict())
    db.add(q); db.commit(); db.refresh(q)
    audit(db, user_id=u.id, actor_email=u.email, action='quote_create',
          status='success', request=request, target_type='quote', target_id=q.id)
    return _quote_to_dict(q)


@router.put('/admin/quotes/{quote_id}')
def admin_quote_update(quote_id: str, body: QuoteUpsertReq, request: Request,
                       u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    q = db.query(QuoteDB).filter(QuoteDB.id == quote_id).first()
    if not q:
        raise HTTPException(404, 'Quote not found')
    for k, v in body.dict().items():
        setattr(q, k, v)
    db.commit(); db.refresh(q)
    audit(db, user_id=u.id, actor_email=u.email, action='quote_update',
          status='success', request=request, target_type='quote', target_id=quote_id)
    return _quote_to_dict(q)


@router.delete('/admin/quotes/{quote_id}')
def admin_quote_delete(quote_id: str, request: Request,
                       u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    q = db.query(QuoteDB).filter(QuoteDB.id == quote_id).first()
    if not q:
        raise HTTPException(404, 'Quote not found')
    db.delete(q); db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='quote_delete',
          status='success', request=request, target_type='quote', target_id=quote_id)
    return {'message': 'Quote deleted'}


# ── Publish All — broadcast to WebSocket clients ──────────────────────────────
@router.post('/admin/publish')
async def admin_publish(body: PublishReq, request: Request,
                        u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    valid = ('all', 'home', 'customer', 'innovator', 'employee', 'shareholder')
    if body.scope not in valid:
        raise HTTPException(400, f"scope must be one of: {', '.join(valid)}")
    h = PublishHistoryDB(scope=body.scope, published_by=u.id,
                         actor_email=u.email, note=body.note)
    db.add(h); db.commit(); db.refresh(h)
    audit(db, user_id=u.id, actor_email=u.email, action='content_publish',
          status='success', request=request, target_type='publish',
          target_id=str(h.id), details={'scope': body.scope, 'note': body.note})
    payload = {
        'type': 'content_published',
        'scope': body.scope,
        'at': h.published_at.isoformat(),
        'by': u.email,
        'id': h.id,
    }
    await ws_manager.broadcast(payload)
    return {'message': 'Published',
            'subscribers_notified': ws_manager.count, 'event': payload}


@router.get('/admin/publish-history')
def admin_publish_history(_u: UserDB = Depends(_admin_role),
                          db: Session = Depends(get_db), limit: int = 50):
    rows = (db.query(PublishHistoryDB)
              .order_by(PublishHistoryDB.published_at.desc())
              .limit(limit).all())
    return [{'id': r.id, 'scope': r.scope, 'actor_email': r.actor_email,
             'note': r.note,
             'published_at': r.published_at.isoformat() if r.published_at else None}
            for r in rows]



# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT D — XP & Incentive Engine Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

# ── XP Summary & Ledger ───────────────────────────────────────────────────────

@router.get('/xp/summary')
def xp_summary(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    q = current_quarter()
    ledger = db.query(XpLedgerDB).filter(XpLedgerDB.user_id == u.id).all()
    q_rows  = [r for r in ledger if r.quarter == q]
    by_type = {}
    for r in q_rows:
        by_type[r.source_type] = by_type.get(r.source_type, 0) + r.xp_delta
    xp_list = [x for (x,) in db.query(UserDB.xp_points).filter(UserDB.is_active == True).all()]  # noqa: E712
    xp_list.sort(reverse=True)
    rank = (xp_list.index(u.xp_points) + 1) if u.xp_points in xp_list else len(xp_list)
    return {
        'total_xp': u.xp_points,
        'quarter': q,
        'quarter_xp': sum(r.xp_delta for r in q_rows),
        'rank': rank,
        'total_users': len(xp_list),
        'breakdown': by_type,
        'level': min(10, (u.xp_points or 0) // 500 + 1),
    }


@router.get('/xp/ledger')
def xp_ledger(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db),
              limit: int = 50, offset: int = 0):
    rows = (db.query(XpLedgerDB).filter(XpLedgerDB.user_id == u.id)
            .order_by(XpLedgerDB.id.desc()).offset(offset).limit(limit).all())
    return [{'id': r.id, 'xp_delta': r.xp_delta, 'xp_balance': r.xp_balance,
             'source_type': r.source_type, 'source_id': r.source_id,
             'art_multiplier': r.art_multiplier, 'quarter': r.quarter,
             'description': r.description,
             'created_at': r.created_at.isoformat() if r.created_at else None}
            for r in rows]


# ── Best Practices ────────────────────────────────────────────────────────────

@router.get('/practices')
def list_practices(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db),
                   pillar: Optional[str] = None, status: str = 'approved',
                   limit: int = 20, offset: int = 0):
    q = db.query(BestPracticeDB)
    if status == 'mine':
        q = q.filter(BestPracticeDB.author_id == u.id)
    elif status:
        q = q.filter(BestPracticeDB.status == status)
    if pillar:
        q = q.filter(BestPracticeDB.pillar == pillar)
    total = q.count()
    rows  = q.order_by(BestPracticeDB.created_at.desc()).offset(offset).limit(limit).all()
    return {'total': total, 'items': [_bp_dict(bp, db) for bp in rows]}


@router.post('/practices')
def submit_practice(body: PracticeSubmitReq, u: UserDB = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    bp = BestPracticeDB(
        id=str(uuid.uuid4()), author_id=u.id, title=body.title, summary=body.summary,
        why_content=body.why_content, how_content=body.how_content,
        what_content=body.what_content, impact_content=body.impact_content,
        difficulty=body.difficulty, pillar=body.pillar, art_tag=body.art_tag,
        tags=body.tags or [], status=body.status or 'pending',
    )
    db.add(bp)
    db.commit()
    db.refresh(bp)
    return _bp_dict(bp, db)


@router.get('/practices/{practice_id}')
def get_practice(practice_id: str, u: UserDB = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    bp = db.query(BestPracticeDB).filter(BestPracticeDB.id == practice_id).first()
    if not bp:
        raise HTTPException(404, 'Practice not found')
    return _bp_dict(bp, db)


@router.put('/practices/{practice_id}')
def update_practice(practice_id: str, body: PracticeSubmitReq,
                    u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    bp = db.query(BestPracticeDB).filter(
        BestPracticeDB.id == practice_id, BestPracticeDB.author_id == u.id).first()
    if not bp:
        raise HTTPException(404, 'Practice not found or not yours')
    if bp.status == 'approved':
        raise HTTPException(400, 'Approved practices cannot be edited')
    for field, val in body.dict(exclude_unset=True).items():
        setattr(bp, field, val)
    bp.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _bp_dict(bp, db)


@router.delete('/practices/{practice_id}')
def delete_practice(practice_id: str, u: UserDB = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    bp = db.query(BestPracticeDB).filter(
        BestPracticeDB.id == practice_id, BestPracticeDB.author_id == u.id).first()
    if not bp or bp.status == 'approved':
        raise HTTPException(404, 'Practice not found or cannot delete approved')
    db.delete(bp)
    db.commit()
    return {'deleted': True}


def _bp_dict(bp: BestPracticeDB, db: Session) -> dict:
    author = db.query(UserDB).filter(UserDB.id == bp.author_id).first()
    return {
        'id': bp.id, 'title': bp.title, 'summary': bp.summary,
        'why_content': bp.why_content, 'how_content': bp.how_content,
        'what_content': bp.what_content, 'impact_content': bp.impact_content,
        'difficulty': bp.difficulty, 'pillar': bp.pillar, 'art_tag': bp.art_tag,
        'tags': bp.tags or [], 'status': bp.status,
        'xp_awarded': bp.xp_awarded, 'replication_cnt': bp.replication_cnt,
        'is_featured': bp.is_featured, 'reject_reason': bp.reject_reason,
        'author_name': author.name if author else 'Unknown',
        'author_id': bp.author_id,
        'created_at': bp.created_at.isoformat() if bp.created_at else None,
    }


# ── Replications ──────────────────────────────────────────────────────────────

@router.post('/replications')
def submit_replication(body: ReplicationSubmitReq, u: UserDB = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    bp = db.query(BestPracticeDB).filter(
        BestPracticeDB.id == body.practice_id,
        BestPracticeDB.status == 'approved').first()
    if not bp:
        raise HTTPException(404, 'Approved practice not found')
    rep = ReplicationDB(
        id=str(uuid.uuid4()), practice_id=body.practice_id, replicator_id=u.id,
        client_name=body.client_name, po_number=body.po_number,
        po_value_inr=body.po_value_inr, notes=body.notes,
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)
    return _rep_dict(rep, db)


@router.get('/replications/mine')
def my_replications(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db),
                    limit: int = 20, offset: int = 0):
    rows = (db.query(ReplicationDB).filter(ReplicationDB.replicator_id == u.id)
            .order_by(ReplicationDB.created_at.desc()).offset(offset).limit(limit).all())
    return [_rep_dict(r, db) for r in rows]


def _rep_dict(rep: ReplicationDB, db: Session) -> dict:
    bp = db.query(BestPracticeDB).filter(BestPracticeDB.id == rep.practice_id).first()
    return {
        'id': rep.id, 'practice_id': rep.practice_id,
        'practice_title': bp.title if bp else '—',
        'client_name': rep.client_name, 'po_number': rep.po_number,
        'po_value_inr': rep.po_value_inr, 'status': rep.status,
        'xp_awarded': rep.xp_awarded, 'referral_xp': rep.referral_xp,
        'notes': rep.notes,
        'created_at': rep.created_at.isoformat() if rep.created_at else None,
    }


# ── Incentive Statement ───────────────────────────────────────────────────────

@router.get('/incentive/statement')
def incentive_statement(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    q = current_quarter()
    ledger = db.query(XpLedgerDB).filter(
        XpLedgerDB.user_id == u.id, XpLedgerDB.quarter == q).all()
    xp_original    = sum(r.xp_delta for r in ledger if r.source_type == 'original_practice')
    xp_replication = sum(r.xp_delta for r in ledger if r.source_type == 'replication')
    xp_tech_day    = sum(r.xp_delta for r in ledger if r.source_type == 'tech_day')
    xp_other       = sum(r.xp_delta for r in ledger if r.source_type not in (
                         'original_practice', 'replication', 'tech_day'))
    amount = (xp_original * INR_RATE['original_practice'] +
              xp_replication * INR_RATE['replication'] +
              xp_tech_day * INR_RATE['tech_day'])
    inc = db.query(IncentiveCalcDB).filter(
        IncentiveCalcDB.user_id == u.id, IncentiveCalcDB.quarter == q).first()
    if not inc:
        inc = IncentiveCalcDB(
            id=str(uuid.uuid4()), user_id=u.id, quarter=q,
            xp_original=xp_original, xp_replication=xp_replication,
            xp_tech_day=xp_tech_day, xp_other=xp_other,
            amount_inr=str(round(amount, 2)), status='draft',
        )
        db.add(inc)
        db.commit()
    return {
        'quarter': q,
        'xp_original': xp_original,
        'xp_replication': xp_replication,
        'xp_tech_day': xp_tech_day,
        'xp_other': xp_other,
        'xp_total': xp_original + xp_replication + xp_tech_day + xp_other,
        'amount_inr': round(amount, 2),
        'rate_original': INR_RATE['original_practice'],
        'rate_replication': INR_RATE['replication'],
        'rate_tech_day': INR_RATE['tech_day'],
        'status': inc.status if inc else 'draft',
        'payout_date': inc.payout_date.isoformat() if inc and inc.payout_date else None,
    }


# ── Tech Days ─────────────────────────────────────────────────────────────────

@router.post('/tech-days')
def submit_tech_day(body: TechDaySubmitReq, u: UserDB = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    from datetime import date
    try:
        cd = date.fromisoformat(body.conducted_on)
    except Exception:
        raise HTTPException(400, 'Invalid conducted_on date (YYYY-MM-DD)')
    td = TechDayDB(
        id=str(uuid.uuid4()), conductor_id=u.id, title=body.title,
        description=body.description, client_name=body.client_name,
        attendee_count=body.attendee_count, conducted_on=cd,
        evidence_url=body.evidence_url, status='pending',
    )
    db.add(td)
    db.commit()
    db.refresh(td)
    return _td_dict(td)


@router.get('/tech-days/mine')
def my_tech_days(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(TechDayDB).filter(TechDayDB.conductor_id == u.id).order_by(
        TechDayDB.created_at.desc()).limit(20).all()
    return [_td_dict(r) for r in rows]


def _td_dict(td: TechDayDB) -> dict:
    return {
        'id': td.id, 'title': td.title, 'description': td.description,
        'client_name': td.client_name, 'attendee_count': td.attendee_count,
        'conducted_on': td.conducted_on.isoformat() if td.conducted_on else None,
        'status': td.status, 'xp_awarded': td.xp_awarded,
        'evidence_url': td.evidence_url,
        'created_at': td.created_at.isoformat() if td.created_at else None,
    }


# ── Certifications ────────────────────────────────────────────────────────────

@router.post('/certifications')
def submit_cert(body: CertSubmitReq, u: UserDB = Depends(get_current_user),
                db: Session = Depends(get_db)):
    from datetime import date
    cert = CertificationDB(
        id=str(uuid.uuid4()), user_id=u.id, cert_name=body.cert_name,
        provider=body.provider, cert_id=body.cert_id,
        issued_on=date.fromisoformat(body.issued_on) if body.issued_on else None,
        expires_on=date.fromisoformat(body.expires_on) if body.expires_on else None,
        evidence_url=body.evidence_url, xp_awarded=CERT_XP, verified=False,
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    add_xp(db, u.id, CERT_XP, 'certification', source_id=cert.id,
           description=f'Certification: {body.cert_name}')
    db.commit()
    return {'id': cert.id, 'cert_name': cert.cert_name, 'xp_awarded': cert.xp_awarded,
            'verified': cert.verified, 'created_at': cert.created_at.isoformat()}


@router.get('/certifications/mine')
def my_certs(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(CertificationDB).filter(CertificationDB.user_id == u.id).order_by(
        CertificationDB.created_at.desc()).limit(20).all()
    return [{'id': r.id, 'cert_name': r.cert_name, 'provider': r.provider,
             'cert_id': r.cert_id, 'xp_awarded': r.xp_awarded, 'verified': r.verified,
             'issued_on': r.issued_on.isoformat() if r.issued_on else None,
             'created_at': r.created_at.isoformat() if r.created_at else None}
            for r in rows]


# ── Leaderboard (live XP) ─────────────────────────────────────────────────────

@router.get('/leaderboard')
def xp_leaderboard(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db),
                   limit: int = 50):
    users = db.query(UserDB).filter(UserDB.is_active == True).order_by(  # noqa: E712
        UserDB.xp_points.desc()).limit(limit).all()
    return [{'rank': i+1, 'user_id': usr.id, 'name': usr.name, 'department': usr.department,
             'role': usr.role, 'xp': usr.xp_points,
             'is_current_user': usr.id == u.id,
             'initials': ''.join(p[0].upper() for p in usr.name.split()[:2])}
            for i, usr in enumerate(users)]


# ── Admin — Practice Review ───────────────────────────────────────────────────

@router.get('/admin/practices')
def admin_practices(u: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
                    db: Session = Depends(get_db),
                    status: str = 'pending', limit: int = 30, offset: int = 0):
    q = db.query(BestPracticeDB)
    if status != 'all':
        q = q.filter(BestPracticeDB.status == status)
    total = q.count()
    rows  = q.order_by(BestPracticeDB.created_at.desc()).offset(offset).limit(limit).all()
    return {'total': total, 'items': [_bp_dict(bp, db) for bp in rows]}


@router.post('/admin/practices/{practice_id}/approve')
def admin_approve_practice(practice_id: str, request: Request,
                           u: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
                           db: Session = Depends(get_db)):
    bp = db.query(BestPracticeDB).filter(BestPracticeDB.id == practice_id).first()
    if not bp:
        raise HTTPException(404, 'Practice not found')
    bp.status = 'approved'
    bp.reviewer_id = u.id
    bp.reviewed_at = datetime.now(timezone.utc)
    xp, mult = calc_practice_xp(bp.difficulty, bp.art_tag)
    bp.xp_awarded = xp
    new_bal = add_xp(db, bp.author_id, xp, 'original_practice',
                     source_id=bp.id, art_multiplier=mult,
                     description=f'Practice approved: {bp.title}')
    db.commit()
    author = db.query(UserDB).filter(UserDB.id == bp.author_id).first()
    if author:
        _dispatch_notification(db, title='Best Practice Approved! 🎉',
                               body=f'Your practice "{bp.title}" was approved. +{xp} XP credited.',
                               category='approved', target_type='user', target_id=author.id,
                               deep_link='/practices', created_by=u.id)
    audit(db, user_id=u.id, actor_email=u.email, action='practice_approve',
          status='success', request=request, target_type='practice', target_id=practice_id,
          details={'xp': xp, 'author_id': bp.author_id})
    return {'approved': True, 'xp_awarded': xp, 'new_balance': new_bal}


@router.post('/admin/practices/{practice_id}/reject')
def admin_reject_practice(practice_id: str, body: AdminPracticeActionReq, request: Request,
                          u: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
                          db: Session = Depends(get_db)):
    bp = db.query(BestPracticeDB).filter(BestPracticeDB.id == practice_id).first()
    if not bp:
        raise HTTPException(404, 'Practice not found')
    bp.status = 'rejected'
    bp.reviewer_id = u.id
    bp.reviewed_at = datetime.now(timezone.utc)
    bp.reject_reason = body.reject_reason
    db.commit()
    author = db.query(UserDB).filter(UserDB.id == bp.author_id).first()
    if author:
        reason = f' Reason: {body.reject_reason}' if body.reject_reason else ''
        _dispatch_notification(db, title='Practice Submission Update',
                               body=f'Your practice "{bp.title}" needs revision.{reason}',
                               category='approved', target_type='user', target_id=author.id,
                               created_by=u.id)
    return {'rejected': True}


# ── Admin — Replication Review ────────────────────────────────────────────────

@router.get('/admin/replications')
def admin_replications(u: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
                       db: Session = Depends(get_db),
                       status: str = 'pending', limit: int = 30, offset: int = 0):
    q = db.query(ReplicationDB)
    if status != 'all':
        q = q.filter(ReplicationDB.status == status)
    total = q.count()
    rows  = q.order_by(ReplicationDB.created_at.desc()).offset(offset).limit(limit).all()
    return {'total': total, 'items': [_rep_dict(r, db) for r in rows]}


@router.post('/admin/replications/{rep_id}/approve')
def admin_approve_replication(rep_id: str, request: Request,
                              u: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
                              db: Session = Depends(get_db)):
    rep = db.query(ReplicationDB).filter(ReplicationDB.id == rep_id).first()
    if not rep:
        raise HTTPException(404, 'Replication not found')
    bp = db.query(BestPracticeDB).filter(BestPracticeDB.id == rep.practice_id).first()
    has_po = bool(rep.po_number)
    diff = bp.difficulty if bp else 'medium'
    art  = bp.art_tag if bp else None
    xp, ref_xp, mult = calc_replication_xp(diff, has_po, art)
    rep.status = 'approved'
    rep.approved_by = u.id
    rep.approved_at = datetime.now(timezone.utc)
    rep.xp_awarded  = xp
    rep.referral_xp = ref_xp
    add_xp(db, rep.replicator_id, xp, 'replication', source_id=rep.id,
           art_multiplier=mult, description=f'Replication approved: {bp.title if bp else rep.id}')
    if bp and bp.author_id != rep.replicator_id:
        add_xp(db, bp.author_id, ref_xp, 'referral', source_id=rep.id,
               description='Referral XP: your practice was replicated')
        bp.replication_cnt = (bp.replication_cnt or 0) + 1
    db.commit()
    _dispatch_notification(db, title='Replication Approved! 🎉',
                           body=f'Replication for {rep.client_name} approved. +{xp} XP credited.',
                           category='replication', target_type='user', target_id=rep.replicator_id,
                           created_by=u.id)
    return {'approved': True, 'xp_awarded': xp, 'referral_xp': ref_xp}


@router.post('/admin/replications/{rep_id}/reject')
def admin_reject_replication(rep_id: str, body: AdminPracticeActionReq, request: Request,
                             u: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
                             db: Session = Depends(get_db)):
    rep = db.query(ReplicationDB).filter(ReplicationDB.id == rep_id).first()
    if not rep:
        raise HTTPException(404, 'Replication not found')
    rep.status = 'rejected'
    rep.approved_by = u.id
    rep.approved_at = datetime.now(timezone.utc)
    db.commit()
    return {'rejected': True}


# ── Admin — Tech Day Review ───────────────────────────────────────────────────

@router.get('/admin/tech-days')
def admin_tech_days(u: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
                    db: Session = Depends(get_db), status: str = 'pending'):
    q = db.query(TechDayDB)
    if status != 'all':
        q = q.filter(TechDayDB.status == status)
    rows = q.order_by(TechDayDB.created_at.desc()).limit(30).all()
    return [_td_dict(r) for r in rows]


@router.post('/admin/tech-days/{td_id}/approve')
def admin_approve_tech_day(td_id: str, request: Request,
                           u: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
                           db: Session = Depends(get_db)):
    td = db.query(TechDayDB).filter(TechDayDB.id == td_id).first()
    if not td:
        raise HTTPException(404, 'Tech Day not found')
    xp = calc_tech_day_xp(td.attendee_count or 0)
    td.status = 'approved'
    td.approved_by = u.id
    td.xp_awarded = xp
    add_xp(db, td.conductor_id, xp, 'tech_day', source_id=td.id,
           description=f'Tech Day approved: {td.title}')
    db.commit()
    _dispatch_notification(db, title='Tech Day Approved! 🎉',
                           body=f'Your Tech Day "{td.title}" was approved. +{xp} XP.',
                           category='approved', target_type='user', target_id=td.conductor_id,
                           created_by=u.id)
    return {'approved': True, 'xp_awarded': xp}


@router.post('/admin/tech-days/{td_id}/reject')
def admin_reject_tech_day(td_id: str, request: Request,
                          u: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
                          db: Session = Depends(get_db)):
    td = db.query(TechDayDB).filter(TechDayDB.id == td_id).first()
    if not td:
        raise HTTPException(404, 'Tech Day not found')
    td.status = 'rejected'
    db.commit()
    return {'rejected': True}


# ── Admin — Certifications ────────────────────────────────────────────────────

@router.get('/admin/certifications')
def admin_certifications(u: UserDB = Depends(require_role('admin', 'super_admin')),
                         db: Session = Depends(get_db)):
    rows = db.query(CertificationDB).order_by(CertificationDB.created_at.desc()).limit(50).all()
    return [{'id': r.id, 'user_id': r.user_id, 'cert_name': r.cert_name,
             'provider': r.provider, 'xp_awarded': r.xp_awarded, 'verified': r.verified,
             'created_at': r.created_at.isoformat() if r.created_at else None}
            for r in rows]


# ── Admin — Analytics ─────────────────────────────────────────────────────────

@router.get('/admin/analytics/summary')
def admin_analytics(u: UserDB = Depends(require_role('admin', 'super_admin')),
                    db: Session = Depends(get_db)):
    q = current_quarter()
    return {
        'quarter': q,
        'total_users': db.query(UserDB).filter(UserDB.is_active == True).count(),  # noqa: E712
        'pending_user_approvals': db.query(UserDB).filter(UserDB.is_active == False).count(),  # noqa: E712
        'total_practices': db.query(BestPracticeDB).filter(BestPracticeDB.status == 'approved').count(),
        'pending_practices': db.query(BestPracticeDB).filter(BestPracticeDB.status == 'pending').count(),
        'total_replications': db.query(ReplicationDB).filter(ReplicationDB.status == 'approved').count(),
        'pending_replications': db.query(ReplicationDB).filter(ReplicationDB.status == 'pending').count(),
        'total_tech_days': db.query(TechDayDB).filter(TechDayDB.status == 'approved').count(),
        'total_certifications': db.query(CertificationDB).count(),
        'total_xp_quarter': db.query(XpLedgerDB).filter(XpLedgerDB.quarter == q).count(),
        'notifications_sent': db.query(NotificationDB).count(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT E — Notifications Endpoints
# ═══════════════════════════════════════════════════════════════════════════════
@router.get('/notifications/unread-count')
def notif_unread_count(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.query(UserNotificationDB).filter(
        UserNotificationDB.user_id == u.id,
        UserNotificationDB.is_read == False,   # noqa: E712
        UserNotificationDB.is_dismissed == False).count()  # noqa: E712
    return {'count': count}


@router.get('/notifications')
def list_notifications(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db),
                       limit: int = 30, offset: int = 0, unread_only: bool = False):
    q = db.query(UserNotificationDB, NotificationDB).join(
        NotificationDB, NotificationDB.id == UserNotificationDB.notification_id).filter(
        UserNotificationDB.user_id == u.id,
        UserNotificationDB.is_dismissed == False)  # noqa: E712
    if unread_only:
        q = q.filter(UserNotificationDB.is_read == False)  # noqa: E712
    total = q.count()
    rows  = q.order_by(UserNotificationDB.delivered_at.desc()).offset(offset).limit(limit).all()
    return {
        'total': total,
        'items': [{
            'id': un.id, 'notification_id': n.id,
            'title': n.title, 'body': n.body, 'category': n.category,
            'is_urgent': n.is_urgent, 'deep_link': n.deep_link,
            'is_read': un.is_read,
            'delivered_at': un.delivered_at.isoformat() if un.delivered_at else None,
            'read_at': un.read_at.isoformat() if un.read_at else None,
        } for un, n in rows]
    }


@router.put('/notifications/{un_id}/read')
def mark_notification_read(un_id: int, u: UserDB = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    un = db.query(UserNotificationDB).filter(
        UserNotificationDB.id == un_id, UserNotificationDB.user_id == u.id).first()
    if not un:
        raise HTTPException(404, 'Notification not found')
    un.is_read = True
    un.read_at = datetime.now(timezone.utc)
    db.commit()
    return {'read': True}


@router.put('/notifications/read-all')
def mark_all_read(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(UserNotificationDB).filter(
        UserNotificationDB.user_id == u.id,
        UserNotificationDB.is_read == False).update(  # noqa: E712
        {'is_read': True, 'read_at': datetime.now(timezone.utc)})
    db.commit()
    return {'done': True}


@router.post('/admin/notifications/send')
def send_notification(body: SendNotificationReq, request: Request,
                      u: UserDB = Depends(require_role('admin', 'super_admin')),
                      db: Session = Depends(get_db)):
    notif = _dispatch_notification(
        db, title=body.title, body=body.body, category=body.category,
        target_type=body.target_type, target_id=body.target_id,
        is_urgent=body.is_urgent, deep_link=body.deep_link, created_by=u.id,
    )
    audit(db, user_id=u.id, actor_email=u.email, action='notification_send',
          status='success', request=request, target_type=body.target_type, target_id=body.target_id,
          details={'title': body.title, 'category': body.category})
    return {'sent': True, 'notification_id': notif.id}


@router.get('/admin/notifications')
def admin_notifications_list(u: UserDB = Depends(require_role('admin', 'super_admin')),
                             db: Session = Depends(get_db), limit: int = 50, offset: int = 0):
    rows = db.query(NotificationDB).order_by(
        NotificationDB.created_at.desc()).offset(offset).limit(limit).all()
    return [{'id': n.id, 'title': n.title, 'body': n.body, 'category': n.category,
             'target_type': n.target_type, 'target_id': n.target_id,
             'is_urgent': n.is_urgent, 'sent_at': n.sent_at.isoformat() if n.sent_at else None,
             'created_at': n.created_at.isoformat() if n.created_at else None}
            for n in rows]


# ── WebSocket endpoint for clients ────────────────────────────────────────────
# NOTE: WebSocket lives at /api/ws (NOT /ws) so it routes through the same
# kubernetes/nginx ingress rule as REST. Clients connect to:
#   wss://<host>/api/ws
@app.websocket('/api/ws')
async def ws_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send a hello so client knows it's connected
        await websocket.send_text('{"type":"hello","msg":"hsi-platform live channel"}')
        # Keep alive — clients can send pings; we just echo to keep connection healthy
        while True:
            data = await websocket.receive_text()
            if data == 'ping':
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:                                          # noqa: BLE001
        await ws_manager.disconnect(websocket)


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


# ── Sprint E — Birthday XP Scheduler ─────────────────────────────────────────
# Awards 50 XP to every user whose birthday is today (daily at 00:05 IST).

def _run_birthday_xp_job():
    """Grant 50 XP to every user born on today's date (month + day match)."""
    try:
        db = SessionLocal()
        today = datetime.now(timezone.utc)
        # Find users with birthday matching today (month and day)
        users = db.query(UserDB).filter(
            UserDB.is_active == True,  # noqa: E712
            UserDB.date_of_birth != None,  # noqa: E711
        ).all()
        count = 0
        for u in users:
            if u.date_of_birth and u.date_of_birth.month == today.month and u.date_of_birth.day == today.day:
                # Check not already awarded today
                existing = db.query(XpLedgerDB).filter(
                    XpLedgerDB.user_id == u.id,
                    XpLedgerDB.source_type == 'birthday',
                    XpLedgerDB.quarter == current_quarter(),
                ).first()
                if not existing:
                    add_xp(db, u.id, BIRTHDAY_XP, 'birthday',
                           description=f'Happy Birthday {u.name}! 🎂 +{BIRTHDAY_XP} XP')
                    _dispatch_notification(
                        db,
                        title=f'🎂 Happy Birthday, {u.name.split()[0]}!',
                        body=f'Wishing you a wonderful birthday! +{BIRTHDAY_XP} XP has been added to your account.',
                        category='birthday', target_type='user', target_id=u.id,
                    )
                    count += 1
        logger.info(f"[BirthdayJob] Awarded {BIRTHDAY_XP} XP to {count} user(s)")
    except Exception as e:
        logger.error(f"[BirthdayJob] Error: {e}")
    finally:
        db.close()


try:
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler(timezone='Asia/Kolkata')
    _scheduler.add_job(_run_birthday_xp_job, 'cron', hour=0, minute=5, id='birthday_xp')
    _scheduler.start()
    logger.info("[Scheduler] Birthday XP job scheduled at 00:05 IST daily")
except Exception as _sched_err:
    logger.warning(f"[Scheduler] Could not start scheduler: {_sched_err}")
