# Builds the fixed scenery seen from above the Inukshuk at English Bay (true compass bearings) and renders its layers:
#   land_ambient.webp  skylit colour with alpha (terrain, freighters, the Inukshuk and its point, beach)
#   sun/*.webp         direct sunlight for a grid of sun positions (see below)
#   land_haze.webp     white, alpha = aerial-perspective amount by distance (0 near, 1 far)
# Run city.py and then horizon.py first: the terrain and the city come from what they write to blender/cache/.
# World axes: +Y north, +X east, metres. Camera 12 m above the rocks at Rock Balance Point, 68 m south-east of the Inukshuk.
# Usage: Blender -b --factory-startup -P land.py -- OUTDIR PXPERDEG SAMPLES [all|ambient|sun|haze]
import bpy, bmesh, math, sys, os, json, random

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, PXD, SAMPLES = argv[0], float(argv[1]), int(argv[2])
MODE = argv[3] if len(argv) > 3 else "all"   # all | ambient | sun | haze: render only that layer
AZ0, AZ1, ALT0, ALT1 = 200.0, 400.0, -16.0, 20.0   # bearings past 360 wrap to the north-east; tall enough for the nearest trees
os.makedirs(OUT, exist_ok=True)
random.seed(4)
CAMH, INUK_BEARING, INUK_DIST = 12.0, 328.2, 68.3   # drone height over Rock Balance Point

for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"; prefs.get_devices()
for d in prefs.devices: d.use = d.type == "METAL"
sc.cycles.device = "GPU"; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.render.film_transparent = True
sc.render.resolution_x = round((AZ1 - AZ0) * PXD); sc.render.resolution_y = round((ALT1 - ALT0) * PXD)
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "WEBP"; sc.render.image_settings.color_mode = "RGBA"; sc.render.image_settings.quality = 90
sc.view_settings.view_transform = "AgX"

def bdir(b):  # compass bearing (deg) -> unit vector
    r = math.radians(b); return math.sin(r), math.cos(r)

# Camera: equirectangular strip centred on bearing 300
mid = (AZ0 + AZ1) / 2
cd = bpy.data.cameras.new("cam"); cd.type = "PANO"; cd.panorama_type = "EQUIRECTANGULAR"
half = (AZ1 - AZ0) / 2
cd.longitude_min = math.radians(-half); cd.longitude_max = math.radians(half)
cd.latitude_min = math.radians(ALT0); cd.latitude_max = math.radians(ALT1)
cd.clip_end = 300000
cam = bpy.data.objects.new("cam", cd); cam.location = (0, 0, CAMH)
cam.rotation_euler = (math.radians(90), 0, math.radians(-mid))
sc.collection.objects.link(cam); sc.camera = cam

