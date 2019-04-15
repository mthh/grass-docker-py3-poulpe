#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: mthh
"""
import asyncio
import binascii
import json
import os
import logging
import rasterio as rio
import shlex
import subprocess
import sys
import tempfile
import uuid
import uvloop
from aiohttp import web
from functools import partial
from pyproj import Proj, transform
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from rasterio.features import shapes as rio_shapes


async def handle_404(request, response):
    return web.Response(text="ERROR 404 !")


async def error_middleware(app, handler):
    async def middleware_handler(request):
        try:
            response = await handler(request)
            if response.status == 404:
                return await handle_404(request, response)
            return response
        except web.HTTPException as ex:
            if ex.status == 404:
                return await handle_404(request, ex)
            raise

    return middleware_handler


async def index_handler(request):
    return web.FileResponse('index.html')


def init_grass(epsg_value=2154):
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
        raise ValueError('Failed to load GRASS')

    gisbase = out.strip(b'\n').decode()
    os.environ['GISBASE'] = gisbase
    sys.path.append(os.path.join(gisbase, 'etc', 'python'))
    gisdb = os.path.join(tempfile.gettempdir(), 'grassdata')

    try:
        os.stat(gisdb)
    except:
        os.mkdir(gisdb)

    location = binascii.hexlify(os.urandom(12)).decode()
    location_path = os.path.join(gisdb, location)
    mapset = 'PERMANENT'

    startcmd = ' '.join([
        grass_bin,
        '-c epsg:{}'.format(epsg_value),
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
        raise ValueError('Failed to start GRASS')

    print('Created location ', location_path)

    import grass.script as grass
    import grass.script.setup as gsetup

    gsetup.init(gisbase, gisdb, location, mapset)
    grass.message('--- GRASS GIS 7: Current GRASS GIS 7 environment:')
    print(grass.gisenv())

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

    grass.message('--- GRASS GIS 7: Defining the region...')
    grass.read_command(
        'g.region',
        n="6551114.0",
        s="6392480.0",
        e="984410.0",
        w="871682.0",
        res="24.96217255547944802")

    in_proj = Proj(
        "+proj=lcc +lat_1=49 +lat_2=44 +lat_0=46.5 +lon_0=3 ""+x_0=700000 "
        "+y_0=6600000 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs")
    out_proj = Proj(init='epsg:4326')

    return (
        partial(transform, out_proj, in_proj),
        {
            "gisbase": gisbase,
            "gisdb": gisdb,
            "location": location,
            "mapset": mapset,
        },
    )


def _validate_coordinates(coords, _to_l93):
    _coords = list(map(lambda x: float(x), coords.split(',')))
    _coords = _to_l93(_coords[1], _coords[0])
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


async def interviz_wrapper(request):
    try:
        c = _validate_coordinates(
            request.rel_url.query['coordinates'],
            request.app['TO_L93'],
        )
        h1 = _validate_number(request.rel_url.query['height1'])
        h2 = _validate_number(request.rel_url.query['height2'])
        m_dist = _validate_number(request.rel_url.query.get('max_distance', '25000'))
    except Exception as e:
        return web.Response(
            text=json.dumps({"message": "Error : {}".format(e)}))

    res = await request.app.loop.run_in_executor(
        request.app["ProcessPool"],
        interviz,
        request.app['path_info'],
        c, h1, h2, m_dist,
    )

    return web.Response(text=res)


def interviz(path_info, coordinates, height1, height2, max_distance="-1"):
    import grass.script as GRASS
    try:
        uid = str(uuid.uuid4()).replace('-', '')
        grass_name = "output_{}".format(uid)
        output_name = os.path.join(path_info['gisdb'], '.'.join([uid, 'tif']))
        GRASS.message(
            '--- GRASS GIS 7: Computing viewshed')
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

        GRASS.message(
            '--- GRASS GIS 7: Saving resulting raster layer')
        res = GRASS.read_command(
            'r.out.gdal',
            input=grass_name,
            output=output_name,
            format="GTiff",
            createopt="TFW=YES,COMPRESS=LZW",
        )
        print(res)

        GRASS.message(
            '--- GRASS GIS 7: Remove temporary result raster from GRASS')
        res = GRASS.read_command(
            'g.remove',
            flags='f',
            type='raster',
            name=grass_name,
        )
        print(res)

    except Exception as e:
        return json.dumps({"message": "Error : {}".format(e)})

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

    p = subprocess.Popen(
        shlex.split(
            'ogr2ogr -s_srs "EPSG:2154" -t_srs "EPSG:4326" '
            '-f GeoJSON /dev/stdout /tmp/{}.geojson'.format(uid)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = p.communicate()
    os.remove('/tmp/{}.geojson'.format(uid))
    if p.returncode != 0:
        print('Error occured !')
        print('Error: ', err)
        return json.dumps({"message": "Error : {}".format(err)})

    return out.decode()


async def init(loop, addr, port):
    logging.basicConfig(level=logging.INFO)

    app = web.Application(
        loop=loop,
        client_max_size=17408**2,
        middlewares=[error_middleware],
    )
    app['logger'] = logging.getLogger("interviz_app")
    app['TO_L93'], app['path_info'] = init_grass()

    app.router.add_route('GET', '/', index_handler)
    app.router.add_route('GET', '/index', index_handler)
    app.router.add_route('GET', '/viewshed', interviz_wrapper)

    handler = app.make_handler()
    srv = await loop.create_server(handler, addr, port)
    return srv, app, handler


def main(addr='0.0.0.0', port=5000):
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    srv, app, handler = loop.run_until_complete(init(loop, addr, port))

    app['logger'].info('serving on' + str(srv.sockets[0].getsockname()))
    app['ThreadPool'] = ThreadPoolExecutor(4)
    app['ProcessPool'] = ProcessPoolExecutor(4)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.close()
        loop.run_until_complete(srv.wait_closed())
        loop.run_until_complete(app.shutdown())
        loop.run_until_complete(handler.shutdown(60.0))
        loop.run_until_complete(app.cleanup())
    loop.close()


if __name__ == '__main__':
    main()
