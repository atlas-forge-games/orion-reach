"""Rebuild the original procedural artwork (development only: numpy, Pillow)."""

from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1] / "assets"
rng = np.random.default_rng(314159)


def noise(w, h, cells):
    grid = Image.fromarray(rng.integers(0, 256, (cells, cells * 2), dtype=np.uint8))
    return np.array(grid.resize((w, h), Image.Resampling.BICUBIC), dtype=float) / 255


def build():
    ROOT.mkdir(exist_ok=True)
    w, h = 1440, 900
    y, x = np.mgrid[0:h, 0:w]
    cloud = sum(noise(w, h, n) * weight for n, weight in ((6, .5), (15, .25), (35, .15), (80, .1)))
    band = np.exp(-((y - (730 - .24*x + 110*np.sin(x/500)))/155)**2)
    region = np.exp(-((x-1120)/620)**2) * band
    bg = np.zeros((h, w, 3)) + [5, 10, 17]
    bg += region[..., None] * cloud[..., None]**2 * np.array([18, 38, 43])
    amber = np.exp(-((x-1370)/300)**2 - ((y-130)/270)**2)
    bg += amber[..., None] * [22, 18, 10]
    vignette = np.clip(1 - .25*((x-w/2)/(w/2))**2 - .18*((y-h/2)/(h/2))**2, .55, 1)
    bg *= vignette[..., None]
    Image.fromarray(np.uint8(np.clip(bg, 0, 255))).save(ROOT / "space.png")

    n = 760
    yy, xx = np.mgrid[0:n, 0:n]
    nx, ny = (xx-n/2)/329, (yy-n/2)/329
    r2 = nx*nx + ny*ny
    mask = r2 <= 1
    nz = np.sqrt(np.maximum(0, 1-r2))
    # Map a multi-scale texture onto a sphere; lighting comes from upper left.
    lon = np.arctan2(nx, nz)
    lat = np.arcsin(np.clip(ny, -1, 1))
    tex = sum(noise(1800, 900, cells)*weight for cells, weight in ((7,.5),(17,.25),(43,.15),(105,.1)))
    u = np.clip(((lon/(2*np.pi)+.52)*1799).astype(int), 0, 1799)
    v = np.clip(((lat/np.pi+.5)*899).astype(int), 0, 899)
    heights = tex[v,u]
    land = np.clip((heights-.515)*18, 0, 1)
    ocean = np.zeros((n,n,3)) + [15, 57, 75]
    ground = np.zeros((n,n,3)) + [79, 95, 84]
    color = ocean*(1-land[...,None]) + ground*land[...,None]
    detail = noise(n,n,170)
    color *= (.8+.35*detail)[...,None]
    clouds = noise(1800,900,18)[v,u]*.6 + noise(1800,900,60)[v,u]*.4
    clouds = np.clip((clouds-.54)*6,0,.85)
    color = color*(1-clouds[...,None]) + np.array([160,181,185])*clouds[...,None]
    sun = np.clip(-nx*.72-ny*.49+nz*.41,0,1)
    color *= (.045+.96*sun**.65)[...,None]
    rim = (1-nz)**4.5 * np.clip(-nx*.6-ny*.5+.55,0,1)
    color += rim[...,None]*[36,108,143]
    city = (rng.random((n,n)) > .992) & (land>.5) & (sun<.18) & mask
    color[city] += np.array([87,61,26])
    # Soft atmosphere is part of the transparent asset, not a hard outline.
    rr = np.sqrt(r2)
    glow = np.exp(-np.maximum(0,rr-1)*65) * (rr>1)
    rgba = np.zeros((n,n,4))
    rgba[...,:3] = np.where(mask[...,None], color, np.array([58,132,166]))
    rgba[...,3] = np.where(mask,255,glow*67)
    Image.fromarray(np.uint8(np.clip(rgba,0,255))).save(ROOT / "planet.png")
    print("Built space.png and planet.png")


if __name__ == "__main__":
    build()
