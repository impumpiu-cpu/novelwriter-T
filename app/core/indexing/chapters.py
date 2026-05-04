from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Chapter

from .builder import ChapterText


def load_chapter_texts(db: Session, novel_id: int) -> list[ChapterText]:
    rows = (
        db.query(Chapter.id, Chapter.content)
        .filter(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_number.asc())
        .all()
    )
    return [
        ChapterText(chapter_id=chapter_id, text=content or "")
        for chapter_id, content in rows
        if (content or "").strip()
    ]
