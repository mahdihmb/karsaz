import asyncio
import contextlib
import time

from sqlalchemy import and_
from sqlalchemy.orm import Session

from constants import ME_WORDS, UNASSIGNED_WORDS, GROUP_WORDS, WORKSPACE_WORDS, LIST_COMMAND, HELP_COMMAND, \
    HELP_COMMAND_IN_PV, TASK_TAG_PATTERN, DONE_TAG_PATTERN, SENDING_MSG_SIZE_LIMIT, MENTION_USERNAME_PATTERN, \
    DONE_TASK_COMMAND, DELETE_TASK_COMMAND
from limoo_driver_provider import getLimooDriver
from models import SessionLocal
from models.task import add_task, update_task, TaskStatus, delete_task, Task
from models.user import get_or_add_user_by_username, get_or_add_user_by_id
from utils import send_msg_in_thread, add_reactions, remove_reactions


async def handle_task_create_or_edit(db: Session, event):
    global ld

    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']
    message_id_ = event['data']['message']['id']
    message_text_ = event['data']['message']['text']
    user_id_ = event['data']['message']['user_id']

    task = db.get(Task, message_id_)
    reporter = await get_or_add_user_by_id(db, ld, user_id_, workspace_id_)

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
            asyncio.create_task(add_task(db, ld, event, reporter, assignee, status))
            add_reactions(ld, workspace_id_, conversation_id_, message_id_, ['large_blue_circle'])
            if marked_as_done:
                add_reactions(ld, workspace_id_, conversation_id_, message_id_, ['white_check_mark'])
    else:
        if task:
            delete_task(db, task)
            remove_reactions(ld, workspace_id_, conversation_id_, message_id_, ['large_blue_circle', 'white_check_mark'])


async def handle_task_done(db: Session, event, task_id: str):
    global ld

    task = db.get(Task, task_id)
    if not task:
        return

    if task.reporter_id == event['data']['message']['user_id']:
        update_task(db, task, event, task.assignee, TaskStatus.DONE)
        add_reactions(ld, task.workspace_id, task.conversation_id, task_id, ['white_check_mark'])
    else:
        await send_msg_in_thread(ld, 'فقط سازنده کار میتونه وضعیت اون رو تغییر بده', event, reply=True)


async def handle_task_delete(db: Session, event, task_id: str, message_deleted=False):
    global ld

    task = db.get(Task, task_id)
    if not task:
        return

    if message_deleted or task.reporter_id == event['data']['message']['user_id']:
        delete_task(db, task_id)
        if not message_deleted:
            remove_reactions(ld, task.workspace_id, task.conversation_id, task_id, ['large_blue_circle', 'white_check_mark'])
    else:
        await send_msg_in_thread(ld, 'فقط سازنده کار میتونه اون رو حذف کنه', event, reply=True)


async def handle_list_of_tasks(db: Session, event, who: str, scope: str):
    global ld

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
        tasks = db.query(Task).where(and_(
            Task.assignee_id == None,
            Task.conversation_id == conversation_id_,
            Task.status == TaskStatus.TODO,
        )).all()
        sending_message += f'لیست کارهای *بدون مسئول* **این {conversation_label}** ({len(tasks)}):\n'
    else:
        if (who in ME_WORDS or assignee_id == user_id_) and in_workspace:
            tasks = db.query(Task).where(and_(
                Task.assignee_id == assignee_id,
                Task.workspace_id == workspace_id_,
                Task.status == TaskStatus.TODO,
            )).all()
            sending_message += f'لیست کارهای {mentioned_user.mention()} در **این فضا** ({len(tasks)}):\n'
        else:
            tasks = db.query(Task).where(and_(
                Task.assignee_id == assignee_id,
                Task.conversation_id == conversation_id_,
                Task.status == TaskStatus.TODO,
            )).all()
            sending_message += f'لیست کارهای {mentioned_user.mention()} در **این {conversation_label}** ({len(tasks)}):\n'

    for task in tasks:
        sending_message += '***\n' + await task.to_string(db, ld, workspace_id_)
        if len(sending_message) >= SENDING_MSG_SIZE_LIMIT:
            await send_msg_in_thread(ld, sending_message, event)
            sending_message = ""

    if not tasks:
        sending_message += "*موردی وجود ندارد*\n"

    if sending_message:
        await send_msg_in_thread(ld, sending_message, event)


async def view_log(event):
    global ld

    thread_root_id_ = event['data']['message']['thread_root_id']
    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']

    if thread_root_id_:
        await ld.threads.view_log(workspace_id_, thread_root_id_)
    else:
        await ld.conversations.view_log(workspace_id_, conversation_id_)


