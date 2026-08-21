from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class PostOut(BaseModel):
    id: int
    linkedin_url: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    quote: Optional[str] = None
    mariana_take: Optional[str] = None
    content_type: Optional[str] = None
    difficulty: Optional[str] = None
    post_date: Optional[datetime] = None
    tags: list[str] = []
    school_name: Optional[str] = None
    discipline_name: Optional[str] = None
    module_name: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_validator("tags", mode="before")
    @classmethod
    def _serialize_tags(cls, v):
        if v and hasattr(next(iter(v), None), "name"):
            return [t.name for t in v]
        return v


class PostList(BaseModel):
    items: list[PostOut]
    total: int
    page: int


class PostDetail(BaseModel):
    post: PostOut
    related: list[PostOut] = []


class DisciplineOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    school_name: Optional[str] = None
    post_count: int = 0
    lesson_count: int = 0
    lab_count: int = 0

    model_config = {"from_attributes": True}


class SchoolOut(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    disciplines: list[DisciplineOut] = []

    model_config = {"from_attributes": True}


class GraphNode(BaseModel):
    id: int
    label: str
    x: float = 0.0
    y: float = 0.0
    radius: float = 10.0
    color: str = "#6366f1"
    layer: int = 0
    posts: int = 0
    is_new: bool = False
    is_trending: bool = False


class GraphEdge(BaseModel):
    source: int
    target: int


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class SearchResult(BaseModel):
    type: str = "post"
    title: str
    subtitle: Optional[str] = None
    tags: list[str] = []
    url: str = ""


class SearchOut(BaseModel):
    results: list[SearchResult]
    total: int


class InviteCreate(BaseModel):
    expires_in_days: int = 30
    usage_limit: int = 1


class InviteValidate(BaseModel):
    token: str


class InviteOut(BaseModel):
    token: str
    expires_at: Optional[datetime] = None
    active: bool = True


class TrendingItem(BaseModel):
    label: str
    posts: int = 0
    delta: str = ""
    color: str = "#6366f1"
    is_new: bool = False


class StatsOut(BaseModel):
    total_posts: int = 0
    total_disciplines: int = 0
    total_schools: int = 0
    total_labs: int = 0
