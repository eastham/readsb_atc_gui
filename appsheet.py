import requests
import json

from config import Config
from dbg import ppd

BODY = {
"Action": "Find",
"Properties": {
   "Locale": "en-US",
   "Timezone": "Pacific Standard Time",
},
"Rows": [
]
}

class Appsheet:
    def __init__(self):
        self.config = Config()
        self.headers = {"ApplicationAccessKey":
            self.config.private_vars["appsheet"]["accesskey"]}

    def id_to_field(self, id, field):
        body = BODY
        body["Properties"]["Selector"] = "Filter(Pilots, CONTAINS([aircraft],'%s'))" % id

        ## TODO: caching
        ## todo more than one match...

        try:
            response = requests.post(
                self.config.private_vars["appsheet"]["piloturl"],
                headers=self.headers, json=body)
            response_dict = json.loads(response.text)
            return response_dict[0][field]
        except:
            return ""

    def id_to_key(self, id):
        self.id_to_field(id, "Key")

    def id_to_code(self, id):
        self.id_to_field(id, "Pilot Code")
