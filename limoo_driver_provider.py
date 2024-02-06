import os

from limoo import LimooDriver

LIMOO_HOST = os.getenv('LIMOO_HOST') or 'web.limoo.im'

ld = None


def getLimooDriver() -> LimooDriver:
    global ld

    if not ld:
        bot_username = os.environ.get('KARSAZ_BOT_USERNAME')
        bot_password = os.environ.get('KARSAZ_BOT_PASSWORD')
        if bot_username is None or bot_password is None:
            raise "required envs not set: KARSAZ_BOT_USERNAME, KARSAZ_BOT_PASSWORD"
        ld = LimooDriver(LIMOO_HOST, bot_username, bot_password)

    return ld
