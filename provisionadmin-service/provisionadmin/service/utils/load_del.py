 # -*- coding: utf-8 -*-
import simplejson
import logging
import types
from operator import itemgetter
from provisionadmin.model.preset import (
    classing_model, check_in_ec2, remove_from_ec2)
from provisionadmin.utils.respcode import (
    ONLINE_DATA_UNDELETE, DUPLICATE_DELETE)
from provisionadmin.utils.common import unixto_string

from provisionadmin.service.views.resource import _update_icon_info
from provisionadmin.service.views.gesture import _update_gesture_info
from provisionadmin.utils.userlog import _save_to_log, _remove_other_log
from provisionadmin.service.utils.preset_tool import _get_local_package_preset


_LOGGER = logging.getLogger("view")
_ANDROID = "android"
_ADMIN = "admin"
_LOCAL = "local"
_CHINA = "china"
_EC2 = "ec2"
All_FLAG = "all_condition"
_GENERAL_SEARCH = 101


def _get_icon_url(icon_dict={}, server_name=_LOCAL):
    if not icon_dict:
        return ""
    else:
        icon_id = icon_dict.get("id")
        icon_list = []
        icon_list.append(icon_id)
        icon_info = _update_icon_info(icon_list, server_name)[0]
        _remove_other_log()
        if icon_info:
            icon = icon_info[0]
            url_name = "%s_url" % server_name
            return icon.get(url_name)
        else:
            return ""


def _get_gesture_url(gesture_dict={}, server_name=_LOCAL):
    if not gesture_dict:
        return ""
    else:
        gesture_id = gesture_dict.get("id")
        gesture_list = []
        gesture_list.append(gesture_id)
        gesture_info_list = _update_gesture_info(gesture_list, server_name)[0]
        _remove_other_log()
        server_url = "%s_url" % server_name
        if gesture_info_list:
            gesture_info = gesture_info_list[0]
            return gesture_info.get(server_url)
        else:
            return ""


def _package_share(shareid, server_name):
    share_dict = {}
    share_content_dict = {}
    ShareContent = classing_model("aossharecontent")
    Template = classing_model("aostemplateshare")
    Recommend = classing_model("aosrecommendshare")
    sharecontent = ShareContent.find(
        {"id": shareid}, one=True, toarray=True)
    if not sharecontent:
        return {}
    share_content_dict["app_url"] = sharecontent.get("app_url")
    share_content_dict["webpage_template"] = sharecontent.get(
        "webpage_template")
    homepage_template = []
    templateshare_list = sharecontent.get("aostemplateshare")
    if templateshare_list:
        for template in templateshare_list:
            template_id = template.get("id")
            temp = Template.find(
                {"id": int(template_id)}, one=True, toarray=True)
            homepage_template.append(temp.get("template_text"))
    share_content_dict["homepage_template"] = homepage_template
    share_dict["share_content"] = share_content_dict
    recommend_shares = []
    recommend_shares_ids = sharecontent.get("aosrecommendshare")
    if recommend_shares_ids:
        for id_dict in recommend_shares_ids:
            temp_dict = {}
            recommend_id = id_dict.get("id")
            temp = Recommend.find(
                {"id": int(recommend_id)}, one=True, toarray=True)
            temp_dict["unique_name"] = temp.get("title")
            temp_dict["icon"] = _get_icon_url(temp.get("icon"), server_name)
            temp_dict["share_url"] = temp.get("url")
            temp_dict["package_name"] = temp.get("packagename")
            temp_dict["title"] = temp.get("name")
            recommend_shares.append(temp_dict)
    share_dict["recommend_shares"] = recommend_shares
    return share_dict


