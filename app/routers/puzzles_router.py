import os
from typing import Optional

from fastapi import APIRouter, Depends, status, Response, Query, Path, HTTPException, Header
from app.core.security import get_current_token
from app.schemas.puzzle_generation_schema import PuzzleGenConfig, GenerateAck, generate_puzzles_responses
from app.schemas.puzzle_schema import PuzzleCreate, PuzzleOut, PuzzleUpdate, \
    PuzzleListPage, LikeAck, PuzzleSolveOut, PuzzleSolveCreate, MySolvesPage, DailyPuzzleOut
from app.services import puzzle_service, puzzle_generation
from datetime import date as _date

from app.core.security import get_current_token_cookie_or_header
from app.core.cookies import require_csrf
from app.core.config import settings

router = APIRouter(prefix="/puzzles", tags=["puzzles"])


@router.post("", response_model=PuzzleOut, status_code=status.HTTP_201_CREATED)
def create_puzzle(payload: PuzzleCreate, token=Depends(get_current_token_cookie_or_header), response: Response = None, _csrf = Depends(require_csrf) ):
    author_id = int(token["sub"])
    data = puzzle_service.create_puzzle(
        author_id=author_id,
        title=payload.title,
        size=payload.size,
        board_spec=payload.board_spec,
        difficulty=payload.difficulty,
        num_solutions=payload.num_solutions,
    )
    if response is not None:
        response.headers["Location"] = f"/puzzles/{data['id']}"
    return data


@router.get("/daily-puzzle", response_model=DailyPuzzleOut)
def get_daily_puzzle(response: Response):
    data = puzzle_service.get_today_daily_puzzle()
    if not data:
        raise HTTPException(status_code=404, detail="Daily puzzle not configured for today")
    response.headers["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=60"
    return data


@router.get("/daily-puzzle/{d}", response_model=DailyPuzzleOut)
def get_daily_puzzle_by_date(
    d: _date = Path(..., description="Fecha en formato YYYY-MM-DD"),
    response: Response = None,
):
    data = puzzle_service.get_daily_puzzle_for_date(d)
    if not data:
        raise HTTPException(status_code=404, detail="Daily puzzle not configured for this date")
    if response is not None:
        # ISR-safe
        response.headers["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=60"
    return data


@router.get("/{puzzle_id}", response_model=PuzzleOut)
def get_puzzle(puzzle_id: int = Path(..., ge=1), response: Response = None):
    data = puzzle_service.get_puzzle_details(puzzle_id)
    if not data:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    # ISR-safe cache headers (ajusta valores a tu gusto)
    if response is not None:
        response.headers["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=60"
    return data


@router.get("", response_model=PuzzleListPage)
def browse_puzzles(
    response: Response,
    size: Optional[int] = Query(None, ge=1, le=10),
    q: Optional[str] = Query(None, min_length=1, max_length=100),
    sort: str = Query("created_at_desc"),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    # 👇 nombres que vienen del FE (camelCase) usando alias
    min_likes: Optional[int] = Query(None, ge=0, alias="minLikes"),
    author_id: Optional[int] = Query(None, ge=1, alias="authorId"),
    generated_by: Optional[str] = Query(
        None,
        alias="generatedBy",
        description="algorithm | user",
    ),
    operators: Optional[str] = Query(
        None,
        alias="operators",
        description="lista separada por comas: add,sub,mul,div",
    ),
):
    try:
        data = puzzle_service.browse_puzzles_public(
            limit=limit,
            cursor=cursor,
            size=size,
            q=q,
            sort=sort,
            min_likes=min_likes,
            author_id=author_id,
            generated_by=generated_by,
            operators=operators,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Cache amigable para SSR/CSR
    response.headers["Cache-Control"] = "public, s-maxage=120, stale-while-revalidate=60"
    return data



@router.post("/{puzzle_id}/like", response_model=LikeAck)
def like_puzzle(
    puzzle_id: int = Path(..., ge=1),
    token=Depends(get_current_token_cookie_or_header),
    _csrf=Depends(require_csrf),
):
    user_id = int(token["sub"])
    return puzzle_service.like_puzzle(current_user_id=user_id, puzzle_id=puzzle_id)


@router.delete("/{puzzle_id}/like", response_model=LikeAck)
def unlike_puzzle(
    puzzle_id: int = Path(..., ge=1),
    token=Depends(get_current_token_cookie_or_header),
    _csrf=Depends(require_csrf),
):
    user_id = int(token["sub"])
    return puzzle_service.unlike_puzzle(current_user_id=user_id, puzzle_id=puzzle_id)


@router.post("/{puzzle_id}/solves", response_model=PuzzleSolveOut, status_code=status.HTTP_201_CREATED)
def submit_solve(
    puzzle_id: int = Path(..., ge=1),
    payload: PuzzleSolveCreate = None,
    token=Depends(get_current_token_cookie_or_header),
    _csrf=Depends(require_csrf),
):
    user_id = int(token["sub"])
    return puzzle_service.submit_puzzle_solve(
        current_user_id=user_id,
        puzzle_id=puzzle_id,
        movements=payload.movements,
        duration_ms=payload.duration_ms,
        solution=payload.solution,
    )



@router.get("/{puzzle_id}/solves/me", response_model=MySolvesPage)
def get_my_solves_for_puzzle(
    puzzle_id: int = Path(..., ge=1),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    token=Depends(get_current_token_cookie_or_header),
    _csrf=Depends(require_csrf),
):
    user_id = int(token["sub"])
    return puzzle_service.list_my_solves_for_puzzle(
        current_user_id=user_id,
        puzzle_id=puzzle_id,
        limit=limit,
        cursor=cursor,
    )


@router.post(
    "/generate",
    status_code=201,
    response_model=GenerateAck,
    responses=generate_puzzles_responses,
)
def generate_puzzles(
    cfg: PuzzleGenConfig,
    secret: Optional[str] = Query(None),
    x_gen_secret: Optional[str] = Header(None, alias="X-Gen-Secret"),
):
    expected = settings.generation_secret
    provided = secret or x_gen_secret
    if not expected or provided != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    return puzzle_generation.generate_and_store_puzzles(**cfg.model_dump())


@router.post("/daily/ensure")
def ensure_daily(secret: Optional[str] = Query(None), x_gen_secret: Optional[str] = Header(None, alias="X-Gen-Secret")):
    expected = settings.generation_secret
    provided = secret or x_gen_secret
    if not expected or provided != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    return puzzle_service.ensure_daily_puzzle_for_today(auto_generate_fallback=True)