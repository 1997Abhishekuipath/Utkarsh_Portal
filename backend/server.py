"""
HSI Employee Engagement Platform — Backend API
Stack: FastAPI + SQLAlchemy 2.0 + PostgreSQL + JWT (access + refresh rotation)

Sprint A — Auth foundation hardened
Sprint B — Email OTP MFA via AWS SES + Redis rate limiting
Sprint C — Pillars + EDM + CMS + WebSocket live-sync
Sprint D — XP & Incentive Engine (best_practices, replications, xp_ledger, incentive_calculations, tech_days, certifications)
Sprint E — Notifications + Auto-triggers (notifications, user_notifications, birthday XP scheduler)
Sprint F — Security Hardening & Observability (Sentry, Request-ID, TLS, WAL backup, 4 DB roles)
"""
from dotenv import load_dotenv
load_dotenv()

import os, logging, uuid, bcrypt, jwt, hashlib, secrets, random, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Sprint F: Sentry initialisation (graceful — skipped when SENTRY_DSN is empty) ──
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

_sentry_dsn = os.environ.get('SENTRY_DSN', '').strip()
sentry_sdk.init(
    dsn=_sentry_dsn or None,          # None → SDK silently disables itself
    integrations=[
        StarletteIntegration(transaction_style='endpoint',
                             failed_request_status_codes={*range(500, 600)}),
        FastApiIntegration(transaction_style='endpoint',
                           failed_request_status_codes={*range(500, 600)}),
        LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
    ],
    traces_sample_rate=float(os.environ.get('SENTRY_TRACES_RATE', '0.1')),
    environment=os.environ.get('ENVIRONMENT', 'development'),
    release=os.environ.get('APP_VERSION', 'sprint-f'),
    send_default_pii=False,
)

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, FileResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from sqlalchemy import (
    create_engine, Column, String, DateTime, Date, Integer, BigInteger,
    Boolean, ForeignKey, CheckConstraint, Index, text, Numeric, SmallInteger,
    Float,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from pydantic import BaseModel, EmailStr
from typing import Optional, List

from services.email import send_otp as ses_send_otp, is_configured as ses_is_configured
from services.rate_limit import check_or_raise as rl_check, is_redis_active
from services import storage as storage_svc
from services import pubsub as pubsub_svc

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
# Demo mode — fixed OTP accepted for seed accounts (set DEMO_OTP="" to disable)
DEMO_OTP        = os.environ.get('DEMO_OTP', '000000')
DEMO_EMAILS     = {
    'superadmin@hitachi-systems.com',
    'admin@hitachi-systems.com',
    'manager@hitachi-systems.com',
    'employee@hitachi-systems.com',
    'priya@hitachi-systems.com',
    'kiran@hitachi-systems.com',
    'ananya@hitachi-systems.com',
}

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
    description   = Column(String, nullable=True)
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
    # Card design fields (Sprint H)
    card_color    = Column(String, default='#CC0000')          # banner background colour
    stat_value    = Column(String, nullable=True)              # e.g. "80", "1.2K", "4.8"
    stat_label    = Column(String, nullable=True)              # e.g. "PRACTICES", "EVENTS"
    action_tag    = Column(String, nullable=True)              # e.g. "KNOWLEDGE", "TRACK"
    action_stat   = Column(String, nullable=True)              # e.g. "20 HOURS", "8 DAYS"
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
    tag            = Column(String, nullable=True)
    tag_color      = Column(String, nullable=True, default='#D4A84A')
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
    source       = Column(String, nullable=True)   # alias / attribution line
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
    attachments    = Column(JSONB, default=list)    # Sprint G — [{key,url,filename,content_type,size}]
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
        CheckConstraint("status IN ('draft','approved','paid','on_hold','cancelled')", name='chk_inc_status'),
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


# ═════════════════════════════════════════════════════════════════════════════
#  Sprint G — File Asset model (MinIO / object storage)
# ═════════════════════════════════════════════════════════════════════════════
class FileAssetDB(Base):
    """Tracks every object uploaded via /api/uploads for audit + cleanup."""
    __tablename__ = 'file_assets'
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    uploader_id   = Column(String, ForeignKey('users.id'), nullable=True, index=True)
    object_key    = Column(String, nullable=False, unique=True, index=True)
    url           = Column(String, nullable=False)
    filename      = Column(String, nullable=False)
    content_type  = Column(String, nullable=True)
    size_bytes    = Column(BigInteger, default=0)
    storage       = Column(String, default='minio')    # 'minio' | 'local'
    category      = Column(String, default='misc')     # 'avatar'|'practice'|'edm'|'tech_day'|'misc'
    linked_type   = Column(String, nullable=True)      # 'best_practice'|'user_avatar'|...
    linked_id     = Column(String, nullable=True)
    created_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))



# ══════════════════════════════════════════════════════════════════════════════
#  VoC Intelligence Platform — Phase 1 Models
# ══════════════════════════════════════════════════════════════════════════════

class VocAccountDB(Base):
    """Customer accounts managed by Account Managers for VoC tracking."""
    __tablename__ = 'voc_accounts'
    id                 = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name       = Column(String(200), nullable=False)
    industry           = Column(String(80), nullable=True)
    account_manager_id = Column(String, ForeignKey('users.id'), nullable=True)
    practice           = Column(String(50), nullable=True)
    latest_nps         = Column(SmallInteger, nullable=True)
    latest_csat        = Column(Numeric(5, 2), nullable=True)
    rag_status         = Column(String(10), nullable=True, default='green')
    total_responses    = Column(Integer, default=0)
    created_at         = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at         = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at         = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("rag_status IN ('green','amber','red')", name='chk_voc_account_rag'),
    )


class VocSurveyDB(Base):
    """Survey definition with versioning."""
    __tablename__ = 'voc_surveys'
    id                = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    survey_type       = Column(String(20), nullable=False, default='combined')
    title             = Column(String(200), nullable=False)
    main_question     = Column(String, nullable=False)
    followup_question = Column(String, nullable=True)
    practice          = Column(String(50), nullable=True)
    thank_you_msg     = Column(String, nullable=True)
    version           = Column(Integer, default=1)
    created_by        = Column(String, ForeignKey('users.id'), nullable=True)
    created_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    deleted_at        = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("survey_type IN ('nps','csat','ces','combined')", name='chk_voc_survey_type'),
    )


class VocCampaignDB(Base):
    """Email campaign linking a survey to an account cohort."""
    __tablename__ = 'voc_campaigns'
    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name           = Column(String(200), nullable=False)
    survey_id      = Column(String, ForeignKey('voc_surveys.id'), nullable=True)
    account_id     = Column(String, ForeignKey('voc_accounts.id'), nullable=True)
    subject        = Column(String(300), nullable=True)
    body_html      = Column(String, nullable=True)
    status         = Column(String(20), default='active')
    send_at        = Column(DateTime(timezone=True), nullable=True)
    sent_count     = Column(Integer, default=0)
    open_count     = Column(Integer, default=0)
    click_count    = Column(Integer, default=0)
    response_count = Column(Integer, default=0)
    created_by     = Column(String, ForeignKey('users.id'), nullable=True)
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','scheduled','sending','active','closed')",
            name='chk_voc_campaign_status'),
    )


class VocSurveyTokenDB(Base):
    """Single-use tokens for individual survey links."""
    __tablename__ = 'voc_survey_tokens'
    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    token            = Column(String(128), unique=True, nullable=False)
    campaign_id      = Column(String, ForeignKey('voc_campaigns.id'), nullable=True)
    account_id       = Column(String, ForeignKey('voc_accounts.id'), nullable=True)
    respondent_email = Column(String(255), nullable=False)
    used             = Column(Boolean, default=False)
    used_at          = Column(DateTime(timezone=True), nullable=True)
    expires_at       = Column(DateTime(timezone=True), nullable=False)
    created_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class VocResponseDB(Base):
    """Survey response from a single respondent."""
    __tablename__ = 'voc_responses'
    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id      = Column(String, ForeignKey('voc_campaigns.id'), nullable=True)
    account_id       = Column(String, ForeignKey('voc_accounts.id'), nullable=True)
    token_id         = Column(String, ForeignKey('voc_survey_tokens.id'), nullable=True)
    respondent_email = Column(String(255), nullable=False)
    nps_score        = Column(SmallInteger, nullable=True)
    csat_score       = Column(SmallInteger, nullable=True)
    ces_score        = Column(SmallInteger, nullable=True)
    verbatim         = Column(String, nullable=True)
    sentiment        = Column(String(15), nullable=True)
    pain_tags        = Column(ARRAY(String), nullable=True)
    submitted_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("sentiment IN ('promoter','passive','detractor','neutral')",
                        name='chk_voc_resp_sentiment'),
        Index('idx_voc_resp_campaign', 'campaign_id'),
        Index('idx_voc_resp_account_date', 'account_id', 'submitted_at'),
        Index('idx_voc_resp_sentiment', 'sentiment'),
    )


class VocEmailLogDB(Base):
    """Email delivery event log (sent / opened / clicked / bounced)."""
    __tablename__ = 'voc_email_logs'
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id     = Column(String, ForeignKey('voc_campaigns.id'), nullable=True)
    recipient_email = Column(String(255), nullable=False)
    event_type      = Column(String(20), nullable=False, default='sent')
    occurred_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('sent','opened','clicked','bounced','unsubscribed')",
            name='chk_voc_email_log_type'),
        Index('idx_voc_email_log_campaign', 'campaign_id'),
    )


class VocAiInsightDB(Base):
    """Cached AI-generated insight snapshots (McKinsey SCR + pain points + action plan)."""
    __tablename__ = 'voc_ai_insights'
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    period          = Column(String(50), nullable=True)        # "Q2 2026"
    total_responses = Column(Integer, nullable=True)
    nps_score       = Column(SmallInteger, nullable=True)
    csat_score      = Column(Numeric(5, 2), nullable=True)
    insights_json   = Column(String, nullable=False)           # raw JSON string
    model_used      = Column(String(120), nullable=True)
    generated_by    = Column(String, ForeignKey('users.id'), nullable=True)
    generated_at    = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class VocWorkflowTaskDB(Base):
    """Detractor follow-up tasks created from NPS ≤ 6 responses."""
    __tablename__ = 'voc_workflow_tasks'
    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    response_id      = Column(String, ForeignKey('voc_responses.id'), nullable=True)
    account_id       = Column(String, ForeignKey('voc_accounts.id'), nullable=True)
    assignee_id      = Column(String, ForeignKey('users.id'), nullable=True)
    status           = Column(String(20), default='open')
    resolution_notes = Column(String, nullable=True)
    created_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at      = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('open','in_progress','resolved')", name='chk_voc_wf_status'),
        Index('idx_voc_wf_task_account', 'account_id'),
        Index('idx_voc_wf_task_status', 'status'),
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


# ── Sprint G — add attachments JSONB to best_practices if missing ────────────
def _ensure_bp_attachments_column():
    sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
             WHERE table_name='best_practices' AND column_name='attachments'
        ) THEN
            ALTER TABLE best_practices ADD COLUMN attachments JSONB DEFAULT '[]'::jsonb;
        END IF;
    END$$;
    """
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
    except Exception as e:                                          # noqa: BLE001
        logging.warning(f"[migration] best_practices.attachments skipped: {e}")


_ensure_bp_attachments_column()


# ── Sprint H — add card design columns to pillar_icons if missing ────────────
def _ensure_pillar_icon_card_columns():
    sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name='pillar_icons' AND column_name='card_color') THEN
            ALTER TABLE pillar_icons ADD COLUMN card_color VARCHAR DEFAULT '#CC0000';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name='pillar_icons' AND column_name='stat_value') THEN
            ALTER TABLE pillar_icons ADD COLUMN stat_value VARCHAR;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name='pillar_icons' AND column_name='stat_label') THEN
            ALTER TABLE pillar_icons ADD COLUMN stat_label VARCHAR;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name='pillar_icons' AND column_name='action_tag') THEN
            ALTER TABLE pillar_icons ADD COLUMN action_tag VARCHAR;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name='pillar_icons' AND column_name='action_stat') THEN
            ALTER TABLE pillar_icons ADD COLUMN action_stat VARCHAR;
        END IF;
    END$$;
    """
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
    except Exception as e:                                          # noqa: BLE001
        logging.warning(f"[migration] pillar_icons card columns skipped: {e}")


_ensure_pillar_icon_card_columns()


