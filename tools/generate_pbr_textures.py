import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.ndimage import gaussian_filter

OUT_DIR = r"c:\Users\gksix\Downloads\새 폴더 (2)\YugiriVillage\Assets\Textures"
os.makedirs(OUT_DIR, exist_ok=True)

SIZE = 1024


def fbm_noise(shape, scales=(4, 8, 16, 32, 64), weights=None, seed=42):
    rng = np.random.default_rng(seed)
    h, w = shape
    if weights is None:
        weights = [1.0 / (i + 1) for i in range(len(scales))]
    total_w = sum(weights)
    acc = np.zeros((h, w), dtype=np.float32)
    for sc, wt in zip(scales, weights):
        gh = max(2, h // sc)
        gw = max(2, w // sc)
        grid = rng.random((gh, gw), dtype=np.float32)
        img = Image.fromarray((grid * 255).astype(np.uint8), mode="L").resize((w, h), Image.BICUBIC)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        acc += arr * (wt / total_w)
    mn, mx = acc.min(), acc.max()
    if mx > mn:
        acc = (acc - mn) / (mx - mn)
    return acc


def ridge_noise(shape, scales=(4, 8, 16, 32), seed=101):
    """Sharp crystalline/creased multi-fractal noise for cleaved rock, bark, and wrinkles."""
    raw = fbm_noise(shape, scales=scales, seed=seed)
    ridged = 1.0 - np.abs(raw * 2.0 - 1.0)
    ridged = ridged ** 1.6
    mn, mx = ridged.min(), ridged.max()
    if mx > mn:
        ridged = (ridged - mn) / (mx - mn)
    return ridged


def height_to_normal(height_map, strength=3.0, smooth_sigma=0.6):
    """Convert a [0, 1] height map into an OpenGL tangent-space normal map."""
    h = height_map.astype(np.float32)
    if smooth_sigma > 0.0:
        h = gaussian_filter(h, sigma=smooth_sigma, mode="wrap")
    dy, dx = np.gradient(h)
    nx = -dx * strength
    ny = -dy * strength
    nz = np.ones_like(h)
    length = np.sqrt(nx * nx + ny * ny + nz * nz) + 1e-8
    nx /= length
    ny /= length
    nz /= length
    rgb = np.stack([(nx * 0.5 + 0.5) * 255.0, (ny * 0.5 + 0.5) * 255.0, (nz * 0.5 + 0.5) * 255.0], axis=-1)
    return np.clip(rgb, 0, 255).astype(np.uint8)


def save_pbr_set(
    name,
    albedo_rgb,
    height_map,
    metallic_map,
    smoothness_map,
    ao_map=None,
    emission_rgb=None,
    albedo_alpha=None,
    normal_strength=3.0,
    smooth_sigma=0.6,
):
    albedo_u8 = np.clip(albedo_rgb * 255.0, 0, 255).astype(np.uint8)
    if albedo_alpha is not None:
        alpha_u8 = np.clip(albedo_alpha * 255.0, 0, 255).astype(np.uint8)
        rgba_u8 = np.dstack([albedo_u8, alpha_u8])
        Image.fromarray(rgba_u8, mode="RGBA").save(os.path.join(OUT_DIR, f"{name}_Albedo.png"))
    else:
        Image.fromarray(albedo_u8, mode="RGB").save(os.path.join(OUT_DIR, f"{name}_Albedo.png"))

    norm_u8 = height_to_normal(height_map, strength=normal_strength, smooth_sigma=smooth_sigma)
    Image.fromarray(norm_u8, mode="RGB").save(os.path.join(OUT_DIR, f"{name}_Normal.png"))

    # Unity Standard / Custom MetallicSmoothness map: R = Metallic, G = AO, B = Height, A = Smoothness
    m_u8 = np.clip(metallic_map * 255.0, 0, 255).astype(np.uint8)
    s_u8 = np.clip(smoothness_map * 255.0, 0, 255).astype(np.uint8)
    if ao_map is None:
        ao_map = np.clip(0.68 + 0.32 * height_map, 0.0, 1.0)
    ao_u8 = np.clip(ao_map * 255.0, 0, 255).astype(np.uint8)
    h_u8 = np.clip(height_map * 255.0, 0, 255).astype(np.uint8)
    ms_rgba = np.stack([m_u8, ao_u8, h_u8, s_u8], axis=-1)
    Image.fromarray(ms_rgba, mode="RGBA").save(os.path.join(OUT_DIR, f"{name}_MetallicSmoothness.png"))
    Image.fromarray(ao_u8, mode="L").save(os.path.join(OUT_DIR, f"{name}_AO.png"))

    if emission_rgb is not None:
        em_u8 = np.clip(emission_rgb * 255.0, 0, 255).astype(np.uint8)
        Image.fromarray(em_u8, mode="RGB").save(os.path.join(OUT_DIR, f"{name}_Emission.png"))
    print(f"Saved PBR set: {name}")


def load_jp_font(size):
    candidates = [
        r"C:\Windows\Fonts\YuGothB.ttc",
        r"C:\Windows\Fonts\meiryob.ttc",
        r"C:\Windows\Fonts\msgothic.ttc",
        r"C:\Windows\Fonts\malgunbd.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def gen_wet_asphalt():
    # Authentic rain-drenched Japanese rural road asphalt:
    # Sharp crushed stone aggregate (basalt/granite chips) embedded in dark wet bitumen,
    # hairline tar-repaired cracks, and mirror-flat standing rainwater puddles that submerge the gravel in low spots.
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    n_macro = fbm_noise((SIZE, SIZE), scales=(32, 64, 128, 256), weights=(0.15, 0.25, 0.35, 0.25), seed=101)
    n_mid = fbm_noise((SIZE, SIZE), scales=(8, 16, 32), weights=(0.45, 0.35, 0.20), seed=102)
    # Fine crushed stone aggregate at 1px, 2px, 3px, 6px scales (no wormy contour lines!)
    n_gravel1 = fbm_noise((SIZE, SIZE), scales=(1, 2, 3, 6), weights=(0.42, 0.30, 0.18, 0.10), seed=103)
    n_gravel2 = fbm_noise((SIZE, SIZE), scales=(2, 4, 8), weights=(0.50, 0.30, 0.20), seed=104)
    aggregate = np.clip(((n_gravel1 ** 1.35) * 0.70 + n_gravel2 * 0.30 - 0.26) * 2.1, 0.0, 1.0)

    # Subtle tar-sealed hairline road crack network
    crack_field = np.abs(fbm_noise((SIZE, SIZE), scales=(16, 32, 64), seed=105) - 0.50)
    tar_seam = np.clip(1.0 - crack_field / 0.015, 0.0, 1.0)

    # Standing puddle mask: water fills low macro basins
    puddle_depth = np.clip((n_macro - 0.50) * 3.4, 0.0, 1.0)
    puddle_mask = gaussian_filter(puddle_depth, sigma=3.5, mode="wrap")

    # Aggregate pebbles poke through shallow puddle edges!
    raw_rock_height = 0.28 + 0.52 * aggregate + 0.20 * n_mid - 0.10 * tar_seam
    water_level = 0.56 * puddle_mask
    submerged = np.clip((water_level - raw_rock_height * (1.0 - 0.45 * puddle_mask)) * 6.0, 0.0, 1.0)

    # Albedo: dark bitumen (0.035), mineral aggregate flecks (0.08..0.14), darker when submerged
    mineral_tint = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), seed=106)
    base_val = 0.042 + 0.068 * aggregate + 0.022 * (mineral_tint - 0.5)
    base_val = base_val * (1.0 - 0.35 * tar_seam) * (1.0 - 0.32 * submerged)

    # Subtle roadside moss/silt near tile edges
    silt = fbm_noise((SIZE, SIZE), scales=(16, 32, 64), seed=107)
    r = base_val * 0.96 + 0.008 * silt
    g = base_val * 0.99 + 0.010 * silt
    b = base_val * 1.05
    albedo = np.stack([r, g, b], axis=-1)

    # Height: mirror-flat (0.5) where submerged under standing water, sharp aggregate where exposed
    height = raw_rock_height * (1.0 - submerged) + 0.50 * submerged
    metallic = np.full((SIZE, SIZE), 0.04, dtype=np.float32) + 0.06 * submerged
    # Smoothness: exposed wet gravel = 0.66..0.78, tar seam = 0.88, standing water puddle = 0.985
    smoothness = (0.64 + 0.16 * (1.0 - aggregate) + 0.14 * tar_seam) * (1.0 - submerged) + 0.985 * submerged
    ao = np.clip(0.58 + 0.42 * raw_rock_height, 0.35, 1.0) * (1.0 - 0.5 * submerged) + 0.96 * submerged
    save_pbr_set("WetAsphalt", albedo, height, metallic, np.clip(smoothness, 0.1, 0.99), ao, normal_strength=2.4, smooth_sigma=0.35)


def gen_stone_paving():
    # Authentic Japanese Ashlar Mikage-ishi (cleaved biotite granite blocks) with deep mortar joints
    # and velvety wet bryophyte moss growing inside the damp recesses.
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    rows = 4
    cols = 2
    row_h = SIZE / rows
    col_w = SIZE / cols

    row_idx = np.floor(y / row_h).astype(np.int32)
    x_shifted = (x + (row_idx % 2) * (col_w * 0.5)) % SIZE
    col_idx = np.floor(x_shifted / col_w).astype(np.int32)

    dy = np.minimum(y % row_h, row_h - (y % row_h))
    dx = np.minimum(x_shifted % col_w, col_w - (x_shifted % col_w))

    n_edge = fbm_noise((SIZE, SIZE), scales=(4, 8, 16, 32), weights=(0.35, 0.30, 0.20, 0.15), seed=201)
    joint_dist = np.minimum(dx, dy) - (n_edge - 0.5) * 9.5
    mortar_mask = np.clip(1.0 - joint_dist / 10.0, 0.0, 1.0)
    chamfer = np.clip(joint_dist / 24.0, 0.0, 1.0)

    # Fine crystalline granite mineral grain (quartz/feldspar/biotite speckle at 1px..8px + subtle planar tilt)
    n_crystals = fbm_noise((SIZE, SIZE), scales=(1, 2, 3, 6), weights=(0.45, 0.30, 0.15, 0.10), seed=202)
    n_cleave = fbm_noise((SIZE, SIZE), scales=(8, 16, 32, 64), weights=(0.35, 0.30, 0.20, 0.15), seed=203)

    # Per-block subtle height and tone variation so each stone block feels hand-quarried
    block_hash = ((row_idx * 7 + col_idx * 13) % 5).astype(np.float32) / 5.0
    stone_val = 0.20 + 0.08 * n_cleave + 0.09 * (n_crystals - 0.5) + 0.04 * (block_hash - 0.5)

    # Velvety green moss grows in mortar joints and damp lower stone edges
    n_moss_patch = fbm_noise((SIZE, SIZE), scales=(8, 16, 32, 64), weights=(0.25, 0.30, 0.25, 0.20), seed=205)
    n_moss_tuft = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), weights=(0.55, 0.30, 0.15), seed=206)
    moss_mask = np.clip((mortar_mask * 0.80 + (1.0 - chamfer) * 0.55 + (n_moss_patch - 0.52) * 1.6) - 0.28, 0.0, 1.0)
    moss_mask = np.clip(moss_mask * (0.75 + 0.50 * n_moss_tuft), 0.0, 1.0)

    # Contrast: cool wet granite vs rich velvety olive-emerald bryophyte moss
    moss_r = 0.055 + 0.045 * n_moss_tuft
    moss_g = 0.145 + 0.085 * n_moss_tuft
    moss_b = 0.042 + 0.030 * n_moss_tuft

    r = stone_val * (1.0 - mortar_mask * 0.52) * (1.0 - moss_mask) + moss_r * moss_mask
    g = (stone_val * 1.01) * (1.0 - mortar_mask * 0.50) * (1.0 - moss_mask) + moss_g * moss_mask
    b = (stone_val * 1.04) * (1.0 - mortar_mask * 0.54) * (1.0 - moss_mask) + moss_b * moss_mask
    albedo = np.stack([r, g, b], axis=-1)

    height = chamfer * (0.62 + 0.18 * n_cleave + 0.16 * n_crystals + 0.04 * block_hash) * (1.0 - mortar_mask * 0.72) + moss_mask * 0.05 * n_moss_tuft
    metallic = np.full((SIZE, SIZE), 0.03, dtype=np.float32) * (1.0 - moss_mask)
    # CRITICAL: Wet cleaved granite is slick (0.76..0.88), whereas wet moss is optically velvety/matte (0.12..0.18)!
    stone_smooth = 0.72 + 0.16 * n_crystals - 0.15 * mortar_mask
    smoothness = stone_smooth * (1.0 - moss_mask) + (0.12 + 0.06 * n_moss_tuft) * moss_mask
    ao = np.clip(0.35 + 0.65 * chamfer * (1.0 - mortar_mask * 0.65), 0.22, 1.0)
    save_pbr_set("StonePaving", albedo, height, metallic, np.clip(smoothness, 0.08, 0.94), ao, normal_strength=2.8, smooth_sigma=0.35)


