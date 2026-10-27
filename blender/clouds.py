# Bakes tileable-ish cloud density textures (white with alpha = density) for the page to tint live.
#   cloud_low.webp   stratocumulus: lumpy clumps with darker cores
#   cloud_mid.webp   altocumulus: cellular ripples
#   cloud_high.webp  cirrus: long wind-drawn streaks
# Usage: Blender -b --factory-startup -P clouds.py -- OUTDIR
import bpy, sys, os

OUT = sys.argv[sys.argv.index("--") + 1:][0]
os.makedirs(OUT, exist_ok=True)
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.samples = 4; sc.cycles.use_denoising = False
sc.render.film_transparent = True
sc.render.resolution_x, sc.render.resolution_y = 2048, 512
sc.render.image_settings.file_format = "WEBP"; sc.render.image_settings.color_mode = "RGBA"; sc.render.image_settings.quality = 88
sc.view_settings.view_transform = "Standard"

bpy.ops.mesh.primitive_plane_add(size=1); pl = bpy.context.object; pl.scale = (4, 1, 1)
cd = bpy.data.cameras.new("c"); cd.type = "ORTHO"; cd.ortho_scale = 4
cam = bpy.data.objects.new("c", cd); cam.location = (0, 0, 5); sc.collection.objects.link(cam); sc.camera = cam
world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0

def bake(name, build):
    m = bpy.data.materials.new(name); m.use_nodes = True
    n = m.node_tree.nodes; l = m.node_tree.links
    for x in list(n): n.remove(x)
    out = n.new("ShaderNodeOutputMaterial"); tc = n.new("ShaderNodeTexCoord")
    dens = build(n, l, tc.outputs["Object"])  # socket giving density 0..1
    # edge fade so sprites never show a hard border
    sep = n.new("ShaderNodeSeparateXYZ"); l.new(tc.outputs["Generated"], sep.inputs[0])
    def edge(sock, k):
        a = n.new("ShaderNodeMath"); a.operation = "PINGPONG"; a.inputs[1].default_value = 0.5; l.new(sock, a.inputs[0])
        b = n.new("ShaderNodeMath"); b.operation = "MULTIPLY"; b.inputs[1].default_value = k; b.use_clamp = True; l.new(a.outputs[0], b.inputs[0])
        return b.outputs[0]
    ex, ey = edge(sep.outputs[0], 7), edge(sep.outputs[1], 5)
    m1 = n.new("ShaderNodeMath"); m1.operation = "MULTIPLY"; l.new(ex, m1.inputs[0]); l.new(ey, m1.inputs[1])
    m2 = n.new("ShaderNodeMath"); m2.operation = "MULTIPLY"; l.new(dens, m2.inputs[0]); l.new(m1.outputs[0], m2.inputs[1])
    # colour: thick cores slightly darker (backlit look), alpha = density
    shade = n.new("ShaderNodeMapRange"); shade.inputs[3].default_value = 1.0; shade.inputs[4].default_value = 0.55
    l.new(m2.outputs[0], shade.inputs[0])
    em = n.new("ShaderNodeEmission"); l.new(shade.outputs[0], em.inputs["Color"])
    tr = n.new("ShaderNodeBsdfTransparent"); mix = n.new("ShaderNodeMixShader")
    l.new(m2.outputs[0], mix.inputs[0]); l.new(tr.outputs[0], mix.inputs[1]); l.new(em.outputs[0], mix.inputs[2])
    l.new(mix.outputs[0], out.inputs["Surface"])
    pl.data.materials.clear(); pl.data.materials.append(m)
    sc.render.filepath = os.path.join(OUT, name + ".webp")
    bpy.ops.render.render(write_still=True); print("RENDERED", name, flush=True)

def ramp(n, l, sock, lo, hi):
    r = n.new("ShaderNodeMapRange"); r.interpolation_type = "SMOOTHSTEP"
    r.inputs[1].default_value = lo; r.inputs[2].default_value = hi; l.new(sock, r.inputs[0]); return r.outputs[0]

def low(n, l, co):
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 2.2, 1); l.new(co, mp.inputs[0])
    nz = n.new("ShaderNodeTexNoise"); nz.noise_dimensions = "3D"; nz.inputs["Scale"].default_value = 2.2
    nz.inputs["Detail"].default_value = 12; nz.inputs["Roughness"].default_value = 0.62; nz.inputs["Distortion"].default_value = 0.4
    l.new(mp.outputs[0], nz.inputs[0])
    return ramp(n, l, nz.outputs["Fac"], 0.47, 0.72)

def mid(n, l, co):
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (1.0, 2.6, 1); l.new(co, mp.inputs[0])
    vo = n.new("ShaderNodeTexVoronoi"); vo.feature = "SMOOTH_F1"; vo.inputs["Scale"].default_value = 14; vo.inputs["Randomness"].default_value = 0.9
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 1.6; nz.inputs["Detail"].default_value = 6
    l.new(mp.outputs[0], vo.inputs[0]); l.new(mp.outputs[0], nz.inputs[0])
    cells = ramp(n, l, vo.outputs["Distance"], 0.42, 0.08)
    patch = ramp(n, l, nz.outputs["Fac"], 0.45, 0.66)
    m = n.new("ShaderNodeMath"); m.operation = "MULTIPLY"; l.new(cells, m.inputs[0]); l.new(patch, m.inputs[1]); return m.outputs[0]

def high(n, l, co):
    mp = n.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.35, 7.0, 1)
    mp.inputs["Rotation"].default_value = (0, 0, 0.12); l.new(co, mp.inputs[0])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 2.0; nz.inputs["Detail"].default_value = 14
    nz.inputs["Roughness"].default_value = 0.7; nz.inputs["Distortion"].default_value = 1.4
    l.new(mp.outputs[0], nz.inputs[0])
    return ramp(n, l, nz.outputs["Fac"], 0.5, 0.78)

bake("cloud_low", low); bake("cloud_mid", mid); bake("cloud_high", high)
