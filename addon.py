import m3u8
import urlparse
import urllib
import xbmc
import xbmcgui
import xbmcplugin
from resources.lib import hgtv
from resources.lib.kodiutils import get_string, set_setting, get_setting

base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
args = urlparse.parse_qs(sys.argv[2][1:])

if addon_handle >= 0:
    xbmcplugin.setContent(addon_handle, 'tvshows')

def build_url(query):
    return base_url + '?' + urllib.urlencode(query)

def print_log(s):
    xbmc.log(s, level=xbmc.LOGNOTICE)

mode = args.get('mode', None)

if mode is None:
    url = build_url({'mode': 'shows'})
    li = xbmcgui.ListItem('Shows', iconImage='DefaultFolder.png')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    xbmcplugin.endOfDirectory(addon_handle)

elif mode[0] == 'authenticate':
    print_log('Authenticate Device')
    hgtv_handle = hgtv.HGTV()
    auth_info = hgtv_handle.setupAuthentication()
    if auth_info:
        dialog = xbmcgui.Dialog()
        print_log(str(auth_info))
        ok = dialog.yesno(get_string(30310),
                          get_string(30320) % auth_info['activation_url'],
                          get_string(30330) % auth_info['user_code'],
                          get_string(30340),
                          get_string(30360),
                          get_string(30350))
        if ok:
            print_log(str(hgtv_handle.headers))
            hgtv_handle.checkAuthentication()
            set_setting('LoggedInToTvProvider', True)

elif mode[0] == 'logoutprovider':
    print_log('Deauthenticate Device')
    hgtv_handle = hgtv.HGTV()
    hgtv_handle.deauthorize()
    set_setting('LoggedInToTvProvider', False)

elif mode[0] == 'play':
    url = args.get('playbackUrl', None)
    if url is not None:
        url = url[0]
        if url != 'AUTH_NEEDED':
            hgtv_handle = hgtv.HGTV()
            print_log(url)
            stream_url, txt = hgtv_handle.playURL(url)
            li = xbmcgui.ListItem(path=stream_url)
            li.setProperty('isFolder', 'false')
            li.setProperty('isPlayable', 'true')
            li.setProperty('inputstreamaddon', 'inputstream.hls')
            li.setProperty('inputstream.hls.manifest_type', 'hls')
            xbmcplugin.setResolvedUrl(addon_handle, True, listitem=li)

else:
    if mode[0] == 'shows':
        hgtv_handle = hgtv.HGTV()
        shows = hgtv_handle.getShows()
        for show in shows:
            url = build_url({'mode': 'seasons', 'show_id': show.id})
            li = xbmcgui.ListItem(show.name, iconImage='DefaultFolder.png')
            li.setInfo('video', {'plot': show.description, 'mediatype': 'tvshow'})
            li.setArt({'poster': show.art, 'fanart': show.art, 'banner': show.art})
            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)

    elif mode[0] == 'seasons':
        show_id = args.get('show_id', None)
        if show_id is not None:
            show_id = show_id[0]
            hgtv_handle = hgtv.HGTV()
            show = hgtv_handle.getShow(show_id)
            seasons = show.getSeasons()

            for season in seasons:
                url = build_url({'mode': 'episodes', 'show_id': show.id, 'season_id': season.id})
                li = xbmcgui.ListItem(season.name, iconImage='DefaultFolder.png')
                li.setInfo('video', {'season': season.number, 'mediatype': 'season'})
                li.setArt({'poster': season.art, 'fanart': season.art, 'banner': season.art})
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)

    elif mode[0] == 'episodes':
        show_id = args.get('show_id', None)
        if show_id is not None:
            show_id = show_id[0]
            season_id = args.get('season_id', None)
            if season_id is not None:
                season_id = season_id[0]
                hgtv_handle = hgtv.HGTV()
                show = hgtv_handle.getShow(show_id)
                seasons = show.getSeasons()
                for season in seasons:
                    if season_id == season.id:
                        episodes = season.getEpisodes()
                        for episode in episodes:
                            url = build_url({'mode': 'play', 'playbackUrl': episode.getPlaybackURL()})
                            li = xbmcgui.ListItem(episode.name, iconImage='DefaultVideo.png')
                            li.setInfo('video', {'plot': episode.description, 'season': episode.season_num, 'episode': episode.episode_num, 'mediatype': 'episode'})
                            li.setArt({'poster': episode.art, 'fanart': episode.art, 'banner': episode.art})
                            li.setProperty('isFolder', 'false')
                            li.setProperty('isPlayable', 'true')
                            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)

    xbmcplugin.endOfDirectory(addon_handle)

