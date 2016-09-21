#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Script to connect to a PostgreSQL database. Connection object to be used in all wasgi scripts
from __future__ import print_function
import psycopg2  # PostgreSQL DB Connection

# configure your DB connection here geomapfish-dev
DB_CONN_STRING = "host='5.196.168.201' dbname='lausanne_cimbach' port='5432' user='geosearch' password='geosearch'"


def getConnection(environ, start_response):
    # SQL database connection
    try:
        conn = psycopg2.connect(DB_CONN_STRING)
        return conn
    except:
        error_text = 'error: database connection failed!'
        # write the error message to the error.log
        print(environ['wsgi.errors'])
        print(errorText)
        response_headers = [('Content-type', 'text/plain'),
                            ('Content-Length', str(len(errorText)))]
        start_response('500 INTERNAL SERVER ERROR', response_headers)

        return None
