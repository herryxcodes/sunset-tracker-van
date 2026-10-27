# English Bay foreground, exec'd from land.py: the Inukshuk (Ilanaaq) on its grassy point, the granite boulder
# revetment with balanced-stone cairns, foam at the waterline, seawall path, benches, rose bed, English Bay Beach
# with its log rows, and the Beach Avenue trees. Shoreline traced from Google satellite imagery
# (statue at 49.284308, -123.1437664). Local frame: metres east (x) / north (y) of the statue.
from mathutils import noise, Vector
SX, SY = bdir(INUK_BEARING); SX, SY = SX * INUK_DIST, SY * INUK_DIST   # statue position, camera at origin
GROUND = 3.5   # grass on the point, metres above the water
SHORE = [(-60, 200), (-50, 120), (-42.5, 70), (-36.7, 50), (-31.7, 28.3), (-30, 15), (-27.5, -1.7), (-22.5, -16.7),
         (-12.5, -28.3), (2.5, -40), (19.2, -53.3), (32.5, -63.3), (40.8, -74.2), (75, -125), (110, -170)]
def shore_dist(x, y):  # signed distance to the water line, positive on land (east side)
    best = 1e9
    for (ax, ay), (bx, by) in zip(SHORE, SHORE[1:]):
        dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
        t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
        d = math.hypot(ax + t * dx - x, ay + t * dy - y)
        if d < abs(best): best = d if dx * (y - ay) - dy * (x - ax) > 0 else -d
    return best
def smooth(a, b, v):
    t = max(0.0, min(1.0, (v - a) / (b - a))); return t * t * (3 - 2 * t)
def W(x, y, z=0.0): return (SX + x, SY + y, z)
def link(o): sc.collection.objects.link(o); return o
def ground_z(x, y):
    d = shore_dist(x, y); beach = smooth(12, 26, y)
    rockz = GROUND * smooth(0, 12, d) - 0.6
    sandz = min(GROUND, 0.07 * d)
    return rockz * (1 - beach) + sandz * beach, d, beach

def shader(name, build):
    m = bpy.data.materials.new(name); m.use_nodes = True
    build(m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]); return m

# ---------- ground: lawn, path, mulch, sand (land only: nothing is drawn under the water) ----------
LAWN, PATHC, MULCH, SAND, WETSAND, ROCKBED = 0, 1, 2, 3, 4, 5
PAL = [(0.075, 0.095, 0.035), (0.42, 0.40, 0.37), (0.07, 0.045, 0.03), (0.40, 0.33, 0.24), (0.15, 0.125, 0.095), (0.09, 0.085, 0.08)]
bm = bmesh.new(); STEP = 0.8; X0, Y0, NX, NY = -70, -150, int(190 / 0.8), int(370 / 0.8)
vs, kind = {}, {}
for i in range(NX + 1):
    for j in range(NY + 1):
        x, y = X0 + i * STEP, Y0 + j * STEP
        z, d, beach = ground_z(x, y)
        if d < -0.8: continue
        r = math.hypot(x, y)
        if beach > 0.5: k = WETSAND if d < 6 else SAND
        elif d < 10.5: k = ROCKBED
        elif r < 5.2: k = MULCH
        elif 13.8 < r < 16.6 and x < 4: k = PATHC
        elif 11.2 < d < 14.6 and y < -6: k = PATHC
        else: k = LAWN
        vs[i, j] = bm.verts.new(W(x, y, z)); kind[i, j] = k
col = bm.loops.layers.color.new("Col")
for i in range(NX):
    for j in range(NY):
        q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
        if not all(k in vs for k in q): continue
        f = bm.faces.new([vs[k] for k in q])
        for lp, k in zip(f.loops, q): lp[col] = (*PAL[kind[k]], 1)
