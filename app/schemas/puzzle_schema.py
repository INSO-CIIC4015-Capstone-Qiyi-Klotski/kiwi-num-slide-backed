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



class PuzzleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    size: Optional[int] = Field(None, ge=1, le=10)
    board_spec: Optional[Dict[str, Any]] = None
    difficulty: Optional[int] = Field(None, ge=1, le=5)
    num_solutions: Optional[int] = Field(None, ge=0)

    @field_validator("board_spec")
    @classmethod
    def board_spec_if_present_must_be_object(cls, v):
        if v is not None and not isinstance(v, dict):
            raise ValueError("board_spec debe ser un objeto JSON")
        return v

class PuzzleUpdateAck(BaseModel):
    ok: bool
    changed: bool



class PuzzleDeleteAck(BaseModel):
    ok: bool
    deleted: bool


class PuzzleListItem(BaseModel):
    id: int
    slug: str
    title: str
    size: int
    difficulty: Optional[int] = None
    created_at: str
    author: Optional[Dict[str, Any]] = None  # { id, slug, display_name, avatar_url? }

class PuzzleListPage(BaseModel):
    items: List[PuzzleListItem]
    next_cursor: Optional[str] = None  # último id de la página (opaco)


class LikeAck(BaseModel):
    ok: bool
    changed: bool  # True si se creó el like; False si ya existía (idempotente)


class LikeCount(BaseModel):
    count: int