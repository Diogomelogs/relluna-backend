from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    main_caption: str = Field(..., min_length=1, max_length=500)
    media_url: Optional[str] = None  # por enquanto texto; depois ligamos Blob
    tags: List[str] = []
    source: Optional[str] = "web"


class MemoryPublic(BaseModel):
    id: str
    user_id: str
    main_caption: str
    media_url: Optional[str] = None
    tags: List[str]
    created_at: datetime
