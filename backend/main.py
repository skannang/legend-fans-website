"""
Legend Fans Website - Backend API
v2.0 - Registration (v1.1) + Login / MPIN / Forgot-MPIN

Built on top of the existing v1.1 backend. ALL existing behaviour preserved:
  - CORS locked to the live site
  - Rate limiting, honeypot, age check, input validation
  - fan_id via Postgres sequence (fan_seq)
  - Neon Postgres via DATABASE_URL

ADDED (run migration.sql first):
  - MPIN at signup (optional field; 4-digit, hashed with bcrypt)
  - POST /login           mobile + MPIN -> 30-day session token
  - GET  /me              validate session, return fan
  - POST /logout
  - POST /forgot-mpin/request   mobile -> OTP (5-min)
  - POST /forgot-mpin/reset     mobile + OTP + new MPIN
  - Lockout: 5 wrong MPIN -> 15-min lock

Decisions locked: 4-digit MPIN, mobile+MPIN login, OTP forgot, 5/15 lockout,
30-day session, auto-login after signup.
"""
import os
import re
import time
import secrets
import datetime as dt
from datetime import date
from collections import defaultdict
from threading import Lock
from typing import Optional

import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# ---- App setup ----
app = FastAPI(title="Legend Fans API", version="2.0")

ALLOWED_ORIGINS = [
    "https://skannang.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ---- Auth config ----
DEV_MODE     = os.environ.get("DEV_MODE", "true").lower() == "true"
SESSION_DAYS = 30
OTP_TTL_MIN  = 5
MAX_FAILED   = 5
LOCKOUT_MIN  = 15
WEAK_MPINS   = {"0000","1111","2222","3333","4444","5555","6666","7777","8888",
                "9999","1234","4321","1212","1122","0123"}

# ---- Rate limiting (in-memory, simple) ----
RATE_LIMIT = 5
RATE_WINDOW = 300
_rate_store = defaultdict(list)
_rate_lock = Lock()

def check_rate_limit(ip: str):
    now = time.time()
    with _rate_lock:
        _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
        if len(_rate_store[ip]) >= RATE_LIMIT:
            raise HTTPException(429, "Too many registration attempts. Please wait a few minutes and try again.")
        _rate_store[ip].append(now)

# ---- Database ----
DATABASE_URL = os.environ.get("DATABASE_URL")
def get_db():
    return psycopg2.connect(DATABASE_URL)

# ---- Auth helpers ----
def _now(): return dt.datetime.utcnow()
def _iso(t): return t.replace(microsecond=0).isoformat()

def hash_mpin(m): return bcrypt.hashpw(m.encode(), bcrypt.gensalt()).decode()
def check_mpin(m, h):
    try: return bool(h) and bcrypt.checkpw(m.encode(), h.encode())
    except Exception: return False

def validate_mpin_value(m):
    if not re.fullmatch(r"\d{4}", m or ""):
        raise HTTPException(400, "MPIN must be exactly 4 digits.")
    if m in WEAK_MPINS:
        raise HTTPException(400, "That MPIN is too easy to guess. Choose another.")

def normalize_mobile(raw):
    s = re.sub(r"[^\d+]", "", raw or "")
    if s.startswith("00"): s = "+" + s[2:]
    if not s.startswith("+"): s = "+" + s
    return s

def make_session(cur, fan_id):
    token = secrets.token_urlsafe(32)
    cur.execute("INSERT INTO sessions (token, fan_id, expires_at) VALUES (%s,%s,%s)",
                (token, fan_id, _iso(_now() + dt.timedelta(days=SESSION_DAYS))))
    return token

def fan_public(r):
    return {"fan_id": r["fan_id"], "name": r["name"], "surname": r.get("surname"),
            "city": r.get("city"), "state": r.get("state"), "country": r.get("country")}

def send_otp_sms(mobile, code):
    """TODO: wire MSG91 here for production."""
    print(f"[OTP] {mobile} -> {code}")

# ---- Schemas ----
class FanRegistration(BaseModel):
    name:          str = Field(..., min_length=1, max_length=80)
    surname:       str = Field(..., min_length=1, max_length=80)
    date_of_birth: date
    mobile:        str = Field(..., min_length=8, max_length=15)
    email:         Optional[str] = Field(None, max_length=120)
    street:        str = Field(..., min_length=1, max_length=200)
    area:          Optional[str] = Field(None, max_length=150)
    city:          str = Field(..., min_length=1, max_length=100)
    pincode:       str = Field(..., min_length=1, max_length=12)
    state:         str = Field(..., min_length=1, max_length=100)
    country:       str = Field(..., min_length=2, max_length=2)
    mpin:          Optional[str] = None          # NEW: 4-digit, set at signup
    website:       Optional[str] = None          # honeypot

    @field_validator('mobile')
    @classmethod
    def _mobile(cls, v):
        cleaned = re.sub(r'[\s\-()]', '', v)
        if not re.match(r'^\+?\d{8,15}$', cleaned):
            raise ValueError('Invalid mobile number format')
        return cleaned

    @field_validator('email')
    @classmethod
    def _email(cls, v):
        if v is None or v == '': return None
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError('Invalid email format')
        return v.lower()

    @field_validator('country')
    @classmethod
    def _country(cls, v): return v.upper()

    @field_validator('mpin')
    @classmethod
    def _mpin(cls, v):
        if v in (None, ''): return None
        if not re.fullmatch(r'\d{4}', v): raise ValueError('MPIN must be 4 digits')
        if v in WEAK_MPINS: raise ValueError('MPIN is too easy to guess')
        return v

    @field_validator('name', 'surname', 'city', 'state')
    @classmethod
    def _strip(cls, v): return v.strip() if v else v

class LoginIn(BaseModel):
    mobile: str
    mpin: str

class ForgotRequestIn(BaseModel):
    mobile: str

class ForgotResetIn(BaseModel):
    mobile: str
    otp: str
    new_mpin: str

# ===================================================================
# Routes
# ===================================================================
@app.get("/")
def home():
    return {"status": "Legend Fans API is running", "version": "2.0", "dev_mode": DEV_MODE}

@app.post("/register")
def register_fan(fan: FanRegistration, request: Request):
    # 1. Honeypot
    if fan.website:
        return {"success": True, "message": "Welcome to the Legend family!",
                "fan_id": "LS-000000000", "name": fan.name}
    # 2. Rate limit
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)
    # 3. Age check
    today = date.today()
    age = today.year - fan.date_of_birth.year - (
        (today.month, today.day) < (fan.date_of_birth.month, fan.date_of_birth.day))
    if age < 13: raise HTTPException(400, "You must be at least 13 years old to register.")
    if age > 120: raise HTTPException(400, "Please enter a valid date of birth.")
    # 4. DB insert
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT fan_id FROM fans WHERE mobile = %s", (fan.mobile,))
        existing = cur.fetchone()
        if existing:
            raise HTTPException(409, f"This mobile is already registered (Fan ID: {existing['fan_id']}).")
        cur.execute("SELECT 'LS-' || LPAD(nextval('fan_seq')::text, 9, '0') AS new_id")
        new_fan_id = cur.fetchone()["new_id"]
        mpin_hash = hash_mpin(fan.mpin) if fan.mpin else None
        cur.execute(
            """INSERT INTO fans
                (fan_id, name, surname, date_of_birth, mobile, email,
                 street, area, city, pincode, state, country, mpin_hash, failed_count)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
               RETURNING fan_id, name, surname, city, state, country""",
            (new_fan_id, fan.name, fan.surname, fan.date_of_birth, fan.mobile,
             fan.email, fan.street, fan.area, fan.city, fan.pincode,
             fan.state, fan.country, mpin_hash))
        created = cur.fetchone()
        token = make_session(cur, new_fan_id)          # auto-login (Q4)
        conn.commit()
        return {"success": True, "message": "Welcome to the Legend family!",
                "fan_id": created["fan_id"], "name": created["name"], "token": token}
    except HTTPException:
        if conn: conn.rollback()
        raise
    except Exception as e:
        if conn: conn.rollback()
        print(f"[ERROR] Registration failed: {e}")
        raise HTTPException(500, "Registration could not be completed. Please try again.")
    finally:
        if conn: conn.close()

