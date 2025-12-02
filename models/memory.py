from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MemoryBase(BaseModel):
    main_caption: str = Field(..., min_length=1)
    media_url: Optional[str] = None
    tags: List[str] = []

    # Acessibilidade IA
    alt_text: Optional[str] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None


class MemoryCreate(MemoryBase):
    """
    Modelo de entrada ao criar memória.
    Campos de acessibilidade são opcionais.
    """
    pass


class MemoryPublic(MemoryBase):
    """
    Modelo retornado nas listagens e detalhes.
    """
    id: str
    user_id: str
    created_at: datetime

    class Config:
        orm_mode = True
