# -*- coding: utf-8 -*-
import logging
import os
import errno
import shutil
import simplejson
import urllib
from django.conf import settings
from provisionadmin.decorator import exception_handler, check_session
from provisionadmin.model.preset import classing_model
from provisionadmin.utils.respcode import (
    PARAM_ERROR, METHOD_ERROR, PARAM_REQUIRED,
    ONLINE_DATA_UNDELETE, DATA_RELETED_BY_OTHER, INVALID_NAME, DUPLICATE_FIELD)
from provisionadmin.utils.common import now_timestamp
from provisionadmin.utils import scp
from provisionadmin.utils.json import json_response_error, json_response_ok
from provisionadmin.settings import MEDIA_ROOT
from provisionadmin.utils.userlog import _save_to_log
# from provisionadmin.service.views.preset import _save_to_log

_LOGGER = logging.getLogger("view")
_RESOURCE_BASE_DIR = "preset_gesture/"
_ADMIN = "admin"
_LOCAL = "local"
_CHINA = "china"
_EC2 = "ec2"
DB_SERVERS = settings.REMOTEDB_SETTINGS
S3_DOMAIN = settings.S3_DOMAIN
HOST = settings.HOST
PAGE_SIZE = 20


def _save_file(file_obj):
    file_name = file_obj.name
    resource_path = os.path.join(MEDIA_ROOT, _RESOURCE_BASE_DIR)
    if not os.path.exists(resource_path):
        os.makedirs(resource_path)
    filepath = os.path.join(resource_path, file_name)
    with open(filepath, "wb") as outputfile:
        for chunk in file_obj.chunks():
            outputfile.write(chunk)


def _check_file_name(file_name):
    check_pass = True
    if file_name:
        i = 0
        while i < len(file_name):
            if file_name[i] > chr(127):
                check_pass = False
                break
            else:
                i = i + 1
    else:
        check_pass = False
    return check_pass


@exception_handler()
@check_session
def preset_add_gesture(request, user):
    """
    POST: Save the gesture of document
    Parameters:
        -gesture: the name of gesture file,
        -title: the tile of gesture
        -category: the category of gesture
    Return:
        -1. upload success
            {
                "status": 0,
                "data":{
                       ...
                }
            }
        -2. error http method
            {
                "status": 11,
                "data":{
                       ...
                }
            }
    """
    if request.method == 'POST':
        Gesture = classing_model("aosgesture")
        data = {"msg": []}
        gesturefile = request.FILES.get('gesture_file')
        if not gesturefile:
            data["msg"].append('gesture_file')
        required_list = ("title", "marked_file")
        for required_para in required_list:
            if request.POST.get(required_para) is None:
                data["msg"].append(required_para)
        if data["msg"]:
            return json_response_error(PARAM_REQUIRED, data, msg="param error")

        gesturefile = request.FILES['gesture_file']
        file_name = gesturefile.name
        if not _check_name(file_name):
            data["msg"].append(file_name)
            return json_response_error(
                INVALID_NAME, data, msg="文件名参数包含非法字符")
        resource = {}
        resource["title"] = request.POST.get("title")
        resource["marked_file"] = request.POST.get("marked_file")
        gesture_url = _RESOURCE_BASE_DIR + file_name
        resource["gesture"] = gesture_url
        check_gesture = Gesture.find({"gesture": gesture_url}, one=True)
        if not check_gesture:
            _save_file(gesturefile)
            result = Gesture.insert(resource)
            if result == "unique_failed":
                data["msg"].append(resource["title"])
                return json_response_error(
                    DUPLICATE_FIELD, data, msg="duplicate field")
            else:
                insert_id = result
                data = Gesture.find(
                    {"id": insert_id}, fields={"_id": 0}, one=True)
                _save_to_log(
                    user.get("user_name"), "创建", insert_id, "aosgesture")
                return json_response_ok(data, msg="add gesture success")
        else:
            return json_response_error(
                PARAM_REQUIRED,
                msg="parameter gesture unque error")
    else:
        return json_response_error(METHOD_ERROR, msg="http method wrong")