def _package_speeddials(desktopid, server_name):
    Destop = classing_model("aosspeeddialdesktop")
    Screen = classing_model("aosspeeddialscreen")
    Folder = classing_model("aosspeeddialfolder")
    Item = classing_model("aosspeeddial")
    screen_list = []
    des = Destop.find({"id": int(desktopid)}, one=True)
    screen_ids = des.get("aosspeeddialscreen")
    if screen_ids:
        for screen_id in screen_ids:
            screen_dict = {}
            screen_dict["id"] = screen_id.get("id")
            screen_capture = []
            screen = Screen.find(
                {"id": int(screen_id.get("id"))}, one=True, toarray=True)
            screen_dict["sid"] = int(screen.get("sid"))
            fold_ids = screen.get("aosspeeddialfolder")
            item_ids = screen.get("aosspeeddial")
            for item_id in item_ids:
                item_dict = {}
                item = Item.find(
                    {"id": int(item_id.get("id"))},
                    one=True, toarray=True)
                item_dict["url"] = item.get("url")
                item_dict["ico"] = _get_icon_url(item.get("icon"), server_name)
                item_dict["ttl"] = item.get("name")
                item_dict["d"] = item.get("allowdel")
                if item_id.get("order") is None:
                    item_dict["p"] = 0
                else:
                    item_dict["p"] = int(item_id.get("order"))
                screen_capture.append(item_dict)
            for fold_id in fold_ids:
                fold_dict = {}
                if fold_id.get("order") is None:
                    fold_dict["p"] = 0
                else:
                    fold_dict["p"] = int(fold_id.get("order"))
                folder = Folder.find(
                    {"id": int(fold_id.get("id"))},
                    one=True, toarray=True)
                item_ids_infolder = folder.get("aosspeeddial")
                item_list = []
                for item_id in item_ids_infolder:
                    item_dict = {}
                    item = Item.find(
                        {"id": int(item_id.get("id"))},
                        one=True, toarray=True)
                    item_dict["url"] = item.get("url")
                    item_dict["ico"] = _get_icon_url(
                        item.get("icon"), server_name)
                    item_dict["ttl"] = item.get("name")
                    item_dict["d"] = item.get("allowdel")
                    if item_id.get("order"):
                        item_dict["p"] = int(item_id.get("order"))
                    else:
                        item_dict["p"] = 0
                    item_list.append(item_dict)
                fold_dict["its"] = sorted(item_list, key=itemgetter("p"))
                fold_dict["ttl"] = folder.get("name")
                if fold_id.get("order") is None:
                    fold_dict["p"] = 0
                else:
                    fold_dict["p"] = int(fold_id.get("order"))
                screen_capture.append(fold_dict)
            screen_dict["its"] = sorted(screen_capture, key=itemgetter("p"))
            screen_list.append(screen_dict)
    return screen_list


def _package_bookmarks(bookmarks, bookmark_folders):
    Bookmark = classing_model("aosbookmark")
    Bookmarkfolder = classing_model("aosbookmarkfolder")
    bookmark_list = []
    if bookmarks:
        for bookmark_id in bookmarks:
            bookmark_dict = {}
            bookmark = Bookmark.find(
                {"id": int(bookmark_id.get("id"))}, one=True, toarray=True)
            bookmark_dict["name"] = bookmark.get("name")
            bookmark_dict["url"] = bookmark.get("url")
            if bookmark_id.get("order") is None:
                bookmark_dict["order"] = 0
            else:
                bookmark_dict["order"] = int(bookmark_id.get("order"))
            bookmark_list.append(bookmark_dict)
    if bookmark_folders:
        for bookmarkfolder_id in bookmark_folders:
            bookmarkfolder = Bookmarkfolder.find(
                {"id": int(bookmarkfolder_id.get("id"))},
                one=True, toarray=True)
            fold_dict = {}
            item_list = []
            item_ids = bookmarkfolder.get("aosbookmark")
            for item_id in item_ids:
                bookmark_dict = {}
                bookmark = Bookmark.find(
                    {"id": int(item_id.get("id"))}, one=True, toarray=True)
                bookmark_dict["name"] = bookmark.get("name")
                bookmark_dict["url"] = bookmark.get("url")
                if item_id.get("order") is None:
                    bookmark_dict["order"] = 0
                else:
                    bookmark_dict["order"] = int(item_id.get("order"))
                item_list.append(bookmark_dict)
            fold_dict["bookmarks"] = sorted(item_list, key=itemgetter("order"))
            fold_dict["name"] = bookmarkfolder.get("name")
            if bookmarkfolder_id.get("order") is None:
                fold_dict["order"] = 0
            else:
                fold_dict["order"] = int(bookmarkfolder_id.get("order"))
            bookmark_list.append(fold_dict)
    return sorted(bookmark_list, key=itemgetter("order"))