def gen_concrete_wall():
    # Weathered poured concrete wall with subtle wooden formwork tie-rod holes, hairline cracks,
    # vertical rain runoff streaks (雨だれ), and damp green basal algae/moss.
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    n_base = fbm_noise((SIZE, SIZE), scales=(4, 8, 16, 32, 64), weights=(0.20, 0.25, 0.25, 0.15, 0.15), seed=301)
    n_sand = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), weights=(0.50, 0.35, 0.15), seed=302)
    n_streak_raw = fbm_noise((SIZE, SIZE), scales=(4, 16, 32), weights=(0.3, 0.4, 0.3), seed=303)
    streaks = gaussian_filter(n_streak_raw, sigma=(36.0, 1.4), mode="wrap")

    # Rising damp & moss at the bottom of the wall
    bottom_damp = np.clip((y / SIZE - 0.58) * 2.4 + (n_base - 0.5) * 0.45, 0.0, 1.0)
    moss_speck = np.clip((bottom_damp - 0.35) * 1.8 * n_sand, 0.0, 1.0)

    # Hairline settling cracks
    crack_val = np.abs(fbm_noise((SIZE, SIZE), scales=(16, 32, 64), seed=304) - 0.5)
    crack_mask = np.clip(1.0 - crack_val / 0.012, 0.0, 1.0)

    base = 0.25 + 0.11 * n_base + 0.04 * (n_sand - 0.5) - 0.10 * streaks - 0.09 * bottom_damp - 0.12 * crack_mask
    r = base * (1.0 - moss_speck * 0.45) + moss_speck * 0.06
    g = base * (1.0 - moss_speck * 0.20) + moss_speck * 0.14
    b = base * (1.0 - moss_speck * 0.50) + moss_speck * 0.05
    albedo = np.stack([r, g, b], axis=-1)

    height = np.clip(0.55 + 0.28 * n_base + 0.12 * n_sand - 0.08 * streaks - 0.22 * crack_mask, 0.0, 1.0)
    metallic = np.zeros((SIZE, SIZE), dtype=np.float32)
    # Wet streaks and damp base have higher water sheen, while moss specks stay matte
    smoothness = np.clip((0.36 + 0.34 * streaks + 0.24 * bottom_damp) * (1.0 - moss_speck * 0.75), 0.12, 0.85)
    save_pbr_set("ConcreteWall", albedo, height, metallic, smoothness, normal_strength=2.8, smooth_sigma=0.45)


def gen_dark_wood():
    # Authentic Yakisugi / Aged Sugi & Hinoki Japanese architectural timber:
    # Crisp vertical planks, fine earlywood/latewood fiber grain, differential water absorption,
    # and rainwater splashback / mud-stain at the lower plank ends.
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    rng = np.random.default_rng(401)
    # High-res anisotropic vertical wood fibers + cathedral grain arches
    grain_strip = rng.random((SIZE // 32, SIZE), dtype=np.float32)
    n_grain = np.asarray(Image.fromarray((grain_strip * 255).astype(np.uint8)).resize((SIZE, SIZE), Image.BICUBIC)) / 255.0
    n_grain = gaussian_filter(n_grain, sigma=(10.0, 0.55), mode="wrap")
    n_grain = (n_grain - n_grain.min()) / max(1e-6, n_grain.max() - n_grain.min())

    # Cathedral growth ring modulation
    n_ring_mod = fbm_noise((SIZE, SIZE), scales=(16, 32, 64), seed=402)
    rings = np.sin((x / 9.5 + n_ring_mod * 4.5) * math.pi) * 0.5 + 0.5
    latewood = np.clip(n_grain * 0.65 + rings * 0.35, 0.0, 1.0)

    # 8 vertical planks with distinct age/tone per plank and recessed V-grooves
    planks = 8
    pw = SIZE / planks
    plank_idx = np.floor(x / pw).astype(np.int32)
    plank_tone = ((plank_idx * 5 + 3) % 7).astype(np.float32) / 7.0
    px = np.minimum(x % pw, pw - (x % pw))
    seam = np.clip(px / 5.5, 0.0, 1.0)

    # Lower plank water capillary wicking & rain mud splash
    n_weath = fbm_noise((SIZE, SIZE), scales=(8, 16, 32, 64), seed=403)
    bottom_soak = np.clip((y / SIZE - 0.66) * 2.6 + (n_weath - 0.5) * 0.4, 0.0, 1.0)

    r = (0.068 + 0.065 * latewood + 0.018 * plank_tone + 0.020 * n_weath) * seam * (1.0 - 0.38 * bottom_soak)
    g = (0.045 + 0.044 * latewood + 0.012 * plank_tone + 0.015 * n_weath) * seam * (1.0 - 0.34 * bottom_soak)
    b = (0.032 + 0.030 * latewood + 0.008 * plank_tone + 0.012 * n_weath) * seam * (1.0 - 0.40 * bottom_soak)
    albedo = np.stack([r, g, b], axis=-1)

    height = seam * (0.38 + 0.52 * latewood + 0.10 * n_weath)
    metallic = np.full((SIZE, SIZE), 0.02, dtype=np.float32)
    # Dense latewood ridges gleam when wet (0.68), porous earlywood channels are matte-damp (0.28), soaked base is slick (0.76)
    smoothness = np.clip((0.26 + 0.42 * latewood + 0.22 * bottom_soak) * seam, 0.16, 0.82)
    ao = np.clip(0.32 + 0.68 * seam * (0.75 + 0.25 * latewood), 0.18, 1.0)
    save_pbr_set("DarkWood", albedo, height, metallic, smoothness, ao, normal_strength=3.4, smooth_sigma=0.42)


def gen_aged_plaster():
    # Traditional Japanese Shikkui (white/cream lime plaster) over mud wattle wall:
    # Subtle trowel marks, rain runoff staining, fine hairline cracks, and damp flaking near the bottom.
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    n_trowel = fbm_noise((SIZE, SIZE), scales=(8, 16, 32, 64), weights=(0.25, 0.30, 0.25, 0.20), seed=501)
    n_grain = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), weights=(0.50, 0.35, 0.15), seed=502)
    n_stain_raw = fbm_noise((SIZE, SIZE), scales=(8, 16, 32), seed=503)
    rain_streaks = gaussian_filter(n_stain_raw, sigma=(32.0, 1.8), mode="wrap")

    # Hairline plaster cracks
    crack_field = np.abs(fbm_noise((SIZE, SIZE), scales=(16, 32, 64), seed=504) - 0.50)
    cracks = np.clip(1.0 - crack_field / 0.010, 0.0, 1.0)

    bottom_damp = np.clip((y / SIZE - 0.60) * 2.2 + (n_trowel - 0.5) * 0.45, 0.0, 1.0)
    # Small patches where lime plaster has flaked off at the damp bottom exposing brownish mud-wall (土壁)
    flake_mask = np.clip((bottom_damp * n_trowel - 0.52) * 5.0, 0.0, 1.0)

    plaster_r = 0.50 + 0.09 * n_trowel + 0.03 * (n_grain - 0.5) - 0.17 * rain_streaks - 0.18 * bottom_damp - 0.22 * cracks
    plaster_g = 0.47 + 0.08 * n_trowel + 0.03 * (n_grain - 0.5) - 0.16 * rain_streaks - 0.17 * bottom_damp - 0.22 * cracks
    plaster_b = 0.41 + 0.07 * n_trowel + 0.03 * (n_grain - 0.5) - 0.15 * rain_streaks - 0.18 * bottom_damp - 0.20 * cracks

    mud_r = 0.22 + 0.06 * n_grain
    mud_g = 0.17 + 0.05 * n_grain
    mud_b = 0.11 + 0.04 * n_grain

    r = plaster_r * (1.0 - flake_mask) + mud_r * flake_mask
    g = plaster_g * (1.0 - flake_mask) + mud_g * flake_mask
    b = plaster_b * (1.0 - flake_mask) + mud_b * flake_mask
    albedo = np.stack([r, g, b], axis=-1)

    height = (0.62 + 0.22 * n_trowel + 0.08 * n_grain - 0.25 * cracks) * (1.0 - flake_mask * 0.45)
    metallic = np.zeros((SIZE, SIZE), dtype=np.float32)
    smoothness = np.clip((0.28 + 0.36 * rain_streaks + 0.22 * bottom_damp) * (1.0 - flake_mask * 0.6), 0.14, 0.76)
    save_pbr_set("AgedPlaster", albedo, height, metallic, smoothness, normal_strength=2.6, smooth_sigma=0.45)


