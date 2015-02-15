# -*- coding: utf-8 -*-
import simplejson
import zipfile
import logging
import StringIO
from django.http import HttpResponse
from provisionadmin.utils.json import json_response_error, json_response_ok
from provisionadmin.decorator import exception_handler, check_session
from provisionadmin.utils.validate_params import get_valid_params
from provisionadmin.utils.userlog import (_save_to_log, _save_del_action_log)
from provisionadmin.model.preset import (
    classing_model, get_filters, ref_get_presetdata,
    get_export_filters, save_to_ec2, get_ref_rule_preset)
from provisionadmin.utils.respcode import (
    PARAM_ERROR, METHOD_ERROR, DATA_DELETE_COMFIRM, PARAM_REQUIRED,
    DATA_NOT_UPLOAD_TO_PRE, DATA_RELETED_BY_OTHER)
from provisionadmin.utils.common import now_timestamp, unixto_string

from provisionadmin.service.views.resource import refered_icon
from provisionadmin.service.utils.preset_tool import (
    get_children_model, _get_local_package_preset, get_model_list,
    _get_ref_lc_pn, get_predata_model, get_model_detail,
    del_model_with_relations, _check_ref_incon, _get_pre_delete_models)
from provisionadmin.service.utils.load_del import (
    package_one_predata, del_predata)


_LOGGER = logging.getLogger("view")
_ADMIN = "admin"
_LOCAL = "local"
_EC2 = "ec2"
All_FLAG = "all_condition"
DEFAULT_SOURCE = "ofw"
_CANNOT_DEL_IF_RELET = ["aosruledata", "aosstrategy", "aosgesture"]
_REF_BY_ONE_PRESET = [
    "icon", "logo", "aosruledata", "aossharecontent", "aosgesture",
    "aosstrategy", "aosspeeddialdesktop"]
_REF_RULE_MODELS = ["aoslocale", "aospackage", "aosoperator", "aossource"]
_PRESET_STATUS_FIELDS = [
    "last_modified", "first_created", "release", "is_upload_ec2",
    "is_upload_local"]


def clean_save_data(temp_dict):
    for key in temp_dict:
        # 由于前端传了大量没用的字段，对需要的字段进行过滤
        if key in _REF_BY_ONE_PRESET:
            origin_dict = temp_dict.get(key)
            if origin_dict:
                new_dict = {
                    "id": origin_dict["id"],
                    "title": origin_dict["title"]}
                temp_dict[key] = new_dict
    return temp_dict


def check_save_data(model_name, temp_dict):
    '''
     notice:the temp_dict pass in, check order field and id field and put it
     into a new children_list
    '''
    Model_Name = classing_model(str(model_name))
    children = Model_Name.relation.get("children")
    if children:
        for key in children:
            children_list = temp_dict.get(key)
            child_info = children[key]
            child_fields = child_info.get("fields")
            if children_list:
                new_children_list = []
                for child in children_list:
                    child_dict = {}
                    child_dict["id"] = child.get("id")
                    for field in child_fields:
                        if field == "order":
                            try:
                                value = int(child.get("order"))
                                child_dict[field] = value
                            except:
                                raise ValueError("order empty")
                        new_children_list.append(child_dict)
                temp_dict[key] = new_children_list
    return temp_dict


def inc_icon(model_name, temp_dict, icon_fields=['icon', 'logo']):
    for icon_field in icon_fields:
        if temp_dict.get(icon_field):
            icon_dict = temp_dict[icon_field]
            model_id = temp_dict['id']
            refered_icon(
                icon_dict.get("id"),
                model_id, model_name, icon_field)


def mod_icon(model_name, temp_dict, item_old, item_id):
    icon_fields = ['icon', 'logo']
    for icon_field in icon_fields:
        if temp_dict.get(icon_field):
            icon_dict = temp_dict.get(icon_field)
            old_icon_dict = item_old.get(icon_field)
            new_icon_id = icon_dict.get("id")
            old_icon_id = old_icon_dict.get("id", None) \
                if old_icon_dict else None
            if new_icon_id == old_icon_id:
                continue
            refered_icon(
                new_icon_id, item_id, model_name,
                icon_field, old_icon_id)


