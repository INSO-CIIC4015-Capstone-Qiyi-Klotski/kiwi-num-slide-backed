from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class SSGSeedItem(BaseModel):
    id: int
    tag: str


class SSGSeedResponse(BaseModel):
    items: List[SSGSeedItem]
    count: int


class PublicUserStats(BaseModel):
    puzzles: int
    likes_received: int
    followers: int


class PublicUser(BaseModel):
    id: int
    slug: str
    display_name: str
    avatar_key: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: str
    stats: PublicUserStats


class MyProfile(PublicUser):
    email: str


class UpdateMyProfile(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    avatar_key: Optional[str] = Field(None, min_length=1, max_length=200)

    # evita payloads vacíos
    def ensure_any(self):
        if self.name is None and self.avatar_key is None:
            raise ValueError("At least one field (name or avatar_key) must be provided.")


class UpdateAck(BaseModel):
    ok: bool
    changed: bool



class FollowAck(BaseModel):
    ok: bool
    changed: bool



class FollowingUserItem(BaseModel):
    id: int
    slug: str
    display_name: str
    avatar_key: Optional[str] = None
    avatar_url: Optional[str] = None
    since: str  # fecha en la que empezaste a seguir (ISO)

class FollowingPage(BaseModel):
    items: List[FollowingUserItem]
    next_cursor: Optional[str] = None  # cursor opaco (id de follows)


class MyLikedPuzzleItem(BaseModel):
    id: int                 # puzzle id
    slug: str               # slug del título
    title: str
    size: int
    difficulty: Optional[int] = None
    created_at: str         # fecha de creación del puzzle
    author: Optional[dict] = None  # { id, slug, display_name, avatar_url? }
    since: str              # fecha en la que diste like (ISO)

class MyLikedPuzzlesPage(BaseModel):
    items: List[MyLikedPuzzleItem]
    next_cursor: Optional[str] = None


class MySolveRow(BaseModel):
    id: int                    # solve id
    puzzle: Dict[str, Any]     # { id, slug, title, size, difficulty? }
    movements: int
    duration_ms: int
    solution: Optional[Dict[str, Any]] = None   # opcional
    created_at: str            # fecha del solve (ISO)

class MySolvesPage(BaseModel):
    items: List[MySolveRow]
    next_cursor: Optional[str] = None           # último solve_id de la página



class BrowseUserCounts(BaseModel):
    created: int
    solved: int
    followers: int


class UserListItem(BaseModel):
    id: int
    slug: str
    display_name: str
    avatar_url: Optional[str] = None
    created_at: str
    counts: BrowseUserCounts


class UserListPage(BaseModel):
    items: List[UserListItem]
    next_cursor: Optional[str] = None