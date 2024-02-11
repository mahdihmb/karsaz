import asyncio
import contextlib

from constants import LIST_COMMAND, HELP_COMMAND, \
    HELP_COMMAND_IN_PV, DONE_TASK_COMMAND, DELETE_TASK_COMMAND, HELP_WORDS
from limoo_driver_provider import getLimooDriver
from logic.create_or_edit_task import handle_create_or_edit_task
from logic.delete_task import handle_delete_task
from logic.done_task import handle_done_task
from logic.help_message import handle_help_message
from logic.list_of_tasks import handle_list_of_tasks
from models import SessionLocal


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
                        or event['data']['conversation_type'] == 'direct' and help_command_in_pv_match \
                        or message_text_.strip() in HELP_WORDS:
                    await handle_help_message(ld, event)
                elif list_command_match:
                    await handle_list_of_tasks(ld, db, event, list_command_match.group(1), list_command_match.group(2))
                elif done_task_command_match:
                    await handle_done_task(ld, db, event, done_task_command_match.group(1))
                elif delete_task_command_match:
                    await handle_delete_task(ld, db, event, delete_task_command_match.group(1))
                else:
                    await handle_create_or_edit_task(ld, db, event)
            finally:
                await view_log(event)
        elif event['event'] == 'message_edited':
            await handle_create_or_edit_task(ld, db, event)
        elif event['event'] == 'message_deleted':
            await handle_delete_task(ld, db, event, event['data']['message']['id'], True)


async def view_log(event):
    global ld

    thread_root_id_ = event['data']['message']['thread_root_id']
    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']

    if thread_root_id_:
        await ld.threads.view_log(workspace_id_, thread_root_id_)
    else:
        await ld.conversations.view_log(workspace_id_, conversation_id_)


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
