import re
from datetime import datetime

from jdatetime import datetime as jdt, FA_LOCALE
from sqlalchemy import Column, String, Enum, ForeignKey, BigInteger, update, delete
from sqlalchemy.orm import Session
from sqlalchemy.orm import relationship

from constants import EMPTY_ASSIGNEE, MENTION_USERNAME_PATTERN, DONE_TASK_TEMPLATE, DELETE_TASK_TEMPLATE
from limoo import LimooDriver
from limoo_driver_provider import LIMOO_HOST
from utils import current_millis
from . import Base, create_model
from .attachment import Attachment
from .conversation import get_or_add_conversation
from .user import User, get_or_add_user_by_username


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
    assign_date = Column(BigInteger, index=True)
    done_date = Column(BigInteger, index=True)
    # due_date = None  # FIXME
    # remind_date = None  # FIXME
    # remind_with_sms = None  # FIXME
    # follow_up_interval = None  # FIXME
    # follow_up_interval_max = None  # FIXME
    # priority = None  # FIXME
    # labels = None  # FIXME

    # to prevent error, here must use Attachment.__name__ instead of string name
    attachments = relationship(Attachment.__name__, back_populates='task')

    conversation_id = Column(String, ForeignKey('conversations.id'))
    conversation = relationship('Conversation', back_populates='tasks')

    workspace_id = Column(String, ForeignKey('workspaces.id'))
    workspace = relationship('Workspace', back_populates='tasks')

    reporter_id = Column(String, ForeignKey('users.id'), nullable=True)
    reporter = relationship('User', back_populates='reported_tasks', foreign_keys=[reporter_id])

    assignee_id = Column(String, ForeignKey('users.id'))
    assignee = relationship('User', back_populates='assigned_tasks', foreign_keys=[assignee_id])

    def status_persian(self):
        if self.status == TaskStatus.TODO:
            return 'انجام نشده :x:'
        elif self.status == TaskStatus.DONE:
            return 'انجام شده :white_check_mark:'
        elif self.status == TaskStatus.SUSPENDED:
            return 'معلق :o:'
        else:
            return 'نامعلوم'

    def assign_date_jalali(self):
        gregorian_datetime = datetime.fromtimestamp(self.assign_date / 1000.0)
        persian_datetime = jdt.fromgregorian(datetime=gregorian_datetime, locale=FA_LOCALE)
        return persian_datetime.strftime("%A، %Y/%m/%d %H:%M")

    async def description_normalized(self, db: Session, ld: LimooDriver, workspace_id: str):
        mentioned_usernames = MENTION_USERNAME_PATTERN.findall(self.description)
        mentioned_users_map = {
            username: (await get_or_add_user_by_username(db, ld, username, workspace_id)).display_name_considering_member(db, workspace_id)
            for username in mentioned_usernames
        }

        result = re.sub(MENTION_USERNAME_PATTERN, lambda match: '@' + mentioned_users_map.get(match.group(1)), self.description)
        result = (result.replace('#فوری', '#_فوری')
                  .replace('#آنی', '#_آنی'))
        return result

    def direct_link(self):
        link = f"https://{LIMOO_HOST}/Limonad/"
        if self.thread_root_id:
            link += f"workspace/{self.workspace.name}/conversation/{self.conversation_id}/thread/{self.thread_root_id}/message/{self.id}"
        else:
            link += f"workspace/{self.workspace.name}/conversation/{self.conversation_id}/message/{self.id}"
        return link

    async def to_string(self, db: Session, ld: LimooDriver, workspace_id: str):
        attachments_table = ""
        if self.attachments:
            attachments_table = (
                "|*ضمیمه‌ها*||\n"
                "|---|---|\n"
            )
            for attachment in self.attachments:
                attachments_table += attachment.table_row()

        return (
            f"{await self.description_normalized(db, ld, workspace_id)}\n\n"
            f"{attachments_table}\n"
            "||*اطلاعات کار*|\n"
            "|---|---|\n"
            f"|:bust_in_silhouette: مسئول|{self.assignee.avatar_and_display_name_considering_member(db, workspace_id) if self.assignee else EMPTY_ASSIGNEE}|\n"
            f"|:white_circle: وضعیت|{self.status_persian()}|\n"
            f"|:date: زمان تخصیص|{self.assign_date_jalali()}|\n"
            f"|:writing_hand: سازنده|{self.reporter.avatar_and_display_name_considering_member(db, workspace_id)}|\n"
            f"|:link: لینک پیام|{self.direct_link()}|\n"
            f"|:radio_button: عملیات|[[اتمام کار]({DONE_TASK_TEMPLATE.format(self.id)})] [[حذف کار]({DELETE_TASK_TEMPLATE.format(self.id)})]|\n"
        )


def attachments_from_event(msg_event):
    if 'files' not in msg_event['data']['message'] or not msg_event['data']['message']['files']:
        return []
    return [Attachment(hash=file['hash'], name=file['name'], mime_type=file['mime_type'], size=file['size']) for
            file in msg_event['data']['message']['files']]


def update_task(db: Session, task: Task, msg_event, assignee: User, status: TaskStatus):
    message_text_ = msg_event['data']['message']['text']

    assignee_id = assignee and assignee.id
    assign_date = task.assign_date
    if task.assignee_id != assignee_id:
        assign_date = current_millis()

    done_date = task.done_date
    if task.status != status and status == TaskStatus.TODO:
        done_date = current_millis()

    update_statement = update(Task).where(Task.id == task.id).values({
        Task.description: message_text_,
        Task.assignee_id: assignee_id,
        Task.status: status,
        Task.assign_date: assign_date,
        Task.done_date: done_date,
    })
    db.execute(update_statement)
    db.commit()


async def add_task(db: Session, ld: LimooDriver, msg_event, reporter: User, assignee: User, status: TaskStatus) -> Task:
    conversation = await get_or_add_conversation(db, ld, msg_event)
    assign_date = current_millis()

    new_task = Task(id=msg_event['data']['message']['id'], description=msg_event['data']['message']['text'],
                    direct_reply_message_id=msg_event['data']['message']['direct_reply_message_id'],
                    thread_root_id=msg_event['data']['message']['thread_root_id'],
                    status=status, create_at=msg_event['data']['message']['create_at'],
                    attachments=attachments_from_event(msg_event),
                    conversation_id=conversation.id, workspace_id=msg_event['data']['workspace_id'],
                    reporter=reporter, assignee=assignee, assign_date=assign_date)
    return create_model(db, new_task)


def delete_task(db: Session, task_id: str):
    delete_statement = delete(Task).where(Task.id == task_id)
    db.execute(delete_statement)
    db.commit()
