"""
HSI Email Service — AWS SES wrapper with graceful dev-mode fallback.

Behaviour:
- If AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY are set → send via SES.
- Otherwise → log the message to backend log (dev fallback). Useful for local
  testing without AWS credentials. Returns success=True so the auth flow does
  not break.

In production, set the AWS creds. The service does NOT auto-fail-closed in dev
because that would block all login flows when MFA is enabled but SES isn't
configured yet (e.g. before going live).
"""
from __future__ import annotations
import os, logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    _HAS_BOTO = True
except ImportError:
    _HAS_BOTO = False


def _is_configured() -> bool:
    return bool(_HAS_BOTO
                and os.environ.get('AWS_ACCESS_KEY_ID')
                and os.environ.get('AWS_SECRET_ACCESS_KEY'))


def _build_otp_html(otp: str, purpose: str) -> str:
    purpose_label = {
        'login':           'log in to your account',
        'register':        'verify your email and complete registration',
        'reset_password':  'reset your password',
        'admin_action':    'authorize a sensitive admin action',
    }.get(purpose, 'verify this request')
    return f"""<!doctype html>
<html><body style="font-family:Arial,Helvetica,sans-serif;background:#f1f5f9;padding:24px">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,0.05)">
    <div style="font-weight:bold;color:#CC0000;font-size:18px;letter-spacing:1px;margin-bottom:6px">HITACHI SYSTEMS INDIA</div>
    <div style="color:#475569;font-size:13px;margin-bottom:24px">HSI Enterprise Platform</div>
    <h2 style="color:#0f172a;font-size:20px;margin:0 0 12px 0">Your verification code</h2>
    <p style="color:#475569;font-size:14px;line-height:1.5">Use this code to {purpose_label}. It expires in <b>10 minutes</b>.</p>
    <div style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#0f172a;background:#f8fafc;border-radius:8px;padding:18px 24px;text-align:center;margin:24px 0;font-family:'SF Mono',Monaco,monospace">{otp}</div>
    <p style="color:#dc2626;font-size:12px;font-weight:600;margin:0">⚠ Never share this code. HSI staff will never ask for it.</p>
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
    <p style="color:#94a3b8;font-size:11px;margin:0">If you didn't request this, ignore this email or contact IT support.</p>
    <p style="color:#94a3b8;font-size:11px;margin:8px 0 0 0">© Hitachi Systems India · HSI Enterprise Platform</p>
  </div>
</body></html>"""


def _build_otp_text(otp: str, purpose: str) -> str:
    return (f"HSI Enterprise Platform — Verification Code\n\n"
            f"Your code is: {otp}\n"
            f"Purpose: {purpose}\n"
            f"Expires in 10 minutes.\n\n"
            f"Never share this code with anyone.\n"
            f"If you didn't request this, ignore this email.\n")


def send_otp(recipient_email: str, otp: str, purpose: str = 'login') -> Tuple[bool, str]:
    """Returns (success, message_id_or_error)."""
    sender_email = os.environ.get('SES_SENDER_EMAIL', 'noreply@hitachi-systems.com')
    sender_name  = os.environ.get('SES_SENDER_NAME',  'HSI Enterprise Platform')
    region       = os.environ.get('AWS_REGION', 'us-east-1')

    if not _is_configured():
        logger.warning(
            f"[email][DEV-FALLBACK] AWS SES not configured. OTP for {recipient_email} "
            f"(purpose={purpose}): {otp}  ← copy from log to test"
        )
        return True, 'dev-fallback'

    try:
        client = boto3.client(
            'ses', region_name=region,
            aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        )
        resp = client.send_email(
            Source=f"{sender_name} <{sender_email}>",
            Destination={'ToAddresses': [recipient_email]},
            Message={
                'Subject': {'Data': f'HSI verification code: {otp}', 'Charset': 'UTF-8'},
                'Body': {
                    'Html': {'Data': _build_otp_html(otp, purpose), 'Charset': 'UTF-8'},
                    'Text': {'Data': _build_otp_text(otp, purpose), 'Charset': 'UTF-8'},
                },
            },
            Tags=[{'Name': 'service', 'Value': 'otp-mfa'},
                  {'Name': 'purpose', 'Value': purpose}],
        )
        msg_id = resp.get('MessageId', '')
        logger.info(f"[email] SES sent to {recipient_email} purpose={purpose} msg_id={msg_id}")
        return True, msg_id
    except ClientError as e:
        code = e.response.get('Error', {}).get('Code', 'Unknown')
        msg  = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"[email] SES ClientError [{code}] for {recipient_email}: {msg}")
        return False, f"SES error [{code}]"
    except (BotoCoreError, Exception) as e:                  # noqa: BLE001
        logger.error(f"[email] SES unexpected error for {recipient_email}: {e}")
        return False, str(e)


def is_configured() -> bool:
    """Public helper for /health and similar endpoints."""
    return _is_configured()
