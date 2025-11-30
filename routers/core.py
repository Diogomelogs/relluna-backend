import os
import uuid
import requests

from fastapi import APIRouter, UploadFile, File, Body, HTTPException
from fastapi.responses import JSONResponse
from openai import AzureOpenAI
from azure.storage.blob import BlobClient

router = APIRouter()

# ============================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================

AZURE_STORAGE_URL = os.getenv("AZURE_STORAGE_URL", "").rstrip("/")
AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING", "")

VISION_ENDPOINT = os.getenv("VISION_ENDPOINT", "").rstrip("/")
VISION_KEY = os.getenv("VISION_KEY", "")

OPENAI_ENDPOINT = os.getenv("OPENAI_ENDPOINT", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_DEPLOYMENT = os.getenv("OPENAI_DEPLOYMENT", "")

if not AZURE_STORAGE_URL:
    raise RuntimeError("AZURE_STORAGE_URL não definido")
if not AZURE_BLOB_CONNECTION_STRING:
    raise RuntimeError("AZURE_BLOB_CONNECTION_STRING não definido")
if not VISION_ENDPOINT or not VISION_KEY:
    raise RuntimeError("VISION_ENDPOINT ou VISION_KEY não definidos")
if not OPENAI_ENDPOINT or not OPENAI_API_KEY or not OPENAI_DEPLOYMENT:
    raise RuntimeError("OPENAI_* não definidos corretamente")


# ============================================================
# CLIENTE AZURE OPENAI (gpt-4o-mini)
# ============================================================

openai_client = AzureOpenAI(
    azure_endpoint=OPENAI_ENDPOINT,   # ex.: https://digop-mil6o1e7-eastus2.cognitiveservices.azure.com/
    api_key=OPENAI_API_KEY,
    api_version="2024-12-01-preview",
)

APP_NAME = "relluna-api"


# ============================================================
# HEALTH + ROOT
# ============================================================

@router.get("/")
async def root():
    return {"message": "Relluna API online", "app": APP_NAME}


@router.get("/health")
async def health():
    return {"status": "ok", "app": APP_NAME}


# ============================================================
# UPLOAD + COMPUTER VISION
# ============================================================

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Envia imagem ao Blob Storage e analisa via Azure Vision.
    """
    try:
        blob_name = f"{uuid.uuid4()}_{file.filename}"

        # Extrair nome do container
        container_url_parts = AZURE_STORAGE_URL.split("/")
        account_url = "/".join(container_url_parts[:3])  # https://rellunastorage.blob.core.windows.net
        container_name = container_url_parts[-1]

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
            if r.ok:
                vision_result = r.json()
            else:
                vision_result = {
                    "error": r.text,
                    "status": r.status_code,
                }
        except Exception as ex:
            vision_result = {"error": str(ex)}

        return JSONResponse({"blob": blob_url, "vision": vision_result})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# NARRATE – GPT-4o-mini
# ============================================================

@router.post("/narrate")
async def narrate(data: dict = Body(...)):
    """
    Gera uma narrativa curta em português a partir de uma lista de tags:
    {
        "tags": ["família", "praia"]
    }
    """
    try:
        tags_list = data.get("tags", [])
        if not isinstance(tags_list, list):
            raise HTTPException(
                status_code=400,
                detail="Campo 'tags' deve ser uma lista de strings."
            )

        tags = ", ".join(tags_list) if tags_list else "memórias pessoais"

        prompt = (
            "Crie uma narrativa curta, emocional e humana em português, inspirada "
            f"pelas seguintes tags: {tags}. "
            "Use no máximo 3 frases."
        )

        response = openai_client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "Você escreve textos curtos, poéticos e emocionais."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=120,
            temperature=0.7,
        )

        text = response.choices[0].message["content"]
        return {"narrative": text.strip()}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
