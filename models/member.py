import asyncio

from sqlalchemy import Column, String, ForeignKey, update
from sqlalchemy.orm import relationship, Session

from cache.member import get_member_json, calc_member_display_name
from limoo import LimooDriver
from . import Base, create_model
from .workspace import get_or_add_workspace


class Member(Base):
    __tablename__ = "members"

    display_name = Column(String)  # (first_name + last_name) | nickname
    avatar_hash = Column(String)

    user_id = Column(String, ForeignKey('users.id'), primary_key=True, index=True)
    user = relationship('User', back_populates='memberships')
    # average_todo_time = None  # FIXME

    workspace_id = Column(String, ForeignKey('workspaces.id'), primary_key=True, index=True)
    workspace = relationship('Workspace', back_populates='memberships')


async def add_member(db: Session, ld: LimooDriver, user, workspace_id: str):
    workspace = await get_or_add_workspace(db, ld, workspace_id)
    member_json = await get_member_json(ld, workspace.id, user.id)
    if member_json:
        new_member = Member(display_name=calc_member_display_name(member_json), avatar_hash=member_json['avatar_hash'],
                            workspace_id=workspace.id, user=user)
    else:
        new_member = Member(display_name=user.display_name, avatar_hash=user.avatar_hash,
                            workspace_id=workspace.id, user=user)
    return create_model(db, new_member)


async def update_member(db: Session, ld: LimooDriver, user, workspace_id: str):
    member: Member = db.query(Member).where(
        Member.user_id == user.id,
        Member.workspace_id == workspace_id,
    ).first()

    if not member:
        asyncio.create_task(add_member(db, ld, user, workspace_id))
        return

    member_json = await get_member_json(ld, workspace_id, user.id)
    display_name = calc_member_display_name(member_json)
    if member_json and \
            (member.display_name != display_name or member.avatar_hash != member_json['avatar_hash']):
        update_statement = update(Member).where(Member.user_id == user.id, Member.workspace_id == workspace_id).values({
            Member.display_name: display_name,
            Member.avatar_hash: member_json['avatar_hash'],
        })
        db.execute(update_statement)
        db.commit()
