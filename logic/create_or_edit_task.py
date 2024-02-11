import asyncio

from sqlalchemy.orm import Session

from constants import TASK_TAG_PATTERN, DONE_TAG_PATTERN, MENTION_USERNAME_PATTERN
from limoo import LimooDriver
from models.task import Task, TaskStatus, update_task, add_task, delete_task
from models.user import get_or_add_user_by_id, get_or_add_user_by_username
from utils import add_reactions, remove_reactions


async def handle_create_or_edit_task(ld: LimooDriver, db: Session, event):
    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']
    message_id_ = event['data']['message']['id']
    message_text_ = event['data']['message']['text']
    doer_user_id_ = event['data']['doer_user_id'] or event['data']['message']['user_id']

    task = db.get(Task, message_id_)
    if task and task.reporter_id != doer_user_id_:
        return;

    doer_user = await get_or_add_user_by_id(db, ld, doer_user_id_, workspace_id_)

    if TASK_TAG_PATTERN.search(message_text_):
        marked_as_done = DONE_TAG_PATTERN.search(message_text_)
        status = TaskStatus.DONE if marked_as_done else TaskStatus.TODO

        mentioned_usernames = MENTION_USERNAME_PATTERN.findall(message_text_)
        mentioned_users = [await get_or_add_user_by_username(db, ld, username, workspace_id_) for username in mentioned_usernames]

        assignee = next((user for user in mentioned_users if not user.is_bot), None)

        if task:
            pre_assignee = task.assignee
            pre_status = task.status

            update_task(db, task, event, assignee, status)

            if marked_as_done and pre_status != TaskStatus.DONE:
                add_reactions(ld, workspace_id_, conversation_id_, message_id_, ['white_check_mark'])
            elif not marked_as_done and pre_status == TaskStatus.DONE:
                remove_reactions(ld, workspace_id_, conversation_id_, message_id_, ['white_check_mark'])
        else:
            asyncio.create_task(add_task(db, ld, event, doer_user, assignee, status))
            add_reactions(ld, workspace_id_, conversation_id_, message_id_, ['large_blue_circle'])
            if marked_as_done:
                add_reactions(ld, workspace_id_, conversation_id_, message_id_, ['white_check_mark'])
    else:
        if task:
            delete_task(db, task.id)
            remove_reactions(ld, workspace_id_, conversation_id_, message_id_, ['large_blue_circle', 'white_check_mark'])
