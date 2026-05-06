"""
Customer Management Portal - FastAPI Backend
"""
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
import secrets
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# ----------------- Setup -----------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]

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
    res = await db.licenses.update_one({"id": lid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await log_activity(user, "update", "license", lid)
    return {"ok": True}

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

@app.on_event("shutdown")
async def on_shutdown():
    client.close()