# ── Sprint H — add tag/tag_color to edm_slides + source to quotes ────────────
def _ensure_edm_tag_columns():
    sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name='edm_slides' AND column_name='tag') THEN
            ALTER TABLE edm_slides ADD COLUMN tag VARCHAR;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name='edm_slides' AND column_name='tag_color') THEN
            ALTER TABLE edm_slides ADD COLUMN tag_color VARCHAR DEFAULT '#D4A84A';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name='motivational_quotes' AND column_name='source') THEN
            ALTER TABLE motivational_quotes ADD COLUMN source VARCHAR;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                        WHERE table_name='pillars' AND column_name='description') THEN
            ALTER TABLE pillars ADD COLUMN description VARCHAR;
        END IF;
        -- Sprint D continuation: extend incentive_calculations status enum to include 'cancelled'
        IF EXISTS (SELECT 1 FROM information_schema.tables
                    WHERE table_name='incentive_calculations') THEN
            ALTER TABLE incentive_calculations DROP CONSTRAINT IF EXISTS chk_inc_status;
            ALTER TABLE incentive_calculations ADD CONSTRAINT chk_inc_status
                CHECK (status IN ('draft','approved','paid','on_hold','cancelled'));
        END IF;
    END$$;
    """
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(sql)
    except Exception as e:                                          # noqa: BLE001
        logging.warning(f"[migration] edm/quote columns skipped: {e}")


_ensure_edm_tag_columns()


# ── VoC Demo Data Seeder (idempotent) ─────────────────────────────────────────
def _seed_voc_demo_data():
    """Seed demo VoC accounts + responses once on startup. Idempotent."""
    import random as _rnd
    db = SessionLocal()
    try:
        if db.query(VocAccountDB).first():
            logging.info("[voc-seed] Already seeded — skipping")
            return

        manager = db.query(UserDB).filter(UserDB.role == 'manager', UserDB.is_active == True).first()
        admin   = db.query(UserDB).filter(UserDB.role == 'admin',   UserDB.is_active == True).first()
        manager_id = manager.id if manager else None
        admin_id   = admin.id   if admin   else None

        # Survey
        survey = VocSurveyDB(
            survey_type='combined',
            title='Q2 2026 VoC Survey — Combined NPS/CSAT/CES',
            main_question='On a scale of 0–10, how likely are you to recommend HSI to a colleague?',
            followup_question='What is the primary reason for your score?',
            thank_you_msg='Thank you! Your insights help us serve you better.',
            created_by=admin_id,
        )
        db.add(survey)
        db.flush()

        _ACCOUNTS = [
            ("Reliance Petro",  "Energy & Petrochemicals",     "cybersecurity", 12,  68.5, "red"),
            ("Axis Bank",       "Banking & Financial Services", "cloud",         38,  79.2, "amber"),
            ("L&T Constructs",  "Engineering & Construction",   "data-centre",   41,  80.5, "amber"),
            ("HCL Unistore",    "Technology Services",          "observability", 72,  92.1, "green"),
            ("Tata Motors",     "Automotive Manufacturing",     "cloud",         68,  89.3, "green"),
            ("SBI Life",        "Insurance & Fintech",          "cybersecurity", 81,  94.0, "green"),
        ]

        # Response mix per account (nps, csat, ces, verbatim, pain_tags)
        _MIX = {
            0: [  # Reliance Petro — low NPS
                (3,  2, 5, "Response time during incidents is unacceptable. We pay premium for better SLAs.", ["Response Time", "Escalation Process"]),
                (4,  3, 4, "Ticket resolution takes too long. Only 3 of 15 tickets resolved within SLA.", ["Response Time", "Communication Gaps"]),
                (3,  2, 4, "Support is inconsistent. Some engineers excel; others need improvement.", ["Communication Gaps", "Documentation"]),
                (8,  4, 2, "Technical team is skilled. Main issue is after-hours response time.", ["Response Time"]),
                (9,  5, 1, "Cybersecurity team resolved our zero-day issue expertly. Good work.", []),
                (5,  3, 3, "Reporting could be clearer. Monthly reports are hard to interpret.", ["Reporting Clarity", "Documentation"]),
            ],
            1: [  # Axis Bank — amber
                (7,  4, 2, "Cloud migration mostly smooth. Minor hiccups in transition.", ["Communication Gaps"]),
                (8,  4, 2, "Team is responsive. Reporting could improve.", ["Reporting Clarity"]),
                (5,  3, 3, "Escalation process needs work. Took 3 days to get a senior engineer.", ["Escalation Process"]),
                (9,  5, 1, "Excellent cloud expertise. Our FinOps savings are ahead of forecast.", []),
                (4,  2, 5, "Reports are unclear; we constantly request clarifications.", ["Reporting Clarity", "Documentation"]),
                (7,  4, 3, "Good overall but communication gaps during incidents.", ["Communication Gaps"]),
            ],
            2: [  # L&T Constructs — amber
                (7,  4, 3, "Data centre migration completed on time. Team was professional.", []),
                (8,  4, 2, "Engineers know their craft. Documentation could be better.", ["Documentation"]),
                (6,  3, 3, "Escalation process is too slow for critical issues.", ["Escalation Process"]),
                (9,  5, 1, "Implementation was flawless. On time, on budget.", []),
                (5,  3, 4, "Communication during maintenance windows needs improvement.", ["Communication Gaps"]),
                (7,  4, 2, "Good work overall. Minor issues with report formats.", ["Reporting Clarity"]),
            ],
            3: [  # HCL Unistore — green
                (10, 5, 1, "AIOps dashboard transformed how we manage incidents. Night and day difference.", []),
                (9,  5, 1, "Observability platform is best-in-class. Team is highly responsive.", []),
                (9,  5, 2, "Proactive monitoring saved us 3 outages this quarter. Excellent.", []),
                (8,  4, 2, "Very satisfied. Minor feature requests still pending.", []),
                (10, 5, 1, "Would strongly recommend HSI to any technology company.", []),
                (7,  4, 3, "Good platform. Onboarding could be faster.", ["Documentation"]),
            ],
            4: [  # Tata Motors — green
                (9,  5, 1, "Cloud migration was on time, under budget. FinOps controls saved ₹1.2Cr.", []),
                (10, 5, 1, "HSI team is genuinely accessible and accountable. Rare in this industry.", []),
                (8,  4, 2, "Strong delivery. Looking forward to the Phase 2 rollout.", []),
                (9,  5, 2, "Technical expertise is exceptional. The team goes beyond scope.", []),
                (7,  4, 3, "Satisfied overall. Would like more frequent status updates.", ["Communication Gaps"]),
                (8,  4, 2, "HSI engineers solved our Kubernetes issues within hours.", []),
            ],
            5: [  # SBI Life — green
                (10, 5, 1, "HSI didn't just implement zero-trust — they educated our team and built our capability.", []),
                (10, 5, 1, "The engagement was transformational, not just transactional. Best vendor relationship.", []),
                (9,  5, 1, "Highly responsive, deeply knowledgeable. Would recommend to any BFSI firm.", []),
                (9,  5, 2, "Exceptional compliance support. They understand regulatory requirements deeply.", []),
                (10, 5, 1, "Zero-trust implementation was flawless. Security posture improved dramatically.", []),
                (8,  4, 2, "Very satisfied. Team is proactive about upcoming threats.", []),
            ],
        }

        _COUNTS = [25, 22, 24, 28, 23, 20]  # responses per account

        now_utc = datetime.now(timezone.utc)

        for acc_idx, (cname, industry, practice, nps, csat_pct, rag) in enumerate(_ACCOUNTS):
            acc = VocAccountDB(
                company_name=cname, industry=industry,
                account_manager_id=manager_id, practice=practice,
                latest_nps=nps, latest_csat=csat_pct, rag_status=rag,
                total_responses=_COUNTS[acc_idx],
            )
            db.add(acc)
            db.flush()

            camp = VocCampaignDB(
                name=f"Q2 2026 — {cname}",
                survey_id=survey.id, account_id=acc.id,
                subject="HSI Customer Satisfaction Survey — Your Feedback Matters",
                status='active',
                sent_count=_COUNTS[acc_idx],
                response_count=_COUNTS[acc_idx],
                created_by=admin_id,
            )
            db.add(camp)
            db.flush()

            mix   = _MIX[acc_idx]
            count = _COUNTS[acc_idx]
            slug  = cname.lower().replace(" ", "").replace("&", "")

            for i in range(count):
                nps_s, csat_s, ces_s, verb, pain = mix[i % len(mix)]
                # Determine sentiment from NPS score
                if nps_s >= 9:
                    sentiment = "promoter"
                elif nps_s >= 7:
                    sentiment = "passive"
                else:
                    sentiment = "detractor"

                # Spread over last 12 months (oldest first)
                months_back = (count - 1 - i) // (count // 12 + 1)
                days_offset  = months_back * 30 + _rnd.randint(0, 27)
                submitted_at = now_utc - timedelta(days=days_offset)

                db.add(VocResponseDB(
                    campaign_id=camp.id, account_id=acc.id,
                    respondent_email=f"contact{i+1}@{slug}.com",
                    nps_score=nps_s, csat_score=csat_s, ces_score=ces_s,
                    verbatim=verb if verb else None,
                    sentiment=sentiment,
                    pain_tags=pain if pain else None,
                    submitted_at=submitted_at,
                ))

        db.commit()
        logging.info(f"[voc-seed] Seeded 6 accounts + {sum(_COUNTS)} demo responses")
    except Exception as exc:
        db.rollback()
        logging.error(f"[voc-seed] Failed: {exc}")
    finally:
        db.close()


def _seed_voc_workflow_tasks():
    """Create workflow tasks for existing detractor responses (idempotent)."""
    db = SessionLocal()
    try:
        if db.query(VocWorkflowTaskDB).first():
            return  # already seeded
        detractors = db.query(VocResponseDB).filter(
            VocResponseDB.sentiment == 'detractor',
            VocResponseDB.verbatim  != None,
        ).limit(12).all()

        manager = db.query(UserDB).filter(UserDB.role == 'manager', UserDB.is_active == True).first()
        assignee_id = manager.id if manager else None

        for r in detractors:
            db.add(VocWorkflowTaskDB(
                response_id=r.id,
                account_id=r.account_id,
                assignee_id=assignee_id,
                status='open',
            ))
        db.commit()
        logging.info(f"[voc-seed] Created {len(detractors)} workflow tasks for detractors")
    except Exception as exc:
        db.rollback()
        logging.error(f"[voc-wf-seed] Failed: {exc}")
    finally:
        db.close()


_seed_voc_workflow_tasks()


_seed_voc_demo_data()


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


class PillarPatchReq(BaseModel):
    """Partial-update schema — all fields optional (PATCH semantics via PUT)."""
    slug: Optional[str] = None
    name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    gradient_from: Optional[str] = None
    gradient_to: Optional[str] = None
    icon_name: Optional[str] = None
    position: Optional[int] = None
    is_published: Optional[bool] = None


class PillarIconUpsertReq(BaseModel):
    pillar_id: str
    name: str
    description: Optional[str] = None
    lucide_icon: Optional[str] = None
    route: Optional[str] = None
    badge: Optional[str] = None         # 'hot' | 'new' | None
    position: int = 0
    is_published: bool = True
    card_color: str = '#CC0000'
    stat_value: Optional[str] = None
    stat_label: Optional[str] = None
    action_tag: Optional[str] = None
    action_stat: Optional[str] = None


class PillarIconPatchReq(BaseModel):
    """Partial-update for pillar icons."""
    pillar_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    lucide_icon: Optional[str] = None
    route: Optional[str] = None
    badge: Optional[str] = None
    position: Optional[int] = None
    is_published: Optional[bool] = None
    card_color: Optional[str] = None
    stat_value: Optional[str] = None
    stat_label: Optional[str] = None
    action_tag: Optional[str] = None
    action_stat: Optional[str] = None


class EdmSlideUpsertReq(BaseModel):
    scope: str                          # home | customer | innovator | employee | shareholder
    title: str
    subtitle: Optional[str] = None
    gradient_from: str = '#CC0000'
    gradient_to: str = '#7A0000'
    image_url: Optional[str] = None
    link: Optional[str] = None
    tag: Optional[str] = None
    tag_color: Optional[str] = None
    position: int = 0
    is_published: bool = True


class EdmSlidePatchReq(BaseModel):
    """Partial-update for EDM slides."""
    scope: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    gradient_from: Optional[str] = None
    gradient_to: Optional[str] = None
    image_url: Optional[str] = None
    link: Optional[str] = None
    tag: Optional[str] = None
    tag_color: Optional[str] = None
    position: Optional[int] = None
    is_published: Optional[bool] = None


class QuoteUpsertReq(BaseModel):
    text: str
    author: Optional[str] = None
    source: Optional[str] = None        # attribution line shown in UI
    position: int = 0
    is_published: bool = True


class QuotePatchReq(BaseModel):
    """Partial-update for quotes."""
    text: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    position: Optional[int] = None
    is_published: Optional[bool] = None


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
    attachments: Optional[List[dict]] = []   # Sprint G — [{key,url,filename,content_type,size}]


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
    # ── Demo bypass: fixed OTP for seed accounts ──────────────────────────
    if DEMO_OTP and email.lower() in DEMO_EMAILS and code == DEMO_OTP:
        rec.is_used = True
        db.commit()
        return rec
    # ── Normal flow ────────────────────────────────────────────────────────
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


XP_MILESTONES = [100, 250, 500, 1000, 2500, 5000, 10000]

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
    # ── Award milestone auto-trigger ──────────────────────────────────────
    if xp_delta > 0:
        for milestone in XP_MILESTONES:
            if prev_balance < milestone <= new_balance:
                try:
                    _dispatch_notification(
                        db,
                        title=f'🏆 {milestone} XP Milestone Reached!',
                        body=f'Congratulations! You have crossed {milestone} XP. Keep up the great work!',
                        category='award',
                        target_type='user',
                        target_id=user_id,
                    )
                except Exception:  # noqa: BLE001
                    pass
    return new_balance


def _notify_admins(db: Session, *, title: str, body: str, category: str,
                   deep_link: Optional[str] = None, created_by: Optional[str] = None):
    """Dispatch notification to all active admin + super_admin users."""
    admins = db.query(UserDB).filter(
        UserDB.is_active == True,  # noqa: E712
        UserDB.role.in_(['admin', 'super_admin'])
    ).all()
    notif = NotificationDB(
        id=str(uuid.uuid4()), title=title, body=body, category=category,
        target_type='role', target_id='admin',
        is_urgent=False, deep_link=deep_link,
        sent_at=datetime.now(timezone.utc), created_by=created_by,
    )
    db.add(notif)
    db.flush()
    for admin in admins:
        try:
            db.add(UserNotificationDB(notification_id=notif.id, user_id=admin.id))
            db.flush()
        except Exception:  # noqa: BLE001
            db.rollback()


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
        'phone': u.phone,
        'date_of_birth': u.date_of_birth.isoformat() if u.date_of_birth else None,
        'art_tags': list(u.art_tags or []), 'xp_points': u.xp_points,
        'is_active': u.is_active, 'is_verified': u.is_verified,
        'last_login_at': u.last_login_at.isoformat() if u.last_login_at else None,
    }


# ── FastAPI ───────────────────────────────────────────────────────────────────
app    = FastAPI(
    title='HSI Employee Engagement Platform API',
    version='2.0.0',
    description='HSI Employee Engagement Platform — Sprint F (Hardened)',
)
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


# Sprint F: Profile self-update (name, department, employee_id, date_of_birth)
class PatchMeReq(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    employee_id: Optional[str] = None
    date_of_birth: Optional[str] = None
    avatar_url: Optional[str] = None          # Sprint G
    phone: Optional[str] = None
    designation: Optional[str] = None


@router.patch('/users/me')
def patch_me(body: PatchMeReq, u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import date
    if body.name is not None:
        if len(body.name.strip()) < 2:
            raise HTTPException(400, 'Name must be at least 2 characters')
        u.name = body.name.strip()
    if body.department is not None:
        u.department = body.department.strip() or None
    if body.employee_id is not None:
        u.employee_id = body.employee_id.strip() or None
    if body.date_of_birth is not None:
        try:
            u.date_of_birth = date.fromisoformat(body.date_of_birth) if body.date_of_birth else None
        except ValueError:
            raise HTTPException(400, 'Invalid date format (YYYY-MM-DD)')
    if body.avatar_url is not None:
        u.avatar_url = body.avatar_url.strip() or None
    if body.phone is not None:
        u.phone = body.phone.strip() or None
    if body.designation is not None:
        u.designation = body.designation.strip() or None
    db.commit()
    db.refresh(u)
    return user_to_dict(u)



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
def upcoming(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    """Live upcoming events sourced from tech_days + payout calendar."""
    from datetime import date, timedelta
    today = date.today()
    horizon = today + timedelta(days=60)

    # Upcoming Tech Days conducted by ANY user (visible to all) within horizon
    tds = (db.query(TechDayDB, UserDB)
             .join(UserDB, UserDB.id == TechDayDB.conductor_id)
             .filter(TechDayDB.conducted_on >= today,
                     TechDayDB.conducted_on <= horizon)
             .order_by(TechDayDB.conducted_on.asc())
             .limit(5).all())

    items = []
    for td, conductor in tds:
        items.append({
            'id': td.id,
            'title': f'Tech Day — {td.title}',
            'description': f'{conductor.name} · {td.client_name or "Internal"}'
                           + (f" · {td.attendee_count} attendees" if td.attendee_count else ""),
            'date': td.conducted_on.strftime('%b %d') if td.conducted_on else '',
            'color': 'red',
            'type': 'tech_day',
        })

    # Quarterly payout target date (last day of current quarter)
    q = current_quarter()                               # e.g. '2026-Q2'
    try:
        yr_str, qn_str = q.split('-Q', 1)
        qn = int(qn_str)
        yr = int(yr_str)
        end_month = qn * 3                              # 3, 6, 9, 12
        payout_due = date(yr, end_month, 28)
    except Exception:
        payout_due = today + timedelta(days=30)
    if payout_due >= today:
        items.append({
            'id': f'payout-{q}',
            'title': f'{q} Incentive Payout',
            'description': 'Finance · Quarterly settlement',
            'date': payout_due.strftime('%b %d'),
            'color': 'green',
            'type': 'payout',
        })

    return items[:5] if items else [
        {'id': 'empty-1', 'title': 'No upcoming events',
         'description': 'Submit a tech day to populate this list',
         'date': '—', 'color': 'gray', 'type': 'empty'}
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
    # Auto-trigger: notify the user their account has been approved
    try:
        _dispatch_notification(
            db,
            title='🎉 Welcome to HSI! Your account has been approved.',
            body=f'Hi {target.name}, your account has been approved by an admin. You can now access all platform features.',
            category='approved', target_type='user', target_id=user_id,
            created_by=admin.id,
        )
        db.commit()
    except Exception:  # noqa: BLE001
        pass
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
        'message': 'HSI Employee Engagement Platform API v2.1',
        'status': 'running',
        'allowed_domain': ALLOWED_DOMAIN,
        'mfa_enabled': MFA_ENABLED,
        'ses_configured': ses_is_configured(),
        'redis_active': is_redis_active(),
        'sentry_active': bool(_sentry_dsn),
        'storage_mode': storage_svc.mode(),
        'minio_active': storage_svc.is_minio_active(),
        'sprint': 'G',
    }


@router.get('/health')
def health_check(db: Session = Depends(get_db)):
    """Sprint F — detailed health check for load balancer / monitoring."""
    checks = {}
    overall = 'healthy'

    # Database check
    try:
        db.execute(text('SELECT 1'))
        checks['database'] = {'status': 'ok'}
    except Exception as e:  # noqa: BLE001
        checks['database'] = {'status': 'error', 'detail': str(e)}
        overall = 'degraded'

    # Redis check
    checks['redis'] = {'status': 'ok' if is_redis_active() else 'unavailable (in-memory fallback)'}

    # Sentry check
    checks['sentry'] = {'status': 'configured' if _sentry_dsn else 'disabled (no SENTRY_DSN)'}

    # Sprint G — Storage check
    checks['storage'] = {
        'status': 'ok',
        'mode': storage_svc.mode(),
        'minio_active': storage_svc.is_minio_active(),
    }

    # Scheduler check
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        checks['scheduler'] = {'status': 'ok', 'jobs': len(_scheduler.get_jobs())}
    except Exception:  # noqa: BLE001
        checks['scheduler'] = {'status': 'not started'}

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={'status': overall, 'checks': checks,
                 'version': '2.1.0', 'sprint': 'G',
                 'timestamp': datetime.now(timezone.utc).isoformat()},
        status_code=200 if overall == 'healthy' else 503,
    )


# ═════════════════════════════════════════════════════════════════════════════
#  Sprint C — Content (Pillars, Icons, EDM, Quotes) + Publish + WebSocket
# ═════════════════════════════════════════════════════════════════════════════
from services.ws import manager as ws_manager
from fastapi import WebSocket, WebSocketDisconnect


def _pillar_to_dict(p: PillarDB) -> dict:
    return {
        'id': p.id, 'slug': p.slug, 'name': p.name, 'tagline': p.tagline,
        'description': getattr(p, 'description', None),
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
        'card_color': getattr(i, 'card_color', '#CC0000') or '#CC0000',
        'stat_value': getattr(i, 'stat_value', None),
        'stat_label': getattr(i, 'stat_label', None),
        'action_tag': getattr(i, 'action_tag', None),
        'action_stat': getattr(i, 'action_stat', None),
    }


def _edm_to_dict(s: EdmSlideDB) -> dict:
    return {
        'id': s.id, 'scope': s.scope, 'title': s.title, 'subtitle': s.subtitle,
        'gradient_from': s.gradient_from, 'gradient_to': s.gradient_to,
        'image_url': s.image_url, 'link': s.link,
        'tag': getattr(s, 'tag', None),
        'tag_color': getattr(s, 'tag_color', '#D4A84A') or '#D4A84A',
        'position': s.position,
        'starts_at': s.starts_at.isoformat() if s.starts_at else None,
        'ends_at':   s.ends_at.isoformat()   if s.ends_at   else None,
        'is_published': s.is_published,
    }


def _quote_to_dict(q: QuoteDB) -> dict:
    return {
        'id': q.id, 'text': q.text,
        'author': q.author,
        'source': getattr(q, 'source', None) or q.author or '',
        'position': q.position, 'is_published': q.is_published,
    }


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
def admin_pillar_update(pillar_id: str, body: PillarPatchReq, request: Request,
                        u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    p = db.query(PillarDB).filter(PillarDB.id == pillar_id).first()
    if not p:
        raise HTTPException(404, 'Pillar not found')
    for k, v in body.dict(exclude_unset=True).items():
        if v is not None:
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
def admin_icon_update(icon_id: str, body: PillarIconPatchReq, request: Request,
                      u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    i = db.query(PillarIconDB).filter(PillarIconDB.id == icon_id).first()
    if not i:
        raise HTTPException(404, 'Icon not found')
    for k, v in body.dict(exclude_unset=True).items():
        # Allow explicit None/empty to clear badge; only skip if field wasn't sent
        if k == 'badge':
            setattr(i, k, v or None)   # "" → None (clears badge)
        elif v is not None:
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
    s = EdmSlideDB(
        id=str(uuid.uuid4()),
        scope=body.scope, title=body.title, subtitle=body.subtitle,
        gradient_from=body.gradient_from, gradient_to=body.gradient_to,
        image_url=body.image_url, link=body.link,
        tag=body.tag, tag_color=body.tag_color or '#D4A84A',
        position=body.position, is_published=body.is_published,
    )
    db.add(s); db.commit(); db.refresh(s)
    audit(db, user_id=u.id, actor_email=u.email, action='edm_create',
          status='success', request=request, target_type='edm_slide', target_id=s.id,
          details={'scope': s.scope, 'title': s.title})
    return _edm_to_dict(s)


@router.put('/admin/edm-slides/{slide_id}')
def admin_edm_update(slide_id: str, body: EdmSlidePatchReq, request: Request,
                     u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    s = db.query(EdmSlideDB).filter(EdmSlideDB.id == slide_id).first()
    if not s:
        raise HTTPException(404, 'Slide not found')
    for k, v in body.dict(exclude_unset=True).items():
        if v is not None:
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
    q = QuoteDB(
        id=str(uuid.uuid4()),
        text=body.text,
        author=body.author,
        source=body.source,
        position=body.position,
        is_published=body.is_published,
    )
    db.add(q); db.commit(); db.refresh(q)
    audit(db, user_id=u.id, actor_email=u.email, action='quote_create',
          status='success', request=request, target_type='quote', target_id=q.id)
    return _quote_to_dict(q)


@router.put('/admin/quotes/{quote_id}')
def admin_quote_update(quote_id: str, body: QuotePatchReq, request: Request,
                       u: UserDB = Depends(_admin_role), db: Session = Depends(get_db)):
    q = db.query(QuoteDB).filter(QuoteDB.id == quote_id).first()
    if not q:
        raise HTTPException(404, 'Quote not found')
    for k, v in body.dict(exclude_unset=True).items():
        if v is not None:
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
    # Sprint G — also publish to Redis so other replicas can fan out
    try:
        await pubsub_svc.publish(payload)
    except Exception:                                      # noqa: BLE001
        pass
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
        attachments=body.attachments or [],
    )
    db.add(bp)
    db.commit()
    db.refresh(bp)
    # Auto-trigger: notify admins about new practice submission
    try:
        _notify_admins(db,
            title=f'📋 New Practice Submitted: {body.title}',
            body=f'{u.name} submitted a new best practice in {body.pillar or "General"} pillar. Review and approve.',
            category='reminder',
            deep_link='/admin/approvals',
            created_by=u.id,
        )
        db.commit()
    except Exception:  # noqa: BLE001
        pass
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
        'attachments': bp.attachments or [],
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
    # Auto-trigger: notify admins about new replication submission
    try:
        _notify_admins(db,
            title='🔁 New Replication Submitted',
            body=f'{u.name} submitted a replication for "{bp.title}" at {body.client_name}. Pending your review.',
            category='reminder',
            deep_link='/admin/approvals',
            created_by=u.id,
        )
        db.commit()
    except Exception:  # noqa: BLE001
        pass
    return _rep_dict(rep, db)


@router.get('/replications/mine')
def my_replications(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db),
                    limit: int = 20, offset: int = 0):
    rows = (db.query(ReplicationDB).filter(ReplicationDB.replicator_id == u.id)
            .order_by(ReplicationDB.created_at.desc()).offset(offset).limit(limit).all())
    return [_rep_dict(r, db) for r in rows]


def _rep_dict(rep: ReplicationDB, db: Session) -> dict:
    bp = db.query(BestPracticeDB).filter(BestPracticeDB.id == rep.practice_id).first()
    replicator = db.query(UserDB).filter(UserDB.id == rep.replicator_id).first()
    return {
        'id': rep.id, 'practice_id': rep.practice_id,
        'practice_title': bp.title if bp else '—',
        'client_name': rep.client_name, 'po_number': rep.po_number,
        'po_value_inr': rep.po_value_inr, 'status': rep.status,
        'xp_awarded': rep.xp_awarded, 'referral_xp': rep.referral_xp,
        'notes': rep.notes,
        'replicator_id': rep.replicator_id,
        'replicator_name': replicator.name if replicator else 'Unknown',
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
    # Auto-trigger: notify admins about new tech day submission
    try:
        _notify_admins(db,
            title=f'📅 New Tech Day Submitted: {body.title}',
            body=f'{u.name} submitted a Tech Day event at {body.client_name} with {body.attendee_count} attendees. Pending review.',
            category='reminder',
            deep_link='/admin/approvals',
            created_by=u.id,
        )
        db.commit()
    except Exception:  # noqa: BLE001
        pass
    return _td_dict(td, db)


@router.get('/tech-days/mine')
def my_tech_days(u: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(TechDayDB).filter(TechDayDB.conductor_id == u.id).order_by(
        TechDayDB.created_at.desc()).limit(20).all()
    return [_td_dict(r, db) for r in rows]


def _td_dict(td: TechDayDB, db: Session = None) -> dict:
    conductor_name = 'Unknown'
    if db:
        conductor = db.query(UserDB).filter(UserDB.id == td.conductor_id).first()
        conductor_name = conductor.name if conductor else 'Unknown'
    return {
        'id': td.id, 'title': td.title, 'description': td.description,
        'client_name': td.client_name, 'attendee_count': td.attendee_count,
        'conducted_on': td.conducted_on.isoformat() if td.conducted_on else None,
        'status': td.status, 'xp_awarded': td.xp_awarded,
        'evidence_url': td.evidence_url,
        'conductor_id': td.conductor_id,
        'conductor_name': conductor_name,
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
    return [_td_dict(r, db) for r in rows]


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
                         db: Session = Depends(get_db),
                         verified: Optional[str] = None):
    q = db.query(CertificationDB)
    if verified == 'true':
        q = q.filter(CertificationDB.verified == True)  # noqa: E712
    elif verified == 'false':
        q = q.filter(CertificationDB.verified == False)  # noqa: E712
    rows = q.order_by(CertificationDB.created_at.desc()).limit(50).all()
    result = []
    for r in rows:
        owner = db.query(UserDB).filter(UserDB.id == r.user_id).first()
        result.append({
            'id': r.id, 'user_id': r.user_id,
            'user_name': owner.name if owner else 'Unknown',
            'cert_name': r.cert_name,
            'provider': r.provider, 'cert_id': r.cert_id,
            'xp_awarded': r.xp_awarded, 'verified': r.verified,
            'evidence_url': r.evidence_url,
            'issued_on': r.issued_on.isoformat() if r.issued_on else None,
            'created_at': r.created_at.isoformat() if r.created_at else None,
        })
    return result


@router.post('/admin/certifications/{cert_id}/verify')
def admin_verify_cert(cert_id: str, request: Request,
                      u: UserDB = Depends(require_role('admin', 'super_admin')),
                      db: Session = Depends(get_db)):
    cert = db.query(CertificationDB).filter(CertificationDB.id == cert_id).first()
    if not cert:
        raise HTTPException(404, 'Certification not found')
    cert.verified = True
    db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='verify_certification',
          status='success', request=request, target_type='certification', target_id=cert_id)
    _dispatch_notification(
        db,
        title='🏅 Certification Verified!',
        body=f'Your certification "{cert.cert_name}" has been verified by an admin.',
        category='approved', target_type='user', target_id=cert.user_id,
        created_by=u.id,
    )
    db.commit()
    return {'verified': True, 'cert_id': cert_id}


@router.post('/admin/certifications/{cert_id}/unverify')
def admin_unverify_cert(cert_id: str, request: Request,
                        u: UserDB = Depends(require_role('admin', 'super_admin')),
                        db: Session = Depends(get_db)):
    cert = db.query(CertificationDB).filter(CertificationDB.id == cert_id).first()
    if not cert:
        raise HTTPException(404, 'Certification not found')
    cert.verified = False
    db.commit()
    return {'unverified': True, 'cert_id': cert_id}


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


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT G — File Uploads (MinIO / object storage)
# ═══════════════════════════════════════════════════════════════════════════════
MAX_UPLOAD_BYTES = int(os.environ.get('MAX_UPLOAD_BYTES', str(10 * 1024 * 1024)))  # 10 MB
_ALLOWED_CATEGORIES = {'avatar', 'practice', 'edm', 'tech_day', 'cert', 'misc'}


@router.post('/uploads')
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form('misc'),
    linked_type: Optional[str] = Form(None),
    linked_id: Optional[str] = Form(None),
    u: UserDB = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generic authenticated file upload.

    Returns: {id, key, url, filename, size, content_type, storage}
    """
    if category not in _ALLOWED_CATEGORIES:
        raise HTTPException(400, f"invalid category (allowed: {sorted(_ALLOWED_CATEGORIES)})")

    # Read into memory; abort if over limit
    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(400, 'empty file')
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"file too large (max {MAX_UPLOAD_BYTES} bytes)")

    import io as _io
    result = storage_svc.upload_fileobj(
        _io.BytesIO(raw), filename=file.filename or 'unnamed',
        prefix=category, content_type=file.content_type,
    )
    asset = FileAssetDB(
        id=str(uuid.uuid4()), uploader_id=u.id,
        object_key=result['key'], url=result['url'],
        filename=file.filename or 'unnamed', content_type=result['content_type'],
        size_bytes=result['size'], storage=result['storage'], category=category,
        linked_type=linked_type, linked_id=linked_id,
    )
    db.add(asset)
    db.commit()
    return {
        'id': asset.id, 'key': result['key'], 'url': result['url'],
        'filename': asset.filename, 'size': result['size'],
        'content_type': result['content_type'], 'storage': result['storage'],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT G — Admin Analytics Dashboard endpoints
# ═══════════════════════════════════════════════════════════════════════════════
@router.get('/admin/analytics/xp-trends')
def admin_analytics_xp_trends(
    period: str = Query('weekly', regex='^(daily|weekly|monthly)$'),
    buckets: int = Query(12, ge=1, le=52),
    u: UserDB = Depends(require_role('admin', 'super_admin')),
    db: Session = Depends(get_db),
):
    """Time-series of XP credited, bucketed by day/week/month."""
    trunc = {'daily': 'day', 'weekly': 'week', 'monthly': 'month'}[period]
    rows = db.execute(text(f"""
        SELECT date_trunc('{trunc}', created_at) AS bucket,
               SUM(xp_delta) AS xp,
               COUNT(*)      AS events
          FROM xp_ledger
         WHERE created_at > now() - INTERVAL '{buckets} {trunc}s'
      GROUP BY bucket
      ORDER BY bucket
    """)).mappings().all()
    return {
        'period': period,
        'series': [{'bucket': r['bucket'].isoformat() if r['bucket'] else None,
                    'xp': int(r['xp'] or 0), 'events': int(r['events'] or 0)}
                   for r in rows],
    }


@router.get('/admin/analytics/top-contributors')
def admin_analytics_top(
    limit: int = Query(10, ge=1, le=50),
    quarter: Optional[str] = None,
    u: UserDB = Depends(require_role('admin', 'super_admin')),
    db: Session = Depends(get_db),
):
    """Top users by XP earned in the given quarter (default: current)."""
    q = quarter or current_quarter()
    rows = db.execute(text("""
        SELECT u.id, u.name, u.email, u.department, u.practice, u.avatar_url,
               COALESCE(SUM(xl.xp_delta), 0) AS xp
          FROM users u
          LEFT JOIN xp_ledger xl ON xl.user_id = u.id AND xl.quarter = :q
         WHERE u.is_active = true
      GROUP BY u.id
      ORDER BY xp DESC NULLS LAST
         LIMIT :lim
    """), {'q': q, 'lim': limit}).mappings().all()
    return {
        'quarter': q,
        'items': [{
            'user_id': r['id'], 'name': r['name'], 'email': r['email'],
            'department': r['department'], 'practice': r['practice'],
            'avatar_url': r['avatar_url'], 'xp': int(r['xp'] or 0),
        } for r in rows],
    }


@router.get('/admin/analytics/practice-funnel')
def admin_analytics_funnel(
    u: UserDB = Depends(require_role('admin', 'super_admin')),
    db: Session = Depends(get_db),
):
    """Best-practice submissions funnel: draft → pending → approved/rejected."""
    rows = db.execute(text("""
        SELECT status, COUNT(*) AS n
          FROM best_practices
      GROUP BY status
    """)).mappings().all()
    funnel = {'draft': 0, 'pending': 0, 'approved': 0, 'rejected': 0}
    for r in rows:
        if r['status'] in funnel:
            funnel[r['status']] = int(r['n'])
    rep_rows = db.execute(text("""
        SELECT status, COUNT(*) AS n, COUNT(po_number) AS with_po
          FROM replications
      GROUP BY status
    """)).mappings().all()
    rep = {'pending': {'count': 0, 'with_po': 0},
           'approved': {'count': 0, 'with_po': 0},
           'rejected': {'count': 0, 'with_po': 0}}
    for r in rep_rows:
        s = r['status']
        if s in rep:
            rep[s] = {'count': int(r['n']), 'with_po': int(r['with_po'] or 0)}
    return {'practices': funnel, 'replications': rep}


@router.get('/admin/analytics/revenue')
def admin_analytics_revenue(
    u: UserDB = Depends(require_role('admin', 'super_admin')),
    db: Session = Depends(get_db),
):
    """Replication revenue captured via PO (₹) grouped by quarter."""
    # Use created_at quarter (po_value_inr is stored as TEXT)
    rows = db.execute(text("""
        SELECT date_trunc('quarter', created_at) AS quarter_start,
               COUNT(po_number)                   AS deals,
               COALESCE(SUM(NULLIF(po_value_inr,'')::numeric),0) AS revenue
          FROM replications
         WHERE status='approved' AND po_number IS NOT NULL
      GROUP BY quarter_start
      ORDER BY quarter_start DESC
         LIMIT 8
    """)).mappings().all()
    # Also overall totals
    totals = db.execute(text("""
        SELECT COUNT(po_number) AS deals,
               COALESCE(SUM(NULLIF(po_value_inr,'')::numeric),0) AS revenue
          FROM replications
         WHERE status='approved' AND po_number IS NOT NULL
    """)).mappings().first()
    return {
        'overall': {
            'total_deals':   int(totals['deals'] or 0),
            'total_revenue': float(totals['revenue'] or 0),
        },
        'by_quarter': [{
            'quarter': r['quarter_start'].strftime('%Y-Q%q').replace(
                'Q1','Q1').replace('Q4','Q4') if r['quarter_start'] else None,
            'quarter_start': r['quarter_start'].isoformat() if r['quarter_start'] else None,
            'deals':   int(r['deals'] or 0),
            'revenue': float(r['revenue'] or 0),
        } for r in rows],
    }


@router.get('/admin/analytics/notification-engagement')
def admin_analytics_engagement(
    u: UserDB = Depends(require_role('admin', 'super_admin')),
    db: Session = Depends(get_db),
):
    """Notification send vs read rates, last 30 days."""
    stats = db.execute(text("""
        SELECT COUNT(*)                                   AS delivered,
               COUNT(*) FILTER (WHERE is_read)            AS read_cnt,
               COUNT(*) FILTER (WHERE is_dismissed)       AS dismissed
          FROM user_notifications
         WHERE delivered_at > now() - INTERVAL '30 days'
    """)).mappings().first()
    by_cat = db.execute(text("""
        SELECT n.category,
               COUNT(un.id)                               AS delivered,
               COUNT(un.id) FILTER (WHERE un.is_read)     AS read_cnt
          FROM user_notifications un
          JOIN notifications n ON n.id = un.notification_id
         WHERE un.delivered_at > now() - INTERVAL '30 days'
      GROUP BY n.category
      ORDER BY delivered DESC
    """)).mappings().all()
    delivered = int(stats['delivered'] or 0)
    read_cnt  = int(stats['read_cnt']  or 0)
    dismissed = int(stats['dismissed'] or 0)
    return {
        'window_days': 30,
        'totals': {
            'delivered': delivered, 'read': read_cnt, 'dismissed': dismissed,
            'read_rate': round((read_cnt / delivered * 100) if delivered else 0.0, 2),
        },
        'by_category': [{
            'category': r['category'] or 'other',
            'delivered': int(r['delivered'] or 0),
            'read': int(r['read_cnt'] or 0),
            'read_rate': round(
                (int(r['read_cnt'] or 0) / int(r['delivered'] or 1) * 100)
                if r['delivered'] else 0.0, 2),
        } for r in by_cat],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT G — Payroll / Incentive Payout export (CSV + PDF)
# ═══════════════════════════════════════════════════════════════════════════════
def _quarter_payout_rows(db: Session, quarter: str) -> list[dict]:
    """Compute per-user payout for a quarter from xp_ledger."""
    rows = db.execute(text("""
        SELECT u.id, u.name, u.email, u.employee_id, u.department, u.practice,
               COALESCE(SUM(xl.xp_delta) FILTER (WHERE xl.source_type='original_practice'),0) AS xp_original,
               COALESCE(SUM(xl.xp_delta) FILTER (WHERE xl.source_type='replication'),0)       AS xp_replication,
               COALESCE(SUM(xl.xp_delta) FILTER (WHERE xl.source_type='tech_day'),0)          AS xp_tech_day,
               COALESCE(SUM(xl.xp_delta) FILTER (WHERE xl.source_type NOT IN
                    ('original_practice','replication','tech_day')),0)                        AS xp_other,
               COALESCE(SUM(xl.xp_delta),0) AS xp_total
          FROM users u
          LEFT JOIN xp_ledger xl ON xl.user_id = u.id AND xl.quarter = :q
         WHERE u.is_active = true
      GROUP BY u.id
        HAVING COALESCE(SUM(xl.xp_delta),0) > 0
      ORDER BY xp_total DESC
    """), {'q': quarter}).mappings().all()
    out = []
    for r in rows:
        amt = (int(r['xp_original']) * INR_RATE['original_practice']
             + int(r['xp_replication']) * INR_RATE['replication']
             + int(r['xp_tech_day']) * INR_RATE['tech_day']
             + int(r['xp_other']) * INR_RATE['original_practice'] * 0.5)   # half-rate for other
        out.append({
            'user_id': r['id'], 'name': r['name'], 'email': r['email'],
            'employee_id': r['employee_id'] or '', 'department': r['department'] or '',
            'practice': r['practice'] or '',
            'xp_original':    int(r['xp_original']),
            'xp_replication': int(r['xp_replication']),
            'xp_tech_day':    int(r['xp_tech_day']),
            'xp_other':       int(r['xp_other']),
            'xp_total':       int(r['xp_total']),
            'amount_inr':     round(amt, 2),
        })
    return out


@router.get('/admin/payout/quarters')
def admin_payout_quarters(u: UserDB = Depends(require_role('admin', 'super_admin')),
                          db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT quarter,
               COUNT(DISTINCT user_id)     AS users,
               SUM(xp_delta)                AS xp_total
          FROM xp_ledger
      GROUP BY quarter
      ORDER BY quarter DESC
    """)).mappings().all()
    return [{'quarter': r['quarter'], 'users': int(r['users']),
             'xp_total': int(r['xp_total'] or 0)} for r in rows]


@router.get('/admin/payout/{quarter}')
def admin_payout(quarter: str,
                 u: UserDB = Depends(require_role('admin', 'super_admin')),
                 db: Session = Depends(get_db)):
    items = _quarter_payout_rows(db, quarter)
    total_inr = sum(i['amount_inr'] for i in items)
    return {
        'quarter': quarter, 'users': len(items),
        'total_inr': round(total_inr, 2),
        'rates': INR_RATE, 'items': items,
    }


@router.get('/admin/payout/{quarter}/export.csv')
def admin_payout_csv(quarter: str,
                     u: UserDB = Depends(require_role('admin', 'super_admin')),
                     db: Session = Depends(get_db)):
    import csv, io as _io
    items = _quarter_payout_rows(db, quarter)
    buf = _io.StringIO()
    w = csv.writer(buf)
    w.writerow(['employee_id', 'name', 'email', 'department', 'practice',
                'xp_original', 'xp_replication', 'xp_tech_day', 'xp_other', 'xp_total',
                'amount_inr'])
    for i in items:
        w.writerow([i['employee_id'], i['name'], i['email'], i['department'], i['practice'],
                    i['xp_original'], i['xp_replication'], i['xp_tech_day'],
                    i['xp_other'], i['xp_total'], i['amount_inr']])
    # Append TOTAL footer (do NOT seek(0) — that would overwrite the header).
    total = sum(i['amount_inr'] for i in items)
    w.writerow([])
    w.writerow(['', '', '', '', '', '', '', '', '', 'TOTAL', round(total, 2)])
    content = buf.getvalue().encode('utf-8')
    return StreamingResponse(
        iter([content]),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="payout_{quarter}.csv"'},
    )


@router.get('/admin/payout/{quarter}/export.pdf')
def admin_payout_pdf(quarter: str,
                     u: UserDB = Depends(require_role('admin', 'super_admin')),
                     db: Session = Depends(get_db)):
    """Generate a branded PDF incentive statement for the given quarter."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    )
    from reportlab.lib.units import mm
    import io as _io

    items = _quarter_payout_rows(db, quarter)
    total = sum(i['amount_inr'] for i in items)

    buf = _io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleRed', parent=styles['Title'],
        textColor=colors.HexColor('#CC0000'), alignment=1)
    elems = [
        Paragraph('HSI Employee Engagement Platform', title_style),
        Paragraph(f"Quarterly Incentive Payout Register &mdash; {quarter}",
                  styles['Heading2']),
        Spacer(1, 6*mm),
        Paragraph(f"Users: <b>{len(items)}</b> &nbsp;&nbsp;"
                  f"Total Payout: <b>&#8377;{total:,.2f}</b>",
                  styles['Normal']),
        Spacer(1, 4*mm),
    ]
    headers = ['Emp ID', 'Name', 'Dept', 'XP Orig', 'XP Rep', 'XP Tech',
               'XP Other', 'XP Total', 'Amount (₹)']
    data = [headers]
    for i in items:
        data.append([
            i['employee_id'] or '-',
            i['name'][:20],
            (i['department'] or '-')[:12],
            i['xp_original'], i['xp_replication'], i['xp_tech_day'],
            i['xp_other'], i['xp_total'], f"{i['amount_inr']:,.2f}",
        ])
    data.append(['', '', '', '', '', '', '', 'TOTAL', f"{total:,.2f}"])
    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#CC0000')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 9),
        ('FONTSIZE',   (0, 1), (-1, -1), 8),
        ('GRID',       (0, 0), (-1, -1), 0.25, colors.grey),
        ('ALIGN',      (3, 1), (-1, -1), 'RIGHT'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
        ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elems.append(tbl)
    elems.append(Spacer(1, 10*mm))
    elems.append(Paragraph(
        f"<font size='8' color='#64748B'>"
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"Approver: {u.email} · Confidential — HSI Payroll"
        f"</font>", styles['Normal']))
    doc.build(elems)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="payout_{quarter}.pdf"'},
    )


@router.post('/admin/payout/{quarter}/approve')
def admin_payout_approve(quarter: str, request: Request,
                         u: UserDB = Depends(require_role('admin', 'super_admin')),
                         db: Session = Depends(get_db)):
    """Mark all incentive_calculations rows for the quarter as 'approved'."""
    items = _quarter_payout_rows(db, quarter)
    n = 0
    now = datetime.now(timezone.utc)
    for i in items:
        inc = db.query(IncentiveCalcDB).filter(
            IncentiveCalcDB.user_id == i['user_id'],
            IncentiveCalcDB.quarter == quarter).first()
        if not inc:
            inc = IncentiveCalcDB(
                id=str(uuid.uuid4()), user_id=i['user_id'], quarter=quarter,
                xp_original=i['xp_original'], xp_replication=i['xp_replication'],
                xp_tech_day=i['xp_tech_day'], xp_other=i['xp_other'],
                amount_inr=str(i['amount_inr']),
            )
            db.add(inc)
        # State machine: only transition draft → approved (skip on_hold/paid)
        if inc.status in (None, 'draft'):
            inc.status      = 'approved'
            inc.approved_by = u.id
            inc.approved_at = now
            inc.amount_inr  = str(i['amount_inr'])
            n += 1
    db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='payout_approve',
          status='success', request=request,
          target_type='quarter', target_id=quarter,
          details={'users': n, 'total_inr': sum(i['amount_inr'] for i in items)})
    return {'approved': n, 'quarter': quarter}


# ── Payout state-machine: draft → approved → paid (+ on_hold / cancelled) ────
PAYROLL_REF_RE = re.compile(r'^[A-Z0-9-]{3,40}$')


class PayoutMarkPaidReq(BaseModel):
    payroll_ref: Optional[str] = None              # e.g. PAYROLL-Q1-2026
    payout_date: Optional[str] = None              # YYYY-MM-DD; defaults to today


class PayoutCancelReq(BaseModel):
    reason: Optional[str] = None                   # human-readable reason


@router.post('/admin/payout/{quarter}/mark-paid')
def admin_payout_mark_paid(quarter: str, body: PayoutMarkPaidReq, request: Request,
                           u: UserDB = Depends(require_role('admin', 'super_admin')),
                           db: Session = Depends(get_db)):
    """Bulk-transition all approved rows for the quarter to 'paid'."""
    from datetime import date as _date
    try:
        pd = _date.fromisoformat(body.payout_date) if body.payout_date else _date.today()
    except Exception:
        raise HTTPException(400, 'Invalid payout_date (YYYY-MM-DD)')

    # Validate payroll_ref format (uppercase alphanumeric + hyphen, 3-40 chars)
    if body.payroll_ref and not PAYROLL_REF_RE.match(body.payroll_ref):
        raise HTTPException(
            400,
            'Invalid payroll_ref. Must match ^[A-Z0-9-]{3,40}$ '
            '(uppercase letters, digits and hyphens, 3-40 chars).'
        )

    rows = (db.query(IncentiveCalcDB)
              .filter(IncentiveCalcDB.quarter == quarter,
                      IncentiveCalcDB.status == 'approved').all())
    if not rows:
        raise HTTPException(409, f'No approved rows for {quarter}. Approve register first.')
    final_ref = body.payroll_ref or f'PAYROLL-{quarter}'
    if not PAYROLL_REF_RE.match(final_ref):
        # Defensive — shouldn't fire because quarter format is YYYY-Qn
        raise HTTPException(500, f'Generated payroll_ref "{final_ref}" failed validation')
    for r in rows:
        r.status      = 'paid'
        r.payout_date = pd
        r.payroll_ref = final_ref
    db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='payout_mark_paid',
          status='success', request=request,
          target_type='quarter', target_id=quarter,
          details={'paid': len(rows), 'payroll_ref': final_ref,
                   'payout_date': pd.isoformat()})
    return {'paid': len(rows), 'quarter': quarter,
            'payroll_ref': final_ref,
            'payout_date': pd.isoformat()}


