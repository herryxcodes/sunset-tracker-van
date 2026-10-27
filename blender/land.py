# Builds the fixed scenery seen from above the Inukshuk at English Bay (true compass bearings) and renders two layers:
#   land_shade.webp  lit colour with alpha (terrain, freighters, the Inukshuk and its point, beach)
#   land_haze.webp   white, alpha = aerial-perspective amount by distance (0 near, 1 far)
# World axes: +Y north, +X east, metres. Camera 12 m above the rocks at Rock Balance Point, 68 m south-east of the Inukshuk.
# Usage: Blender -b --factory-startup -P land.py -- OUTDIR PXPERDEG SAMPLES
import bpy, bmesh, math, sys, os, json, random

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, PXD, SAMPLES = argv[0], float(argv[1]), int(argv[2])
AZ0, AZ1, ALT0, ALT1 = 200.0, 400.0, -16.0, 8.0   # bearings past 360 wrap to the north-east
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

# Ridges: angular profile from sea level (bearing, elevation deg) as surveyed from Sunset Beach, distance, depth,
# tree spikes, and the bearing shift for this viewpoint ~0.5 km to the north-west
RIDGES = [
    ("Vancouver Island", 80000, 9000, 0, -0.3, [[244,0],[250,.12],[256,.28],[262,.4],[266,.56],[268,.6],[271,.42],[278,.36],[286,.3],[296,.26],[304,.2],[310,0]]),
    ("Bowen Island", 20000, 3000, 12, -1.0, [[286,0],[289,.35],[293,.9],[297,1.5],[300,1.95],[303,2.1],[306,1.75],[309,1.3],[313,1.1],[318,1.3]]),
    # North Shore from Lighthouse Park up to Black Mountain, Hollyburn and Strachan, then Crown and Grouse (peak bearings measured from this spot)
    ("North Shore", 13000, 3500, 25, 0.0, [[299,0],[300.5,.4],[304,.7],[308,1.1],[312,1.6],[316,2.2],[320,2.9],[324,3.6],[328,4.5],[331,5.3],[334.5,6.0],
        [337,5.6],[340,5.5],[343.4,5.6],[344.7,6.0],[347,5.0],[349,4.5],[352,4.4],[355,4.6],[358,4.9],[362,5.2],[366,5.5],[370,5.8],[374.6,6.0],[378,5.6],[383,6.1],[386,5.6],[390,5.0],[395,4.4],[400,3.9]]),
    ("The Lions", 19500, 1500, 0, 0.0, [[346,4.0],[348.6,4.6],[349.5,5.15],[350.0,4.9],[350.5,4.95],[350.9,5.2],[351.8,4.7],[354,4.0]]),
    ("Point Grey", 8000, 1500, 35, -3.5, [[196,.95],[205,.95],[214,.9],[220,.75],[226,.6],[233,.55],[240,.68],[247,.8],[254,.76],[259,.62],[262,.42],[264.5,.15],[266,0]]),
    ("Stanley Park", 1300, 400, 45, 0.0, [[314,0],[316,1.4],[320,2.4],[325,2.9],[331,3.1],[338,3.0],[346,3.2],[354,3.4],[362,3.3],[372,3.0]]),
]
def prof(pts, a):
    if a <= pts[0][0] or a >= pts[-1][0]: return 0.0
    for (a0, h0), (a1, h1) in zip(pts, pts[1:]):
        if a <= a1: return h0 + (h1 - h0) * (a - a0) / (a1 - a0)
    return 0.0

