import asyncio
import contextlib
import re
import time

from limoo_driver_provider import getLimooDriver
from models import SessionLocal
from models.task import add_task, get_task, update_task, TaskStatus

TASK_TAG_PATTERN = re.compile(r'(?<!\w)(#Task|#Assigned|#کار)(?!\w)', re.IGNORECASE)
DONE_TAG_PATTERN = re.compile(r'(?<!\w)(#Done|#Done_and_Approved)(?!\w)', re.IGNORECASE)
MENTION_USERNAME_PATTERN = re.compile(r'@(\S+)')


async def on_event(event):
    global ld, bot_user

    # TODO: handle conversation/workspace display_name changes
    # TODO: use #Postponed tag? (for example for manual suspending?)

    if ((event['event'] == 'message_created' or event['event'] == 'message_edited')
            and not (event['data']['message']['type'] or event['data']['message']['user_id'] == bot_user['id'])):
        print('*********************************************************************')
        print(event['event'], event['data'])
        print('*********************************************************************')

        db = SessionLocal()

        workspace_id_ = event['data']['workspace_id']
        conversation_id_ = event['data']['message']['conversation_id']
        message_id_ = event['data']['message']['id']
        thread_root_id_ = event['data']['message']['thread_root_id']
        message_text_ = event['data']['message']['text']

        sending_msg_thread_root_id = thread_root_id_ if thread_root_id_ else message_id_

        if TASK_TAG_PATTERN.search(message_text_):
            marked_as_done = DONE_TAG_PATTERN.search(message_text_)
            status = TaskStatus.DONE if marked_as_done else TaskStatus.TODO

            usernames = [u for u in MENTION_USERNAME_PATTERN.findall(message_text_) if u != bot_user['username']]
            assignee_username = usernames[0] if len(usernames) else None

            message = None

            task = get_task(db, event)
            if task:
                pre_assignee_username = task.assignee_username
                pre_status = task.status

                update_task(db, event, assignee_username, status)

                if not marked_as_done:
                    if pre_assignee_username != assignee_username:
                        message = f'این کار به @{assignee_username} تخصیص یافت' if assignee_username else 'این کار بدون تخصیص شد'
                    if pre_status == TaskStatus.DONE:
                        if message:
                            message += ' و دوباره باز شد'
                        else:
                            message = f'این کار برای @{assignee_username} دوباره باز شد' if assignee_username else 'این کار بدون تخصیص دوباره باز شد'
                    #  TODO: notify about description changes?
            else:
                await add_task(db, ld, event, assignee_username, status)

                if not marked_as_done:
                    message = f'کار جدید برای @{assignee_username} ایجاد شد' if assignee_username else 'کار جدید بدون تخصیص ایجاد شد'

            if message:
                time.sleep(1)
                await ld.messages.create(workspace_id_, conversation_id_, message,
                                         thread_root_id=sending_msg_thread_root_id, direct_reply_message_id=message_id_)
        else:
            # TODO: check if tag removed, remove from DB (only if task exists)
            pass


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
