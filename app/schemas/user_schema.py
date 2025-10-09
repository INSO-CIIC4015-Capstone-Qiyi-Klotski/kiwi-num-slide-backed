from pydantic import BaseModel
from typing import List


class SSGSeedItem(BaseModel):
    id: int
    tag: str


class SSGSeedResponse(BaseModel):
    items: List[SSGSeedItem]
    count: int
