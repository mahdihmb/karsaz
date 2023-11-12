from sqlalchemy import Column, String, Enum, ForeignKey, BigInteger, update, delete
from sqlalchemy.orm import Session
from sqlalchemy.orm import relationship

from limoo import LimooDriver
from . import Base, create_model
from .conversation import get_or_add_conversation
from .user import User


class TaskStatus(Enum):
    TODO = 'todo'
    DONE = 'done'
    SUSPENDED = 'suspended'


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    description = Column(String)
    direct_reply_message_id = Column(String)  # FIXME: use for subtasks? also use in message subtasks?
    thread_root_id = Column(String)
    status = Column(Enum(TaskStatus.TODO, TaskStatus.DONE, length=20), nullable=False, default=TaskStatus.TODO,
                    index=True)
    create_at = Column(BigInteger, index=True)
    # due_date = None  # FIXME
    # remind_date = None  # FIXME
    # remind_with_sms = None  # FIXME
    # follow_up_interval = None  # FIXME
    # follow_up_interval_max = None  # FIXME
    # priority = None  # FIXME
    # labels = None  # FIXME

    conversation_id = Column(String, ForeignKey('conversations.id'))
    conversation = relationship('Conversation', back_populates='tasks')

    workspace_id = Column(String, ForeignKey('workspaces.id'))
    workspace = relationship('Workspace', back_populates='tasks')

    reporter_id = Column(String, ForeignKey('users.id'), nullable=True)
    reporter = relationship('User', back_populates='reported_tasks', foreign_keys=[reporter_id])

    assignee_id = Column(String, ForeignKey('users.id'))
    assignee = relationship('User', back_populates='assigned_tasks', foreign_keys=[assignee_id])


def get_task(db: Session, id: str) -> Task:
    return db.query(Task).get(id)


def update_task(db: Session, msg_event, assignee: User, status: TaskStatus):
    message_id_ = msg_event['data']['message']['id']
    message_text_ = msg_event['data']['message']['text']

    update_statement = update(Task).where(Task.id == message_id_).values({
        Task.description: message_text_,
        Task.assignee: assignee,
        Task.status: status,
    })
    db.execute(update_statement)
    db.commit()


async def add_task(db: Session, ld: LimooDriver, msg_event, reporter: User, assignee: User, status: TaskStatus) -> Task:
    conversation = await get_or_add_conversation(db, ld, msg_event)
    new_task = Task(id=(msg_event['data']['message']['id']), description=(msg_event['data']['message']['text']),
                    direct_reply_message_id=msg_event['data']['message']['direct_reply_message_id'],
                    thread_root_id=msg_event['data']['message']['thread_root_id'],
                    status=status, create_at=msg_event['data']['message']['create_at'],
                    conversation_id=conversation.id, workspace_id=msg_event['data']['workspace_id'],
                    reporter=reporter, assignee=assignee, )
    return create_model(db, new_task)


def delete_task(db: Session, task: Task):
    delete_statement = delete(Task).where(Task.id == task.id)
    db.execute(delete_statement)
    db.commit()
