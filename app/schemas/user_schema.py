from pydantic import BaseModel
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
    avatar_url: Optional[str] = None  # si tienes CDN, se arma en service
    created_at: str
    stats: PublicUserStats


class MyProfile(PublicUser):
    email: str