def gen_kawara_tile():
    # Traditional Japanese Ibushi-gawara (smoked silver-gray clay S-tiles) with crisp horizontal tier overlaps,
    # rain-slick ceramic glaze in the S-curve channels, and subtle moss/lichen in the overlap crevices.
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    cols = 8
    rows = 6
    cw = SIZE / cols
    rh = SIZE / rows

    wave_x = np.sin((x / cw) * 2.0 * math.pi) * 0.5 + 0.5
    row_pos = (y % rh) / rh
    overlap_lip = np.clip((row_pos - 0.86) / 0.14, 0.0, 1.0)
    under_shadow = np.clip(1.0 - row_pos / 0.16, 0.0, 1.0)

    n_clay = fbm_noise((SIZE, SIZE), scales=(4, 8, 16, 32), weights=(0.30, 0.30, 0.25, 0.15), seed=601)
    # Lichen/moss tucked just below each tile overlap lip
    lichen = np.clip(under_shadow * (n_clay - 0.38) * 2.4, 0.0, 1.0)

    base = (0.12 + 0.09 * wave_x + 0.03 * n_clay) * (1.0 - 0.42 * under_shadow)
    r = base * 0.96 * (1.0 - lichen * 0.4) + lichen * 0.07
    g = base * 0.99 * (1.0 - lichen * 0.2) + lichen * 0.13
    b = base * 1.06 * (1.0 - lichen * 0.5) + lichen * 0.05
    albedo = np.stack([r, g, b], axis=-1)

    height = np.clip(wave_x * 0.72 + (1.0 - row_pos) * 0.20 - overlap_lip * 0.32 + 0.05 * n_clay, 0.0, 1.0)
    metallic = np.full((SIZE, SIZE), 0.32, dtype=np.float32) * (1.0 - lichen)
    # Wet smoked clay tiles gleam brightly in the rain (0.82..0.90), while lichen stays matte (0.18)
    smoothness = (0.78 + 0.12 * (1.0 - wave_x) + 0.06 * n_clay) * (1.0 - lichen) + 0.18 * lichen
    ao = np.clip((0.52 + 0.48 * wave_x) * (1.0 - 0.55 * under_shadow), 0.22, 1.0)
    save_pbr_set("KawaraTile", albedo, height, metallic, np.clip(smoothness, 0.15, 0.94), ao, normal_strength=4.2, smooth_sigma=0.55)


def gen_rusted_metal():
    # Painted & galvanized corrugated tin (トタン板) with blistered rust patches, bolt heads, and rain streaks
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    corrug = np.sin((x / (SIZE / 16.0)) * 2.0 * math.pi) * 0.5 + 0.5
    n_rust = fbm_noise((SIZE, SIZE), scales=(4, 8, 16, 32, 64), weights=(0.25, 0.25, 0.20, 0.15, 0.15), seed=701)
    n_pitting = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), weights=(0.55, 0.30, 0.15), seed=702)
    n_drip = gaussian_filter(n_rust, sigma=(28.0, 1.5), mode="wrap")

    rust_mask = np.clip((n_rust * 0.75 + n_drip * 0.25 - 0.50) * 3.4, 0.0, 1.0)
    rust_edge = np.clip(rust_mask * (1.0 - rust_mask) * 4.0, 0.0, 1.0)

    metal_r = 0.17 + 0.06 * corrug - 0.04 * n_drip
    metal_g = 0.19 + 0.06 * corrug - 0.04 * n_drip
    metal_b = 0.22 + 0.07 * corrug - 0.03 * n_drip

    rust_r = 0.26 + 0.10 * n_rust + 0.05 * (n_pitting - 0.5)
    rust_g = 0.11 + 0.05 * n_rust + 0.02 * (n_pitting - 0.5)
    rust_b = 0.05 + 0.02 * n_rust

    r = metal_r * (1.0 - rust_mask) + rust_r * rust_mask
    g = metal_g * (1.0 - rust_mask) + rust_g * rust_mask
    b = metal_b * (1.0 - rust_mask) + rust_b * rust_mask
    albedo = np.stack([r, g, b], axis=-1)

    height = corrug * 0.78 - rust_mask * 0.09 + rust_edge * 0.04 * n_pitting
    metallic = np.clip(0.82 * (1.0 - rust_mask * 0.90), 0.05, 0.88)
    # Wet galvanized metal is slick (0.76), flaky rust is rougher (0.28)
    smoothness = np.clip(0.76 * (1.0 - rust_mask * 0.68) + 0.08 * n_pitting, 0.20, 0.86)
    ao = np.clip(0.64 + 0.36 * corrug - 0.18 * rust_mask, 0.35, 1.0)
    save_pbr_set("RustedMetal", albedo, height, metallic, smoothness, ao, normal_strength=3.2, smooth_sigma=0.50)


def gen_shoji_windows():
    # Crisp dark Kumiko wooden lattice over translucent handmade Washi mulberry paper (with visible mulberry fibers!)
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    n_paper = fbm_noise((SIZE, SIZE), scales=(4, 8, 16, 32, 64), weights=(0.25, 0.25, 0.20, 0.15, 0.15), seed=801)
    n_fibers = ridge_noise((SIZE, SIZE), scales=(2, 4, 8), seed=802)

    gx = np.minimum(np.mod(x, SIZE / 6.0), (SIZE / 6.0) - np.mod(x, SIZE / 6.0))
    gy = np.minimum(np.mod(y, SIZE / 10.0), (SIZE / 10.0) - np.mod(y, SIZE / 10.0))
    border = np.minimum(np.minimum(x, SIZE - x), np.minimum(y, SIZE - y))
    wood_mask = ((gx < 7.0) | (gy < 6.0) | (border < 22.0)).astype(np.float32)
    wood_mask = gaussian_filter(wood_mask, sigma=0.55)

    cx, cy = (x - SIZE * 0.5) / (SIZE * 0.5), (y - SIZE * 0.62) / (SIZE * 0.5)
    glow_falloff = np.clip(1.0 - (cx * cx * 0.72 + cy * cy * 0.62), 0.18, 1.0)
    silhouette = 1.0 - 0.38 * np.exp(-((cx + 0.14) ** 2 / 0.05 + (cy - 0.05) ** 2 / 0.20))

    # Subtle water-stain / aged yellowing along bottom panes
    bottom_age = np.clip((y / SIZE - 0.70) * 2.5 * n_paper, 0.0, 0.35)

    paper_mask = 1.0 - wood_mask
    paper_intensity = glow_falloff * silhouette * (0.85 + 0.10 * n_paper + 0.05 * n_fibers) * (1.0 - bottom_age)

    alb_w = np.stack([
        wood_mask * 0.08 + paper_mask * (0.78 * paper_intensity),
        wood_mask * 0.05 + paper_mask * (0.50 * paper_intensity),
        wood_mask * 0.03 + paper_mask * (0.22 * paper_intensity),
    ], axis=-1)
    em_w = np.stack([
        paper_mask * paper_intensity * 0.92,
        paper_mask * paper_intensity * 0.52,
        paper_mask * paper_intensity * 0.18,
    ], axis=-1)
    height = wood_mask * 0.68 + paper_mask * (0.48 + 0.025 * n_fibers)
    metallic = np.zeros((SIZE, SIZE), dtype=np.float32)
    smoothness = wood_mask * 0.42 + paper_mask * 0.16
    save_pbr_set("ShojiWindow", alb_w, height, metallic, smoothness, emission_rgb=em_w, normal_strength=1.6, smooth_sigma=0.6)

    alb_e = np.stack([
        wood_mask * 0.07 + paper_mask * (0.28 * paper_intensity),
        wood_mask * 0.05 + paper_mask * (0.46 * paper_intensity),
        wood_mask * 0.04 + paper_mask * (0.42 * paper_intensity),
    ], axis=-1)
    em_e = np.stack([
        paper_mask * paper_intensity * 0.22,
        paper_mask * paper_intensity * 0.44,
        paper_mask * paper_intensity * 0.38,
    ], axis=-1)
    save_pbr_set("ShojiWindowEerie", alb_e, height, metallic, smoothness, emission_rgb=em_e, normal_strength=1.6, smooth_sigma=0.6)


