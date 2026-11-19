"""
A small numpy software rasteriser, so a mesh can be LOOKED AT without Blender or the game.

Orthographic camera, z-buffer, perspective-free barycentric interpolation, optional texture and
back-face culling. Slow (a Python loop over triangles) but enough for a 20k-triangle character.
"""

import numpy as np
from PIL import Image


def view_matrix(yaw=0.0, pitch=0.0):
    """yaw turns the camera round the model's up axis (degrees); 0 looks at the model's front (+z towards us)"""
    y, p = np.radians(yaw), np.radians(pitch)
    ry = np.array([[np.cos(y), 0, -np.sin(y)], [0, 1, 0], [np.sin(y), 0, np.cos(y)]])
    rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    return rx @ ry


def render(pos, nrm, tris_list, size=(700, 900), yaw=0, pitch=0, bounds=None, uv=None, textures=None,
           colors=None, cull=True, bg=(40, 40, 46), light=(0.3, 0.5, 0.8), flat_shade=0.45, ssaa=1):
    """
    tris_list: list of (T, 3) index arrays (one per component)
    textures:  list of HxWx3 float arrays (0..1) per component, or None
    colors:    list per component: an (N, 3) per-vertex colour array or a single rgb, used where no texture
    bounds:    (xmin, xmax, ymin, ymax) in view space; default fits the model
    cull:      True hides faces whose winding faces away (as the game does), "mark" paints them magenta
    """
    W, H = size[0] * ssaa, size[1] * ssaa
    R = view_matrix(yaw, pitch)
    vp = pos @ R.T
    vn = nrm @ R.T
    if bounds is None:
        used = np.unique(np.concatenate([t.reshape(-1) for t in tris_list]))
        mn, mx = vp[used].min(0), vp[used].max(0)
        pad = 0.03 * max(mx[0] - mn[0], mx[1] - mn[1])
        bounds = (mn[0] - pad, mx[0] + pad, mn[1] - pad, mx[1] + pad)
    x0, x1, y0, y1 = bounds
    s = min(W / (x1 - x0), H / (y1 - y0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sx = (vp[:, 0] - cx) * s + W / 2
    sy = H / 2 - (vp[:, 1] - cy) * s
    sz = vp[:, 2]
    img = np.empty((H, W, 3), np.float32)
    img[:] = np.array(bg, np.float32) / 255
    zb = np.full((H, W), -1e9, np.float32)
    L = np.array(light, np.float32)
    L /= np.linalg.norm(L)

    for ci, tris in enumerate(tris_list):
        tex = textures[ci] if textures else None
        col = colors[ci] if colors else None
        if col is not None:
            col = np.asarray(col, np.float32)
        for a, b, c in tris:
            ax, ay, bx, by, cx_, cy_ = sx[a], sy[a], sx[b], sy[b], sx[c], sy[c]
            area = (bx - ax) * (cy_ - ay) - (cx_ - ax) * (by - ay)
            if area == 0:
                continue
            # screen y is flipped, so a counter-clockwise (front) model triangle has NEGATIVE area here
            back = area > 0
            if back and cull is True:
                continue
            xmin = max(int(np.floor(min(ax, bx, cx_))), 0)
            xmax = min(int(np.ceil(max(ax, bx, cx_))), W - 1)
            ymin = max(int(np.floor(min(ay, by, cy_))), 0)
            ymax = min(int(np.ceil(max(ay, by, cy_))), H - 1)
            if xmin > xmax or ymin > ymax:
                continue
            xs = np.arange(xmin, xmax + 1) + 0.5
            ys = np.arange(ymin, ymax + 1) + 0.5
            X, Y = np.meshgrid(xs, ys)
            w0 = ((bx - X) * (cy_ - Y) - (cx_ - X) * (by - Y)) / area
            w1 = ((cx_ - X) * (ay - Y) - (ax - X) * (cy_ - Y)) / area
            w2 = 1 - w0 - w1
            m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not m.any():
                continue
            z = w0 * sz[a] + w1 * sz[b] + w2 * sz[c]
            zsub = zb[ymin:ymax + 1, xmin:xmax + 1]
            m &= z > zsub
            if not m.any():
                continue
            n = w0[m, None] * vn[a] + w1[m, None] * vn[b] + w2[m, None] * vn[c]
            n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
            if back:
                n = -n
            sh = flat_shade + (1 - flat_shade) * np.clip(n @ L, 0, 1)
            if back and cull == "mark":
                base = np.array([1.0, 0.0, 1.0], np.float32)[None]
            elif tex is not None:
                u = w0[m] * uv[a, 0] + w1[m] * uv[b, 0] + w2[m] * uv[c, 0]
                v = w0[m] * uv[a, 1] + w1[m] * uv[b, 1] + w2[m] * uv[c, 1]
                th, tw = tex.shape[:2]
                tx = np.clip((u % 1.0) * tw, 0, tw - 1).astype(int)
                ty = np.clip((v % 1.0) * th, 0, th - 1).astype(int)
                base = tex[ty, tx, :3]
            elif col is not None and col.ndim == 2:
                base = w0[m, None] * col[a] + w1[m, None] * col[b] + w2[m, None] * col[c]
            elif col is not None:
                base = col[None]
            else:
                base = np.array([0.8, 0.8, 0.8], np.float32)[None]
            sub = img[ymin:ymax + 1, xmin:xmax + 1]
            sub[m] = base * sh[:, None]
            zsub[m] = z[m]
    out = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    im = Image.fromarray(out)
    if ssaa > 1:
        im = im.resize(size, Image.Resampling.LANCZOS)
    return im


def sheet(images, cols=None, labels=None):
    """paste images side by side into one contact sheet"""
    from PIL import ImageDraw
    cols = cols or len(images)
    rows = (len(images) + cols - 1) // cols
    w, h = images[0].size
    out = Image.new("RGB", (w * cols, h * rows), (20, 20, 24))
    d = ImageDraw.Draw(out)
    for i, im in enumerate(images):
        x, y = (i % cols) * w, (i // cols) * h
        out.paste(im, (x, y))
        if labels:
            d.text((x + 6, y + 4), str(labels[i]), fill=(255, 255, 0))
    return out


def load_tex(path):
    return np.asarray(Image.open(path).convert("RGBA"), np.float32) / 255
