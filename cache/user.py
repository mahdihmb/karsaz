from limoo import LimooDriver

username_to_user = {}
id_to_user = {}


async def load_json_users(ld: LimooDriver, workspace_id: str):
    global username_to_user, id_to_user
    w_users = await ld.workspaces.users(workspace_id)
    for user in w_users:
        username_to_user[user['username']] = user
        id_to_user[user['id']] = user


async def get_user_json_by_username(ld: LimooDriver, username: str, workspace_id: str):
    global username_to_user
    if username not in username_to_user:
        await load_json_users(ld, workspace_id)
    return username_to_user.get(username)


async def get_user_json_by_id(ld: LimooDriver, id: str, workspace_id: str):
    global id_to_user
    if id not in id_to_user:
        await load_json_users(ld, workspace_id)
    return id_to_user.get(id)


def calc_user_display_name(user_json):
    if not user_json:
        return None

    if user_json['first_name'] is None and user_json['last_name'] is None:
        return user_json['nickname'] or user_json['username']
    elif user_json['first_name'] is None:
        return user_json['last_name']
    elif user_json['last_name'] is None:
        return user_json['first_name']
    else:
        return ' '.join([user_json['first_name'], user_json['last_name']])