def gen_torii_vermilion():
    # Wet Cinnabar Vermilion lacquer (Shu-iro) over aged keyaki/hinoki timber with blistered lacquer peel & basal moss
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    rng = np.random.default_rng(901)
    grain_base = rng.random((SIZE // 32, SIZE // 2), dtype=np.float32)
    n_grain = np.asarray(Image.fromarray((grain_base * 255).astype(np.uint8)).resize((SIZE, SIZE), Image.BICUBIC)) / 255.0
    n_grain = gaussian_filter(n_grain, sigma=(6.0, 0.7), mode="wrap")
    n_grain = (n_grain - n_grain.min()) / max(1e-6, n_grain.max() - n_grain.min())

    n_peel = fbm_noise((SIZE, SIZE), scales=(8, 16, 32, 64), weights=(0.25, 0.25, 0.25, 0.25), seed=902)
    bottom_moss = np.clip((y / SIZE - 0.70) * 3.0 * n_peel, 0.0, 1.0)
    peel_mask = np.clip((n_peel - 0.64) * 4.2, 0.0, 1.0)

    red_r = 0.46 + 0.10 * n_grain
    red_g = 0.065 + 0.025 * n_grain
    red_b = 0.045 + 0.018 * n_grain

    wood_r = 0.11 + 0.04 * n_grain
    wood_g = 0.07 + 0.03 * n_grain
    wood_b = 0.04 + 0.02 * n_grain

    albedo = np.stack([
        (red_r * (1.0 - peel_mask) + wood_r * peel_mask) * (1.0 - bottom_moss * 0.55),
        (red_g * (1.0 - peel_mask) + wood_g * peel_mask) * (1.0 - bottom_moss * 0.20) + bottom_moss * 0.13,
        (red_b * (1.0 - peel_mask) + wood_b * peel_mask) * (1.0 - bottom_moss * 0.55),
    ], axis=-1)
    height = (1.0 - peel_mask * 0.28) * (0.62 + 0.38 * n_grain)
    metallic = np.full((SIZE, SIZE), 0.05, dtype=np.float32) * (1.0 - peel_mask)
    # Wet lacquer is glossy (0.82), exposed raw wood is rougher (0.30), moss is matte (0.14)
    smoothness = np.clip((0.78 * (1.0 - peel_mask) + 0.28 * peel_mask) * (1.0 - bottom_moss * 0.8), 0.14, 0.86)
    save_pbr_set("ToriiVermilion", albedo, height, metallic, smoothness, normal_strength=2.5, smooth_sigma=0.55)


def gen_mossy_granite():
    # Hand-carved weathered Japanese shrine granite (Jizo statues, Ishidoro stone lanterns, Komainu pedestals):
    # Fine crystalline mineral grain + subtle stone surface undulation + thick velvety green moss patches in crevices.
    n_crystals = fbm_noise((SIZE, SIZE), scales=(1, 2, 3, 6), weights=(0.45, 0.30, 0.15, 0.10), seed=1001)
    n_cleave = fbm_noise((SIZE, SIZE), scales=(8, 16, 32, 64), weights=(0.35, 0.30, 0.20, 0.15), seed=1002)
    n_moss_macro = fbm_noise((SIZE, SIZE), scales=(16, 32, 64, 128), weights=(0.25, 0.30, 0.25, 0.20), seed=1003)
    n_moss_tuft = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), weights=(0.55, 0.30, 0.15), seed=1004)

    moss = np.clip((n_moss_macro - 0.54) * 3.6, 0.0, 1.0)
    moss = np.clip(moss * (0.72 + 0.55 * n_moss_tuft), 0.0, 1.0)

    # Lichen crust rings around moss borders
    lichen_ring = np.clip(moss * (1.0 - moss) * 3.8 * n_crystals, 0.0, 1.0)

    g_val = 0.20 + 0.09 * n_cleave + 0.08 * (n_crystals - 0.5) + 0.08 * lichen_ring
    moss_r = 0.055 + 0.050 * n_moss_tuft
    moss_g = 0.155 + 0.095 * n_moss_tuft
    moss_b = 0.042 + 0.032 * n_moss_tuft

    r = g_val * (1.0 - moss) + moss_r * moss
    g = (g_val * 1.01) * (1.0 - moss) + moss_g * moss
    b = (g_val * 1.03) * (1.0 - moss) + moss_b * moss
    albedo = np.stack([r, g, b], axis=-1)

    height = (0.52 + 0.24 * n_cleave + 0.20 * n_crystals) * (1.0 - moss * 0.22) + moss * (0.44 + 0.14 * n_moss_tuft)
    metallic = np.zeros((SIZE, SIZE), dtype=np.float32)
    # Wet granite glistens (0.72..0.84), velvety moss absorbs specular into a soft matte finish (0.12..0.18)
    smoothness = (0.68 + 0.16 * n_crystals) * (1.0 - moss) + (0.12 + 0.06 * n_moss_tuft) * moss
    ao = np.clip(0.54 + 0.26 * n_cleave + 0.20 * n_crystals - 0.12 * moss, 0.30, 1.0)
    save_pbr_set("MossyGranite", albedo, height, metallic, np.clip(smoothness, 0.10, 0.88), ao, normal_strength=2.6, smooth_sigma=0.35)


def gen_vending_machine_front():
    img = Image.new("RGB", (SIZE, SIZE), (210, 214, 220))
    em = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_em = ImageDraw.Draw(em)

    font_lg = load_jp_font(44)
    font_md = load_jp_font(26)
    font_sm = load_jp_font(18)

    # Outer red enamel border & off-white steel body panel (non-emissive)
    draw.rectangle([0, 0, SIZE, SIZE], fill=(168, 28, 26))
    draw.rectangle([28, 28, SIZE - 28, SIZE - 28], fill=(205, 210, 216))

    # Top backlit acrylic header sign (y: 44..126 -> UV v: 0.875..0.957)
    draw.rectangle([48, 44, SIZE - 48, 126], fill=(165, 26, 24))
    draw.text((75, 60), "24時間営業  お飲み物  DRINK", fill=(248, 244, 232), font=font_lg)
    draw_em.rectangle([52, 48, SIZE - 52, 122], fill=(72, 16, 14))
    draw_em.text((75, 60), "24時間営業  お飲み物  DRINK", fill=(185, 168, 138), font=font_lg)

    # Dedicated backlit showcase interior back-wall band (y: 128..162 -> UV v: 0.840..0.874)
    draw.rectangle([56, 128, SIZE - 56, 162], fill=(195, 220, 238))
    draw_em.rectangle([56, 128, SIZE - 56, 162], fill=(92, 118, 138))

    # 3 rows of 8 Beverage Can / Bottle label textures (y: 165..610)
    # Kept LOW emission on can bodies so 3D cans/bottles show rich 3D cylindrical shading & specular highlights!
    win_box = [56, 164, SIZE - 56, 610]
    draw.rectangle(win_box, fill=(34, 38, 44), outline=(42, 46, 54), width=6)

    can_colors = [
        (178, 28, 28), (26, 78, 165), (32, 128, 54), (198, 118, 22),
        (82, 46, 28), (52, 34, 105), (210, 214, 222), (162, 125, 64),
    ]
    for shelf_idx, sy in enumerate([168, 316, 464]):
        draw.rectangle([64, sy + 110, SIZE - 64, sy + 132], fill=(42, 46, 54))
        for c_idx in range(8):
            cx = 84 + c_idx * 108
            col = can_colors[(shelf_idx * 3 + c_idx) % len(can_colors)]
            draw.rectangle([cx, sy + 8, cx + 78, sy + 88], fill=col, outline=(22, 24, 28), width=2)
            draw.rectangle([cx + 6, sy + 24, cx + 72, sy + 56], fill=(236, 234, 228))
            draw.rectangle([cx + 12, sy + 32, cx + 66, sy + 46], fill=col)
            # Subtle ambient bounce on can label (NOT blinding white!)
            draw_em.rectangle([cx + 2, sy + 10, cx + 76, sy + 86], fill=(int(col[0] * 0.14), int(col[1] * 0.15), int(col[2] * 0.16)))

            is_hot = (shelf_idx == 2 and c_idx >= 4)
            tag_col = (195, 42, 26) if is_hot else (26, 98, 185)
            draw.rectangle([cx, sy + 90, cx + 78, sy + 108], fill=tag_col)
            draw_em.rectangle([cx + 2, sy + 92, cx + 76, sy + 106], fill=(int(tag_col[0] * 0.55), int(tag_col[1] * 0.55), int(tag_col[2] * 0.55)))
            draw.text((cx + 12, sy + 89), "130円", fill=(252, 252, 252), font=font_sm)
            draw_em.text((cx + 12, sy + 89), "130円", fill=(165, 165, 165), font=font_sm)
            draw.rounded_rectangle([cx + 10, sy + 113, cx + 68, sy + 129], radius=4, fill=(24, 28, 34))
            led_col = (235, 48, 30) if (c_idx == 3 and shelf_idx == 1) else (65, 215, 98)
            draw.ellipse([cx + 32, sy + 116, cx + 44, sy + 126], fill=led_col)
            draw_em.ellipse([cx + 30, sy + 114, cx + 46, sy + 128], fill=(int(led_col[0] * 0.7), int(led_col[1] * 0.7), int(led_col[2] * 0.7)))

    # Control panel & digital price readout strip (y: 630..760 -> UV v: 0.258..0.385)
    draw.rectangle([56, 630, SIZE - 56, 760], fill=(32, 36, 42))
    draw.rectangle([680, 650, 810, 705], fill=(10, 14, 10), outline=(85, 90, 95), width=3)
    draw.text((700, 658), "130", fill=(245, 48, 28), font=font_lg)
    draw_em.text((700, 658), "130", fill=(195, 38, 22), font=font_lg)
    draw.rectangle([80, 652, 340, 702], fill=(24, 88, 168))
    draw.text((105, 662), "つめたい COLD", fill=(250, 250, 250), font=font_md)
    draw_em.rectangle([82, 654, 338, 700], fill=(16, 58, 112))
    draw.rectangle([360, 652, 620, 702], fill=(185, 42, 26))
    draw.text((385, 662), "あたたかい HOT", fill=(250, 250, 250), font=font_md)
    draw_em.rectangle([362, 654, 618, 700], fill=(118, 28, 18))

    # Pickup flap dark acrylic plate (y: 790..950 -> UV v: 0.072..0.228)
    draw.rectangle([90, 790, SIZE - 220, 950], fill=(24, 28, 32), outline=(72, 78, 86), width=6)
    draw.text((310, 845), "P U S H   取 出 口", fill=(175, 180, 185), font=font_md)

    alb = np.asarray(img, dtype=np.float32) / 255.0
    em_arr = np.asarray(em, dtype=np.float32) / 255.0
    grime = fbm_noise((SIZE, SIZE), scales=(16, 32, 64), weights=(0.35, 0.35, 0.30), seed=1101)
    alb = alb * (0.84 + 0.16 * grime[..., None])

    height = np.full((SIZE, SIZE), 0.5, dtype=np.float32)
    height[145:610, 56:SIZE - 56] = 0.35
    height[790:950, 90:SIZE - 220] = 0.25
    metallic = np.full((SIZE, SIZE), 0.52, dtype=np.float32)
    smoothness = np.full((SIZE, SIZE), 0.84, dtype=np.float32)
    save_pbr_set("VendingMachineFront", alb, height, metallic, smoothness, emission_rgb=em_arr, normal_strength=2.0, smooth_sigma=0.9)


