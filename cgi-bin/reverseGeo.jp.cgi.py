#!/usr/bin/python
# -*- coding: utf-8 -*-
import math
import cgi
import json
import pickle
import os

from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry import Polygon, Point, mapping

form = cgi.FieldStorage()

if (not os.path.exists('prefectures.mpolys') or
    not os.path.exists('prefectures.latlon')):
    print('HTTP/1.1 500 Internal Server Error')
    print('Content-type: application/json; charset=utf-8')
    print()
    print('{"error":"server error"}')
    exit(1)


def getSearchLatLonAry(lat, lon):
    try:
        lat = float(lat)
        lon = float(lon)

        if (lon < -180 or lon > 180 or lat < -90 or lat > 90):
            print('HTTP/1.1 400 Bad Request')
            print('Content-type: application/json; charset=utf-8')
            print()
            print('{"error":"invalid range"}')
            exit()

        return [lat, lon]

    except TypeError:
        print('HTTP/1.1 400 Bad Request')
        print('Content-type: application/json; charset=utf-8')
        print()
        print('{"error":"bad request"}')
        exit()
        return None

    except ValueError:
        print('HTTP/1.1 400 Bad Request')
        print('Content-type: application/json; charset=utf-8')
        print()
        print('{"error":"invalid number"}')
        exit()
        return None


search_latlon = getSearchLatLonAry(form.getfirst('lat'), form.getfirst('lon'))

def returnUnknown():
    print("Content-Type: application/json; charset=utf-8")
    print()
    print('{"location":"Unknown"}')
    exit()


# Is in Japan? (relax detection)
# See: https://www.gsi.go.jp/KOKUJYOHO/center.htm
if (search_latlon[0] < 20 or search_latlon[0] > 46 or search_latlon[1] < 122 or search_latlon[1] > 154):
    returnUnknown()


pref_lats = []
pref_lons = []


with open('prefectures.latlon', 'rb') as f:
    pf_latlon = pickle.load(f)
    pref_lats = pf_latlon[0]
    pref_lons = pf_latlon[1]


# Check if the search lat/lon is in any prefectures (relax detection)
def searchLonLatEligPrefs(search_latlon):
    s_eligLatId = []
    for i, v in enumerate(pref_lats):
        if (search_latlon[0] > v[0] and search_latlon[0] < v[1]):
            s_eligLatId.append(i)

    s_eligLonId = []
    for i, v in enumerate(pref_lons):
        if (search_latlon[1] > v[0] and search_latlon[1] < v[1]):
            s_eligLonId.append(i)

    s_eligLonLatId = list(
        set(s_eligLonId) - set(set(s_eligLonId) - set(s_eligLatId)))

    return s_eligLonLatId

s_eligLonLatId = searchLonLatEligPrefs(search_latlon)

# If not match in any prefectures
if (len(s_eligLonLatId) == 0):
    returnUnknown()


# Load strict prefecture shape data
# Search from prefecture data (strict)
def isLatLonInMultiPolygon(mpoly, point):
    pnt = Point(point[1], point[0])
    for poly in mpoly.geoms:
        if (poly.contains(pnt)):
            return True
    return False

def searchPrefFromLatLon(mpolys, s_eligLonLatId, search_latlon):
    for prefCode in s_eligLonLatId:
        mpoly = mpolys[prefCode]
        isInRange = isLatLonInMultiPolygon(mpoly, search_latlon)
        print(prefCode, isInRange)
        if (isInRange):
            return prefCode

    return None

## If match in multiple prefectures, search from strict prefecture data
if (len(s_eligLonLatId) == 1):
    s_prefcode = s_eligLonLatId[0]
else:
    mpolys = []
    with open('prefectures.mpolys', 'rb') as f:
        mpolys = pickle.load(f)
    if (len(mpolys) != 47):
        print('HTTP/1.1 500 Internal Server Error')
        print('Content-type: application/json; charset=utf-8')
        print()
        print('{"error":"server error"}')
        exit()

    s_prefcode = searchPrefFromLatLon(mpolys, s_eligLonLatId, search_latlon)
    if (s_prefcode == None):
        returnUnknown()


# Load city level shape data
regionMpolys = {}
if (not os.path.exists('region_' + str(s_prefcode) + '.mpolys')):
    print('HTTP/1.1 500 Internal Server Error')
    print('Content-type: application/json; charset=utf-8')
    print()
    print('{"error":"server error"}')
    exit()

with open('region_' + str(s_prefcode) + '.mpolys', 'rb') as f:
    regionMpolys[s_prefcode] = pickle.load(f)


# Search from city data (strict)
def searchCityFromLatLonAndPref(pref_code, search_latlon):
    for areaId, mpoly in regionMpolys[pref_code].items():
        if (mpoly == None):
            continue
        if (isLatLonInMultiPolygon(mpoly, search_latlon)):
            return areaId
    return None

s_areacode = searchCityFromLatLonAndPref(s_prefcode, search_latlon)


# Prepare response
revGeoObj = {
    'attribution': '「国土数値情報（行政区域データ）」(国土交通省) (https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-v3_1.html)を加工して作成',
    'location': 'Unknown',
}


administrativeAreaCode = {}
prefs = [None] * 47

prefzero_id = str(s_prefcode + 1).zfill(2)
with open('administrativeAreaCode/api/v1/' + prefzero_id + '.json', 'r', encoding='utf-8') as f:
    obj = json.load(f)
    for i in obj:
        file_pref = obj[i]['prefecture']
        if (file_pref not in prefs):
            prefs[s_prefcode] = file_pref
        if (len(i) == 5):
            if (s_prefcode not in administrativeAreaCode):
                administrativeAreaCode[s_prefcode] = {}
            administrativeAreaCode[s_prefcode][i] = obj[i]['city']

revGeoObj['location'] = prefs[s_prefcode]
if (s_areacode != None and s_areacode != ''):
    revGeoObj['location'] += administrativeAreaCode[s_prefcode][s_areacode]

print("Content-Type: application/json; charset=utf-8")
print()
print(json.dumps(revGeoObj))
