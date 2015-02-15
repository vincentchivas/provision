 # -*- coding: utf-8 -*-
import simplejson
import time
import logging
import re
from operator import itemgetter
from provisionadmin.model.preset import (
    classing_model, get_lc_pn_by_predataids)
from provisionadmin.utils.respcode import DATA_DELETE_COMFIRM

from provisionadmin.service.views.resource import derefered_icon


_LOGGER = logging.getLogger("view.utils")
_ONE_DAY = 86400.0
_MAX_VERSION_LIMITED = 4294967295
_DESKTOP_SHARE_IN_PRESET = ["aosspeeddialdesktop", "aossharecontent"]


def get_predata_model(origin_model):
    '''
    notice:初始数据list页面需要的时间字段和release字段来控制发布数据同步
    '''
    result = {}
    Predata = classing_model("aospredata")
    predata_ids = []
    predata_ids.append(origin_model.get("id"))
    lc_pn = _get_ref_lc_pn(Predata, predata_ids)
    result["aoslocale"] = lc_pn.get("locale")
    result["aospackage"] = lc_pn.get("package")
    last_modified = origin_model.get("last_modified")
    if origin_model.get("last_modified"):
        release_local_time = origin_model.get("last_release_local")
        release_ec2_time = origin_model.get("last_release_ec2")
        if last_modified > release_local_time:
            # need upload
            if release_local_time > release_ec2_time:
                result["release"] = 2
            else:
                result["release"] = 1
        else:
            if release_local_time > release_ec2_time:
                result["release"] = 2
            else:
                result["release"] = 0
    Predata.update(
        {"id": result.get("id")},
        {"release": result["release"]})
    return result


def get_children_model(child_name, parent_model, api_type="add", item_ids=[]):
    '''
     notice: when call add model api, if the model has children models,it
     will return children model data list
     规则模块：调用改函数，其他的api未用到
    '''
    _LOGGER.debug("paras:child_name[%s], parent_model:[%s]", child_name, parent_model)
    model_list = []
    Model_Child = classing_model(str(child_name))
    if Model_Child:
        relation = Model_Child.relation
        parents = relation["parent"]
        parent_dict = parents.get(parent_model)
        fields = parent_dict.get("fields")
        display_field = parent_dict.get("display")
        results = Model_Child.find({}, fields, toarray=True)
        for result in results:
            model_dict = {}
            model_id = int(result.get("id"))
            model_dict["value"] = model_id
            model_dict["display"] = result.get(display_field)
            if api_type == "edit" and model_id in item_ids:
                model_dict["selected"] = True
            else:
                model_dict["selected"] = False
            model_list.append(model_dict)
        if child_name in ["aoslocale", "aospackage", "aossource"]:
            model_list = sorted(model_list, key=itemgetter("display"))
    return model_list


def _get_local_package_preset(rawid):
    result = {}
    predata_ids = []
    locale_name_list = []
    package_name_list = []
    locale_id_list = []
    package_id_list = []
    predata_ids.append(rawid)
    lc_pn = get_lc_pn_by_predataids(predata_ids)
    for lc in lc_pn[0]:
        locale_name_list.append(lc.get("name"))
        locale_id_list.append(lc.get("id"))
    for pn in lc_pn[1]:
        package_name_list.append(pn.get("title"))
        package_id_list.append(pn.get("id"))
    result["aoslocale"] = ",".join(locale_name_list)
    result["aospackage"] = ",".join(package_name_list)
    return result