def gen_shop_shutter_sign():
    img = Image.new("RGB", (SIZE, SIZE), (54, 58, 64))
    em = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_em = ImageDraw.Draw(em)

    font_xl = load_jp_font(54)
    font_lg = load_jp_font(38)
    font_md = load_jp_font(26)

    # Quadrant 1 (Top-Left, y: 8..248): Tobacco & Dagashi Shop Signboard
    draw.rectangle([8, 8, 680, 248], fill=(158, 34, 28), outline=(225, 215, 195), width=8)
    draw.rectangle([20, 20, 155, 236], fill=(228, 222, 205))
    draw.text((38, 48), "た\nば\nこ", fill=(165, 28, 24), font=font_lg)
    draw.text((180, 45), "駄菓子・雑貨", fill=(235, 228, 205), font=font_lg)
    draw.text((178, 118), "夕 霧 商 店", fill=(250, 242, 220), font=font_xl)
    draw_em.rectangle([16, 16, 672, 240], fill=(55, 24, 15))
    draw_em.text((178, 118), "夕 霧 商 店", fill=(185, 155, 105), font=font_xl)

    # Quadrant 2 (Top-Right, x: 692..1014, y: 8..248): Warning Sign "立入禁止"
    draw.rectangle([692, 8, 1014, 248], fill=(215, 180, 32), outline=(25, 25, 25), width=8)
    draw.rectangle([708, 24, 998, 105], fill=(175, 26, 22))
    draw.text((735, 38), "立 入 禁 止", fill=(248, 242, 235), font=font_lg)
    draw.text((718, 125), "これより先、崩落危険", fill=(20, 20, 20), font=font_md)
    draw.text((735, 175), "夕霧村役場・神社庁", fill=(28, 28, 28), font=font_md)

    # Band 2 Left (x: 8..500, y: 260..504): Rural Bus Stop Sign ("夕霧村 停留所")
    draw.rectangle([8, 260, 500, 504], fill=(220, 218, 206), outline=(42, 78, 130), width=10)
    draw.rectangle([18, 270, 490, 355], fill=(32, 74, 136))
    draw.text((95, 288), "夕霧村 停留所", fill=(242, 242, 236), font=font_lg)
    draw.text((55, 375), "最終便  23:45 (運休)", fill=(155, 32, 28), font=font_md)
    draw.text((55, 425), "※夜間は停車いたしません", fill=(42, 42, 48), font=font_md)

    # Band 2 Right (x: 516..1014, y: 260..504): Shrine Wooden Plaque ("夕霧神社")
    draw.rectangle([516, 260, 1014, 504], fill=(42, 28, 18), outline=(135, 105, 48), width=8)
    draw.text((615, 340), "夕 霧 神 社", fill=(208, 172, 88), font=font_xl)

    # Lower Half (y: 512..1024): Corrugated Steel Shop Shutter (Shatta)
    y_grid, x_grid = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    alb = np.asarray(img, dtype=np.float32) / 255.0
    em_arr = np.asarray(em, dtype=np.float32) / 255.0

    shutter_mask = (y_grid >= 512).astype(np.float32)
    slat_wave = np.sin(((y_grid - 512.0) / 22.0) * 2.0 * math.pi) * 0.5 + 0.5
    n_weath = fbm_noise((SIZE, SIZE), scales=(8, 16, 32, 64), weights=(0.30, 0.30, 0.25, 0.15), seed=1201)

    bottom_rust = np.clip(((y_grid - 760.0) / 264.0) * n_weath * 2.0, 0.0, 1.0) * shutter_mask
    shutter_val = 0.20 + 0.08 * slat_wave - 0.04 * n_weath
    alb[512:, :, 0] = shutter_val[512:, :] * (1.0 - bottom_rust[512:, :] * 0.5) + bottom_rust[512:, :] * 0.25
    alb[512:, :, 1] = (shutter_val[512:, :] + 0.01) * (1.0 - bottom_rust[512:, :] * 0.6) + bottom_rust[512:, :] * 0.11
    alb[512:, :, 2] = (shutter_val[512:, :] + 0.03) * (1.0 - bottom_rust[512:, :] * 0.7) + bottom_rust[512:, :] * 0.05

    alb[:512, :, :] *= (0.86 + 0.14 * n_weath[:512, :, None])

    height = np.where(y_grid >= 512, 0.35 + 0.55 * slat_wave, 0.50 + 0.03 * n_weath).astype(np.float32)
    metallic = np.where(y_grid >= 512, 0.76 * (1.0 - bottom_rust * 0.75), 0.20).astype(np.float32)
    smoothness = np.where(y_grid >= 512, 0.72 * (1.0 - bottom_rust * 0.55), 0.58).astype(np.float32)
    save_pbr_set("ShopShutterSign", alb, height, metallic, smoothness, emission_rgb=em_arr, normal_strength=2.6, smooth_sigma=0.7)


def gen_utility_concrete():
    # Spun-cast prestressed concrete utility pole (電柱) with aggregate pores, weather streaks,
    # black-and-yellow zebra reflector sleeve, and metallic pole number plate.
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    n1 = fbm_noise((SIZE, SIZE), scales=(4, 8, 16, 32, 64), weights=(0.25, 0.25, 0.25, 0.15, 0.10), seed=1301)
    n_pores = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), weights=(0.55, 0.30, 0.15), seed=1302)
    streaks = gaussian_filter(n1, sigma=(28.0, 1.5), mode="wrap")

    val = 0.27 + 0.09 * n1 + 0.04 * (n_pores - 0.5) - 0.07 * streaks
    albedo = np.stack([val, val * 1.01, val * 0.99], axis=-1)

    band = (y >= 620) & (y <= 760)
    stripe = (np.mod(x + y * 1.2, 96.0) < 48.0)
    albedo[band & stripe] = [0.74, 0.58, 0.08]
    albedo[band & (~stripe)] = [0.08, 0.08, 0.10]

    height = 0.55 + 0.30 * n1 + 0.15 * n_pores
    height[band] = 0.72
    metallic = np.zeros((SIZE, SIZE), dtype=np.float32)
    smoothness = np.where(band, 0.78, 0.44 + 0.20 * streaks).astype(np.float32)
    save_pbr_set("UtilityConcrete", albedo, height, metallic, smoothness, normal_strength=2.6, smooth_sigma=0.45)


def gen_ac_unit_metal():
    img = Image.new("RGB", (SIZE, SIZE), (158, 154, 145))
    draw = ImageDraw.Draw(img)
    cx, cy, rad = 340, 512, 260
    draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(24, 26, 30), outline=(88, 85, 78), width=12)
    for r in range(40, rad, 28):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(68, 68, 65), width=5)
    for ly in range(cy - rad + 20, cy + rad - 20, 18):
        draw.line([(cx - rad + 30, ly), (cx + rad - 30, ly)], fill=(105, 102, 95), width=4)
    draw.rectangle([660, 120, 940, 900], outline=(100, 96, 88), width=6)
    draw.rectangle([710, 180, 890, 250], fill=(38, 68, 115))

    alb = np.asarray(img, dtype=np.float32) / 255.0
    grime = fbm_noise((SIZE, SIZE), scales=(8, 16, 32, 64), weights=(0.25, 0.25, 0.25, 0.25), seed=1401)
    streaks = gaussian_filter(grime, sigma=(24.0, 1.5), mode="wrap")
    alb = alb * (0.76 + 0.24 * grime[..., None]) * (1.0 - 0.14 * streaks[..., None])
    height = 0.5 + 0.3 * (np.mean(alb, axis=-1) - 0.5)
    metallic = np.full((SIZE, SIZE), 0.56, dtype=np.float32)
    smoothness = np.clip(0.58 + 0.22 * (1.0 - grime), 0.28, 0.80)
    save_pbr_set("ACUnitMetal", alb, height, metallic, smoothness, normal_strength=2.5, smooth_sigma=0.7)