@exception_handler()
@check_session
def preset_modify_gesture(request, user):
    """
    POST: Save the gesture of document
    Parameters:
        -gesture: the name of gesture file,
        -title: the tile of gesture
        -category: the category of gesture
    Return:
        -1. upload success
            {
                "status": 0,
                "data":{
                       ...
                }
            }
        -2. error http method
            {
                "status": 11,
                "data":{
                       ...
                }
            }
    """
    if request.method == 'POST':
        Gesture = classing_model("aosgesture")
        gesturefile = request.FILES.get('gesture_file')
        required_list = ("title", "marked_file")
        for required_para in required_list:
            if request.POST.get(required_para) is None:
                return json_response_error(
                    PARAM_REQUIRED,
                    msg="parameter %s request" % required_para)
        req_id = int(request.POST.get("id"))
        cond = {}
        cond["id"] = req_id
        resource = {}
        resource["title"] = request.POST.get("title")
        resource["marked_file"] = request.POST.get("marked_file")
        if gesturefile:
            gesturefile = request.FILES['gesture_file']
            file_name = gesturefile.name
            if not _check_file_name(file_name):
                return json_response_error(
                    PARAM_ERROR,
                    msg="parameter文件名包含中文字符")
            gesture_url = _RESOURCE_BASE_DIR + file_name
            check_gesture = Gesture.find(
                {"gesture": gesture_url}, one=True)
            if check_gesture:
                db_id = check_gesture.get("id")
                if req_id == db_id:
                    Gesture.update(cond, resource)
                    data = Gesture.find(
                        {"id": req_id}, fields={"_id": 0}, one=True)
                    return json_response_ok(data, msg="ges file not changed")
                else:
                    return json_response_error(
                        PARAM_ERROR, msg="upload file name is exist!")
            else:
                _save_file(gesturefile)
                resource["gesture"] = gesture_url
                Gesture.update(cond, resource)
                data = Gesture.find(
                    {"id": req_id}, fields={"_id": 0}, one=True)
                _save_to_log(
                    user.get("user_name"), "修改", req_id, "aosgesture")
                return json_response_ok(data, msg="modify gesture success")
        else:
            Gesture.update(cond, resource)
            data = Gesture.find(
                {"id": req_id}, fields={"_id": 0}, one=True)
            _save_to_log(
                user.get("user_name"), "修改", req_id, "aosgesture")
            return json_response_ok(data, msg="ges file not changed")
    else:
        return json_response_error(METHOD_ERROR, msg="http method wrong")


@exception_handler()
@check_session
def preset_upload_gesture(request, user):
    """
    POST: upload resource to server
    Parameters:
        -id: the id of gesture,
    Return:
        -1. upload success
            {
                "status": 0,
                "data":{
                       ...
                }
            }
        -2. error http method
            {
                "status": 11,
                "data":{
                       ...
                }
            }
    """
    if request.method == 'POST':
        temp_strs = request.raw_post_data
        try:
            temp_dict = simplejson.loads(temp_strs)
        except ValueError as expt:
            _LOGGER.error("upload gesture api para except:%s", expt)
            return json_response_error(
                PARAM_ERROR,
                msg="json loads error,check parameters format")
        required_list = ("server", "items")
        for required_para in required_list:
            if temp_dict.get(required_para) is None:
                return json_response_error(
                    PARAM_REQUIRED,
                    msg="parameter %s request" % required_para)
        server = temp_dict.get("server", "local")
        gesture_info = temp_dict.get("items")
        upload_success, upload_failed = _update_gesture_info(
            gesture_info, server, is_del=False, uname=user.get("user_name"))
        data = {}
        data["success"] = upload_success
        data["failed"] = upload_failed
        return json_response_ok(data)
    else:
        return json_response_error(METHOD_ERROR, msg="http method wrong")


