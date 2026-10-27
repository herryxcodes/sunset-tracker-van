# Traces the real horizon from the English Bay viewpoint through the Copernicus GLO-30 surface model (30 m, trees and
# buildings included) and writes:
#   assets/land/horizon.json    skyline the page uses for "the sun drops behind X": apparent altitude per 0.05 deg of bearing
#   blender/cache/terrain.npz   polar height grid (bearing x distance) that land.py turns into the terrain mesh
# Heights are lowered by the Earth's curvature less standard refraction (k = 0.13), so a ridge 80 km away sits ~440 m
# lower than its map height, and the sea horizon dips 0.10 deg below level from 12 m up.
# Data: Copernicus DEM GLO-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018, provided under
# COPERNICUS by the European Union and ESA. Tiles: https://copernicus-dem-30m.s3.amazonaws.com/
# Usage (needs numpy + rasterio): python blender/horizon.py DEM_DIR
import sys, os, json, math, glob
import numpy as np, rasterio

SITE_LAT, SITE_LON, CAM_H = 49.283786, -123.143271, 12.0     # above Rock Balance Point, 68 m SE of the Inukshuk
R_EARTH, K_REFR = 6371000.0, 0.13
INUK_BEARING, INUK_DIST = 328.2, 68.3
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

# ---------- DEM tiles: 1x1 deg Copernicus COGs, read whole into memory ----------
TILES = {}
for f in glob.glob(os.path.join(sys.argv[1], "Copernicus_DSM_COG_10_*_DEM.tif")):
    with rasterio.open(f) as src:
        a = src.read(1).astype(np.float32); t = src.transform
        TILES[(math.floor(t.f - 0.5), math.floor(t.c + 0.5))] = (a, t)   # key: (floor lat, floor lon) of the tile
print(len(TILES), "tiles", flush=True)

def sample(lat, lon):
    """Bilinear height (m) at arrays of lat/lon; 0 over the sea or off the tiles."""
    out = np.zeros(lat.shape, np.float32)
    kl, ko = np.floor(lat).astype(int), np.floor(lon).astype(int)
    for (tl, to), (a, t) in TILES.items():
        m = (kl == tl) & (ko == to)
        if not m.any(): continue
        c = (lon[m] - t.c) / t.a - 0.5; r = (lat[m] - t.f) / t.e - 0.5
        c0 = np.clip(np.floor(c).astype(int), 0, a.shape[1] - 2); r0 = np.clip(np.floor(r).astype(int), 0, a.shape[0] - 2)
        fc, fr = np.clip(c - c0, 0, 1), np.clip(r - r0, 0, 1)
        out[m] = (a[r0, c0] * (1 - fc) * (1 - fr) + a[r0, c0 + 1] * fc * (1 - fr) +
                  a[r0 + 1, c0] * (1 - fc) * fr + a[r0 + 1, c0 + 1] * fc * fr)
    return np.maximum(out, 0)

def destination(bearing_deg, dist):
    """Vincenty direct on WGS84 from the site: arrays of bearings (deg) and distances (m) -> lat, lon (deg)."""
    a, f = 6378137.0, 1 / 298.257223563; b = a * (1 - f)
    al1 = np.radians(bearing_deg); s = np.asarray(dist, float)
    U1 = math.atan((1 - f) * math.tan(math.radians(SITE_LAT)))
    s1 = np.arctan2(math.tan(U1), np.cos(al1)); sa = math.cos(U1) * np.sin(al1)
    c2a = 1 - sa * sa; u2 = c2a * (a * a - b * b) / (b * b)
    A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2))); B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    sig = s / (b * A)
    for _ in range(6):
        c2m = np.cos(2 * s1 + sig); ss, cs = np.sin(sig), np.cos(sig)
        ds = B * ss * (c2m + B / 4 * (cs * (-1 + 2 * c2m ** 2) - B / 6 * c2m * (-3 + 4 * ss ** 2) * (-3 + 4 * c2m ** 2)))
        sig = s / (b * A) + ds
    ss, cs, c2m = np.sin(sig), np.cos(sig), np.cos(2 * s1 + sig)
    t = math.sin(U1) * ss - math.cos(U1) * cs * np.cos(al1)
    lat = np.arctan2(math.sin(U1) * cs + math.cos(U1) * ss * np.cos(al1), (1 - f) * np.sqrt(sa * sa + t * t))
    lam = np.arctan2(ss * np.sin(al1), math.cos(U1) * cs - math.sin(U1) * ss * np.cos(al1))
    C = f / 16 * c2a * (4 + f * (4 - 3 * c2a))
    L = lam - (1 - C) * f * sa * (sig + C * ss * (c2m + C * cs * (-1 + 2 * c2m ** 2)))
    return np.degrees(lat), SITE_LON + np.degrees(L)

