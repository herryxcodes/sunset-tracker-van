# Is the sunset good?

A one-page site that answers one question for Vancouver: is it worth going out to English Bay for the sunset right now?

Live at **[isthesunsetgood.ca](https://isthesunsetgood.ca)**.

- **The answer**: a 0–100 score and a plain verdict, from the live [Open-Meteo](https://open-meteo.com) forecast for the beach and
  for a point about 60 km west over the Strait of Georgia (low cloud there is what usually spoils a Vancouver sunset).
- **The view**: a time-lapse from about 12 m above Rock Balance Point, looking past the Inukshuk to Stanley Park and the
  North Shore mountains. The sun position is computed in the browser; sky, sea and scenery are rendered in Blender; clouds,
  rain, fog and haze are drawn live from the forecast.

No build step and no API keys: `index.html` plus the `assets/` folder is the whole site.

## Re-rendering the scenery

The Blender 5.x scripts in `blender/` write into `assets/`:

```bash
blender -b --factory-startup -P blender/sky_frames.py -- assets/sky 16 48 30,24,19,15,12,10,8,6.5,5,4,3,2.25,1.5,0.75,0,-0.75,-1.5,-2.25,-3,-4,-5,-6,-7,-8.5,-10,-12,-15
blender -b --factory-startup -P blender/land.py -- assets/land 24 64
blender -b --factory-startup -P blender/clouds.py -- assets/clouds
```

`land.py` builds the horizon ridges and runs `fg_ebay.py` (the Inukshuk point) and `sp_ebay.py` (Stanley Park and the English Bay shore), with shorelines traced from satellite imagery.
The sky frames are in sun-relative azimuth, so the page slides them to the sun's true bearing for any day of the year.
