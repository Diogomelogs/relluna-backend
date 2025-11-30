import os
import uuid
import requests

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
# HEALTH & ROOT
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

        # pegar container
        container_name = AZURE_STORAGE_URL.split("/")[-1]

        blob = BlobClient.from_connection_string(
            conn_str=AZURE_BLOB_CONNECTION_STRING,
            container_name=container_name,
            blob_name=blob_name,
        )

        data = await file.read()
        blob.upload_blob(data, overwrite=True)

        blob_url = f"{AZURE_STORAGE_URL}/{blob_name}"

        # vision
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
                vision_result = {"error": r.text, "status": r.status_code}
        except Exception as ex:
            vision_result = {"error": str(ex)}

        return JSONResponse({"blob": blob_url, "vision": vision_result})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# NARRATE (GPT-4o-mini)
# ============================================================

@router.post("/narrate")
async def narrate(data: dict = Body(...)):
    try:
        tags_list = data.get("tags", [])
        if not isinstance(tags_list, list):
            raise HTTPException(
                status_code=400,
                detail="Campo 'tags' deve ser uma lista de strings.",
            )

        tags = ", ".join(tags_list) if tags_list else "memórias pessoais"

        prompt = (
            "Você é a inteligência narrativa da Relluna. "
            "Você recebe palavras‑chave e pistas sobre uma foto, como tags visuais, ano aproximado, tipo de lugar e clima. "
            f"As palavras‑chave desta imagem são: {tags}. "
            "Escreva uma descrição contextualizada em português, com 3 a 6 frases, "
            "que ajude a lembrar do tipo de momento retratado (ambiente, clima, tipo de relação, ocasião), "
            "mas sem inventar nomes próprios, graus de parentesco específicos "
            "(como avô, tia) ou detalhes concretos que não estejam claramente implícitos nas palavras‑chave. "
            "Use expressões genéricas como 'uma pessoa', 'uma família', 'um grupo', 'um momento especial', "
            "e foque em como a cena poderia ser sentida e lembrada, não em criar uma história fictícia."
        )

        response = openai_client.chat.completions.create(
            model=OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=90,
            temperature=0.7,
        )

        message = response.choices[0].message
        text = message.content if hasattr(message, "content") else str(message)
        return {"narrative": text.strip()}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
