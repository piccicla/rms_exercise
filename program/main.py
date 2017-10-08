# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
# Name:        main.py
# Purpose:     main program to download a shapefile and make a simple webmap
#               connected to postgis
#
# Author:      claudio piccinini
#
# Updated:     08/10/2017
#-------------------------------------------------------------------------------
import urllib.request
import urllib.error
import os
import shutil
import zipfile
import io
import sys
import copy

import shapefile
from psycopg2.extensions import AsIs

from osgeo import ogr
from osgeo import osr

import folium
from folium.features import DivIcon
from selenium import webdriver
from PIL import Image

import utils
import settings


# global variable to store the states geojson
GEOJSON = None


def download_zip(url, folder=None):
    """
    This function will download a zip file to disk
    :param url:
    :param folder: a folder to save the file, if None will download to this script folder
    :return: a tuple with path to folder and the filename
    """

    # get this file folder name and save the file name
    if not folder:
        folder = os.path.dirname(os.path.abspath(__file__))
    file_name = os.path.split(url)[1]

    # Download the file from "url" and save it locally under "file_name":
    try:
        with urllib.request.urlopen(url) as response, open(folder + "/" + file_name, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    except urllib.error.URLError as e:
        print('urllib.error.URLError')
        raise Exception(e)
    except Exception as e:
        raise Exception(e)
    else:
        return folder,file_name


def unzip(folder, file_name):
    """
    Unzip a .zip
    :param folder: the path to the folder with the zip file
    :param file_name: the zip file name
    :return: the folder name of the folder with the extracted files
    """

    base = os.path.splitext(file_name)[0] #get file name with no extension
    if not os.path.exists(folder + "/" + base):  #create a new directory if not existing
       os.mkdir(folder + "/" + base)

    z = None
    zipShape = None
    try:
       z = open(folder + "/" + file_name,"rb")
       zipShape = zipfile.ZipFile(z)

       #print (zipShape.namelist()) #list the zip content
       for fileName in zipShape.namelist():  #unzip files
            out = open(folder + "/" + base+'/'+fileName, "wb")
            out.write(zipShape.read(fileName))
            out.close()

    except Exception as e:
        raise Exception(e)
    else:
        return base
    finally:
       if zipShape: zipShape.close()
       if z: z.close()


def check_shapefile(folder):
    """
    Check the folder contains the three mandatory files with extension  .shp, .dbf,.dbf
    Also check there is only 1 shapefile and this is a polygon type
    :param folder: path to the folder with the shapefile to check
    :return: the name of the shapefile
    """

    '''
    Value | Shape Type
    0  | Null Shape
    1  | Point
    3  | PolyLine
    5  | Polygon
    8  | MultiPoint
    11 | PointZ
    13 | PolyLineZ
    15 | PolygonZ
    18 | MultiPointZ
    21 | PointM
    23 | PolyLineM
    25 | PolygonM
    28 | MultiPointM
    31 | MultiPatch
    '''

    try:
        files = os.listdir(folder)
        sfiles = {i.split('.')[-1] for i in files}
        if not sfiles >= settings.SHAPE_MANDATORY_FILES:
            raise Exception("A shapefile should contain " + str(settings.SHAPE_MANDATORY_FILES))

        # check if there is only one shapefile
        file = [i.split(".")[0] for i in files if i.endswith("shp")]
        if len(file) > 1:
            raise Exception("zip file should contain only 1 shapefile ")

        # check this is a polygon shapefile
        sf = shapefile.Reader(folder + "/" + file[0])
        shapes = sf.shapes()
        if shapes[0].shapeType not in [5, 15, 25]:  # check polygon shapetypes
            raise Exception("shapefile should be polygon")

        return file[0]+".shp"
    except Exception as e:
        raise Exception(e)


def check_table(schemaname=settings.DEFAULT_SCHEMA, tablename=settings.STATES):
    """
    Check if the table exercise.states is already in the database
    :param schemaname:
    :param tablename:
    :return: True if table exists otherwise False
    """

    conn = None
    cur = None

    try:

        conn = utils.pgconnect(**settings.DEFAULT_CONNECTION)
        cur = conn.cursor()
        cur.execute("""SELECT to_regclass('%s.%s');""", (AsIs(schemaname), AsIs(tablename)))
        result = cur.fetchone()[0]

        return (True if result else False)

    except Exception as e:
        raise Exception(e)

    finally:
        if conn: conn = None
        if cur: cur = None


def upload_shape(shapepath):
    """
    Upload file to database
    :param shapepath: path to the shapefile
    :return: None
    """

    conn = None
    cur = None

    try:
        # first create the sqlstring with inserts
        # call PGSQL2SHP with some parameters, -s 4326 to set lat/lon srid, -I to create a spatial index on the geometry column
        params = [settings.SHP2PGSQL, "-s", "4326", "-I", shapepath, settings.STATES_TABLE_NAME]
        sqlstring,info = utils.run_tool(params)
        if not sqlstring:
            raise Exception("cannot upload file to database")

        #then use the sqlstring
        conn = utils.pgconnect(**settings.DEFAULT_CONNECTION)
        cur = conn.cursor()
        cur.execute(sqlstring)
        conn.commit()

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def upload_point(x, y, label=""):
    """
    Check the user input for a point, if inside USA, if OK add it to the database
    Crop nummber to 4 digits, define the marker size based  on the bigger number of digits
    :param x: point longitude (wgs84) as string
    :param y: point latitude (wgs84) as string
    :param label: point label
    :return: ("longitude","latitude", size) ; coordinates are cropped to 4 decimal digits, size will be the bookmark size
    """

    conn = None
    cur = None

    try:
        # check the point is inside the usa, both point and states must be WGS84
        conn = utils.pgconnect(**settings.DEFAULT_CONNECTION)
        cur = conn.cursor()
        #if the point is inside this will return (True,) otherwise None
        cur.execute("""select result from
                        (select st_contains(s.geom,ST_GeomFromText('POINT(%s %s)', 4326)) as result 
                          from %s as s) as subquery
                          where result is true""",(AsIs(x),AsIs(y), AsIs(settings.STATES_TABLE_NAME)))

        result = cur.fetchone()
        #print(result)

        if result: # if result is not None

            #check numbers size, crop to 4 digits, define the marker size

            # size symbol
            size=None

            # store number of decimal digits
            lx = 0
            ly = 0

            # convert numbers to string
            #x = str(x);y = str(y)

            if ',' in x or ',' in y:
                raise Exception("decimal numbers should not contain ','")

            # check the number of decimal digits and crop to 4
            if '.' in x:  # do only for float number
                lx = len(x.split('.')[1])  # get decimals
                if lx > 4:  # crop size to 4
                    x = x[:(4 - lx)]
                    lx = 4
            if '.' in y:  # do only for float number
                ly = len(y.split('.')[1])
                if ly > 4:
                    y = y[:(4 - ly)]
                    ly = 4

            # select a symbol size according
            # for the size take the bigger number of digits of the two numbers
            ndigits = max([lx, ly])
            if ndigits == 0:
                size = 5
            elif ndigits == 1:
                size = 4
            elif ndigits == 2:
                size = 3
            elif ndigits == 3:
                size = 2
            elif ndigits == 4:
                size = 1

            #upload to database
            cur.execute(
                    """INSERT INTO %s(lat,lon,label,size) VALUES (%s,%s,%s,%s) RETURNING id""",
                        ( AsIs(settings.BOOKMARKS_TABLE_NAME),  y, x, label, size))
            #id = cur.fetchone()[0]
            #print(id)
            cur.execute("""UPDATE %s SET geom = ST_PointFromText('POINT(' || lon || ' ' || lat || ')', 4326)""", (AsIs(settings.BOOKMARKS_TABLE_NAME),))
            conn.commit()

        else:
            raise Exception("the point is not inside USA")

    except Exception as e:
        raise Exception(e)

    else:
        return x, y, size #return the cropped coordinates and marker size

    finally:
        if cur: cur = None
        if conn: conn = None


def get_epsg(path):
    """
    Return the epsg code for a shapefile
    :param path: the path to the shp file
    :return:
    """
    dataset = None
    layer = None
    srs = None
    try:

        driver = ogr.GetDriverByName('ESRI Shapefile')
        dataset = driver.Open(path, 0)  # 0 means read-only
        layer = dataset.GetLayer()
        srs = layer.GetSpatialRef()
        #Set EPSG authority info if possible.
        srs.AutoIdentifyEPSG()
        return srs.GetAuthorityCode(None)

    finally:
        if srs: srs = None
        if layer: layer = None
        if dataset: dataset = None


def reproject_vector( path, epsg_from=None, epsg_to=None):
    """ reproject a vector file (only the first layer!) (it does not save the dataset to disk)
    :param path: the path to the input vectorfile
    :param epsg_from: the input spatial reference; in None take the source reference
    :param epsg_to: the output spatial reference
    :return: the reprojected dataset
    """

    if not epsg_to: raise Exception("please, specify the output EPSG codes")

    inDataSet = None
    outDataSet = None
    inFeature = None
    outFeature = None
    outLayer = None

    try:

        driver = ogr.GetDriverByName('ESRI Shapefile')
        inDataSet = driver.Open(path, 0)  # 0 means read-only

        # define input SpatialReference
        if not epsg_from:
            layer = inDataSet.GetLayer()
            inSpatialRef = layer.GetSpatialRef()
        else:
            inSpatialRef = osr.SpatialReference()
            inSpatialRef.ImportFromEPSG(epsg_from)

        # define output SpatialReference
        outSpatialRef = osr.SpatialReference()
        outSpatialRef.ImportFromEPSG(epsg_to)

        # create the CoordinateTransformation
        coordTrans = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)

        # get the first input layer and the geometry type
        inLayer = inDataSet.GetLayer()
        geotype = inLayer.GetGeomType()
        lname = inLayer.GetName()

        drv = ogr.GetDriverByName("ESRI Shapefile")
        outDataSet = drv.CreateDataSource("/vsimem/memory.shp")

        outLayer = outDataSet.CreateLayer(lname, srs=outSpatialRef, geom_type=geotype)

        # add fields
        inLayerDefn = inLayer.GetLayerDefn()

        for i in range(0, inLayerDefn.GetFieldCount()):
            fieldDefn = inLayerDefn.GetFieldDefn(i)
            outLayer.CreateField(fieldDefn)

        # get the output layer"s feature definition
        outLayerDefn = outLayer.GetLayerDefn()

        counter = 1

        # loop through the input features
        inFeature = inLayer.GetNextFeature()
        while inFeature:
            # get the input geometry
            geom = inFeature.GetGeometryRef()
            # reproject the geometry
            geom.Transform(coordTrans)
            # create a new feature
            outFeature = ogr.Feature(outLayerDefn)
            # set the geometry and attribute
            outFeature.SetGeometry(geom)
            for i in range(0, outLayerDefn.GetFieldCount()):
                outFeature.SetField(outLayerDefn.GetFieldDefn(i).GetNameRef(), inFeature.GetField(i))
            # add the feature to the shapefile
            outLayer.CreateFeature(outFeature)

            # destroy the features and get the next input feature
            if outFeature: outFeature = None
            inFeature = inLayer.GetNextFeature()

            counter += 1
            #print(counter)

        return outDataSet

    except RuntimeError as err:
        raise err
    except Exception as e:
        raise e

    finally:
        if inDataSet: outDataSet == None  # give back control to C++
        if outDataSet: outDataSet == None
        if outLayer: outLayer == None
        if inFeature: inFeature == None
        if outFeature: outFeature = None


