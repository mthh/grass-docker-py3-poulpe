#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
@author: mthh
"""
import os
import sys
import subprocess
import binascii
import tempfile
import uuid
import json
import rasterio as rio
import shlex
from rasterio.features import shapes as rio_shapes
#import select
from flask import Flask, g
from pyproj import Proj, transform
from functools import partial
from werkzeug.local import LocalProxy
from flask import request, send_from_directory

app = Flask(__name__)



# def get_grass():
#     if 'grass_path_info' not in g:
#         g.grass, g.grass_path_info, g.reproj = init_grass()
#     return (g.grass, g.grass_path_info, g.reproj)

STRING_LENGTH = 12
EPSG_VALUE = 2154

def init_grass():
    grass_bin = 'grass'
    startcmd = grass_bin + ' --config path'
    p = subprocess.Popen(
        startcmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        )
    out, err = p.communicate()
    if p.returncode != 0:
        print('Error occured !')
        print('Out: ', out)
        print('Error: ', err)

    gisbase = out.strip(b'\n').decode()
    os.environ['GISBASE'] = gisbase
    gpydir = os.path.join(gisbase, 'etc', 'python')
    sys.path.append(gpydir)
    gisdb= os.path.join(tempfile.gettempdir(), 'grassdata')
    try:
        os.stat(gisdb)
    except:
        os.mkdir(gisdb)

    location = binascii.hexlify(os.urandom(12)).decode()
    mapset = 'PERMANENT'
    location_path = os.path.join(gisdb, location)

    startcmd = ' '.join([
        grass_bin,
        '-c epsg:{}'.format(EPSG_VALUE),
        '-e',
        location_path,
        ])

    print('Starting grass with command: `' + startcmd + '`')
    p = subprocess.Popen(
        startcmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        )

    out, err = p.communicate()
    if p.returncode != 0:
        print('Error occured !')
        print('Out: ', out)
        print('Error: ', err)
        return

    if out:
        print('Out: ', out)
    print('Created location ', location_path)

    import grass.script as grass
    import grass.script.setup as gsetup

    gsetup.init(gisbase, gisdb, location, mapset)
    grass.message('--- GRASS GIS 7: Current GRASS GIS 7 environment:')
    print(grass.gisenv())

#    grass.message('--- GRASS GIS 7: Checking projection info:')
#    in_proj = grass.read_command('g.proj', flags = 'jf')
#    print(in_proj)

    grass.message('--- GRASS GIS 7: Setting projection info using proj4 string:')
    _out_proj = grass.read_command('g.proj', flags='c', proj4="+proj=lcc +lat_1=49 +lat_2=44 +lat_0=46.5 +lon_0=3 +x_0=700000 +y_0=6600000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs")
    print(_out_proj)

    grass.message('--- GRASS GIS 7: Loading DEM file:')
    res = grass.read_command(
        'r.external',
        flags='o',
        input="grenoble_est_eudem_2154.tif",
        band=1,
        output="rast_5cb08c8150bbc7",
        )
    print(res)

    grass.message('--- GRASS GIS 7: Defining the region:')
    res = grass.read_command(
        'g.region',
        n="6551114.0",
        s="6392480.0",
        e="984410.0",
        w="871682.0",
        res="24.96217255547944802")
    print(res)
    in_proj = Proj("+proj=lcc +lat_1=49 +lat_2=44 +lat_0=46.5 +lon_0=3 +x_0=700000 +y_0=6600000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs")
    out_proj = Proj(init='epsg:4326')

    return (
        grass,
        partial(transform, out_proj, in_proj),
        {
            "gisbase": gisbase,
            "gisdb": gisdb,
            "location": location,
            "mapset": mapset,
        },
    )

def _validate_coordinates(coords):
    _coords = list(map(lambda x: float(x), coords.split(',')))
    print(_coords)
    _coords = TO_L93(_coords[1], _coords[0])
    if _coords[1] >= 6551114.0 or _coords[1] <= 6392480.0 \
            or _coords[0] >= 984410.0 or _coords[0] <= 871682.0:
        raise ValueError(
            'Requested point {} is outside the allowed region '
            '(xmin=6392480, xmax=6551114, ymin=871682, ymax=984410)'
            .format(_coords))
    return '{},{}'.format(*_coords)

def _validate_number(h):
    float(h)
    return h

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/viewshed')
def interviz_wrapper():
    params = {}
    try:
        params['coordinates'] = _validate_coordinates(request.args['coordinates'])
        params['height1'] = _validate_number(request.args['height1'])
        params['height2'] = _validate_number(request.args['height2'])
        params['max_distance'] = _validate_number(request.args.get('max_distance', '25000'))
    except Exception as e:
        return app.response_class(
            response=json.dumps({"message": "Error : {}".format(e)}),
            mimetype='application/json',
            )

    return app.response_class(
        response=interviz(**params),
        mimetype='application/json',
        )

def interviz(coordinates, height1, height2, max_distance="-1"):
    try:
        uid = str(uuid.uuid4()).replace('-', '')
        grass_name = "output_{}".format(uid)
        output_name = os.path.join(PATH_INFO['gisdb'], '.'.join([uid, 'tif']))
        GRASS.message('--- GRASS GIS 7: Computing viewshed:')
        res = GRASS.read_command(
            'r.viewshed',
            input='rast_5cb08c8150bbc7',
            coordinates=coordinates,
            observer_elevation=height1,
            target_elevation=height2,
            max_distance=max_distance,
            refraction_coeff="0.14286",
            memory="1000",
            flags='b',
            output=grass_name,
            )
        print(res)

        GRASS.message('--- GRASS GIS 7: Saving resulting raster layer:')
        res = GRASS.read_command(
            'r.out.gdal',
            input=grass_name,
            output=output_name,
            format="GTiff",
            createopt="TFW=YES,COMPRESS=LZW")
        print(res)

        GRASS.message('--- GRASS GIS 7: Remove result raster from GRASS:')
        res = GRASS.read_command(
            'g.remove',
            flags='f',
            type='raster',
            name=grass_name)
        print(res)
    except Exception as e:
        print(e)
        return json.dumps({"message": "Error"})

    with rio.open(output_name) as src:
        image = src.read(1)
        results = [{
            'properties': {'visibility': v},
            'geometry': s,
            'type': 'Feature',
            } for i, (s, v) in enumerate(rio_shapes(
                image, mask=None, transform=src.transform)) if v == 1.0]
    with open('/tmp/{}.geojson'.format(uid), 'w') as f:
        f.write(json.dumps({"type": "FeatureCollection", "features": results}))
    p = subprocess.Popen(shlex.split(
        'ogr2ogr -s_srs "EPSG:2154" -t_srs "EPSG:4326" -f GeoJSON /dev/stdout /tmp/{}.geojson'.format(uid, uid)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        )
    out, err = p.communicate()
    if p.returncode != 0:
        print('Error occured !')
        print('Error: ', err)
    os.remove('/tmp/{}.geojson'.format(uid))
    return out.decode()

GRASS, TO_L93, PATH_INFO = LocalProxy(init_grass)
# result = interviz(
#     "917408.7481353938,6464098.815927067",
#     "0",
#     "1.6",
#     "22000")
# print(result)
#
# result = interviz(
#     "917102.7,6464912.1",
#     "1.0",
#     "1.0",
#     "22000")
# print(result)
