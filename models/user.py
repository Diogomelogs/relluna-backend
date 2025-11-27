from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserInDB(UserBase):
    id: str
    hashed_password: str
    created_at: datetime


class UserPublic(UserBase):
    id: str
