import re
from typing import List

from sqlalchemy import Column, String, Enum, ForeignKey, BigInteger, update
from sqlalchemy.orm import Session
from sqlalchemy.orm import relationship

from limoo import LimooDriver
from . import Base, create_model
from .conversation import get_or_create_conversation


class TaskStatus(Enum):
    TODO = 'todo'
    DONE = 'done'
    SUSPENDED = 'suspended'


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    description = Column(String)
    reporter_id = Column(String)
    assignee_username = Column(String)
    direct_reply_message_id = Column(String)  # FIXME: use for subtasks?
    thread_root_id = Column(String)
    status = Column(Enum(TaskStatus.TODO, TaskStatus.DONE, length=20), nullable=False, default=TaskStatus.TODO)
    create_at = Column(BigInteger)
    # follow_up_interval = None  # TODO:
    # follow_up_interval_max = None  # TODO:
    # priority = None  # TODO:
    # labels = None  # TODO:

    conversation_id = Column(String, ForeignKey('conversations.id'))
    conversation = relationship('Conversation', back_populates='tasks')


def get_all_tasks(db: Session) -> List[Task]:
    return db.query(Task).all()


def get_conversation_tasks(db: Session, conversation_id: str) -> List[Task]:
    return db.query(Task).filter(Task.workspace_id == workspace_id).all()


def get_task(db: Session, msg_event) -> Task:
    return db.query(Task).get(msg_event['data']['message']['id'])


def update_task(db: Session, msg_event, assignee_username: str, status: TaskStatus):
    message_id_ = msg_event['data']['message']['id']
    message_text_ = msg_event['data']['message']['text']

    update_statement = update(Task).where(Task.id == message_id_).values({
        Task.description: message_text_,
        Task.assignee_username: assignee_username,
        Task.status: status,
    })
    db.execute(update_statement)
    db.commit()


async def add_task(db: Session, ld: LimooDriver, msg_event, assignee_username: str, status: TaskStatus) -> Task:
    conversation = await get_or_create_conversation(db, ld, msg_event)
    new_task = Task(id=(msg_event['data']['message']['id']), description=(msg_event['data']['message']['text']),
                    reporter_id=msg_event['data']['message']['user_id'], assignee_username=assignee_username,
                    direct_reply_message_id=msg_event['data']['message']['direct_reply_message_id'],
                    thread_root_id=msg_event['data']['message']['thread_root_id'],
                    status=status, create_at=msg_event['data']['message']['create_at'],
                    conversation_id=conversation.id)
    return create_model(db, new_task)
