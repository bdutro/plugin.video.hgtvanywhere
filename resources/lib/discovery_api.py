import urllib
import requests
import base64
import re
from resources.lib.settings_file import SettingsFile

CONFIG_URL = 'https://api.discovery.com/v1/configurations/{}'
CLIENT_SECRET = base64.b64decode('MjQ4OWY0OTRhNGExNzczZTA4NDUxYzI2ZGUyYTE4NjRjZjllNDY0Mw==')
CLIENT_ID = base64.b64decode('NDU2OTEyODg4YTA2MDJmYzhjNDE=')
USER_AGENT = 'Mozilla/5.0 (Linux; Android 9; sdk_google_atv_x86 Build/PSR1.180720.061; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/73.0.3683.90 Mobile Safari/537.36'

TOKEN_REQUEST_DATA = {
    'grant_type': 'client_credentials',
    'client_secret': CLIENT_SECRET,
    'client_id': CLIENT_ID
}

AUTH_REQUEST_DATA = {
    'client_secret': CLIENT_SECRET,
    'client_id': CLIENT_ID
}

ART_WIDTH=1280

SETTINGS_FILE = SettingsFile('auth.json')
SETTINGS = SETTINGS_FILE.settings

def parse_links(link_json_list):
    return {link['rel']: link['href'] for link in link_json_list}

class Episode(object):
    def __init__(self, episode_json):
        self.json = episode_json
        self.name = episode_json['name']

        self.description = ''
        if 'description' in episode_json:
            if 'detailed' in episode_json['description']:
                self.description = episode_json['description']['detailed']
            if self.description == '' and 'standard' in episode_json['description']:
                self.description = episode_json['description']['standard']

        self.season_num = episode_json['season']['number']
        self.episode_num = episode_json['episodeNumber']
        self.authenticated = episode_json['authenticated']
        self.links = parse_links(episode_json['links'])
        self.is_playable = episode_json['isPlayable']
        self.art = parse_links(episode_json['image']['links'])['16x9'].format(width=ART_WIDTH)

    def isPlayable(self):
        return self.is_playable

    def needsAuthentication(self):
        return self.authenticated
    
    def getPlaybackURL(self):
        return self.links['play'] if self.is_playable else 'AUTH_NEEDED'

class Season(object):
    SORT_REGEX = re.compile(r'Season ([0-9]+)')

    def __init__(self, season_json, handle, show_art):
        self.json = season_json
        self.handle = handle
        self.name = season_json['name']
        self.id = season_json['id']
        self.links = parse_links(season_json['links'])
        self.episodes = None
        self.art = show_art
        m = self.SORT_REGEX.search(self.name)
        if m is None:
            self.sort_key = self.name
        else:
            self.sort_key = int(m.group(1))

    def getEpisodes(self):
        if self.episodes is None:
            episodes_resp = self.handle.doAuthenticatedRequest('GET', self.links['episodes'])
            episodes_json = episodes_resp.json()
            episodes_resp.close()
            self.episodes = [Episode(e) for e in episodes_json]

        return self.episodes

class Show(object):
    def __init__(self, show_json, handle):
        self.json = show_json
        self.name = show_json['name']
        self.id = show_json['id']
        self.description = show_json['description']
        self.handle = handle
        self.links = parse_links(show_json['links'])
        self.seasons = None
        self.art = parse_links(show_json['image']['links'])['16x9'].format(width=ART_WIDTH)

    def getSeasons(self):
        if self.seasons is None:
            season_resp = self.handle.doAuthenticatedRequest('GET', self.links['seasons'])
            season_json = season_resp.json()
            season_resp.close()
            self.seasons = [Season(s, self.handle, self.art) for s in season_json]
            self.seasons.sort(key=lambda s: s.sort_key)

        return self.seasons

