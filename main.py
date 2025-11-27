from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers.auth import router as auth_router
from routers.memories import router as memories_router

app = FastAPI(title="Relluna API")

origins = [
    "http://localhost:3000",
    "http://192.168.0.181:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# servir arquivos locais da pasta "uploads"
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(memories_router, prefix="/memories", tags=["memories"])
