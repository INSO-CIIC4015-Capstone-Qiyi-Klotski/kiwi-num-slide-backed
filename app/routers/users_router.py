from typing import Optional

from fastapi import APIRouter, Query, Path, HTTPException, Depends
from fastapi.openapi.models import Response
from starlette import status

from app.core.security import get_current_token
from app.schemas.user_schema import SSGSeedResponse, PublicUser, MyProfile, UpdateAck, UpdateMyProfile, FollowAck, \
    FollowingPage
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/ssg-seed", response_model=SSGSeedResponse)
def ssg_seed(limit: int = Query(200, ge=1, le=1000)):
    return user_service.get_ssg_seed(limit)



@router.get("/me", response_model=MyProfile)
def get_me(token=Depends(get_current_token)):
    user_id = int(token["sub"])
    data = user_service.get_my_profile(user_id)
    if not data:
        # si el token es válido pero el usuario ya no existe
        raise HTTPException(status_code=404, detail="User not found")
    # Importante: perfil propio es privado → NO cache público
    return data


@router.patch("/me", response_model=UpdateAck, status_code=200)
def patch_me(payload: UpdateMyProfile, token=Depends(get_current_token)):
    if payload.name is None and payload.avatar_key is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Provide at least one of: name, avatar_key")

    user_id = int(token["sub"])
    return user_service.patch_my_profile(
        user_id,
        name=payload.name,
        avatar_key=payload.avatar_key,
    )


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


@router.post("/{user_id}/follow", response_model=FollowAck)
def follow_user(
    user_id: int = Path(..., ge=1),
    token=Depends(get_current_token),
):
    follower_id = int(token["sub"])
    return user_service.follow_user(follower_id, user_id)



@router.delete("/{user_id}/follow", response_model=FollowAck)
def unfollow_user(
    user_id: int = Path(..., ge=1),
    token=Depends(get_current_token),
):
    follower_id = int(token["sub"])
    return user_service.unfollow_user(follower_id, user_id)



@router.get("/me/following", response_model=FollowingPage)
def get_my_following(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    token = Depends(get_current_token),
):
    current_user_id = int(token["sub"])
    return user_service.list_my_following(current_user_id, limit=limit, cursor=cursor)



@router.get("/me/followers", response_model=FollowingPage)
def get_my_followers(
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    token = Depends(get_current_token),
):
    current_user_id = int(token["sub"])
    return user_service.list_my_followers(current_user_id, limit=limit, cursor=cursor)