def _package_searchers(searcher_folders, server_name=_LOCAL):
    Searcher = classing_model("aossearcher")
    Searcherfolder = classing_model("aossearcherfolder")
    search_engines = []
    for folder_id in searcher_folders:
        folder_dict = {}
        search_list = []
        folder = Searcherfolder.find(
            {"id": int(folder_id.get("id"))}, one=True, toarray=True)
        defalut_id = folder.get("defaultCheck")
        item_ids = folder.get("aossearcher")
        default_count = 0
        for item_id in item_ids:
            item_dict = {}
            item = Searcher.find(
                {"id": int(item_id.get("id"))}, one=True, toarray=True)
            extend_dict = item.get("extend")
            if item_id.get("id") == defalut_id:
                item_dict["default"] = True
            else:
                item_dict["default"] = False
                default_count = default_count + 1
            item_dict["id"] = item.get("id")
            item_dict["suggest"] = item.get("suggest")
            item_dict["url"] = item.get("url")
            if item.get("logo"):
                item_dict["logo"] = _get_icon_url(
                    item.get("logo"), server_name)
            item_dict["icon"] = _get_icon_url(item.get("icon"), server_name)
            if item.get("logo"):
                item_dict["logo"] = _get_icon_url(
                    item.get("logo"), server_name)
            else:
                item_dict["logo"] = item_dict["icon"]
            if extend_dict:
                try:
                    extend_dict = simplejson.loads(extend_dict)
                except:
                    raise ValueError("searcher:%s is not jsonformat" % item_id)
            else:
                item_dict["unique_name"] = item.get("unique_name")
            if isinstance(extend_dict, types.DictType):
                for key in extend_dict:
                    item_dict[key] = extend_dict[key]
            item_dict["title"] = item.get("name")
            if item_id.get("order") is None:
                item_dict["order"] = 0
            else:
                item_dict["order"] = int(item_id.get("order"))
            search_list.append(item_dict)
        if default_count == len(item_ids):
            _LOGGER.error("no default searcher")
        folder_dict["title"] = folder.get("name")
        folder_dict["layout"] = _GENERAL_SEARCH
        folder_dict["searches"] = sorted(search_list, key=itemgetter("order"))
        search_engines.append(folder_dict)
    return search_engines


def _package_ruledata(ruleid):
    Ruledata = classing_model("aosruledata")
    Source = classing_model("aossource")
    Locale = classing_model("aoslocale")
    Operator = classing_model("aosoperator")
    Package = classing_model("aospackage")
    rule = Ruledata.find({"id": ruleid}, one=True, toarray=True)
    locale_ids = rule.get("aoslocale")
    operator_ids = rule.get("aosoperator")
    package_ids = rule.get("aospackage")
    source_ids = rule.get("aossource")
    locale_list = []
    if locale_ids == [] or locale_ids == [0]:
        locale_list.append(All_FLAG)
    else:
        for locale_id in locale_ids:
            locale = Locale.find(
                {"id": locale_id}, one=True, toarray=True)
            locale_list.append(locale.get("name"))
    operator_list = []
    if operator_ids == [] or operator_ids == [0]:
        operator_list.append(All_FLAG)
    else:
        for operator_id in operator_ids:
            operator = Operator.find(
                {"id": operator_id}, one=True, toarray=True)
            operator_list.append(operator.get("code"))
    packagename_list = []
    if package_ids:
        for package_id in package_ids:
            package = Package.find(
                {"id": package_id}, one=True, toarray=True)
            packagename_list.append(package.get("package_name"))
    source_list = []
    if source_ids == [] or source_ids == [0]:
        source_list.append(All_FLAG)
    else:
        for source_id in source_ids:
            source = Source.find(
                {"id": source_id}, one=True, toarray=True)
            source_list.append(source.get("title"))
    rule_dict = {}
    rule_dict["min_version"] = rule.get("min_version")
    rule_dict["max_version"] = rule.get("max_version")
    rule_dict["locales"] = locale_list
    rule_dict["sources"] = source_list
    rule_dict["packages"] = packagename_list
    rule_dict["operators"] = operator_list
    rule_dict["os"] = _ANDROID
    return rule_dict