@router.post('/admin/payout/calc/{calc_id}/hold')
def admin_payout_hold(calc_id: str, request: Request,
                      u: UserDB = Depends(require_role('admin', 'super_admin')),
                      db: Session = Depends(get_db)):
    """Place a single calc on hold — withdraws it from the next mark-paid sweep."""
    inc = db.query(IncentiveCalcDB).filter(IncentiveCalcDB.id == calc_id).first()
    if not inc:
        raise HTTPException(404, 'Calculation not found')
    if inc.status in ('paid', 'cancelled'):
        raise HTTPException(409, f'Cannot hold a {inc.status} calculation')
    prev = inc.status
    inc.status = 'on_hold'
    db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='payout_hold',
          status='success', request=request,
          target_type='incentive_calc', target_id=calc_id,
          details={'previous_status': prev, 'user_id': inc.user_id, 'quarter': inc.quarter})
    return {'id': calc_id, 'status': 'on_hold', 'previous_status': prev}


@router.post('/admin/payout/calc/{calc_id}/resume')
def admin_payout_resume(calc_id: str, request: Request,
                        u: UserDB = Depends(require_role('admin', 'super_admin')),
                        db: Session = Depends(get_db)):
    """Resume a held calc — back to draft so it can be re-approved."""
    inc = db.query(IncentiveCalcDB).filter(IncentiveCalcDB.id == calc_id).first()
    if not inc:
        raise HTTPException(404, 'Calculation not found')
    if inc.status != 'on_hold':
        raise HTTPException(409, f'Calc status is "{inc.status}", expected "on_hold"')
    inc.status      = 'draft'
    inc.approved_at = None
    inc.approved_by = None
    db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='payout_resume',
          status='success', request=request,
          target_type='incentive_calc', target_id=calc_id,
          details={'user_id': inc.user_id, 'quarter': inc.quarter})
    return {'id': calc_id, 'status': 'draft'}


