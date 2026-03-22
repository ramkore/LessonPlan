"""FastAPI application initialization."""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add project root to sys.path so 'import src.xxx' works
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.core.database import create_db_and_tables, run_migrations  # noqa: E402

# Import all models so SQLModel registers them before create_all
import backend.models.user  # noqa: E402, F401
import backend.models.calendar  # noqa: E402, F401
import backend.models.holiday  # noqa: E402, F401
import backend.models.timetable  # noqa: E402, F401
import backend.models.subject  # noqa: E402, F401
import backend.models.lesson_plan  # noqa: E402, F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    run_migrations()
    yield


app = FastAPI(title="Lesson Plan Generator API", version="1.0.0", lifespan=lifespan)

import os  # noqa: E402

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from backend.api.auth import router as auth_router  # noqa: E402
from backend.api.calendar import router as calendar_router  # noqa: E402
from backend.api.holidays import router as holidays_router  # noqa: E402
from backend.api.timetable import router as timetable_router  # noqa: E402
from backend.api.syllabus import router as syllabus_router  # noqa: E402
from backend.api.generate import router as generate_router  # noqa: E402

app.include_router(auth_router)
app.include_router(calendar_router)
app.include_router(holidays_router)
app.include_router(timetable_router)
app.include_router(syllabus_router)
app.include_router(generate_router)


@app.get("/")
def root():
    return {"message": "Lesson Plan Generator API", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "ok"}
