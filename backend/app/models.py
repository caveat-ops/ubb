from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    linkedin_url = Column(String(500), unique=True, nullable=False)
    linkedin_post_id = Column(String(100), nullable=True)
    title = Column(String(300), nullable=True)
    subtitle = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    quote = Column(Text, nullable=True)
    mariana_take = Column(Text, nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=True)
    module_id = Column(Integer, ForeignKey("modules.id"), nullable=True)
    content_type = Column(String(50), nullable=True)
    skill_type = Column(String(50), nullable=True)
    difficulty = Column(String(50), nullable=True)
    post_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    indexed_at = Column(DateTime, nullable=True)
    embedding = Column(Vector(384), nullable=True)
    raw_json = Column(JSON, nullable=True)

    tags = relationship("Tag", secondary=post_tags, back_populates="posts")
    school = relationship("School", back_populates="posts")
    discipline = relationship("Discipline", back_populates="posts")
    module = relationship("Module", back_populates="posts")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    normalized_name = Column(String(100), unique=True)

    posts = relationship("Post", secondary=post_tags, back_populates="tags")


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    slug = Column(String(100), unique=True)
    description = Column(Text, nullable=True)
    color = Column(String(20), nullable=True)
    icon = Column(String(50), nullable=True)

    disciplines = relationship("Discipline", back_populates="school")
    posts = relationship("Post", back_populates="school")


class Discipline(Base):
    __tablename__ = "disciplines"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    slug = Column(String(100), unique=True)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    color = Column(String(20), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)

    school = relationship("School", back_populates="disciplines")
    modules = relationship("Module", back_populates="discipline")
    posts = relationship("Post", back_populates="discipline")


class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    slug = Column(String(200))
    description = Column(Text, nullable=True)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=True)

    discipline = relationship("Discipline", back_populates="modules")
    posts = relationship("Post", back_populates="module")


class SemanticRelation(Base):
    __tablename__ = "semantic_relations"

    id = Column(Integer, primary_key=True)
    source_post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    target_post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    similarity_score = Column(Float, nullable=True)
    relation_type = Column(String(50), nullable=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(20), default="viewer")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    invite_token_id = Column(Integer, ForeignKey("invite_tokens.id"), nullable=True)


class InviteToken(Base):
    __tablename__ = "invite_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String(100), unique=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    usage_limit = Column(Integer, default=1)
    times_used = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
