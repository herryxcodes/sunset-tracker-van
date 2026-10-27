# Renders volumetric cloud sprites for the page to scatter over each cloud deck and light live:
#   18 broad cloud masses (8 stratocumulus slabs for the low deck, 6 altocumulus sheets for the mid deck, 4 feathery patches
#   for the high deck), each a box of procedural density (flattened lobes eroded by noise into ragged edges and holes,
#   flat base, thin enough at the edges for the sun to glow through) in Cycles.
# Every cloud is rendered under four lights, saved as opaque colour atlases the page tints and adds up, plus one alpha atlas:
#   cloud_amb.jpg    skylight only (bright dome above, dark sea below)
#   cloud_back.jpg   sun low behind the cloud, toward the camera: silver linings, glow through thin parts
#   cloud_front.jpg  sun low behind the camera
#   cloud_below.jpg  sun just under the cloud's horizon, lighting the base from below (after sunset)
#   cloud_alpha.webp white, alpha = coverage
#   clouds.json      where each sprite sits in the atlases and where its base is
# Usage: Blender -b --factory-startup -P clouds.py -- OUTDIR
import bpy, sys, os, json, math, random
import numpy as np

OUT = sys.argv[sys.argv.index("--") + 1:][0]
os.makedirs(OUT, exist_ok=True)
CW, CH, COLS = 512, 128, 4          # sprite cell size (px, a 4 x 1 unit frame), atlas columns
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"; prefs.get_devices()
for d in prefs.devices: d.use = d.type == "METAL"
sc.cycles.device = "GPU"; sc.cycles.samples = 64; sc.cycles.use_denoising = True
sc.cycles.volume_bounces = 6; sc.cycles.max_bounces = 8; sc.cycles.transparent_max_bounces = 8
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = CW, CH, 100
sc.render.image_settings.file_format = "OPEN_EXR"; sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"

# camera: orthographic, looking north (+Y) at a 4 x 1 unit frame; cloud bases sit at z = 0, a little above the frame bottom
BASE_Y = 0.2                         # fraction of the frame height below the base (room for the eroded underside)
cd = bpy.data.cameras.new("c"); cd.type = "ORTHO"; cd.ortho_scale = 4.0
cam = bpy.data.objects.new("c", cd); cam.location = (0, -10, 0.5 - BASE_Y); cam.rotation_euler = (math.radians(90), 0, 0)
sc.collection.objects.link(cam); sc.camera = cam

world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
wn, wl = world.node_tree.nodes, world.node_tree.links
tco = wn.new("ShaderNodeTexCoord"); sep = wn.new("ShaderNodeSeparateXYZ"); mr = wn.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = -0.3; mr.inputs["From Max"].default_value = 0.6
mr.inputs["To Min"].default_value = 0.12; mr.inputs["To Max"].default_value = 1.0
wl.new(tco.outputs["Generated"], sep.inputs[0]); wl.new(sep.outputs["Z"], mr.inputs["Value"])
wl.new(mr.outputs["Result"], wn["Background"].inputs["Strength"])

sun_d = bpy.data.lights.new("sun", "SUN"); sun_d.energy = 3.2; sun_d.angle = math.radians(0.53)
sun = bpy.data.objects.new("sun", sun_d); sc.collection.objects.link(sun)
def aim(travel):                     # point the sun along a travel direction (x, y, z)
    from mathutils import Vector
    sun.rotation_euler = Vector(travel).normalized().to_track_quat("-Z", "Y").to_euler()
LIGHTS = {"amb": None, "back": (0, -1, -0.09), "front": (0, 1, -0.17), "below": (0, -1, 0.14)}
ENERGY = {"back": 3.2, "front": 8.0, "below": 4.0}   # sun strength per pass, so each fills the 8-bit range

bpy.ops.mesh.primitive_cube_add(size=1); box = bpy.context.object
box.scale = (4.0, 2.0, 1.0); box.location = (0, 0, 0.3)

