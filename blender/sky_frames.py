# Renders the sky + English Bay water as seen from above the Inukshuk at English Bay, one frame per sun altitude.
# Frames are in sun-relative azimuth (sun at rel 0) so the page can slide them to the true bearing.
# The sea curves away (Earth's curvature less refraction, k = 0.13), so its horizon dips 0.10 deg below level as seen from 12 m.
# AEROSOL is the sky model's aerosol density: the page keeps one set per air-quality band (clean 0.5, typical 1.25, hazy 3).
# Usage: Blender -b --factory-startup -P sky_frames.py -- OUTDIR PXPERDEG SAMPLES ALT[,ALT...] [AEROSOL] [disc]
import bpy, math, sys, json, os
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, PXD, SAMPLES = argv[0], float(argv[1]), int(argv[2])
ALTS = [float(a) for a in argv[3].split(",")]
DISC = "disc" in argv[4:]
AEROSOL = next((float(a) for a in argv[4:] if a != "disc"), 1.25)
CAM_H, K_REFR = 12.0, 0.13
REL0, REL1, ALT0, ALT1 = -100.0, 140.0, -16.0, 30.0  # sun-relative azimuth and altitude range (deg)

os.makedirs(OUT, exist_ok=True)
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "METAL"; prefs.get_devices()
for d in prefs.devices: d.use = d.type == "METAL"
sc.cycles.device = "GPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4
sc.render.resolution_x = round((REL1 - REL0) * PXD)
sc.render.resolution_y = round((ALT1 - ALT0) * PXD)
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 88
sc.view_settings.view_transform = "AgX"
try: sc.view_settings.look = "AgX - Punchy"
except Exception: pass

# Camera: 12 m above the water (drone height over the Inukshuk point), equirectangular strip. Looks along +Y (the sun's bearing).
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "PANO"
cam_data.panorama_type = "EQUIRECTANGULAR"
cam_data.longitude_min = math.radians(REL0); cam_data.longitude_max = math.radians(REL1)
cam_data.latitude_min = math.radians(ALT0); cam_data.latitude_max = math.radians(ALT1)
cam_data.clip_end = 300000  # see the water all the way to the horizon
cam = bpy.data.objects.new("cam", cam_data)
cam.location = (0, 0, CAM_H)
cam.rotation_euler = (math.radians(90), 0, 0)
sc.collection.objects.link(cam); sc.camera = cam

# Water: a curved disc out past the horizon (polar grid, finer near the camera) with layered ripples, dark green-blue like English Bay.
pa = np.radians(np.arange(0, 360, 1.0)); pd = np.concatenate([[0.0], np.geomspace(2, 120000, 220)])
gb, gd = np.meshgrid(pa, pd, indexing="ij")
co = np.stack([gd * np.sin(gb), gd * np.cos(gb), -(1 - K_REFR) * gd * gd / (2 * 6371000.0)], -1).reshape(-1, 3)
na, nd = gb.shape
ii, jj = np.meshgrid(np.arange(na), np.arange(nd - 1), indexing="ij")
faces = np.stack([ii * nd + jj, (ii + 1) % na * nd + jj, (ii + 1) % na * nd + jj + 1, ii * nd + jj + 1], -1).reshape(-1, 4)
wm = bpy.data.meshes.new("water"); wm.from_pydata(co.tolist(), [], faces.tolist())
for p in wm.polygons: p.use_smooth = True
water = bpy.data.objects.new("water", wm); sc.collection.objects.link(water)
mat = bpy.data.materials.new("water"); mat.use_nodes = True
nt = mat.node_tree; N = nt.nodes; Lk = nt.links
bsdf = N["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.006, 0.016, 0.022, 1)
bsdf.inputs["Roughness"].default_value = 0.06
bsdf.inputs["IOR"].default_value = 1.333
tc = N.new("ShaderNodeTexCoord")
mp = N.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.35, 1.0, 1.0)
w1 = N.new("ShaderNodeTexNoise"); w1.inputs["Scale"].default_value = 0.6; w1.inputs["Detail"].default_value = 6; w1.inputs["Roughness"].default_value = 0.6
w2 = N.new("ShaderNodeTexWave"); w2.inputs["Scale"].default_value = 0.08; w2.inputs["Distortion"].default_value = 6; w2.inputs["Detail"].default_value = 4
add = N.new("ShaderNodeMath"); add.operation = "ADD"
bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.35; bump.inputs["Distance"].default_value = 0.08
Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
Lk.new(mp.outputs["Vector"], w1.inputs["Vector"]); Lk.new(mp.outputs["Vector"], w2.inputs["Vector"])
Lk.new(w1.outputs["Fac"], add.inputs[0]); Lk.new(w2.outputs["Fac"], add.inputs[1])
Lk.new(add.outputs["Value"], bump.inputs["Height"]); Lk.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
water.data.materials.append(mat)

# Sky
world = bpy.data.worlds.new("sky"); sc.world = world; world.use_nodes = True
wn = world.node_tree.nodes; wl = world.node_tree.links
sky = wn.new("ShaderNodeTexSky")
sky.sky_type = "MULTIPLE_SCATTERING"
sky.sun_disc = DISC
sky.altitude = CAM_H   # metres
sky.air_density = 1.0
sky.aerosol_density = AEROSOL
sky.ozone_density = 1.0
sky.sun_rotation = 0.0
wl.new(sky.outputs["Color"], wn["Background"].inputs["Color"])

def EV(alt):
    pts = [(-14, 3.4), (-9, 2.6), (-6, 1.6), (-3, 0.2), (0, -2.2), (3, -3.6), (8, -4.4), (15, -5.0), (30, -5.3)]
    if alt <= pts[0][0]: return pts[0][1]
    for (a0, e0), (a1, e1) in zip(pts, pts[1:]):
        if alt <= a1: return e0 + (e1 - e0) * (alt - a0) / (a1 - a0)
    return pts[-1][1]

meta = {}
for alt in ALTS:
    sky.sun_elevation = math.radians(alt)
    # Auto-exposure like a camera operator riding the iris through dusk
    ev = EV(alt)
    sc.view_settings.exposure = ev
    name = f"sky_{alt:+.1f}.jpg".replace("+", "p").replace("-", "m")
    sc.render.filepath = os.path.join(OUT, name)
    bpy.ops.render.render(write_still=True)
    meta[name] = {"alt": alt, "exposure": ev}
    print("RENDERED", name, flush=True)
json.dump({"rel": [REL0, REL1], "alt": [ALT0, ALT1], "pxPerDeg": PXD, "aerosol": AEROSOL, "frames": meta},
          open(os.path.join(OUT, "sky_meta.json"), "w"), indent=1)
