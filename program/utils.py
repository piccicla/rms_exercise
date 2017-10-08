# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
# Name:        utils.py
# Purpose:     utility functions
#
# Author:      claudio piccinini
#
# Updated:     07/10/2017
#-------------------------------------------------------------------------------

import psycopg2

def run_tool(params):
    """ run an executable tool (exe, bat,..)
    :param params: list of string parameters  ["tool path", "parameter1", "parameter2",.... ]
    :return: messages
    """
    import subprocess
    p = subprocess.Popen(params, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # A pipe is a section of shared memory that processes use for communication.
    out, err = p.communicate()
    return bytes.decode(out), bytes.decode(err)

def pgconnect(**kwargs):
    """ Connect to a postgresql database
    call as pgconnect(**kwargs) where kwargs  is something like
    {"dbname": "dbname", "user": "user", "password": "xxx", "port":"5432", "host": "127.0.0.1"}
    :param **kwargs :   a dictionary with connection
    :return: postgresql connection
    """
    connstring = ""
    for i in kwargs:connstring += str(i) +"="+ kwargs[i]+ " "
    #print(connstring)
    conn = psycopg2.connect(connstring)
    return conn


# function used to style a geojson layer
style_function = lambda x: {'fillColor': 'yellow', 'fillOpacity': 0.1, 'color': 'black', 'opacity':0.1}