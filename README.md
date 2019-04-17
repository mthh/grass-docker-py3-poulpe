### Simple Docker container to expose r.viewshed and r.sunmask functionnalities from GRASS 7.7


#### Usage :

- Building the container can be done with something like :
```
docker build -t "test_interviz_grass" .
```
A zip archive (containing a .tif file : the DEM to use) is expected to be in the same folder (and that geotiff file must have a valid projection which can be decribed by an EPSG code).

- Running it and exposing it on port 5000 :
```
docker run --publish "5000:5000" -it "test_interviz_grass:latest"
```

- Go on http://localhost:5000/ to test it or query the API on http://localhost:5000/viewshed and http://localhost:5000/sunmask. Example :

```
curl "http://localhost:5000/viewshed?coordinates=45.362277645,5.68130493&height1=1.2&height2=1.3"
```
Returns a GeoJSON FeatureCollection corresponding to the zone of visibility.  

```
curl "http://localhost:5000/sunmask?year=2000&month=12&day=1&hour=15&minute=49&center=45.2900000,5.784999961"
```
Returns a GeoJSON FeatureCollection corresponding to the zone not reachable by the sun.


See GRASS r.viewshed and r.sunmask documentation for details on the methods used.
