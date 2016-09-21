#!/usr/bin/python3
# -*- coding: utf-8 -*-
# sample queries
# http://localhost/wsgi/search.wsgi?searchtables=abwasser.such§tabelle&query=1100&cb=bla
# http://localhost/wsgi/search.wsgi?query=Oberlandstr&cb=bla
from __future__ import print_function
import re  # regular expression support
from webob import Request
from webob import Response
import psycopg2  # PostgreSQL DB Connection
import psycopg2.extras  # z.b. für named column indexes
import json
import sys
import os


# make themes choosable in search combo
THEMES_CHOOSABLE = True
# zoom to this bbox if a layer is chosen in the search combo [minx, miny, maxx, maxy]
# set to None if extent should not be changed
MAX_BBOX = None


# append the Python path with the wsgi-directory
qwcPath = os.path.dirname(__file__)
if qwcPath not in sys.path:
    sys.path.append(qwcPath)

import qwc_connect


def application(environ, start_response):
    request = Request(environ)
    searchtables = ['main.tsearch']  # enter your default searchtable(s) here
    searchtablesstring = ''
    if "searchtables" in request.params:
        searchtablesstring = request.params["searchtables"]
        if len(searchtablesstring) > 0:
            # sanitize
            if re.search(r"[^A-Za-z,._]", searchtablesstring):
                print(environ['wsgi.errors'])
                print("offending input: {s}".format(s=searchtablesstring))
                searchtables = []  # set empty to have no search table error returned
            else:
                searchtables.extend(searchtablesstring.split(','))

    querystring = request.params["query"]
    # strip away leading and trailing whitespaces
    querystring = querystring.strip()
    # split on whitespaces
    regex = re.compile(r'\s+')
    querystrings = regex.split(querystring)

    searchtableLength = len(searchtables)
    querystringsLength = len(querystrings)
    sql = ""
    errorText = ''

    # any searchtable given?
    if searchtableLength == 0:
        errorText += 'error: no search table'
        # write the error message to the error.log
        print(environ['wsgi.errors'])
        print(errorText)
        response_headers = [('Content-type', 'text/plain'),
                            ('Content-Length', str(len(errorText)))]
        start_response('500 INTERNAL SERVER ERROR', response_headers)

        return [errorText]

    data = ()
    # for each table
    for i in range(searchtableLength):
        sql += "SELECT label as displaytext, '" + searchtables[
            i] + r"' AS searchtable, layer_name as search_category, substring(layer_name from 1) AS searchcat_trimmed, 'mylayer' as showlayer, "
        # the following line is responsible for zooming in to the features
        # this is supposed to work in PostgreSQL since version 9.0
        sql += "'['||replace(regexp_replace(BOX2D(the_geom)::text,'BOX\(|\)','','g'),' ',',')||']'::text AS bbox "
        # if the above line does not work for you, deactivate it and uncomment the next line
        # sql += "'['||replace(regexp_replace(BOX2D(the_geom)::text,'BOX[(]|[)]','','g'),' ',',')||']'::text AS bbox "
        sql += "FROM " + searchtables[i] + " WHERE "
        # for each querystring
        for j in range(0, querystringsLength):
            # to implement a search method uncomment the sql and its following data line
            # for tsvector issues see the docs, use whichever version works best for you
            # this search does not use the field searchstring_tsvector at all but converts searchstring into a tsvector, its use is discouraged!
            # sql += "searchstring::tsvector @@ lower(%s)::tsquery"
            # data += (querystrings[j]+":*",)
            # this search uses the searchstring_tsvector field, which _must_ have been filled with to_tsvector('not_your_language', 'yourstring')
            sql += "ts @@ to_tsquery(\'french\', %s)"
            # data += (querystrings[j]+":*",)
            # if all tsvector stuff fails you can use this string comparison on the searchstring field
            # sql += "searchstring ILIKE %s"
            data += ("%" + querystrings[j] + "%",)

            if j < querystringsLength - 1:
                sql += " AND "
        # union for next table
        if i < searchtableLength - 1:
            sql += " UNION "

    sql += " ORDER BY search_category ASC, displaytext ASC;"

    conn = qwc_connect.getConnection(environ, start_response)

    if  conn is None:
        return [""]

    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        cur.execute(sql, data)
    except:
        exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
        conn.close()
        errorText += 'error: could not execute query'
        # write the error message to the error.log
        print(environ['wsgi.errors'])
        print("{error}: {exception}".format(error=errorText, exception= exceptionValue))
        response_headers = [('Content-type', 'text/plain'),
                            ('Content-Length', str(len(errorText)))]
        start_response('500 INTERNAL SERVER ERROR', response_headers)

        return [errorText]

    if THEMES_CHOOSABLE:
        selectable = "1"
        maxBbox = MAX_BBOX
    else:
        selectable = "0"
        maxBbox = None

    rowData = [];
    rows = cur.fetchall()
    lastSearchCategory = '';
    for row in rows:
        if lastSearchCategory != row['search_category']:
            rowData.append({"displaytext": row['searchcat_trimmed'], "searchtable": None, "bbox": maxBbox,
                            "showlayer": row['showlayer'], "selectable": selectable})
            lastSearchCategory = row['search_category']
        rowData.append({"displaytext": row['displaytext'], "searchtable": row['searchtable'], "bbox": row['bbox'],
                        "showlayer": row['showlayer'], "selectable": "1"})

    result_string = '{"results": ' + json.dumps(rowData) + '}'
    result_string = result_string.replace('"bbox": "[', '"bbox": [')
    result_string = result_string.replace(']"', ']')

    # we need to add the name of the callback function if the parameter was specified
    if "cb" in request.params:
        result_string = request.params["cb"] + '(' + result_string + ')'

    response = Response(result_string, "200 OK",
                        [("Content-type", "application/javascript"), ("Content-length", str(len(result_string)))])

    conn.close()

    return response(environ, start_response)
