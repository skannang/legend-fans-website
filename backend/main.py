"""
Legend Fans Website - Backend API
First slice: Register a fan
"""
import os
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="Legend Fans API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL)


class FanRegistration(BaseModel):
    name: str
    surname: Optional[str] = None
    date_of_birth: Optional[date] = None
    mobile: str
    email: Optional[str] = None
    street: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


@app.get("/")
def home():
    return {"status": "Legend Fans API is running", "version": "1.0"}


@app.post("/register")
def register_fan(fan: FanRegistration):
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT fan_id FROM fans WHERE mobile = %s", (fan.mobile,))
        existing = cur.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"This mobile is already registered as {existing['fan_id']}"
            )

        cur.execute("SELECT 'LS-' || LPAD(nextval('fan_seq')::text, 9, '0') AS new_id")
        new_fan_id = cur.fetchone()["new_id"]

        cur.execute(
            """
            INSERT INTO fans
                (fan_id, name, surname, date_of_birth, mobile, email,
                 street, area, city, pincode, state, country)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING fan_id, name, surname, city, country
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
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()
