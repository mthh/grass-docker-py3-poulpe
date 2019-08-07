## Docker container to expose GRASS 7.7 `r.viewshed` and `r.sunmask` functionnalities

Note: *This container is based on the [development version of GRASS](https://trac.osgeo.org/grass/wiki/DownloadSource#GitGRASSmainsourcecoderepository) (current state of the master branch when building the container).*  

Note: *See the ['with_region'](https://github.com/mthh/grass-docker-py3-poulpe/tree/with_region) branch for the same container allowing to specify the region on each query (instead of 'max_distance').*

### Usage :

*A zip archive (containing a .tif file : the DEM to use) is expected to be in the same folder as the Dockerfile (and that geotiff file must have a valid projection which can be decribed by an EPSG code).*  


- Building the container can be done with something like :
```
docker build -t "test_interviz_grass" .
```

- Running it and exposing it on port 5000 :
```
docker run --publish "5000:5000" -it "test_interviz_grass:latest"
```

- Go on http://localhost:5000/ to test it interactively or query the API on http://localhost:5000/viewshed and http://localhost:5000/sunmask. Example :

#### Viewshed

```
curl "http://localhost:5000/viewshed?coordinates=45.362277645,5.68130493&height1=1.2&height2=1.3"
```

| Parameter    | Description                                                                       |
|--------------|-----------------------------------------------------------------------------------|
| coordinates  | String of format {latitude},{longitude}.                                          |
| height1      | Double or integer >= 0. Viewing elevation above the ground (in meters).           |
| height2      | Double or integer >= 0. Offset for target elevation above the ground (in meters). |

| Option        | Description                                                                   |
|---------------|-------------------------------------------------------------------------------|
|  max_distance | Integer > 0. Maximum visibility radius (in meters). Defaults to 22000m.       |


Returns a GeoJSON FeatureCollection corresponding to the zone of visibility.  

#### Sunmask

```
curl "http://localhost:5000/sunmask?coordinates=45.2900000,5.784999961&year=2000&month=10&day=1&hour=15&minute=49"
```

| Parameter    | Description                                 |
|--------------|---------------------------------------------|
| coordinates  | String of format {latitude},{longitude}.    |
| year         | Integer with 1950 <= year < 2050.           |
| month        | Integer with 0 < month <= 12.               |
| day          | Integer with 0 < day <= 31.                 |
| hour         | Integer with 0 <= hour < 24.                |
| minute       | Integer with 0 <= minute < 60.              |

| Option        | Description                                                                   |
|---------------|-------------------------------------------------------------------------------|
| max_distance  | Integer > 0. Maximum computation radius (in meters). Defaults to 4000m.       |
| timezone      | Integer >= 0. East positive, offset from GMT. Defaults to 1.                  |


Returns a GeoJSON FeatureCollection corresponding to areas of cast shadow at the given datetime.

See GRASS [r.viewshed](https://grass.osgeo.org/grass77/manuals/r.viewshed.html) and [r.sunmask](https://grass.osgeo.org/grass77/manuals/r.sunmask.html) documentation for details on the methods used.
