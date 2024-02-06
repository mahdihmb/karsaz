import asyncio
import uuid

from sqlalchemy import Column, String, Boolean, update
from sqlalchemy.orm import Session
from sqlalchemy.orm import relationship

from cache.user import get_user_json_by_username, get_user_json_by_id, calc_user_display_name
from limoo import LimooDriver
from . import Base, create_model
from .member import add_member, update_member, Member


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    is_bot = Column(Boolean, nullable=False, default=False)
    display_name = Column(String)  # (first_name + last_name) | nickname | username
    avatar_hash = Column(String)

    memberships = relationship('Member', back_populates='user')
    reported_tasks = relationship('Task', back_populates='reporter', foreign_keys="Task.reporter_id")
    assigned_tasks = relationship('Task', back_populates='assignee', foreign_keys="Task.assignee_id")

    def mention(self):
        return "@" + self.username

    def avatar_and_display_name_considering_member(self, db: Session, workspace_id: str):
        member: Member = db.query(Member).where(
            Member.user_id == self.id,
            Member.workspace_id == workspace_id,
        ).first()

        display_name = member and member.display_name or self.display_name
        avatar_hash = member and member.avatar_hash or self.avatar_hash
        if avatar_hash:
            return f'![{display_name}](/fileserver/api/v1/files?hash={avatar_hash}&mode=view =x25 "{display_name}") {display_name}'
        return display_name

    def display_name_considering_member(self, db: Session, workspace_id: str):
        member: Member = db.query(Member).where(
            Member.user_id == self.id,
            Member.workspace_id == workspace_id,
        ).first()

        return member and member.display_name or self.display_name


def update_user_by_user_json(db: Session, ld: LimooDriver, user: User, user_json, workspace_id: str):
    display_name = calc_user_display_name(user_json)
    if user.username != user_json['username'] or user.display_name != display_name or \
            user.avatar_hash != user_json['avatar_hash']:
        update_statement = update(User).where(User.id == user.id).values({
            User.username: user_json['username'],
            User.display_name: display_name,
            User.avatar_hash: user_json['avatar_hash'],
        })
        db.execute(update_statement)
        db.commit()

    asyncio.create_task(update_member(db, ld, user, workspace_id))


def add_user(db: Session, ld: LimooDriver, new_user: User, workspace_id: str):
    user = create_model(db, new_user)
    asyncio.create_task(add_member(db, ld, user, workspace_id))
    return user


async def get_or_add_user_by_username(db: Session, ld: LimooDriver, username: str, workspace_id: str) -> User:
    if not username:
        return None

    user = db.query(User).where(User.username == username).first()
    if user:
        return user

    user_json = await get_user_json_by_username(ld, username, workspace_id)
    if user_json:
        user = db.get(User, user_json['id'])
        if user:
            update_user_by_user_json(db, ld, user, user_json, workspace_id)
            return user

        new_user = User(id=user_json['id'], username=user_json['username'], is_bot=user_json['is_bot'],
                        display_name=calc_user_display_name(user_json), avatar_hash=user_json['avatar_hash'])
    else:
        new_user = User(id=str(uuid.uuid4()), username=username)

    return add_user(db, ld, new_user, workspace_id)


async def get_or_add_user_by_id(db: Session, ld: LimooDriver, id: str, workspace_id: str) -> User:
    user = db.get(User, id)
    if user:
        return user

    user_json = await get_user_json_by_id(ld, id, workspace_id)
    if not user_json:
        return None

    new_user = User(id=user_json['id'], username=user_json['username'], is_bot=user_json['is_bot'],
                    display_name=calc_user_display_name(user_json), avatar_hash=user_json['avatar_hash'])
    return add_user(db, ld, new_user, workspace_id)
