# Stanley Park and the English Bay shore up to it, exec'd from land.py after fg_ebay.py (uses its helpers).
# Shoreline traced from Google satellite imagery, in metres east (x) / north (y) of the Inukshuk, ordered from
# Lions Gate round Prospect Point, south past Siwash Rock, Third Beach, Ferguson Point and Second Beach, then down
# English Bay Beach to the Inukshuk point. Land lies on the right-hand side of travel.
PARK_SHORE = [(110, 4100), (-140, 3970), (-480, 3930), (-770, 3805), (-935, 3555), (-1030, 3260), (-1095, 2970),
              (-1180, 2675), (-1262, 2425), (-1313, 2175), (-1246, 1925), (-1062, 1715), (-811, 1505), (-619, 1255),
              (-460, 1020), (-309, 795), (-184, 585), (-120, 330), (-60, 200), (-50, 120)]
def park_dist(x, y):
    best = 1e9
    for (ax, ay), (bx, by) in zip(PARK_SHORE, PARK_SHORE[1:]):
        dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
        t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
        d = math.hypot(ax + t * dx - x, ay + t * dy - y)
        if d < abs(best): best = d if dx * (y - ay) - dy * (x - ax) > 0 else -d
    return best
SECOND_BEACH, THIRD_BEACH = (1130, 1380), (2560, 2800)   # y-ranges of the sandy beaches
def park_ground(x, y, d):
    if y < 1050: return min(14, 2.5 + d * 0.08)                     # English Bay Beach and the West End shore
    cliff = smooth(3300, 3700, y)                                    # Siwash Rock to Prospect Point: cliffs
    hill = 3 + d * (0.12 + 0.5 * cliff)
    return min(18 + 42 * cliff + 25 * smooth(200, 700, d), hill)
def zone(x, y, d):
    if y < 1050:
        if d < 45: return "sand"
        if d < 75: return "grass"
        return "city"
    if d < 7: return "seawall"
    if SECOND_BEACH[0] < y < SECOND_BEACH[1] and d < 60: return "sand" if d < 45 else "grass"
    if THIRD_BEACH[0] < y < THIRD_BEACH[1] and d < 35: return "sand"
    if 1050 < y < 1500 and d < 160: return "grass"                  # lawns behind Second Beach
    return "forest"
ZC = {"sand": (0.4, 0.33, 0.24), "grass": (0.07, 0.09, 0.035), "seawall": (0.42, 0.4, 0.37), "city": (0.1, 0.1, 0.1), "forest": (0.02, 0.03, 0.02)}

def heightfield(x0, x1, y0, y1, step):
    bm = bmesh.new(); col = bm.loops.layers.color.new("Col"); vs, cs = {}, {}
    nx, ny = int((x1 - x0) / step), int((y1 - y0) / step)
    for i in range(nx + 1):
        for j in range(ny + 1):
            x, y = x0 + i * step, y0 + j * step
            d = park_dist(x, y)
            if d < -step * 1.5: continue
            z = park_ground(x, y, max(d, 0)) if d > 0 else -1.0
            zn = zone(x, y, max(d, 0))
            if zn == "forest" and d > 320: z += 38 * smooth(320, 420, d)   # canopy cap where the trees end
            vs[i, j] = bm.verts.new(W(x, y, z)); cs[i, j] = ZC[zn]
    for i in range(nx):
        for j in range(ny):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if all(k in vs for k in q):
                f = bm.faces.new([vs[k] for k in q])
                for lp, k in zip(f.loops, q): lp[col] = (*cs[k], 1)
    me = bpy.data.meshes.new("parkland"); bm.to_mesh(me); bm.free()
    me.materials.append(bpy.data.materials["ground"]); link(bpy.data.objects.new("parkland", me))
    for p in me.polygons: p.use_smooth = True
heightfield(-330, 150, 180, 1060, 4)      # English Bay Beach up to Second Beach, fine cells (closer)
heightfield(-1400, 700, 1040, 4200, 12)   # the park