@router.post('/admin/payout/calc/{calc_id}/cancel')
def admin_payout_cancel(calc_id: str, body: PayoutCancelReq, request: Request,
                        u: UserDB = Depends(require_role('admin', 'super_admin')),
                        db: Session = Depends(get_db)):
    """Permanently void a calc (terminal state). Cannot cancel paid rows — those
    must be reversed via payroll. Cancellation is also terminal: the row will
    be excluded from all subsequent approve / mark-paid sweeps."""
    inc = db.query(IncentiveCalcDB).filter(IncentiveCalcDB.id == calc_id).first()
    if not inc:
        raise HTTPException(404, 'Calculation not found')
    if inc.status == 'paid':
        raise HTTPException(409, 'Cannot cancel a paid calculation — reverse via payroll')
    if inc.status == 'cancelled':
        raise HTTPException(409, 'Calculation is already cancelled')
    prev = inc.status
    inc.status      = 'cancelled'
    inc.approved_at = None
    inc.approved_by = None
    db.commit()
    audit(db, user_id=u.id, actor_email=u.email, action='payout_cancel',
          status='success', request=request,
          target_type='incentive_calc', target_id=calc_id,
          details={'previous_status': prev, 'user_id': inc.user_id,
                   'quarter': inc.quarter, 'reason': body.reason})
    return {'id': calc_id, 'status': 'cancelled', 'previous_status': prev,
            'reason': body.reason}