def _get_gesture_info(rawids, failed=False):
    Gesture = classing_model("aosgesture")
    gesture_list = []
    if rawids:
        for rawid in rawids:
            gesture_dict = {}
            if failed:
                gesture_dict = Gesture.find(
                    {"id": int(rawid)}, fields={"_id": 0}, one=True)
                ref_preset_id = gesture_dict.get("ref_preset_id")
                refered_info = []
                assert ref_preset_id
                for ref_id in ref_preset_id:
                    ref_dict = {}
                    ref_dict["modelName"] = "aospredata"
                    ref_dict["id"] = ref_id
                    refered_info.append(ref_dict)
                gesture_dict["refered_info"] = refered_info
            gesture_list.append(gesture_dict)
    return gesture_list


@exception_handler()
@check_session
def preset_delete_gesture(request, user):
    """
    POST: delete resource from server
    Parameters:
        -id: the id of gesture,
    Return:
        -1. upload success
            {
                "status": 0,
                "data":{
                       ...
                }
            }
        -2. error http method
            {
                "status": 11,
                "data":{
                       ...
                }
            }
    """
    if request.method == 'POST':
        temp_strs = request.raw_post_data
        try:
            temp_dict = simplejson.loads(temp_strs)
        except ValueError as expt:
            _LOGGER.error("delete gesture api para except:%s", expt)
            return json_response_error(
                PARAM_ERROR,
                msg="json loads error,check parameters format")
        required_list = ("server", "items")
        for required_para in required_list:
            if temp_dict.get(required_para) is None:
                return json_response_error(
                    PARAM_REQUIRED,
                    msg="parameter %s request" % required_para)
        server = temp_dict.get("server", "local")
        gesture_info = temp_dict.get("items")
        data = {}
        if server == "admin":
            result = _delete_gesture_from_admin(
                gesture_info, user.get("user_name"))
            success_list = result[0]
            data["success"] = success_list
            if result[1]:
                failed_list = _get_gesture_info(result[1], failed=True)
                data["failed"] = failed_list
                return json_response_error(ONLINE_DATA_UNDELETE, data)
            elif result[2]:
                failed_list = _get_gesture_info(result[2], failed=True)
                data["failed"] = failed_list
                return json_response_error(DATA_RELETED_BY_OTHER, data)
            else:
                data["failed"] = []
                return json_response_ok(data)
        else:
            delete_success, delete_failed = _update_gesture_info(
                gesture_info, server, is_del=True, uname=user.get("user_name"))
            data = {}
            data["success"] = delete_success
            data["failed"] = delete_failed
            return json_response_ok(data)
    else:
        return json_response_error(METHOD_ERROR, msg="http method wrong")


def _save_gesture_file(file_obj):
    # save pic file to resource path
    gesture_name = file_obj.name
    resource_path = os.path.join(MEDIA_ROOT, _RESOURCE_BASE_DIR)
    if not os.path.exists(resource_path):
        os.makedirs(resource_path)
    gesturefilepath = os.path.join(resource_path, gesture_name)
    with open(gesturefilepath, "wb") as picoutputfile:
        for chunk in file_obj.chunks():
            picoutputfile.write(chunk)


def _upload_file(server, gesture_info, is_del=False):
    is_upload_server = gesture_info.get("is_upload_%s", server)
    if is_del and not is_upload_server:
        return False
    file_obj = gesture_info.get("gesture")
    result = _transfer_file(file_obj, server, is_del)
    return result


def _transfer_file(file_obj, server, is_del=False, from_s3=True):
    if file_obj and server:
        local_base = MEDIA_ROOT
        server_conf = DB_SERVERS[server]
        remote_base = server_conf['remote_base'] if server_conf.get(
            'remote') else '/home/static/resources'
        s3_flag = False
        if from_s3 and server_conf.get('s3_remote'):
            remote_base = server_conf["s3_remote"]
            s3_flag = True
        remote = os.path.join(remote_base, file_obj)
        if is_del:
            if s3_flag:
                try:
                    os.unlink(remote)
                    result = True
                except OSError as e:
                    result = False
            else:
                result = scp.sdel(
                    server_conf["statics"], 'static',
                    '/var/app/data/provisionadmin-service/static.pem', remote)
            return (result, "")
        else:
            local = os.path.join(local_base, file_obj)
            if s3_flag:
                try:
                    mkdir = os.path.dirname(remote)
                    os.makedirs(mkdir)
                except OSError as e:
                    if e.errno != errno.EEXIST:
                        raise ValueError(
                            ('mkdir file path %s for s3 fail') % file_obj)
                try:
                    shutil.copy(local, remote)
                except EnvironmentError as e:
                    raise ValueError(('upload file %s to s3 fail') % file_obj)
                return (True, '%s/%s' % (S3_DOMAIN, file_obj))
            else:
                result = scp.scp(
                    server_conf['statics'], 'static',
                    '/var/app/data/provisionadmin-service/static.pem',
                    local, remote)
                if not result:
                    raise ValueError(('upload file %s fail') % file_obj)
                    return (False,)
                else:
                    return (
                        True, 'http://%s/resources/%s' % (
                            server_conf['domain'], file_obj))


