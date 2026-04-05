"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..ingestion.models import NewsCategory


class Base(DeclarativeBase):
    pass


class Article(Base):
    """Raw ingested news article. URL is the deduplication key."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[NewsCategory] = mapped_column(
        Enum(NewsCategory, name="news_category"), nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    used_in_episode: Mapped[bool] = mapped_column(default=False, nullable=False)

    __table_args__ = (
        Index("ix_articles_category_published", "category", "published_at"),
        Index("ix_articles_fetched_at", "fetched_at"),
    )
