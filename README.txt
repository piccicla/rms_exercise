Windows 64 bit installation instructions

1)Python and libraries

The program was developed and tested with python 3.5 64bit on Windows.

You can download Python 3.5.4 64bit from https://www.python.org/ftp/python/3.5.4/python-3.5.4-amd64.exe

Then you will need to install/update some python libraries, the links for the download are in "installation/requirements.txt"
A zip file with all the libraries can be downloaded from  https://www.dropbox.com/s/lomcu6o7xnnrzle/libraries.zip?dl=0

Libraries can be installed globally, however it is better to use a virtual environment to avoid problems

Many binaries depend on Visual C++ 2015, install it before installing python libraries
https://www.microsoft.com/en-us/download/details.aspx?id=53587


1.1) global installation
Put the downloaded libraries inside the "installation" folder and doubleclick librariesGLOBAL.bat to install/update them

1.2) use a virtual environment

create a folder anywhere, open a PowerShell window (or a Windows Command Line) and change the current directory to the new folder

> cd "path to new folder"

Initialize a virtual environment with

> py -3.5 -m venv myenv

This will create the "myenv" folder. Put all the libraries plus the file librariesVenv.bat from the "installation" folder inside  "myenv/Scripts", then
doubleclick librariesVIRTUAL.bat to install them 

copy and past the "program" folder into the "myenv" folder


2) PostgreSQL

2.1) Installation
The program was created and tested with PostgreSQL9.6.5/PostGIS 2.4.0 64 bits on Windows.

PostgreSQL9.6.5 installer can be found at https://www.enterprisedb.com/downloads/postgres-postgresql-downloads#windows

Run the installer, change the default settings if necessary, choose a password for the "postgres" user
At the end of the installation run the StackBuilder, select the local PostgreSQL9.6.5 installation, and select "SpatialExtensions>PostGIS 2.4.0 bundle", if necessary change the download directory, change the default installation settings if necessary, finally set the environment variables:
- GDAL_DATA choose "No" if you are not sure about your system settings, for example it might be already available from a previous installation of the Python GDAL package 
- POSTGIS_ENABLED_DRIVERS choose "Yes"
- POSTGIS_ENABLE_OUTDB_RASTERS choose "Yes"

2.2) Create a database

After installation open the psql shell to connet to the local database server to:
- create a new user and new database, 
- add the postgis extension to the new database
- add a new schema 
- create a table for the bookmarks

copy and run the commands below: 



CREATE USER "user" WITH PASSWORD 'user';
CREATE DATABASE "exercise" WITH OWNER="user" ENCODING='UTF8' TEMPLATE=template0;
\connect "exercise";
CREATE EXTENSION postgis;
CREATE SCHEMA exercise;
GRANT ALL PRIVILEGES ON SCHEMA exercise TO "user";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA exercise TO "user";
CREATE TABLE exercise.bookmarks (
	id  serial  primary key,
	lat real,
	lon real,
	label varchar(15),
	size smallint CHECK (size >= 1 AND size <= 5),  
	geom geometry(POINT,4326)
	);	
GRANT ALL PRIVILEGES ON TABLE exercise.bookmarks TO "user";
CREATE INDEX idx_bookmarks_geom ON exercise.bookmarks USING GIST(geom);
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA exercise TO "user";


3) Python code

In the file settings.py change PGBIN to your postgresql installation,the value "C:/Program Files/PostgreSQL/9.6/bin" 
should be already correct if PostgreSQL was installed with the default settings

Change BROWSER to 'firefox' or 'edge' if 'chrome' is not the favourite browser
Change MARKER to change the marker icon
Change TILES to use a different background
Change DEFAULT_CONNECTION if you're using an existing postgresql server

4) Starting the program
Open a PowerShell window (or a Windows Command Line) and change the current directory to "program" directory  

> cd  "directory path"

To run the program with a global installation

> py -3.5 main.py

To run the program within a virtual environment

> ../Scripts/Python main.py

NOTE: Start secondary.py to run a similar program that uses matplotlib instead of a web browser. 
 
5) Using the program
Follow the instructions on screen. The program will download a zipped shafile, unzip it, check the shapefile, check and change the coordinate system,
upload the shapefile to a new postgresql table, add geometry to the table. Running the program again will skip the download and will use the existing table.
The program will let the user download a screenshot of the webpage and insert points in WGS84 latitude/longitude format. Points outside USA will be discarded.
The size of the points will depend on the number of decimal digits, if latitude and longitude have a different number of digit the program will use the biggest number.
Users can type showall to show all the points stored in the database. Users can click on the point to show the label.

6) Deleting the virtual environment
Just delete the "myenv" folder
