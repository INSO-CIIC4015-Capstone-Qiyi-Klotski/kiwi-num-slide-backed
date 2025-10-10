from fastapi import APIRouter, Query, Path, HTTPException, Depends
from fastapi.openapi.models import Response

from app.core.security import get_current_token
from app.schemas.user_schema import SSGSeedResponse, PublicUser, MyProfile
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