def _delete_gesture_from_admin(gesture_info, uname="admin"):
    gesture = classing_model("aosgesture")
    success_results = []
    online_results = []
    refered_results = []
    for i in gesture_info:
        cond = {}
        gesture_id = int(i) if not isinstance(i, int) else i
        cond["id"] = gesture_id
        gesture_info = gesture.find(cond, one=True)
        if not gesture_info:
            raise ValueError("gesture:%s not in db", gesture_id)
        if gesture_info["ref_preset_id"]:
            _LOGGER.error("gesture:%s already refered", gesture_info['title'])
            refered_results.append(gesture_id)
            continue
        if gesture_info["is_upload_local"] or gesture_info["is_upload_ec2"]:
            online_results.append(gesture_id)
            continue
        # remove old gesture file
        old_gesture_file = gesture_info.get("gesture")
        if old_gesture_file:
            old_gesture_file_path = os.path.join(
                MEDIA_ROOT, old_gesture_file)
            if os.path.exists(old_gesture_file_path):
                os.remove(old_gesture_file_path)
        success_results.append(gesture_id)
        operator = "从控制台删除"
        _save_to_log(uname, operator, gesture_id, "aosgesture")
        gesture.remove(cond)
    else:
        return success_results, online_results, refered_results


def _update_gesture_info(gesture_info, server, is_del=False, uname="admin"):
    Gesture = classing_model("aosgesture")
    is_upload_server = "is_upload_%s" % server
    upload_server = "upload_%s" % server
    server_url = "%s_url" % server
    success_results = []
    failed_results = []
    for i in gesture_info:
        cond = {}
        gesture_id = int(i) if not isinstance(i, int) else i
        cond["id"] = gesture_id
        gesture_info = Gesture.find(cond, fields={"_id": 0}, one=True)
        if not gesture_info:
            raise ValueError("icon:%s not in db", gesture_info['title'])
        if is_del and not gesture_info[is_upload_server]:
            _LOGGER.error("icon:%s already delete", gesture_info['title'])
            continue
        if not is_del and gesture_info[is_upload_server]:
            _LOGGER.info("icon:%s already upload", gesture_info['title'])
        operator = "删除" if is_del else "上传"
        operator = operator + "-" + server
        _save_to_log(uname, operator, gesture_id, "aosgesture")
        file_obj = gesture_info.get("gesture")
        result = _transfer_file(file_obj, server, is_del)
        if result:
            if not result[0]:
                _LOGGER.error("operation:%s failed", gesture_info['title'])
                failed_results.append(gesture_info)
                continue
            gesture_info[is_upload_server] = False if is_del else True
            gesture_info[server_url] = result[1]
            gesture_info[upload_server] = now_timestamp()
            success_results.append(gesture_info)
            # update gesture information in MongoDB
            Gesture.update(cond, gesture_info)
            _LOGGER.info("the id:%s is delete successful", gesture_id)
    else:
        return success_results, failed_results


def _check_name(name):
    encode_name = name.encode('utf-8')
    if len(encode_name) != len(name):
        _LOGGER.warning("The name of %s contains invalid characters.", name)
        return False
    new_name = urllib.quote(name)
    if len(new_name) != len(name):
        _LOGGER.warning("The name of %s contains invalid characters.", name)
        return False
    else:
        return True