def check_preset_rule(temp_dict, cond={}):
    Predata = classing_model("aospredata")
    old_predata = Predata.find(cond, one=True)
    old_rule = old_predata.get("aosruledata")
    rule_dict = temp_dict["aosruledata"]
    temp_dict["last_modified"] = now_timestamp()
    temp_dict["release"] = 0
    if rule_dict.get("id") != old_rule.get("id"):
        check_unique_cond = {}
        check_unique_cond["aosruledata.id"] = int(
            rule_dict.get("id"))
        item_indb = Predata.find(check_unique_cond, toarray=True)
        if len(item_indb) >= 1:
            ref_item = item_indb[0]
            item_id = ref_item["id"]
            return json_response_error(
                PARAM_ERROR,
                msg="关联的规则已经被preset_id:%d 引用" % item_id)


@exception_handler()
@check_session
def preset_model_add(req, model_name, user):
    '''
    notice: when get request, if the model had children model, it will return
    a child model data list
    when post request, it will return add successfully or failed
    Request URL: /admin/P<model_name>/add
    HTTP Method: GET/POST
    when get:
    Parameters: None
    Return:{
        "child_model":[
        {"value":child_id,
          "display_value":child_field
        }
        ]
        }
    when post:
    Parameters: {"field1":value1, "field2":value2,...}
    Return:{
         "status":0,
         "msg":"add successfully"
        }
    '''
    Model_Name = classing_model(str(model_name))
    error_msg = {"msg": []}
    if not Model_Name:
        return json_response_error(
            PARAM_ERROR, msg="model name %s is not exist" % model_name)
    if req.method == "POST":
        temp_strs = req.raw_post_data
        try:
            temp_dict = simplejson.loads(temp_strs)
        except ValueError as expt:
            _LOGGER.error("json loads except:%s", expt)
            error_msg["msg"].append({"json_format": "json format error"})
            return json_response_error(PARAM_ERROR, error_msg)
        required_list = Model_Name.required
        for required_para in required_list:
            if temp_dict.get(required_para) is None:
                _LOGGER.error("parameter %s request", required_para)
                error_msg["msg"].append(required_para)
        if error_msg["msg"]:
            return json_response_error(PARAM_REQUIRED, error_msg)
        temp_dict = clean_save_data(temp_dict)
        # 在strategy和ruledata中使用了"fields_check"配置
        if hasattr(Model_Name, "fields_check"):
            fields_convert_dict = Model_Name.fields_check
            temp_dict = get_valid_params(temp_dict, fields_convert_dict)

        if Model_Name.relation and model_name != "aosruledata":
            # 在非ruledata表中使用的过滤字段，检验子model的order字段规则
            temp_dict = check_save_data(model_name, temp_dict)
        if model_name == "aospredata":
            # 配置规则只能被一条预置单独引用
            for key in _PRESET_STATUS_FIELDS:
                if temp_dict.get(key):
                    temp_dict.pop(key, None)
            Predata = classing_model("aospredata")
            rule_dict = temp_dict["aosruledata"]
            item = Predata.find(
                {"aosruledata.id": rule_dict.get("id")}, one=True)
            if item:
                error_dict = {}
                error_dict["rule"] = "the rule has refered by other preset"
                error_msg["msg"].append(error_dict)
                return json_response_error(PARAM_ERROR, error_msg)
        if model_name == "aosruledata":
            if not temp_dict.get("aospackage"):
                error_msg["msg"].append("package")
                return json_response_error(PARAM_REQUIRED, error_msg)
        for key in ("first_created", "last_modified"):
            if temp_dict.get(key):
                temp_dict.pop(key)
        result = Model_Name.insert(temp_dict)
        if result == "unique_failed":
            _LOGGER.error("check unique error")
            error_msg["msg"].append("title")
            msg = "title unique check failed"
            return json_response_error(PARAM_ERROR, error_msg, msg)
        else:
            temp_dict["id"] = result
            inc_icon(model_name, temp_dict)
            # 当该model引用了icon, logo字段的时候，引用计数加1
            _LOGGER.info(
                "use id %s insert in to model %s id is %s",
                user.get("user_name"), model_name, result)
            _save_to_log(user.get("user_name"), "创建", result, model_name)
        return json_response_ok(
            temp_dict, msg="add %s success" % model_name)
    elif req.method == "GET":
        data = {}
        if Model_Name.relation:
            children = Model_Name.relation.get("children")
            if children:
                for key in children:
                    model_list = get_children_model(key, model_name)
                    data[key] = model_list
                return json_response_ok(data, msg="get %s list" % key)
            else:
                return json_response_ok({}, msg="no child model")
        else:
            return json_response_ok({}, msg="no relation model")
    else:
        return json_response_error(
            METHOD_ERROR, msg="http method error")


