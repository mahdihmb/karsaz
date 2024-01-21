import asyncio
import contextlib
import re
import time

from limoo_driver_provider import getLimooDriver
from models import SessionLocal
from models.task import add_task, get_task, update_task, TaskStatus, delete_task
from models.user import get_or_add_user_by_username, User, get_or_add_user_by_id

ME_WORDS = ['من', 'خودم', 'بنده', 'اینجانب']
GROUP_WORDS = ['گروه', 'گروپ', 'مکالمه', 'اعضا', 'کاربران', 'همه']
WORKSPACE_WORDS = ['فضا', 'فضای کاری', 'ورک اسپیس', 'تیم']

LIST_COMMAND = re.compile(
    r'^/کارساز\s+'
    r'(?:(?:لیست|فهرست|مجموعه)\s+)?'
    r'(?:(?:همه|همه‌ی|همه ی|تمام|کل)\s+)?'
    r'(?:لیست|فهرست|مجموعه|موارد|اساین|اساینی|اساین شده|اساین شده به|تخصیص|تخصیص یافته|تخصیص یافته به|تودو|تو دو|کارهای|کارای|کار های|کارها|کار ها|تسکهای|تسکای|تسک های|تسکها|تسک ها)'
    r'(?:\s+(?:باز|تودو|تو دو|انجام نشده|دان نشده|نیازمند اقدام|نیازمند بررسی|نیازمند توجه|منتظر|منتظر اقدام|منتظر بررسی|منتظر توجه))?'
    r'(?:\s+(' + '|'.join(ME_WORDS) + '|' + '|'.join(
        GROUP_WORDS) + '|@\S+)(?:\s+(?:(?:در|تو|توی|داخل|درون)\s+)?(' + '|'.join(WORKSPACE_WORDS) + '))?)?(?:\s+.*)?'
)

TASK_TAG_PATTERN = re.compile(r'(?<!\w)(#Task|#Assigned|#کار)(?!\w)', re.IGNORECASE)
DONE_TAG_PATTERN = re.compile(r'(?<!\w)(#Done|#Done_and_Approved)(?!\w)', re.IGNORECASE)
MENTION_USERNAME_PATTERN = re.compile(r'@(\S+)')


async def task_create_or_edit(event):
    global ld, bot_user

    db = SessionLocal()

    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']
    message_id_ = event['data']['message']['id']
    thread_root_id_ = event['data']['message']['thread_root_id']
    message_text_ = event['data']['message']['text']
    user_id_ = event['data']['message']['user_id']

    sending_msg_thread_root_id = thread_root_id_ if thread_root_id_ else message_id_

    task = get_task(db, message_id_)
    reporter = await get_or_add_user_by_id(db, ld, user_id_, workspace_id_)

    sending_message = None
    if TASK_TAG_PATTERN.search(message_text_):
        marked_as_done = DONE_TAG_PATTERN.search(message_text_)
        status = TaskStatus.DONE if marked_as_done else TaskStatus.TODO

        mentioned_usernames = [u for u in MENTION_USERNAME_PATTERN.findall(message_text_) if
                               u != bot_user['username']]

        assignee = None
        for username in mentioned_usernames:
            user = await get_or_add_user_by_username(db, ld, username, workspace_id_)
            if not user.is_bot:
                assignee = user
                break

        if task:
            pre_assignee = task.assignee
            pre_status = task.status

            update_task(db, task, event, assignee, status)

            if not marked_as_done:
                if pre_assignee != assignee:
                    sending_message = f'{reporter.display_name} این کار را ' + (
                        f'به @{assignee.username} تخصیص داد' if assignee else 'بدون تخصیص کرد')
                if pre_status == TaskStatus.DONE:
                    if sending_message:
                        sending_message += ' و دوباره کار را باز کرد'
                    else:
                        sending_message = f'{reporter.display_name} این کار را ' + (
                            f'برای @{assignee.username}' if assignee else 'بدون تخصیص') + ' دوباره باز کرد'
        else:
            await add_task(db, ld, event, reporter, assignee, status)

            if not marked_as_done:
                sending_message = 'کار جدید ' + (
                    f'برای @{assignee.username}' if assignee else 'بدون تخصیص') + f' توسط {reporter.display_name} ایجاد شد'
    else:
        if task:
            delete_task(db, task)
            sending_message = f'این کار توسط {reporter.display_name} حذف شد'

    if sending_message:
        time.sleep(1)
        await ld.messages.create(workspace_id_, conversation_id_, sending_message,
                                 thread_root_id=sending_msg_thread_root_id, direct_reply_message_id=message_id_)


async def task_delete(event):
    global ld, bot_user

    db = SessionLocal()

    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']
    message_id_ = event['data']['message']['id']
    thread_root_id_ = event['data']['message']['thread_root_id']
    user_id_ = event['data']['message']['user_id']

    task = get_task(db, message_id_)
    if task:
        delete_task(db, task)

        if thread_root_id_:
            reporter = await get_or_add_user_by_id(db, ld, user_id_, workspace_id_)
            sending_message = f'این کار توسط {reporter.display_name} حذف شد'
            time.sleep(1)
            await ld.messages.create(workspace_id_, conversation_id_, sending_message,
                                     thread_root_id=thread_root_id_, direct_reply_message_id=message_id_)


async def on_event(event):
    global ld, bot_user

    if event['data']['message']['type'] or event['data']['message']['user_id'] == bot_user['id']:
        return

    if event['event'] == 'message_created':
        message_text_ = event['data']['message']['text']

        match = LIST_COMMAND.match(message_text_)
        if match:
            print(match.group(1), match.group(2))
            # FIXME
            # FIXME: if request for tasks of workspace, each group has a separate section
        else:
            await task_create_or_edit(event)
    elif event['event'] == 'message_edited':
        await task_create_or_edit(event)
    elif event['event'] == 'message_deleted':
        await task_create_or_edit(event)


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
