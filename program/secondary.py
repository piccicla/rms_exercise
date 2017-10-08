# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
# Name:        secondary.py
# Purpose:     program to download a shapefile and make a simple webmap
#               connected to postgis, maps are rendered with matplotlib
#              NOTE: this was a wrong attempt to solve the exercise, most of the code has been recycled and moved to main.py,
#						duplicated code is intentional
#
# Author:      claudio piccinini
#
# Updated:     07/10/2017
#-------------------------------------------------------------------------------
import urllib.request
import urllib.error
import os
import shutil
import zipfile

import shapefile
from psycopg2.extensions import AsIs
from osgeo import ogr
from osgeo import osr
from shapely.wkb import loads
from numpy import asarray
from mpl_toolkits.basemap import Basemap
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import matplotlib.pyplot as plt

import settings
import utils


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


def plot_states():
    """
    Plot the states
    :return: plot and map objects
    """

    fig = plt.figure(num=None, figsize=(11.3, 7.00))
    ax = plt.axes([0, 0, 1, 1], facecolor=(0.4471, 0.6235, 0.8117))
    map = Basemap(projection='lcc', urcrnrlat=47.7, llcrnrlat=23.08, urcrnrlon=-62.5,
                  llcrnrlon=-120, lon_0=-98.7, lat_0=39, lat_1=33, lat_2=45,
                  resolution='l')
    map.fillcontinents(color='0.7', zorder=0)

    source = ogr.Open("PG:host="+settings.DEFAULT_CONNECTION["host"]+" dbname="+settings.DEFAULT_CONNECTION["dbname"] +
                      " user="+settings.DEFAULT_CONNECTION["user"]+" password="+settings.DEFAULT_CONNECTION["password"])
    data = source.ExecuteSQL("select geom from " + settings.STATES_TABLE_NAME)

    patches = []
    while True:
        feature = data.GetNextFeature()
        if not feature:
            break
        geom = loads(feature.GetGeometryRef().ExportToWkb())
        for polygon in geom:
            a = asarray(polygon.exterior)
            x, y = map(a[:, 0], a[:, 1])
            a = zip(x, y)
            p = Polygon(list(a), fc="y", ec='k', alpha=0.2, zorder=2, lw=.1)
            patches.append(p)

    ax.add_collection(PatchCollection(patches, match_original=True))

    return plt, map


def show_save_plot(plt, name="states.jpg", folder=None):
    """
    Show matplotlib plot on screen and save it to disk
    :param plt: matplotlib plot object
    :param name: name for the output image
    :param folder: output folder
    :return:
    """

    fig = plt.gcf()
    if not folder:
        folder = os.path.dirname(os.path.abspath(__file__))
    fig.savefig(folder + '/' + name, dpi=200)
    plt.show()


def add_point(plt, map, x, y, size, label, sizemult=2):

    x_, y_ = map(x, y)

    if label:
        plt.text(x_, y_, label, fontsize=8, fontweight='bold',
             ha='center', va='bottom', color='k')
    map.plot(x_, y_, "r*", markersize=size*sizemult)

    return plt


def add_all_points(plt,map, sizemult=3):
    """
    Add all the points to the map
    :param plt: a matplotlib plot object
    :param map: a matplotlib map object
    :param sizemult: multiplier to scale the marker size
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

            x_, y_ = map(rs[0], rs[1])

            if rs[2]:
                plt.text(x_, y_, rs[2], fontsize=8, fontweight='bold',
                     ha='center', va='bottom', color='k')
            map.plot(x_, y_, "r*", markersize=rs[3]*sizemult)

        return plt

    except Exception as e:
        raise Exception(e)

    finally:
        if cur: cur = None
        if conn: conn = None


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
                        (AsIs(settings.BOOKMARKS_TABLE_NAME), y, x, label, size))
            #id = cur.fetchone()[0]
            #print(id)
            cur.execute("""UPDATE %s SET geom = ST_PointFromText('POINT(' || lon || ' ' || lat || ')', 4326)""",(AsIs(settings.BOOKMARKS_TABLE_NAME),))
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


if __name__ == '__main__':

    import sys

    def exit(value):
        # Break if user types q
        if value == "q" or value=="Q":sys.exit()

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
            print("folder contains 1 shapefile of type polygon/multipolygon type called " + shapename)
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

        print('Press enter to plot to the states and download an image')

        value = input()
        exit(value)

        try:
            print("plotting... you will need to close the plot to continue")
            plot, map = plot_states()
            show_save_plot(plot)
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
                print("plotting... you will need to close the plot to continue")
                plot, map = plot_states()
                plot = add_point(plot, map, float(x), float(y), size, valuel)
                show_save_plot(plot, name="singlemarkers.jpg")
                print("image saved on disk")
            except Exception as e:
                print(e)

        while True: #inner while for showing all points
            try:
                # display_all_point
                print("plotting... you will need to close the plot to continue")
                plot, map = plot_states()
                plot = add_all_points(plot, map)
                show_save_plot(plot, name="allmarkers.jpg")
                print("image saved on disk")
            except Exception as e:
                print(e)
            finally:
                break