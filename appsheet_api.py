import copy
import json
import datetime
import argparse
import requests

from config import Config
from dbg import ppd, log, set_dbg_level, dbg

BODY = {
"Properties": {
   "Locale": "en-US",
   "Timezone": "Pacific Standard Time",
},
"Rows": [
]
}

SEND_AC = True
SEND_OPS = True
SEND_CPES = True

class Appsheet:
    def __init__(self):
        self.config = Config()
        self.headers = {"ApplicationAccessKey":
            self.config.private_vars["appsheet"]["accesskey"]}

    def aircraft_lookup(self, tail, wholeobj=False):
        log("aircraft_lookup %s" % (tail))

        body = copy.deepcopy(BODY)
        body["Action"] = "Find"
        body["Properties"]["Selector"] = "Filter(Aircraft, [Regno] = \"%s\")" % tail
        #ppd(body)
        try:
            if SEND_AC:
                ret = self.sendop(self.config.private_vars["appsheet"]["aircraft_url"], body)
                log("op returned %s" % ret)
                if ret:
                    log("returning "+ ret[0]["Row ID"])
                    if wholeobj: return ret[0]
                    else: return ret[0]["Row ID"]
                return ret
        except Exception:
            log("aircraft_lookup op raised exception")

        return None

    def add_aircraft(self, regno, test=False, description=""):
        log("add_aircraft %s" % (regno))

        body = copy.deepcopy(BODY)
        body["Action"] = "Add"
        body["Rows"] = [{
            "regno": regno,
            "test": test,
            "description": description
        }]
        #ppd(self.headers)
        #ppd(body)
        try:
            if SEND_AC or "616" in regno or "818" in regno:
                ret = self.sendop(self.config.private_vars["appsheet"]["aircraft_url"], body)
                log("op returned %s" % ret)
                return ret["Rows"][0]["Row ID"] # XXX think about exception
        except Exception:
            log("add_aircraft op raised exception")

        return None

    def get_all_entries(self, table):
        log("get_all_entries " + table)

        body = copy.deepcopy(BODY)
        body["Action"] = "Find"
        #ppd(body)
        url = table + "_url"
        try:
            ret = self.sendop(self.config.private_vars["appsheet"][url], body)
            if ret:
                return ret
        except Exception:
            pass
        return None

    def delete_all_entries(self, table):
        allentries = self.get_all_entries(table)
        deleterows = []
        for op in allentries:
            deleterows.append({"Row ID": op["Row ID"]})

        dbg("delete rows are " + str(deleterows))

        body = copy.deepcopy(BODY)
        body["Action"] = "Delete"
        body["Rows"] = deleterows
        url = table + "_url"
        ppd(body)
        ret = self.sendop(self.config.private_vars["appsheet"][url], body)
        log("op returned %s" % ret)

    def add_op(self, aircraft, time, scenic, optype, flight_name):
        log("add_op %s %s" % (aircraft, optype))
        optime = datetime.datetime.fromtimestamp(time)

        body = copy.deepcopy(BODY)
        body["Action"] = "Add"
        body["Rows"] = [{
            "Aircraft": aircraft,
            "Scenic": scenic,
            #"test": True,
            "manual": False,
            "optype": optype,
            "Time": optime.strftime("%m/%d/%Y %H:%M:%S"),
            "Flight Name": flight_name
        }]

        try:
            if SEND_OPS:
                ret = self.sendop(self.config.private_vars["appsheet"]["ops_url"], body)
                log(f"op returned {ret}")
                return True
        except Exception:
            log("add_op raised exception")

        return None

    def add_cpe(self, flight1, flight2, latdist, altdist, time):
        log("add_cpe %s %s" % (flight1, flight2))
        optime = datetime.datetime.fromtimestamp(time)

        body = copy.deepcopy(BODY)
        body["Action"] = "Add"
        body["Rows"] = [{
            "Aircraft1": flight1,
            "Aircraft2": flight2,
            "Time": optime.strftime("%m/%d/%Y %H:%M:%S"),
            "Min alt sep": altdist,
            "Min lat sep": latdist*6076
        }]
        ppd(body)
        try:
            if SEND_CPES:
                ret = self.sendop(self.config.private_vars["appsheet"]["cpe_url"], body)
                log("op returned %s" % ret)
                return ret["Rows"][0]["Row ID"]
        except Exception:
            log("add_cpe op raised exception")
        return None

    def update_cpe(self, flight1, flight2, latdist, altdist, time, rowid):
        log("update_cpe %s %s" % (flight1, flight2))
        optime = datetime.datetime.fromtimestamp(time)
        body = copy.deepcopy(BODY)
        body["Action"] = "Edit"
        body["Rows"] = [{
            "Row ID": rowid,
            "Aircraft1": flight1,
            "Aircraft2": flight2,
            "Time": optime.strftime("%m/%d/%Y %H:%M:%S"),
            "Min alt sep": altdist,
            "Min lat sep": latdist*6076,
            "Final": True
        }]
        ppd(body)

        try:
            if SEND_CPES:
                ret = self.sendop(self.config.private_vars["appsheet"]["cpe_url"], body)
                log("op returned %s" % ret)
                return ret
        except Exception:
            log("update_cpe op raised exception")
        return None

    def sendop(self, url, body):
        log("sending to url "+url)
        response_dict = None
        response = requests.post(
            url,
            headers=self.headers, json=body, timeout=30)
        if response.status_code != 200:
            ppd(response)
            raise Exception("op fail")
        #ppd(response)
        if not response.text: return None
        response_dict = json.loads(response.text)
        #log("sendop response_dict: %s" % response_dict)

        if not len(response_dict): return None

        return response_dict

# XXX need to figure out restart story.  exception raised above

# for manual testing only:
if __name__ == "__main__":
    set_dbg_level(2)
    as_instance = Appsheet()

    parser = argparse.ArgumentParser(description="match flights against kml bounding boxes")
    parser.add_argument("--get_all_ops", action="store_true")
    parser.add_argument("--delete_all_ops", action="store_true")
    parser.add_argument("--delete_all_pilots", action="store_true")
    parser.add_argument("--delete_all_aircraft", action="store_true")
    parser.add_argument("--delete_all_abes", action="store_true")
    parser.add_argument("--delete_all_notes", action="store_true")

    args = parser.parse_args()

    if args.get_all_ops: print(as_instance.get_all_ops())
    if args.delete_all_ops:
        confirm = input("Deleting all ops. Are you sure? (y/n): ")
        if confirm.lower() == 'y':
            as_instance.delete_all_entries("ops")
    if args.delete_all_pilots:
        confirm = input("Deleting all pilots. Are you sure? (y/n): ")
        if confirm.lower() == 'y':
            as_instance.delete_all_entries("pilot")
    if args.delete_all_aircraft:
        confirm = input("Deleting all aircraft. Are you sure? (y/n): ")
        if confirm.lower() == 'y':
            as_instance.delete_all_entries("aircraft")
    if args.delete_all_abes:
        confirm = input("Deleting all ABEs. Are you sure? (y/n): ")
        if confirm.lower() == 'y':
            as_instance.delete_all_entries("cpe")
    if args.delete_all_notes:
        confirm = input("Deleting all notes. Are you sure? (y/n): ")
        if confirm.lower() == 'y':
            as_instance.delete_all_entries("notes")