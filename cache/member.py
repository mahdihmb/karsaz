from limoo import LimooDriver

workspace_id_to_user_member_dict = {}


async def load_json_members(ld: LimooDriver, workspace_id: str):
    global workspace_id_to_user_member_dict
    w_members = await ld.workspaces.members(workspace_id)
    if workspace_id not in workspace_id_to_user_member_dict:
        workspace_id_to_user_member_dict[workspace_id] = {}
    for member in w_members:
        workspace_id_to_user_member_dict[workspace_id][member['user_id']] = member


def get_member_json_by_workspace_id_and_user_id(workspace_id: str, user_id: str):
    global workspace_id_to_user_member_dict
    if workspace_id not in workspace_id_to_user_member_dict:
        return None
    return workspace_id_to_user_member_dict[workspace_id].get(user_id)


def calc_member_display_name(member_json):
    if member_json['first_name'] is None and member_json['last_name'] is None:
        return member_json['nickname']
    elif member_json['first_name'] is None:
        return member_json['last_name']
    elif member_json['last_name'] is None:
        return member_json['first_name']
    else:
        return ' '.join([member_json['first_name'], member_json['last_name']])