me = bpy.data.meshes.new("ground"); bm.to_mesh(me); bm.free()
gobj = link(bpy.data.objects.new("ground", me))
def ground_mat(n, l, b):
    vc = n.new("ShaderNodeVertexColor"); vc.layer_name = "Col"
    big = n.new("ShaderNodeTexNoise"); big.inputs["Scale"].default_value = 0.08; big.inputs["Detail"].default_value = 4
    fine = n.new("ShaderNodeTexNoise"); fine.inputs["Scale"].default_value = 6; fine.inputs["Detail"].default_value = 10
    dry = n.new("ShaderNodeMix"); dry.data_type = "RGBA"; dry.blend_type = "OVERLAY"
    l.new(big.outputs["Fac"], dry.inputs[0]); l.new(vc.outputs["Color"], dry.inputs[6])
    dry.inputs[7].default_value = (0.75, 0.65, 0.35, 1)
    grain = n.new("ShaderNodeMix"); grain.data_type = "RGBA"; grain.blend_type = "MULTIPLY"; grain.inputs[0].default_value = 0.3
    l.new(dry.outputs[2], grain.inputs[6]); l.new(fine.outputs["Color"], grain.inputs[7]); l.new(grain.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.25; l.new(fine.outputs["Fac"], bp.inputs["Height"]); l.new(bp.outputs["Normal"], b.inputs["Normal"])
me.materials.append(shader("ground", ground_mat))
for p in me.polygons: p.use_smooth = True

# ---------- granite boulders: a handful of sculpted variants, instanced ----------
def granite_mat(n, l, b):
    oi = n.new("ShaderNodeObjectInfo"); ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.17, 0.165, 0.16, 1); ramp.color_ramp.elements[1].color = (0.42, 0.39, 0.36, 1)
    e = ramp.color_ramp.elements.new(0.55); e.color = (0.33, 0.29, 0.27, 1)
    l.new(oi.outputs["Random"], ramp.inputs[0])
    vor = n.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 40
    speck = n.new("ShaderNodeMix"); speck.data_type = "RGBA"; speck.blend_type = "MULTIPLY"; speck.inputs[0].default_value = 0.35
    l.new(ramp.outputs["Color"], speck.inputs[6]); l.new(vor.outputs["Color"], speck.inputs[7])
    geo = n.new("ShaderNodeNewGeometry"); sep = n.new("ShaderNodeSeparateXYZ"); l.new(geo.outputs["Position"], sep.inputs[0])
    wet = n.new("ShaderNodeMapRange"); wet.inputs[1].default_value = 0.2; wet.inputs[2].default_value = 1.3
    wet.inputs[3].default_value = 1.0; wet.inputs[4].default_value = 0.0; l.new(sep.outputs["Z"], wet.inputs[0])
    dark = n.new("ShaderNodeMix"); dark.data_type = "RGBA"; dark.blend_type = "MULTIPLY"
    l.new(wet.outputs[0], dark.inputs[0]); l.new(speck.outputs[2], dark.inputs[6]); dark.inputs[7].default_value = (0.35, 0.36, 0.38, 1)
    l.new(dark.outputs[2], b.inputs["Base Color"])
    rough = n.new("ShaderNodeMapRange"); rough.inputs[3].default_value = 0.75; rough.inputs[4].default_value = 0.25
    l.new(wet.outputs[0], rough.inputs[0]); l.new(rough.outputs[0], b.inputs["Roughness"])
    bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.3; l.new(vor.outputs["Distance"], bp.inputs["Height"]); l.new(bp.outputs["Normal"], b.inputs["Normal"])
granite = shader("granite", granite_mat)
ROCKS = []
for v in range(9):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    seed = Vector((v * 13.1, v * 7.7, v * 3.3)); cut = random.uniform(-0.35, -0.1)
    for vt in bm.verts:
        p = vt.co.copy()
        n1 = noise.noise(p * 0.9 + seed) * 0.28 + noise.noise(p * 2.3 + seed) * 0.1 + noise.noise(p * 6 + seed) * 0.03
        vt.co = p * (1 + n1)
        vt.co.x *= 1.25; vt.co.z *= random.uniform(0.62, 0.8)
        if vt.co.z < cut: vt.co.z = cut + (vt.co.z - cut) * 0.15    # flat-ish base where it beds into the slope
    me = bpy.data.meshes.new(f"rock{v}"); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(granite); ROCKS.append(me)
