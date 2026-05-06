"""
Customer Management Portal - FastAPI Backend
"""
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import io
import csv
import logging
import uuid
import secrets
import asyncio
import bcrypt
import jwt
import resend
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal, Dict, Any
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# ----------------- Setup -----------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = os.environ.get("APP_NAME", "cmportal")
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
storage_key: Optional[str] = None
if RESEND_API_KEY and not RESEND_API_KEY.startswith("re_placeholder"):
    resend.api_key = RESEND_API_KEY


def init_storage() -> Optional[str]:
    """Initialize storage session. Returns storage_key or None on failure."""
    global storage_key
    if storage_key:
        return storage_key
    if not EMERGENT_LLM_KEY:
        return None
    try:
        resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
        resp.raise_for_status()
        storage_key = resp.json()["storage_key"]
        return storage_key
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
        return None


def storage_put(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=503, detail="Storage unavailable")
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    if resp.status_code == 403:
        # refresh key once
        global storage_key
        storage_key = None
        key = init_storage()
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data, timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def storage_get(path: str) -> tuple:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=503, detail="Storage unavailable")
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 403:
        global storage_key
        storage_key = None
        key = init_storage()
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Customer Management Portal")
api = APIRouter(prefix="/api")

# ----------------- Helpers -----------------
def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def create_access_token(uid: str, email: str, role: str) -> str:
    payload = {"sub": uid, "email": email, "role": role,
               "exp": datetime.now(timezone.utc) + timedelta(hours=8),
               "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(uid: str) -> str:
    payload = {"sub": uid, "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=28800, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=604800, path="/")

def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(*roles: str):
    async def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker

require_admin = require_role("admin")
require_manager = require_role("admin", "manager")  # both can write
# viewer is read-only; auth alone via get_current_user is sufficient for GET

async def log_activity(user: dict, action: str, entity: str, entity_id: str = "", details: str = ""):
    await db.activity_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user.get("id"),
        "user_email": user.get("email"),
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

# ----------------- Models -----------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordIn(BaseModel):
    email: EmailStr

class ResetPasswordIn(BaseModel):
    token: str
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["admin", "manager", "viewer"]

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[Literal["admin", "manager", "viewer"]] = None
    password: Optional[str] = None

class CustomerIn(BaseModel):
    company_name: str
    customer_name: str
    contact_number: str = ""
    email: str = ""
    address: str = ""
    country: str = ""
    state: str = ""
    city: str = ""
    gst_number: str = ""
    pan_number: str = ""
    support_contact_person: str = ""
    support_contact_number: str = ""
    account_manager: str = ""
    status: Literal["Active", "Inactive"] = "Active"

class ProductIn(BaseModel):
    product_name: str
    product_version: str = ""
    product_category: str = ""
    vendor: str = ""
    support_type: str = ""
    license_model: str = ""
    os_compatibility: str = ""
    description: str = ""

class LicenseIn(BaseModel):
    customer_id: str
    product_id: str
    license_key: str
    license_type: str = "Subscription"
    license_count: int = 1
    subscription_type: str = "Annual"
    purchase_date: str
    activation_date: str
    expiry_date: str
    renewal_date: str = ""
    cost: float = 0.0
    currency: str = "USD"
    invoice_number: str = ""
    po_number: str = ""
    support_expiry: str = ""
    warranty_expiry: str = ""
    auto_renewal: bool = False
    notes: str = ""

# ----------------- Auth Endpoints -----------------
@api.post("/auth/login")
async def login(payload: LoginIn, response: Response, request: Request):
    email = payload.email.lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"

    # Brute force
    attempt = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if attempt and attempt.get("count", 0) >= 5:
        last = datetime.fromisoformat(attempt["last_attempt"])
        if datetime.now(timezone.utc) - last < timedelta(minutes=15):
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
        await db.login_attempts.delete_one({"identifier": identifier})

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"last_attempt": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    await db.login_attempts.delete_one({"identifier": identifier})

    access = create_access_token(user["id"], user["email"], user["role"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)

    user.pop("_id", None)
    user.pop("password_hash", None)
    return user

@api.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    clear_auth_cookies(response)
    return {"ok": True}

@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user

@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    rt = request.cookies.get("refresh_token")
    if not rt:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(rt, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access = create_access_token(user["id"], user["email"], user["role"])
        response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=28800, path="/")
        return {"ok": True}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@api.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordIn):
    user = await db.users.find_one({"email": payload.email.lower()})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "token": token,
            "user_id": user["id"],
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "used": False,
        })
        logger.info(f"Password reset link: /reset-password?token={token}")
    return {"message": "If the email exists, a reset link has been sent."}

@api.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordIn):
    record = await db.password_reset_tokens.find_one({"token": payload.token, "used": False})
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if record["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")
    await db.users.update_one({"id": record["user_id"]}, {"$set": {"password_hash": hash_password(payload.password)}})
    await db.password_reset_tokens.update_one({"token": payload.token}, {"$set": {"used": True}})
    return {"ok": True}

# ----------------- User Management (admin) -----------------
@api.get("/users")
async def list_users(user: dict = Depends(require_admin)):
    return await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)