# ---------- trees: one merged mesh of conifers (Douglas fir, cedar) and broadleaf (bigleaf maple, some turning in October) ----------
def tree_mat(n, l, b):
    vc = n.new("ShaderNodeVertexColor"); vc.layer_name = "Tint"
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.35; nz.inputs["Detail"].default_value = 6
    mul = n.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs[0].default_value = 0.45
    l.new(vc.outputs["Color"], mul.inputs[6]); l.new(nz.outputs["Color"], mul.inputs[7]); l.new(mul.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 1.0
    bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.6; l.new(nz.outputs["Fac"], bp.inputs["Height"]); l.new(bp.outputs["Normal"], b.inputs["Normal"])
bm = bmesh.new(); tint = bm.loops.layers.color.new("Tint")
def add_cone(cx, cy, z0, r, h, sides, c):
    ring = [bm.verts.new(W(cx + math.cos(a) * r * random.uniform(.85, 1.15), cy + math.sin(a) * r * random.uniform(.85, 1.15), z0))
            for a in [k * 2 * math.pi / sides + random.random() * .3 for k in range(sides)]]
    top = bm.verts.new(W(cx + random.uniform(-.6, .6), cy + random.uniform(-.6, .6), z0 + h))
    for k in range(sides):
        f = bm.faces.new((ring[k], ring[(k + 1) % sides], top))
        for lp in f.loops: lp[tint] = c
def add_blob(cx, cy, z0, r, c):
    g = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
    for v in g["verts"]:
        v.co = Vector(W(cx, cy, z0)) + Vector((v.co.x * random.uniform(.85, 1.15), v.co.y * random.uniform(.85, 1.15), v.co.z * .75))
    for f in {f for v in g["verts"] for f in v.link_faces}:
        for lp in f.loops: lp[tint] = c
random.seed(11); count = 0
SP = 8.5
for gx in range(int(-1400 / SP), int(700 / SP)):
    for gy in range(int(1040 / SP), int(4200 / SP)):
        x, y = gx * SP + random.uniform(-3, 3), gy * SP + random.uniform(-3, 3)
        d = park_dist(x, y)
        if d < 12 or d > 380: continue
        zn = zone(x, y, d)
        if zn != "forest" and not (zn == "grass" and random.random() < 0.08): continue
        z0 = park_ground(x, y, d)
        if random.random() < 0.72:   # conifer: two or three tiers
            h = random.uniform(32, 58) * (1.15 if d > 60 else 0.9); r = h * random.uniform(.14, .19)
            c = (random.uniform(.016, .03), random.uniform(.032, .05), random.uniform(.026, .04), 1)
            add_cone(x, y, z0 + h * .12, r, h * .55, 7, c)
            add_cone(x, y, z0 + h * .45, r * .72, h * .55, 7, c)
        else:                         # broadleaf crown; a quarter of them in autumn colour
            h = random.uniform(18, 30); r = random.uniform(5, 8.5)
            c = (random.uniform(.18, .3), random.uniform(.1, .16), .02, 1) if random.random() < .28 else (random.uniform(.035, .05), random.uniform(.06, .08), .025, 1)
            add_blob(x, y, z0 + h * .62, r, c)
        count += 1
# a row of big street trees along Beach Avenue behind English Bay Beach
for k in range(40):
    y = 230 + k * 20 + random.uniform(-4, 4)
    for x in range(-330, 150, 6):
        if 75 < park_dist(x, y) < 81:
            add_blob(x + random.uniform(-2, 2), y, park_ground(x, y, 78) + 14, random.uniform(5.5, 7.5), (0.04, 0.065, 0.025, 1)); break
me = bpy.data.meshes.new("parktrees"); bm.to_mesh(me); bm.free()
me.materials.append(shader("parktrees", tree_mat)); link(bpy.data.objects.new("parktrees", me))
print("PARK TREES", count, flush=True)

# West End buildings behind Beach Avenue (low-rise near the water, towers further in)
tower = bpy.data.materials["tower"] if "tower" in bpy.data.materials else material("tower", (0.12, 0.12, 0.13), 0.5)
for k in range(70):
    x, y = random.uniform(-280, 400), random.uniform(260, 1050)
    d = park_dist(x, y)
    if d < 95: continue
    h = random.uniform(12, 30) if d < 180 else random.uniform(30, 85)
    w = random.uniform(16, 28)
    box(W(x, y, park_ground(x, y, d) + h / 2), (w, w * random.uniform(.7, 1.3), h), random.uniform(0, 1.5), tower)

# Siwash Rock: the sea stack off the park's west shore, with its lone tree
bpy.ops.mesh.primitive_cylinder_add(vertices=14, radius=7, depth=16, location=W(-1078, 3268, 7))
sr = bpy.context.object; sr.scale = (1.0, 0.8, 1.0); sr.data.materials.append(granite)
dm = sr.modifiers.new("d", "DISPLACE"); tx = bpy.data.textures.new("siwash", "CLOUDS"); tx.noise_scale = 3; dm.texture = tx; dm.strength = 2.5
bm = bmesh.new(); tint = bm.loops.layers.color.new("Tint"); add_cone(-1078, 3268, 15, 2.5, 9, 7, (0.02, 0.04, 0.03, 1))
me = bpy.data.meshes.new("siwashtree"); bm.to_mesh(me); bm.free(); me.materials.append(bpy.data.materials["parktrees"]); link(bpy.data.objects.new("siwashtree", me))