@exception_handler()
@check_session
def preset_model_list(req, model_name, user):
    '''
    Request URL: /admin/preset_{P<model>}_list
    HTTP Method: GET
    Parameters: None
    Return:
        {
            "status":0,
            "data":{
                "items":[
                {"field1":value1},
                {"field2":value2}
                ],
                "total":123
                }
            }

    '''
    Model_Name = classing_model(str(model_name))
    if Model_Name:
        if req.method == "GET":
            list_api = Model_Name.list_api
            model_list = []
            page_models = get_model_list(req, model_name)
            results = page_models["results"]
            total = page_models["total"]
            for result in results:
                # whether the model is ref to preset data
                if hasattr(Model_Name, "ref_preset_data"):
                    ref_dict = Model_Name.ref_preset_data
                    predata_ids = []
                    model_id = result.get("id")
                    if model_name in _REF_RULE_MODELS:
                        # if the model is child model of rule model
                        predata_ids = get_ref_rule_preset(
                            model_name, model_id)
                        Model_Name.update(
                            {"id": result.get("id")},
                            {"ref_preset_id": predata_ids})
                    else:
                        for key in ref_dict:
                            object_link = ref_dict[key]
                            predata_ids = predata_ids + ref_get_presetdata(
                                model_id, model_name, object_link)
                        if predata_ids:
                            lc_pn = _get_ref_lc_pn(Model_Name, predata_ids)
                            result["aoslocale"] = lc_pn.get("locale")
                            result["aospackage"] = lc_pn.get("package")
                            Model_Name.update(
                                {"id": result.get("id")},
                                {"ref_preset_id": predata_ids})
                        else:
                            Model_Name.update(
                                {"id": result.get("id")},
                                {"ref_preset_id": []})
                if model_name == "aospredata":
                    lc_pn_release = get_predata_model(result)
                    result["release"] = lc_pn_release.get("release")
                    result["aoslocale"] = lc_pn_release.get("aoslocale")
                    result["aospackage"] = lc_pn_release.get("aospackage")
                result["last_modified"] = unixto_string(
                    result.get("last_modified"))
                if result.get("first_created"):
                    result["first_created"] = unixto_string(
                        result.get("first_created"))
                result["last_release_ec2"] = unixto_string(
                    result.get("last_release_ec2"))
                model_list.append(result)
            data = {}
            data["total"] = total
            if list_api.get("get_filters"):
                params = list_api.get("get_filters")
                filters = get_filters(params)
                data["filters"] = filters
            data["items"] = model_list
            return json_response_ok(data, msg="get list")
        else:
            return json_response_error(
                METHOD_ERROR, msg="http method error")
    else:
        return json_response_error(
            PARAM_ERROR, msg="model name %s is not exist" % model_name)


@exception_handler()
def preset_model_detail(req, model_name):
    '''
     notice:get one  item detail
     url: /admin/model_name/edit?id=xxxxxxxxxxxxxxx
     http method: get
        return:{
            "item":{
                "field1":value1,
                "field2":value2
                }
            }
    '''
    Model_Name = classing_model(str(model_name))
    if Model_Name:
        if req.method == "GET":
            item_id = req.GET.get("id")
            if not item_id:
                return json_response_error(
                    PARAM_ERROR, msg="the id is required")
            cond = {"id": int(item_id)}
            detail_item = Model_Name.find(
                cond, fields={"_id": 0}, one=True, toarray=True)
            if detail_item:
                if model_name != "aosruledata":
                    detail_item = get_model_detail(model_name, detail_item)
                if model_name == "aosruledata":
                    children = Model_Name.relation.get("children")
                    for key in children:
                        item_ids = detail_item.get(key)
                        model_list = get_children_model(
                            key, model_name,
                            api_type="edit", item_ids=item_ids)
                        detail_item[key] = model_list
                    return json_response_ok(
                        detail_item, msg="edit api:rule model %s list" % key)
                else:
                    return json_response_ok(
                        detail_item, msg="general detail item return")
            else:
                return json_response_error(
                    PARAM_ERROR, msg="the id is not exist")
        else:
            return json_response_error(
                METHOD_ERROR, msg="http method error")
    else:
        return json_response_error(
            PARAM_ERROR, msg="model name %s is not exist" % model_name)


