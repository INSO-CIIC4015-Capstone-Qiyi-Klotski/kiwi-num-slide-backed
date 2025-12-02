import os
from typing import Optional

import boto3
from fastapi import APIRouter, Query, Path, HTTPException, Depends
# from fastapi.openapi.models import Response
from fastapi import APIRouter, Query, Path, HTTPException, Depends, Response
from starlette import status

from app.core.security import get_current_token
from app.schemas.user_schema import PublicUser, MyProfile, UpdateAck, UpdateMyProfile, FollowAck, \
    FollowingPage, MyLikedPuzzlesPage, MySolvesPage, UserListPage, AvatarCatalogResponse, AvatarItem, UpdateAvatarBody

from app.schemas.puzzle_schema import PuzzleListPage

from app.services import user_service

from app.core.security import get_current_token_cookie_or_header
from app.core.cookies import require_csrf
from app.services.user_service import AVATAR_CDN_BASE

from app.core.config import settings

AVATAR_BUCKET = settings.avatar_bucket
AVATAR_PREFIX = settings.avatar_prefix

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/avatar-catalog", response_model=AvatarCatalogResponse)
def list_avatars():
    """
    Devuelve el catálogo de avatares en S3 bajo AVATAR_PREFIX.
    Solo lista PNGs dentro de avatars/.
    """
    s3 = boto3.client("s3")

    resp = s3.list_objects_v2(
        Bucket=AVATAR_BUCKET,
        Prefix=AVATAR_PREFIX,
    )

    contents = resp.get("Contents", [])
    items: list[AvatarItem] = []

    cdn_base = AVATAR_CDN_BASE.rstrip("/")

    for obj in contents:
        key = obj.get("Key") or ""
        # ignorar la carpeta en sí y solo PNG
        if not key or key.endswith("/") or not key.lower().endswith(".png"):
            continue

        url = f"{cdn_base}/{key}"
        items.append(AvatarItem(key=key, url=url))

    return AvatarCatalogResponse(items=items)


@router.patch("/me", response_model=UpdateAck, status_code=200)
def patch_me(
    payload: UpdateMyProfile,
    token = Depends(get_current_token_cookie_or_header),
    _csrf = Depends(require_csrf),
):
    user_id = int(token["sub"])

    # Normalizamos los campos
    name = payload.name.strip() if payload.name is not None else None
    avatar_key = payload.avatar_key.strip() if payload.avatar_key is not None else None

    # Validación: al menos uno
    if (not name) and (not avatar_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of: name, avatar_key",
        )

    # Validación extra del avatar_key
    if avatar_key is not None:
        if not avatar_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="avatar_key is required",
            )

        if not avatar_key.startswith(AVATAR_PREFIX):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid avatar key",
            )

    result = user_service.patch_my_profile(
        user_id=user_id,
        name=name,
        avatar_key=avatar_key,
    )

    return result


@router.get("/{user_id}", response_model=PublicUser)
def get_user_public_profile(
        user_id: int = Path(..., ge=1),
        response: Response = None,
):
    data = user_service.get_public_profile(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="User not found")
    # Cache para CDN/edge (opcional)
    if response is not None:
        response.headers["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=60"
    return data


@router.get("/{user_id}/puzzles/likes", response_model=PuzzleListPage)
def list_user_liked_puzzles(
    user_id: int = Path(..., ge=1),
    response: Response = None,
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
):
    """
    Lista de puzzles a los que el usuario `user_id` les ha dado like.
    Público, con paginación por cursor (puzzle_likes.id).
    """
    data = user_service.list_puzzles_liked_by_user(
        user_id=user_id,
        limit=limit,
        cursor=cursor,
    )

    if response is not None:
        response.headers["Cache-Control"] = "public, s-maxage=120, stale-while-revalidate=60"

    return data



@router.post("/{user_id}/follow", response_model=FollowAck)
def follow_user(
        user_id: int = Path(..., ge=1),
        token=Depends(get_current_token_cookie_or_header),
        _csrf=Depends(require_csrf),
):
    follower_id = int(token["sub"])
    return user_service.follow_user(follower_id, user_id)


@router.delete("/{user_id}/follow", response_model=FollowAck)
def unfollow_user(
        user_id: int = Path(..., ge=1),
        token=Depends(get_current_token_cookie_or_header),
        _csrf=Depends(require_csrf),
):
    follower_id = int(token["sub"])
    return user_service.unfollow_user(follower_id, user_id)



@router.get("", response_model=UserListPage)
def browse_users(
        response: Response,
        q: Optional[str] = Query(None, min_length=1, max_length=100),
        sort: str = Query("created_at_desc"),
        limit: int = Query(20, ge=1, le=100),
        cursor: Optional[str] = Query(None),
        followers_of: Optional[int] = Query(
            None,
            ge=1,
            alias="followersOf",
            description="Users who follow this user id",
        ),
        following_of: Optional[int] = Query(
            None,
            ge=1,
            alias="followingOf",
            description="Users this user id is following",
        ),
):
    try:
        data = user_service.browse_users_public(
            limit=limit,
            cursor=cursor,
            q=q,
            sort=sort,
            followers_of=followers_of,
            following_of=following_of,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Cache amigable para SSR/CSR
    response.headers[
        "Cache-Control"
    ] = "public, s-maxage=120, stale-while-revalidate=60"
    return data

