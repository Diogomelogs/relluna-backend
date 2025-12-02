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
from models.memory import MemoryCreate, MemoryPublic

router = APIRouter()


def get_current_user_id(authorization: str = Header(...)) -> str:
    """
    Espera header: Authorization: Bearer <token>
    Retorna o user_id (sub) decodificado do JWT.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente ou inválido.",
        )

    token = authorization.split(" ", 1)[1]

    try:
        user_id = decode_access_token(token)
        return user_id
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        )


@router.post("/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """
    Recebe um arquivo (imagem/vídeo), salva em disco na pasta 'uploads'
    e retorna a URL pública local (http://localhost:8000/uploads/...).
    """
    os.makedirs("uploads", exist_ok=True)

    safe_name = file.filename.replace(" ", "_")
    filename = f"{user_id}_{int(datetime.utcnow().timestamp())}_{safe_name}"
    filepath = os.path.join("uploads", filename)

    try:
        contents = await file.read()
        with open(filepath, "wb") as f:
            f.write(contents)

        media_url = f"http://localhost:8000/uploads/{filename}"
        return {"media_url": media_url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar arquivo: {e}",
        )


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
    )


@router.post("/", response_model=MemoryPublic, status_code=status.HTTP_201_CREATED)
async def create_memory(
    memory_in: MemoryCreate,
    user_id: str = Depends(get_current_user_id),
):
    """
    Cria uma memória ligada ao usuário autenticado.
    Pode receber ou não uma media_url (vinda do /core/upload ou /memories/upload-file).
    Inclui campos de acessibilidade IA se fornecidos.
    """
    doc = {
        "user_id": ObjectId(user_id),
        "main_caption": memory_in.main_caption,
        "media_url": memory_in.media_url,
        "tags": memory_in.tags or [],
        "alt_text": memory_in.alt_text,
        "short_description": memory_in.short_description,
        "long_description": memory_in.long_description,
        "created_at": datetime.utcnow(),
    }
    result = await db.timeline_items.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_memory(doc)


@router.get("/", response_model=List[MemoryPublic])
async def list_memories(
    user_id: str = Depends(get_current_user_id),
):
    """
    Lista memórias do usuário autenticado em ordem decrescente de criação.
    Inclui campos de acessibilidade IA.
    """
    cursor = db.timeline_items.find({"user_id": ObjectId(user_id)}).sort(
        "created_at", -1
    )
    items: List[MemoryPublic] = []
    async for doc in cursor:
        items.append(_doc_to_memory(doc))
    return items


@router.get("/{memory_id}", response_model=MemoryPublic)
async def get_memory(
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Detalhe de uma memória específica do usuário autenticado.
    Inclui campos de acessibilidade IA.
    """
    try:
        oid = ObjectId(memory_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="ID inválido."
        )

    doc = await db.timeline_items.find_one({"_id": oid, "user_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memória não encontrada."
        )
    return _doc_to_memory(doc)
