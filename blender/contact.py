# Stack images vertically into one PNG. Usage: -- OUT img1 img2 ...
import bpy, sys, numpy as np
a = sys.argv[sys.argv.index("--") + 1:]
imgs = [bpy.data.images.load(p) for p in a[1:]]
w = max(i.size[0] for i in imgs)
rows = []
for i in imgs:
    px = np.array(i.pixels[:], dtype=np.float32).reshape(i.size[1], i.size[0], 4)
    pad = np.zeros((i.size[1], w, 4), np.float32); pad[..., 3] = 1; pad[:, :i.size[0]] = px
    rows.append(pad); rows.append(np.ones((4, w, 4), np.float32))
arr = np.concatenate(rows[::-1][1:], axis=0)  # blender pixel rows are bottom-up
out = bpy.data.images.new("c", w, arr.shape[0]); out.pixels = arr.ravel()
out.filepath_raw = a[0]; out.file_format = "PNG"; out.save()
