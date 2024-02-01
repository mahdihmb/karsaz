from sqlalchemy import Column, String, ForeignKey, Enum
from sqlalchemy.orm import Session
from sqlalchemy.orm import relationship

from limoo import LimooDriver
from . import Base, create_model
from .workspace import get_or_add_workspace


class ConversationType(Enum):
    PUBLIC = 'public'
    PRIVATE = 'private'
    DIRECT = 'direct'


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, index=True)
    type = Column(Enum(ConversationType.PUBLIC, ConversationType.PRIVATE, ConversationType.DIRECT, length=10))
    display_name = Column(String)
    # auto_detect_task_enabled = None  # FIXME: detect with ? and done after mentioned user response with a specific pattern (detect dot and other runs!)
    # follow_up_interval = None  # FIXME: can set first day of week or everyday or custom interval (maybe better name for field)
    # custom_text_with_follow_up = None  # FIXME: to sent at first of message

    workspace_id = Column(String, ForeignKey('workspaces.id'))
    workspace = relationship('Workspace', back_populates='conversations')

    tasks = relationship('Task', back_populates='conversation')


async def get_or_add_conversation(db: Session, ld: LimooDriver, msg_event) -> Conversation:
    conversation_id_ = msg_event['data']['message']['conversation_id']
    existing_conversation = db.get(Conversation, conversation_id_)
    if existing_conversation:
        return existing_conversation
    workspace = await get_or_add_workspace(db, ld, msg_event['data']['workspace_id'])
    new_conversation = Conversation(id=conversation_id_, type=msg_event['data']['conversation_type'],
                                    display_name=msg_event['data']['conversation_display_name'],
                                    workspace_id=workspace.id)
    return create_model(db, new_conversation)
