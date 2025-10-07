from fastapi import HTTPException, status
from passlib.hash import bcrypt
from ..repositories import users_repo

def register_user(name: str, email: str, password: str) -> dict:
    # 1. Verificar si ya existe el email
    existing = users_repo.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # 2. Hashear la contraseña
    hashed = bcrypt.hash(password)

    # 3. Insertar nuevo usuario
    user = users_repo.insert_user(name, email, hashed)

    # 4. Devolver el usuario (sin contraseña)
    return user
