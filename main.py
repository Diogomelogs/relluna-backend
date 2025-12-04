from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers.auth import router as auth_router
from routers.memories import router as memories_router
from routers.core import router as core_router

app = FastAPI(
    title="Relluna API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# -----------------------------
# CORS
# -----------------------------
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.0.181:3000",
    "https://relluna.me",
    "https://www.relluna.me",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# STATIC FILES
# -----------------------------
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/media", StaticFiles(directory="media"), name="media")

# -----------------------------
# ROUTERS
# -----------------------------
app.include_router(core_router, prefix="", tags=["core"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(memories_router, prefix="/memories", tags=["memories"])
