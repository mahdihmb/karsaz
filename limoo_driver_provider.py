import os

from limoo import LimooDriver

ld = None


def getLimooDriver() -> LimooDriver:
    global ld

    #  TODO: get db user/pass and url from ENV
    bot_username = os.environ.get('KARSAZ_BOT_USERNAME')
    bot_password = os.environ.get('KARSAZ_BOT_PASSWORD')
    if bot_username is None or bot_password is None:
        raise "required envs not set: KARSAZ_BOT_USERNAME, KARSAZ_BOT_PASSWORD"

    if not ld:
        ld = LimooDriver('web.limoo.im', bot_username, bot_password)
    return ld
