from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

DB = ROOT / "smartbus.db"
WEB = ROOT / "web"
DETECTIONS = ROOT / "backend" / "detections"

WEB.mkdir(parents=True, exist_ok=True)
DETECTIONS.mkdir(parents=True, exist_ok=True)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="AI Smart Bus",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE
# ============================================================

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():

    c = conn()

    # --------------------------------------------------------
    # Events table
    # --------------------------------------------------------

    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            label TEXT,
            confidence REAL,
            latitude REAL,
            longitude REAL,
            timestamp TEXT,
            metadata TEXT
        )
    """)

    # --------------------------------------------------------
    # Incidents table
    # --------------------------------------------------------

    c.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            photo TEXT,
            latitude REAL,
            longitude REAL,
            time TEXT,
            confidence REAL,
            status TEXT DEFAULT 'Pending',
            bus_id TEXT DEFAULT 'BUS-001'
        )
    """)

    # --------------------------------------------------------
    # Buses table
    # --------------------------------------------------------

    c.execute("""
        CREATE TABLE IF NOT EXISTS buses (
            bus_id TEXT PRIMARY KEY,
            latitude REAL,
            longitude REAL,
            last_seen TEXT,
            status TEXT DEFAULT 'OFFLINE'
        )
    """)

    # --------------------------------------------------------
    # Safe migration for old database
    # --------------------------------------------------------

    cols = {
        row["name"]
        for row in c.execute(
            "PRAGMA table_info(incidents)"
        ).fetchall()
    }

    if "bus_id" not in cols:
        c.execute("""
            ALTER TABLE incidents
            ADD COLUMN bus_id TEXT DEFAULT 'BUS-001'
        """)

    c.commit()
    c.close()


init_db()


# ============================================================
# STATIC DETECTION PHOTOS
# ============================================================

app.mount(
    "/detections",
    StaticFiles(directory=str(DETECTIONS)),
    name="detections"
)


# ============================================================
# INCIDENT APIs
# ============================================================

