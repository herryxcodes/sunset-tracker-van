# Gathers the real West End and Coal Harbour, the part of the city in frame (bearings 290..55 deg, out to 3.6 km), into
# blender/cache/city.json for land.py and horizon.py:
#   buildings  City of Vancouver building footprints 2009 (LiDAR base and roof elevations), plus OpenStreetMap buildings
#              with a height or storey count for towers finished since then
#   trees      City of Vancouver public trees (position and height)
# Positions are metres east (x) / north (y) of the camera; elevations are metres above sea level.
# Data: City of Vancouver Open Data (Open Government Licence - Vancouver); (c) OpenStreetMap contributors (ODbL).
# Usage: python blender/city.py DATA_DIR   (downloads into DATA_DIR on first run)
import sys, os, json, math, urllib.request, urllib.parse
import numpy as np
from scipy.spatial import cKDTree

SITE_LAT, SITE_LON = 49.283786, -123.143271
R_MAX = 3600
HERE = os.path.dirname(os.path.abspath(__file__))
D = sys.argv[1]; os.makedirs(D, exist_ok=True)
COV = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/{}/exports/{}?where=" + urllib.parse.quote(
    f"within_distance(geom, geom'POINT({SITE_LON} {SITE_LAT})', {R_MAX}m)")
SOURCES = {
    "footprints.geojson": COV.format("building-footprints-2009", "geojson"),
    "trees.json": COV.format("public-trees", "json") + "&select=height_m,diameter_cm,geo_point_2d",
    "osm.json": "https://overpass.kumi.systems/api/interpreter?data=" + urllib.parse.quote(
        f'[out:json][timeout:120];way["building"](around:{R_MAX},{SITE_LAT},{SITE_LON});out tags geom;'),
}
for name, url in SOURCES.items():
    p = os.path.join(D, name)
    if not os.path.exists(p):
        req = urllib.request.Request(url, headers={"User-Agent": "isthesunsetgood.ca scenery build"})
        open(p, "wb").write(urllib.request.urlopen(req, timeout=300).read()); print("downloaded", name, flush=True)

# local metres on the WGS84 ellipsoid around the camera (well under a metre off at 3.6 km)
a, e2 = 6378137.0, 6.69437999014e-3
phi = math.radians(SITE_LAT); w = math.sqrt(1 - e2 * math.sin(phi) ** 2)
M, N = a * (1 - e2) / w ** 3, a / w
def xy(lon, lat): return ((np.asarray(lon) - SITE_LON) * math.radians(1) * N * math.cos(phi), (np.asarray(lat) - SITE_LAT) * math.radians(1) * M)
def in_view(x, y):
    b = (np.degrees(np.arctan2(x, y)) + 360) % 360; r = np.hypot(x, y)
    return ((b >= 290) | (b <= 55)) & (r > 40) & (r < R_MAX)

def inside(px, py, ring):
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > py) != (y2 > py) and px < x1 + (py - y1) * (x2 - x1) / (y2 - y1): c = not c
    return c

# ---------- City footprints ----------
blds = []
for f in json.load(open(os.path.join(D, "footprints.geojson")))["features"]:
    p, g = f["properties"], f["geometry"]
    rings = g["coordinates"] if g["type"] == "Polygon" else [r[0] for r in g["coordinates"]]
    base, top = p.get("base_m") or p.get("baseelev_m"), p.get("topelev_m")
    if base is None or top is None or top - base < 2.5: continue
    for r in rings[:1] if g["type"] == "Polygon" else rings:
        x, y = xy([c[0] for c in r], [c[1] for c in r])
        if not in_view(x, y).any(): continue
        ring = [(round(float(u), 2), round(float(v), 2)) for u, v in zip(x, y)][:-1]
        if len(ring) >= 3: blds.append({"base": base, "top": top, "ring": ring, "src": "cov"})
print("city footprints in view", len(blds), flush=True)
bases = cKDTree(np.array([np.mean(b["ring"], 0) for b in blds]))
base_z = np.array([b["base"] for b in blds])

# ---------- OpenStreetMap towers newer than 2009 ----------
def num(v):
    try: return float(str(v).split(";")[0].split()[0].replace(",", "."))
    except Exception: return None
added = replaced = 0
for el in json.load(open(os.path.join(D, "osm.json")))["elements"]:
    t = el.get("tags", {}); h = num(t.get("height"))
    if h is None and num(t.get("building:levels")): h = num(t["building:levels"]) * 3.0 + 2.0
    if not h or h < 8 or "geometry" not in el: continue
    x, y = xy([q["lon"] for q in el["geometry"]], [q["lat"] for q in el["geometry"]])
    if not in_view(x, y).any(): continue
    cx, cy = float(np.mean(x)), float(np.mean(y))
    near = bases.query_ball_point([cx, cy], 120)
    hits = [i for i in near if blds[i] and inside(cx, cy, blds[i]["ring"])]
    if any(blds[i]["top"] - blds[i]["base"] >= 0.7 * h for i in hits): continue   # the 2009 survey already has it
    for i in hits: blds[i] = None; replaced += 1                                  # a lower building that was torn down
    d, k = bases.query([cx, cy], 4); z = float(np.average(base_z[k], weights=1 / (np.asarray(d) + 1)))
    ring = [(round(float(u), 2), round(float(v), 2)) for u, v in zip(x, y)]
    if ring[0] == ring[-1]: ring = ring[:-1]
    blds.append({"base": z, "top": z + h, "ring": ring, "src": "osm"}); added += 1
blds = [b for b in blds if b]
print("osm towers added", added, "replacing", replaced, flush=True)

# ---------- street and park trees ----------
trees = []
tr = json.load(open(os.path.join(D, "trees.json")))
tx, ty = xy([q["geo_point_2d"]["lon"] for q in tr], [q["geo_point_2d"]["lat"] for q in tr])
keep = in_view(tx, ty)
d, k = bases.query(np.stack([tx, ty], 1), 4)
tz = np.average(base_z[k], axis=1, weights=1 / (d + 1))
for i in np.nonzero(keep)[0]:
    h = tr[i].get("height_m") or 6.0
    trees.append([round(float(tx[i]), 1), round(float(ty[i]), 1), round(float(tz[i]), 1), round(min(h, 40), 1)])
print("trees in view", len(trees), flush=True)

os.makedirs(os.path.join(HERE, "cache"), exist_ok=True)
json.dump({"buildings": blds, "trees": trees}, open(os.path.join(HERE, "cache", "city.json"), "w"), separators=(",", ":"))
