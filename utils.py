import asyncio
import time

from limoo import LimooDriver

current_millis = lambda: int(round(time.time() * 1000))


async def send_msg_in_thread(ld: LimooDriver, msg, event, reply=False):
    workspace_id_ = event['data']['workspace_id']
    conversation_id_ = event['data']['message']['conversation_id']
    message_id_ = event['data']['message']['id']
    thread_root_id_ = event['data']['message']['thread_root_id']

    sending_msg_thread_root_id = thread_root_id_ if thread_root_id_ else message_id_

    time.sleep(0.1)
    await ld.messages.create(workspace_id_, conversation_id_, msg, thread_root_id=sending_msg_thread_root_id,
                             direct_reply_message_id=reply and message_id_)


def add_reactions(ld: LimooDriver, workspace_id, conversation_id, message_id, reactions: list):
    for reaction in reactions:
        time.sleep(0.1)
        asyncio.create_task(
            ld.messages.add_reaction(workspace_id, conversation_id, message_id, reaction))


def remove_reactions(ld: LimooDriver, workspace_id, conversation_id, message_id, reactions: list):
    for reaction in reactions:
        time.sleep(0.5)
        asyncio.create_task(
            ld.messages.remove_reaction(workspace_id, conversation_id, message_id, reaction))
