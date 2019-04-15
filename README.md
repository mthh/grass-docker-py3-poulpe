### Simple Docker container to expose the viewshed functionnality from GRASS 7.7


#### Usage :

- Building the container can be done with something like :
```
docker build -t "test_interviz_grass" .
```

- Running it and exposing it on port 5000 :
```
docker run --publish "5000:5000" -it "test_interviz_grass:latest"
```

- Go on http://localhost:5000/ to test it or query the API on http://localhost:5000/viewshed. Example :

```
curl http://localhost:5000/viewshed?coordinates=45.362277645,5.68130493&height1=1.2&height2=1.3
```
Returns a GeoJSON FeatureCollection corresponding to the zone of visibility.  
See GRASS r.viewshed documentation for details on the method used.
