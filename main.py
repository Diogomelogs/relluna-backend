from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers.auth import router as auth_router
from routers.memories import router as memories_router

app = FastAPI(
    title="Relluna API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Origens permitidas para o frontend (dev + produção)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.0.181:3000",
    "https://relluna.me",
    "https://www.relluna.me",
    # se o front estiver no Vercel, adicione aqui
    # "https://SEU-PROJETO.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # em DEV, se precisar, pode trocar por ["*"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos locais da pasta "uploads" (apenas se existir no App Service)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": "relluna-api",
        "message": "Relluna API online",
    }


# Rotas de autenticação e memórias
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(memories_router, prefix="/memories", tags=["memories"])
