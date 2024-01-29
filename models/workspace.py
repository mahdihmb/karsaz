from typing import List

from sqlalchemy import Column, String
from sqlalchemy.orm import Session
from sqlalchemy.orm import relationship

from limoo import LimooDriver
from . import Base, create_model


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    display_name = Column(String)
    default_conversation_id = Column(String)

    conversations = relationship('Conversation', back_populates='workspace')
    memberships = relationship('Member', back_populates='workspace')
    tasks = relationship('Task', back_populates='workspace')


async def get_or_add_workspace(db: Session, ld: LimooDriver, id: str) -> Workspace:
    existing_workspace = db.query(Workspace).get(id)
    if existing_workspace:
        return existing_workspace
    workspace_json = await ld.workspaces.get(id)
    new_workspace = Workspace(id=id, name=workspace_json['name'],
                              display_name=workspace_json['display_name'],
                              default_conversation_id=workspace_json['default_conversation_id'])
    return create_model(db, new_workspace)
