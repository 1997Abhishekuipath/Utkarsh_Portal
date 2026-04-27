"""
Sprint G — MinIO / S3-compatible object storage service.

Responsibilities:
- Single entry point for uploading attachments, avatars, EDM images.
- Returns a stable object key + public URL for frontend consumption.
- Graceful degradation: if MinIO isn't reachable, falls back to local disk
  (./uploads) so dev still works; logs a warning.

Env (docker-compose populates these; defaults for local dev):
    MINIO_ENDPOINT          host:port of MinIO server (default: minio:9000)
    MINIO_ACCESS_KEY        default: minioadmin
    MINIO_SECRET_KEY        default: minioadmin
    MINIO_BUCKET            default: hsi-eep
    MINIO_SECURE            "true"/"false"; default false (docker network)
    MINIO_PUBLIC_URL        public base URL shown to browser for object reads
                            e.g. https://example.com/uploads
                            defaults to http://{MINIO_ENDPOINT}/{BUCKET}
"""
from __future__ import annotations
import os, logging, uuid, io, mimetypes
from pathlib import Path
from typing import BinaryIO, Optional

logger = logging.getLogger(__name__)

_MINIO_ENDPOINT   = os.environ.get('MINIO_ENDPOINT', 'minio:9000').strip()
_MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', 'minioadmin').strip()
_MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', 'minioadmin').strip()
_MINIO_BUCKET     = os.environ.get('MINIO_BUCKET', 'hsi-eep').strip()
_MINIO_SECURE     = os.environ.get('MINIO_SECURE', 'false').lower() in ('1', 'true', 'yes')
_MINIO_PUBLIC_URL = os.environ.get('MINIO_PUBLIC_URL', '').strip().rstrip('/')

# Local fallback dir — served by FastAPI StaticFiles mount at /api/uploads-local/*
_LOCAL_DIR = Path(os.environ.get('LOCAL_UPLOADS_DIR', '/tmp/hsi_uploads')).resolve()
_LOCAL_DIR.mkdir(parents=True, exist_ok=True)

_client = None
_mode   = 'local'                                          # 'minio' or 'local'


def _init_client():
    global _client, _mode
    try:
        from minio import Minio
        from minio.error import S3Error                    # noqa: F401
        _client = Minio(
            _MINIO_ENDPOINT,
            access_key=_MINIO_ACCESS_KEY,
            secret_key=_MINIO_SECRET_KEY,
            secure=_MINIO_SECURE,
        )
        # Idempotent bucket create
        found = _client.bucket_exists(_MINIO_BUCKET)
        if not found:
            _client.make_bucket(_MINIO_BUCKET)
        # Public-read policy so browsers can GET objects directly
        policy = (
            '{"Version":"2012-10-17","Statement":[{"Effect":"Allow",'
            '"Principal":{"AWS":["*"]},"Action":["s3:GetObject"],'
            f'"Resource":["arn:aws:s3:::{_MINIO_BUCKET}/*"]}}]}}'
        )
        try:
            _client.set_bucket_policy(_MINIO_BUCKET, policy)
        except Exception:                                  # noqa: BLE001
            pass
        _mode = 'minio'
        logger.info(f"[storage] MinIO OK · bucket={_MINIO_BUCKET} · endpoint={_MINIO_ENDPOINT}")
    except Exception as e:                                 # noqa: BLE001
        logger.warning(f"[storage] MinIO unavailable ({e}); using local-disk fallback at {_LOCAL_DIR}")
        _client = None
        _mode   = 'local'


_init_client()


# ── Public API ───────────────────────────────────────────────────────────────

def is_minio_active() -> bool:
    return _mode == 'minio' and _client is not None


def mode() -> str:
    return _mode


def _safe_ext(filename: str) -> str:
    ext = Path(filename or '').suffix.lower()
    # whitelist safe extensions (add more as needed)
    allowed = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg',
               '.pdf', '.txt', '.md', '.csv', '.xlsx', '.docx', '.pptx'}
    return ext if ext in allowed else '.bin'


def _object_key(prefix: str, filename: str) -> str:
    return f"{prefix.strip('/')}/{uuid.uuid4().hex}{_safe_ext(filename)}"


def upload_fileobj(file_obj: BinaryIO, filename: str, prefix: str = 'misc',
                   content_type: Optional[str] = None) -> dict:
    """Upload a file-like object. Returns {key, url, size, content_type}."""
    key = _object_key(prefix, filename)
    ct  = content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    # Read once, we need length for MinIO and bytes for local fallback
    data = file_obj.read()
    size = len(data)

    if is_minio_active():
        try:
            _client.put_object(
                _MINIO_BUCKET, key, io.BytesIO(data), length=size, content_type=ct,
            )
            base = _MINIO_PUBLIC_URL or f"http://{_MINIO_ENDPOINT}/{_MINIO_BUCKET}"
            url = f"{base}/{key}"
            return {'key': key, 'url': url, 'size': size, 'content_type': ct, 'storage': 'minio'}
        except Exception as e:                             # noqa: BLE001
            logger.error(f"[storage] MinIO put failed ({e}); falling back to local")

    # Local fallback — write to disk, URL served by /api/uploads-local/*
    target = _LOCAL_DIR / key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    # URL is a relative path served by FastAPI StaticFiles mount in server.py
    url = f"/api/uploads-local/{key}"
    return {'key': key, 'url': url, 'size': size, 'content_type': ct, 'storage': 'local'}


def local_path(key: str) -> Path:
    """Absolute path for a local-fallback object; safe joined inside _LOCAL_DIR."""
    p = (_LOCAL_DIR / key).resolve()
    if not str(p).startswith(str(_LOCAL_DIR)):
        raise ValueError('invalid key')
    return p


def delete_object(key: str) -> bool:
    try:
        if is_minio_active():
            _client.remove_object(_MINIO_BUCKET, key)
            return True
        # Local
        p = local_path(key)
        if p.exists():
            p.unlink()
            return True
    except Exception as e:                                 # noqa: BLE001
        logger.warning(f"[storage] delete failed key={key}: {e}")
    return False
