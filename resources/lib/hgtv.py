from resources.lib import discovery_api

class HGTV(discovery_api.DiscoveryAPI):
    def __init__(self, access_token=None):
        super(HGTV, self).__init__('hgtvgo', access_token)
