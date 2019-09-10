## Docker container to expose GRASS 7.8 `r.viewshed` and `r.sunmask` functionnalities

Note: *This container is based on the [release branch of GRASS 7.8](https://trac.osgeo.org/grass/wiki/DownloadSource) (current state of the tree when building the container).*  


### Usage :

*A zip archive (containing a .tif file : the DEM to use) is expected to be in the same folder as the Dockerfile (and that geotiff file must have a valid projection which can be decribed by an EPSG code).*  


- Building the container can be done with something like :
```
docker build -t "interviz_sunmask_grass78" .
```

- Running it and exposing it on port 5000 :
```
docker run --publish "5000:5000" -it "interviz_sunmask_grass78:latest"
```

#### Viewshed

```
curl "http://localhost:5000/viewshed?coordinates=45.362277645,5.68130493&height1=1.2&height2=1.3"
```

```
curl "http://localhost:5000/viewshed?coordinates=45.36,5.68&height1=1.2&height2=1.3&region=5.60,5.80,45.35,45.52"
```

| Parameter    | Description                                                                       |
|--------------|-----------------------------------------------------------------------------------|
| coordinates  | String of format {latitude},{longitude}.                                          |
| height1      | Double or integer >= 0. Viewing elevation above the ground (in meters).           |
| height2      | Double or integer >= 0. Offset for target elevation above the ground (in meters). |

| Option     | Description                                                                                             |
|------------|---------------------------------------------------------------------------------------------------------|
|  region    | String of format {west},{east},{sud},{north}. The region to use. Defaults to the region of the dataset. |


Returns a GeoJSON FeatureCollection corresponding to the zone of visibility.  

#### Sunmask

```
curl "http://localhost:5000/sunmask?year=2000&month=10&day=1&hour=15&minute=49"
```

```
curl "http://localhost:5000/sunmask?year=2000&month=10&day=1&hour=15&minute=49&region=5.60,5.80,45.35,45.52"
```

| Parameter    | Description                                 |
|--------------|---------------------------------------------|
| year         | Integer with 1950 <= year < 2050.           |
| month        | Integer with 0 < month <= 12.               |
| day          | Integer with 0 < day <= 31.                 |
| hour         | Integer with 0 <= hour < 24.                |
| minute       | Integer with 0 <= minute < 60.              |

| Option    | Description                                                                                             |
|-----------|---------------------------------------------------------------------------------------------------------|
| region    | String of format {west},{east},{sud},{north}. The region to use. Defaults to the region of the dataset. |
| timezone  | Integer >= 0. East positive, offset from GMT. Defaults to 1.                                            |
| sun       | Boolean. Wheter to returns the areas of sun instead of the areas of shadows. Defaults to 'false'.       |

Returns a GeoJSON FeatureCollection corresponding to areas of cast shadow at the given datetime (or the difference between the region and theses areas, if the 'sun' argument is set to 'true').

#### Sun

```
curl "http://localhost:5000/sun?year=2000&month=10&day=1&hour=15&minute=49"
```

```
curl "http://localhost:5000/sun?year=2000&month=10&day=1&hour=15&minute=49&region=5.60,5.80,45.35,45.52"
```

| Parameter    | Description                                 |
|--------------|---------------------------------------------|
| year         | Integer with 1950 <= year < 2050.           |
| month        | Integer with 0 < month <= 12.               |
| day          | Integer with 0 < day <= 31.                 |
| hour         | Integer with 0 <= hour < 24.                |
| minute       | Integer with 0 <= minute < 60.              |

| Option    | Description                                                                                             |
|-----------|---------------------------------------------------------------------------------------------------------|
| region    | String of format {west},{east},{sud},{north}. The region to use. Defaults to the region of the dataset. |
| timezone  | Integer >= 0. East positive, offset from GMT. Defaults to 1.                                            |
| sun       | Boolean. Wheter to returns the areas of sun instead of the areas of shadows. Defaults to 'false'.       |

Returns a GeoJSON FeatureCollection corresponding to areas of cast shadow at the given datetime (or the difference between the region and theses areas, if the 'sun' argument is set to 'true'). Result should be the same as with __sunmask__ ... but computed faster.

See GRASS [r.viewshed](https://grass.osgeo.org/grass78/manuals/r.viewshed.html), [r.sun](https://grass.osgeo.org/grass78/manuals/r.sun.html) and [r.sunmask](https://grass.osgeo.org/grass78/manuals/r.sunmask.html) documentation for details on the methods used.