def save_vector(dataset, outpath, driver=None):
    """ save an ogr dataset to disk, (it will delete preexisting output)
    :param dataset: ogr dataset
    :param outpath: output path
    :param driver: override with a driver name, otherwise the driver will be inferred from the dataset
    :return: None
    """
    try:
        if not driver:
            driver = dataset.GetDriver()
            if os.path.exists(outpath):
                driver.DeleteDataSource(outpath)
            dst_ds = driver.CopyDataSource(dataset, outpath)
        else:
            driver = ogr.GetDriverByName(driver)
            if os.path.exists(outpath):
                driver.DeleteDataSource(outpath)
            dst_ds = driver.CopyDataSource(dataset, outpath)


    except RuntimeError as err:
        raise err
    except Exception as e:
        raise e

    finally:
        dst_ds = None  # Flush the dataset to disk


def simple_map(location = [48, -102] , zoom=3, tiles=settings.TILES):
    """
    Initialize a map
    :param location:
    :param zoom:
    :param tiles:
    :return: the map object
    """
    map = folium.Map(
        location=location,
        zoom_start=zoom,
        tiles=tiles
    )
    return map


def get_class_size(size):
    """
    Return html class fragment for the marker size
    :param size: number between 1 and 5
    :return: string
    """

    s = 'fa-lg'
    if size == 1:
        s = 'fa-lg'
    elif size == 2:
        s = 'fa-2x'
    elif size == 3:
        s = 'fa-3x'
    elif size == 4:
        s = 'fa-4x'
    elif size == 5:
        s = 'fa-5x'
    return s


