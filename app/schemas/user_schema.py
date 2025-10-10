from pydantic import BaseModel, Field
from typing import List, Optional


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