"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..ingestion.models import NewsCategory


class Base(DeclarativeBase):
    pass


class StoryCluster(Base):
    """Groups articles about the same news story/topic."""

    __tablename__ = "story_clusters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topic_key: Mapped[str] = mapped_column(
        String(512), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    covered_in_episode: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_covered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    article_count: Mapped[int] = mapped_column(default=0, nullable=False)

    articles: Mapped[list["Article"]] = relationship(
        "Article", back_populates="cluster", lazy="selectin"
    )

    __table_args__ = (Index("ix_clusters_covered", "covered_in_episode", "last_covered_at"),)


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
    cluster_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_clusters.id"), nullable=True
    )

    cluster: Mapped[StoryCluster | None] = relationship(
        "StoryCluster", back_populates="articles", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_articles_category_published", "category", "published_at"),
        Index("ix_articles_fetched_at", "fetched_at"),
        Index("ix_articles_cluster_id", "cluster_id"),
    )


class Episode(Base):
    """Tracks which story clusters were covered in each episode."""

    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    episode_title: Mapped[str] = mapped_column(String(512), nullable=False)
    episode_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    story_count: Mapped[int] = mapped_column(default=0, nullable=False)

    __table_args__ = (Index("ix_episodes_published_at", "published_at"),)
