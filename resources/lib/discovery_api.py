import urllib
import requests
import base64

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

def parse_links(link_json_list):
    return {link['rel']: link['href'] for link in link_json_list}

class Episode(object):
    def __init__(self, episode_json, headers):
        self.json = episode_json
        self.headers = headers
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
    def __init__(self, season_json, headers, show_art):
        self.json = season_json
        self.headers = headers
        self.name = season_json['name']
        self.id = season_json['id']
        self.links = parse_links(season_json['links'])
        self.episodes = None
        self.art = show_art

    def getEpisodes(self):
        if self.episodes is None:
            episodes_resp = requests.get(self.links['episodes'], headers=self.headers)
            episodes_json = episodes_resp.json()
            episodes_resp.close()
            self.episodes = [Episode(e, self.headers) for e in episodes_json]

        return self.episodes

class Show(object):
    def __init__(self, show_json, headers):
        self.json = show_json
        self.name = show_json['name']
        self.id = show_json['id']
        self.description = show_json['description']
        self.headers = headers
        self.links = parse_links(show_json['links'])
        self.seasons = None
        self.art = parse_links(show_json['image']['links'])['16x9'].format(width=ART_WIDTH)

    def getSeasons(self):
        if self.seasons is None:
            season_resp = requests.get(self.links['seasons'], headers=self.headers)
            season_json = season_resp.json()
            season_resp.close()
            self.seasons = [Season(s, self.headers, self.art) for s in season_json]

        return self.seasons

class DiscoveryAPI(object):
    def __init__(self, channel_string, access_token=None):
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

        if access_token:
            self.headers['authorization'] = 'Bearer {}'.format(access_token)
            self.has_token = True
            self.authenticated = True
        else:
            self.has_token = False
            self.authenticated = False

        self.shows = None
        self.show_dict = None

    def getAuthenticationInfo(self):
        if not self.authenticated:
            auth_resp = requests.post(self.config_dict['device_authorization']['href'], data=AUTH_REQUEST_DATA)
            auth_dict = auth_resp.json()
            auth_resp.close()
            return auth_dict
        else:
            return None

    def checkAuthentication(self, auth_info):
        CHECK_AUTH_REQUEST_DATA = {
            'grant_type': 'device_activation',
            'code': auth_info['device_code'],
            'client_secret': CLIENT_SECRET,
            'client_id': CLIENT_ID
        }

        check_auth_resp = requests.post(self.config_dict['device_token']['href'], data=CHECK_AUTH_REQUEST_DATA)
        check_auth_dict = check_auth_resp.json()
        check_auth_resp.close()

        self.headers['authorization'] = 'Bearer {}'.format(check_auth_dict['access_token'])
        self.has_token = True
        self.authenticated = True

        return check_auth_dict

    def deauthorize(self):
        if self.authenticated:
            deauth_resp = requests.post(self.config_dict['device_deauthorize']['href'], data=AUTH_REQUEST_DATA)
            deauth_resp.close()

    def getToken(self):
        if not self.has_token:
            token_resp = requests.post(self.config_dict['device_token']['href'], data=TOKEN_REQUEST_DATA)
            print(token_resp)
            token_dict = token_resp.json()
            token_resp.close()

            self.headers['authorization'] = 'Bearer {}'.format(token_dict['access_token'])
            self.has_token = True

    def getShows(self):
        if self.shows is None:
            self.getToken()
            shows_resp = requests.get(self.config_dict['shows']['href'], headers=self.headers)
            shows_dict = shows_resp.json()
            next_url = shows_resp.links['next']['url']
            shows_resp.close()

            while next_url != '':
                shows_resp = requests.get(next_url, headers=self.headers)
                shows_dict.extend(shows_resp.json())
                next_url = shows_resp.links['next']['url']
                shows_resp.close()

            self.shows = sorted([Show(j, self.headers) for j in shows_dict], key=lambda x: x.name)
            self.show_dict = {show.id : show for show in self.shows}

        return self.shows

    def getShow(self, show_id):
        if self.show_dict is None:
            self.show_dict = {}
        if show_id not in self.show_dict:
            self.getToken()
            show_resp = requests.get(self.config_dict['show_with_id']['href'].format(showId=show_id), headers=self.headers)
            show_json = show_resp.json()
            show = Show(show_json[0], self.headers)
            self.show_dict[show_id] = show
        return self.show_dict[show_id]
    
    def formatHeaders(self, join_char='',pipes=True):
        #return join_char.join(['{}={}'.format(k,v) for k,v in self.headers.items()])
        return join_char.join(['{}{}={}'.format('|' if pipes else '', urllib.quote_plus(k), urllib.quote_plus(v)) for k,v in self.headers.items()])

    def playURL(self, url):
        self.getToken()
        play_resp = requests.get(url, headers=self.headers)
        play_json = play_resp.json()
        play_resp.close()
        play_resp = requests.get(play_json['streamUrl'], headers=self.headers)
        txt = play_resp.text
        play_resp.close()
        return (play_json['ssdaiStreamUrl'], txt)