@app.post("/login")
def login(body: LoginIn):
    mobile = normalize_mobile(body.mobile)
    conn = None
    error = result = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM fans WHERE mobile = %s", (mobile,))
        row = cur.fetchone()
        if not row:
            error = (404, "No account found for this mobile.")
        elif not row.get("mpin_hash"):
            error = (403, "No MPIN set for this account. Use 'Forgot MPIN' to create one.")
        elif row.get("lockout_until") and _now() < dt.datetime.fromisoformat(row["lockout_until"]):
            mins = int((dt.datetime.fromisoformat(row["lockout_until"]) - _now()).total_seconds()//60)+1
            error = (429, f"Too many attempts. Try again in {mins} min.")
        elif check_mpin(body.mpin, row["mpin_hash"]):
            cur.execute("UPDATE fans SET failed_count=0, lockout_until=NULL WHERE fan_id=%s", (row["fan_id"],))
            token = make_session(cur, row["fan_id"])
            result = {"token": token, "fan": fan_public(row)}
        else:
            failed = (row.get("failed_count") or 0) + 1
            if failed >= MAX_FAILED:
                cur.execute("UPDATE fans SET failed_count=0, lockout_until=%s WHERE fan_id=%s",
                            (_iso(_now()+dt.timedelta(minutes=LOCKOUT_MIN)), row["fan_id"]))
                error = (429, f"Too many attempts. Locked for {LOCKOUT_MIN} min.")
            else:
                cur.execute("UPDATE fans SET failed_count=%s WHERE fan_id=%s", (failed, row["fan_id"]))
                error = (401, f"Wrong MPIN. {MAX_FAILED-failed} attempt(s) left.")
        conn.commit()   # commit lockout/session writes BEFORE raising
    except HTTPException:
        raise
    except Exception as e:
        if conn: conn.rollback()
        print(f"[ERROR] Login failed: {e}")
        raise HTTPException(500, "Login could not be completed. Please try again.")
    finally:
        if conn: conn.close()
    if error: raise HTTPException(error[0], error[1])
    return result

@app.get("/me")
def me(authorization: str = Header(None)):
    token = (authorization or "").replace("Bearer ", "").strip()
    if not token: raise HTTPException(401, "Not logged in.")
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM sessions WHERE token = %s", (token,))
        s = cur.fetchone()
        if not s or dt.datetime.fromisoformat(s["expires_at"]) < _now():
            raise HTTPException(401, "Session expired. Please log in again.")
        cur.execute("SELECT * FROM fans WHERE fan_id = %s", (s["fan_id"],))
        row = cur.fetchone()
        return {"fan": fan_public(row)}
    finally:
        if conn: conn.close()

@app.post("/logout")
def logout(authorization: str = Header(None)):
    token = (authorization or "").replace("Bearer ", "").strip()
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE token = %s", (token,))
        conn.commit()
        return {"ok": True}
    finally:
        if conn: conn.close()

@app.post("/forgot-mpin/request")
def forgot_request(body: ForgotRequestIn):
    mobile = normalize_mobile(body.mobile)
    conn = None
    code = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT 1 FROM fans WHERE mobile = %s", (mobile,))
        if not cur.fetchone():
            return {"sent": True}    # don't reveal existence
        code = "123456" if DEV_MODE else f"{secrets.randbelow(1000000):06d}"
        cur.execute("DELETE FROM otps WHERE mobile = %s", (mobile,))
        cur.execute("INSERT INTO otps (mobile, code, expires_at) VALUES (%s,%s,%s)",
                    (mobile, code, _iso(_now()+dt.timedelta(minutes=OTP_TTL_MIN))))
        conn.commit()
    finally:
        if conn: conn.close()
    send_otp_sms(mobile, code)
    resp = {"sent": True}
    if DEV_MODE: resp["dev_otp"] = code
    return resp

@app.post("/forgot-mpin/reset")
def forgot_reset(body: ForgotResetIn):
    mobile = normalize_mobile(body.mobile)
    validate_mpin_value(body.new_mpin)
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM otps WHERE mobile = %s", (mobile,))
        otp = cur.fetchone()
        if not otp or dt.datetime.fromisoformat(otp["expires_at"]) < _now():
            raise HTTPException(400, "OTP expired. Request a new one.")
        if otp["code"] != body.otp.strip():
            raise HTTPException(400, "Incorrect OTP.")
        cur.execute("UPDATE fans SET mpin_hash=%s, failed_count=0, lockout_until=NULL WHERE mobile=%s",
                    (hash_mpin(body.new_mpin), mobile))
        cur.execute("DELETE FROM otps WHERE mobile = %s", (mobile,))
        conn.commit()
        return {"reset": True}
    except HTTPException:
        if conn: conn.rollback()
        raise
    finally:
        if conn: conn.close()