def package_one_predata(rawid, server_name=_LOCAL):
    pre_dict = {}
    check_success = True
    msg = ""
    # init classes
    Predata = classing_model("aospredata")
    Gesture = classing_model("aosgesture")
    Strategy = classing_model("aosstrategy")
    predata = Predata.find(cond={"id": rawid}, one=True, toarray=True)
    predata_dict = {}
    # package share
    share_dict = {}
    share_content_id = predata.get("aossharecontent")
    if share_content_id:
        share_dict = _package_share(
            int(share_content_id.get("id")), server_name)
    predata_dict["shares"] = share_dict
    # print share_dict
    # package speeddials
    speeddial_destop = predata.get("aosspeeddialdesktop")
    speeddial_list = []
    if speeddial_destop:
        speeddial_list = _package_speeddials(
            speeddial_destop.get("id"), server_name)
    predata_dict["speeddials"] = speeddial_list
    # print speeddial_list
    # package bookmark
    bookmarks = predata.get("aosbookmark")
    bookmark_folders = predata.get("aosbookmarkfolder")
    bookmark_list = []
    if bookmarks or bookmark_folders:
        bookmark_list = _package_bookmarks(bookmarks, bookmark_folders)
    predata_dict["bookmarks"] = bookmark_list
    # search engine
    searcher_folders = predata.get("aossearcherfolder")
    search_engines = []
    if searcher_folders:
        search_engines = _package_searchers(searcher_folders, server_name)
        if search_engines is None:
            check_success = False
            msg = 'no default search engine'
    predata_dict["search_engines"] = search_engines
    # print search_engines
    # Strategy
    strategy = predata.get("aosstrategy")
    strategy_dict = {}
    if strategy:
        strategy = Strategy.find(
            {"id": int(strategy.get("id"))}, one=True)
        strategy_dict["duration"] = strategy.get("duration")
        strategy_dict["tutorials"] = strategy.get("tutorials").split(',')
        strategy_dict["strategy_test"] = False
        strategy_dict["id"] = strategy.get("id")
    predata_dict["strategy"] = strategy_dict
    # gesture
    gesture = predata.get("aosgesture")
    gesture_dict = {}
    if gesture:
        gesture_item = Gesture.find(
            {"id": int(gesture.get("id"))}, one=True)
        gesture_dict["marked_file"] = gesture_item.get("marked_file")
        try:
            gesture_dict["user_gesture_file"] = _get_gesture_url(
                gesture_item, server_name)
        except:
            check_success = False
            msg = 'package gesture file error'
    predata_dict["gesture"] = gesture_dict
    #  rule configure
    rule_id = predata.get("aosruledata")
    rule_dict = {}
    if rule_id:
        rule_dict = _package_ruledata(int(rule_id.get("id")))
        if rule_dict.get("packages"):
            pre_dict["_rule"] = rule_dict
        else:
            pre_dict["_rule"] = {}
            check_success = False
            msg = "package is empty"
    else:
        check_success = False
    # package other fields
    field_list = [
        "more_addon_link", "about",
        "home_page", "rate_me_link", "more_theme_link",
        "hotapps", "check_update_link", "tutorial"]
    for field in field_list:
        predata_dict[field] = predata.get(field)
    predata_dict["show_download_translate"] = False
    predata_dict["data_test"] = False
    predata_dict["id"] = predata.get("id")
    # package predata
    pre_dict["_meta"] = predata_dict
    pre_dict["first_created"] = predata.get("first_created")
    pre_dict["last_modified"] = predata.get("last_modified")
    pre_dict["id"] = predata.get("id")
    # package local preset
    preset_local_dict = {}
    preset_local_dict["id"] = pre_dict["id"]
    preset_local_dict["_rule"] = pre_dict["_rule"]
    preset_local_dict["_meta"] = pre_dict["_meta"]
    return check_success, msg, preset_local_dict


