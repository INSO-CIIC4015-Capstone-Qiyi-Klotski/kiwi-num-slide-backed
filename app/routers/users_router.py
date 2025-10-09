from fastapi import APIRouter, Query
from app.schemas.user_schema import SSGSeedResponse
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/ssg-seed", response_model=SSGSeedResponse)
def ssg_seed(limit: int = Query(200, ge=1, le=1000)):
    return user_service.get_ssg_seed(limit)