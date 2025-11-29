from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pymongo.errors import ServerSelectionTimeoutError

from core.database import db
from core.security import get_password_hash, verify_password, create_access_token
from models.user import UserCreate, UserPublic, UserInDB
from models.auth import LoginData, Token

router = APIRouter()


def _user_doc_to_in_db(doc) -> UserInDB:
    return UserInDB(
        id=str(doc["_id"]),
        name=doc["name"],
        email=doc["email"],
        hashed_password=doc["hashed_password"],
        created_at=doc["created_at"],
    )


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate):
    email = user_in.email.lower()

    try:
        existing = await db.users.find_one({"email": email})
    except ServerSelectionTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falha ao conectar ao banco de dados. Verifique a conexão com o MongoDB Atlas.",
        )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail já cadastrado.",
        )

    hashed_password = get_password_hash(user_in.password)
    now = datetime.utcnow()

    doc = {
        "name": user_in.name,
        "email": email,
        "hashed_password": hashed_password,
        "created_at": now,
    }

    try:
        result = await db.users.insert_one(doc)
    except ServerSelectionTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falha ao conectar ao banco de dados. Verifique a conexão com o MongoDB Atlas.",
        )

    return UserPublic(
        id=str(result.inserted_id),
        name=user_in.name,
        email=email,
    )


@router.post("/login", response_model=Token)
async def login(data: LoginData):
    email = data.email.lower()

    try:
        doc = await db.users.find_one({"email": email})
    except ServerSelectionTimeoutError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Falha ao conectar ao banco de dados. Verifique a conexão com o MongoDB Atlas.",
        )

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    user = _user_doc_to_in_db(doc)

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    access_token = create_access_token({"sub": user.id})
    return Token(access_token=access_token)
