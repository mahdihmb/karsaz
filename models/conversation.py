from sqlalchemy import Column, String, ForeignKey, Enum
from sqlalchemy.orm import Session
from sqlalchemy.orm import relationship

from limoo import LimooDriver
from . import Base, create_model
from .workspace import get_or_create_workspace


class ConversationType(Enum):
    PUBLIC = 'public'
    PRIVATE = 'private'
    DIRECT = 'direct'


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, index=True)
    type = Column(Enum(ConversationType.PUBLIC, ConversationType.PRIVATE, ConversationType.DIRECT, length=10))
    display_name = Column(String)

    workspace_id = Column(String, ForeignKey('workspaces.id'))
    workspace = relationship('Workspace', back_populates='conversations')

    tasks = relationship('Task', back_populates='conversation')


def get_all_conversations(db: Session):
    return db.query(Conversation).all()


def get_workspace_conversations(db: Session, workspace_id: str):
    return db.query(Conversation).filter(Conversation.workspace_id == workspace_id).all()


async def get_or_create_conversation(db: Session, ld: LimooDriver, msg_event) -> Conversation:
    conversation_id_ = msg_event['data']['message']['conversation_id']
    existing_conversation = db.query(Conversation).get(conversation_id_)
    if existing_conversation:
        return existing_conversation
    workspace = await get_or_create_workspace(db, ld, msg_event)
    new_conversation = Conversation(id=conversation_id_, type=msg_event['data']['conversation_type'],
                                    display_name=msg_event['data']['conversation_display_name'],
                                    workspace_id=workspace.id)
    return create_model(db, new_conversation)
