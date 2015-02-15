# coding: utf-8
import logging
from operator import itemgetter
from provisionadmin.model.base import ModelBase
from provisionadmin.settings import MODELS
from provisionadmin.db.config import LOCAL_DB, EC2_DB
from provisionadmin.utils.common import now_timestamp
# from provisionadmin.utils.version_list import VERSION_LIST


_LOGGER = logging.getLogger("model")
_CHINA = "china"
_EC2 = "ec2"
_ANDROID = "android"
_IOS = "ios"
_DEFAULT_SOURCE = "ofw"
_DB_NAME_IN_EC2 = "preset_ec2"


def _get_ids(child_ids, child_model, parent_model):
    '''
     通过子model的id获取父model的id
    '''
    parent_ids = []
    cond = {}
    Parent_Model = classing_model(str(parent_model))
    for child_id in child_ids:
        cond[child_model + ".id"] = child_id
        parents = Parent_Model.find(cond, toarray=True)
        for parent in parents:
            parent_ids.append(parent.get("id"))
    return list(set(parent_ids))


def get_lc_pn_by_predataids(predata_ids=[]):
    '''
     通过反向关联预置数据的id获取对应的locale和package
    '''
    Predata = classing_model("aospredata")
    locale_list = []
    package_list = []
    Rule = classing_model("aosruledata")
    Locale = classing_model("aoslocale")
    Package = classing_model("aospackage")
    for predata_id in predata_ids:
        predata = Predata.find({"id": predata_id}, one=True)
        rule_dict = predata.get("aosruledata")
        rule = Rule.find({"id": rule_dict.get("id")}, one=True)
        if rule:
            locale_ids = rule.get("aoslocale")
            package_ids = rule.get("aospackage")
            for locale_id in locale_ids:
                locale_dict = Locale.find({"id": locale_id}, one=True)
                if locale_dict:
                    locale_dict.pop("_id", None)
                    locale_list.append(locale_dict)
            for package_id in package_ids:
                package_dict = Package.find({"id": package_id}, one=True)
                if package_dict:
                    package_dict.pop("_id", None)
                    package_list.append(package_dict)
    return locale_list, package_list


def get_ref_rule_preset(model_name, model_id):
    '''
    获取跟规则rule的子model的引用id
    '''
    Predata = classing_model("aospredata")
    Rule = classing_model("aosruledata")
    rules = Rule.find({model_name: model_id}, toarray=True)
    ref_ids = []
    if rules:
        for rule in rules:
            ruleid = rule.get("id")
            presets = Predata.find({"aosruledata.id": ruleid}, toarray=True)
            if presets:
                for preset in presets:
                    presetid = preset.get("id")
                    ref_ids.append(presetid)
    return list(set(ref_ids))


def ref_get_presetdata(model_id, model_name, object_link=[]):
    Predata = classing_model("aospredata")
    predata_list = []
    length = len(object_link)
    cond = {}
    predata_ids = []
    if length == 1:
        cond[model_name + ".id"] = model_id
        predata_list = Predata.find(cond, toarray=True)
        if predata_list:
            for predata in predata_list:
                predata_ids.append(predata.get("id"))
    else:
        index = 0
        start_model = model_name
        next_ids = []
        next_ids.append(model_id)
        while index < length:
            next_ids = _get_ids(next_ids, start_model, object_link[index])
            start_model = object_link[index]
            index = index + 1
        predata_ids = next_ids
    return predata_ids


def check_in_ec2(rawid):
    item = EC2_DB[_DB_NAME_IN_EC2].find_one({"id": rawid})
    return True if item else False


def remove_from_ec2(rawid):
    item = EC2_DB[_DB_NAME_IN_EC2].find_one({"id": rawid})
    if item:
        EC2_DB[_DB_NAME_IN_EC2].remove({"id": rawid})
        return True
    else:
        return False


def get_one_ec2_preset(cond):
    return EC2_DB[_DB_NAME_IN_EC2].find_one(cond, fields={"_id": 0})


def save_to_ec2(ec2_dict):
    rawid = ec2_dict.get("id")
    cond = {"id": rawid}
    save_data = {}
    save_data["id"] = ec2_dict["id"]
    save_data["_meta"] = ec2_dict["_meta"]
    save_data["_rule"] = ec2_dict["_rule"]
    save_data["first_created"] = now_timestamp()
    save_data["last_modified"] = now_timestamp()
    EC2_DB[_DB_NAME_IN_EC2].update(cond, save_data, True)
    _LOGGER.info("origin_id:%d insert to ec2 success" % rawid)
    return True


def get_filters(params=[]):
    filter_list = []
    if not params:
        return []
    else:
        if "aoslocale" in params:
            locale_list = []
            Locale = classing_model("aoslocale")
            locales = Locale.find({}, toarray=True)
            for local in locales:
                locale_dict = {
                    "display_value": local.get("name"),
                    "value": local.get("id")}
                locale_list.append(locale_dict)
            filter_dict = {}
            locale_list = sorted(
                locale_list, key=itemgetter("display_value"))
            locale_list.insert(
                0, {"display_value": "选择Locales", "value": ""})
            filter_dict["items"] = locale_list
            filter_dict["name"] = "aoslocale"
            filter_list.append(filter_dict)
        if "aospackage" in params:
            package_list = []
            Package = classing_model("aospackage")
            packages = Package.find({}, toarray=True)
            for package in packages:
                package_dict = {
                    "display_value": package.get("title"),
                    "value": package.get("id")}
                package_list.append(package_dict)
            filter_dict = {}
            package_list = sorted(
                package_list, key=itemgetter("display_value"))
            package_list.insert(
                0, {"display_value": "选择项目名称", "value": ""})
            filter_dict["items"] = package_list
            filter_dict["name"] = "aospackage"
            filter_list.append(filter_dict)
        return filter_list


