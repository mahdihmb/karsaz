from sqlalchemy.orm import Session

from constants import WORKSPACE_WORDS, GROUP_WORDS, UNASSIGNED_WORDS, ME_WORDS, SENDING_MSG_SIZE_LIMIT
from limoo import LimooDriver
from models.task import Task, TaskStatus
from models.user import get_or_add_user_by_username, get_or_add_user_by_id
from utils import send_msg_in_thread


async def handle_list_of_tasks(ld: LimooDriver, db: Session, event, who: str, scope: str):
    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']
    user_id_ = event['data']['message']['user_id']

    conversation_label = "مکالمه" if event['data']['conversation_type'] == 'direct' else "گروه"

    in_workspace = scope and scope in WORKSPACE_WORDS
    mentioned_user = who and who.startswith('@') and await get_or_add_user_by_username(db, ld, who[1:], workspace_id_)
    mentioned_user = mentioned_user or await get_or_add_user_by_id(db, ld, user_id_, workspace_id_)
    assignee_id = mentioned_user.id

    sending_message = ":clipboard: "
    if who in GROUP_WORDS:
        tasks = db.query(Task).where(
            Task.conversation_id == conversation_id_,
            Task.status == TaskStatus.TODO,
        ).all()
        sending_message += f'لیست کارهای **این {conversation_label}** ({len(tasks)}):\n'
    elif who in UNASSIGNED_WORDS:
        tasks = db.query(Task).where(
            Task.assignee_id == None,
            Task.conversation_id == conversation_id_,
            Task.status == TaskStatus.TODO,
        ).all()
        sending_message += f'لیست کارهای *بدون مسئول* **این {conversation_label}** ({len(tasks)}):\n'
    else:
        if (who in ME_WORDS or assignee_id == user_id_) and in_workspace:
            tasks = db.query(Task).where(
                Task.assignee_id == assignee_id,
                Task.workspace_id == workspace_id_,
                Task.status == TaskStatus.TODO,
            ).all()
            sending_message += f'لیست کارهای {mentioned_user.mention()} در **این فضا** ({len(tasks)}):\n'
        else:
            tasks = db.query(Task).where(
                Task.assignee_id == assignee_id,
                Task.conversation_id == conversation_id_,
                Task.status == TaskStatus.TODO,
            ).all()
            sending_message += f'لیست کارهای {mentioned_user.mention()} در **این {conversation_label}** ({len(tasks)}):\n'

    for task in tasks:
        sending_message += '***\n' + await task.to_string(db, ld, workspace_id_)
        if len(sending_message) >= SENDING_MSG_SIZE_LIMIT:
            await send_msg_in_thread(ld, sending_message, event)
            sending_message = ""

    if not tasks:
        sending_message += "[*موردی وجود ندارد*]\n"

    if sending_message:
        await send_msg_in_thread(ld, sending_message, event)
