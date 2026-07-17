from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.course import Course
from app.schemas.course import CourseCreateRequest, CourseResponse
from app.services.courses import (
    CourseNotFoundError,
    create_course,
    delete_course,
    list_courses,
)

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseResponse])
def get_courses(
    user_id: str = "demo-user",
    db: Session = Depends(get_db),
) -> list[CourseResponse]:
    return [_to_response(course) for course in list_courses(db, user_id=user_id)]


@router.post("", response_model=CourseResponse, status_code=201)
def post_course(
    request: CourseCreateRequest,
    db: Session = Depends(get_db),
) -> CourseResponse:
    return _to_response(
        create_course(db=db, user_id=request.user_id, name=request.name)
    )


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_course(
    course_id: int,
    user_id: str = "demo-user",
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_course(db=db, user_id=user_id, course_id=course_id)
    except CourseNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


def _to_response(course: Course) -> CourseResponse:
    return CourseResponse(
        id=course.id,
        user_id=course.user_id,
        name=course.name,
        created_at=course.created_at,
    )