def rock(x, y, z, r, rz=None):
    o = link(bpy.data.objects.new("rock", random.choice(ROCKS)))
    o.location = W(x, y, z); o.scale = (r, r * random.uniform(.75, 1.1), r * random.uniform(.8, 1.1))
    o.rotation_euler = (random.uniform(-.25, .25), random.uniform(-.25, .25), random.uniform(0, 6.3) if rz is None else rz)
    return o
# revetment: walk the shoreline, packing boulders across the band, bigger ones toward the water
for (ax, ay), (bx, by) in zip(SHORE[2:], SHORE[3:]):
    L = math.hypot(bx - ax, by - ay); nxn, nyn = (by - ay) / L, -(bx - ax) / L
    for k in range(int(L / 1.0)):
        t = (k + random.random()) / (L / 1.0)
        for dd in [-1.6 + q * 1.05 for q in range(12)]:
            x = ax + (bx - ax) * t + nxn * (dd + random.uniform(-.45, .45)); y = ay + (by - ay) * t + nyn * dd
            if y > 22 or random.random() < 0.12: continue
            z, d, beach = ground_z(x, y)
            r = random.uniform(.55, .95) * (1.45 - 0.05 * max(dd, 0))
            rock(x, y, max(z, -0.5) + r * 0.15, r)
# balanced-stone cairns on the rocks at Rock Balance Point (the camera's own foreground)
for k in range(26):
    x, y = random.uniform(8, 55), random.uniform(-95, -40)
    z, d, beach = ground_z(x, y)
    if not (0.5 < d < 9): continue
    z += 0.55
    for s in range(random.randint(3, 7)):
        rr = max(0.09, 0.3 - s * 0.035) * random.uniform(.85, 1.15)
        o = rock(x + random.uniform(-.06, .06), y + random.uniform(-.06, .06), z + rr * 0.35, rr)
        o.scale.z = rr * 0.42; z += rr * 0.62

# ---------- foam where the bay meets the rocks ----------
def foam_mat(n, l, b):
    out = n["Material Output"]; nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.9; nz.inputs["Detail"].default_value = 9
    tc = n.new("ShaderNodeTexCoord"); l.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = n.new("ShaderNodeMapRange"); ramp.inputs[1].default_value = 0.52; ramp.inputs[2].default_value = 0.7; l.new(nz.outputs["Fac"], ramp.inputs[0])
    uv = n.new("ShaderNodeAttribute"); uv.attribute_name = "edge"
    m = n.new("ShaderNodeMath"); m.operation = "MULTIPLY"; l.new(ramp.outputs[0], m.inputs[0]); l.new(uv.outputs["Fac"], m.inputs[1])
    b.inputs["Base Color"].default_value = (0.85, 0.88, 0.9, 1); b.inputs["Roughness"].default_value = 0.6
    tr = n.new("ShaderNodeBsdfTransparent"); mx = n.new("ShaderNodeMixShader")
    l.new(m.outputs[0], mx.inputs[0]); l.new(tr.outputs[0], mx.inputs[1]); l.new(b.outputs[0], mx.inputs[2]); l.new(mx.outputs[0], out.inputs["Surface"])
bm = bmesh.new(); edge = bm.verts.layers.float.new("edge"); prev = None
pts = []
for (ax, ay), (bx, by) in zip(SHORE, SHORE[1:]):
    L = math.hypot(bx - ax, by - ay); nxn, nyn = (by - ay) / L, -(bx - ax) / L
    for k in range(int(L / 0.7)):
        t = k / (L / 0.7); pts.append((ax + (bx - ax) * t, ay + (by - ay) * t, nxn, nyn))
for (x, y, nxn, nyn) in pts:
    row = []
    for dd, e in [(0.6, 1.0), (-0.6, 0.9), (-2.2, 0.35), (-3.6, 0.0)]:
        v = bm.verts.new(W(x + nxn * dd, y + nyn * dd, 0.03)); v[edge] = e; row.append(v)
    if prev:
        for q in range(3): bm.faces.new((prev[q], row[q], row[q + 1], prev[q + 1]))
    prev = row
me = bpy.data.meshes.new("foam"); bm.to_mesh(me); bm.free()
me.materials.append(shader("foam", foam_mat)); link(bpy.data.objects.new("foam", me))

