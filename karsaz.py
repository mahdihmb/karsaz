import asyncio
import contextlib
import re
import time

from sqlalchemy import and_
from sqlalchemy.orm import Session

from limoo import LimooDriver
from limoo_driver_provider import getLimooDriver
from models import SessionLocal
from models.task import add_task, get_task, update_task, TaskStatus, delete_task, Task, MENTION_USERNAME_PATTERN
from models.user import get_or_add_user_by_username, get_or_add_user_by_id

ME_WORDS = ['من', 'خودم', 'بنده', 'اینجانب',
            'اساین به من', 'اساین به خودم', 'اساین به بنده', 'اساین به اینجانب',
            'تخصیص به من', 'تخصیص به خودم', 'تخصیص به بنده', 'تخصیص به اینجانب',
            'مال من', 'مال خودم', 'مال بنده', 'مال اینجانب',
            'مربوط به من', 'مربوط به خودم', 'مربوط به بنده', 'مربوط به اینجانب', ]

UNASSIGNED_WORDS = ['رو هوا', 'مال هیچ کس', 'مال هیچکس', 'مال هیچکی',  'مال هیشکی',
                    'بدون تخصیص', 'بدون‌تخصیص', 'بی تخصیص', 'بی‌تخصیص',
                    'بی صاحب', 'بی‌صاحب', 'بدون صاحب', 'بدون‌صاحب',
                    'بی مسئول', 'بی‌مسئول', 'بدون مسئول', 'بدون‌مسئول',
                    'بی انجام دهنده', 'بی‌انجام دهنده', 'بدون انجام دهنده', 'بدون‌انجام دهنده',
                    'بی انجام‌دهنده', 'بی‌انجام‌دهنده', 'بدون انجام‌دهنده', 'بدون‌انجام‌دهنده', ]

GROUP_WORDS = ['گروه', 'این گروه', 'گروپ', 'این گروپ', 'مکالمه', 'این مکالمه',
               'اعضا', 'کاربران', 'همه', 'اینجا', 'همینجا', ]

WORKSPACE_WORDS = ['فضا', 'فضای کاری', 'فضای‌کاری', 'ورک اسپیس', 'ورک‌‌اسپیس', 'تیم', ]

LIST_COMMAND = re.compile(
    r'^\s*/کارساز\s+'
    r'(?:(?:لیست|فهرست|مجموعه)\s+)?'
    r'(?:(?:همه|همه‌ی|همه ی|تمام|کل)\s+)?'
    r'(?:لیست|فهرست|مجموعه|موارد|اساین|اساینی|اساین شده|اساین شده به|مسئول|تخصیص|تخصیص یافته|تخصیص یافته به|تودو|تو دو|کارهای|کارای|کار های|کارها|کار ها|تسکهای|تسکای|تسک های|تسکها|تسک ها)'
    r'(?:\s+(?:باز|تودو|تو دو|انجام نشده|دان نشده|نیازمند اقدام|نیازمند بررسی|نیازمند توجه|منتظر|منتظر اقدام|منتظر بررسی|منتظر توجه))?'
    r'(?:\s+(' + '|'.join(ME_WORDS) + '|' + '|'.join(UNASSIGNED_WORDS) + '|' + '|'.join(
        GROUP_WORDS) + '|@\S+)(?:\s+(?:(?:در|تو|توی|داخل|درون)\s+)?(' + '|'.join(WORKSPACE_WORDS) + '))?)?(?:\s+.*)?'
)

HELP_WORDS = ['کمک', 'چیه', 'چی هست', 'هلپ', 'help', 'معرفی', 'آشنایی', 'توضیح', 'چیست', 'چی کار', 'چیکار', '؟', '\?',
              'کارت چیه', 'کارش چیه', ]

HELP_COMMAND = re.compile(
    r'^\s*/کارساز\s+'
    r'(?:' + '|'.join(HELP_WORDS) + ')'
)

HELP_COMMAND_IN_PV = re.compile(
    r'^\s*/(?:' + '|'.join(HELP_WORDS) + ')'
)

TASK_TAG_PATTERN = re.compile(r'(?<!\w)(#Task|#Assigned|#کار)(?!\w)', re.IGNORECASE)
DONE_TAG_PATTERN = re.compile(r'(?<!\w)(#Done|#Done_and_Approved)(?!\w)', re.IGNORECASE)

