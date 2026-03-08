"""Phase I: 사용자 API 엔드포인트

즐겨찾기(favorites) + 저장 검색(saved-searches) CRUD.
모든 엔드포인트는 Authorization: Bearer <token> 필수.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.v1.auth import verify_token
from app.models.db.user import User, UserFavorite, UserSavedSearch

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])
_bearer = HTTPBearer(auto_error=False)


# ── 인증 의존성 ───────────────────────────────────────────────────────────

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """JWT 검증 → User ORM 반환. 실패 시 401."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다")
    try:
        payload = verify_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다")
    return user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """JWT 검증 → User | None (인증 없어도 허용)"""
    if credentials is None:
        return None
    try:
        payload = verify_token(credentials.credentials)
        return db.query(User).filter(User.id == payload["sub"]).first()
    except (ValueError, Exception):
        return None


# ── 스키마 ─────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str | None
    image: str | None


class FavoriteItem(BaseModel):
    case_number: str
    created_at: datetime


class FavoritesResponse(BaseModel):
    case_numbers: list[str]


class BulkSyncRequest(BaseModel):
    """localStorage 즐겨찾기 일괄 동기화"""
    case_numbers: list[str]


class SavedSearchItem(BaseModel):
    id: str
    name: str
    params_json: dict[str, Any]
    created_at: datetime


class SaveSearchRequest(BaseModel):
    name: str
    params_json: dict[str, Any]


# ── 엔드포인트 ─────────────────────────────────────────────────────────────

@router.get("/users/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """현재 사용자 정보"""
    return UserResponse(
        user_id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        image=current_user.image,
    )


# ── 즐겨찾기 ──────────────────────────────────────────────────────────────

@router.get("/users/me/favorites", response_model=FavoritesResponse)
def get_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FavoritesResponse:
    """즐겨찾기 목록 조회"""
    rows = (
        db.query(UserFavorite)
        .filter(UserFavorite.user_id == current_user.id)
        .order_by(UserFavorite.created_at.desc())
        .all()
    )
    return FavoritesResponse(case_numbers=[r.case_number for r in rows])


@router.put("/users/me/favorites/{case_number}", status_code=status.HTTP_204_NO_CONTENT)
def add_favorite(
    case_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """즐겨찾기 추가 (이미 있으면 무시)"""
    existing = (
        db.query(UserFavorite)
        .filter(
            UserFavorite.user_id == current_user.id,
            UserFavorite.case_number == case_number,
        )
        .first()
    )
    if existing is None:
        db.add(UserFavorite(user_id=current_user.id, case_number=case_number))
        db.commit()


@router.delete("/users/me/favorites/{case_number}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    case_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """즐겨찾기 제거"""
    db.query(UserFavorite).filter(
        UserFavorite.user_id == current_user.id,
        UserFavorite.case_number == case_number,
    ).delete()
    db.commit()


@router.post("/users/me/favorites/bulk", status_code=status.HTTP_204_NO_CONTENT)
def bulk_sync_favorites(
    body: BulkSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """localStorage → DB 일괄 동기화 (로그인 시 한 번 호출)"""
    existing = {
        r.case_number
        for r in db.query(UserFavorite).filter(UserFavorite.user_id == current_user.id).all()
    }
    new_items = [
        UserFavorite(user_id=current_user.id, case_number=cn)
        for cn in body.case_numbers
        if cn not in existing
    ]
    if new_items:
        db.bulk_save_objects(new_items)
        db.commit()


# ── 저장 검색 ──────────────────────────────────────────────────────────────

@router.get("/users/me/saved-searches", response_model=list[SavedSearchItem])
def get_saved_searches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SavedSearchItem]:
    """저장된 검색 조건 목록"""
    rows = (
        db.query(UserSavedSearch)
        .filter(UserSavedSearch.user_id == current_user.id)
        .order_by(UserSavedSearch.created_at.desc())
        .all()
    )
    return [
        SavedSearchItem(
            id=r.id,
            name=r.name,
            params_json=r.params_json,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/users/me/saved-searches", response_model=SavedSearchItem, status_code=status.HTTP_201_CREATED)
def save_search(
    body: SaveSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SavedSearchItem:
    """검색 조건 저장 (최대 20개, 초과 시 오래된 것 삭제)"""
    # 최대 20개 제한: 초과분 삭제
    rows = (
        db.query(UserSavedSearch)
        .filter(UserSavedSearch.user_id == current_user.id)
        .order_by(UserSavedSearch.created_at.asc())
        .all()
    )
    if len(rows) >= 20:
        db.delete(rows[0])

    new_search = UserSavedSearch(
        user_id=current_user.id,
        name=body.name,
        params_json=body.params_json,
    )
    db.add(new_search)
    db.commit()
    db.refresh(new_search)
    return SavedSearchItem(
        id=new_search.id,
        name=new_search.name,
        params_json=new_search.params_json,
        created_at=new_search.created_at,
    )


@router.delete("/users/me/saved-searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(
    search_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """저장 검색 삭제"""
    deleted = (
        db.query(UserSavedSearch)
        .filter(
            UserSavedSearch.id == search_id,
            UserSavedSearch.user_id == current_user.id,
        )
        .delete()
    )
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="저장 검색을 찾을 수 없습니다")