@exception_handler()
@check_session
def preset_model_modify(req, model_name, user):
    '''
     notice:update one item of a model
     url :  /admin/model_name/update
     parameter:{"field1":value1, "field2:value2"}
     return:{
        "status":0,
        "msg":"save successfully"
        }
    '''
    Model_Name = classing_model(str(model_name))
    if not Model_Name:
        return json_response_error(
            PARAM_ERROR, msg="model name %s is not exist" % model_name)
    if req.method == "POST":
        required_list = Model_Name.required
        temp_strs = req.raw_post_data
        try:
            temp_dict = simplejson.loads(temp_strs)
        except ValueError as expt:
            _LOGGER.error("model edit api params except:%s", expt)
            return json_response_error(
                PARAM_ERROR,
                msg="json loads error,check parameters format")
        item_id = temp_dict.get("id")
        for required_para in required_list:
            para_value = temp_dict.get(required_para)
            if para_value == "" or para_value == [] or para_value == {}:
                return json_response_error(
                    PARAM_REQUIRED, msg="para %s request" % required_para)
        temp_dict = clean_save_data(temp_dict)
        cond = {"id": int(item_id)}
        if hasattr(Model_Name, "fields_check"):
            fields_convert_dict = Model_Name.fields_check
            temp_dict = get_valid_params(temp_dict, fields_convert_dict)
        if model_name == "aospredata":
            check_preset_rule(temp_dict, cond)
        if model_name == "aosruledata":
            if not temp_dict.get("aospackage"):
                return json_response_error(
                    PARAM_ERROR, msg="缺少包名")
            para_list = ("aoslocale", "aossource", "aosoperator")
            for para in para_list:
                if not temp_dict.get(para):
                    temp_dict[para] = [0]
        check_unique_cond = Model_Name.build_unique_cond(temp_dict)
        check_unique_cond["id"] = {"$ne": int(item_id)}
        another_item = Model_Name.find(
            check_unique_cond, one=True, toarray=True)
        if another_item:
            return json_response_error(
                PARAM_ERROR, msg="update error, check unique error")
        item_old = Model_Name.find(cond, one=True)
        if item_old:
            temp_dict.pop("_id", None)
            temp_dict.pop("id", None)
            temp_dict["last_modified"] = now_timestamp()
            if Model_Name.relation and model_name != "aosruledata":
                temp_dict = check_save_data(model_name, temp_dict)
            mod_icon(model_name, temp_dict, item_old, item_id)
            Model_Name.update(cond, temp_dict)
            _LOGGER.info(
                "user id %s saved the model_name %s id:%s successful",
                user.get("user_name"), model_name, item_id)
            _save_to_log(user.get("user_name"), "修改", item_id, model_name)
            update_item = Model_Name.find(
                cond, fields={"_id": 0}, one=True, toarray=True)
            return json_response_ok(
                update_item, msg="update %s success" % model_name)
        else:
            _LOGGER.info("the id:%s is not exist", item_id)
            return json_response_error(
                PARAM_ERROR, msg="the  id: %s is not exist" % item_id)
    else:
        return json_response_error(
            METHOD_ERROR, msg="http method error")


