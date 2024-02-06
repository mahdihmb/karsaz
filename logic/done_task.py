from sqlalchemy.orm import Session

from limoo import LimooDriver
from models.task import Task, update_task, TaskStatus
from utils import add_reactions, send_msg_in_thread


async def handle_done_task(ld: LimooDriver, db: Session, event, task_id: str):
    task = db.get(Task, task_id)
    if not task:
        return

    if task.reporter_id == event['data']['message']['user_id']:
        update_task(db, task, event, task.assignee, TaskStatus.DONE)
        add_reactions(ld, task.workspace_id, task.conversation_id, task_id, ['white_check_mark'])
    else:
        await send_msg_in_thread(ld, 'فقط سازنده کار میتونه وضعیت اون رو تغییر بده', event, reply=True)
