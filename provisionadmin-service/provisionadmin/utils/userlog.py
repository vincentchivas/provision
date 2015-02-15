# -*- coding: utf-8 -*-
import types
from provisionadmin.model.user import UserLog, Permission, User, Group
from provisionadmin.model.preset import classing_model


def _save_to_user_log(user_name, operator, model_id, model_name):
    if model_name in ["user", "groups", "exportpreset"]:
        # model_alias = Permission._get_model_alias(str(model_name))
        model_title = ""
        if model_name == "user":
            user_detail = User.find({"_id": int(model_id)}, one=True)
            model_title = user_detail.get("user_name", "")
        elif model_name == "groups":
            group_detail = Group.find({"_id": int(model_id)}, one=True)
            model_title = group_detail.get("group_name", "")
        else:
            model_alias = Permission._get_model_alias(str(model_name))
            operator = operator + "-" + model_alias
        instance = UserLog.new(
            user_name, operator, model_name, model_id, model_title)
        UserLog.save(instance)
    else:
        Model_Name = classing_model(str(model_name))
        model_alias = Permission._get_model_alias(str(model_name))
        item = Model_Name.find(
            {"id": int(model_id)}, fields={"_id": 0}, one=True)
        model_title = ""
        msg = operator + "-" + model_alias
        if item:
            model_title = item.get("title")
            if not model_title:
                model_title = item.get("name")
            instance = UserLog.new(
                user_name, msg, model_name, model_id, model_title)
            UserLog.save(instance)
        else:
            instance = UserLog.new(
                user_name, msg, model_name, model_id, model_title)
            UserLog.save(instance)


def _save_to_log(user_name, operator, model_id_list, model_name):
    if model_id_list:
        if isinstance(model_id_list, types.ListType):
            for model_id in model_id_list:
                _save_to_user_log(user_name, operator, model_id, model_name)
        else:
            _save_to_user_log(user_name, operator, model_id_list, model_name)


def _remove_other_log():
    UserLog.remove({"user_name": "admin"})


def _save_del_action_log(user_name, model_list, model_name):
    if model_list:
        for model_item in model_list:
            model_id = model_item.get("id")
            model_title = model_item.get("title")
            model_alias = Permission._get_model_alias(str(model_name))
            msg = "删除" + "-" + model_alias
            if not model_title:
                model_title = model_item.get("name")
            instance = UserLog.new(
                user_name, msg, model_name, model_id, model_title)
            UserLog.save(instance)
    else:
        return None
