# -*- coding: utf-8 -*-

import os
import xbmc
import xbmcaddon
import xbmcgui
import sys
import logging
if sys.version_info >= (2, 7):
    import json as json
else:
    import simplejson as json

# read settings
ADDON = xbmcaddon.Addon()

logger = logging.getLogger(__name__)

addon_data_path = xbmc.translatePath(ADDON.getAddonInfo('path')).decode('utf-8')
addon_profile_path = xbmc.translatePath(ADDON.getAddonInfo('profile')).decode('utf-8')


def ensure_profile_path_exists():
    if not os.path.exists(addon_profile_path):
        os.makedirs(addon_profile_path)


def notification(header, message, time=5000, icon=ADDON.getAddonInfo('icon'), sound=True):
    xbmcgui.Dialog().notification(header, message, icon, time, sound)


def show_settings():
    ADDON.openSettings()


def get_setting(setting):
    return ADDON.getSetting(setting).strip().decode('utf-8')


def set_setting(setting, value):
    ADDON.setSetting(setting, str(value))


def get_setting_as_bool(setting):
    return ADDON.getSettingBool(setting)


def get_setting_as_float(setting):
    try:
        return ADDON.getSettingNumber(setting)
    except ValueError:
        return 0


def get_setting_as_int(setting):
    try:
        return ADDON.getSettingInt(setting)
    except ValueError:
        return 0


def get_string(string_id):
    return ADDON.getLocalizedString(string_id).encode('utf-8', 'ignore')


def kodi_json_request(params):
    data = json.dumps(params)
    request = xbmc.executeJSONRPC(data)

    try:
        response = json.loads(request)
    except UnicodeDecodeError:
        response = json.loads(request.decode('utf-8', 'ignore'))

    try:
        if 'result' in response:
            return response['result']
        return None
    except KeyError:
        logger.warn("[{}] {}".format(params['method'], response['error']['message']))
        return None