forest = material("forest", (0.012, 0.02, 0.016), 1.0)
far = material("farhill", (0.03, 0.038, 0.04), 0.95, 0.3, 0.004)
for name, D, depth, tree, shift, pts in RIDGES:
    pts = [[a + shift, h] for a, h in pts]
    a0, a1 = pts[0][0], pts[-1][0]
    step = max(0.03, D / 2000000 * 3)  # finer columns for nearer ridges
    cols = int((a1 - a0) / step) + 1
    rows = [-1.0, -0.6, -0.25, 0.0, 0.35, 1.0]  # fraction of depth, 0 = crest line
    bm = bmesh.new(); grid = []
    phase = random.random() * 100
    for ci in range(cols):
        a = a0 + ci * step
        H = H0 = D * math.tan(math.radians(prof(pts, a)))
        if tree and H > 0:  # conifer skyline: irregular spikes on the crest only
            k = (a * D * 0.01745 / 26.0 + phase)
            spike = 1 - abs((k % 1) - 0.5) * 2
            H += tree * (0.55 + 0.45 * math.sin(a * 37.1 + phase) * math.sin(a * 13.7)) * spike ** 1.3
        sx, sy = bdir(a); col = []
        for f in rows:
            r = D + f * depth
            base = H if f >= 0 else H0 + (H - H0) * 0.15
            z = -2 if f == -1.0 else base * (1 - abs(f) ** 1.6 * (1.0 if f < 0 else 0.35))
            col.append(bm.verts.new((sx * r, sy * r, z)))
        grid.append(col)
    for ci in range(cols - 1):
        for ri in range(len(rows) - 1):
            bm.faces.new((grid[ci][ri], grid[ci + 1][ri], grid[ci + 1][ri + 1], grid[ci][ri + 1]))
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    me.materials.append(far if D > 15000 else forest)
    for p in me.polygons: p.use_smooth = True

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

# Daylight to shade the scenery: sun low in the WSW (backlit, as it is all afternoon from this beach)
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
wn = world.node_tree.nodes; wl = world.node_tree.links
sky = wn.new("ShaderNodeTexSky"); sky.sky_type = "MULTIPLE_SCATTERING"; sky.sun_disc = True
sky.sun_elevation = math.radians(22); sky.sun_rotation = math.radians(110); sky.aerosol_density = 1.25
wl.new(sky.outputs["Color"], wn["Background"].inputs["Color"])
sc.view_settings.exposure = -4.6
sc.render.filepath = os.path.join(OUT, "land_shade.webp")
bpy.ops.render.render(write_still=True); print("RENDERED shade", flush=True)

# Haze pass: emission = 1 - exp(-distance / 14 km)
hz = bpy.data.materials.new("haze"); hz.use_nodes = True
n = hz.node_tree.nodes; l = hz.node_tree.links
for x in list(n): n.remove(x)
camd = n.new("ShaderNodeCameraData"); m1 = n.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; m1.inputs[1].default_value = -1 / 14000
ex = n.new("ShaderNodeMath"); ex.operation = "EXPONENT"; inv = n.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
em = n.new("ShaderNodeEmission"); outm = n.new("ShaderNodeOutputMaterial")
l.new(camd.outputs["View Distance"], m1.inputs[0]); l.new(m1.outputs[0], ex.inputs[0]); l.new(ex.outputs[0], inv.inputs[1])
em.inputs["Color"].default_value = (1, 1, 1, 1)
tr = n.new("ShaderNodeBsdfTransparent"); mx = n.new("ShaderNodeMixShader")  # alpha = haze amount
l.new(inv.outputs[0], mx.inputs[0]); l.new(tr.outputs[0], mx.inputs[1]); l.new(em.outputs[0], mx.inputs[2])
l.new(mx.outputs[0], outm.inputs["Surface"])
for ob in sc.objects:
    if ob.type == "MESH":
        ob.data.materials.clear(); ob.data.materials.append(hz)
wn["Background"].inputs["Strength"].default_value = 0
sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = 0
sc.cycles.samples = 16
sc.render.filepath = os.path.join(OUT, "land_haze.webp")
bpy.ops.render.render(write_still=True); print("RENDERED haze", flush=True)
json.dump({"az": [AZ0, AZ1], "alt": [ALT0, ALT1], "pxPerDeg": PXD, "cameraHeight": CAMH, "inukshukBearing": INUK_BEARING},
          open(os.path.join(OUT, "land_meta.json"), "w"), indent=1)