# ---------- the Inukshuk: proportions measured from a front-on photo (about 6.3 m), arms broadside to the camera ----------
ux, uy = bdir(INUK_BEARING + 90); yaw = math.atan2(uy, ux)
def stone_mat(n, l, b):
    vor = n.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 30
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.5
    mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.inputs[6].default_value = (0.36, 0.35, 0.33, 1); mx.inputs[7].default_value = (0.24, 0.235, 0.23, 1)
    l.new(nz.outputs["Fac"], mx.inputs[0]); l.new(mx.outputs[2], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = 0.8
    bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.35; l.new(vor.outputs["Distance"], bp.inputs["Height"]); l.new(bp.outputs["Normal"], b.inputs["Normal"])
stone = shader("inukshuk", stone_mat)
def block(w, dpt, h, lx, z0, taper=0.0, tilt=0.0):
    bm = bmesh.new(); t = 1 - taper
    pts = [(-w / 2, -dpt / 2, 0), (w / 2, -dpt / 2, 0), (w / 2, dpt / 2, 0), (-w / 2, dpt / 2, 0),
           (-w / 2 * t, -dpt / 2 * t, h), (w / 2 * t, -dpt / 2 * t, h), (w / 2 * t, dpt / 2 * t, h), (-w / 2 * t, dpt / 2 * t, h)]
    v = [bm.verts.new(p) for p in pts]
    for f in [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]: bm.faces.new([v[i] for i in f])
    me = bpy.data.meshes.new("stone"); bm.to_mesh(me); bm.free()
    o = link(bpy.data.objects.new("stone", me))
    o.location = W(ux * lx, uy * lx, z0); o.rotation_euler = (random.uniform(-.03, .03), tilt, yaw + random.uniform(-.05, .05))
    bv = o.modifiers.new("bevel", "BEVEL"); bv.width = min(w, dpt, h) * 0.16; bv.segments = 3
    sub = o.modifiers.new("sub", "SUBSURF"); sub.levels = sub.render_levels = 2
    tex = bpy.data.textures.new("rough", "CLOUDS"); tex.noise_scale = 0.3
    dp = o.modifiers.new("disp", "DISPLACE"); dp.texture = tex; dp.strength = 0.08
    me.materials.append(stone); return o
z = GROUND + 0.05
block(1.35, 1.0, 1.6, -0.72, z); block(1.5, 1.05, 1.6, 0.78, z, tilt=0.03)
block(1.05, 0.9, 1.2, -0.62, z + 1.6, 0.08); block(1.15, 0.9, 1.2, 0.68, z + 1.6, 0.06)
block(2.7, 1.1, 0.9, 0.05, z + 2.8, 0.05)
block(1.15, 0.95, 0.85, 0.0, z + 3.7, 0.1)
block(3.0, 0.85, 0.7, -0.05, z + 4.55, 0.08, tilt=-0.02)
block(0.95, 0.8, 1.1, 0.05, z + 5.25, 0.2)

# rose bed around the base: low shrubs with white and pink blooms
def bed_mat(n, l, b):
    vor = n.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 9
    dots = n.new("ShaderNodeMapRange"); dots.inputs[1].default_value = 0.12; dots.inputs[2].default_value = 0.05; l.new(vor.outputs["Distance"], dots.inputs[0])
    pk = n.new("ShaderNodeMix"); pk.data_type = "RGBA"; pk.inputs[6].default_value = (0.85, 0.82, 0.8, 1); pk.inputs[7].default_value = (0.8, 0.35, 0.5, 1)
    l.new(vor.outputs["Color"], pk.inputs[0])
    mx = n.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.inputs[6].default_value = (0.03, 0.06, 0.025, 1)
    l.new(dots.outputs[0], mx.inputs[0]); l.new(pk.outputs[2], mx.inputs[7]); l.new(mx.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
bedm = shader("rosebed", bed_mat)
bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=48, radius=4.8)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=6, use_grid_fill=True)
for vt in bm.verts:
    r = math.hypot(vt.co.x, vt.co.y)
    h = 0 if r < 1.9 or r > 4.6 else (0.35 + 0.35 * (noise.noise(vt.co * 1.3) + 0.5)) * min(1, (r - 1.9) * 2, (4.6 - r) * 2)
    vt.co.z = GROUND + max(0, h)
