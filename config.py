import yaml
from dbg import ppd

CONFIGPATH = "config.yaml"
PRIVPATH = "private.yaml"

class Config:
    def __init__(self):
        with open(CONFIGPATH, "r") as f:
            self.vars = yaml.safe_load(f)

        self.private_vars = {}
        try:
            with open(PRIVPATH, "r") as f:
                self.private_vars = yaml.safe_load(f)
        except:
            print("No private.yaml found.")