@exception_handler()
@check_session
def preset_model_delete(req, model_name, user):
    '''
    Request URL: /admin/P<model_name>/delete
    HTTP Method: POST
    Parameters: {"item_ids": ["123","124"]}
    Return:{
        "status":0,
        "msg":"delete successfully"
        }
    '''
    Model_Name = classing_model(str(model_name))
    item_ids = []
    temp_dict = {}
    if not Model_Name:
        return json_response_error(
            PARAM_ERROR, msg="model name %s is not exist" % model_name)
    if req.method == "POST":
        temp_strs = req.raw_post_data
        try:
            temp_dict = simplejson.loads(temp_strs)
        except ValueError as expt:
            _LOGGER.info("model delete api para except:%s", expt)
            return json_response_error(PARAM_ERROR, msg="json form error")
        item_ids = temp_dict.get("items")
        model_predel_list = _get_pre_delete_models(item_ids, model_name)
        if not item_ids:
            return json_response_error(PARAM_ERROR, msg="item_id is empty")
        else:
            comfirm = temp_dict.get("comfirm")
            comfirm = True if comfirm is not None else False
            delete_ids = []
            for item in item_ids:
                if model_name == "aospackage":
                    # feature: 如果icon引用包名，包名不可直接删
                    icon_id = _check_ref_incon(int(item))
                    if icon_id:
                        return json_response_error(
                            DATA_RELETED_BY_OTHER,
                            msg="refence by icon id :%s" % icon_id)
                if not comfirm:
                    list_all = _CANNOT_DEL_IF_RELET + _REF_RULE_MODELS
                    if hasattr(Model_Name, "ref_preset_data"):
                        result = Model_Name.find({"id": int(item)}, one=True)
                        ref_preset_ids = result.get("ref_preset_id")
                        if ref_preset_ids:
                            if model_name in list_all:
                                return json_response_error(
                                    DATA_RELETED_BY_OTHER,
                                    msg="id:%d refence by preset_id: %s" %
                                    (int(item), ref_preset_ids[0]))
                            else:
                                return json_response_error(
                                    DATA_DELETE_COMFIRM,
                                    msg="id:%d refence by preset_id: %s" %
                                    (int(item), ref_preset_ids[0]))
                        else:
                            if model_name in _REF_RULE_MODELS:
                                ret_val = del_model_with_relations(
                                    str(model_name), item, comfirm)
                                if ret_val:
                                    return json_response_error(
                                        DATA_RELETED_BY_OTHER,
                                        msg="id refered by rule")
                                else:
                                    del_model_with_relations(
                                        str(model_name), item, True)
                                    delete_ids.append(item)
                            else:
                                ret_val = del_model_with_relations(
                                    str(model_name), item, comfirm)
                                if ret_val:
                                    return json_response_error(
                                        DATA_DELETE_COMFIRM,
                                        msg="item has been refered")
                                delete_ids.append(item)
                    else:
                        del_model_with_relations(
                            str(model_name), item)
                        delete_ids.append(item)
                else:
                    del_model_with_relations(
                        str(model_name), item, comfirm)
                    delete_ids.append(item)
            _LOGGER.info(
                "user id %s delete model %s ids: %s",
                user.get("user_name"), model_name, item_ids)
            _save_del_action_log(
                user.get("user_name"), model_predel_list, model_name)
            return json_response_ok(delete_ids, msg="delete success")
    else:
        return json_response_error(
            METHOD_ERROR, msg="http method error")


@exception_handler()
@check_session
def preset_predata_delete(req, user):
    temp_strs = req.raw_post_data
    item_ids = []
    temp_dict = {}
    try:
        temp_dict = simplejson.loads(temp_strs)
    except ValueError as expt:
        _LOGGER.info("model delete api para except:%s", expt)
        return json_response_error(PARAM_ERROR, msg="json format error")
    items = temp_dict.get("items")
    place = temp_dict.get("server")
    for item in items:
        item_ids.append(int(item))
    results = del_predata(place, item_ids, user.get("user_name"))
    status = results[0]
    data = {}
    data["success"] = results[1]
    data["failed"] = results[2]
    if status == -1:
        return json_response_error(PARAM_ERROR, msg="UNKNOWN UPLOAD PLACE")
    elif status == 0:
        if place == _ADMIN:
            suc_ids = fail_ids = []
            if data["failed"]:
                for fai_item in data["failed"]:
                    fail_ids.append(fai_item.get("id"))
            if data["success"]:
                for suc_item in data["success"]:
                    suc_ids.append(suc_item.get("id"))
            data["success"] = suc_ids
            data["failed"] = fail_ids
        return json_response_ok(data, msg="delete successfully")
    else:
        return json_response_error(status, data, msg="del error")