def add_point(map, x, y, size, label, marker=settings.MARKER, color=settings.MARKER_COLOR):
    """
    Add one point to the map
    :param map: a folim map object
    :param x: longitude WGS84
    :param y: latitude WGS84
    :param size: marker size
    :param label:  marker label
    :param marker: a font-awesome marker
    :return: None
    """

    s = get_class_size(size)

    folium.map.Marker(
        location=[y, x],
        popup=label,

        icon=DivIcon(
            #icon_size=(150,36),
            icon_anchor=(0,0),
            html='<i class="fa '+marker+' '+s+'" style="color:'+color+'" aria-hidden="true"></i>',
            )
    ).add_to(map)


def add_all_points(map, marker=settings.MARKER,color=settings.MARKER_COLOR):
    """
    Add all the points to the map
    :param map: a matplotlib map object
    :param marker: a font-awesome marker
    :return:
    """

    conn = None
    curr = None

    try:
        conn = utils.pgconnect(**settings.DEFAULT_CONNECTION)
        cur = conn.cursor()
        # if the point is inside this will return (True,) otherwise None
        cur.execute("""select lon, lat, label,size from %s""", (AsIs(settings.BOOKMARKS_TABLE_NAME),))

        result = cur.fetchall()

        #iterate and add point
        for rs in result:

            s = get_class_size(rs[3])

            folium.map.Marker(
                location=[rs[1],rs[0]],
                popup=rs[2],

                icon=DivIcon(
                    # icon_size=(150,36),
                    icon_anchor=(0, 0),
                    html='<i class="fa '+marker+' ' + s + '" style="color:'+color+'" aria-hidden="true"></i>'
                )
            ).add_to(map)

    except Exception as e:
        raise Exception(e)

    finally:
        if cur: cur = None
        if conn: conn = None