me = bpy.data.meshes.new("bed"); bm.to_mesh(me); bm.free(); me.materials.append(bedm)
bed = link(bpy.data.objects.new("bed", me)); bed.location = (SX, SY, 0)
for p in me.polygons: p.use_smooth = True

# seawall benches facing the water, and lamp posts along the path
wood = material("bench", (0.16, 0.1, 0.06), 0.7); metal = material("metal", (0.03, 0.03, 0.035), 0.4)
def box(loc, dims, rz, mat):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.object
    o.scale = dims; o.rotation_euler = (0, 0, rz); o.data.materials.append(mat); return o
for bx_, by_ in [(-11.5, 9), (-12.5, -6), (6, -27)]:
    z0, d, _ = ground_z(bx_, by_); nx_, ny_ = -1, 0.15; rz = math.atan2(ny_, nx_) + math.pi / 2
    box(W(bx_, by_, z0 + 0.45), (1.9, 0.45, 0.07), rz, wood)
    box(W(bx_ + 0.25, by_, z0 + 0.8), (1.9, 0.06, 0.4), rz, wood)
    for s in (-0.8, 0.8): box(W(bx_ + 0.05, by_ + s * 0.98, z0 + 0.22), (0.06, 0.5, 0.44), rz, metal)
for lx_, ly_ in [(-16, 2), (-6, -22), (14, -38), (-14, 26)]:
    z0, d, _ = ground_z(lx_, ly_)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.07, depth=4.2, location=W(lx_, ly_, z0 + 2.1)); bpy.context.object.data.materials.append(metal)
    box(W(lx_, ly_, z0 + 4.25), (0.35, 0.35, 0.25), 0, metal)

# English Bay Beach logs (rows running north-south, as on the satellite image)
log = material("driftwood", (0.26, 0.21, 0.16), 0.85, 0.5, 3.0)
for x, y, L, r in [(16, 24, 9, .4), (17.5, 33, 10, .42), (19, 43, 8, .38), (20.5, 30, 11, .45), (14.5, 40, 9, .4),
                   (22, 52, 10, .42), (11, 58, 9, .4), (6, 70, 12, .45), (2, 88, 10, .42), (-4, 104, 11, .4), (-8, 122, 10, .4)]:
    z0, d, _ = ground_z(x, y)
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=L, vertices=20, location=W(x, y, z0 + r * .85))
    c = bpy.context.object; c.rotation_euler = (math.radians(90), 0, math.radians(random.uniform(-8, 8))); c.data.materials.append(log)

# Beach Avenue trees behind English Bay Beach (big London planes and elms), and a few West End towers beyond
leaf = material("canopy", (0.035, 0.05, 0.022), 1.0, 0.8, 1.2); bark = material("bark", (0.05, 0.04, 0.035), 0.9)
def tree(x, y, h):
    z0, d, _ = ground_z(x, y); z0 = max(z0, GROUND)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=h * 0.5, location=W(x, y, z0 + h * 0.25)); bpy.context.object.data.materials.append(bark)
    for k in range(6):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=h * random.uniform(.18, .26),
            location=W(x + random.uniform(-2.5, 2.5), y + random.uniform(-2.5, 2.5), z0 + h * random.uniform(.55, .85)))
        o = bpy.context.object; o.scale.z = 0.8; o.data.materials.append(leaf)
        dm = o.modifiers.new("d", "DISPLACE"); tx = bpy.data.textures.new("leafy", "CLOUDS"); tx.noise_scale = 1.2; dm.texture = tx; dm.strength = 1.2
for k in range(16):
    tree(random.uniform(45, 62), 30 + k * 13 + random.uniform(-3, 3), random.uniform(13, 18))
tower = material("tower", (0.12, 0.12, 0.13), 0.5)
for x, y, h, w in [(380, 560, 70, 22), (470, 650, 95, 25), (330, 760, 60, 20), (560, 520, 80, 24), (430, 880, 110, 26), (640, 700, 85, 22)]:
    box(W(x, y, h / 2), (w, w, h), 0.3, tower)
