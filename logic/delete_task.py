from sqlalchemy.orm import Session

from limoo import LimooDriver
from models.task import Task, delete_task
from utils import remove_reactions, send_msg_in_thread


async def handle_delete_task(ld: LimooDriver, db: Session, event, task_id: str, message_deleted=False):
    task = db.get(Task, task_id)
    if not task:
        return

    if message_deleted or task.reporter_id == event['data']['message']['user_id']:
        delete_task(db, task_id)
        if not message_deleted:
            remove_reactions(ld, task.workspace_id, task.conversation_id, task_id, ['large_blue_circle', 'white_check_mark'])
    else:
        await send_msg_in_thread(ld, 'فقط سازنده کار میتونه اون رو حذف کنه', event, reply=True)