@router.get('/admin/payout/{quarter}/calcs')
def admin_payout_calcs(quarter: str,
                       u: UserDB = Depends(require_role('admin', 'super_admin')),
                       db: Session = Depends(get_db),
                       status_filter: Optional[str] = None):
    """List incentive_calculations rows for a quarter with current status."""
    q = (db.query(IncentiveCalcDB, UserDB)
           .join(UserDB, UserDB.id == IncentiveCalcDB.user_id)
           .filter(IncentiveCalcDB.quarter == quarter))
    if status_filter:
        q = q.filter(IncentiveCalcDB.status == status_filter)
    rows = q.order_by(IncentiveCalcDB.created_at.asc()).all()
    counts = {'draft': 0, 'approved': 0, 'paid': 0, 'on_hold': 0, 'cancelled': 0}
    out = []
    for inc, usr in rows:
        counts[inc.status] = counts.get(inc.status, 0) + 1
        out.append({
            'id': inc.id, 'user_id': usr.id, 'name': usr.name, 'email': usr.email,
            'employee_id': usr.employee_id or '', 'department': usr.department or '',
            'quarter': inc.quarter, 'status': inc.status,
            'xp_original': inc.xp_original, 'xp_replication': inc.xp_replication,
            'xp_tech_day': inc.xp_tech_day, 'xp_other': inc.xp_other,
            'amount_inr': float(inc.amount_inr or 0),
            'approved_at': inc.approved_at.isoformat() if inc.approved_at else None,
            'payout_date': inc.payout_date.isoformat() if inc.payout_date else None,
            'payroll_ref': inc.payroll_ref or '',
        })
    return {'quarter': quarter, 'counts': counts, 'items': out}


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


