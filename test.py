from dbg import dbg, test
from flight import Flight, Location
import time
boot_time = time.time()
last_test_uptime = 0

def test_insert(flights, app):
    global last_test_uptime
    uptime = time.time() - boot_time

    if uptime >= 5 and last_test_uptime < 5:
        dbg("--- Test update 1")
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, gs=100, alt_baro=1000, lat=37.395647,lon=-121.954186), app)
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, gs=100, alt_baro=1000, lat=37.395647,lon=-121.954186), app)
    if uptime >= 7 and last_test_uptime < 7:
        dbg("--- Test update 2")
        # default zone, alt change
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, gs=100, alt_baro=1500, lat=37.434824,lon=-122.185409), app)
        # off map, alt change
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, gs=100, alt_baro=10600, lat=36.395647,lon=-121.954186), app)
    if uptime >= 10 and last_test_uptime < 10:
        dbg("--- Test update 3")
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, gs=100, alt_baro=1500, lat=36.395647,lon=-121.954186), app)
        flights.add_location(Location(flight="**test 1**", now=time.time(), track=0, gs=100, alt_baro=1600, lat=36.395647,lon=-121.954186), app)
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, gs=100, alt_baro=1000, lat=37.395647,lon=-121.954186), app)

    if uptime >= 15 and last_test_uptime < 15:
        # PAO
        dbg("--- Test update 4")
        flights.add_location(Location(flight="**test 2**", now=time.time(), track=0, gs=100, alt_baro=1000, lat=37.461671,lon=-122.121137), app)

    last_test_uptime = uptime
