# The West End and Coal Harbour, exec'd from land.py after sp_ebay.py: every building in frame extruded from its surveyed
# footprint (City of Vancouver 2009 LiDAR footprints, plus OpenStreetMap towers built since) and every public tree at its
# recorded position and height. Run city.py first; it writes blender/cache/city.json in metres from the camera.
from mathutils import Matrix, Vector, noise
CITY = json.load(open(os.path.join(os.path.dirname(__file__), "cache", "city.json")))
def sag(x, y): return (1 - 0.13) * (x * x + y * y) / (2 * 6371000.0)   # curvature less refraction, as for the terrain

FACADES = [(0.30, 0.29, 0.27), (0.36, 0.32, 0.26), (0.24, 0.22, 0.20), (0.26, 0.13, 0.09), (0.42, 0.41, 0.38)]
GLASS = [(0.07, 0.10, 0.11), (0.10, 0.13, 0.14), (0.06, 0.08, 0.10)]
random.seed(21)
bm = bmesh.new(); tint = bm.loops.layers.color.new("Tint"); gl = bm.faces.layers.int.new("glass")
count = 0
for b in CITY["buildings"]:
    ring = b["ring"]; h = b["top"] - b["base"]
    glassy = h > 40 and random.random() < 0.6
    col = (*random.choice(GLASS if glassy else FACADES), 1)
    lo = [bm.verts.new((x, y, b["base"] - 3 - sag(x, y))) for x, y in ring]
    hi = [bm.verts.new((x, y, b["top"] - sag(x, y))) for x, y in ring]
    faces = []
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        try: faces.append(bm.faces.new((lo[i], lo[j], hi[j], hi[i])))
        except ValueError: pass
    try: faces.append(bm.faces.new(hi))
    except ValueError: pass
    for f in faces:
        f[gl] = int(glassy)
        for lp in f.loops: lp[tint] = col
    count += 1
me = bpy.data.meshes.new("city"); bm.to_mesh(me); bm.free()
def facade_mat(n, l, b):
    vc = n.new("ShaderNodeVertexColor"); vc.layer_name = "Tint"; l.new(vc.outputs["Color"], b.inputs["Base Color"])
    at = n.new("ShaderNodeAttribute"); at.attribute_type = "GEOMETRY"; at.attribute_name = "glass"
    rr = n.new("ShaderNodeMapRange"); rr.inputs["To Min"].default_value = 0.75; rr.inputs["To Max"].default_value = 0.18
    l.new(at.outputs["Fac"], rr.inputs["Value"]); l.new(rr.outputs["Result"], b.inputs["Roughness"])   # glass towers catch the low sun
me.materials.append(shader("facades", facade_mat)); link(bpy.data.objects.new("city", me))
print("CITY buildings", count, flush=True)

# trees: rounded crowns; a share of the broadleaf street trees in autumn colour, as in the park
bm = bmesh.new(); tint = bm.loops.layers.color.new("Tint")
def hand_ground(x, y, z):   # inside the hand-built beach and park, stand on their ground rather than the interpolated city
    X, Y = x - SX, y - SY
    if -70 <= X <= 120 and -150 <= Y <= 220: return ground_z(X, Y)[0]
    if (-330 <= X <= 150 and 180 <= Y <= 1060) or (-1400 <= X <= 700 and 1040 <= Y <= 4200): return park_ground(X, Y, max(park_dist(X, Y), 0))
    return z
for x, y, z, h in CITY["trees"]:
    z = hand_ground(x, y, z)
    r = max(1.6, h * 0.3)
    if math.hypot(x, y) < 600:   # trunks where they can be seen
        cb = z + h - r * 1.6
        if cb > z + 1:
            tw = max(.25, h * .018)
            ring = [bm.verts.new((x + math.cos(k * 1.047) * tw, y + math.sin(k * 1.047) * tw, z - 1)) for k in range(6)]
            top = [bm.verts.new((x + math.cos(k * 1.047) * tw * .7, y + math.sin(k * 1.047) * tw * .7, cb)) for k in range(6)]
            for k in range(6):
                f = bm.faces.new((ring[k], ring[(k + 1) % 6], top[(k + 1) % 6], top[k]))
                for lp in f.loops: lp[tint] = (.05, .04, .03, 1)
    autumn = random.random() < 0.28
    c = (random.uniform(.18, .3), random.uniform(.1, .16), .02, 1) if autumn else (random.uniform(.03, .05), random.uniform(.055, .08), .025, 1)
    m = Matrix.Translation((x, y, z + h - r * 0.9 - sag(x, y))) @ Matrix.Diagonal((random.uniform(.9, 1.1), random.uniform(.9, 1.1), .85, 1))
    d = math.hypot(x, y)   # finer, lumpier crowns close to the camera
    g = bmesh.ops.create_icosphere(bm, subdivisions=3 if d < 350 else 2 if d < 900 else 1, radius=r, matrix=m)
    if d < 900:
        ctr = m.to_translation()
        for v in g["verts"]: v.co = ctr + (v.co - ctr) * (0.82 + 0.3 * noise.noise(v.co * 0.35 + Vector((x, y, 0))) + 0.08 * random.random())
    for f in {f for v in g["verts"] for f in v.link_faces}:
        for lp in f.loops: lp[tint] = c
me = bpy.data.meshes.new("citytrees"); bm.to_mesh(me); bm.free()
me.materials.append(bpy.data.materials["parktrees"]); link(bpy.data.objects.new("citytrees", me))
print("CITY trees", len(CITY["trees"]), flush=True)