def gen_shrine_wood_ornament():
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    n1 = fbm_noise((SIZE, SIZE), scales=(4, 8, 16, 32), weights=(0.35, 0.30, 0.20, 0.15), seed=1501)
    n_straw_fiber = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), weights=(0.55, 0.30, 0.15), seed=1502)

    alb = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
    slats = np.sin((x / 32.0) * 2.0 * math.pi) * 0.5 + 0.5
    # Top half (PIL y 0..512 -> v=0.5..1.0): Hinoki wood Saisenbako offering box
    alb[:, :, 0] = 0.24 + 0.08 * slats + 0.04 * n1
    alb[:, :, 1] = 0.16 + 0.05 * slats + 0.03 * n1
    alb[:, :, 2] = 0.09 + 0.03 * slats + 0.02 * n1

    # Middle band (PIL y 512..768 -> v=0.25..0.50): Golden woven rice-straw Shimenawa with individual straw fibers
    weave = np.sin((x + y * 0.8) / 6.5) * 0.5 + 0.5
    straw_detail = weave * 0.65 + n_straw_fiber * 0.35
    straw_mask = (y >= 512) & (y < 768)
    alb[straw_mask, 0] = 0.58 + 0.20 * straw_detail[straw_mask]
    alb[straw_mask, 1] = 0.44 + 0.16 * straw_detail[straw_mask]
    alb[straw_mask, 2] = 0.18 + 0.08 * straw_detail[straw_mask]

    # Bottom band (PIL y 768..1024 -> v=0.00..0.25): Pure white Washi Shide paper (left) & sacred brass (right)
    shide_mask = (y >= 768) & (x < 600)
    alb[shide_mask, 0] = 0.90 + 0.05 * n1[shide_mask]
    alb[shide_mask, 1] = 0.88 + 0.05 * n1[shide_mask]
    alb[shide_mask, 2] = 0.84 + 0.05 * n1[shide_mask]

    brass_mask = (y >= 768) & (x >= 600)
    alb[brass_mask, 0] = 0.78 + 0.10 * n1[brass_mask]
    alb[brass_mask, 1] = 0.60 + 0.08 * n1[brass_mask]
    alb[brass_mask, 2] = 0.22 + 0.04 * n1[brass_mask]

    height = np.where(y < 512, 0.5 + 0.35 * slats, 0.42 + 0.48 * straw_detail).astype(np.float32)
    height[shide_mask] = 0.5 + 0.05 * n1[shide_mask]
    metallic = np.zeros((SIZE, SIZE), dtype=np.float32)
    metallic[brass_mask] = 0.90
    smoothness = np.full((SIZE, SIZE), 0.42, dtype=np.float32)
    smoothness[straw_mask] = 0.24  # fibrous rice straw
    smoothness[brass_mask] = 0.86
    save_pbr_set("ShrineWoodOrnament", alb, height, metallic, smoothness, normal_strength=2.8, smooth_sigma=0.45)


def gen_foliage_bark():
    # Left half (x < 512, u=0..0.5): Deeply furrowed fibrous Japanese Sugi Cedar Bark (杉皮) with moss strips
    # Right half (x >= 512, u=0.5..1.0): Dense dark cedar interior twig/needle mass
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    n1 = fbm_noise((SIZE, SIZE), scales=(4, 8, 16, 32, 64), weights=(0.30, 0.25, 0.20, 0.15, 0.10), seed=1601)
    n_fiber = ridge_noise((SIZE, SIZE), scales=(2, 4, 8), seed=1602)
    strips = np.sin(x / 6.5 + n1 * 2.8) * 0.5 + 0.5
    bark_relief = strips * 0.65 + n_fiber * 0.35

    alb = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
    bark = x < 512
    foliage = x >= 512

    # Subtle green moss growing along vertical bark crevices
    bark_moss = np.clip((1.0 - strips) * (n1 - 0.46) * 2.8, 0.0, 1.0)
    alb[bark, 0] = (0.12 + 0.06 * bark_relief[bark]) * (1.0 - bark_moss[bark]) + 0.05 * bark_moss[bark]
    alb[bark, 1] = (0.08 + 0.04 * bark_relief[bark]) * (1.0 - bark_moss[bark]) + 0.13 * bark_moss[bark]
    alb[bark, 2] = (0.05 + 0.025 * bark_relief[bark]) * (1.0 - bark_moss[bark]) + 0.04 * bark_moss[bark]

    alb[foliage, 0] = 0.025 + 0.025 * n_fiber[foliage]
    alb[foliage, 1] = 0.078 + 0.058 * n_fiber[foliage]
    alb[foliage, 2] = 0.042 + 0.030 * n_fiber[foliage]

    height = np.where(bark, 0.28 + 0.62 * bark_relief, 0.35 + 0.45 * n_fiber).astype(np.float32)
    metallic = np.zeros((SIZE, SIZE), dtype=np.float32)
    smoothness = np.where(bark, 0.36 * (1.0 - bark_moss * 0.6), 0.58).astype(np.float32)
    save_pbr_set("FoliageBark", alb, height, metallic, smoothness, normal_strength=3.2, smooth_sigma=0.45)


def gen_props_atlas():
    # Remember: UV v = 1.0 - (y / SIZE)!
    # Top row in PIL (y: 0..512) == UV v: 0.50..1.00:
    #   - x: 0..256   (u: 0.00..0.25, v: 0.50..1.00): Red Postbox ("〒 POST 郵便")
    #   - x: 256..512 (u: 0.25..0.50, v: 0.50..1.00): Convex Mirror (Orange rim + Chrome Mirror Center)
    #   - x: 512..768 (u: 0.50..0.75, v: 0.50..1.00): Blue Plastic Garbage Bin & Yellow Plastic Beer Crate
    #   - x: 768..1024(u: 0.75..1.00, v: 0.50..1.00): Black Vinyl LDPE Trash Bag with stretch crinkles
    # Bottom row in PIL (y: 512..1024) == UV v: 0.00..0.50:
    #   - x: 0..512   (u: 0.00..0.50, v: 0.00..0.50): Terracotta Plant Pot with efflorescence & wet soil
    #   - x: 512..768 (u: 0.50..0.75, v: 0.00..0.50): Ema Plaque ("帰してください") + Crooked Pole Flyers/Ofuda
    #   - x: 768..1024(u: 0.75..1.00, v: 0.00..0.50): Woven Red Cotton Jizo Cloth Bib ("よだれかけ")
    img = Image.new("RGB", (SIZE, SIZE), (60, 60, 60))
    draw = ImageDraw.Draw(img)
    font_lg = load_jp_font(34)
    font_md = load_jp_font(24)
    font_sm = load_jp_font(18)

    # 1. Red Postbox (x: 0..256, y: 0..512)
    draw.rectangle([0, 0, 256, 512], fill=(162, 24, 22))
    draw.text((48, 160), "〒 郵便", fill=(242, 238, 228), font=font_lg)
    draw.text((62, 220), "POST", fill=(242, 238, 228), font=font_md)

    # 2. Convex Curve Mirror (x: 256..512, y: 0..512)
    draw.rectangle([256, 0, 512, 512], fill=(215, 82, 18))
    draw.ellipse([282, 56, 486, 456], fill=(178, 194, 212), outline=(235, 105, 25), width=16)

    # 3. Blue Garbage Bin (y: 0..280) & Yellow Beer Crate / Amber Bottle (y: 280..512) in x: 512..768
    draw.rectangle([512, 0, 768, 300], fill=(26, 72, 134))
    draw.rectangle([512, 300, 768, 512], fill=(182, 136, 24))
    draw.text((548, 365), "夕霧麦酒", fill=(35, 28, 18), font=font_md)

    # 4. Black Vinyl LDPE Trash Bag (x: 768..1024, y: 0..512)
    draw.rectangle([768, 0, 1024, 512], fill=(18, 20, 24))

    # 5. Terracotta Plant Pot (x: 0..512, y: 512..1024)
    draw.rectangle([0, 512, 512, 1024], fill=(122, 58, 35))

    # 6. Ema Wishing Plaque (y: 512..780) & Weathered Pole Flyer / Talisman (y: 780..1024) in x: 512..768
    draw.rectangle([512, 512, 768, 780], fill=(178, 138, 86))
    draw.text((545, 620), "帰してください", fill=(28, 22, 18), font=font_md)
    draw.rectangle([512, 780, 768, 1024], fill=(215, 208, 192), outline=(60, 55, 50), width=4)
    draw.rectangle([524, 792, 756, 836], fill=(165, 28, 24))
    draw.text((558, 800), "尋 ね 人", fill=(245, 240, 230), font=font_md)
    draw.text((536, 855), "夕霧村字宮前付近にて", fill=(28, 28, 30), font=font_sm)
    draw.text((536, 888), "行方不明・目撃情報求む", fill=(28, 28, 30), font=font_sm)
    draw.text((565, 940), "御嶽神社 厄除札", fill=(140, 24, 22), font=font_md)

    # 7. Woven Red Jizo Cloth Bib (x: 768..1024, y: 512..1024)
    draw.rectangle([768, 512, 1024, 1024], fill=(154, 24, 24))

    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    alb = np.asarray(img, dtype=np.float32) / 255.0
    n1 = fbm_noise((SIZE, SIZE), scales=(8, 16, 32, 64), weights=(0.30, 0.30, 0.25, 0.15), seed=1701)
    n_fine = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), weights=(0.55, 0.30, 0.15), seed=1702)
    alb = alb * (0.82 + 0.18 * n1[..., None])

    # Specific micro-surface heights and roughness per material region!
    height = 0.50 + 0.20 * n1 + 0.08 * n_fine
    metallic = np.full((SIZE, SIZE), 0.10, dtype=np.float32)
    smoothness = np.full((SIZE, SIZE), 0.62, dtype=np.float32)

    # Vinyl trash bag (x: 768..1024, y: 0..512): diagonal tension stretch crinkles + high wet plastic gloss
    bag_mask = (x >= 768) & (y < 512)
    bag_crinkle = ridge_noise((SIZE, SIZE), scales=(4, 8, 16), seed=1703)
    height[bag_mask] = 0.30 + 0.60 * bag_crinkle[bag_mask]
    smoothness[bag_mask] = 0.88 + 0.08 * bag_crinkle[bag_mask]

    # Woven cotton Jizo bib (x: 768..1024, y: 512..1024): fine cross-hatch fabric thread weave & matte cloth roughness
    bib_mask = (x >= 768) & (y >= 512)
    weave_x = np.sin(x * 1.6) * 0.5 + 0.5
    weave_y = np.sin(y * 1.6) * 0.5 + 0.5
    cloth_weave = (weave_x + weave_y) * 0.5
    height[bib_mask] = 0.42 + 0.24 * cloth_weave[bib_mask] + 0.12 * n1[bib_mask]
    smoothness[bib_mask] = 0.18 + 0.06 * n1[bib_mask]
    metallic[bib_mask] = 0.0

    # Terracotta pot (x: 0..512, y: 512..1024): porous unglazed clay with white salt efflorescence band
    pot_mask = (x < 512) & (y >= 512)
    efflor = np.clip((1.0 - np.abs(y - 720.0) / 55.0) * (n1 - 0.35) * 1.8, 0.0, 0.45)
    alb[pot_mask, 0] = np.clip(alb[pot_mask, 0] + efflor[pot_mask] * 0.45, 0.0, 1.0)
    alb[pot_mask, 1] = np.clip(alb[pot_mask, 1] + efflor[pot_mask] * 0.42, 0.0, 1.0)
    alb[pot_mask, 2] = np.clip(alb[pot_mask, 2] + efflor[pot_mask] * 0.38, 0.0, 1.0)
    smoothness[pot_mask] = 0.34 + 0.22 * n1[pot_mask]

    # Convex mirror glass (x: 286..482, y: 60..452): chrome mirror reflection
    mirror_glass = ((x - 384.0) ** 2 / (96.0 ** 2) + (y - 256.0) ** 2 / (190.0 ** 2)) < 0.85
    metallic[mirror_glass] = 0.95
    smoothness[mirror_glass] = 0.96
    height[mirror_glass] = 0.50

    save_pbr_set("PropsAtlas", alb, height, metallic, smoothness, normal_strength=2.6, smooth_sigma=0.45)


