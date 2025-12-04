import os
import shutil
from uuid import uuid4
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import requests
import numpy as np
from fastapi import HTTPException
from moviepy.editor import ImageClip, CompositeVideoClip

from PIL import Image as PILImage, ImageDraw, ImageFont

# ----------------------------------------------------------------------
# Compatibilidade Pillow >= 10 (ANTIALIAS removido)
# ----------------------------------------------------------------------
if not hasattr(PILImage, "ANTIALIAS"):
    # Redireciona para LANCZOS
    PILImage.ANTIALIAS = PILImage.Resampling.LANCZOS  # type: ignore[attr-defined]

# ----------------------------------------------------------------------
# Parâmetros de vídeo (formato stories)
# ----------------------------------------------------------------------
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 24
DURATION = 10  # segundos

RELUMINATION_OUTPUT_DIR = os.path.join("media", "reluminations")
os.makedirs(RELUMINATION_OUTPUT_DIR, exist_ok=True)


def _resolve_local_source_path(url: str) -> str | None:
    """
    Se a URL aponta para um arquivo local (uploads/...), resolve o caminho
    no sistema de arquivos. Caso contrário, retorna None.
    """
    parsed = urlparse(url)

    # Caso 1: caminho relativo (/uploads/... ou uploads/...)
    if not parsed.scheme and not parsed.netloc:
        path = url.lstrip("/")  # remove / inicial se existir
        return os.path.join(".", path)

    # Caso 2: http://localhost:8000/uploads/... ou 127.0.0.1
    if parsed.scheme in ("http", "https") and parsed.netloc in (
        "localhost:8000",
        "127.0.0.1:8000",
    ):
        path = parsed.path.lstrip("/")  # ex: "uploads/arquivo.jpg"
        return os.path.join(".", path)

    # Outros hosts (Azure Blob etc.) não são locais
    return None


def download_image_to_local(url: str) -> str:
    """
    Garante que a imagem esteja em media/reluminations e retorna o caminho local.

    - Se a URL for local (uploads/...), copia o arquivo do disco.
    - Se for remota (ex.: Azure Blob), faz download via HTTP.
    """
    # Tentar resolver como arquivo local primeiro
    local_source = _resolve_local_source_path(url)

    if local_source is not None:
        if not os.path.exists(local_source):
            raise HTTPException(
                status_code=400,
                detail="Arquivo de imagem local não encontrado para esta memória.",
            )

        filename = f"{uuid4().hex}.jpg"
        dest_path = os.path.join(RELUMINATION_OUTPUT_DIR, filename)
        shutil.copyfile(local_source, dest_path)
        return dest_path

    # Se não for local, tratar como URL remota
    try:
        resp = requests.get(url, timeout=20)
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Tempo excedido ao tentar baixar a imagem remota.",
        )

    if not resp.ok:
        raise HTTPException(
            status_code=502,
            detail="Falha ao baixar imagem de origem (remota).",
        )

    filename = f"{uuid4().hex}.jpg"
    dest_path = os.path.join(RELUMINATION_OUTPUT_DIR, filename)

    with open(dest_path, "wb") as f:
        f.write(resp.content)

    return dest_path


def _create_text_image(
    text: str,
    max_width: int,
    padding: int = 20,
) -> PILImage.Image:
    """
    Cria uma imagem RGBA com fundo semi-transparente e texto centralizado,
    usando Pillow (sem ImageMagick).
    """
    # Tentar Arial; se não existir, usa fonte padrão
    try:
        font = ImageFont.truetype("arial.ttf", 50)
    except Exception:
        font = ImageFont.load_default()

    # Quebra de linha simples
    import textwrap

    lines = textwrap.wrap(text, width=40)
    dummy_img = PILImage.new("RGBA", (max_width, 10), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy_img)

    line_heights = []
    max_line_width = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_heights.append(h)
        max_line_width = max(max_line_width, w)

    total_height = sum(line_heights) + padding * 2 + (len(lines) - 1) * 8
    img = PILImage.new(
        "RGBA",
        (max_width, total_height),
        (0, 0, 0, 0),
    )
    draw = ImageDraw.Draw(img)

    # Fundo semi-transparente
    bg_rect = [0, 0, max_width, total_height]
    draw.rectangle(bg_rect, fill=(0, 0, 0, 150))

    # Desenha texto centralizado
    y = padding
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (max_width - w) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += h + 8

    return img


