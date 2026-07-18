from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.document import Document
from app.models.quiz import QuizAttempt, QuizItem
from app.models.review import ReviewRecord
from app.services.ingestion import UPLOAD_DIR


class CourseNotFoundError(RuntimeError):
    pass


def list_courses(db: Session, *, user_id: str = "demo-user") -> list[Course]:
    return list(
        db.scalars(
            select(Course)
            .where(Course.user_id == user_id)
            .order_by(Course.created_at.desc())
        )
    )


def create_course(db: Session, *, user_id: str, name: str) -> Course:
    course = Course(user_id=user_id, name=name.strip())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def validate_course_scope(
    db: Session,
    *,
    user_id: str,
    course_id: int | None,
) -> None:
    if course_id is None:
        return

    if get_course(db=db, user_id=user_id, course_id=course_id) is None:
        raise CourseNotFoundError("Course not found for this user")


def get_course(db: Session, *, user_id: str, course_id: int) -> Course | None:
    return db.scalar(
        select(Course).where(Course.id == course_id, Course.user_id == user_id)
    )


def delete_course(db: Session, *, user_id: str, course_id: int) -> None:
    course = get_course(db=db, user_id=user_id, course_id=course_id)
    if course is None:
        raise CourseNotFoundError("Course not found for this user")

    storage_paths = list(
        db.scalars(
            select(Document.storage_path).where(
                Document.user_id == user_id,
                Document.course_id == course_id,
                Document.storage_path.is_not(None),
            )
        )
    )

    db.execute(
        delete(QuizAttempt).where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.course_id == course_id,
        )
    )
    db.execute(
        delete(ReviewRecord).where(
            ReviewRecord.user_id == user_id,
            ReviewRecord.course_id == course_id,
        )
    )
    db.execute(
        delete(QuizItem).where(
            QuizItem.user_id == user_id,
            QuizItem.course_id == course_id,
        )
    )
    db.execute(
        delete(Document).where(
            Document.user_id == user_id,
            Document.course_id == course_id,
        )
    )
    db.delete(course)
    db.commit()

    for storage_path in storage_paths:
        if storage_path:
            _delete_stored_file(storage_path)


def assign_existing_uncoursed_data(
    db: Session,
    *,
    user_id: str,
    course_id: int,
) -> None:
    validate_course_scope(db=db, user_id=user_id, course_id=course_id)
    db.execute(
        update(Document)
        .where(Document.user_id == user_id, Document.course_id.is_(None))
        .values(course_id=course_id)
    )
    db.execute(
        update(QuizItem)
        .where(QuizItem.user_id == user_id, QuizItem.course_id.is_(None))
        .values(course_id=course_id)
    )
    db.execute(
        update(ReviewRecord)
        .where(ReviewRecord.user_id == user_id, ReviewRecord.course_id.is_(None))
        .values(course_id=course_id)
    )
    db.execute(
        update(QuizAttempt)
        .where(QuizAttempt.user_id == user_id, QuizAttempt.course_id.is_(None))
        .values(course_id=course_id)
    )
    db.commit()


def _delete_stored_file(storage_path: str) -> None:
    upload_root = UPLOAD_DIR.resolve()
    path = Path(storage_path)
    candidate = path if path.is_absolute() else Path.cwd() / path

    try:
        resolved = candidate.resolve()
    except OSError:
        return

    if resolved != upload_root and upload_root not in resolved.parents:
        return

    try:
        resolved.unlink(missing_ok=True)
    except OSError:
        return
