"""FastAPI application — articles API for editorial consumption."""

from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import Article, Base
from ..db.session import engine, get_db
from ..ingestion.models import NewsCategory

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI News Podcast — Articles API", version="0.1.0")


class ArticleOut(BaseModel):
    id: int
    url: str
    title: str
    summary: str
    source: str
    category: NewsCategory
    published_at: datetime
    fetched_at: datetime
    used_in_episode: bool

    model_config = {"from_attributes": True}


@app.get("/articles", response_model=list[ArticleOut])
def list_articles(
    category: NewsCategory | None = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200),
    unused_only: bool = Query(False, description="Return only articles not yet used in an episode"),
    db: Session = Depends(get_db),
) -> list[Article]:
    q = db.query(Article).order_by(Article.published_at.desc())
    if category is not None:
        q = q.filter(Article.category == category)
    if unused_only:
        q = q.filter(Article.used_in_episode == False)  # noqa: E712
    return q.limit(limit).all()


@app.get("/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db)) -> Article:
    from fastapi import HTTPException

    article = db.query(Article).filter(Article.id == article_id).first()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