def cloud_material(blobs, base_soft, erode, dens_scale, seed):
    m = bpy.data.materials.new("cloud"); m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    for x in list(n): n.remove(x)
    out = n.new("ShaderNodeOutputMaterial"); tc = n.new("ShaderNodeTexCoord")
    vol = n.new("ShaderNodeVolumePrincipled"); vol.inputs["Color"].default_value = (1, 1, 1, 1)
    vol.inputs["Anisotropy"].default_value = 0.35
    # wobble the lookup point so the lobes are not perfect spheres
    wob = n.new("ShaderNodeTexNoise"); wob.noise_dimensions = "4D"; wob.inputs["Scale"].default_value = 3.0; wob.inputs["Detail"].default_value = 3
    wob.inputs["W"].default_value = seed; l.new(tc.outputs["Object"], wob.inputs["Vector"])
    wc = n.new("ShaderNodeVectorMath"); wc.operation = "SUBTRACT"; wc.inputs[1].default_value = (0.5, 0.5, 0.5)
    l.new(wob.outputs["Color"], wc.inputs[0])
    ws = n.new("ShaderNodeVectorMath"); ws.operation = "SCALE"; ws.inputs["Scale"].default_value = 0.12; l.new(wc.outputs[0], ws.inputs[0])
    gp = n.new("ShaderNodeVectorMath"); gp.operation = "ADD"; l.new(tc.outputs["Object"], gp.inputs[0]); l.new(ws.outputs[0], gp.inputs[1])
    # p is in the cube's object space (unit cube); convert to frame units
    sp = n.new("ShaderNodeVectorMath"); sp.operation = "MULTIPLY"; sp.inputs[1].default_value = tuple(box.scale)
    l.new(gp.outputs[0], sp.inputs[0])
    off = n.new("ShaderNodeVectorMath"); off.operation = "ADD"; off.inputs[1].default_value = (0, 0, box.location.z)
    l.new(sp.outputs[0], off.inputs[0]); p = off.outputs[0]
    shape = None
    for cx, cy, cz, r in blobs:     # union of soft blobs: max(1 - |p - c| / r)
        d = n.new("ShaderNodeVectorMath"); d.operation = "DISTANCE"; d.inputs[1].default_value = (cx, cy, cz); l.new(p, d.inputs[0])
        f = n.new("ShaderNodeMath"); f.operation = "DIVIDE"; f.inputs[1].default_value = r; l.new(d.outputs["Value"], f.inputs[0])
        g = n.new("ShaderNodeMath"); g.operation = "SUBTRACT"; g.inputs[0].default_value = 1.0; l.new(f.outputs[0], g.inputs[1])
        if shape is None: shape = g.outputs[0]
        else:
            mx = n.new("ShaderNodeMath"); mx.operation = "MAXIMUM"; l.new(shape, mx.inputs[0]); l.new(g.outputs[0], mx.inputs[1]); shape = mx.outputs[0]
    # cauliflower erosion: billowy noise eats into the edges more than the core
    fb = n.new("ShaderNodeTexNoise"); fb.noise_dimensions = "4D"; fb.inputs["Scale"].default_value = 9.0; fb.inputs["Detail"].default_value = 8
    fb.inputs["Roughness"].default_value = 0.55; fb.inputs["W"].default_value = seed + 7
    l.new(p, fb.inputs["Vector"])
    er = n.new("ShaderNodeMath"); er.operation = "MULTIPLY_ADD"; er.inputs[1].default_value = erode; er.inputs[2].default_value = -erode * 0.62
    l.new(fb.outputs["Fac"], er.inputs[0])
    sh = n.new("ShaderNodeMath"); sh.operation = "ADD"; l.new(shape, sh.inputs[0]); l.new(er.outputs[0], sh.inputs[1])
    dn = n.new("ShaderNodeMapRange"); dn.interpolation_type = "SMOOTHSTEP"
    dn.inputs["From Min"].default_value = 0.0; dn.inputs["From Max"].default_value = 0.3; l.new(sh.outputs[0], dn.inputs["Value"])
    # flat, slightly ragged base at z = 0
    sz = n.new("ShaderNodeSeparateXYZ"); l.new(p, sz.inputs[0])
    bs = n.new("ShaderNodeMapRange"); bs.interpolation_type = "SMOOTHSTEP"
    bs.inputs["From Min"].default_value = -base_soft; bs.inputs["From Max"].default_value = base_soft
    l.new(sz.outputs["Z"], bs.inputs["Value"])
    m1 = n.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; l.new(dn.outputs["Result"], m1.inputs[0]); l.new(bs.outputs["Result"], m1.inputs[1])
    m2 = n.new("ShaderNodeMath"); m2.operation = "MULTIPLY"; m2.inputs[1].default_value = dens_scale; l.new(m1.outputs[0], m2.inputs[0])
    l.new(m2.outputs[0], vol.inputs["Density"]); l.new(vol.outputs[0], out.inputs["Volume"])
    return m

