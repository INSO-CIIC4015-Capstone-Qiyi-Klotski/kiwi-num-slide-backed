from fastapi import APIRouter, Depends, status, Response
from app.core.security import get_current_token
from app.schemas.puzzle_schema import PuzzleCreate, PuzzleOut
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
