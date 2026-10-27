# Is the sunset good?

A one-page site that answers one question for Vancouver: is it worth going out to English Bay for the sunset right now?

Live at **[isthesunsetgood.ca](https://isthesunsetgood.ca)**.

- **The answer**: a 0–100 score and a plain verdict, from the live [Open-Meteo](https://open-meteo.com) forecast for the beach and
  for a point about 60 km west over the Strait of Georgia (low cloud there is what usually spoils a Vancouver sunset).
- **The view**: a time-lapse from about 12 m above Rock Balance Point, looking past the Inukshuk to Stanley Park and the
  North Shore mountains. The sun position is computed in the browser; sky, sea and scenery are rendered in Blender; clouds,
  rain, fog and haze are drawn live from the forecast. The horizon is traced from a 30 m elevation model, allowing for the Earth's curvature.

No build step and no API keys: `index.html` plus the `assets/` folder is the whole site.

## Re-rendering the scenery

The horizon and terrain come from the [Copernicus DEM GLO-30](https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model)
surface model (30 m, trees included). Download the 1° tiles N47–N50 × W123–W126 from the public bucket, trace the horizon, then render
with the Blender 5.x scripts in `blender/`:

```bash
for la in 47 48 49 50; do for lo in 123 124 125 126; do n=Copernicus_DSM_COG_10_N${la}_00_W${lo}_00_DEM
  curl -sfO https://copernicus-dem-30m.s3.amazonaws.com/$n/$n.tif; done; done        # into a folder of your choice, ~450 MB
python blender/city.py CITY_FOLDER         # needs numpy + scipy; downloads City of Vancouver and OpenStreetMap data, writes blender/cache/city.json
python blender/horizon.py DEM_FOLDER       # needs numpy, rasterio + scipy; writes assets/land/horizon.json and blender/cache/terrain.npz
blender -b --factory-startup -P blender/land.py -- assets/land 24 64
for s in clean:0.5 typical:1.25 hazy:3.0; do
  blender -b --factory-startup -P blender/sky_frames.py -- assets/sky/${s%%:*} 16 48 30,24,19,15,12,10,8,6.5,5,4,3,2.25,1.5,0.75,0,-0.75,-1.5,-2.25,-3,-4,-5,-6,-7,-8.5,-10,-12,-15 ${s##*:}
done
blender -b --factory-startup -P blender/clouds.py -- assets/clouds
```

`horizon.py` follows WGS84 geodesics out from the camera and lowers every height by the Earth's curvature less standard refraction
(k = 0.13), so the skyline, the sea horizon (0.10° below level from 12 m) and the terrain mesh sit where the eye sees them.
`land.py` turns that grid into a 2-million-face terrain mesh around the hand-built foreground (`fg_ebay.py`, the Inukshuk point) and
Stanley Park (`sp_ebay.py`), adds the West End and Coal Harbour from survey data (`city_ebay.py`: City of Vancouver building
footprints with LiDAR heights, OpenStreetMap towers built since 2009, and the City's public trees), and renders the skylit scenery, a haze-distance layer and direct sunlight for 56 sun positions; the page
tints that sunlight by the air mass and the forecast aerosol depth. The sky frames are in sun-relative azimuth, so the page slides them
to the sun's true bearing for any day of the year.

Buildings and trees: City of Vancouver Open Data, Open Government Licence – Vancouver; © OpenStreetMap contributors, ODbL.
Elevation data: Copernicus DEM GLO-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, provided under COPERNICUS by
the European Union and ESA; all rights reserved.