class DiscoveryAPI(object):
    def __init__(self, channel_string):
        self.headers = {
            'User-Agent': USER_AGENT
        }

        self.config_url = CONFIG_URL.format(channel_string)

        config_resp = requests.get(self.config_url, params={'key': CLIENT_ID}, headers=self.headers)

        self.config_dict = {}
        
        for item in config_resp.json()['links']:
            self.config_dict[item['rel']] = {
                'href': item['href'],
                'method': item['method'],
                'type': item['type']
            }
        config_resp.close()

        access_token = SETTINGS.get('access_token')
        if access_token:
            self.headers['authorization'] = 'Bearer {}'.format(access_token)
            self.has_token = True
            self.authenticated = True
        else:
            self.has_token = False
            self.authenticated = False

        self.shows = None
        self.show_dict = None

    def setupAuthentication(self):
        if not self.authenticated:
            auth_resp = requests.post(self.config_dict['device_authorization']['href'], data=AUTH_REQUEST_DATA)
            auth_dict = auth_resp.json()
            auth_resp.close()
            self.device_code = auth_dict['device_code']
            return auth_dict
        else:
            return None

    def checkAuthentication(self):
        CHECK_AUTH_REQUEST_DATA = {
            'grant_type': 'device_activation',
            'code': self.device_code,
            'client_secret': CLIENT_SECRET,
            'client_id': CLIENT_ID
        }

        check_auth_resp = requests.post(self.config_dict['device_token']['href'], data=CHECK_AUTH_REQUEST_DATA)
        check_auth_resp.raise_for_status()
        check_auth_dict = check_auth_resp.json()
        check_auth_resp.close()

        self.headers['authorization'] = 'Bearer {}'.format(check_auth_dict['access_token'])
        SETTINGS['access_token'] = check_auth_dict['access_token']
        SETTINGS['refresh_token'] = check_auth_dict['refresh_token']
        SETTINGS_FILE.save_settings()
        self.has_token = True
        self.authenticated = True

    def deauthorize(self):
        if self.authenticated:
            deauth_resp = requests.post(self.config_dict['device_deauthorize']['href'], data=AUTH_REQUEST_DATA)
            deauth_resp.close()
            SETTINGS.pop('access_token', None)
            SETTINGS.pop('refresh_token', None)
            SETTINGS_FILE.save_settings()

    def reauthenticate(self):
        REAUTH_REQUEST_DATA = {
            'grant_type': 'refresh_token',
            'refresh_token': SETTINGS['refresh_token'],
            'client_secret': CLIENT_SECRET,
            'client_id': CLIENT_ID
        }

        reauth_resp = requests.post(self.config_dict['device_token']['href'], data=REAUTH_REQUEST_DATA)
        reauth_resp.raise_for_status()
        reauth_dict = reauth_resp.json()
        reauth_resp.close()

        self.headers['authorization'] = 'Bearer {}'.format(reauth_dict['access_token'])
        SETTINGS['access_token'] = reauth_dict['access_token']
        SETTINGS['refresh_token'] = reauth_dict['refresh_token']
        SETTINGS_FILE.save_settings()

        self.has_token = True
        self.authenticated = True

    def getToken(self):
        if not self.has_token:
            token_resp = requests.post(self.config_dict['device_token']['href'], data=TOKEN_REQUEST_DATA)
            token_dict = token_resp.json()
            token_resp.close()

            self.headers['authorization'] = 'Bearer {}'.format(token_dict['access_token'])
            self.has_token = True

    def doAuthenticatedRequest(self, method, url, data=None):
        if method == 'POST':
            req = requests.post
        elif method == 'GET':
            req = requests.get
        else:
            raise ValueError('Unknown request method: ' + method)

        self.getToken()

        resp = None
        try:
            resp = req(url, headers=self.headers)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if self.authenticated and 'refresh_token' in SETTINGS and e.response.status_code == 401:
                # Need to reauthenticate and try again
                self.reauthenticate()
                resp = req(url, data=data, headers=self.headers)
                resp.raise_for_status()
            else:
                raise e
        finally:
            return resp

    def getShows(self):
        if self.shows is None:
            self.getToken()

            shows_resp = self.doAuthenticatedRequest('GET', self.config_dict['shows']['href'])
            shows_resp.raise_for_status()
            shows_dict = shows_resp.json()
            next_url = shows_resp.links['next']['url']
            shows_resp.close()

            while next_url != '':
                shows_resp = self.doAuthenticatedRequest('GET', next_url)
                shows_dict.extend(shows_resp.json())
                next_url = shows_resp.links['next']['url']
                shows_resp.close()

            self.shows = sorted([Show(j, self) for j in shows_dict], key=lambda x: x.name)
            self.show_dict = {show.id : show for show in self.shows}

        return self.shows

    def getShow(self, show_id):
        if self.show_dict is None:
            self.show_dict = {}
        if show_id not in self.show_dict:
            self.getToken()
            show_resp = self.doAuthenticatedRequest('GET', self.config_dict['show_with_id']['href'].format(showId=show_id))
            show_json = show_resp.json()
            show = Show(show_json[0], self)
            self.show_dict[show_id] = show
        return self.show_dict[show_id]
    
    def formatHeaders(self, join_char='',pipes=True):
        return join_char.join(['{}{}={}'.format('|' if pipes else '', urllib.quote_plus(k), urllib.quote_plus(v)) for k,v in self.headers.items()])

    def playURL(self, url):
        self.getToken()
        play_resp = self.doAuthenticatedRequest('GET', url)
        play_json = play_resp.json()
        play_resp.close()
        play_resp = self.doAuthenticatedRequest('GET', play_json['streamUrl'])
        txt = play_resp.text
        play_resp.close()
        return (play_json['ssdaiStreamUrl'], txt)

