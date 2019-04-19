#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: mthh
"""
import asyncio
import binascii
import json
import logging
import math
import os
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

def get_extent_proj(path):
    with rio.open(path) as f:
        crs = f.read_crs()
        bounds = f.bounds
        return {
            'path': path,
            'crs_epsg': crs.to_epsg(),
            'crs_string': Proj(crs.to_string()).srs,
            'w': math.ceil(bounds[0]),
            's': math.ceil(bounds[1]),
            'e': math.floor(bounds[2]),
            'n': math.floor(bounds[3]),
            'ewres': f.res[0],
            'nsres': f.res[1],
        }

def init_grass(info_dem):
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
        raise ValueError(
            'Failed to load GRASS\nStdout: {}\nStderr: {}\n'
            .format(out.decode(), err.decode()))

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
        '-c epsg:{}'.format(info_dem['crs_epsg']),
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
        raise ValueError(
            'Failed to load GRASS\nStdout: {}\nStderr: {}\n'
            .format(out.decode(), err.decode()))

    print('Created location ', location_path)

    import grass.script as grass
    import grass.script.setup as gsetup

    gsetup.init(gisbase, gisdb, location, mapset)
    grass.message('--- GRASS GIS 7: Current GRASS GIS 7 environment:')
    print(grass.gisenv())

    grass.message('--- GRASS GIS 7: Setting projection info:')
    _out_proj = grass.read_command(
        'g.proj',
        flags='c',
        epsg=info_dem['crs_epsg'],
    )
    print(_out_proj)

    grass.message('--- GRASS GIS 7: Loading DEM file:')
    res = grass.read_command(
        'r.external',
        flags='o',
        input=info_dem['path'],
        band=1,
        output="rast_5cb08c8150bbc7",
    )
    print(res)

    grass.message('--- GRASS GIS 7: Defining the region...')
    grass.read_command(
        'g.region',
        n=info_dem['n'],
        s=info_dem['s'],
        e=info_dem['e'],
        w=info_dem['w'],
        nsres=info_dem['nsres'],
        ewres=info_dem['ewres'],
    )

    in_proj = Proj(info_dem['crs_string'])
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


def _validate_coordinates(coords, _to_projected, info_dem):
    _coords = list(map(lambda x: float(x), coords.split(',')))
    _coords = _to_projected(_coords[1], _coords[0])
    if _coords[1] >= info_dem['n'] or _coords[1] <= info_dem['s'] \
            or _coords[0] >= info_dem['e'] or _coords[0] <= info_dem['w']:
        raise ValueError(
            'Requested point {} is outside the allowed region '
            '(xmin={}, xmax={}, ymin={}, ymax={})'
            .format(
                _coords,
                info_dem['w'],
                info_dem['e'],
                info_dem['s'],
                info_dem['n'],
            ))
    return '{},{}'.format(*_coords)


def _validate_number(h):
    # Will raise a ValueError if 'h' isn't / can't be converted
    # to 'float' :
    float(h)
    return h


async def interviz_wrapper(request):
    try:
        c = _validate_coordinates(
            request.rel_url.query['coordinates'],
            request.app['to_proj'],
            request.app['info_dem'],
        )
        h1 = _validate_number(request.rel_url.query['height1'])
        h2 = _validate_number(request.rel_url.query['height2'])
        m_dist = _validate_number(request.rel_url.query.get('max_distance', '22000'))
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


def interviz(path_info, coordinates, height1, height2, max_distance):
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
        epsg_value = src.crs.to_epsg()
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
            'ogr2ogr -s_srs "EPSG:{}" -t_srs "EPSG:4326" '
            '-f GeoJSON /dev/stdout /tmp/{}.geojson'.format(epsg_value, uid)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = p.communicate()
    os.remove('/tmp/{}.geojson'.format(uid))
    if p.returncode != 0:
        print('Error: ', err)
        return json.dumps({"message": "Error : {}".format(err)})

    return out.decode()

def _validate_datetime(year, month, day, hour, minute):
    # In order to raise a ValueError if one of them
    # isn't (or cannot be converted to) an 'int' :
    int(year) + int(month) + int(day) + int(hour) + int(minute)
    return (year, month, day, hour, minute)

async def sunmask_wrapper(request):
    try:
        d = _validate_datetime(
            request.rel_url.query['year'],
            request.rel_url.query['month'],
            request.rel_url.query['day'],
            request.rel_url.query['hour'],
            request.rel_url.query['minute'],
        )
        c = _validate_coordinates(
            request.rel_url.query['coordinates'],
            request.app['to_proj'],
            request.app['info_dem'],
        )
        max_distance = int(request.rel_url.query.get('max_distance', '4000'))
        tz = _validate_number(request.rel_url.query.get('timezone', '1'))
        if not 0 <= int(tz) <= 25:
            raise ValueError('Invalid timezone')
    except Exception as e:
        return web.Response(
            text=json.dumps({"message": "Error : {}".format(e)}))

    res = await request.app.loop.run_in_executor(
        request.app["ProcessPool"],
        sunmask,
        request.app['path_info'],
        request.app['info_dem'],
        d, c, max_distance, tz,
    )

    return web.Response(text=res)

def sunmask(path_info, info_dem, d, coordinates, max_distance, tz):
    c = list(map(lambda x: float(x), coordinates.split(',')))
    import grass.script as GRASS
    try:
        uid = str(uuid.uuid4()).replace('-', '')
        grass_name = "output_{}".format(uid)
        output_name = os.path.join(path_info['gisdb'], '.'.join([uid, 'tif']))

        ### TODO : ensure no other process is trying to read while
        ### we use that reduced region :
        GRASS.read_command(
            'g.region',
            n=str(c[1] + max_distance),
            s=str(c[1] - max_distance),
            e=str(c[0] + max_distance),
            w=str(c[0] - max_distance),
            nsres=info_dem['nsres'],
            ewres=info_dem['ewres'],
        )

        GRASS.message(
            '--- GRASS GIS 7: Computing sunmask')
        res = GRASS.read_command(
            'r.sunmask',
            elevation='rast_5cb08c8150bbc7',
            year=d[0],
            month=d[1],
            day=d[2],
            hour=d[3],
            minute=d[4],
            timezone=tz,
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

        GRASS.read_command(
            'g.region',
            n=info_dem['n'],
            s=info_dem['s'],
            e=info_dem['e'],
            w=info_dem['w'],
            nsres=info_dem['nsres'],
            ewres=info_dem['ewres'],
        )

    except Exception as e:
        return json.dumps({"message": "Error : {}".format(e)})

    with rio.open(output_name) as src:
        epsg_value = src.crs.to_epsg()
        image = src.read(1)
        results = [{
            'properties': {'sun': v},
            'geometry': s,
            'type': 'Feature',
            } for i, (s, v) in enumerate(rio_shapes(
                image, mask=None, transform=src.transform)) if v == 1.0]

    with open('/tmp/{}.geojson'.format(uid), 'w') as f:
        f.write(json.dumps({"type": "FeatureCollection", "features": results}))

    p = subprocess.Popen(
        shlex.split(
            'ogr2ogr -s_srs "EPSG:{}" -t_srs "EPSG:4326" '
            '-f GeoJSON /dev/stdout /tmp/{}.geojson'.format(epsg_value, uid)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = p.communicate()
    os.remove('/tmp/{}.geojson'.format(uid))
    if p.returncode != 0:
        print('Error: ', err)
        return json.dumps({"message": "Error : {}".format(err)})

    return out.decode()


async def init(loop, addr, port, info_dem):
    logging.basicConfig(level=logging.INFO)

    app = web.Application(
        loop=loop,
        client_max_size=17408**2,
        middlewares=[error_middleware],
    )
    app['logger'] = logging.getLogger("interviz_app")
    app['to_proj'], app['path_info'] = init_grass(info_dem)
    app['info_dem'] = info_dem
    app.router.add_route('GET', '/', index_handler)
    app.router.add_route('GET', '/index', index_handler)
    app.router.add_route('GET', '/sunmask', sunmask_wrapper)
    app.router.add_route('GET', '/viewshed', interviz_wrapper)

    handler = app.make_handler()
    srv = await loop.create_server(handler, addr, port)
    return srv, app, handler


def main(info_dem, addr='0.0.0.0', port=5000):
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    srv, app, handler = loop.run_until_complete(
        init(loop, addr, port, info_dem))

    app['logger'].info('serving on' + str(srv.sockets[0].getsockname()))
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
    from glob import glob
    from pprint import pprint
    filename = glob('*.tif')
    info_dem = get_extent_proj(filename[0])
    pprint("DEM file info :")
    pprint(info_dem)
    main(info_dem)