def material(name, rgb, rough=0.9, bump=0.0, scale=40.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links; b = n["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*rgb, 1); b.inputs["Roughness"].default_value = rough
    if bump:
        tx = n.new("ShaderNodeTexNoise"); tx.inputs["Scale"].default_value = scale; tx.inputs["Detail"].default_value = 8
        bm = n.new("ShaderNodeBump"); bm.inputs["Strength"].default_value = bump
        l.new(tx.outputs["Fac"], bm.inputs["Height"]); l.new(bm.outputs["Normal"], b.inputs["Normal"])
        cr = n.new("ShaderNodeMix"); cr.data_type = "RGBA"
        cr.inputs[6].default_value = (*rgb, 1); cr.inputs[7].default_value = (rgb[0] * 1.8, rgb[1] * 1.7, rgb[2] * 1.5, 1)
        l.new(tx.outputs["Fac"], cr.inputs[0]); l.new(cr.outputs[2], b.inputs["Base Color"])
    return m

# Terrain: the real landscape from Point Grey round to the North Shore, Bowen, the Sunshine Coast, the Gulf Islands and
# Vancouver Island, from the polar height grid horizon.py traces through the Copernicus GLO-30 surface model. Heights
# are already lowered for the Earth's curvature (less refraction), so far ridges sit where the eye sees them.
import numpy as np
T = np.load(os.path.join(os.path.dirname(__file__), "cache", "terrain.npz"))
GA, GD, GH, GZ, OWN, CITYG = T["az"], T["dist"], T["h"], T["z"], T["own"], T["city"]
na, nd = GH.shape
land = GH > 0.5
bb, dd = np.meshgrid(np.radians(GA), GD, indexing="ij")
zz = np.where(land, GZ, GZ - 3.0)          # sea cells dip under the water line so coasts slope into the sea
co = np.stack([dd * np.sin(bb), dd * np.cos(bb), zz], -1).reshape(-1, 3)
ii, jj = np.meshgrid(np.arange(na - 1), np.arange(nd - 1), indexing="ij")
q = np.stack([ii * nd + jj, (ii + 1) * nd + jj, (ii + 1) * nd + jj + 1, ii * nd + jj + 1], -1).reshape(-1, 4)
lf, of = land.ravel()[q], OWN.ravel()[q]
q = q[lf.any(1) & ~of.any(1)]
used, inv = np.unique(q, return_inverse=True)
co, q = co[used], inv.reshape(-1, 4)
me = bpy.data.meshes.new("terrain")
me.vertices.add(len(co)); me.vertices.foreach_set("co", co.astype(np.float32).ravel())
me.loops.add(q.size); me.loops.foreach_set("vertex_index", q.astype(np.int32).ravel())
me.polygons.add(len(q)); me.polygons.foreach_set("loop_start", np.arange(0, q.size, 4, dtype=np.int32))
me.update(); me.validate()
# colour: coastal forest and towns low down, subalpine forest, then grey rock and scree on the high peaks
h = GH.ravel()[used]
c = np.empty((len(h), 4), np.float32); c[:, 3] = 1
t = np.clip((h - 1300) / 500, 0, 1)[:, None]
c[:, :3] = np.array([0.014, 0.022, 0.017]) * (1 - t) + np.array([0.07, 0.068, 0.065]) * t
c[CITYG.ravel()[used], :3] = (0.05, 0.05, 0.045)    # streets and lawns between the city's buildings
ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT"); ca.data.foreach_set("color", c.ravel())
for p in me.polygons: p.use_smooth = True
def terrain_mat(n, l, b):
    vc = n.new("ShaderNodeVertexColor"); vc.layer_name = "Col"
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.004; nz.inputs["Detail"].default_value = 8
    mul = n.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs[0].default_value = 0.35
    l.new(vc.outputs["Color"], mul.inputs[6]); l.new(nz.outputs["Color"], mul.inputs[7]); l.new(mul.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
tm = bpy.data.materials.new("terrain"); tm.use_nodes = True
terrain_mat(tm.node_tree.nodes, tm.node_tree.links, tm.node_tree.nodes["Principled BSDF"])
me.materials.append(tm); sc.collection.objects.link(bpy.data.objects.new("terrain", me))
print("TERRAIN", len(co), "verts", len(q), "faces", flush=True)

# The sea as a curved holdout: it cuts out anything below the true sea horizon (the page draws the water there),
# so the feet of far islands drop out of sight as they do over a curving sea. It casts no shadows.
SA = np.radians(np.arange(195, 406, 0.5)); SD = np.concatenate([[0.0], np.geomspace(5, 230000, 260)])
sb, sd = np.meshgrid(SA, SD, indexing="ij")
sco = np.stack([sd * np.sin(sb), sd * np.cos(sb), -(1 - T["k"]) * sd * sd / (2 * 6371000.0)], -1).reshape(-1, 3)
nsa, nsd = sb.shape
ii, jj = np.meshgrid(np.arange(nsa - 1), np.arange(nsd - 1), indexing="ij")
sq = np.stack([ii * nsd + jj, (ii + 1) * nsd + jj, (ii + 1) * nsd + jj + 1, ii * nsd + jj + 1], -1).reshape(-1, 4)
sm = bpy.data.meshes.new("sea"); sm.from_pydata(sco.tolist(), [], sq.tolist())
hold = bpy.data.materials.new("sea_holdout"); hold.use_nodes = True
hn = hold.node_tree.nodes
for x in list(hn): hn.remove(x)
hold.node_tree.links.new(hn.new("ShaderNodeHoldout").outputs[0], hn.new("ShaderNodeOutputMaterial").inputs["Surface"])
sm.materials.append(hold)
sea = bpy.data.objects.new("sea", sm); sea.visible_shadow = False; sc.collection.objects.link(sea)

# Freighters at anchor in English Bay
hull = material("hull", (0.035, 0.018, 0.016), 0.6)
house = material("house", (0.55, 0.55, 0.52), 0.5)
for b, dist, L, head in [(258, 4200, 190, 30), (267, 5600, 225, 75), (276, 3800, 180, 20), (283, 6100, 210, 60), (291, 4700, 200, 40)]:
    sx, sy = bdir(b); cx, cy = sx * dist, sy * dist
    bpy.ops.mesh.primitive_cube_add(location=(cx, cy, 6)); h = bpy.context.object
    h.scale = (L / 2, 16, 7); h.rotation_euler = (0, 0, math.radians(-head)); h.data.materials.append(hull)
    off = L * 0.4
    hx, hy = cx + math.cos(math.radians(-head)) * off, cy + math.sin(math.radians(-head)) * off
    bpy.ops.mesh.primitive_cube_add(location=(hx, hy, 24)); s = bpy.context.object
    s.scale = (9, 14, 12); s.rotation_euler = h.rotation_euler; s.data.materials.append(house)
    for k in range(4):  # cargo cranes / containers
        kx = cx + math.cos(math.radians(-head)) * (L * (0.25 - k * 0.17))
        ky = cy + math.sin(math.radians(-head)) * (L * (0.25 - k * 0.17))
        bpy.ops.mesh.primitive_cube_add(location=(kx, ky, 16)); c = bpy.context.object
        c.scale = (L * 0.07, 13, 4 + random.random() * 3); c.rotation_euler = h.rotation_euler; c.data.materials.append(hull)

exec(open(os.path.join(os.path.dirname(__file__), "fg_ebay.py")).read())
exec(open(os.path.join(os.path.dirname(__file__), "sp_ebay.py")).read())   # Stanley Park, modelled in 3D
exec(open(os.path.join(os.path.dirname(__file__), "city_ebay.py")).read())   # the West End and Coal Harbour from survey data

# Lighting is rendered in parts so the page can relight the scenery for any sun position and air quality:
#   land_ambient.webp       skylight only (a white dome, darker below the horizon), no sun
#   sun/sun_AZ_ALT.webp     direct sunlight only, white sun at compass bearing AZ and apparent altitude ALT, half resolution;
#                           the page tints it with the transmittance along the sun's path and blends the nearest four
# A curved Earth that only casts shadows lets the sun leave the beach first and then climb off the peaks after sunset.
from mathutils import Vector
SUN_AZ = [210, 225, 240, 255, 270, 285, 300, 315]
SUN_ALT = [20, 8, 3, 1, 0, -0.5, -1.0]
earth = bpy.data.objects.new("earth", sm.copy()); earth.location.z = -1.0; earth.visible_camera = False
earth.data.materials.clear(); earth.data.materials.append(material("earth", (0.0, 0.0, 0.0), 1.0)); sc.collection.objects.link(earth)
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
wn = world.node_tree.nodes; wl = world.node_tree.links
tco = wn.new("ShaderNodeTexCoord"); sep = wn.new("ShaderNodeSeparateXYZ"); mr = wn.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = -0.05; mr.inputs["From Max"].default_value = 0.05
mr.inputs["To Min"].default_value = 0.15; mr.inputs["To Max"].default_value = 1.0
wl.new(tco.outputs["Generated"], sep.inputs[0]); wl.new(sep.outputs["Z"], mr.inputs["Value"])
wl.new(mr.outputs["Result"], wn["Background"].inputs["Strength"])
wn["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = 0.6
sc.render.filepath = os.path.join(OUT, "land_ambient.webp")
if MODE in ("all", "ambient"): bpy.ops.render.render(write_still=True); print("RENDERED ambient", flush=True)

sd = bpy.data.lights.new("sun", "SUN"); sd.energy = 8.0; sd.angle = math.radians(0.53)
sun = bpy.data.objects.new("sun", sd); sc.collection.objects.link(sun)
sun_keys = []
if MODE in ("all", "sun"):
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    sc.cycles.samples = max(8, SAMPLES // 4); sc.render.resolution_percentage = 50
    os.makedirs(os.path.join(OUT, "sun"), exist_ok=True)
    for az in SUN_AZ:
        for alt in SUN_ALT:
            e = math.radians(alt); to_sun = Vector((math.sin(math.radians(az)) * math.cos(e), math.cos(math.radians(az)) * math.cos(e), math.sin(e)))
            sun.rotation_euler = (-to_sun).to_track_quat("-Z", "Y").to_euler()
            sc.render.filepath = os.path.join(OUT, "sun", f"sun_{az}_{alt:+.1f}.webp".replace("+", "p").replace("-", "m"))
            bpy.ops.render.render(write_still=True); print("RENDERED sun", az, alt, flush=True)
    sc.render.resolution_percentage = 100
sun.hide_render = True

json.dump({"az": [AZ0, AZ1], "alt": [ALT0, ALT1], "pxPerDeg": PXD, "cameraHeight": CAMH, "inukshukBearing": INUK_BEARING,
           "sunAz": SUN_AZ, "sunAlt": SUN_ALT, "sunScale": 0.5},
          open(os.path.join(OUT, "land_meta.json"), "w"), indent=1)

# Haze pass: solid emission = 1 - exp(-distance / 14 km), rendered linear to EXR, then moved into the alpha channel
# (a see-through haze material would let far objects' haze leak into near ones)
hz = bpy.data.materials.new("haze"); hz.use_nodes = True
n = hz.node_tree.nodes; l = hz.node_tree.links
for x in list(n): n.remove(x)
camd = n.new("ShaderNodeCameraData"); m1 = n.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; m1.inputs[1].default_value = -1 / 14000
ex = n.new("ShaderNodeMath"); ex.operation = "EXPONENT"; inv = n.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
em = n.new("ShaderNodeEmission"); outm = n.new("ShaderNodeOutputMaterial")
l.new(camd.outputs["View Distance"], m1.inputs[0]); l.new(m1.outputs[0], ex.inputs[0]); l.new(ex.outputs[0], inv.inputs[1])
l.new(inv.outputs[0], em.inputs["Color"]); l.new(em.outputs[0], outm.inputs["Surface"])
for ob in sc.objects:
    if ob.type == "MESH" and ob.name != "sea":
        ob.data.materials.clear(); ob.data.materials.append(hz)
wl.remove(wn["Background"].inputs["Strength"].links[0]); wn["Background"].inputs["Strength"].default_value = 0
sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = 0
sc.cycles.samples = 16
sc.render.image_settings.file_format = "OPEN_EXR"; sc.render.image_settings.color_mode = "RGBA"
tmp = os.path.join(OUT, "_haze.exr"); sc.render.filepath = tmp
if MODE not in ("all", "haze"): sys.exit(0)
bpy.ops.render.render(write_still=True)
src = bpy.data.images.load(tmp); w, h = src.size
px = np.array(src.pixels[:], dtype=np.float32).reshape(h, w, 4)
outpx = np.ones_like(px); outpx[..., 3] = np.clip(px[..., 0], 0, 1) * px[..., 3]
dst = bpy.data.images.new("haze", w, h, alpha=True); dst.pixels = outpx.ravel()
dst.filepath_raw = os.path.join(OUT, "land_haze.webp"); dst.file_format = "WEBP"; dst.save()
os.remove(tmp); print("RENDERED haze", flush=True)
