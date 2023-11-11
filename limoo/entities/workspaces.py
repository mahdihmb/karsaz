import urllib.parse


class Workspaces:

    def __init__(self, driver):
        self._driver = driver

    _MINE = 'user/my_workspaces'
    async def mine(self):
        return await self._driver._execute_api_get(self._MINE)

    _GET = 'workspace/items/{}'
    async def get(self, workspace_id):
        return await self._driver._execute_api_get(self._GET.format(workspace_id))

    _GET_MEMBERS = 'workspace/items/{}/members'
    async def members(self, workspace_id):
        return await self._driver._execute_api_get(self._GET_MEMBERS.format(workspace_id))

    _WORKSPACE_ALL_MEMBERS = 'workspace/items/{}/members/search?page=0&per_page=-1'
    async def getAllMembers(self, workspace_id=None):
        if workspace_id is None:
            raise "Workspace_id is needed"
        return await self._driver._execute_api_post(self._WORKSPACE_ALL_MEMBERS.format(workspace_id), body={"term":""})
