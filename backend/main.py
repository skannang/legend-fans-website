"""
Legend Fans Website - Backend API
v1.1 - Production-hardened registration

Security upgrades:
- CORS locked to the live website only
- Rate limiting (5 registrations per IP per 5 minutes)
- Honeypot field check (catches bots)
- Stronger input validation
- No sensitive info leaked in error messages
"""
import os
import re
import time
from datetime import date
from collections import defaultdict
from threading import Lock
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

# ---- App setup ----
app = FastAPI(title="Legend Fans API", version="1.1")

# CORS — only allow YOUR website to call this API
ALLOWED_ORIGINS = [
    "https://skannang.github.io",
    "http://localhost:8000",      # for local testing
    "http://127.0.0.1:5500",      # VS Code Live Server local
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ---- Rate limiting (in-memory, simple) ----
RATE_LIMIT = 5            # max 5 registrations
RATE_WINDOW = 300         # per 5 minutes (300 seconds)
_rate_store = defaultdict(list)
_rate_lock = Lock()

def check_rate_limit(ip: str):
    now = time.time()
    with _rate_lock:
        # remove old entries
        _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
        if len(_rate_store[ip]) >= RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Too many registration attempts. Please wait a few minutes and try again."
            )
        _rate_store[ip].append(now)


# ---- Database ----
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)


# ---- Request schema with validation ----
class FanRegistration(BaseModel):
    name:          str  = Field(..., min_length=1, max_length=80)
    surname:       str  = Field(..., min_length=1, max_length=80)
    date_of_birth: date
    mobile:        str  = Field(..., min_length=8, max_length=15)
    email:         Optional[str] = Field(None, max_length=120)
    street:        str  = Field(..., min_length=1, max_length=200)
    area:          Optional[str] = Field(None, max_length=150)
    city:          str  = Field(..., min_length=1, max_length=100)
    pincode:       str  = Field(..., min_length=1, max_length=12)
    state:         str  = Field(..., min_length=1, max_length=100)
    country:       str  = Field(..., min_length=2, max_length=2)
    website:       Optional[str] = None    # honeypot field

    @field_validator('mobile')
    @classmethod
    def validate_mobile(cls, v):
        cleaned = re.sub(r'[\s\-()]', '', v)
        if not re.match(r'^\+?\d{8,15}$', cleaned):
            raise ValueError('Invalid mobile number format')
        return cleaned

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v is None or v == '':
            return None
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError('Invalid email format')
        return v.lower()

    @field_validator('country')
    @classmethod
    def validate_country(cls, v):
        return v.upper()

    @field_validator('name', 'surname', 'city', 'state')
    @classmethod
    def strip_text(cls, v):
        return v.strip() if v else v


# ---- Endpoints ----
@app.get("/")
def home():
    return {"status": "Legend Fans API is running", "version": "1.1"}


@app.post("/register")
def register_fan(fan: FanRegistration, request: Request):
    # 1. Honeypot check — real users never fill this
    if fan.website:
        # Silently pretend success to confuse bots
        return {
            "success": True,
            "message": "Welcome to the Legend family!",
            "fan_id": "LS-000000000",
            "name": fan.name,
        }

    # 2. Rate limit by client IP
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    # 3. Age sanity check
    today = date.today()
    age = today.year - fan.date_of_birth.year - (
        (today.month, today.day) < (fan.date_of_birth.month, fan.date_of_birth.day)
    )
    if age < 13:
        raise HTTPException(status_code=400, detail="You must be at least 13 years old to register.")
    if age > 120:
        raise HTTPException(status_code=400, detail="Please enter a valid date of birth.")

    # 4. Database insert
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check duplicate mobile
        cur.execute("SELECT fan_id FROM fans WHERE mobile = %s", (fan.mobile,))
        existing = cur.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"This mobile is already registered (Fan ID: {existing['fan_id']})."
            )

        # Generate next fan ID
        cur.execute("SELECT 'LS-' || LPAD(nextval('fan_seq')::text, 9, '0') AS new_id")
        new_fan_id = cur.fetchone()["new_id"]

        # Insert
        cur.execute(
            """
            INSERT INTO fans
                (fan_id, name, surname, date_of_birth, mobile, email,
                 street, area, city, pincode, state, country)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING fan_id, name
            """,
            (new_fan_id, fan.name, fan.surname, fan.date_of_birth, fan.mobile,
             fan.email, fan.street, fan.area, fan.city, fan.pincode,
             fan.state, fan.country)
        )
        created = cur.fetchone()
        conn.commit()

        return {
            "success": True,
            "message": "Welcome to the Legend family!",
            "fan_id": created["fan_id"],
            "name": created["name"],
        }

    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
        # Never leak internal error details to public
        print(f"[ERROR] Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration could not be completed. Please try again.")
    finally:
        if conn:
            conn.close()