def _get_platform_list():
    platform_list = []
    Preset_Local = classing_model("preset_local")
    all_data = Preset_Local.find({}, toarray=True)
    if all_data:
        for item in all_data:
            rule_dict = item.get("_rule")
            platform_list.append(rule_dict.get("os"))
        return list(set(platform_list))
    else:
        return []


def _get_source_list(platform=_ANDROID, package=""):
    cond = {}
    source_list = []
    if platform:
        cond["_rule.os"] = platform
    if package:
        cond["_rule.packages"] = package
        Preset_Local = classing_model("preset_local")
        all_data = Preset_Local.find(cond, toarray=True)
        if all_data:
            for item in all_data:
                rule_dict = item.get("_rule")
                source_list = source_list + rule_dict.get("sources")
            return list(set(source_list))
        else:
            return []
    else:
        return []


def _get_package_list(platform=_ANDROID):
    cond = {}
    if platform:
        cond["_rule.os"] = platform
        Preset_Local = classing_model("preset_local")
        all_data = Preset_Local.find(cond, toarray=True)
        package_list = []
        if all_data:
            for item in all_data:
                rule_dict = item.get("_rule")
                package_list = package_list + rule_dict.get("packages")
            return list(set(package_list))
        else:
            return []
    else:
        return []


def _get_all_list(platform=_ANDROID):
    cond = {}
    all_list = []
    package_list = []
    if platform:
        cond["_rule.os"] = platform
    Preset_Local = classing_model("preset_local")
    all_data = Preset_Local.find(cond, fields={"_id": 0}, toarray=True)
    if all_data:
        for item in all_data:
            rule_dict = item.get("_rule")
            package_list = package_list + rule_dict.get("sources")
        package_list = list(set(package_list))
        for package in package_list:
            item_dict = {}
            item_dict["display_value"] = package
            item_dict["value"] = package
            all_list.append(item_dict)
        all_list.append({"display_value": "ALL", "value": ""})
    return all_list


def _get_locale_list(platform=_ANDROID):
    Preset_Local = classing_model("preset_local")
    locale_list = []
    return_items = []
    cond = {}
    if platform:
        cond['_rule.os'] = platform
    all_data = Preset_Local.find(cond, toarray=True)
    if all_data:
        for item in all_data:
            rule_dict = item.get("_rule")
            locale_list = locale_list + rule_dict.get("locales")
        locale_list = list(set(locale_list))
        for locale in locale_list:
            locale_dict = {}
            locale_dict["display_value"] = locale
            locale_dict["value"] = locale
            return_items.append(locale_dict)
        return sorted(return_items, key=itemgetter("display_value"))
    else:
        return []


def _get_country_locale(platform=_ANDROID):
    return_items = []
    countrylist_dict = {}
    locales = _get_locale_list(platform)
    if locales:
        for locale in locales:
            locale_strs = locale["value"].split('_')
            if len(locale_strs) == 2:
                country_short = locale_strs[1]
                countrylist_dict.setdefault(
                    country_short, []).append(locale["value"])
    if countrylist_dict:
        countries_configed = {}
        countries = LOCAL_DB.countries.find()
        for coun in countries:
            countries_configed[coun.get("short_name")] = coun.get("long_name")
        for key in countrylist_dict:
            country_dict = {"children": {"items": []}}
            if countries_configed.get(key):
                country_dict["display_value"] = countries_configed[key] +\
                    "(" + key + ")"
                country_dict["value"] = key
                country_locales = countrylist_dict[key]
                for locale in country_locales:
                    locale_dict = {}
                    locale_dict["display_value"] = locale
                    locale_dict["value"] = locale
                    country_dict["children"]["items"].append(locale_dict)
                return_items.append(country_dict)
        all_dict = {
            "display_value": "ALL", "value": "", "children": {"items": []}}
        all_dict["children"]["items"] = locales
        return_items.append(all_dict)
    return return_items


def get_export_filters():
    all_filters = {}
    filters = {"name": "platform", "items": []}
    platform_list = _get_platform_list()
    for platform in platform_list:
        plat_children = {"name": "package", "items": []}
        platform_item = {"display_value": "", "value": "", "children": {}}
        package_list = _get_package_list(platform)
        '''
        all_package_dict = {
            "display_value": "All", "value": "",
            "children": {"items": [], "name": "source"}}
        '''
        for package in package_list:
            package_children = {"name": "source", "items": []}
            package_item = {
                "display_value": "", "value": "", "children": {}}
            source_list = _get_source_list(platform, package)
            # all_source_dict = {"display_value": "All", "value": ""}
            for source in source_list:
                source_item = {"display_value": "", "value": ""}
                source_item["display_value"] = source
                source_item["value"] = source
                package_children["items"].append(source_item)
            package_item["display_value"] = package
            package_item["value"] = package
            package_item["children"] = package_children
            plat_children["items"].append(package_item)
            # package_children["items"].append(all_source_dict)
        platform_item["display_value"] = platform
        platform_item["value"] = platform
        platform_item["children"] = plat_children
        filters["items"].append(platform_item)
        # all_package_dict["children"]["items"] = _get_all_list(platform)
        # plat_children["items"].append(all_package_dict)
    countries = _get_country_locale()
    all_filters["filters"] = filters
    all_filters["countries"] = countries
    return all_filters


def classing_model(model_name):
    '''
    type method can be used as a metaclass funtion, when a string "model_name"
    came, it can be return the class
    '''
    if MODELS.get(model_name):
        ATTRS = MODELS.get(model_name)
        return type(model_name, (ModelBase,), ATTRS)
    else:
        return None
