from fastapi import APIRouter, Depends, status, Response, Query, Path, HTTPException
from app.core.security import get_current_token
from app.schemas.puzzle_schema import PuzzleCreate, PuzzleOut, PuzzlesSSGSeedResponse
from app.services import puzzle_service

router = APIRouter(prefix="/puzzles", tags=["puzzles"])


@router.post("", response_model=PuzzleOut, status_code=status.HTTP_201_CREATED)
def create_puzzle(payload: PuzzleCreate, token=Depends(get_current_token), response: Response = None):
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



@router.get("/ssg-seed", response_model=PuzzlesSSGSeedResponse)
def puzzles_ssg_seed(limit: int = Query(200, ge=1, le=1000)):
    return puzzle_service.get_puzzles_ssg_seed(limit)


@router.get("/{puzzle_id}", response_model=PuzzleOut)
def get_puzzle(puzzle_id: int = Path(..., ge=1), response: Response = None):
    data = puzzle_service.get_puzzle_details(puzzle_id)
    if not data:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    # ISR-safe cache headers (ajusta valores a tu gusto)
    if response is not None:
        response.headers["Cache-Control"] = "public, s-maxage=300, stale-while-revalidate=60"
    return data