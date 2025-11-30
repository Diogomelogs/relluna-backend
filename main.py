from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers.auth import router as auth_router
from routers.memories import router as memories_router
from routers.core import router as core_router


# ============================================================
# CONFIGURAÇÃO FASTAPI
# ============================================================

app = FastAPI(
    title="Relluna API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ============================================================
# CORS – Permissões para o Frontend
# ============================================================

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.0.181:3000",
    "https://relluna.me",
    "https://www.relluna.me",
    # "https://SEU_PROJECTO.vercel.app",  # adicione quando publicar no Vercel
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# SERVIR ARQUIVOS ESTÁTICOS (APENAS SE EXISTIR "uploads/")
# ============================================================

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ============================================================
# REGISTRO DOS ROUTERS
# ============================================================

# Núcleo: /, /health, /upload, /narrate
app.include_router(core_router, prefix="", tags=["core"])

# Autenticação
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# Memórias
app.include_router(memories_router, prefix="/memories", tags=["memories"])