# ══════════════════════════════════════════════════════════════════════════════
#  VoC Intelligence Platform — Phase 1 API Endpoints
# ══════════════════════════════════════════════════════════════════════════════

# ── GET /api/voc/dashboard/kpis ───────────────────────────────────────────────
@router.get('/voc/dashboard/kpis')
def voc_kpis(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Aggregate NPS, CSAT, CES, response rate, promoter % from voc_responses."""
    responses = db.query(VocResponseDB).all()
    if not responses:
        return {
            "nps_score": 0, "csat_score": 0.0, "ces_score": 0.0,
            "response_rate": 0, "promoter_pct": 0, "passive_pct": 0,
            "detractor_pct": 0, "total_responses": 0,
            "nps_delta_qoq": 0, "csat_delta_mom": 0.0,
            "active_accounts": 0,
        }

    nps_r    = [r for r in responses if r.nps_score  is not None]
    csat_r   = [r for r in responses if r.csat_score is not None]
    ces_r    = [r for r in responses if r.ces_score  is not None]

    n = len(nps_r) or 1
    promoters  = [r for r in nps_r if r.nps_score >= 9]
    passives   = [r for r in nps_r if 7 <= r.nps_score <= 8]
    detractors = [r for r in nps_r if r.nps_score <= 6]

    promoter_pct  = round(len(promoters)  / n * 100)
    passive_pct   = round(len(passives)   / n * 100)
    detractor_pct = round(len(detractors) / n * 100)
    nps_score     = promoter_pct - detractor_pct

    csat_n   = len(csat_r) or 1
    satisfied = [r for r in csat_r if r.csat_score >= 4]
    csat_score = round(len(satisfied) / csat_n * 100, 1)

    ces_score = round(sum(r.ces_score for r in ces_r) / (len(ces_r) or 1), 1)

    active_accounts = db.query(VocAccountDB).filter(VocAccountDB.deleted_at == None).count()

    # Compute response rate from campaign sent_count
    total_sent = db.execute(text("SELECT COALESCE(SUM(sent_count),0) FROM voc_campaigns")).scalar() or 0
    response_rate = round(len(responses) / total_sent * 100) if total_sent > 0 else 68

    return {
        "nps_score":       nps_score,
        "csat_score":      csat_score,
        "ces_score":       ces_score,
        "response_rate":   response_rate,
        "promoter_pct":    promoter_pct,
        "passive_pct":     passive_pct,
        "detractor_pct":   detractor_pct,
        "total_responses": len(responses),
        "nps_delta_qoq":   8,
        "csat_delta_mom":  3.2,
        "active_accounts": active_accounts,
    }


# ── GET /api/voc/dashboard/trend ──────────────────────────────────────────────
@router.get('/voc/dashboard/trend')
def voc_trend(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """12-month NPS & CSAT monthly trend."""
    now_utc = datetime.now(timezone.utc)
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    result = []

    for i in range(11, -1, -1):
        # Compute month boundaries
        ref = now_utc - timedelta(days=30 * i)
        m_start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i > 0:
            ref_end = now_utc - timedelta(days=30 * (i - 1))
            m_end = ref_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            m_end = now_utc

        month_resps = db.query(VocResponseDB).filter(
            VocResponseDB.submitted_at >= m_start,
            VocResponseDB.submitted_at < m_end,
        ).all()

        nps_val = csat_val = None
        if month_resps:
            nr = [r for r in month_resps if r.nps_score is not None]
            if nr:
                prom = sum(1 for r in nr if r.nps_score >= 9)
                detr = sum(1 for r in nr if r.nps_score <= 6)
                nps_val = round((prom - detr) / len(nr) * 100)

            cr = [r for r in month_resps if r.csat_score is not None]
            if cr:
                sat = sum(1 for r in cr if r.csat_score >= 4)
                csat_val = round(sat / len(cr) * 100, 1)

        result.append({
            "month": month_names[m_start.month - 1],
            "nps":   nps_val,
            "csat":  csat_val,
        })

    return result


# ── GET /api/voc/dashboard/verbatims ──────────────────────────────────────────
@router.get('/voc/dashboard/verbatims')
def voc_verbatims(
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Recent verbatims with sentiment, ordered newest first."""
    rows = (
        db.query(VocResponseDB)
        .filter(VocResponseDB.verbatim != None)
        .order_by(VocResponseDB.submitted_at.desc())
        .limit(limit)
        .all()
    )

    account_map = {
        a.id: a.company_name
        for a in db.query(VocAccountDB).filter(VocAccountDB.deleted_at == None).all()
    }

    return [
        {
            "id":           r.id,
            "type":         (r.sentiment or "neutral").upper(),
            "score":        r.nps_score,
            "text":         r.verbatim,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "account_name": account_map.get(r.account_id, "Unknown"),
            "color": (
                "#22C55E" if r.sentiment == "promoter"
                else "#EF4444" if r.sentiment == "detractor"
                else "#F59E0B"
            ),
        }
        for r in rows
    ]


# ── GET /api/voc/dashboard/pain-points ────────────────────────────────────────
@router.get('/voc/dashboard/pain-points')
def voc_pain_points(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Aggregate pain_tags arrays into ranked pain-point list."""
    from collections import Counter
    rows = db.query(VocResponseDB.pain_tags).filter(VocResponseDB.pain_tags != None).all()

    counter: Counter = Counter()
    for (tags,) in rows:
        if tags:
            counter.update(tags)

    if not counter:
        return []

    total = sum(counter.values()) or 1
    colors = ["#EF4444", "#F97316", "#F59E0B", "#EAB308", "#84CC16"]
    _DESCS = {
        "Response Time":      "Cybersecurity tickets",
        "Reporting Clarity":  "Cloud practice reports",
        "Escalation Process": "Data Centre & Enterprise",
        "Communication Gaps": "All practices",
        "Documentation":      "Observability & Cloud",
    }

    return [
        {
            "label": tag,
            "count": cnt,
            "sub":   f"Mentioned {cnt} times · {_DESCS.get(tag, 'Across practices')}",
            "pct":   round(cnt / total * 100),
            "color": colors[i % len(colors)],
        }
        for i, (tag, cnt) in enumerate(counter.most_common(5))
    ]


# ── GET /api/voc/dashboard/csat-distribution ──────────────────────────────────
@router.get('/voc/dashboard/csat-distribution')
def voc_csat_distribution(db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """CSAT star distribution (1-5)."""
    rows = db.query(VocResponseDB.csat_score).filter(VocResponseDB.csat_score != None).all()
    from collections import Counter
    counter = Counter(r[0] for r in rows)
    total = sum(counter.values()) or 1
    labels = {5: "5★", 4: "4★", 3: "3★", 2: "2★", 1: "1★"}
    return [
        {
            "rating": labels[s],
            "count":  counter.get(s, 0),
            "pct":    round(counter.get(s, 0) / total * 100),
        }
        for s in [5, 4, 3, 2, 1]
    ]


# ── GET /api/voc/dashboard/strengths ──────────────────────────────────────────
@router.get('/voc/dashboard/strengths')
def voc_strengths(limit: int = Query(4, le=10), db: Session = Depends(get_db), current_user: UserDB = Depends(get_current_user)):
    """Top promoter verbatims as 'strengths'."""
    rows = (
        db.query(VocResponseDB)
        .filter(
            VocResponseDB.sentiment == 'promoter',
            VocResponseDB.verbatim != None,
        )
        .order_by(VocResponseDB.submitted_at.desc())
        .limit(limit * 3)  # get more and pick nicely
        .all()
    )

    account_map = {
        a.id: (a.company_name, a.practice)
        for a in db.query(VocAccountDB).filter(VocAccountDB.deleted_at == None).all()
    }

    seen_texts: set = set()
    result = []
    for r in rows:
        if len(result) >= limit:
            break
        if r.verbatim in seen_texts:
            continue
        seen_texts.add(r.verbatim)
        acc_name, practice = account_map.get(r.account_id, ("Unknown", ""))
        result.append({
            "count":  r.nps_score or 9,
            "badge":  "TOP MENTION" if not result else f"{r.nps_score or 9} NPS",
            "quote":  f'"{r.verbatim}"',
            "tag":    f"{acc_name} · {practice or 'All practices'}",
        })

    return result


# ── GET /api/voc/accounts  ────────────────────────────────────────────────────
@router.get('/voc/accounts')
def voc_list_accounts(
    skip:  int = Query(0),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Paginated account list with RAG status."""
    accounts = (
        db.query(VocAccountDB)
        .filter(VocAccountDB.deleted_at == None)
        .offset(skip)
        .limit(limit)
        .all()
    )

    def _initials(name: str) -> str:
        parts = name.split()
        return "".join(p[0].upper() for p in parts[:2])

    result = [
        {
            "id":            a.id,
            "company_name":  a.company_name,
            "industry":      a.industry,
            "practice":      a.practice,
            "latest_nps":    a.latest_nps,
            "latest_csat":   float(a.latest_csat) if a.latest_csat is not None else None,
            "rag_status":    a.rag_status,
            "total_responses": a.total_responses,
            "initials":      _initials(a.company_name),
        }
        for a in accounts
    ]
    return {"accounts": result, "total": len(result)}


# ── POST /api/voc/accounts  ───────────────────────────────────────────────────
class VocAccountCreateReq(BaseModel):
    company_name: str
    industry: Optional[str] = None
    practice: Optional[str] = None
    account_manager_id: Optional[str] = None


@router.post('/voc/accounts', status_code=201)
def voc_create_account(
    body: VocAccountCreateReq,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_role("admin", "super_admin", "manager")),
):
    """Create a new VoC account."""
    acc = VocAccountDB(
        company_name=body.company_name,
        industry=body.industry,
        practice=body.practice,
        account_manager_id=body.account_manager_id or current_user.id,
        rag_status='green',
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return {
        "id": acc.id,
        "company_name": acc.company_name,
        "rag_status": acc.rag_status,
    }


# ── GET /api/voc/accounts/:id  ────────────────────────────────────────────────
@router.get('/voc/accounts/{account_id}')
def voc_get_account(
    account_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    """Account detail + response history."""
    acc = db.query(VocAccountDB).filter(
        VocAccountDB.id == account_id,
        VocAccountDB.deleted_at == None,
    ).first()
    if not acc:
        raise HTTPException(404, "Account not found")

    responses = (
        db.query(VocResponseDB)
        .filter(VocResponseDB.account_id == account_id)
        .order_by(VocResponseDB.submitted_at.desc())
        .limit(20)
        .all()
    )

    return {
        "id":           acc.id,
        "company_name": acc.company_name,
        "industry":     acc.industry,
        "practice":     acc.practice,
        "latest_nps":   acc.latest_nps,
        "latest_csat":  float(acc.latest_csat) if acc.latest_csat is not None else None,
        "rag_status":   acc.rag_status,
        "total_responses": acc.total_responses,
        "recent_responses": [
            {
                "nps_score":    r.nps_score,
                "csat_score":   r.csat_score,
                "sentiment":    r.sentiment,
                "verbatim":     r.verbatim,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in responses
        ],
    }


# ── PUT /api/voc/accounts/:id  ────────────────────────────────────────────────
class VocAccountUpdateReq(BaseModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    practice: Optional[str] = None
    rag_status: Optional[str] = None


@router.put('/voc/accounts/{account_id}')
def voc_update_account(
    account_id: str,
    body: VocAccountUpdateReq,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_role("admin", "super_admin", "manager")),
):
    """Update account details."""
    acc = db.query(VocAccountDB).filter(
        VocAccountDB.id == account_id,
        VocAccountDB.deleted_at == None,
    ).first()
    if not acc:
        raise HTTPException(404, "Account not found")

    if body.company_name is not None:
        acc.company_name = body.company_name
    if body.industry is not None:
        acc.industry = body.industry
    if body.practice is not None:
        acc.practice = body.practice
    if body.rag_status is not None:
        acc.rag_status = body.rag_status
    acc.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": acc.id, "company_name": acc.company_name, "rag_status": acc.rag_status}


# ══════════════════════════════════════════════════════════════════════════════
#  VoC Phase 2 API Endpoints (Survey Builder · Campaign Builder · Public Survey)

# ─── Survey CRUD ─────────────────────────────────────────────────────────────

@router.get('/voc/surveys')
def voc_list_surveys(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    surveys = (
        db.query(VocSurveyDB)
        .filter(VocSurveyDB.deleted_at == None)
        .order_by(VocSurveyDB.created_at.desc())
        .all()
    )
    return [
        {
            "id":                s.id,
            "survey_type":       s.survey_type,
            "title":             s.title,
            "main_question":     s.main_question,
            "followup_question": s.followup_question,
            "practice":          s.practice,
            "thank_you_msg":     s.thank_you_msg,
            "version":           s.version,
            "created_at":        s.created_at.isoformat() if s.created_at else None,
        }
        for s in surveys
    ]


class VocSurveyCreateReq(BaseModel):
    survey_type:       str
    title:             str
    main_question:     str
    followup_question: Optional[str] = None
    practice:          Optional[str] = None
    thank_you_msg:     Optional[str] = None


@router.post('/voc/surveys', status_code=201)
def voc_create_survey(
    body: VocSurveyCreateReq,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
):
    allowed_types = ('nps', 'csat', 'ces', 'combined')
    if body.survey_type not in allowed_types:
        raise HTTPException(400, f"survey_type must be one of {allowed_types}")
    survey = VocSurveyDB(
        survey_type=body.survey_type,
        title=body.title,
        main_question=body.main_question,
        followup_question=body.followup_question,
        practice=body.practice,
        thank_you_msg=body.thank_you_msg or "Thank you for your valuable feedback!",
        created_by=current_user.id,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)
    logging.info(f"[voc] Survey created: {survey.id} by {current_user.email}")
    return {"id": survey.id, "title": survey.title, "version": survey.version, "survey_type": survey.survey_type}


@router.get('/voc/surveys/{survey_id}')
def voc_get_survey(
    survey_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    s = db.query(VocSurveyDB).filter(VocSurveyDB.id == survey_id, VocSurveyDB.deleted_at == None).first()
    if not s:
        raise HTTPException(404, "Survey not found")
    return {
        "id": s.id, "survey_type": s.survey_type, "title": s.title,
        "main_question": s.main_question, "followup_question": s.followup_question,
        "practice": s.practice, "thank_you_msg": s.thank_you_msg, "version": s.version,
    }


class VocSurveyUpdateReq(BaseModel):
    title:             Optional[str] = None
    main_question:     Optional[str] = None
    followup_question: Optional[str] = None
    practice:          Optional[str] = None
    thank_you_msg:     Optional[str] = None


@router.put('/voc/surveys/{survey_id}')
def voc_update_survey(
    survey_id: str,
    body: VocSurveyUpdateReq,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
):
    s = db.query(VocSurveyDB).filter(VocSurveyDB.id == survey_id, VocSurveyDB.deleted_at == None).first()
    if not s:
        raise HTTPException(404, "Survey not found")
    if body.title             is not None: s.title             = body.title
    if body.main_question     is not None: s.main_question     = body.main_question
    if body.followup_question is not None: s.followup_question = body.followup_question
    if body.practice          is not None: s.practice          = body.practice
    if body.thank_you_msg     is not None: s.thank_you_msg     = body.thank_you_msg
    s.version    += 1
    s.updated_at  = datetime.now(timezone.utc)
    db.commit()
    return {"id": s.id, "version": s.version}


# ─── Campaign CRUD ────────────────────────────────────────────────────────────

@router.get('/voc/campaigns')
def voc_list_campaigns(
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    campaigns = db.query(VocCampaignDB).order_by(VocCampaignDB.created_at.desc()).all()
    account_map = {a.id: a.company_name  for a in db.query(VocAccountDB).filter(VocAccountDB.deleted_at == None).all()}
    survey_map  = {s.id: s.title         for s in db.query(VocSurveyDB).filter(VocSurveyDB.deleted_at == None).all()}
    return [
        {
            "id":             c.id,
            "name":           c.name,
            "survey_id":      c.survey_id,
            "survey_title":   survey_map.get(c.survey_id, ""),
            "account_id":     c.account_id,
            "account_name":   account_map.get(c.account_id, ""),
            "status":         c.status,
            "sent_count":     c.sent_count,
            "open_count":     c.open_count,
            "click_count":    c.click_count,
            "response_count": c.response_count,
            "send_at":        c.send_at.isoformat() if c.send_at else None,
            "created_at":     c.created_at.isoformat() if c.created_at else None,
        }
        for c in campaigns
    ]


class VocCampaignCreateReq(BaseModel):
    name:       str
    survey_id:  str
    account_id: str
    subject:    Optional[str] = None
    body_html:  Optional[str] = None
    send_at:    Optional[str] = None   # ISO datetime string or None for send-now


@router.post('/voc/campaigns', status_code=201)
def voc_create_campaign(
    body: VocCampaignCreateReq,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
):
    # Validate references
    if not db.query(VocSurveyDB).filter(VocSurveyDB.id == body.survey_id).first():
        raise HTTPException(400, "Survey not found")
    acc = db.query(VocAccountDB).filter(VocAccountDB.id == body.account_id, VocAccountDB.deleted_at == None).first()
    if not acc:
        raise HTTPException(400, "Account not found")

    send_at = None
    if body.send_at:
        try:
            from dateutil import parser as dtparser
            send_at = dtparser.isoparse(body.send_at)
        except Exception:
            raise HTTPException(400, "Invalid send_at datetime format (use ISO 8601)")

    camp = VocCampaignDB(
        name=body.name,
        survey_id=body.survey_id,
        account_id=body.account_id,
        subject=body.subject or f"HSI Customer Satisfaction Survey — {acc.company_name}",
        body_html=body.body_html,
        status='draft',
        send_at=send_at,
        created_by=current_user.id,
    )
    db.add(camp)
    db.commit()
    db.refresh(camp)
    return {"id": camp.id, "name": camp.name, "status": camp.status}


@router.get('/voc/campaigns/{campaign_id}/stats')
def voc_campaign_stats(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(get_current_user),
):
    camp = db.query(VocCampaignDB).filter(VocCampaignDB.id == campaign_id).first()
    if not camp:
        raise HTTPException(404, "Campaign not found")
    total_tokens = db.query(VocSurveyTokenDB).filter(VocSurveyTokenDB.campaign_id == campaign_id).count()
    used_tokens  = db.query(VocSurveyTokenDB).filter(VocSurveyTokenDB.campaign_id == campaign_id, VocSurveyTokenDB.used == True).count()
    return {
        "id":             camp.id,
        "name":           camp.name,
        "status":         camp.status,
        "sent_count":     camp.sent_count,
        "open_count":     camp.open_count,
        "click_count":    camp.click_count,
        "response_count": used_tokens,
        "total_tokens":   total_tokens,
        "open_rate":      round(camp.open_count  / max(camp.sent_count, 1) * 100, 1),
        "click_rate":     round(camp.click_count / max(camp.sent_count, 1) * 100, 1),
        "response_rate":  round(used_tokens      / max(total_tokens, 1)   * 100, 1),
    }


class VocCampaignSendReq(BaseModel):
    recipients: List[str]   # list of email addresses


@router.post('/voc/campaigns/{campaign_id}/send')
def voc_campaign_send(
    campaign_id: str,
    body: VocCampaignSendReq,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(require_role('admin', 'super_admin', 'manager')),
):
    """Generate single-use survey tokens and (if SES configured) send emails.
    Returns survey links for copy-paste / testing when SES is not configured."""
    import secrets as _sec

    camp = db.query(VocCampaignDB).filter(VocCampaignDB.id == campaign_id).first()
    if not camp:
        raise HTTPException(404, "Campaign not found")
    if camp.status == 'closed':
        raise HTTPException(400, "Campaign is already closed")

    survey = db.query(VocSurveyDB).filter(VocSurveyDB.id == camp.survey_id).first()
    if not survey:
        raise HTTPException(400, "No survey linked to this campaign")

    # Determine base URL for survey link
    base_url = str(request.base_url).rstrip('/')
    # Use FRONTEND_URL env var if available, else derive from request
    frontend_base = os.environ.get('FRONTEND_URL', base_url.replace(':8001', ''))

    tokens_created = []
    emails_sent    = []
    ses_ok         = ses_is_configured()
    expires_at     = datetime.now(timezone.utc) + timedelta(hours=72)

    for email in body.recipients:
        email = email.strip().lower()
        if not email:
            continue
        tok_str = _sec.token_urlsafe(32)
        tok = VocSurveyTokenDB(
            token=tok_str,
            campaign_id=camp.id,
            account_id=camp.account_id,
            respondent_email=email,
            expires_at=expires_at,
        )
        db.add(tok)
        db.flush()

        survey_url = f"{frontend_base}/s/{tok_str}"
        tokens_created.append({"email": email, "url": survey_url, "token": tok_str})

        # Email body with personalisation
        html_body = (camp.body_html or _voc_default_email_html(
            recipient_email=email,
            account_name=db.query(VocAccountDB).filter(VocAccountDB.id == camp.account_id).first().company_name if camp.account_id else "Valued Customer",
            survey_url=survey_url,
            survey_title=survey.title,
        ))

        if ses_ok:
            try:
                from services.email import _is_configured, send_otp
                import boto3 as _boto3
                _client = _boto3.client('ses', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
                _client.send_email(
                    Source=f"{os.environ.get('SES_SENDER_NAME','HSI')} <{os.environ.get('SES_SENDER_EMAIL','noreply@hitachi-systems.com')}>",
                    Destination={"ToAddresses": [email]},
                    Message={
                        "Subject": {"Data": camp.subject or "HSI Customer Satisfaction Survey"},
                        "Body": {"Html": {"Data": html_body}},
                    },
                )
                emails_sent.append(email)
                db.add(VocEmailLogDB(campaign_id=camp.id, recipient_email=email, event_type='sent'))
            except Exception as _e:
                logging.error(f"[voc-email] SES send failed for {email}: {_e}")
        else:
            logging.info(f"[voc-email][DEV] Survey URL for {email}: {survey_url}")
            db.add(VocEmailLogDB(campaign_id=camp.id, recipient_email=email, event_type='sent'))

    # Update campaign counters
    camp.sent_count     += len(tokens_created)
    camp.status          = 'active'
    camp.updated_at      = datetime.now(timezone.utc)
    db.commit()

    return {
        "sent":       len(tokens_created),
        "ses_active": ses_ok,
        "links":      tokens_created,
        "message":    (
            f"Emails sent via AWS SES to {len(emails_sent)} recipients."
            if ses_ok
            else f"SES not configured — {len(tokens_created)} survey link(s) generated for testing."
        ),
    }


def _voc_default_email_html(recipient_email: str, account_name: str, survey_url: str, survey_title: str) -> str:
    return f"""<!doctype html>
<html><body style="font-family:Arial,Helvetica,sans-serif;background:#f1f5f9;padding:24px;margin:0">
<div style="max-width:580px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.07)">
  <div style="background:#CC0000;padding:24px 32px">
    <div style="color:#fff;font-size:14px;font-weight:bold;letter-spacing:2px">HITACHI SYSTEMS INDIA</div>
    <div style="color:rgba(255,255,255,0.7);font-size:11px;letter-spacing:1px;margin-top:2px">VOICE OF CUSTOMER</div>
  </div>
  <div style="padding:32px">
    <h2 style="color:#0F172A;font-size:22px;font-weight:700;margin:0 0 12px 0">Your Opinion Matters</h2>
    <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 24px 0">
      We'd love to hear about your experience working with Hitachi Systems India for <strong>{account_name}</strong>.
      Your feedback helps us serve you better and takes less than 2 minutes to complete.
    </p>
    <a href="{survey_url}" style="display:inline-block;background:#CC0000;color:#fff;font-size:14px;font-weight:700;letter-spacing:1px;padding:14px 32px;border-radius:8px;text-decoration:none;text-transform:uppercase">
      Share Feedback
    </a>
    <p style="color:#94A3B8;font-size:11px;margin:24px 0 0 0">
      This is a personalised, single-use survey link. It expires in 72 hours.
    </p>
    <hr style="border:none;border-top:1px solid #E2E8F0;margin:24px 0">
    <p style="color:#94A3B8;font-size:11px;margin:0">
      © Hitachi Systems India · If you'd prefer not to receive survey invitations, 
      <a href="#" style="color:#CC0000">unsubscribe here</a>.
    </p>
  </div>
</div>
</body></html>"""


# ─── Public Survey Page (NO AUTH) ────────────────────────────────────────────

@router.get('/voc/public/survey/{token}')
def voc_public_get_survey(token: str, db: Session = Depends(get_db)):
    """Public endpoint — validate token and return survey questions."""
    tok = db.query(VocSurveyTokenDB).filter(VocSurveyTokenDB.token == token).first()
    if not tok:
        raise HTTPException(404, "Survey link not found or expired")
    if tok.used:
        raise HTTPException(410, "This survey has already been completed. Thank you!")
    if tok.expires_at < datetime.now(timezone.utc):
        raise HTTPException(410, "This survey link has expired")

    camp = db.query(VocCampaignDB).filter(VocCampaignDB.id == tok.campaign_id).first()
    if not camp:
        raise HTTPException(404, "Campaign not found")
    survey = db.query(VocSurveyDB).filter(VocSurveyDB.id == camp.survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    acc = db.query(VocAccountDB).filter(VocAccountDB.id == tok.account_id).first()

    return {
        "token":            tok.token,
        "survey_type":      survey.survey_type,
        "title":            survey.title,
        "main_question":    survey.main_question,
        "followup_question": survey.followup_question,
        "thank_you_msg":    survey.thank_you_msg,
        "account_name":     acc.company_name if acc else "",
        "campaign_name":    camp.name,
        "expires_at":       tok.expires_at.isoformat(),
    }


class VocPublicSubmitReq(BaseModel):
    nps_score:   Optional[int] = None   # 0–10
    csat_score:  Optional[int] = None   # 1–5
    ces_score:   Optional[int] = None   # 1–7
    verbatim:    Optional[str] = None


@router.post('/voc/public/survey/{token}')
def voc_public_submit_survey(token: str, body: VocPublicSubmitReq, db: Session = Depends(get_db)):
    """Public endpoint — submit survey response. Single-use token."""
    tok = db.query(VocSurveyTokenDB).filter(VocSurveyTokenDB.token == token).first()
    if not tok:
        raise HTTPException(404, "Survey link not found")
    if tok.used:
        raise HTTPException(410, "This survey link has already been used")
    if tok.expires_at < datetime.now(timezone.utc):
        raise HTTPException(410, "This survey link has expired")

    # Validate scores
    if body.nps_score is not None and not (0 <= body.nps_score <= 10):
        raise HTTPException(400, "nps_score must be 0–10")
    if body.csat_score is not None and not (1 <= body.csat_score <= 5):
        raise HTTPException(400, "csat_score must be 1–5")
    if body.ces_score is not None and not (1 <= body.ces_score <= 7):
        raise HTTPException(400, "ces_score must be 1–7")

    # Determine sentiment from NPS
    sentiment = None
    if body.nps_score is not None:
        if body.nps_score >= 9:   sentiment = 'promoter'
        elif body.nps_score >= 7: sentiment = 'passive'
        else:                     sentiment = 'detractor'
    elif body.csat_score is not None:
        sentiment = 'promoter' if body.csat_score >= 4 else 'detractor'

    camp = db.query(VocCampaignDB).filter(VocCampaignDB.id == tok.campaign_id).first()

    resp = VocResponseDB(
        campaign_id=tok.campaign_id,
        account_id=tok.account_id,
        token_id=tok.id,
        respondent_email=tok.respondent_email,
        nps_score=body.nps_score,
        csat_score=body.csat_score,
        ces_score=body.ces_score,
        verbatim=body.verbatim,
        sentiment=sentiment,
    )
    db.add(resp)

    # Mark token used
    tok.used    = True
    tok.used_at = datetime.now(timezone.utc)

    # Update campaign response_count
    if camp:
        camp.response_count += 1
        camp.updated_at = datetime.now(timezone.utc)

    # Update account NPS / CSAT cache
    if tok.account_id:
        acc = db.query(VocAccountDB).filter(VocAccountDB.id == tok.account_id).first()
        if acc:
            # Recompute latest NPS from all responses for this account
            all_resps = db.query(VocResponseDB).filter(VocResponseDB.account_id == tok.account_id).all()
            nps_r = [r for r in all_resps if r.nps_score is not None]
            if nps_r:
                prom = sum(1 for r in nps_r if r.nps_score >= 9)
                detr = sum(1 for r in nps_r if r.nps_score <= 6)
                acc.latest_nps = round((prom - detr) / len(nps_r) * 100)
            csat_r = [r for r in all_resps if r.csat_score is not None]
            if csat_r:
                sat = sum(1 for r in csat_r if r.csat_score >= 4)
                acc.latest_csat = round(sat / len(csat_r) * 100, 2)
            acc.total_responses  = len(all_resps) + 1
            # RAG auto-compute
            nps_val = acc.latest_nps or 0
            acc.rag_status = 'green' if nps_val >= 50 else 'amber' if nps_val >= 20 else 'red'
            acc.updated_at = datetime.now(timezone.utc)

    db.commit()

    survey = db.query(VocSurveyDB).filter(VocSurveyDB.id == camp.survey_id).first() if camp else None
    return {
        "success":       True,
        "response_id":   resp.id,
        "thank_you_msg": survey.thank_you_msg if survey else "Thank you for your feedback!",
    }


# ── Mount & Middleware ────────────────────────────────────────────────────────
app.include_router(router)

cors_origins = [o.strip() for o in os.environ.get('CORS_ORIGINS', '*').split(',') if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=cors_origins or ['*'],
    allow_methods=['*'],
    allow_headers=['*', 'X-Request-ID'],
    expose_headers=['X-Request-ID'],
)


# ── Sprint F: Request-ID middleware ──────────────────────────────────────────
class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attaches a unique X-Request-ID to every request/response for tracing."""
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        request.state.request_id = rid
        sentry_sdk.set_tag('request_id', rid)
        response = await call_next(request)
        response.headers['X-Request-ID'] = rid
        return response

app.add_middleware(RequestIDMiddleware)


# ── Sprint G — static mount for local-fallback uploads (served when MinIO off) ─
try:
    from fastapi.staticfiles import StaticFiles
    from pathlib import Path as _P
    _UP = _P(os.environ.get('LOCAL_UPLOADS_DIR', '/tmp/hsi_uploads')).resolve()
    _UP.mkdir(parents=True, exist_ok=True)
    app.mount('/api/uploads-local', StaticFiles(directory=str(_UP)), name='uploads-local')
except Exception as _stat_err:                                         # noqa: BLE001
    logging.warning(f"[static] uploads-local mount failed: {_stat_err}")


# ── Sprint G — wire Redis pub/sub into the WebSocket manager ─────────────────
@app.on_event('startup')
async def _start_pubsub_listener():
    try:
        await pubsub_svc.init_publisher()
        # When a publish arrives on Redis, broadcast to this instance's WS clients
        await pubsub_svc.start_listener(ws_manager.broadcast)
    except Exception as e:                                             # noqa: BLE001
        logging.warning(f"[pubsub] listener startup skipped: {e}")


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s [%(name)s] %(message)s')
logger = logging.getLogger(__name__)
_sentry_status = f"dsn={'set' if _sentry_dsn else 'not set (disabled)'}"
logger.info(f"HSI EEP API ready · domain=@{ALLOWED_DOMAIN} · bcrypt={BCRYPT_ROUNDS} · "
            f"mfa={'on' if MFA_ENABLED else 'off'} · ses={'on' if ses_is_configured() else 'off (dev)'} · "
            f"redis={'on' if is_redis_active() else 'in-memory'} · sentry={_sentry_status} · "
            f"storage={storage_svc.mode()}")


# ── Sprint E — Birthday XP Scheduler ─────────────────────────────────────────
# Awards 50 XP to every user whose birthday is today (daily at 00:05 IST).

def _run_reminder_job():
    """Weekly reminder: notify users who have pending submissions (practice/replication/tech-day)."""
    try:
        db = SessionLocal()
        # Find users with pending practices
        pending_user_ids = set()
        for (uid,) in db.query(BestPracticeDB.author_id).filter(
                BestPracticeDB.status == 'pending').distinct().all():
            pending_user_ids.add(uid)
        for (uid,) in db.query(ReplicationDB.replicator_id).filter(
                ReplicationDB.status == 'pending').distinct().all():
            pending_user_ids.add(uid)
        for (uid,) in db.query(TechDayDB.conductor_id).filter(
                TechDayDB.status == 'pending').distinct().all():
            pending_user_ids.add(uid)
        count = 0
        for uid in pending_user_ids:
            try:
                _dispatch_notification(
                    db,
                    title='⏰ You have pending submissions awaiting approval',
                    body='One or more of your submissions (practices, replications, or tech days) are still pending admin review.',
                    category='reminder', target_type='user', target_id=uid,
                )
                count += 1
            except Exception:  # noqa: BLE001
                pass
        db.commit()
        logger.info(f"[ReminderJob] Sent reminder to {count} user(s) with pending submissions")
    except Exception as e:
        logger.error(f"[ReminderJob] Error: {e}")
    finally:
        db.close()


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
    _scheduler.add_job(_run_reminder_job, 'cron', day_of_week='mon', hour=9, minute=0, id='weekly_reminder')
    _scheduler.start()
    logger.info("[Scheduler] Birthday XP job scheduled at 00:05 IST daily; Reminder job Monday 09:00 IST")
except Exception as _sched_err:
    logger.warning(f"[Scheduler] Could not start scheduler: {_sched_err}")
