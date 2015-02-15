def enum(**enums):
    return type('Enum', (), enums)

Method = enum(GET="GET", POST="POST")


class Perm_Sys(object):
    # views/user.py api
    user_list_group = {Method.GET: ["auth-groups-list"]}
    user_create_group = {Method.POST: ["auth-groups-add"]}
    user_detail_modify_group = {
        Method.GET: ["auth-groups-list"],
        Method.POST: ["auth-groups-edit"]}
    user_delete_group = {Method.POST: ["auth-groups-delete"]}

    user_list_user = {Method.GET: ["auth-user-list"]}
    user_create_user = {
        Method.GET: ["auth-user-add"],
        Method.POST: ["auth-user-add"]}
    user_detail_modify_user = {
        Method.GET: ["auth-user-list"],
        Method.POST: ["auth-user-edit"]}
    user_delete_user = {Method.POST: ["auth-user-delete"]}
    user_list_perm = {Method.GET: ["auth-permission-list"]}

    user_user_active = {Method.POST: ["auth-active-user"]}
    user_group_perm_list = {
        Method.GET: ["grant-perms-to-group"],
        Method.POST: ["grant-perms-to-group"]}
    user_user_perm_list = {
        Method.GET: ["grant-perms-to-user"],
        Method.POST: ["grant-perms-to-user"]}