def _search_cond(request, search_fields):
    '''
    notice:when a request comes,combination of the search_fields and the
    request parameter values, return a condition query to mongodb
    '''
    cond = {}
    regex_cond_list = []
    for key in search_fields.keys():
        value = request.GET.get(key)
        if value:
            value_dict = search_fields.get(key)
            value_type = value_dict.get("type")
            if value_type == "list":
                value_data_type = value_dict.get("data_type")
                if value_data_type:
                    if value_data_type == "int":
                        cond[key] = int(value)
                    else:
                        cond[key] = value
        else:
            if search_fields.get(key)["type"] == "date":
                start_time = request.GET.get("start")
                if not start_time:
                    continue
                start = time.mktime(
                    time.strptime(start_time, '%Y-%m-%d'))
                end_time = request.GET.get("end")
                end = time.mktime(
                    time.strptime(end_time, '%Y-%m-%d')) + _ONE_DAY
                cond[key] = {"$gte": start, "$lte": end}
            # 当给searchKeyword时候，能全局搜索
            if search_fields.get(key)["type"] == "text":
                if request.GET.get("searchKeyword"):
                    regex_cond = {}
                    searchKeyword = request.GET.get("searchKeyword")
                    if search_fields.get(key)["data_type"] == "int":
                        try:
                            regex_cond[key] = int(searchKeyword)
                        except:
                            _LOGGER.info("not a number string")
                    if search_fields.get(key)["data_type"] == "string":
                        regex_cond[key] = {"$regex": re.escape(searchKeyword)}
                    if regex_cond:
                        regex_cond_list.append(regex_cond)
    if regex_cond_list:
        cond["$or"] = regex_cond_list
    return cond


def get_model_list(req, model_name):
    '''
     notice: get the list data of one model
    '''
    return_data = {}
    Model_Name = classing_model(str(model_name))
    cond = {}
    list_api = Model_Name.list_api
    query_dict = req.GET
    sort_strs = query_dict.get("sort")
    sort_dict = {}
    if sort_strs:
        try:
            sort_dict = simplejson.loads(sort_strs)
        except ValueError as expt:
            _LOGGER.error("json loads except:%s", expt)
            raise ValueError("sort string error")
    sort_field = sort_dict.get("sortBy")
    sort_way = sort_dict.get("sortWay")
    if not sort_field:
        sort_field = 'last_modified'
    if not sort_way:
        sort_way = -1
    else:
        sort_way = 1 if sort_way == "asc" else -1
    _LOGGER.debug("sort_field %s, sort way %s", sort_field, sort_way)
    pageindex = query_dict.get("index")
    pagesize = query_dict.get("limit")
    if not pageindex:
        pageindex = 1
    if not pagesize:
        pagesize = 20
    if list_api.get("search_fields"):
        search_fields = list_api["search_fields"]
        cond = _search_cond(req, search_fields)
    fields = list_api["fields"]
    fields["_id"] = 0
    results = Model_Name.find(
        cond, fields=fields).sort(
        sort_field, sort_way).skip(
        (int(pageindex) - 1) * int(pagesize)).limit(int(pagesize))
    total = Model_Name.find(cond).count()
    return_data["results"] = results
    return_data["total"] = total
    return return_data


def _get_ref_lc_pn(Model_Name, predata_ids):
    '''
     notice:将所有model关联locale和package
    '''
    result = {}
    lc_pn = get_lc_pn_by_predataids(
        list(set(predata_ids)))
    locale_name_list = []
    locale_id_list = []
    package_name_list = []
    package_id_list = []
    for lc in lc_pn[0]:
        locale_name_list.append(lc.get("name"))
        locale_id_list.append(lc.get("id"))
    for pn in lc_pn[1]:
        package_name_list.append(pn.get("title"))
        package_id_list.append(pn.get("id"))
    result["locale"] = ",".join(list(set(locale_name_list)))
    result["package"] = ",".join(list(set(package_name_list)))
    Model_Name.update(
        {"id": result.get("id")},
        {"aoslocale": list(set(locale_id_list)),
            "aospackage": list(set(package_id_list)),
            "ref_preset_id": list(set(predata_ids))})
    return result


def get_model_detail(model_name, detail_item):
    '''
     输入model name，如果该model包含子model，将按照order字段
     将子model排序
    '''
    children = []
    Model_Name = classing_model(str(model_name))
    if Model_Name.relation:
        children = Model_Name.relation.get("children")
    if children:
        for key in children:
            Child_Model = classing_model(str(key))
            new_children_list = []
            child_info_list = detail_item[key]
            for child_info in child_info_list:
                child_id = child_info["id"]
                child_detail = Child_Model.find(
                    {"id": child_id},
                    fields={"_id": 0}, one=True)
                if child_detail:
                    for child_item in child_info:
                        child_detail[child_item] = child_info[child_item]
                    new_children_list.append(child_detail)
            new_children_list = sorted(
                new_children_list, key=itemgetter("order"))
            detail_item[key] = new_children_list
    return detail_item