@exception_handler()
@check_session
def upload_predata(req, user):
    rawids = []
    Predata = classing_model("aospredata")
    Preset_Local = classing_model("preset_local")
    upload_success = []
    upload_failed = []
    if req.method == "POST":
        temp_strs = req.raw_post_data
        try:
            temp_dict = simplejson.loads(temp_strs)
        except ValueError as expt:
            _LOGGER.info("model delete api para except:%s", expt)
            return json_response_error(
                PARAM_ERROR,
                msg="json loads error,check parameters format")
        item_ids = temp_dict.get("items")
        for item in item_ids:
            rawids.append(int(item))
        if not rawids:
            return json_response_error(PARAM_ERROR, msg="id is empty")
        count = len(rawids)
        upload_place = temp_dict.get("server")
        if upload_place == _LOCAL:
            for rawid in rawids:
                count = count - 1
                # update status upload to local
                results = package_one_predata(rawid, upload_place)
                if results[0]:
                    preset_local_dict = results[2]
                    now_time = now_timestamp()
                    Predata.update(
                        {"id": rawid},
                        {"is_upload_local": True,
                            "last_release_local": now_time,
                            "release": 2})
                    item_suc = Predata.find(
                        {"id": rawid}, fields={"_id": 0}, one=True)
                    item_suc["last_modified"] = unixto_string(
                        item_suc["last_modified"])
                    item_suc["first_created"] = unixto_string(
                        item_suc["first_created"])
                    lc_pn = _get_local_package_preset(rawid)
                    item_suc["aoslocale"] = lc_pn.get("aoslocale")
                    item_suc["aospackage"] = lc_pn.get("aospackage")
                    upload_success.append(item_suc)
                    if not Preset_Local.find({"id": rawid}, one=True):
                        result = Preset_Local.insert(preset_local_dict)
                        _LOGGER.info(
                            "%d rawdata has put into local,result:%s",
                            rawid, result)
                    else:
                        upt_dict = {}
                        upt_dict["last_modified"] = now_timestamp()
                        upt_dict["_meta"] = preset_local_dict["_meta"]
                        upt_dict["_rule"] = preset_local_dict["_rule"]
                        Preset_Local.update({"id": rawid}, upt_dict)
                    _save_to_log(
                        user.get("user_name"),
                        "上传到测试环境", rawid, "aospredata")
                else:
                    return json_response_error(PARAM_ERROR, msg=results[1])
            # return_items = _get_predata_list(rawids)
            data = {}
            data["success"] = upload_success
            data["failed"] = upload_failed
            return json_response_ok(
                data, "there is %d not package success" % count)
        elif upload_place == _EC2:
            # 同步local中的数据到ec2
            Preset_Local = classing_model("preset_local")
            for rawid in rawids:
                item = Preset_Local.find({"id": rawid}, one=True, toarray=True)
                if not item:
                    item_failed = Predata.find(
                        {"id": rawid}, fields={"_id": 0}, one=True)
                    item_failed["last_modified"] = unixto_string(
                        item_failed["last_modified"])
                    item_failed["first_created"] = unixto_string(
                        item_failed["first_created"])
                    lc_pn = _get_local_package_preset(rawid)
                    item_failed["aoslocale"] = lc_pn.get("aoslocale")
                    item_failed["aospackage"] = lc_pn.get("aospackage")
                    upload_failed.append(item_failed)
                    return json_response_error(
                        DATA_NOT_UPLOAD_TO_PRE, data={},
                        msg="id:%d should upload to local first" % rawid)
                else:
                    results = package_one_predata(rawid, upload_place)
                    if results[0]:
                        preset_ec2_dict = results[2]
                        now_time = now_timestamp()
                        if save_to_ec2(preset_ec2_dict):
                            Predata.update(
                                {"id": rawid},
                                {"is_upload_ec2": True,
                                    "last_release_ec2": now_time,
                                    "release": 0})
                            item_suc = Predata.find(
                                {"id": rawid}, fields={"_id": 0}, one=True)
                            item_suc["last_modified"] = unixto_string(
                                item_suc["last_modified"])
                            item_suc["first_created"] = unixto_string(
                                item_suc["first_created"])
                            item_suc["last_release_ec2"] = unixto_string(
                                item_suc["last_release_ec2"])
                            lc_pn = _get_local_package_preset(rawid)
                            item_suc["aoslocale"] = lc_pn.get("aoslocale")
                            item_suc["aospackage"] = lc_pn.get("aospackage")
                            upload_success.append(item_suc)
                            _save_to_log(
                                user.get("user_name"),
                                "上传到正式环境", rawid, "aospredata")
                    else:
                        json_response_error(PARAM_ERROR, msg=results[1])
            # return_items = _get_predata_list(rawids)
            data = {}
            data["success"] = upload_success
            data["failed"] = upload_failed
            return json_response_ok(
                data, msg="there is %d not package success" % count)
        else:
            return json_response_error(
                PARAM_ERROR, msg="UNKNOWN UPLOAD PLACE")
    else:
        return json_response_error(
            METHOD_ERROR, msg="http method error")