def gen_foliage_leaf_cutout():
    """
    Generate a 1024x1024 RGBA Alpha-Cutout Botanical Atlas ('FoliageLeafCutout') so every individual
    leaf, serrated fern pinna, Sugi cedar needle, and wild grass blade is razor-sharp!
    Remember: PIL y=0..512 corresponds to Blender UV v=0.5..1.0; PIL y=512..1024 corresponds to UV v=0.0..0.5.
      - Q1 Top-Left  (x: 0..512,   y: 0..512   -> u: 0.0..0.5, v: 0.5..1.0): Japanese Woodland Fern Frond (シダ)
      - Q2 Top-Right (x: 512..1024,y: 0..512   -> u: 0.5..1.0, v: 0.5..1.0): Sugi Cedar Needle Branch Spray (杉の葉枝)
      - Q3 Bot-Left  (x: 0..512,   y: 512..1024-> u: 0.0..0.5, v: 0.0..0.5): Veined Hosta / Broadleaf (ギボウシ・ドクダミ)
      - Q4 Bot-Right (x: 512..1024,y: 512..1024-> u: 0.5..1.0, v: 0.0..0.5): Wild Alley Grass & Sedge Blades (雑草)
    """
    y, x = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    alb = np.zeros((SIZE, SIZE, 3), dtype=np.float32)
    alpha = np.zeros((SIZE, SIZE), dtype=np.float32)
    height = np.full((SIZE, SIZE), 0.35, dtype=np.float32)
    smoothness = np.full((SIZE, SIZE), 0.72, dtype=np.float32)

    n_organic = fbm_noise((SIZE, SIZE), scales=(4, 8, 16, 32), weights=(0.35, 0.30, 0.20, 0.15), seed=1901)
    n_droplets = fbm_noise((SIZE, SIZE), scales=(1, 2, 4), weights=(0.60, 0.25, 0.15), seed=1902)
    droplet_mask = np.clip((n_droplets - 0.74) * 5.0, 0.0, 1.0)

    # Pre-fill RGB background with dark botanical green so mipmap/bilinear edge bleeding never shows black/white halos!
    alb[:, :, 0] = 0.045 + 0.02 * n_organic
    alb[:, :, 1] = 0.125 + 0.04 * n_organic
    alb[:, :, 2] = 0.040 + 0.02 * n_organic

    # =========================================================================
    # Q1: Top-Left (x: 0..512, y: 0..512 -> UV u: 0.0..0.5, v: 0.5..1.0)
    # Japanese Woodland Fern Frond (シダ) - Base at bottom (y=495, v=0.515), tip at top (y=24, v=0.976)
    # =========================================================================
    q1_y = y[:512, :512]
    q1_x = x[:512, :512]
    # Normalized frond axis t: 0 at base (y=496) -> 1 at tip (y=20)
    t_fern = np.clip((496.0 - q1_y) / 476.0, 0.0, 1.0)
    stem_cx = 256.0 + 10.0 * np.sin(t_fern * math.pi * 1.2)
    dx_fern = q1_x - stem_cx

    # Central rachis (stem)
    stem_half_w = 4.2 * (1.0 - 0.65 * t_fern)
    rachis_mask = (np.abs(dx_fern) <= stem_half_w) & (q1_y >= 20) & (q1_y <= 504)

    # 15 pairs of serrated pinnae (leaflets) branching left & right
    pinna_mask = np.zeros((512, 512), dtype=np.float32)
    pinna_vein = np.zeros((512, 512), dtype=np.float32)
    pinna_age = np.zeros((512, 512), dtype=np.float32)

    for p_idx in range(16):
        tp = 0.05 + p_idx * 0.058
        if tp >= 0.96:
            continue
        py_base = 496.0 - tp * 476.0
        max_len = 215.0 * math.sin(tp * math.pi * 0.88) * (1.0 - 0.18 * tp)
        if max_len < 18.0:
            continue
        for side in (-1.0, 1.0):
            # Alternating slight offset between left and right pinnae
            py0 = py_base - (3.5 if side > 0 else -3.5)
            px0 = 256.0 + 10.0 * math.sin(tp * math.pi * 1.2)
            # Local coordinates along the pinna axis (angled upward by ~22 degrees)
            ang = -0.36 * side
            ca, sa = math.cos(ang), math.sin(ang)
            rx = (q1_x - px0) * side
            ry = q1_y - py0
            u_p = rx * ca - ry * sa * side
            v_p = rx * sa * side + ry * ca
            s_p = u_p / max_len
            valid = ((s_p >= 0.0) & (s_p <= 1.0)).astype(np.float32)
            s_p_clamped = np.clip(s_p, 0.0, 1.0)
            # Serrated pinnule lobes along each pinna!
            lobe_wave = 1.0 + 0.34 * np.cos(s_p_clamped * 11.0 * math.pi)
            sin_val = np.maximum(0.0, np.sin(s_p_clamped * math.pi))
            half_w = (15.5 * (1.0 - 0.25 * tp)) * (sin_val ** 0.65) * lobe_wave
            inside = (valid > 0.5) & (np.abs(v_p) <= half_w)
            edge_soft = np.clip((half_w - np.abs(v_p)) / 1.5, 0.0, 1.0) * valid
            pinna_mask = np.maximum(pinna_mask, edge_soft)
            vein = np.clip(1.0 - np.abs(v_p) / 2.2, 0.0, 1.0) * inside
            pinna_vein = np.maximum(pinna_vein, vein)
            pinna_age = np.maximum(pinna_age, np.clip((s_p_clamped - 0.72) * 3.5, 0.0, 1.0) * inside)

    q1_alpha = np.clip(pinna_mask + rachis_mask.astype(np.float32), 0.0, 1.0)
    alpha[:512, :512] = q1_alpha
    # Color: rich forest chlorophyll green, lighter yellow-green along midrib veins, rusty-brown spore tips
    alb[:512, :512, 0] = 0.048 + 0.055 * pinna_vein + 0.14 * pinna_age + 0.03 * n_organic[:512, :512]
    alb[:512, :512, 1] = 0.145 + 0.085 * pinna_vein - 0.04 * pinna_age + 0.05 * n_organic[:512, :512]
    alb[:512, :512, 2] = 0.038 + 0.025 * pinna_vein - 0.02 * pinna_age + 0.02 * n_organic[:512, :512]
    height[:512, :512] = 0.35 + 0.32 * q1_alpha + 0.22 * pinna_vein + 0.18 * droplet_mask[:512, :512] * q1_alpha
    smoothness[:512, :512] = (0.68 + 0.26 * droplet_mask[:512, :512]) * q1_alpha

    # =========================================================================
    # Q2: Top-Right (x: 512..1024, y: 0..512 -> UV u: 0.5..1.0, v: 0.5..1.0)
    # Japanese Sugi Cedar Needle Branch Spray (杉の葉枝) - Hundreds of individual curved awl needles!
    # =========================================================================
    cedar_img = Image.new("L", (512, 512), 0)
    cedar_twig = Image.new("L", (512, 512), 0)
    cedar_h = Image.new("L", (512, 512), 90)
    d_alpha = ImageDraw.Draw(cedar_img)
    d_twig = ImageDraw.Draw(cedar_twig)
    d_h = ImageDraw.Draw(cedar_h)

    rng_cedar = np.random.default_rng(1905)
    # 7 branching sub-shoots radiating from bottom-center (256, 500) to top (256, 18)
    shoots = [
        [(256, 502), (254, 360), (258, 200), (256, 22)],
        [(255, 445), (195, 345), (135, 225), (85, 110)],
        [(257, 430), (315, 330), (378, 215), (430, 105)],
        [(254, 320), (185, 230), (120, 130), (68, 48)],
        [(258, 305), (325, 215), (390, 120), (442, 42)],
        [(195, 345), (175, 260), (160, 165)],
        [(315, 330), (338, 245), (355, 150)],
    ]
    for path in shoots:
        # Interpolate points along shoot and draw dense curved awl-shaped Sugi needles
        pts = []
        for idx in range(len(path) - 1):
            x0, y0 = path[idx]
            x1, y1 = path[idx + 1]
            steps = 28
            for s in range(steps):
                f = s / float(steps)
                pts.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, math.atan2(y1 - y0, x1 - x0)))
        for idx, (px, py, tang) in enumerate(pts):
            # Woody central twig
            tw_w = max(2, int(5 * (1.0 - idx / max(1, len(pts)))))
            d_alpha.ellipse([px - tw_w, py - tw_w, px + tw_w, py + tw_w], fill=255)
            d_twig.ellipse([px - tw_w, py - tw_w, px + tw_w, py + tw_w], fill=230)
            d_h.ellipse([px - tw_w, py - tw_w, px + tw_w, py + tw_w], fill=210)
            # Pair of forward-curving awl needles every step
            for side in (-1.0, 1.0):
                n_ang = tang + side * (0.48 + rng_cedar.uniform(-0.12, 0.14))
                n_len = rng_cedar.uniform(22.0, 36.0) * (1.0 - 0.25 * (idx / max(1, len(pts))))
                mx = px + math.cos(n_ang + side * 0.12) * (n_len * 0.55)
                my = py + math.sin(n_ang + side * 0.12) * (n_len * 0.55)
                tx = px + math.cos(n_ang - side * 0.08) * n_len
                ty = py + math.sin(n_ang - side * 0.08) * n_len
                nx_perp = -math.sin(n_ang) * 2.6
                ny_perp = math.cos(n_ang) * 2.6
                poly = [
                    (px - nx_perp, py - ny_perp),
                    (mx - nx_perp * 0.7, my - ny_perp * 0.7),
                    (tx, ty),
                    (mx + nx_perp * 0.7, my + ny_perp * 0.7),
                    (px + nx_perp, py + ny_perp),
                ]
                d_alpha.polygon(poly, fill=255)
                h_val = int(rng_cedar.integers(145, 245))
                d_h.polygon(poly, fill=h_val)

    q2_alpha = np.asarray(cedar_img, dtype=np.float32) / 255.0
    q2_twig = np.asarray(cedar_twig, dtype=np.float32) / 255.0
    q2_h = np.asarray(cedar_h, dtype=np.float32) / 255.0
    alpha[:512, 512:] = q2_alpha
    alb[:512, 512:, 0] = (0.032 + 0.030 * q2_h + 0.02 * n_organic[:512, 512:]) * (1.0 - q2_twig) + 0.16 * q2_twig
    alb[:512, 512:, 1] = (0.088 + 0.068 * q2_h + 0.03 * n_organic[:512, 512:]) * (1.0 - q2_twig) + 0.10 * q2_twig
    alb[:512, 512:, 2] = (0.045 + 0.035 * q2_h + 0.02 * n_organic[:512, 512:]) * (1.0 - q2_twig) + 0.06 * q2_twig
    height[:512, 512:] = 0.25 + 0.58 * q2_h + 0.16 * droplet_mask[:512, 512:] * q2_alpha
    smoothness[:512, 512:] = (0.64 + 0.28 * droplet_mask[:512, 512:]) * q2_alpha

    # =========================================================================
    # Q3: Bottom-Left (x: 0..512, y: 512..1024 -> UV u: 0.0..0.5, v: 0.0..0.5)
    # Cordate/Ovate Broadleaf (Hosta / Giboshi / Dokudami) with arcuate veins, serrated margin & bug hole!
    # =========================================================================
    q3_y = y[512:, :512] - 512.0
    q3_x = x[512:, :512]
    # Petiole stem from bottom (y=502) to leaf base (y=420), leaf blade from y=430 to tip y=28
    t_leaf = np.clip((435.0 - q3_y) / 405.0, 0.0, 1.0)
    dx_leaf = (q3_x - 256.0) / 185.0
    # Heart/ovate contour with fine marginal serration
    ang_leaf = np.arctan2(q3_y - 265.0, q3_x - 256.0)
    serration = 0.035 * np.sin(ang_leaf * 38.0) * (1.0 - t_leaf * 0.5)
    target_w = np.maximum(0.0, np.sin((t_leaf ** 0.62) * math.pi)) * (1.0 + 0.18 * (1.0 - t_leaf)) + serration
    blade_dist = target_w - np.abs(dx_leaf)
    blade_mask = np.clip(blade_dist * 24.0, 0.0, 1.0) * ((q3_y >= 26) & (q3_y <= 438))
    petiole_mask = np.clip((6.5 - np.abs(q3_x - 256.0)) / 1.5, 0.0, 1.0) * ((q3_y >= 410) & (q3_y <= 504))

    # Realistic insect-chewed hole (虫食い穴) on one side of the leaf!
    bug_hole1 = ((q3_x - 182.0) ** 2 + (q3_y - 235.0) ** 2) < (16.0 ** 2)
    bug_hole2 = ((q3_x - 328.0) ** 2 + (q3_y - 165.0) ** 2) < (11.0 ** 2)
    q3_alpha = np.clip(blade_mask + petiole_mask, 0.0, 1.0)
    q3_alpha[bug_hole1 | bug_hole2] = 0.0

    # Primary midrib + 7 pairs of arcuate lateral veins (Giboshi parallel-arc venation)
    midrib = np.clip(1.0 - np.abs(q3_x - 256.0) / (5.5 * (1.0 - 0.65 * t_leaf) + 1.2), 0.0, 1.0) * blade_mask
    lat_veins = np.clip(np.cos((np.maximum(0.0, np.abs(dx_leaf)) ** 0.78 * 6.5 - t_leaf * 2.2) * math.pi) ** 12, 0.0, 1.0) * blade_mask
    vein_total = np.clip(midrib + lat_veins * 0.75, 0.0, 1.0)

    # Brownish necrotic rim right around the insect chew holes!
    hole_rim = (
        np.exp(-(((q3_x - 182.0) ** 2 + (q3_y - 235.0) ** 2 - 256.0) ** 2) / 18000.0)
        + np.exp(-(((q3_x - 328.0) ** 2 + (q3_y - 165.0) ** 2 - 121.0) ** 2) / 9000.0)
    ) * q3_alpha

    alpha[512:, :512] = q3_alpha
    alb[512:, :512, 0] = (0.045 + 0.065 * vein_total + 0.18 * hole_rim + 0.03 * n_organic[512:, :512])
    alb[512:, :512, 1] = (0.145 + 0.095 * vein_total - 0.04 * hole_rim + 0.05 * n_organic[512:, :512])
    alb[512:, :512, 2] = (0.042 + 0.030 * vein_total - 0.02 * hole_rim + 0.02 * n_organic[512:, :512])
    # Leaf cushions puff up between sunken veins, plus raised rainwater droplets!
    height[512:, :512] = (0.55 - 0.24 * lat_veins + 0.18 * midrib + 0.25 * droplet_mask[512:, :512]) * q3_alpha
    smoothness[512:, :512] = (0.76 + 0.22 * droplet_mask[512:, :512]) * q3_alpha

    # =========================================================================
    # Q4: Bottom-Right (x: 512..1024, y: 512..1024 -> UV u: 0.5..1.0, v: 0.0..0.5)
    # Wild Alley Grass & Sedge Blades (雑草・カヤツリグサ) - 11 sharp arching individual blades
    # =========================================================================
    q4_y = y[512:, 512:] - 512.0
    q4_x = x[512:, 512:] - 512.0
    t_grass = np.clip((504.0 - q4_y) / 485.0, 0.0, 1.0)
    grass_alpha = np.zeros((512, 512), dtype=np.float32)
    grass_ridge = np.zeros((512, 512), dtype=np.float32)
    grass_tint = np.zeros((512, 512), dtype=np.float32)

    blade_specs = [
        (256.0, 0.0, 0.96, 13.0, 0.0),
        (235.0, -55.0, 0.92, 12.0, 0.2),
        (278.0, 62.0, 0.90, 12.0, -0.1),
        (215.0, -118.0, 0.84, 11.0, 0.4),
        (296.0, 125.0, 0.86, 11.5, 0.1),
        (195.0, -172.0, 0.76, 10.5, 0.6),
        (318.0, 178.0, 0.78, 10.5, 0.3),
        (246.0, -28.0, 0.88, 10.0, -0.2),
        (268.0, 32.0, 0.85, 10.0, 0.5),
        (178.0, -210.0, 0.66, 9.5, 0.8),
        (336.0, 212.0, 0.68, 9.5, 0.7),
    ]
    for bx0, bend, max_h, bw, tint_off in blade_specs:
        s_b = np.clip(t_grass / max_h, 0.0, 1.0)
        valid = ((t_grass >= 0.0) & (t_grass <= max_h)).astype(np.float32)
        cx_b = bx0 + bend * (s_b ** 1.65)
        hw = bw * (1.0 - s_b ** 1.35) * np.clip(s_b * 12.0, 0.35, 1.0)
        dist = np.abs(q4_x - cx_b)
        b_mask = np.clip((hw - dist) / 1.4, 0.0, 1.0) * valid
        b_ridge = np.clip(1.0 - dist / (hw + 1e-4), 0.0, 1.0) * b_mask
        higher = b_mask > grass_alpha
        grass_alpha = np.maximum(grass_alpha, b_mask)
        grass_ridge = np.where(higher, b_ridge, grass_ridge)
        grass_tint = np.where(higher, tint_off + 0.4 * (s_b ** 2), grass_tint)

    alpha[512:, 512:] = grass_alpha
    alb[512:, 512:, 0] = 0.045 + 0.045 * grass_ridge + 0.045 * grass_tint
    alb[512:, 512:, 1] = 0.135 + 0.085 * grass_ridge + 0.020 * grass_tint
    alb[512:, 512:, 2] = 0.036 + 0.025 * grass_ridge
    height[512:, 512:] = (0.35 + 0.45 * grass_ridge + 0.18 * droplet_mask[512:, 512:]) * grass_alpha
    smoothness[512:, 512:] = (0.70 + 0.24 * droplet_mask[512:, 512:]) * grass_alpha

    metallic = np.zeros((SIZE, SIZE), dtype=np.float32)
    ao = np.clip(0.55 + 0.45 * height, 0.35, 1.0)
    save_pbr_set(
        "FoliageLeafCutout",
        alb,
        height,
        metallic,
        smoothness,
        ao_map=ao,
        albedo_alpha=alpha,
        normal_strength=3.0,
        smooth_sigma=0.45,
    )


def main():
    print("Generating soul-crafted 1K PBR texture sets (including RGBA Alpha-Cutout Botanical Atlas)...")
    gen_wet_asphalt()
    gen_stone_paving()
    gen_concrete_wall()
    gen_dark_wood()
    gen_aged_plaster()
    gen_kawara_tile()
    gen_rusted_metal()
    gen_shoji_windows()
    gen_torii_vermilion()
    gen_mossy_granite()
    gen_vending_machine_front()
    gen_shop_shutter_sign()
    gen_utility_concrete()
    gen_ac_unit_metal()
    gen_shrine_wood_ornament()
    gen_foliage_bark()
    gen_props_atlas()
    gen_foliage_leaf_cutout()
    print(f"All 19 PBR texture sets saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
