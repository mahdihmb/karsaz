from sqlalchemy import or_
from sqlalchemy.orm import Session

from limoo import LimooDriver
from models.task import Task, delete_task
from utils import remove_reactions, send_msg_in_thread


async def handle_delete_task(ld: LimooDriver, db: Session, event, msg_id: str, message_deleted=False):
    if message_deleted:
        tasks = db.query(Task).where(or_(
            Task.id == msg_id,
            Task.thread_root_id == msg_id,
        )).all()
    else:
        t = db.get(Task, msg_id)
        tasks = [t] if t else []

    if not tasks:
        return

    for task in tasks:
        if message_deleted or task.reporter_id == event['data']['message']['user_id']:
            delete_task(db, task.id)
            if not message_deleted:
                remove_reactions(ld, task.workspace_id, task.conversation_id, task.id, ['large_blue_circle', 'white_check_mark'])
        else:
            await send_msg_in_thread(ld, 'فقط سازنده کار میتونه اون رو حذف کنه', event, reply=True)