def del_predata(place, rawids, user_name):
    status = 0
    delete_success = []
    delete_failed = []
    Predata = classing_model("aospredata")
    Preset_Local = classing_model("preset_local")
    count = len(rawids)
    if place == _ADMIN:
        for rawid in rawids:
            item = Preset_Local.find(
                {"id": rawid}, fields={"_id": 0}, one=True)
            raw_item = Predata.find({"id": rawid}, fields={"_id": 0}, one=True)
            raw_item["last_modified"] = unixto_string(
                raw_item["last_modified"])
            raw_item["first_created"] = unixto_string(
                raw_item["first_created"])
            lc_pn = _get_local_package_preset(rawid)
            raw_item["aoslocale"] = lc_pn.get("aoslocale")
            raw_item["aospackage"] = lc_pn.get("aospackage")
            if not item:
                count = count - 1
                _save_to_log(user_name, "从控制台删除", rawid, "aospredata")
                Predata.remove({"id": rawid})
                delete_success.append(raw_item)
                _LOGGER.info(
                    "id:%d delete from admin success", rawid)
            else:
                status = ONLINE_DATA_UNDELETE
                delete_failed.append(raw_item)
                _LOGGER.error("id:%d should delete from local first" % rawid)
    elif place == _LOCAL:
        for rawid in rawids:
            if not check_in_ec2(rawid):
                count = count - 1
                item_local = Preset_Local.find(
                    {"id": rawid}, fields={"_id": 0}, one=True)
                if item_local:
                    _save_to_log(
                        user_name, "从测试环境删除", rawid, "aospredata")
                    Preset_Local.remove({"id": rawid})
                    Predata.update(
                        {"id": rawid},
                        {"is_upload_local": False,
                            "release": 1, "upload_local": 0})
                    raw_item = Predata.find(
                        {"id": rawid}, fields={"_id": 0}, one=True)
                    raw_item["last_modified"] = unixto_string(
                        raw_item["last_modified"])
                    raw_item["first_created"] = unixto_string(
                        raw_item["first_created"])
                    raw_item["last_release_ec2"] = unixto_string(
                        raw_item["last_release_ec2"])
                    lc_pn = _get_local_package_preset(rawid)
                    raw_item["aoslocale"] = lc_pn.get("aoslocale")
                    raw_item["aospackage"] = lc_pn.get("aospackage")
                    delete_success.append(raw_item)
                    _LOGGER.info(
                        "id:%d delete from local success", rawid)
                else:
                    raw_item = Predata.find(
                        {"id": rawid}, fields={"_id": 0}, one=True)
                    delete_failed.append(raw_item)
                    status = DUPLICATE_DELETE
            else:
                status = ONLINE_DATA_UNDELETE,
                raw_item = Predata.find(
                    {"id": rawid}, fields={"_id": 0}, one=True)
                raw_item["last_modified"] = unixto_string(
                    raw_item["last_modified"])
                raw_item["first_created"] = unixto_string(
                    raw_item["first_created"])
                raw_item["last_release_ec2"] = unixto_string(
                    raw_item["last_release_ec2"])
                lc_pn = _get_local_package_preset(rawid)
                raw_item["aoslocale"] = lc_pn.get("aoslocale")
                raw_item["aospackage"] = lc_pn.get("aospackage")
                delete_failed.append(raw_item)
                _LOGGER.error("id:%d should delete from ec2 first" % rawid)
    elif place == _EC2:
        for rawid in rawids:
            raw_item = Predata.find({"id": rawid}, fields={"_id": 0}, one=True)
            count = count - 1
            is_del_success = remove_from_ec2(rawid)
            if is_del_success:
                _save_to_log(
                    user_name, "从正式环境删除", rawid, "aospredata")
                Predata.update(
                    {"id": rawid},
                    {"is_upload_ec2": False, "release": 2, "upload_ec2": 0,
                        "last_release_ec2": 0})
                raw_item = Predata.find(
                    {"id": rawid}, fields={"_id": 0}, one=True)
                raw_item["last_modified"] = unixto_string(
                    raw_item["last_modified"])
                raw_item["first_created"] = unixto_string(
                    raw_item["first_created"])
                raw_item["last_release_ec2"] = unixto_string(
                    raw_item["last_release_ec2"])
                lc_pn = _get_local_package_preset(rawid)
                raw_item["aoslocale"] = lc_pn.get("aoslocale")
                raw_item["aospackage"] = lc_pn.get("aospackage")
                delete_success.append(raw_item)
                _LOGGER.info(
                    "id:%d delete from ec2 success", rawid)
            else:
                raw_item = Predata.find(
                    {"id": rawid}, fields={"_id": 0}, one=True)
                delete_failed.append(raw_item)
                status = DUPLICATE_DELETE
    else:
        status = -1
    return status, delete_success, delete_failed