def generate_relumination_style1(image_url: str, narrative: str, title: str) -> str:
    """
    Gera vídeo vertical ~10s com zoom suave + texto no terço inferior.
    Retorna caminho local do MP4 gerado.
    """
    local_img = download_image_to_local(image_url)

    # Imagem base em 1080x1920 com duração ajustada
    base_clip = ImageClip(local_img)
    base_clip = base_clip.resize(height=VIDEO_HEIGHT)
    base_clip = base_clip.crop(
        x_center=base_clip.w / 2,
        y_center=base_clip.h / 2,
        width=VIDEO_WIDTH,
        height=VIDEO_HEIGHT,
    )
    base_clip = base_clip.set_duration(DURATION)

    # Zoom leve ao longo do tempo (1.0 -> 1.08)
    def zoom(t):
        factor = 1.0 + 0.08 * (t / DURATION)
        return factor

    zoom_clip = base_clip.resize(zoom)

    # Texto
    text_content = (narrative or "").strip()
    if len(text_content) > 260:
        text_content = text_content[:257] + "..."

    if not text_content:
        text_content = "Um momento especial."

    # Cria imagem de texto via Pillow
    text_img = _create_text_image(
        text_content,
        max_width=VIDEO_WIDTH - 200,
        padding=20,
    )
    text_arr = np.array(text_img)

    text_clip = (
        ImageClip(text_arr)
        .set_duration(DURATION)
        .set_position(("center", VIDEO_HEIGHT - 400))
    )

    final = CompositeVideoClip(
        [zoom_clip, text_clip],
        size=(VIDEO_WIDTH, VIDEO_HEIGHT),
    )

    out_filename = f"{uuid4().hex}_style1.mp4"
    out_path = os.path.join(RELUMINATION_OUTPUT_DIR, out_filename)

    final.write_videofile(
        out_path,
        fps=FPS,
        codec="libx264",
        audio=False,
        verbose=False,
        logger=None,
    )

    return out_path


# ----------------------------------------------------------------------
# Limites de uso do beta / créditos de Reluminação
# ----------------------------------------------------------------------
BETA_MONTHLY_LIMIT = 10


async def check_and_consume_relumination_quota(
    user_doc: dict[str, Any],
    db,
) -> None:
    """
    Aplica regras de cota/créditos de Reluminação.

    Regras MVP:
      - Se relumination_credits > 0: consome 1 crédito.
      - Senão, aplica limite mensal BETA_MONTHLY_LIMIT para plano beta_free.
    """
    now_ref = datetime.utcnow().strftime("%Y-%m")
    month_ref = user_doc.get("relumination_month_ref")
    used = user_doc.get("relumination_used_this_month", 0)
    credits = user_doc.get("relumination_credits", 0)
    plan = user_doc.get("plan_tier", "beta_free")

    user_id = user_doc["_id"]

    # Reset mensal
    if month_ref != now_ref:
        used = 0
        await db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "relumination_month_ref": now_ref,
                    "relumination_used_this_month": 0,
                }
            },
        )

    # Créditos pagos
    if credits > 0:
        await db.users.update_one(
            {"_id": user_id},
            {"$inc": {"relumination_credits": -1}},
        )
        return

    # Plano beta_free com limite mensal
    if plan == "beta_free":
        if used >= BETA_MONTHLY_LIMIT:
            raise HTTPException(
                status_code=402,
                detail="Limite de Reluminações do plano beta grátis atingido neste mês.",
            )

        await db.users.update_one(
            {"_id": user_id},
            {
                "$inc": {"relumination_used_this_month": 1},
                "$set": {"relumination_month_ref": now_ref},
            },
        )
        return

    # Futuro: planos com regras específicas (plus/pro etc.)