@exception_handler()
@check_session
def export_predata(req, user):
    Preset_Local = classing_model("preset_local")
    rawids = []
    zip_file_name = "data.zip"
    if req.method == "GET":
        temp_dict = req.GET
        if temp_dict:
            ids = temp_dict.get("id")
            strs_id = ids.split(',')
            for sid in strs_id:
                rawids.append(int(sid))
        if rawids:
            mf = StringIO.StringIO()
            with zipfile.ZipFile(mf, 'w') as myzip:
                for rawid in rawids:
                    rawid = int(rawid)
                    preset_local_dict = {}
                    item = Preset_Local.find({"id": rawid}, one=True)
                    if item:
                        preset_local_dict = item
                    else:
                        results = package_one_predata(rawid, _LOCAL)
                        if results[0]:
                            preset_local_dict = results[2]
                        else:
                            _LOGGER.error("export data error: %s" % results[1])
                    json_obj = preset_local_dict.get("_meta")
                    file_name = "preset_%d.json" % rawid
                    simplejson.dump(json_obj, mf, indent=4)
                    myzip.writestr(file_name, mf.getvalue())
                    _save_to_log(
                        user.get("user_name"),
                        "导出", rawid, "aospredata")
            respone = HttpResponse(mf.getvalue(), mimetype="application/zip")
            respone["Content-Disposition"] = "attachment; "\
                "filename=%s" % zip_file_name
            return respone
        else:
            return json_response_error("no ids find")
    else:
        return json_response_error(
            METHOD_ERROR, msg="http method error")


def export_predata_by_rule(req):
    if req.method == "GET":
        filters = get_export_filters()
        return json_response_ok(filters, "test version")
    else:
        return json_response_error(METHOD_ERROR, "http method error")


@exception_handler()
@check_session
def export_byrule(req, user):
    if req.method == "GET":
        Preset_Local = classing_model("preset_local")
        zip_file_name = "data.zip"
        platform = req.GET.get("platform")
        package = req.GET.get("package")
        source = req.GET.get("source")
        version_code = req.GET.get("version_code")
        if version_code:
            try:
                version_code = int(version_code)
            except:
                raise ValueError
        locales = req.GET.get("locale")
        locale_list = []
        if locales:
            locale_list = locales.split('|')
        mf = StringIO.StringIO()
        if locale_list:
            with zipfile.ZipFile(mf, mode='w') as zf:
                for locale in locale_list:
                    cond = {}
                    if platform:
                        cond["_rule.os"] = platform
                    if package:
                        cond["_rule.packages"] = package
                    if source:
                        cond["_rule.sources"] = {
                            "$in": [source, All_FLAG, DEFAULT_SOURCE]}
                    if locale:
                        cond["_rule.locales"] = locale
                    if version_code:
                        cond["$or"] = [
                            {"_rule.min_version": {"$lte": version_code},
                                "_rule.max_version": {"$gte": version_code}},
                            {"_rule.min_version": 0, "_rule.max_version": 0}]
                    item = Preset_Local.find(cond, one=True)
                    '''
                    item = get_one_ec2_preset(cond)
                    '''
                    if item:
                        file_name = "preload_%s.json" % locale
                        preset_dict = item.get("_meta")
                        simplejson.dump(preset_dict, mf, indent=4)
                        zf.writestr(file_name, mf.getvalue())
                        _save_to_log(
                            user.get("user_name"),
                            "导出", item.get("id"), "exportpreset")
            if mf.getvalue():
                respone = HttpResponse(
                    mf.getvalue(), mimetype="application/zip")
                respone["Content-Disposition"] = "attachment; "\
                    "filename=%s" % zip_file_name
                return respone
            else:
                return json_response_error(
                    PARAM_ERROR, msg="no data find")
        else:
            return json_response_error(
                PARAM_ERROR, msg="must chose one more locale")
    else:
        return json_response_error(METHOD_ERROR, "ttp method error")
