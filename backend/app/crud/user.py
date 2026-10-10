# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, validate_password_strength, verify_password
from app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.scalar(select(User).where(User.id == user_id))


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def create_user(db: Session, username: str, password: str, **kwargs) -> User:
    validate_password_strength(password)
    user = User(username=username, password_hash=hash_password(password), **kwargs)
    db.add(user)
    db.flush()
    return user


def set_password(db: Session, user: User, password: str) -> User:
    validate_password_strength(password)
    user.password_hash = hash_password(password)
    db.flush()
    return user


def change_user_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise ValueError("原密码不正确")
    set_password(db, user, new_password)


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user