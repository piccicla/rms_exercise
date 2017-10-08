### change to your path
PGBIN = "C:/Program Files/PostgreSQL/9.6/bin"
###### change browser
BROWSER = "chrome"   #possible values are "chrome" "firefox" "edge"
###### change marker
MARKER = "fa-star"   #   change marker with others such as 'fa-map-marker' , look at http://fontawesome.io/icons/ for available markers
MARKER_COLOR = "red"
#######
TILES = "CartoDB positron"
''' Possible TILES value
"OpenStreetMap"
"Mapbox Bright"
"Stamen Terrain"
"Stamen Toner"
"Stamen Watercolor"
"CartoDB positron"
'''

DEFAULT_CONNECTION = {"dbname": "exercise", "user": "user", "password": "user", "port":"5432", "host": "127.0.0.1"}


OGR_CONNECTION = "PG:host="+DEFAULT_CONNECTION["host"]+" dbname="+DEFAULT_CONNECTION["dbname"]\
                 +" user="+DEFAULT_CONNECTION["user"]+" password="+DEFAULT_CONNECTION["password"]
DEFAULT_SCHEMA = "exercise"
STATES = "states"
STATES_TABLE_NAME = DEFAULT_SCHEMA + "." + STATES
BOOKMARKS = "bookmarks"
BOOKMARKS_TABLE_NAME = DEFAULT_SCHEMA + "." + BOOKMARKS

SHAPE_MANDATORY_FILES = {"shp", "shx", "dbf"}
SHP2PGSQL =PGBIN + "/shp2pgsql.exe"
PGSQL = PGBIN + "/psql.exe"
PGUSER = "user"
PGPASSW = "user"