@app.post("/incidents")
async def create_incident(
    type: str = Form(...),
    photo: Optional[UploadFile] = File(None),

    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),

    lat: Optional[float] = Form(None),
    lon: Optional[float] = Form(None),

    time: Optional[str] = Form(None),
    confidence: Optional[float] = Form(None),

    status: str = Form("Pending"),
    bus_id: str = Form("BUS-001"),
):

    # Support both GPS naming formats
    latitude = latitude if latitude is not None else lat
    longitude = longitude if longitude is not None else lon

    # Generate time if not supplied
    time = time or datetime.now(
        timezone.utc
    ).isoformat()

    photo_path = None

    # --------------------------------------------------------
    # Save detection photo
    # --------------------------------------------------------

    if photo and photo.filename:

        safe_name = Path(photo.filename).name

        filename = (
            f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            f"_{safe_name}"
        )

        save_path = DETECTIONS / filename

        save_path.write_bytes(
            await photo.read()
        )

        photo_path = f"/detections/{filename}"

    # --------------------------------------------------------
    # Save incident
    # --------------------------------------------------------

    c = conn()

    cur = c.execute(
        """
        INSERT INTO incidents
        (
            type,
            photo,
            latitude,
            longitude,
            time,
            confidence,
            status,
            bus_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            type.lower(),
            photo_path,
            latitude,
            longitude,
            time,
            confidence,
            status,
            bus_id
        )
    )

    c.commit()

    incident_id = cur.lastrowid

    c.close()

    return {
        "ok": True,
        "id": incident_id,
        "message": "Incident created successfully",
        "photo": photo_path
    }


@app.get("/incidents")
def get_incidents(
    status: Optional[str] = None,
    type: Optional[str] = None,
    bus_id: Optional[str] = None
):

    c = conn()

    query = """
        SELECT
            id,
            type,
            photo,
            latitude,
            longitude,
            time,
            confidence,
            status,
            bus_id
        FROM incidents
    """

    where = []
    args = []

    if status and status.lower() != "all":

        where.append(
            "LOWER(status)=LOWER(?)"
        )

        args.append(status)

    if type and type.lower() != "all":

        where.append(
            "LOWER(type)=LOWER(?)"
        )

        args.append(type)

    if bus_id and bus_id.lower() != "all":

        where.append(
            "bus_id=?"
        )

        args.append(bus_id)

    if where:

        query += " WHERE " + " AND ".join(where)

    query += " ORDER BY id DESC"

    rows = c.execute(
        query,
        args
    ).fetchall()

    c.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# RESOLVE INCIDENT
# ============================================================

@app.put("/incidents/{incident_id}/resolve")
def resolve_incident(
    incident_id: int
):

    c = conn()

    cur = c.execute(
        """
        UPDATE incidents
        SET status='Resolved'
        WHERE id=?
        """,
        (incident_id,)
    )

    c.commit()
    c.close()

    return {
        "ok": cur.rowcount > 0,
        "message":
            "Incident resolved"
            if cur.rowcount
            else "Incident not found"
    }


# ============================================================
# DELETE INCIDENT
# ============================================================

@app.delete("/incidents/{incident_id}")
def delete_incident(
    incident_id: int
):

    c = conn()

    row = c.execute(
        """
        SELECT photo
        FROM incidents
        WHERE id=?
        """,
        (incident_id,)
    ).fetchone()

    if not row:

        c.close()

        return {
            "ok": False,
            "message": "Incident not found"
        }

    c.execute(
        """
        DELETE FROM incidents
        WHERE id=?
        """,
        (incident_id,)
    )

    c.commit()
    c.close()

    # Delete evidence photo
    if row["photo"]:

        photo_file = (
            DETECTIONS /
            Path(row["photo"]).name
        )

        if photo_file.exists():

            try:
                photo_file.unlink()
            except OSError:
                pass

    return {
        "ok": True,
        "message": "Incident deleted"
    }


# ============================================================
# BUS HEARTBEAT
# ============================================================

@app.post("/api/buses/heartbeat")
def bus_heartbeat(data: dict):

    bus_id = str(
        data.get(
            "bus_id",
            "BUS-001"
        )
    )

    latitude = data.get(
        "latitude",
        data.get("lat")
    )

    longitude = data.get(
        "longitude",
        data.get("lon")
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    c = conn()

    c.execute(
        """
        INSERT INTO buses
        (
            bus_id,
            latitude,
            longitude,
            last_seen,
            status
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            'ACTIVE'
        )

        ON CONFLICT(bus_id)
        DO UPDATE SET
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            last_seen=excluded.last_seen,
            status='ACTIVE'
        """,
        (
            bus_id,
            latitude,
            longitude,
            now
        )
    )

    c.commit()
    c.close()

    return {
        "ok": True,
        "bus_id": bus_id,
        "last_seen": now
    }


# ============================================================
# GET BUSES
# ============================================================

@app.get("/api/buses")
def get_buses():

    c = conn()

    rows = c.execute(
        """
        SELECT *
        FROM buses
        ORDER BY bus_id
        """
    ).fetchall()

    now = datetime.now(
        timezone.utc
    )

    result = []

    for row in rows:

        data = dict(row)

        active = False

        if row["last_seen"]:

            try:

                last_seen = datetime.fromisoformat(
                    row["last_seen"].replace(
                        "Z",
                        "+00:00"
                    )
                )

                seconds = (
                    now - last_seen
                ).total_seconds()

                active = seconds <= 30

            except ValueError:

                active = False

        data["status"] = (
            "ACTIVE"
            if active
            else "OFFLINE"
        )

        result.append(data)

    c.close()

    return result


# ============================================================
# DASHBOARD STATISTICS
# ============================================================

@app.get("/api/stats")
def stats():

    c = conn()

    # Total incidents
    total = c.execute(
        """
        SELECT COUNT(*) n
        FROM incidents
        """
    ).fetchone()["n"]

    # Open incidents
    open_count = c.execute(
        """
        SELECT COUNT(*) n
        FROM incidents
        WHERE LOWER(status) != 'resolved'
        """
    ).fetchone()["n"]

    # Today's incidents
    today = datetime.now(
        timezone.utc
    ).date().isoformat()

    today_count = c.execute(
        """
        SELECT COUNT(*) n
        FROM incidents
        WHERE substr(time,1,10)=?
        """,
        (today,)
    ).fetchone()["n"]

    # Detection categories
    counts = {}

    for incident_type in [
        "garbage",
        "pothole",
        "road_damage",
        "laptop",
        "person"
    ]:

        counts[incident_type] = c.execute(
            """
            SELECT COUNT(*) n
            FROM incidents
            WHERE LOWER(type)=?
            """,
            (incident_type,)
        ).fetchone()["n"]

    # Active buses
    active = 0

    bus_rows = c.execute(
        """
        SELECT last_seen
        FROM buses
        """
    ).fetchall()

    now = datetime.now(
        timezone.utc
    )

    for row in bus_rows:

        if not row["last_seen"]:
            continue

        try:

            last_seen = datetime.fromisoformat(
                row["last_seen"].replace(
                    "Z",
                    "+00:00"
                )
            )

            if (
                now - last_seen
            ).total_seconds() <= 30:

                active += 1

        except ValueError:
            pass

    total_buses = len(
        bus_rows
    )

    c.close()

    return {
        "total_incidents": total,
        "open_incidents": open_count,
        "today_incidents": today_count,

        "active_buses": active,
        "total_buses": total_buses,

        **counts
    }


# ============================================================
# REPORTS
# ============================================================

@app.get("/api/reports")
def reports(
    days: int = 7
):

    c = conn()

    rows = c.execute(
        """
        SELECT
            substr(time,1,10) day,
            COUNT(*) total,

            SUM(
                CASE
                    WHEN LOWER(type)='garbage'
                    THEN 1
                    ELSE 0
                END
            ) garbage,

            SUM(
                CASE
                    WHEN LOWER(type)='pothole'
                    THEN 1
                    ELSE 0
                END
            ) pothole,

            SUM(
                CASE
                    WHEN LOWER(type)='road_damage'
                    THEN 1
                    ELSE 0
                END
            ) road_damage,

            SUM(
                CASE
                    WHEN LOWER(type)='laptop'
                    THEN 1
                    ELSE 0
                END
            ) laptop

        FROM incidents

        GROUP BY substr(time,1,10)

        ORDER BY day DESC

        LIMIT ?
        """,
        (days,)
    ).fetchall()

    c.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# OLD EVENTS API
# ============================================================

@app.post("/api/events")
def add_event(
    e: dict
):

    c = conn()

    cur = c.execute(
        """
        INSERT INTO events
        (
            event_type,
            label,
            confidence,
            latitude,
            longitude,
            timestamp,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            e.get("event_type"),
            e.get("label"),
            e.get("confidence"),
            e.get("latitude"),
            e.get("longitude"),
            e.get(
                "timestamp",
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            json.dumps(
                e.get(
                    "metadata",
                    {}
                )
            )
        )
    )

    c.commit()

    event_id = cur.lastrowid

    c.close()

    return {
        "ok": True,
        "id": event_id
    }


@app.get("/api/events")
def get_events(
    limit: int = 100
):

    c = conn()

    rows = c.execute(
        """
        SELECT *
        FROM events
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()

    c.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# FRONTEND
# ============================================================
# IMPORTANT:
# This must be LAST.
#
# It makes:
# /style.css
# /app.js
# /index.html
# /incidents.html
# /reports.html
# /buses.html
# /map.html
# /photo.html
#
# available directly from the browser.
# ============================================================

app.mount(
    "/",
    StaticFiles(
        directory=str(WEB),
        html=True
    ),
    name="frontend"
)