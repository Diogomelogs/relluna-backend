import os
import uuid
import requests
from typing import Any, Dict, List

from fastapi import APIRouter, UploadFile, File, Body, HTTPException
from fastapi.responses import JSONResponse
from azure.storage.blob import BlobClient
from openai import AzureOpenAI

router = APIRouter()

# ============================================================
# ENV
# ============================================================

AZURE_STORAGE_URL = os.getenv("AZURE_STORAGE_URL", "").rstrip("/")
AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING", "")

VISION_ENDPOINT = os.getenv("VISION_ENDPOINT", "").rstrip("/")
VISION_KEY = os.getenv("VISION_KEY", "")

OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_DEPLOYMENT = os.getenv("OPENAI_DEPLOYMENT", "")

if not OPENAI_ENDPOINT or not OPENAI_API_KEY or not OPENAI_DEPLOYMENT:
    raise RuntimeError("OPENAI configs não definidas corretamente.")

openai_client = AzureOpenAI(
    azure_endpoint=OPENAI_ENDPOINT,
    api_key=OPENAI_API_KEY,
    api_version="2024-12-01-preview",
)

APP_NAME = "relluna-api"

# ============================================================
# ROOT + HEALTH
# ============================================================

@router.get("/")
async def root():
    return {"message": "Relluna API online", "app": APP_NAME}

@router.get("/health")
async def health():
    return {"status": "ok", "app": APP_NAME}

# ============================================================
# UPLOAD (Blob + Vision)
# ============================================================

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        blob_name = f"{uuid.uuid4()}_{file.filename}"
        container_name = AZURE_STORAGE_URL.split("/")[-1]

        blob = BlobClient.from_connection_string(
            conn_str=AZURE_BLOB_CONNECTION_STRING,
            container_name=container_name,
            blob_name=blob_name,
        )

        data = await file.read()
        blob.upload_blob(data, overwrite=True)
        blob_url = f"{AZURE_STORAGE_URL}/{blob_name}"

        analyze_url = (
            f"{VISION_ENDPOINT}/vision/v3.2/analyze"
            "?visualFeatures=Description,Tags,Faces"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": VISION_KEY,
            "Content-Type": "application/json",
        }
        payload = {"url": blob_url}

        try:
            r = requests.post(analyze_url, headers=headers, json=payload, timeout=20)
            vision_result = r.json() if r.ok else {"error": r.text}
        except Exception as ex:
            vision_result = {"error": str(ex)}

        return JSONResponse({"blob": blob_url, "vision": vision_result})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# ACCESSIBILITY (ALT + SHORT + LONG)
# ============================================================

@router.post("/accessibility")
async def accessibility(payload: Dict[str, Any] = Body(...)):
    """
    ALT TEXT + SHORT DESCRIPTION + LONG DESCRIPTION
    usando Vision + texto do usuário
    """
    try:
        blob_url = payload.get("blob_url")
        vision_result = payload.get("vision_result") or {}
        user_caption = (payload.get("user_caption") or "").strip()

        if not blob_url or not vision_result:
            raise HTTPException(
                status_code=400,
                detail="Campos 'blob_url' e 'vision_result' são obrigatórios.",
            )

        # Vision → caption + tags
        desc = vision_result.get("description") or {}
        captions: List[Dict[str, Any]] = desc.get("captions") or []
        vision_caption = (
            captions[0].get("text") if captions and isinstance(captions[0], dict)
            else "Imagem."
        )

        tags_raw = vision_result.get("tags") or []
        tag_names: List[str] = []
        for t in tags_raw:
            if isinstance(t, dict):
                if t.get("name"):
                    tag_names.append(t["name"])
            else:
                tag_names.append(str(t))

        tags_str = ", ".join(tag_names) if tag_names else "memória pessoal"

        # =======================
        # ALT TEXT (1 frase)
        # =======================
        alt_prompt = (
            "Gere um texto alternativo (alt text) em UMA frase, útil para uma pessoa "
            "com deficiência visual, usando apenas o que o usuário descreveu e o que o Vision detectou.\n\n"
            f"Descrição do usuário: {user_caption or '[vazia]'}\n"
            f"Legenda do Vision: {vision_caption}\n"
            f"Tags: {tags_str}\n"
        )

        alt_resp = openai_client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": alt_prompt}],
            max_tokens=60,
            temperature=0.2,
        )
        alt_msg = alt_resp.choices[0].message
        alt_text = alt_msg.content.strip()

        # =======================
        # SHORT DESCRIPTION (1–2 frases)
        # =======================
        short_prompt = (
            "Descreva a imagem em 1–2 frases, de forma objetiva e acessível.\n"
            "Use apenas o que o usuário disse e o que o Vision detectou. Não invente nada.\n\n"
            f"Descrição do usuário: {user_caption or '[vazia]'}\n"
            f"Legenda do Vision: {vision_caption}\n"
            f"Tags: {tags_str}\n"
        )

        short_resp = openai_client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": short_prompt}],
            max_tokens=80,
            temperature=0.3,
        )
        short_description = short_resp.choices[0].message.content.strip()

        # =======================
        # LONG DESCRIPTION (3–6 frases)
        # =======================
        long_prompt = (
            "Crie uma descrição acessível e detalhada (3–6 frases), "
            "usando APENAS o texto do usuário, a legenda do Vision e as tags detectadas.\n"
            "Não invente nomes, locais ou relações familiares não citadas.\n"
            "Se o usuário mencionou 'mãos do meu avô', você pode repetir exatamente.\n\n"
            f"Descrição do usuário: {user_caption or '[vazia]'}\n"
            f"Legenda do Vision: {vision_caption}\n"
            f"Tags: {tags_str}\n"
        )

        long_resp = openai_client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": long_prompt}],
            max_tokens=220,
            temperature=0.3,
        )
        long_description = long_resp.choices[0].message.content.strip()

        return {
            "alt_text": alt_text,
            "short_description": short_description,
            "long_description": long_description,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