def drop(d): return (1 - K_REFR) * d * d / (2 * R_EARTH)   # apparent lowering by curvature less refraction

def name_of(lat, lon, d):
    if lat < 48.3: return "the Olympic Mountains"
    if lat < 48.8 and lon > -123.3: return "the San Juan Islands"
    if 49.21 < lat < 49.31 and -123.28 < lon < -123.14: return "Point Grey"
    if 49.31 < lat < 49.42 and -123.44 < lon < -123.29: return "Bowen Island"
    if lat > 49.30 and lon > -123.29: return "the North Shore mountains"
    if lat > 49.36 and lon < -123.44 and lon > -124.2: return "the Sunshine Coast"
    if d < 60000 and lon > -123.85 and lat < 49.25: return "the Gulf Islands"
    return "Vancouver Island"

# ---------- skyline for the page ----------
AZ = np.round(np.arange(195, 405.0001, 0.05), 3)
D = [150.0]
while D[-1] < 200000: D.append(D[-1] + max(15.0, D[-1] * 0.0015))
D = np.array(D)
dip = -math.degrees(math.sqrt(2 * CAM_H * (1 - K_REFR) / R_EARTH))   # sea horizon
sky_alt, sky_d, sky_name = [], [], []
for az in AZ:
    lat, lon = destination(np.full(D.shape, az), D)
    h = sample(lat, lon)
    ang = np.degrees(np.arctan2(h - drop(D) - CAM_H, D))
    ang[h < 0.5] = -90                                       # open water: handled by the sea horizon
    i = int(np.argmax(ang))
    if ang[i] > dip: sky_alt.append(round(float(ang[i]), 3)); sky_d.append(int(D[i])); sky_name.append(name_of(lat[i], lon[i], D[i]))
    else: sky_alt.append(round(dip, 3)); sky_d.append(0); sky_name.append("the sea")
names = sorted(set(sky_name))
json.dump({"az0": float(AZ[0]), "step": 0.05, "dip": round(dip, 3), "names": names,
           "alt": sky_alt, "dist": sky_d, "name": [names.index(n) for n in sky_name],
           "source": "Copernicus DEM GLO-30, curvature with refraction k=0.13, camera 12 m"},
          open(os.path.join(ROOT, "assets/land/horizon.json"), "w"), separators=(",", ":"))
print("skyline written", flush=True)
for a in range(230, 315, 5):
    i = int(round((a - AZ[0]) / 0.05)); print(f"  {a:3d}  {sky_alt[i]:+.3f} deg  {sky_d[i] / 1000:6.1f} km  {sky_name[i]}")

# ---------- polar terrain grid for Blender ----------
GA = np.arange(199.0, 401.0001, 0.06)
GD = [500.0]
while GD[-1] < 190000: GD.append(GD[-1] + max(25.0, GD[-1] * 0.004))
GD = np.array(GD)
bb, dd = np.meshgrid(GA, GD, indexing="ij")
lat, lon = destination(bb.ravel(), dd.ravel())
H = sample(lat, lon).reshape(bb.shape)
# areas already modelled by hand in fg_ebay.py / sp_ebay.py (metres east/north of the Inukshuk) are left out
sx, sy = math.sin(math.radians(INUK_BEARING)) * INUK_DIST, math.cos(math.radians(INUK_BEARING)) * INUK_DIST
x, y = dd * np.sin(np.radians(bb)) - sx, dd * np.cos(np.radians(bb)) - sy
own = (((-330 <= x) & (x <= 150) & (180 <= y) & (y <= 1060)) | ((-1400 <= x) & (x <= 700) & (1040 <= y) & (y <= 4200)) |
       ((-280 <= x) & (x <= 400) & (260 <= y) & (y <= 1050)) | ((-70 <= x) & (x <= 120) & (-150 <= y) & (y <= 220)))
os.makedirs(os.path.join(HERE, "cache"), exist_ok=True)
np.savez_compressed(os.path.join(HERE, "cache/terrain.npz"), az=GA, dist=GD, h=H.astype(np.float32),
                    z=(H - drop(dd)).astype(np.float32), own=own, k=K_REFR)
print("terrain grid", H.shape, "land cells", int((H > 0.5).sum()), flush=True)
