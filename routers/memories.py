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
    Request,
)

from core.database import db
from core.security import decode_access_token   # <-- sem indentação indevida
from models.memory import MemoryCreate, MemoryPublic

router = APIRouter()