def save_map(map, name="index.html", folder=None):
    """
    Save the html page
    :param map: a map object
    :param name: name fot the html page
    :param folder: folder to save to, if None save to current program folder
    :return: the path to the page
    """

    if not folder:
        folder = os.path.dirname(os.path.abspath(__file__))


    map.save(folder + "/" + name)

    return folder + "/" + name


def get_geojson():
    """
    Download geojson from the database
    :return: None
    """

    # check the file was already downloaded
    global GEOJSON
    if GEOJSON: return GEOJSON

    conn = None
    cur = None
    try:

        conn = utils.pgconnect(**settings.DEFAULT_CONNECTION)
        cur = conn.cursor()
        cur.execute(    """SELECT row_to_json(fc) FROM 
                          ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
                          FROM (SELECT 'Feature' As type , ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json(lp) As properties
                           FROM exercise.states As lg  INNER JOIN (SELECT gid,name FROM exercise.states) As lp
                               ON lg.gid = lp.gid ) As f)  As fc;""", (AsIs(settings.STATES_TABLE_NAME)))
        result = cur.fetchone()[0]

        #print(result)

        #make the result global
        GEOJSON = result

    except Exception as e:
        raise Exception(e)

    finally:
        if conn: conn = None
        if cur: cur = None


def add_geojson(map, geojson, style_function, name='states' ):
    """
    Add a geojson layer to the map
    :param map: a map object
    :param geojson:
    :param style_function: a style function used to style the layer
    :param name:
    :return:
    """

    folium.GeoJson(
        geojson,
        name=name,
        style_function=style_function
    ).add_to(map)


def browser(path, driver='chrome'):
    """
    Open a web page with a browser
    :param path: the path to the html file
    :param driver: the driver name
    :return: webdriver object
    """

    if driver=='chrome':
        driver = webdriver.Chrome()
    elif driver=='firefox':
        driver = webdriver.Firefox()
    elif driver=='edge':
        driver = webdriver.Edge()
    else:
        raise Exception("driver "+driver+ " is not supported")

    driver.get("file:///"+ path)
    return driver


def save_image(driver, outname="states.jpeg", folder=None):
    """
    Save screenshot at 200dpi in jpeg format
    :param driver: the selenium driver
    :param folder: folder to save the image to , if None save to the program folder
    :return:
    """

    # set the output folder
    if not folder:
        folder = os.path.dirname(os.path.abspath(__file__))

    # get thescreenshot
    binary = driver.get_screenshot_as_png()
    stream = io.BytesIO(binary)

    # save screenshot in jpeg format
    img = Image.open(stream)
    img = img.convert(mode="RGB")
    img.save(folder + '/' + outname, format='JPEG', dpi=(200,200))