@api.post("/users")
async def create_user(payload: UserCreate, user: dict = Depends(require_admin)):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")
    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": payload.name,
        "role": payload.role,
        "password_hash": hash_password(payload.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(new_user)
    await log_activity(user, "create", "user", new_user["id"], f"Created user {email}")
    new_user.pop("password_hash")
    new_user.pop("_id", None)
    return new_user

@api.put("/users/{user_id}")
async def update_user(user_id: str, payload: UserUpdate, user: dict = Depends(require_admin)):
    update = {}
    if payload.name is not None:
        update["name"] = payload.name
    if payload.role is not None:
        update["role"] = payload.role
    if payload.password:
        update["password_hash"] = hash_password(payload.password)
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    res = await db.users.update_one({"id": user_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await log_activity(user, "update", "user", user_id)
    return {"ok": True}

@api.delete("/users/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_admin)):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    res = await db.users.delete_one({"id": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    await log_activity(user, "delete", "user", user_id)
    return {"ok": True}

# ----------------- Customers -----------------
@api.get("/customers")
async def list_customers(
    search: Optional[str] = None,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    query = {}
    if status:
        query["status"] = status
    if search:
        query["$or"] = [
            {"company_name": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"city": {"$regex": search, "$options": "i"}},
        ]
    return await db.customers.find(query, {"_id": 0}).sort("created_at", -1).to_list(2000)

@api.get("/customers/{cid}")
async def get_customer(cid: str, user: dict = Depends(get_current_user)):
    cust = await db.customers.find_one({"id": cid}, {"_id": 0})
    if not cust:
        raise HTTPException(status_code=404, detail="Not found")
    return cust

@api.post("/customers")
async def create_customer(payload: CustomerIn, user: dict = Depends(require_manager)):
    doc = payload.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["customer_code"] = f"CUST-{int(datetime.now().timestamp())}"
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["updated_at"] = doc["created_at"]
    await db.customers.insert_one(doc)
    await log_activity(user, "create", "customer", doc["id"], payload.company_name)
    doc.pop("_id", None)
    return doc

@api.put("/customers/{cid}")
async def update_customer(cid: str, payload: CustomerIn, user: dict = Depends(require_manager)):
    update = payload.model_dump()
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.customers.update_one({"id": cid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "update", "customer", cid)
    return {"ok": True}

@api.delete("/customers/{cid}")
async def delete_customer(cid: str, user: dict = Depends(require_admin)):
    res = await db.customers.delete_one({"id": cid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "delete", "customer", cid)
    return {"ok": True}

# ----------------- Products -----------------
@api.get("/products")
async def list_products(
    search: Optional[str] = None,
    category: Optional[str] = None,
    vendor: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    query = {}
    if category:
        query["product_category"] = category
    if vendor:
        query["vendor"] = vendor
    if search:
        query["$or"] = [
            {"product_name": {"$regex": search, "$options": "i"}},
            {"vendor": {"$regex": search, "$options": "i"}},
        ]
    return await db.products.find(query, {"_id": 0}).sort("created_at", -1).to_list(2000)

@api.post("/products")
async def create_product(payload: ProductIn, user: dict = Depends(require_manager)):
    doc = payload.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.products.insert_one(doc)
    await log_activity(user, "create", "product", doc["id"], payload.product_name)
    doc.pop("_id", None)
    return doc

@api.put("/products/{pid}")
async def update_product(pid: str, payload: ProductIn, user: dict = Depends(require_manager)):
    res = await db.products.update_one({"id": pid}, {"$set": payload.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "update", "product", pid)
    return {"ok": True}

@api.delete("/products/{pid}")
async def delete_product(pid: str, user: dict = Depends(require_admin)):
    res = await db.products.delete_one({"id": pid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "delete", "product", pid)
    return {"ok": True}

# ----------------- Licenses -----------------
def license_status(expiry: str) -> str:
    try:
        d = datetime.fromisoformat(expiry).date()
    except Exception:
        return "Unknown"
    today = datetime.now(timezone.utc).date()
    days = (d - today).days
    if days < 0:
        return "Expired"
    if days <= 30:
        return "Expiring Soon"
    return "Active"

async def enrich_license(lic: dict) -> dict:
    lic.pop("_id", None)
    lic["status"] = license_status(lic.get("expiry_date", ""))
    cust = await db.customers.find_one({"id": lic.get("customer_id")}, {"_id": 0, "company_name": 1, "customer_name": 1})
    prod = await db.products.find_one({"id": lic.get("product_id")}, {"_id": 0, "product_name": 1, "vendor": 1, "product_category": 1})
    lic["customer_name"] = cust["company_name"] if cust else "Unknown"
    lic["product_name"] = prod["product_name"] if prod else "Unknown"
    lic["vendor"] = prod["vendor"] if prod else lic.get("vendor", "")
    lic["product_category"] = prod["product_category"] if prod else ""
    return lic

@api.get("/licenses")
async def list_licenses(
    search: Optional[str] = None,
    status: Optional[str] = None,
    vendor: Optional[str] = None,
    category: Optional[str] = None,
    expiry_within_days: Optional[int] = None,
    user: dict = Depends(get_current_user),
):
    licenses = await db.licenses.find({}, {"_id": 0}).sort("expiry_date", 1).to_list(5000)
    enriched = []
    today = datetime.now(timezone.utc).date()
    for lic in licenses:
        e = await enrich_license(lic)
        if status and e["status"] != status:
            continue
        if vendor and e.get("vendor") != vendor:
            continue
        if category and e.get("product_category") != category:
            continue
        if expiry_within_days is not None:
            try:
                exp = datetime.fromisoformat(e["expiry_date"]).date()
                if (exp - today).days > expiry_within_days or (exp - today).days < 0:
                    continue
            except Exception:
                continue
        if search:
            s = search.lower()
            blob = " ".join([str(e.get(k, "")) for k in ["license_key", "customer_name", "product_name", "vendor", "invoice_number", "po_number"]]).lower()
            if s not in blob:
                continue
        enriched.append(e)
    return enriched

@api.post("/licenses")
async def create_license(payload: LicenseIn, user: dict = Depends(require_manager)):
    doc = payload.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.licenses.insert_one(doc)
    await log_activity(user, "create", "license", doc["id"], payload.license_key)
    return await enrich_license(doc)

@api.put("/licenses/{lid}")
async def update_license(lid: str, payload: LicenseIn, user: dict = Depends(require_manager)):
    update = payload.model_dump()
    existing = await db.licenses.find_one({"id": lid}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    # Compute diff
    changes = {}
    for k, v in update.items():
        if existing.get(k) != v:
            changes[k] = {"from": existing.get(k), "to": v}
    if changes:
        await db.renewal_history.insert_one({
            "id": str(uuid.uuid4()),
            "license_id": lid,
            "changed_by": user["email"],
            "changed_by_id": user["id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "changes": changes,
            "snapshot_after": update,
        })
    res = await db.licenses.update_one({"id": lid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "update", "license", lid, f"{len(changes)} fields changed")
    return {"ok": True, "changes": len(changes)}

@api.delete("/licenses/{lid}")
async def delete_license(lid: str, user: dict = Depends(require_admin)):
    res = await db.licenses.delete_one({"id": lid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "delete", "license", lid)
    return {"ok": True}

# ----------------- Dashboard & Reports -----------------
@api.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    today = datetime.now(timezone.utc).date()
    customers = await db.customers.count_documents({})
    active_customers = await db.customers.count_documents({"status": "Active"})
    licenses = await db.licenses.find({}, {"_id": 0}).to_list(5000)
    products_count = await db.products.count_documents({})

    active = expiring_30 = expiring_60 = expiring_90 = expired = 0
    revenue_total = 0.0
    monthly_revenue = {}
    monthly_renewals = {}
    vendor_stats = {}
    product_stats = {}
    customer_growth = {}

    critical_expiring = []
    upcoming_renewals = []

    for lic in licenses:
        try:
            exp = datetime.fromisoformat(lic["expiry_date"]).date()
        except Exception:
            continue
        days = (exp - today).days
        cost = float(lic.get("cost", 0) or 0)
        revenue_total += cost
        # monthly buckets
        ym = exp.strftime("%Y-%m")
        monthly_renewals[ym] = monthly_renewals.get(ym, 0) + 1
        try:
            pdate = datetime.fromisoformat(lic["purchase_date"]).date()
            pym = pdate.strftime("%Y-%m")
            monthly_revenue[pym] = monthly_revenue.get(pym, 0) + cost
        except Exception:
            pass

        if days < 0:
            expired += 1
        elif days <= 30:
            expiring_30 += 1
            critical_expiring.append({**lic, "days_left": days})
        elif days <= 60:
            expiring_60 += 1
        elif days <= 90:
            expiring_90 += 1
        if days >= 0:
            active += 1
        if 0 <= days <= 60:
            upcoming_renewals.append({**lic, "days_left": days})

        prod = await db.products.find_one({"id": lic.get("product_id")}, {"_id": 0, "product_name": 1, "vendor": 1})
        if prod:
            product_stats[prod["product_name"]] = product_stats.get(prod["product_name"], 0) + lic.get("license_count", 1)
            vendor_stats[prod["vendor"]] = vendor_stats.get(prod["vendor"], 0) + 1

    customers_list = await db.customers.find({}, {"_id": 0, "created_at": 1}).to_list(2000)
    for c in customers_list:
        try:
            cd = datetime.fromisoformat(c["created_at"]).date()
            ym = cd.strftime("%Y-%m")
            customer_growth[ym] = customer_growth.get(ym, 0) + 1
        except Exception:
            pass

    # enrich critical & upcoming
    for arr in [critical_expiring, upcoming_renewals]:
        for x in arr:
            await enrich_license(x)
    critical_expiring.sort(key=lambda x: x.get("days_left", 0))
    upcoming_renewals.sort(key=lambda x: x.get("days_left", 0))

    # top customers (by license cost)
    top_customers = {}
    for lic in licenses:
        cid = lic.get("customer_id")
        top_customers[cid] = top_customers.get(cid, 0) + float(lic.get("cost", 0) or 0)
    top_customer_list = []
    for cid, val in sorted(top_customers.items(), key=lambda x: -x[1])[:5]:
        c = await db.customers.find_one({"id": cid}, {"_id": 0, "company_name": 1})
        if c:
            top_customer_list.append({"company_name": c["company_name"], "revenue": val})

    return {
        "totals": {
            "customers": customers,
            "active_customers": active_customers,
            "products": products_count,
            "licenses": len(licenses),
            "active_licenses": active,
            "expired_licenses": expired,
            "expiring_30": expiring_30,
            "expiring_60": expiring_60,
            "expiring_90": expiring_90,
            "revenue_total": round(revenue_total, 2),
        },
        "monthly_revenue": [{"month": k, "revenue": round(v, 2)} for k, v in sorted(monthly_revenue.items())],
        "monthly_renewals": [{"month": k, "count": v} for k, v in sorted(monthly_renewals.items())],
        "customer_growth": [{"month": k, "count": v} for k, v in sorted(customer_growth.items())],
        "vendor_stats": [{"vendor": k, "count": v} for k, v in sorted(vendor_stats.items(), key=lambda x: -x[1])],
        "product_stats": [{"product": k, "count": v} for k, v in sorted(product_stats.items(), key=lambda x: -x[1])],
        "critical_expiring": critical_expiring[:10],
        "upcoming_renewals": upcoming_renewals[:10],
        "top_customers": top_customer_list,
    }

@api.get("/reports/{report_type}")
async def reports(report_type: str, user: dict = Depends(get_current_user)):
    today = datetime.now(timezone.utc).date()
    licenses = await db.licenses.find({}, {"_id": 0}).to_list(5000)
    enriched = [await enrich_license(l) for l in licenses]
    if report_type == "monthly-expiry":
        end = today + timedelta(days=30)
        return [l for l in enriched if l["status"] in ("Expiring Soon",)]
    elif report_type == "customer-license":
        return enriched
    elif report_type == "vendor":
        agg = {}
        for l in enriched:
            v = l.get("vendor") or "Unknown"
            agg.setdefault(v, {"vendor": v, "count": 0, "revenue": 0.0, "expired": 0, "active": 0})
            agg[v]["count"] += 1
            agg[v]["revenue"] += float(l.get("cost", 0) or 0)
            if l["status"] == "Expired":
                agg[v]["expired"] += 1
            else:
                agg[v]["active"] += 1
        return list(agg.values())
    elif report_type == "revenue":
        return enriched
    elif report_type == "renewal":
        return [l for l in enriched if l["status"] in ("Expiring Soon", "Expired")]
    elif report_type == "expired":
        return [l for l in enriched if l["status"] == "Expired"]
    raise HTTPException(status_code=404, detail="Unknown report")

# ----------------- Activity Logs & Notifications -----------------
@api.get("/activity-logs")
async def get_activity_logs(user: dict = Depends(require_admin)):
    return await db.activity_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(200).to_list(200)

@api.get("/notifications")
async def notifications(user: dict = Depends(get_current_user)):
    today = datetime.now(timezone.utc).date()
    licenses = await db.licenses.find({}, {"_id": 0}).to_list(5000)
    notifs = []
    for lic in licenses:
        try:
            exp = datetime.fromisoformat(lic["expiry_date"]).date()
        except Exception:
            continue
        days = (exp - today).days
        if days in (90, 60, 30) or days < 0 and days > -30:
            e = await enrich_license(lic)
            notifs.append({
                "id": lic["id"],
                "title": f"License {'Expired' if days < 0 else 'expires in ' + str(days) + ' days'}",
                "message": f"{e.get('product_name')} for {e.get('customer_name')}",
                "level": "expired" if days < 0 else ("critical" if days <= 30 else ("warning" if days <= 60 else "info")),
                "expiry_date": lic["expiry_date"],
                "days_left": days,
            })
    notifs.sort(key=lambda x: x["days_left"])
    return notifs[:20]

# ----------------- Seeding -----------------
async def seed_data():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.customers.create_index("id", unique=True)
    await db.products.create_index("id", unique=True)
    await db.licenses.create_index("id", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index("identifier")

    # Seed users
    seeds = [
        (os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"], "Admin User", "admin"),
        (os.environ["MANAGER_EMAIL"], os.environ["MANAGER_PASSWORD"], "Manager User", "manager"),
        (os.environ["VIEWER_EMAIL"], os.environ["VIEWER_PASSWORD"], "Viewer User", "viewer"),
    ]
    for email, pw, name, role in seeds:
        existing = await db.users.find_one({"email": email})
        if existing:
            if not verify_password(pw, existing["password_hash"]):
                await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(pw)}})
        else:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": email, "name": name, "role": role,
                "password_hash": hash_password(pw),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    if await db.customers.count_documents({}) > 0:
        return  # already seeded

    # Sample customers
    customers_data = [
        ("Acme Corporation", "John Anderson", "USA", "California", "San Francisco", "Sarah Mitchell"),
        ("Globex Industries", "Maria Rodriguez", "USA", "New York", "New York", "David Chen"),
        ("Initech Software", "Peter Gibbons", "USA", "Texas", "Austin", "Sarah Mitchell"),
        ("Umbrella Corp", "Albert Wesker", "Germany", "Berlin", "Berlin", "Lisa Park"),
        ("Wayne Enterprises", "Bruce Wayne", "USA", "New Jersey", "Gotham", "David Chen"),
        ("Stark Industries", "Tony Stark", "USA", "California", "Los Angeles", "Sarah Mitchell"),
        ("Wonka Industries", "Willy Wonka", "UK", "London", "London", "Lisa Park"),
        ("Cyberdyne Systems", "Miles Dyson", "USA", "California", "Sunnyvale", "David Chen"),
        ("Hooli Inc", "Gavin Belson", "USA", "California", "Palo Alto", "Sarah Mitchell"),
        ("Pied Piper", "Richard Hendricks", "USA", "California", "Mountain View", "Lisa Park"),
        ("Tyrell Corporation", "Eldon Tyrell", "USA", "California", "Los Angeles", "David Chen"),
        ("Soylent Corp", "William Simonson", "USA", "Illinois", "Chicago", "Sarah Mitchell"),
    ]
    customer_ids = []
    base_date = datetime.now(timezone.utc) - timedelta(days=365)
    for i, (cn, ct, country, state, city, am) in enumerate(customers_data):
        cid = str(uuid.uuid4())
        customer_ids.append(cid)
        created = (base_date + timedelta(days=i * 25)).isoformat()
        await db.customers.insert_one({
            "id": cid,
            "customer_code": f"CUST-{1000+i}",
            "company_name": cn, "customer_name": ct,
            "contact_number": f"+1-555-0{100+i:03d}",
            "email": f"contact@{cn.lower().replace(' ', '').replace(',', '')}.com",
            "address": f"{100+i} Business Park",
            "country": country, "state": state, "city": city,
            "gst_number": f"GST{29+i}ABC{1234+i}D1Z{i%10}",
            "pan_number": f"AAAAA{1000+i}A",
            "support_contact_person": ct, "support_contact_number": f"+1-555-0{200+i:03d}",
            "account_manager": am,
            "status": "Active" if i % 9 != 0 else "Inactive",
            "created_at": created, "updated_at": created,
        })

    # Sample products
    products_data = [
        ("Microsoft Office 365", "2024", "Productivity", "Microsoft", "Premium", "Subscription", "Windows, macOS, Web", "Cloud office suite"),
        ("Adobe Creative Cloud", "2024", "Design", "Adobe", "Standard", "Subscription", "Windows, macOS", "Creative suite"),
        ("Salesforce CRM", "Spring 25", "CRM", "Salesforce", "Premium", "Subscription", "Web", "CRM platform"),
        ("VMware vSphere", "8.0", "Virtualization", "VMware", "Enterprise", "Perpetual", "Linux, Windows", "Virtualization platform"),
        ("AutoCAD", "2025", "CAD", "Autodesk", "Standard", "Subscription", "Windows, macOS", "2D/3D CAD software"),
        ("Slack Business+", "2024", "Communication", "Slack", "Premium", "Subscription", "Web, Mobile", "Team messaging"),
        ("Atlassian Jira", "Cloud", "Project Management", "Atlassian", "Premium", "Subscription", "Web", "Issue tracking"),
        ("AWS Support", "Business", "Cloud", "Amazon", "Enterprise", "Subscription", "Web", "AWS premium support"),
        ("Cisco AnyConnect", "5.0", "Security", "Cisco", "Standard", "Perpetual", "Windows, macOS, Linux", "VPN client"),
        ("Tableau Desktop", "2024.3", "Analytics", "Salesforce", "Standard", "Subscription", "Windows, macOS", "Data visualization"),
    ]
    product_ids = []
    for i, (n, v, cat, ven, st, lm, oc, desc) in enumerate(products_data):
        pid = str(uuid.uuid4())
        product_ids.append(pid)
        await db.products.insert_one({
            "id": pid,
            "product_name": n, "product_version": v, "product_category": cat,
            "vendor": ven, "support_type": st, "license_model": lm,
            "os_compatibility": oc, "description": desc,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # Sample licenses
    import random
    random.seed(42)
    today = datetime.now(timezone.utc).date()
    for i in range(45):
        cid = random.choice(customer_ids)
        pid = random.choice(product_ids)
        # mix of expiry states
        if i % 7 == 0:
            expiry = today - timedelta(days=random.randint(5, 90))  # expired
        elif i % 5 == 0:
            expiry = today + timedelta(days=random.randint(1, 30))  # expiring soon
        elif i % 3 == 0:
            expiry = today + timedelta(days=random.randint(31, 90))
        else:
            expiry = today + timedelta(days=random.randint(91, 720))
        purchase = expiry - timedelta(days=365)
        cost = round(random.uniform(500, 25000), 2)
        await db.licenses.insert_one({
            "id": str(uuid.uuid4()),
            "customer_id": cid, "product_id": pid,
            "license_key": f"XXXX-YYYY-{1000+i}-{random.randint(1000,9999)}",
            "license_type": random.choice(["Subscription", "Perpetual", "Floating"]),
            "license_count": random.choice([1, 5, 10, 25, 50, 100]),
            "subscription_type": random.choice(["Monthly", "Annual", "Multi-Year"]),
            "purchase_date": purchase.isoformat(),
            "activation_date": purchase.isoformat(),
            "expiry_date": expiry.isoformat(),
            "renewal_date": expiry.isoformat(),
            "cost": cost,
            "currency": random.choice(["USD", "EUR", "INR"]),
            "invoice_number": f"INV-{2024}-{2000+i}",
            "po_number": f"PO-{1000+i}",
            "support_expiry": expiry.isoformat(),
            "warranty_expiry": expiry.isoformat(),
            "auto_renewal": random.choice([True, False]),
            "notes": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    logger.info("Sample data seeded successfully.")

# ----------------- Email Alerts -----------------
def render_alert_email(licenses_by_status: Dict[str, list]) -> str:
    rows = []
    for status, items in licenses_by_status.items():
        if not items:
            continue
        color = {"expired": "#dc2626", "30": "#d97706", "60": "#ca8a04", "90": "#0891b2"}.get(status, "#475569")
        label = {"expired": "Expired", "30": "Expiring in 30 days", "60": "Expiring in 60 days", "90": "Expiring in 90 days"}.get(status, status)
        rows.append(f'<h3 style="color:{color};font-family:Arial,sans-serif;margin:24px 0 8px">{label} ({len(items)})</h3>')
        rows.append('<table style="width:100%;border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px"><thead><tr style="background:#f1f5f9"><th style="text-align:left;padding:8px;border:1px solid #e2e8f0">Customer</th><th style="text-align:left;padding:8px;border:1px solid #e2e8f0">Product</th><th style="text-align:left;padding:8px;border:1px solid #e2e8f0">License Key</th><th style="text-align:left;padding:8px;border:1px solid #e2e8f0">Expiry</th></tr></thead><tbody>')
        for l in items[:25]:
            rows.append(f'<tr><td style="padding:8px;border:1px solid #e2e8f0">{l.get("customer_name","")}</td><td style="padding:8px;border:1px solid #e2e8f0">{l.get("product_name","")}</td><td style="padding:8px;border:1px solid #e2e8f0;font-family:monospace;font-size:11px">{l.get("license_key","")}</td><td style="padding:8px;border:1px solid #e2e8f0">{l.get("expiry_date","")}</td></tr>')
        rows.append("</tbody></table>")
    body = "".join(rows) or "<p>No licenses requiring attention.</p>"
    return f"""
    <div style="max-width:680px;margin:0 auto;padding:24px;background:#fff">
      <div style="border-bottom:3px solid #2563eb;padding-bottom:12px;margin-bottom:16px">
        <h1 style="font-family:Arial,sans-serif;color:#0f172a;margin:0">CMPortal Alert Digest</h1>
        <p style="font-family:Arial,sans-serif;color:#64748b;font-size:13px;margin:4px 0 0">{datetime.now(timezone.utc).strftime('%B %d, %Y')}</p>
      </div>
      {body}
      <p style="font-family:Arial,sans-serif;color:#64748b;font-size:11px;margin-top:32px;border-top:1px solid #e2e8f0;padding-top:12px">CMPortal Enterprise — automated license expiry alert.</p>
    </div>
    """

async def send_email_async(recipients: List[str], subject: str, html: str) -> Dict[str, Any]:
    if not RESEND_API_KEY or RESEND_API_KEY.startswith("re_placeholder"):
        return {"sent": False, "reason": "RESEND_API_KEY not configured", "recipients": recipients}
    try:
        params = {"from": SENDER_EMAIL, "to": recipients, "subject": subject, "html": html}
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"sent": True, "id": result.get("id"), "recipients": recipients}
    except Exception as e:
        logger.error(f"Resend send failed: {e}")
        return {"sent": False, "reason": str(e), "recipients": recipients}

async def collect_alert_buckets() -> Dict[str, list]:
    licenses = await db.licenses.find({}, {"_id": 0}).to_list(5000)
    today = datetime.now(timezone.utc).date()
    buckets: Dict[str, list] = {"expired": [], "30": [], "60": [], "90": []}
    for lic in licenses:
        try:
            exp = datetime.fromisoformat(lic["expiry_date"]).date()
        except Exception:
            continue
        days = (exp - today).days
        if days < 0 and days >= -30:
            buckets["expired"].append(await enrich_license(lic))
        elif 0 <= days <= 30:
            buckets["30"].append(await enrich_license(lic))
        elif 31 <= days <= 60:
            buckets["60"].append(await enrich_license(lic))
        elif 61 <= days <= 90:
            buckets["90"].append(await enrich_license(lic))
    return buckets

class TestEmailIn(BaseModel):
    recipient: EmailStr

@api.post("/alerts/test-email")
async def alerts_test_email(payload: TestEmailIn, user: dict = Depends(require_admin)):
    html = render_alert_email({"30": [{"customer_name": "Demo Customer", "product_name": "Demo Product", "license_key": "TEST-1234", "expiry_date": str(datetime.now(timezone.utc).date() + timedelta(days=10))}]})
    res = await send_email_async([payload.recipient], "CMPortal Test Alert", html)
    return res

@api.post("/alerts/run-digest")
async def alerts_run_digest(user: dict = Depends(require_admin)):
    buckets = await collect_alert_buckets()
    total = sum(len(v) for v in buckets.values())
    if total == 0:
        return {"sent": False, "reason": "No alerts to send"}
    recipients_raw = os.environ.get("ALERT_RECIPIENTS", "admin@cmportal.com")
    config = await db.alert_config.find_one({"id": "default"}, {"_id": 0})
    if config and config.get("recipients"):
        recipients = config["recipients"]
    else:
        recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    html = render_alert_email(buckets)
    result = await send_email_async(recipients, f"CMPortal Daily Digest — {total} licenses need attention", html)
    await db.alert_config.update_one(
        {"id": "default"},
        {"$set": {"last_run": datetime.now(timezone.utc).isoformat(), "last_result": result}},
        upsert=True,
    )
    await log_activity(user, "send", "alert-digest", "", f"{total} licenses; sent={result.get('sent')}")
    return {**result, "total": total, "buckets": {k: len(v) for k, v in buckets.items()}}

class AlertConfigIn(BaseModel):
    recipients: List[EmailStr]
    enabled: bool = True
    cadence: Literal["daily", "weekly", "manual"] = "daily"

@api.get("/alerts/config")
async def alerts_get_config(user: dict = Depends(require_admin)):
    cfg = await db.alert_config.find_one({"id": "default"}, {"_id": 0})
    if not cfg:
        cfg = {"id": "default", "recipients": [user["email"]], "enabled": True, "cadence": "daily"}
    cfg["resend_configured"] = bool(RESEND_API_KEY and not RESEND_API_KEY.startswith("re_placeholder"))
    return cfg

@api.put("/alerts/config")
async def alerts_put_config(payload: AlertConfigIn, user: dict = Depends(require_admin)):
    await db.alert_config.update_one(
        {"id": "default"},
        {"$set": {"recipients": payload.recipients, "enabled": payload.enabled, "cadence": payload.cadence, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    await log_activity(user, "update", "alert-config", "default")
    return {"ok": True}

# ----------------- Bulk Import / Update -----------------
def _parse_csv(content: bytes) -> List[Dict[str, str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]

@api.post("/customers/bulk-import")
async def customers_bulk_import(file: UploadFile = File(...), mode: str = Form("upsert"), user: dict = Depends(require_manager)):
    """CSV columns (any subset, must include email or customer_code as identifier):
    company_name, customer_name, contact_number, email, address, country, state, city,
    gst_number, pan_number, support_contact_person, support_contact_number, account_manager, status, customer_code
    """
    content = await file.read()
    rows = _parse_csv(content)
    inserted = updated = skipped = 0
    errors: List[str] = []
    valid_status = {"Active", "Inactive"}
    for idx, r in enumerate(rows, start=2):
        try:
            ident_email = (r.get("email") or "").lower().strip()
            ident_code = (r.get("customer_code") or "").strip()
            if not ident_email and not ident_code:
                errors.append(f"Row {idx}: missing email or customer_code")
                skipped += 1
                continue
            query = {"customer_code": ident_code} if ident_code else {"email": ident_email}
            existing = await db.customers.find_one(query)
            payload = {k: v for k, v in r.items() if k in {
                "company_name", "customer_name", "contact_number", "email", "address",
                "country", "state", "city", "gst_number", "pan_number",
                "support_contact_person", "support_contact_number", "account_manager", "status",
            } and v != ""}
            if "status" in payload and payload["status"] not in valid_status:
                payload["status"] = "Active"
            if "email" in payload:
                payload["email"] = payload["email"].lower()
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            if existing:
                if mode == "insert":
                    skipped += 1
                    continue
                await db.customers.update_one({"id": existing["id"]}, {"$set": payload})
                updated += 1
            else:
                if mode == "update":
                    skipped += 1
                    continue
                if not payload.get("company_name"):
                    errors.append(f"Row {idx}: company_name required for insert")
                    skipped += 1
                    continue
                payload["id"] = str(uuid.uuid4())
                payload["customer_code"] = ident_code or f"CUST-{int(datetime.now().timestamp())}-{idx}"
                payload.setdefault("status", "Active")
                payload["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.customers.insert_one(payload)
                inserted += 1
        except Exception as e:
            errors.append(f"Row {idx}: {e}")
            skipped += 1
    await log_activity(user, "bulk-import", "customers", "", f"+{inserted} ~{updated} skip={skipped}")
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "total": len(rows), "errors": errors[:20]}

@api.post("/licenses/bulk-import")
async def licenses_bulk_import(file: UploadFile = File(...), mode: str = Form("upsert"), user: dict = Depends(require_manager)):
    """CSV columns: license_key (identifier), customer_email or customer_code, product_name,
    license_type, license_count, subscription_type, purchase_date, activation_date,
    expiry_date, renewal_date, cost, currency, invoice_number, po_number, support_expiry,
    warranty_expiry, auto_renewal, notes
    """
    content = await file.read()
    rows = _parse_csv(content)
    inserted = updated = skipped = 0
    errors: List[str] = []
    for idx, r in enumerate(rows, start=2):
        try:
            license_key = (r.get("license_key") or "").strip()
            if not license_key:
                errors.append(f"Row {idx}: license_key required")
                skipped += 1
                continue
            existing = await db.licenses.find_one({"license_key": license_key})
            # resolve customer
            customer_id = existing.get("customer_id") if existing else None
            cust_email = (r.get("customer_email") or "").lower().strip()
            cust_code = (r.get("customer_code") or "").strip()
            if cust_email or cust_code:
                cq = {"customer_code": cust_code} if cust_code else {"email": cust_email}
                cust = await db.customers.find_one(cq)
                if cust:
                    customer_id = cust["id"]
            # resolve product
            product_id = existing.get("product_id") if existing else None
            pname = (r.get("product_name") or "").strip()
            if pname:
                prod = await db.products.find_one({"product_name": pname})
                if prod:
                    product_id = prod["id"]
            payload = {k: v for k, v in r.items() if k in {
                "license_key", "license_type", "subscription_type", "purchase_date",
                "activation_date", "expiry_date", "renewal_date", "currency",
                "invoice_number", "po_number", "support_expiry", "warranty_expiry", "notes",
            } and v != ""}
            if "license_count" in r and r["license_count"]:
                try: payload["license_count"] = int(r["license_count"])
                except Exception: pass
            if "cost" in r and r["cost"]:
                try: payload["cost"] = float(r["cost"])
                except Exception: pass
            if "auto_renewal" in r and r["auto_renewal"] != "":
                payload["auto_renewal"] = r["auto_renewal"].lower() in ("true", "1", "yes", "y")
            if customer_id:
                payload["customer_id"] = customer_id
            if product_id:
                payload["product_id"] = product_id
            if existing:
                if mode == "insert":
                    skipped += 1
                    continue
                await db.licenses.update_one({"id": existing["id"]}, {"$set": payload})
                updated += 1
            else:
                if mode == "update":
                    skipped += 1
                    continue
                if not payload.get("customer_id") or not payload.get("product_id") or not payload.get("expiry_date"):
                    errors.append(f"Row {idx}: customer, product and expiry_date required for insert")
                    skipped += 1
                    continue
                payload["id"] = str(uuid.uuid4())
                payload.setdefault("license_count", 1)
                payload.setdefault("cost", 0.0)
                payload.setdefault("currency", "USD")
                payload.setdefault("license_type", "Subscription")
                payload.setdefault("subscription_type", "Annual")
                payload["created_at"] = datetime.now(timezone.utc).isoformat()
                await db.licenses.insert_one(payload)
                inserted += 1
        except Exception as e:
            errors.append(f"Row {idx}: {e}")
            skipped += 1
    await log_activity(user, "bulk-import", "licenses", "", f"+{inserted} ~{updated} skip={skipped}")
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "total": len(rows), "errors": errors[:20]}

@api.get("/templates/customers.csv")
async def customers_template(user: dict = Depends(get_current_user)):
    headers = "company_name,customer_name,contact_number,email,address,country,state,city,gst_number,pan_number,support_contact_person,support_contact_number,account_manager,status,customer_code\n"
    sample = "Acme Corp,John Doe,+1-555-0001,john@acme.com,100 Main St,USA,CA,SF,GSTXXX,PANXXX,Jane Smith,+1-555-0002,Account Mgr,Active,\n"
    return Response(content=headers + sample, media_type="text/csv")

@api.get("/templates/licenses.csv")
async def licenses_template(user: dict = Depends(get_current_user)):
    headers = "license_key,customer_email,product_name,license_type,license_count,subscription_type,purchase_date,activation_date,expiry_date,renewal_date,cost,currency,invoice_number,po_number,support_expiry,warranty_expiry,auto_renewal,notes\n"
    sample = "ABCD-1234-EFGH-5678,john@acme.com,Microsoft Office 365,Subscription,5,Annual,2025-01-01,2025-01-01,2026-01-01,2026-01-01,1500,USD,INV-001,PO-001,2026-01-01,2026-01-01,true,Renewed annually\n"
    return Response(content=headers + sample, media_type="text/csv")

# ----------------- Dashboard & Custom Report Config -----------------
DEFAULT_DASHBOARD_WIDGETS = ["kpi_customers", "kpi_products", "kpi_active_licenses", "kpi_expiring_30", "kpi_expired", "kpi_revenue", "chart_revenue", "chart_product_pie", "chart_renewals", "chart_vendor", "chart_growth", "critical_expiring", "top_customers"]

@api.get("/dashboard/config")
async def dashboard_get_config(user: dict = Depends(get_current_user)):
    cfg = await db.dashboard_configs.find_one({"user_id": user["id"]}, {"_id": 0})
    if not cfg:
        cfg = {"user_id": user["id"], "widgets": DEFAULT_DASHBOARD_WIDGETS}
    return cfg

class DashboardConfigIn(BaseModel):
    widgets: List[str]

@api.put("/dashboard/config")
async def dashboard_put_config(payload: DashboardConfigIn, user: dict = Depends(get_current_user)):
    await db.dashboard_configs.update_one(
        {"user_id": user["id"]},
        {"$set": {"widgets": payload.widgets, "user_id": user["id"], "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"ok": True}

class CustomReportIn(BaseModel):
    name: str
    entity: Literal["customers", "products", "licenses"]
    columns: List[str]
    filters: Dict[str, Any] = {}

@api.get("/custom-reports")
async def list_custom_reports(user: dict = Depends(get_current_user)):
    return await db.custom_reports.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)

@api.post("/custom-reports")
async def create_custom_report(payload: CustomReportIn, user: dict = Depends(get_current_user)):
    doc = payload.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["user_id"] = user["id"]
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.custom_reports.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.delete("/custom-reports/{rid}")
async def delete_custom_report(rid: str, user: dict = Depends(get_current_user)):
    res = await db.custom_reports.delete_one({"id": rid, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}

@api.post("/custom-reports/run")
async def run_custom_report(payload: CustomReportIn, user: dict = Depends(get_current_user)):
    """Execute an ad-hoc custom report (does not save it)."""
    f = payload.filters or {}
    if payload.entity == "customers":
        q = {}
        if f.get("status") and f["status"] != "all":
            q["status"] = f["status"]
        rows = await db.customers.find(q, {"_id": 0}).to_list(5000)
    elif payload.entity == "products":
        q = {}
        if f.get("vendor") and f["vendor"] != "all":
            q["vendor"] = f["vendor"]
        if f.get("category") and f["category"] != "all":
            q["product_category"] = f["category"]
        rows = await db.products.find(q, {"_id": 0}).to_list(5000)
    else:  # licenses
        rows = await db.licenses.find({}, {"_id": 0}).to_list(5000)
        rows = [await enrich_license(r) for r in rows]
        today = datetime.now(timezone.utc).date()
        if f.get("status") and f["status"] != "all":
            rows = [r for r in rows if r["status"] == f["status"]]
        if f.get("vendor") and f["vendor"] != "all":
            rows = [r for r in rows if r.get("vendor") == f["vendor"]]
        if f.get("category") and f["category"] != "all":
            rows = [r for r in rows if r.get("product_category") == f["category"]]
        if f.get("expiry_from"):
            try:
                start = datetime.fromisoformat(f["expiry_from"]).date()
                rows = [r for r in rows if datetime.fromisoformat(r["expiry_date"]).date() >= start]
            except Exception: pass
        if f.get("expiry_to"):
            try:
                end = datetime.fromisoformat(f["expiry_to"]).date()
                rows = [r for r in rows if datetime.fromisoformat(r["expiry_date"]).date() <= end]
            except Exception: pass
    # project columns
    if payload.columns:
        rows = [{c: r.get(c, "") for c in payload.columns} for r in rows]
    return rows

# ----------------- Renewal History -----------------
@api.get("/licenses/{lid}/history")
async def license_history(lid: str, user: dict = Depends(get_current_user)):
    history = await db.renewal_history.find({"license_id": lid}, {"_id": 0}).sort("timestamp", -1).to_list(200)
    return history

# ----------------- File Attachments -----------------
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "doc", "docx", "xls", "xlsx", "txt", "csv", "ppt", "pptx"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

@api.post("/attachments/upload")
async def upload_attachment(
    file: UploadFile = File(...),
    entity_type: str = Form(...),  # "customer" or "license"
    entity_id: str = Form(...),
    description: str = Form(""),
    user: dict = Depends(require_manager),
):
    if entity_type not in ("customer", "license"):
        raise HTTPException(status_code=400, detail="entity_type must be customer or license")
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type .{ext} not allowed")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
    # validate parent
    coll = db.customers if entity_type == "customer" else db.licenses
    if not await coll.find_one({"id": entity_id}):
        raise HTTPException(status_code=404, detail="Parent record not found")
    file_id = str(uuid.uuid4())
    path = f"{APP_NAME}/attachments/{entity_type}/{entity_id}/{file_id}.{ext}"
    content_type = file.content_type or "application/octet-stream"
    try:
        result = storage_put(path, data, content_type)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")
    doc = {
        "id": file_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "storage_path": result["path"],
        "filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "description": description,
        "uploaded_by": user["email"],
        "uploaded_by_id": user["id"],
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "is_deleted": False,
    }
    await db.attachments.insert_one(doc)
    await log_activity(user, "upload", "attachment", file_id, f"{file.filename} for {entity_type} {entity_id}")
    doc.pop("_id", None)
    return doc

@api.get("/attachments/{file_id}/download")
async def download_attachment(file_id: str, user: dict = Depends(get_current_user)):
    rec = await db.attachments.find_one({"id": file_id, "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data, ct = storage_get(rec["storage_path"])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(status_code=500, detail="Download failed")
    return Response(
        content=data,
        media_type=rec.get("content_type", ct),
        headers={"Content-Disposition": f'inline; filename="{rec["filename"]}"'},
    )

@api.get("/attachments/{entity_type}/{entity_id}")
async def list_attachments(entity_type: str, entity_id: str, user: dict = Depends(get_current_user)):
    rows = await db.attachments.find(
        {"entity_type": entity_type, "entity_id": entity_id, "is_deleted": False},
        {"_id": 0}
    ).sort("uploaded_at", -1).to_list(200)
    return rows

@api.delete("/attachments/{file_id}")
async def delete_attachment(file_id: str, user: dict = Depends(require_manager)):
    res = await db.attachments.update_one(
        {"id": file_id, "is_deleted": False},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc).isoformat(), "deleted_by": user["email"]}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "delete", "attachment", file_id)
    return {"ok": True}

# ----------------- Health -----------------
@api.get("/")
async def root():
    return {"status": "ok", "service": "Customer Management Portal"}

# ----------------- App wiring -----------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    await seed_data()
    init_storage()

@app.on_event("shutdown")
async def on_shutdown():
    client.close()
