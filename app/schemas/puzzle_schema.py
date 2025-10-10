from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field, validator, field_validator


class PuzzleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    size: int = Field(..., ge=1, le=10)  # ajusta el máximo si quieres
    board_spec: Dict[str, Any]  # flexible: cualquier objeto JSON
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    num_solutions: Optional[int] = Field(None, ge=0)

    @field_validator("board_spec")
    @classmethod
    def board_spec_must_be_object(cls, v):
        # Evita listas/strings como board_spec (queremos un objeto JSON)
        if not isinstance(v, dict):
            raise ValueError("board_spec debe ser un objeto JSON")
        return v


class PuzzleOut(BaseModel):
    id: int
    author_id: int
    title: str
    size: int
    board_spec: Dict[str, Any]
    difficulty: Optional[int] = None
    num_solutions: Optional[int] = None
    created_at: str

    author: Optional[Dict[str, Any]] = None  # { id, slug, display_name, avatar_key, avatar_url }


class PuzzlesSSGSeedItem(BaseModel):
    id: int
    tag: str  # slug del título

class PuzzlesSSGSeedResponse(BaseModel):
    items: List[PuzzlesSSGSeedItem]
    count: int