if __name__ == '__main__':

    driver=None

    def exit(value):
        # Break if user types q
        if value == "q" or value=="Q":
            if driver:driver.quit()
            sys.exit()

    def refreshmap():
        map = simple_map()
        get_geojson()
        add_geojson(map, GEOJSON, utils.style_function)
        return map

    print("Welcome. To quit the program type q")
    print("This program will use the folder " + os.path.dirname(os.path.abspath(__file__)) +" to download data and images")
    exists = check_table()
    if exists: print("The table 'exercise.states' already exists and will be used. Drop it if a new table is required")

    while True:
        if exists:break #if the table states already exists skip download
        print("First I will download a zip file from 'http://www2.census.gov/geo/tiger/GENZ2016/shp/cb_2016_us_state_20m.zip'")
        print('Press enter to begin download')

        value = input()
        exit(value) # if 'q' exit program

        try:
            print("Downloading...")
            folder, file_name = download_zip("http://www2.census.gov/geo/tiger/GENZ2016/shp/cb_2016_us_state_20m.zip")
            print("Download succeeded")
            break
        except Exception as e:
            print(e)

    while True:
        if exists: break # if the table states already exists skip unzip
        print('Press enter to unzip the file')

        value = input()
        exit(value)

        try:
            print("Unzipping...")
            base = unzip(folder, file_name)
            print("Unzipping succeeded")
            print("Checking the folder content")
            shapename = check_shapefile(folder + "/" + base + '/')
            print("folder contains 1 shapefile of type polygon/multipolygon called " + shapename)
            print(".shp,.dbf, .shx mandatory files are there")
            break
        except Exception as e:
            print(e)

    while True:
        if exists: break #if the table states already exists skip uploading
        print('Press enter to upload shapefile to the database')

        value = input()
        exit(value)

        try:
            print("The database will store geometry in WGS84 lat/lon")
            print("Checking coordinate system...")
            epsg = get_epsg(folder + "/" + base + '/' + shapename)
            if epsg != "4326":
                print("Coordinate system is epgs:" + epsg)
                print("Coordinate system will be converted to epgs:4326")
                print("reprojecting....")
                dataset = reproject_vector(folder + "/" + base + '/' + shapename, epsg_from=int(epsg), epsg_to=4326)
                print("overwrite shapefile...")
                save_vector(dataset, folder + "/" + base + '/' + shapename, driver=None)
                dataset = None

            print("uploading states")
            upload_shape(folder + "/" + base + '/' + shapename)
            print("Upload succeeded")
            break
        except Exception as e:
            print(e)


    while True:

        print('Press enter to plot the states')

        value = input()
        exit(value)


        try:
            print("plotting...")

            # initialize map
            map=refreshmap()

            path = save_map(map)
            driver = browser(path, settings.BROWSER)

            print("Press enter to take a screenshot")
            value = input()
            exit(value)
            save_image(driver)
            print("image saved on disk")
            break

        except Exception as e:
            print(e)

    print("Insert a bookmark, use showall to view all bookmarks")
    while True:
        while True:  # inner while fot inserting/showing single point
            print("---insert showall to view all bookmarks---")
            print("Insert WGS84 longitude(x) and press enter, for USA this value should be negative")

            valuex = input()
            exit(valuex)
            if valuex.lower() == "showall": break

            print("Insert WGS84 latitude(y) and press enter")
            valuey = input()
            exit(valuey)
            if valuey.lower() == "showall": break

            try:
                float(valuex)
                float(valuey)
            except:
                print("coordinates should be integer or float")
                continue

            print("Insert a text label")
            valuel = input()
            exit(valuel)
            if valuel.lower() == "showall": break

            try:
                #check point, fix it, and upload to database
                x,y,size = upload_point(valuex,valuey, valuel)
                print("long(x)= " + x + " lat(y)=" + y + " label= " + valuel + " size= " + str(size))
                #print(x,y,size)

                print("plotting...")
                map = refreshmap()
                add_point(map, float(x), float(y), size, valuel)
                path = save_map(map)
                driver.refresh()

                print("Press enter to take a screenshot")
                value = input()
                exit(value)
                save_image(driver,  valuel+".jpeg")
                print("image "+valuel+".jpeg saved on disk")

            except Exception as e:
                print(e)

        while True: #inner while for showing all points
            try:
                # display_all_point
                print("plotting... ")
                map = refreshmap()
                add_all_points(map)
                path = save_map(map)
                driver.refresh()

                print("Press enter to take a screenshot")
                value = input()
                exit(value)
                save_image(driver, "allpoints.jpeg")
                print("image allpoints.jpeg saved on disk")
                break

            except Exception as e:
                print(e)














