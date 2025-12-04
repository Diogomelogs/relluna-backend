from datetime import datetime
import os
from typing import List

from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status,
    UploadFile,
    File,
)

from core.database import db
from core.security import decode_access_token
from core.reluminations import (
    generate_relumination_style1,
    check_and_consume_relumination_quota,
)

from models.memory import MemoryCreate, MemoryPublic

router = APIRouter()

API_BASE = "http://localhost:8000"  # usado para URLs absolutas no retorno


# -----------------------------
# AUTH HELPERS
# -----------------------------
def get_current_user_id(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente ou inválido.",
        )
    token = authorization.split(" ", 1)[1]
    try:
        return decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        )


# -----------------------------
# UPLOAD LOCAL
# -----------------------------
@router.post("/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    os.makedirs("uploads", exist_ok=True)

    safe_name = file.filename.replace(" ", "_")
    filename = f"{user_id}_{int(datetime.utcnow().timestamp())}_{safe_name}"
    filepath = os.path.join("uploads", filename)

    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    media_url = f"{API_BASE}/uploads/{filename}"

    return {"media_url": media_url}


# -----------------------------
# HELPERS
# -----------------------------
def _doc_to_memory(doc) -> MemoryPublic:
    return MemoryPublic(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        main_caption=doc.get("main_caption", ""),
        media_url=doc.get("media_url"),
        tags=doc.get("tags", []),
        alt_text=doc.get("alt_text"),
        short_description=doc.get("short_description"),
        long_description=doc.get("long_description"),
        created_at=doc["created_at"],
        relumination_url=doc.get("relumination_url"),
        relumination_style=doc.get("relumination_style"),
    )


# -----------------------------
# CRUD MEMÓRIAS
# -----------------------------
@router.post("/", response_model=MemoryPublic, status_code=201)
async def create_memory(
    memory_in: MemoryCreate,
    user_id: str = Depends(get_current_user_id),
):
    doc = {
        "user_id": ObjectId(user_id),
        "main_caption": memory_in.main_caption,
        "media_url": memory_in.media_url,
        "tags": memory_in.tags or [],
        "alt_text": memory_in.alt_text,
        "short_description": memory_in.short_description,
        "long_description": memory_in.long_description,
        "created_at": datetime.utcnow(),
        "relumination_url": None,
        "relumination_style": None,
    }

    result = await db.timeline_items.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_memory(doc)


@router.get("/", response_model=List[MemoryPublic])
async def list_memories(user_id: str = Depends(get_current_user_id)):
    cursor = db.timeline_items.find(
        {"user_id": ObjectId(user_id)}
    ).sort("created_at", -1)

    results = []
    async for doc in cursor:
        results.append(_doc_to_memory(doc))
    return results


@router.get("/{memory_id}", response_model=MemoryPublic)
async def get_memory(memory_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        oid = ObjectId(memory_id)
    except:
        raise HTTPException(400, "ID inválido.")

    doc = await db.timeline_items.find_one(
        {"_id": oid, "user_id": ObjectId(user_id)}
    )
    if not doc:
        raise HTTPException(404, "Memória não encontrada.")

    return _doc_to_memory(doc)


# -----------------------------
# RELUMINAÇÃO
# -----------------------------
@router.post(
    "/{memory_id}/relumination",
    status_code=201,
    summary="Criar Reluminação Style 1",
)
async def create_relumination_for_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
):
    # buscar memória
    try:
        oid = ObjectId(memory_id)
    except:
        raise HTTPException(400, "ID inválido.")

    mem = await db.timeline_items.find_one(
        {"_id": oid, "user_id": ObjectId(user_id)}
    )
    if not mem:
        raise HTTPException(404, "Memória não encontrada.")

    # buscar usuário completo
    user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user_doc:
        raise HTTPException(401, "Usuário não encontrado.")

    # 1 por memória no beta_free
    if (
        mem.get("relumination_url")
        and user_doc.get("plan_tier", "beta_free") == "beta_free"
        and user_doc.get("relumination_credits", 0) <= 0
    ):
        raise HTTPException(409, "Esta memória já possui uma Reluminação.")

    # cota/créditos
    await check_and_consume_relumination_quota(user_doc, db)

    # coleta dados
    media_url = mem.get("media_url")
    if not media_url:
        raise HTTPException(400, "Memória sem mídia.")

    narrative = (
        mem.get("short_description")
        or mem.get("long_description")
        or mem.get("alt_text")
        or ""
    )

    title = mem.get("main_caption") or "Um momento especial"

    # gerar vídeo
    video_path = generate_relumination_style1(media_url, narrative, title)
    filename = os.path.basename(video_path)

    # importante → sempre URL absoluta
    public_url = f"{API_BASE}/media/reluminations/{filename}"

    await db.timeline_items.update_one(
        {"_id": mem["_id"]},
        {
            "$set": {
                "relumination_url": public_url,
                "relumination_style": 1,
            }
        },
    )

    return {"relumination_url": public_url, "style": 1}
