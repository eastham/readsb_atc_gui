# readsb_atc_gui
ATC-style flight strip representations for aircraft seen by readsb.

Given one or more KML files describing some bounding boxes / gates,
this script will attach to a readsb JSON socket, and report when flights are inside the bounding boxes.
Command-line and a Kivy-based GUI are available.

Use cases:
* The main goal here is to facilitate monitoring and statistics-gathering for flight operations at airports.
* Individuals might also be interested in alerting, but this isn't the focus, at least until users like that step forward.

Future work:
* Support for annotation of flight strips on click (partially implemented)
* Clean up CLI output, it's just random debugging output at present
* Support for manually-added flight strips
* Call APIs upon gate entry/exit (for alerts, tracking, adding data to the flight strip, etc)

Other ideas:
* Conflict warnings?
* Lookup origin/destination outputs somehow?
* bring in aircraft registration database somehow?
* Your idea here, not sure what all this might be useful for.  Get in touch or send code.


![Screenshot](screenshot.png)

Command-line Usage:

    python3 aio.py -v  --ipaddr 192.168.87.60 --port 30666 sample_kml/sjc.kml sample_kml/valley.kml

GUI Usage:

    python3 controller.py -- --ipaddr 192.168.87.60 --port 30666 sample_kml/sjc.kml sample_kml/valley.kml

KML format:

Specify gates with Polygons named as follows (Google Earth can do this for you easily):

    [Gate Name]: [minimum altitude]-[maximum altitude] [start heading range]-[end heading range]
example:
    Departure SJC 31:0-2000 250-070