SENDING_MSG_SIZE_LIMIT = 5000


async def handle_task_create_or_edit(event):
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
                asyncio.create_task(ld.messages.add_reaction(workspace_id_, conversation_id_, message_id_, 'white_check_mark'))
            elif not marked_as_done and pre_status == TaskStatus.DONE:
                asyncio.create_task(ld.messages.remove_reaction(workspace_id_, conversation_id_, message_id_, 'white_check_mark'))
        else:
            asyncio.create_task(add_task(db, ld, event, reporter, assignee, status))
            asyncio.create_task(ld.messages.add_reaction(workspace_id_, conversation_id_, message_id_, 'large_blue_circle'))
            if marked_as_done:
                asyncio.create_task(ld.messages.add_reaction(workspace_id_, conversation_id_, message_id_, 'white_check_mark'))
    else:
        if task:
            delete_task(db, task)
            asyncio.create_task(ld.messages.remove_reaction(workspace_id_, conversation_id_, message_id_, 'large_blue_circle'))
            if task.status == TaskStatus.DONE:
                asyncio.create_task(ld.messages.remove_reaction(workspace_id_, conversation_id_, message_id_, 'white_check_mark'))


async def handle_task_delete(event):
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


async def handle_list_of_tasks(event, who: str, scope: str):
    global ld, bot_user

    db = SessionLocal()

    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']
    message_id_ = event['data']['message']['id']
    thread_root_id_ = event['data']['message']['thread_root_id']
    user_id_ = event['data']['message']['user_id']

    conversation_representation = "مکالمه" if event['data']['conversation_type'] == 'direct' else "گروه"

    sending_msg_thread_root_id = thread_root_id_ if thread_root_id_ else message_id_

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
        sending_message += f'لیست کارهای **این {conversation_representation}** ({len(tasks)}):\n'
    elif who in UNASSIGNED_WORDS:
        tasks = db.query(Task).where(and_(
            Task.assignee_id == None,
            Task.conversation_id == conversation_id_,
            Task.status == TaskStatus.TODO,
        )).all()
        sending_message += f'لیست کارهای *بدون مسئول* **این {conversation_representation}** ({len(tasks)}):\n'
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
            sending_message += f'لیست کارهای {mentioned_user.mention()} در **این {conversation_representation}** ({len(tasks)}):\n'

    for task in tasks:
        sending_message += '***\n' + await task.to_string(db, ld, workspace_id_)
        if len(sending_message) >= SENDING_MSG_SIZE_LIMIT:
            time.sleep(0.1)
            await ld.messages.create(workspace_id_, conversation_id_, sending_message,
                                     thread_root_id=sending_msg_thread_root_id)
            sending_message = ""

    if not tasks:
        sending_message += "*موردی وجود ندارد*\n"

    if sending_message:
        time.sleep(0.1)
        await ld.messages.create(workspace_id_, conversation_id_, sending_message,
                                 thread_root_id=sending_msg_thread_root_id)


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

    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']
    message_id_ = event['data']['message']['id']
    thread_root_id_ = event['data']['message']['thread_root_id']

    sending_msg_thread_root_id = thread_root_id_ if thread_root_id_ else message_id_

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
    )

    time.sleep(0.1)
    await ld.messages.create(workspace_id_, conversation_id_, help_message,
                             thread_root_id=sending_msg_thread_root_id)


async def on_event(event):
    global ld, bot_user

    if 'message' in event['data'] and (
            event['data']['message']['type'] or event['data']['message']['user_id'] == bot_user['id']):
        return

    if event['event'] == 'message_created':
        try:
            message_text_ = event['data']['message']['text']

            list_command_match = LIST_COMMAND.match(message_text_)
            help_command_match = HELP_COMMAND.match(message_text_)
            help_command_in_pv_match = HELP_COMMAND_IN_PV.match(message_text_)
            if list_command_match:
                await handle_list_of_tasks(event, list_command_match.group(1), list_command_match.group(2))
            elif message_text_.strip() == f"@{bot_user['username']}" or help_command_match \
                    or event['data']['conversation_type'] == 'direct' and help_command_in_pv_match:
                await help_message(event)
            else:
                await handle_task_create_or_edit(event)
        finally:
            await view_log(event)
    elif event['event'] == 'message_edited':
        await handle_task_create_or_edit(event)
    elif event['event'] == 'message_deleted':
        await handle_task_delete(event)


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