def heap(R, n_blobs, width, height, flat, rmin, rmax):
    """Blob centres and radii for a cloud: a domed heap of lobes standing on z = 0."""
    out = []
    for k in range(n_blobs):
        x = R.uniform(-width, width)
        dome = math.sqrt(max(0.0, 1 - (x / (width * 1.15)) ** 2))
        r = R.uniform(rmin, rmax) * (0.6 + 0.6 * dome)
        z = r * flat + R.uniform(0, height) * dome
        out.append((x, R.uniform(-0.45, 0.45), z, r))
    return out

R = random.Random(11)
SPRITES = []
for i in range(8):   # low: stratocumulus, broad lumpy slabs with breaks
    SPRITES.append(("low", heap(R, 34, R.uniform(1.4, 1.8), R.uniform(.1, .22), .45, .14, .3), .05, 1.1, 20, i))
for i in range(6):   # mid: altocumulus sheets, rows of small rounded elements with holes between
    SPRITES.append(("mid", heap(R, 48, R.uniform(1.5, 1.8), .05, .55, .07, .15), .04, 1.2, 14, 20 + i))
for i in range(4):   # high: thin, feathery patches
    SPRITES.append(("high", heap(R, 44, 1.8, .03, .4, .08, .17), .06, 1.3, 5, 40 + i))

def read_exr(path):
    img = bpy.data.images.load(path); w, h = img.size
    a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(img); os.remove(path); return a

rows = math.ceil(len(SPRITES) / COLS)
atl = {k: np.zeros((rows * CH, COLS * CW, 3), np.float32) for k in LIGHTS}
alpha = np.zeros((rows * CH, COLS * CW), np.float32)
meta = []
for idx, (kind, blobs, base_soft, erode, dens, seed) in enumerate(SPRITES):
    box.data.materials.clear(); box.data.materials.append(cloud_material(blobs, base_soft, erode, dens, seed))
    r0, c0 = (idx // COLS) * CH, (idx % COLS) * CW
    for key, travel in LIGHTS.items():
        sun.hide_render = travel is None   # skylight alone, or the sun alone in a black sky
        wn["Background"].inputs["Color"].default_value = (1, 1, 1, 1) if travel is None else (0, 0, 0, 1)
        if travel: aim(travel); sun_d.energy = ENERGY[key]
        sc.render.filepath = os.path.join(OUT, "_tmp.exr"); bpy.ops.render.render(write_still=True)
        px = read_exr(os.path.join(OUT, "_tmp.exr"))
        a = np.clip(px[..., 3], 0, 1)
        col = px[..., :3] / np.maximum(a[..., None], 1e-3)      # straight (unpremultiplied) colour
        if key == "amb": alpha[r0:r0 + CH, c0:c0 + CW] = a
        atl[key][r0:r0 + CH, c0:c0 + CW] = np.where(a[..., None] > 0.02, col, 0)
    print("RENDERED", kind, idx, flush=True)
    meta.append({"kind": kind, "x": c0, "y": r0, "w": CW, "h": CH, "base": 1 - BASE_Y})

# fill the empty surround of each colour atlas with nearby cloud colour so soft edges never pick up black when scaled
def dilate(col, a, n=24):
    w = (a > 0.02).astype(np.float32)
    c = col * w[..., None]
    for _ in range(n):
        cs = sum(np.roll(np.roll(c, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        ws = sum(np.roll(np.roll(w, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
        fill = (w == 0) & (ws > 0)
        c[fill] = cs[fill] / ws[fill][:, None]; w = np.where(fill, 1.0, w)
    return np.where(w[..., None] > 0, c, col.mean((0, 1)))

def save(arr, name, fmt, rgba=False):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(name, w, h, alpha=True, float_buffer=False)
    if not rgba: arr = np.concatenate([arr, np.ones((h, w, 1), np.float32)], -1)
    img.pixels = np.clip(arr[::-1], 0, 1).ravel()
    img.filepath_raw = os.path.join(OUT, name); img.file_format = fmt
    sc.render.image_settings.quality = 88
    img.save(); bpy.data.images.remove(img)

for k, arr in atl.items():
    lin = dilate(arr, alpha)
    srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0, None), 1 / 2.4) - 0.055)
    save(srgb, f"cloud_{k}.jpg", "JPEG")
save(np.dstack([np.ones_like(alpha)] * 3 + [alpha]), "cloud_alpha.webp", "WEBP", rgba=True)
json.dump({"cell": [CW, CH], "frame": [4.0, 1.0], "sprites": meta}, open(os.path.join(OUT, "clouds.json"), "w"), indent=1)
print("DONE", flush=True)