async def help_message(event):
    global ld

    help_message = (
        'بات کارساز یه ابزار مدیریت کار (Task Management) هست.\n  \n'
        '**ساخت کار:** شما میتونید با زدن یکی از برچسب‌های `#کار`، `#Task` یا `#Assigned` روی پیامتون، '
        'از روی اون یک کار برای فردی که درون پیام منشن شده بسازید.\n'
        'اگه درون پیام چندین فرد و یا حتی بات‌ها منشن شده باشن، اولین کاربر غیر بات به عنوان «مسئول» کار مشخص میشه.\n  \n'
        '**لیست کارها:** برای مشاهده لیست کارها، میتونید از دستورات زیر (یا شبیه اون‌ها) استفاده کنید:\n'
        '[/کارساز کارهای من](/کارساز کارهای من)\n'
        '[/کارساز کارهای گروه](/کارساز کارهای گروه)\n'
        '`/کارساز کارهای @منشن_فرد`\n'
        '[/کارساز کارهای بدون مسئول](/کارساز کارهای بدون مسئول)\n'
        '[/کارساز کارهای من در فضا](/کارساز کارهای من در فضا)\n  \n'
        '**اتمام کار:** وقتی یه کار انجام شد، سازنده کار با زدن یکی از برچسب‌های `#Done` یا `#Done_and_Approved` روی پیام مربوط به کار، '
        'میتونه وضعیت اون رو به «انجام شده» تغییر بده.\n  \n'
        '**حذف کار:** برای حذف کار، سازنده کار باید برچسب `#کار`، `#Task` یا `#Assigned` رو از روی پیام مربوط به کار برداره.\n  \n'
        '#### نکات:\n'
        '- برای برچسب زدن به پیام، یا باید برچسب رو تو متن پیام تایپ کنید یا از منوی پیام گزینه «برچسب زدن» رو انتخاب کنید (برای برداشتن برچسب هم همچنین).\n'
        '- با ویرایش متن پیامِ مربوط به کار، میتونید توضیحات یا مسئول کار رو تغییر بدید.\n'
        # '- برای اتمام یا حذف کار، علاوه بر ویرایش پیام مربوط به کار، میتونید از لینک‌های عملیات درون جدول لیست کارها هم استفاده کنید.\n'  # TODO
    )

    await send_msg_in_thread(ld, help_message, event)


async def on_event(event):
    global ld, bot_user

    if 'message' in event['data'] and (
            event['data']['message']['type'] or event['data']['message']['user_id'] == bot_user['id']):
        return

    with SessionLocal() as db:
        if event['event'] == 'message_created':
            try:
                message_text_ = event['data']['message']['text']

                help_command_match = HELP_COMMAND.match(message_text_)
                help_command_in_pv_match = HELP_COMMAND_IN_PV.match(message_text_)
                list_command_match = LIST_COMMAND.match(message_text_)
                done_task_command_match = DONE_TASK_COMMAND.match(message_text_)
                delete_task_command_match = DELETE_TASK_COMMAND.match(message_text_)

                if message_text_.strip() == f"@{bot_user['username']}" or help_command_match \
                        or event['data']['conversation_type'] == 'direct' and help_command_in_pv_match:
                    await help_message(event)
                elif list_command_match:
                    await handle_list_of_tasks(db, event, list_command_match.group(1), list_command_match.group(2))
                elif done_task_command_match:
                    await handle_task_done(db, event, done_task_command_match.group(1))
                elif delete_task_command_match:
                    await handle_task_delete(db, event, delete_task_command_match.group(1))
                else:
                    await handle_task_create_or_edit(db, event)
            finally:
                await view_log(event)
        elif event['event'] == 'message_edited':
            await handle_task_create_or_edit(db, event)
        elif event['event'] == 'message_deleted':
            await handle_task_delete(db, event, event['data']['message']['id'], True)


async def listen(ld):
    forever = asyncio.get_running_loop().create_future()
    ld.set_event_handler(lambda event: asyncio.create_task(on_event(event)))
    print("The bot starts listening...")
    await forever


async def main():
    global ld, bot_user
    async with contextlib.AsyncExitStack() as stack:
        ld = getLimooDriver()
        stack.push_async_callback(ld.close)
        bot_user = await ld.users.get()
        await listen(ld)


if __name__ == "__main__":
    # Base.metadata.create_all(bind=engine)
    asyncio.run(main())