def del_model_with_relations(model_name, item_id, comfirm=False):
    '''
    notice:关联删除，当资源被引用的时候返回DATA_DELETE_COMFIRM,
    确认完后如果资源可以被删除，返回1005，不可删除返回1004
    '''
    Model_Name = classing_model(str(model_name))
    relation = Model_Name.relation
    parent_dict = {}
    if relation.get("parent"):
        parent_dict = relation.get("parent")
    item_id = int(item_id)
    model = Model_Name.find(cond={"id": item_id}, one=True)
    if model:
        if parent_dict:
            for key in parent_dict:
                fields_in_parent = model_name
                if key == "aosruledata":
                    # 子model在父model中的字段名字，rule model存储为数组id
                    Rule = classing_model("aosruledata")
                    model_list = Rule.find(
                        {fields_in_parent: item_id}, toarray=True)
                    if model_list:
                        if comfirm:
                            for mod in model_list:
                                child_list = mod.get(fields_in_parent)
                                child_list.remove(item_id)
                                Rule.update(
                                    {"id": mod["id"]},
                                    {fields_in_parent: child_list})
                        else:
                            return DATA_DELETE_COMFIRM
                    else:
                        _LOGGER.info("rule data model has no ref id")
                elif model_name not in _DESKTOP_SHARE_IN_PRESET:
                    # 一般的父model存储子model：[{"id":1},{"id":2}]
                    Parent_Model = classing_model(str(key))
                    id_fields_in_parent = model_name + ".id"
                    model_list = Parent_Model.find(
                        {id_fields_in_parent: item_id}, toarray=True)
                    if model_list:
                        for mod in model_list:
                            child_list = mod.get(fields_in_parent)
                            for id_dict in child_list:
                                if id_dict.get("id") == item_id:
                                    if comfirm:
                                        child_list.remove(id_dict)
                                    else:
                                        return DATA_DELETE_COMFIRM
                            Parent_Model.update(
                                {"id": mod["id"]},
                                {fields_in_parent: child_list})
                    else:
                        _LOGGER.info("parent model has no ref id")
                else:
                    # 特殊的父model存储子model：{"id":1}
                    Parent_Model = classing_model(str(key))
                    id_fields_in_parent = model_name + ".id"
                    model_list = Parent_Model.find(
                        {id_fields_in_parent: item_id}, toarray=True)
                    if model_list:
                        for mod in model_list:
                            child_dict = mod.get(fields_in_parent)
                            if child_dict:
                                if comfirm:
                                    child_dict = {}
                                else:
                                    return DATA_DELETE_COMFIRM
                            Parent_Model.update(
                                {"id": mod["id"]},
                                {fields_in_parent: child_dict})
                    else:
                        _LOGGER.info("parent model has no ref id")
        else:
            _LOGGER.info("%s has no parent model" % model_name)
        icon_fields = ['icon', 'logo']
        for icon_field in icon_fields:
            icon_dict = model.get(icon_field)
            if icon_dict:
                old_icon_id = icon_dict.get("id")
                model_id = model["id"]
                derefered_icon(old_icon_id, model_id, model_name, icon_field)
        Model_Name.remove({"id": item_id})
    else:
        _LOGGER.info(
            "model %s itemid %s is not exist" % (model_name, item_id))


def _check_ref_incon(package_id):
    Icon = classing_model("icon")
    item = Icon.find({"package": package_id}, one=True)
    if item:
        return item.get("id")


def _get_pre_delete_models(model_ids, model_name):
    '''
     用于在用户删除该数据之前记录数据的信息
    '''
    model_list = []
    Model_Name = classing_model(str(model_name))
    comfirm_int_ids = []
    if model_ids:
        for model_id in model_ids:
            try:
                comfirm_int_ids.append(int(model_id))
            except:
                continue
        model_list = Model_Name.find(
            {"id": {"$in": comfirm_int_ids}}, fields={"_id": 0}, toarray=True)
    return model_list
