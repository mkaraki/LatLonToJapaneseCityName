import math
import json
import pickle
import os

import geopandas as gpd
from shapely.geometry.multipolygon import MultiPolygon
from shapely.geometry import Polygon, Point, mapping


administrativeAreaCode = {}
prefs = []

for j in range(47):
    zero_id = str(j + 1).zfill(2)
    with open('administrativeAreaCode/api/v1/' + zero_id + '.json', 'r', encoding='utf-8') as f:
        obj = json.load(f)
        for i in obj:
            file_pref = obj[i]['prefecture']
            if (file_pref not in prefs):
                prefs.append(file_pref)
            if (len(i) == 5):
                if (j not in administrativeAreaCode):
                    administrativeAreaCode[j] = {}
                administrativeAreaCode[j][i] = obj[i]['city']


def _validateWithFloat(needle, original):
    if (type(needle) is float and type(original) is float and math.isnan(needle) and math.isnan(original)):
        return True
    else:
        return needle == original


def filterGeo(japanGeo, prefectureName=None, subPrefectureName=None, countryName=None, cityName=None, administrativeAreaCode=None):
    ret_polys = []

    for i in range(len(japanGeo['N03_001'])):
        if (
            (prefectureName == None or _validateWithFloat(prefectureName, japanGeo['N03_001'][i])) and
            (subPrefectureName == None or _validateWithFloat(subPrefectureName, japanGeo['N03_002'][i])) and
            (countryName == None or _validateWithFloat(countryName, japanGeo['N03_003'][i])) and
            (cityName == None or _validateWithFloat(cityName, japanGeo['N03_004'][i])) and
            (administrativeAreaCode == None or _validateWithFloat(
                administrativeAreaCode, japanGeo['N03_007'][i]))
        ):
            if (type(japanGeo['geometry'][i]) is MultiPolygon):
                return japanGeo['geometry'][i]
            elif (type(japanGeo['geometry'][i]) is Polygon):
                ret_polys.append(japanGeo['geometry'][i])

    if (len(ret_polys) > 0):
        return MultiPolygon(ret_polys)

    return None


mpolys = []
skip_mpolys = False
if (os.path.exists('prefectures.mpolys')):
    with open('prefectures.mpolys', 'rb') as f:
        mpolys = pickle.load(f)
        skip_mpolys = True
    if (len(mpolys) != 47):
        mpolys = []
        skip_mpolys = False


regionMpolys = {}
skip_regionMpolys = False
if (os.path.exists('all_region.mpolys')):
    with open('all_region.mpolys', 'rb') as f:
        regionMpolys = pickle.load(f)
        skip_regionMpolys = True


jpn_geo = None
if (not skip_mpolys and not skip_regionMpolys):
    print('Reading shapefile')
    jpn_geo = gpd.read_file('N03-22_220101.shp')


pref_lats = []
pref_lons = []
skip_preflatlon = False
if (os.path.exists('prefectures.latlon')):
    with open('prefectures.latlon', 'rb') as f:
        pf_latlon = pickle.load(f)
        pref_lats = pf_latlon[0]
        pref_lons = pf_latlon[1]
        skip_preflatlon = True


for prefidx, pref in enumerate(prefs):
    mpoly = None
    if (skip_mpolys):
        mpoly = mpolys[prefidx]
    else:
        print('Getting prefecture ' + pref)
        mpoly = filterGeo(jpn_geo, prefectureName=pref, subPrefectureName=math.nan,
                          countryName=math.nan, cityName=math.nan, administrativeAreaCode=math.nan)
        mpolys.append(mpoly)

    if (not skip_preflatlon):
        print('Analyzing prefecture ' + pref)
        min_lon = 180
        max_lon = -1
        min_lat = 180
        max_lat = -1

        for poly in mpoly.geoms:
            for points in mapping(poly)['coordinates']:
                for point in points:
                    lon = point[0]
                    lat = point[1]
                    if (lon > max_lon):
                        max_lon = lon
                    if (lon < min_lon):
                        min_lon = lon
                    if (lat > max_lat):
                        max_lat = lat
                    if (lat < min_lat):
                        min_lat = lat

        pref_lons.append([min_lon, max_lon])
        pref_lats.append([min_lat, max_lat])

    if (not skip_regionMpolys):
        print('Analyzing cities of ' + pref)
        regionMpolys[prefidx] = {}
        for areaCode in administrativeAreaCode[prefidx]:
            mpoly = filterGeo(jpn_geo, administrativeAreaCode=areaCode)
            if (mpoly == None):
                continue
            regionMpolys[prefidx][areaCode] = mpoly

        with open('region_' + str(prefidx) + '.mpolys', 'wb') as f:
            pickle.dump(regionMpolys[prefidx], f)


if (not skip_mpolys):
    with open('prefectures.mpolys', 'wb') as f:
        pickle.dump(mpolys, f)

if (not skip_regionMpolys):
    with open('all_region.mpolys', 'wb') as f:
        pickle.dump(regionMpolys, f)

if (not skip_preflatlon):
    with open('prefectures.latlon', 'wb') as f:
        pf_latlon = pickle.dump([pref_lats, pref_lons], f)


def isLatLonInMultiPolygon(mpoly, point):
    pnt = Point(point[1], point[0])
    for poly in mpoly.geoms:
        if (poly.contains(pnt)):
            return True
    return False


def searchPrefFromLatLon(mpolys, search_latlon):
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
    for prefCode in s_eligLonLatId:
        mpoly = mpolys[prefCode]
        isInRange = isLatLonInMultiPolygon(mpoly, search_latlon)
        if (isInRange):
            return prefCode

    return None


def searchCityFromLatLonAndPref(pref_code, search_latlon):
    for areaId, mpoly in regionMpolys[pref_code].items():
        if (mpoly == None):
            continue
        if (isLatLonInMultiPolygon(mpoly, search_latlon)):
            return areaId
    return None


search_latlon = [45.321208, 148.524874]

s_prefcode = searchPrefFromLatLon(mpolys, search_latlon)
if (s_prefcode == None):
    print('Not found')
    exit()
print(prefs[s_prefcode])

s_areacode = searchCityFromLatLonAndPref(s_prefcode, search_latlon)
if (s_areacode == None):
    print('Not found')
    exit()
print(administrativeAreaCode[s_prefcode][s_areacode])
