import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix, Euler
from pathlib import Path

MODELS_DIR = Path(r"c:\Users\gksix\Downloads\새 폴더 (2)\YugiriVillage\Assets\Models")
TEX_DIR = Path(r"c:\Users\gksix\Downloads\새 폴더 (2)\YugiriVillage\Assets\Textures")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MAT_NAMES = [
    "WetAsphalt",
    "StonePaving",
    "ConcreteWall",
    "DarkWood",
    "AgedPlaster",
    "KawaraTile",
    "RustedMetal",
    "ShojiWindow",
    "ShojiWindowEerie",
    "ToriiVermilion",
    "MossyGranite",
    "VendingMachineFront",
    "ShopShutterSign",
    "UtilityConcrete",
    "ACUnitMetal",
    "ShrineWoodOrnament",
    "FoliageBark",
    "PropsAtlas",
    "FoliageLeafCutout",
]

MATERIALS = {}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.meshes):
        if m.users == 0:
            bpy.data.meshes.remove(m)


def init_materials():
    MATERIALS.clear()
    for name in MAT_NAMES:
        mat_name = f"Mat_{name}"
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            alb_path = TEX_DIR / f"{name}_Albedo.png"
            if alb_path.exists():
                tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
                tex_node.image = bpy.data.images.load(str(alb_path), check_existing=True)
                mat.node_tree.links.new(bsdf.inputs["Base Color"], tex_node.outputs["Color"])
                if name == "FoliageLeafCutout" and "Alpha" in bsdf.inputs:
                    mat.node_tree.links.new(bsdf.inputs["Alpha"], tex_node.outputs["Alpha"])
        MATERIALS[name] = mat


def apply_box_uvs(bm, faces, center, size, mat_idx, uv_scale=1.0, uv_rect=None):
    cx, cy, cz = center
    sx, sy, sz = max(1e-4, size[0]), max(1e-4, size[1]), max(1e-4, size[2])
    uv_layer = bm.loops.layers.uv.verify()
    for f in faces:
        f.material_index = mat_idx
        n = f.normal
        for loop in f.loops:
            co = loop.vert.co
            if uv_rect is not None:
                u0, v0, u1, v1 = uv_rect
                if abs(n.y) >= abs(n.x) and abs(n.y) >= abs(n.z):
                    lu = min(1.0, max(0.0, (co.x - (cx - sx * 0.5)) / sx))
                    lv = min(1.0, max(0.0, (co.z - (cz - sz * 0.5)) / sz))
                elif abs(n.x) >= abs(n.y) and abs(n.x) >= abs(n.z):
                    lu = min(1.0, max(0.0, (co.y - (cy - sy * 0.5)) / sy))
                    lv = min(1.0, max(0.0, (co.z - (cz - sz * 0.5)) / sz))
                else:
                    lu = min(1.0, max(0.0, (co.x - (cx - sx * 0.5)) / sx))
                    lv = min(1.0, max(0.0, (co.y - (cy - sy * 0.5)) / sy))
                loop[uv_layer].uv = (u0 + lu * (u1 - u0), v0 + lv * (v1 - v0))
            else:
                if abs(n.z) > 0.7:
                    loop[uv_layer].uv = (co.x * uv_scale, co.y * uv_scale)
                elif abs(n.x) > 0.7:
                    loop[uv_layer].uv = (co.y * uv_scale, co.z * uv_scale)
                else:
                    loop[uv_layer].uv = (co.x * uv_scale, co.z * uv_scale)


def add_box(bm, center, size, mat_idx=0, uv_scale=1.0, uv_rect=None, bevel=0.0, bevel_segs=2, rot_euler=(0, 0, 0)):
    cx, cy, cz = center
    sx, sy, sz = size
    ret = bmesh.ops.create_cube(bm, size=1.0)
    verts = ret["verts"]
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=verts)

    v_set = set(verts)
    box_edges = [e for e in bm.edges if all(v in v_set for v in e.verts)]
    min_dim = min(sx, sy, sz)
    eff_bevel = bevel if bevel > 0.0 else min(0.012, min_dim * 0.14)
    if eff_bevel > 0.0015 and uv_rect is None:
        try:
            b_ret = bmesh.ops.bevel(
                bm,
                geom=box_edges,
                offset=eff_bevel,
                offset_type="OFFSET",
                segments=bevel_segs,
                profile=0.5,
                affect="EDGES",
            )
            v_set = set(v for v in b_ret.get("verts", []) if v.is_valid)
        except Exception:
            v_set = set(v for v in v_set if v.is_valid)

    valid_verts = [v for v in v_set if v.is_valid]
    if any(rot_euler):
        rot_mat = Euler(rot_euler, "XYZ").to_matrix()
        bmesh.ops.rotate(bm, matrix=rot_mat, verts=valid_verts)
    bmesh.ops.translate(bm, vec=(cx, cy, cz), verts=valid_verts)

    faces = [f for f in bm.faces if f.is_valid and all(v in v_set for v in f.verts)]
    for f in faces:
        f.smooth = (uv_rect is None and eff_bevel > 0.0015)
    apply_box_uvs(bm, faces, center, size, mat_idx, uv_scale=uv_scale, uv_rect=uv_rect)
    return list(v_set)


def add_cylinder(
    bm,
    center,
    radius_bottom,
    radius_top,
    height,
    segments=32,
    mat_idx=0,
    uv_scale=1.0,
    rot_euler=(0, 0, 0),
    uv_rect=None,
    smooth=True,
):
    ret = bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius_bottom,
        radius2=radius_top,
        depth=height,
    )
    verts = ret["verts"]
    v_set = set(verts)
    uv_layer = bm.loops.layers.uv.verify()
    max_r = max(0.02, radius_bottom, radius_top)

    for f in bm.faces:
        if all(v in v_set for v in f.verts):
            f.material_index = mat_idx
            is_cap = abs(f.normal.z) > 0.85
            f.smooth = (smooth and not is_cap)
            for loop in f.loops:
                co = loop.vert.co
                if is_cap:
                    lu = min(1.0, max(0.0, (co.x / (2.0 * max_r)) + 0.5))
                    lv = min(1.0, max(0.0, (co.y / (2.0 * max_r)) + 0.5))
                else:
                    ang = math.atan2(co.y, co.x)
                    lu = (ang / (2.0 * math.pi)) + 0.5
                    lv = min(1.0, max(0.0, (co.z / max(0.05, height)) + 0.5))
                if uv_rect is not None:
                    u0, v0, u1, v1 = uv_rect
                    loop[uv_layer].uv = (u0 + lu * (u1 - u0), v0 + lv * (v1 - v0))
                else:
                    loop[uv_layer].uv = (lu * uv_scale * 2.0, lv * uv_scale)

    if any(rot_euler):
        rot_mat = Euler(rot_euler, "XYZ").to_matrix()
        bmesh.ops.rotate(bm, matrix=rot_mat, verts=verts)
    bmesh.ops.translate(bm, vec=center, verts=verts)
    return verts


def add_sphere(bm, center, radius, scale=(1.0, 1.0, 1.0), u_segs=28, v_segs=18, mat_idx=0, uv_scale=1.0, uv_rect=None):
    ret = bmesh.ops.create_uvsphere(bm, u_segments=u_segs, v_segments=v_segs, radius=radius)
    verts = ret["verts"]
    bmesh.ops.scale(bm, vec=scale, verts=verts)
    v_set = set(verts)
    uv_layer = bm.loops.layers.uv.verify()

    for f in bm.faces:
        if all(v in v_set for v in f.verts):
            f.material_index = mat_idx
            f.smooth = True
            for loop in f.loops:
                co = loop.vert.co
                ang = math.atan2(co.y, co.x)
                lu = (ang / (2.0 * math.pi)) + 0.5
                lv = min(1.0, max(0.0, (co.z / max(0.02, 2.0 * radius * scale[2])) + 0.5))
                if uv_rect is not None:
                    u0, v0, u1, v1 = uv_rect
                    loop[uv_layer].uv = (u0 + lu * (u1 - u0), v0 + lv * (v1 - v0))
                else:
                    loop[uv_layer].uv = (lu * uv_scale, lv * uv_scale)

    bmesh.ops.translate(bm, vec=center, verts=verts)
    return verts


def add_torus(bm, center, major_r, minor_r, major_segs=40, minor_segs=14, mat_idx=0, rot_euler=(0, 0, 0), uv_scale=1.0, uv_rect=None):
    uv_layer = bm.loops.layers.uv.verify()
    grid = []
    for i in range(major_segs):
        u_ang = (i / major_segs) * 2.0 * math.pi
        cu, su = math.cos(u_ang), math.sin(u_ang)
        ring = []
        for j in range(minor_segs):
            v_ang = (j / minor_segs) * 2.0 * math.pi
            cv, sv = math.cos(v_ang), math.sin(v_ang)
            r = major_r + minor_r * cv
            v = bm.verts.new((r * cu, r * su, minor_r * sv))
            ring.append(v)
        grid.append(ring)

    all_verts = [v for ring in grid for v in ring]
    for i in range(major_segs):
        i_next = (i + 1) % major_segs
        for j in range(minor_segs):
            j_next = (j + 1) % minor_segs
            v00 = grid[i][j]
            v10 = grid[i_next][j]
            v11 = grid[i_next][j_next]
            v01 = grid[i][j_next]
            f = bm.faces.new((v00, v10, v11, v01))
            f.material_index = mat_idx
            f.smooth = True
            for k, loop in enumerate(f.loops):
                lu = (i + (1 if k in (1, 2) else 0)) / major_segs
                lv = (j + (1 if k in (2, 3) else 0)) / minor_segs
                if uv_rect is not None:
                    u0, v0, u1, v1 = uv_rect
                    loop[uv_layer].uv = (u0 + lu * (u1 - u0), v0 + lv * (v1 - v0))
                else:
                    loop[uv_layer].uv = (lu * uv_scale * 4.0, lv * uv_scale)

    if any(rot_euler):
        rot_mat = Euler(rot_euler, "XYZ").to_matrix()
        bmesh.ops.rotate(bm, matrix=rot_mat, verts=all_verts)
    bmesh.ops.translate(bm, vec=center, verts=all_verts)
    return all_verts


# UV Rects for the 4 quadrants of FoliageLeafCutout_Albedo.png:
# Q1 (Top-Left): Japanese Woodland Fern Frond (シダ)
UV_FERN_FROND = (0.01, 0.51, 0.49, 0.99)
# Q2 (Top-Right): Sugi Cedar Needle Branch Spray (杉の葉枝)
UV_CEDAR_SPRAY = (0.51, 0.51, 0.99, 0.99)
# Q3 (Bottom-Left): Veined Broadleaf Hosta/Dokudami with tiny bug hole (ギボウシ)
UV_BROADLEAF = (0.01, 0.01, 0.49, 0.49)
# Q4 (Bottom-Right): Wild Alley Grass & Sedge Blades (雑草)
UV_WILD_GRASS = (0.51, 0.01, 0.99, 0.49)


def add_curved_leaf_card(
    bm,
    base_pos,
    length,
    width,
    yaw=0.0,
    pitch=0.65,
    arch_droop=0.14,
    v_fold=0.025,
    roll=0.0,
    mat_idx=0,
    uv_rect=UV_FERN_FROND,
    segs_l=5,
    segs_w=2,
):
    """
    Create a true 3D multi-segment arched and V-creased botanical leaf/frond mesh.
    Base is at local (0,0,0), extending along +Y with upward pitch and natural gravity droop.
    """
    uv_layer = bm.loops.layers.uv.verify()
    u0, v0, u1, v1 = uv_rect
    grid = []
    for il in range(segs_l + 1):
        tl = il / float(segs_l)
        # Arched spine in local Y-Z plane
        y_loc = tl * length * math.cos(pitch * (1.0 - 0.35 * tl))
        z_loc = tl * length * math.sin(pitch) - (tl ** 2.1) * arch_droop
        row = []
        for iw in range(segs_w + 1):
            tw = (iw / float(segs_w)) - 0.5
            x_loc = tw * width
            # Natural V-channel midrib crease along center of frond/leaf
            z_crease = abs(tw * 2.0) * v_fold * (1.0 - 0.4 * tl)
            v = bm.verts.new((x_loc, y_loc, z_loc + z_crease))
            row.append(v)
        grid.append(row)

    all_verts = [v for row in grid for v in row]
    rot_mat = Euler((0.0, roll, yaw), "XYZ").to_matrix()
    bmesh.ops.rotate(bm, matrix=rot_mat, verts=all_verts)
    bmesh.ops.translate(bm, vec=base_pos, verts=all_verts)

    for il in range(segs_l):
        for iw in range(segs_w):
            v00 = grid[il][iw]
            v10 = grid[il][iw + 1]
            v11 = grid[il + 1][iw + 1]
            v01 = grid[il + 1][iw]
            f = bm.faces.new((v00, v10, v11, v01))
            f.material_index = mat_idx
            f.smooth = True
            uvs = [
                (iw / float(segs_w), il / float(segs_l)),
                ((iw + 1) / float(segs_w), il / float(segs_l)),
                ((iw + 1) / float(segs_w), (il + 1) / float(segs_l)),
                (iw / float(segs_w), (il + 1) / float(segs_l)),
            ]
            for k, loop in enumerate(f.loops):
                lu, lv = uvs[k]
                loop[uv_layer].uv = (u0 + lu * (u1 - u0), v0 + lv * (v1 - v0))
    return all_verts


def add_fern_and_weed_rosette(bm, center, scale=1.0, seed=101, mat_idx=0, include_ferns=True, include_broadleaf=True, include_grass=True):
    """
    Build a rich multi-species 3D botanical cluster (woodland ferns, veined Hosta broadleaves, and wild grass blades)
    where every individual leaf and leaflet is distinct in 3D space.
    """
    cx, cy, cz = center
    rng = random.Random(seed)
    if include_ferns:
        n_fronds = 11
        for i in range(n_fronds):
            yaw = (i / float(n_fronds)) * 2.0 * math.pi + rng.uniform(-0.22, 0.22)
            tier = i % 3
            length = (0.34 + 0.08 * tier + rng.uniform(-0.04, 0.05)) * scale
            width = length * 0.56
            pitch = 0.32 + 0.24 * (2 - tier) + rng.uniform(-0.08, 0.08)
            droop = length * (0.38 + 0.12 * tier)
            roll = rng.uniform(-0.18, 0.18)
            add_curved_leaf_card(
                bm,
                (cx + math.sin(yaw) * 0.02 * scale, cy + math.cos(yaw) * 0.02 * scale, cz),
                length=length,
                width=width,
                yaw=yaw,
                pitch=pitch,
                arch_droop=droop,
                v_fold=0.022 * scale,
                roll=roll,
                mat_idx=mat_idx,
                uv_rect=UV_FERN_FROND,
                segs_l=5,
                segs_w=2,
            )
    if include_broadleaf:
        n_leaves = 7
        for i in range(n_leaves):
            yaw = (i / float(n_leaves)) * 2.0 * math.pi + 0.45 + rng.uniform(-0.25, 0.25)
            length = rng.uniform(0.18, 0.28) * scale
            width = length * 0.85
            pitch = rng.uniform(0.28, 0.68)
            add_curved_leaf_card(
                bm,
                (cx + rng.uniform(-0.04, 0.04) * scale, cy + rng.uniform(-0.04, 0.04) * scale, cz + 0.01 * scale),
                length=length,
                width=width,
                yaw=yaw,
                pitch=pitch,
                arch_droop=length * 0.30,
                v_fold=-0.018 * scale,
                roll=rng.uniform(-0.15, 0.15),
                mat_idx=mat_idx,
                uv_rect=UV_BROADLEAF,
                segs_l=4,
                segs_w=2,
            )
    if include_grass:
        n_tufts = 6
        for i in range(n_tufts):
            yaw = (i / float(n_tufts)) * math.pi + rng.uniform(-0.3, 0.3)
            h = rng.uniform(0.22, 0.36) * scale
            w = h * 0.85
            add_curved_leaf_card(
                bm,
                (cx + rng.uniform(-0.06, 0.06) * scale, cy + rng.uniform(-0.06, 0.06) * scale, cz),
                length=h,
                width=w,
                yaw=yaw,
                pitch=rng.uniform(0.95, 1.32),
                arch_droop=h * 0.22,
                v_fold=0.03 * scale,
                roll=rng.uniform(-0.1, 0.1),
                mat_idx=mat_idx,
                uv_rect=UV_WILD_GRASS,
                segs_l=4,
                segs_w=2,
            )


def add_architectural_gutter_and_downspout(bm, eave_x0, eave_x1, eave_y, eave_z, down_x, wall_y, ground_z, mat_idx):
    """
    Authentic Japanese architectural rain gutter & wall-clamped downspout system (雨樋 - Amadoi):
    - Horizontal eave gutter trough (軒樋 - Nokidoi) along the eave edge with metal support brackets every 0.65m,
    - Corner rainwater collector funnel box (集水器 - Shusuiki),
    - Angled S-bend elbow pipe (呼び樋 - Yobidoi) routing rainwater back from the eave to the building wall corner,
    - Vertical downspout pipe (竪樋 - Tategoi) clamped tightly against the building wall with metal standoff rings (控え金具)
      and an angled drainage boot at the bottom!
    """
    gutter_w = abs(eave_x1 - eave_x0)
    gutter_cx = 0.5 * (eave_x0 + eave_x1)
    # Horizontal eave gutter trough (軒樋)
    add_cylinder(
        bm,
        (gutter_cx, eave_y, eave_z),
        0.032,
        0.032,
        gutter_w,
        segments=16,
        mat_idx=mat_idx,
        rot_euler=(0, math.pi * 0.5, 0),
    )
    # Gutter support brackets (軒樋金具)
    n_brackets = max(4, int(gutter_w / 0.65))
    for i in range(n_brackets):
        bx = eave_x0 + 0.12 + (i / float(max(1, n_brackets - 1))) * (gutter_w - 0.24)
        add_torus(bm, (bx, eave_y, eave_z), 0.035, 0.005, major_segs=16, minor_segs=6, mat_idx=mat_idx, rot_euler=(0, math.pi * 0.5, 0))

    # Collector funnel (集水器) at down_x on the eave
    add_cylinder(bm, (down_x, eave_y, eave_z - 0.05), 0.032, 0.052, 0.11, segments=16, mat_idx=mat_idx)
    add_box(bm, (down_x, eave_y, eave_z - 0.01), (0.095, 0.095, 0.065), mat_idx=mat_idx, uv_scale=0.5, bevel=0.008)

    # Angled elbow pipe (呼び樋) connecting collector funnel at (down_x, eave_y, eave_z - 0.10) to wall at (down_x, wall_y, eave_z - 0.34)
    p0 = Vector((down_x, eave_y, eave_z - 0.10))
    p1 = Vector((down_x, wall_y, eave_z - 0.34))
    diff = p1 - p0
    elbow_len = diff.length
    if elbow_len > 0.02:
        mid = 0.5 * (p0 + p1)
        pitch_ang = math.atan2(diff.y, -diff.z)
        add_cylinder(bm, (mid.x, mid.y, mid.z), 0.028, 0.028, elbow_len + 0.03, segments=16, mat_idx=mat_idx, rot_euler=(pitch_ang, 0, 0))
        add_sphere(bm, (p0.x, p0.y, p0.z), 0.031, u_segs=14, v_segs=10, mat_idx=mat_idx)
        add_sphere(bm, (p1.x, p1.y, p1.z), 0.031, u_segs=14, v_segs=10, mat_idx=mat_idx)

    # Vertical downspout pipe (竪樋) hugging the building wall from (eave_z - 0.34) down to ground_z + 0.08
    top_z = eave_z - 0.34
    bot_z = ground_z + 0.08
    v_h = max(0.2, top_z - bot_z)
    add_cylinder(bm, (down_x, wall_y, 0.5 * (top_z + bot_z)), 0.028, 0.028, v_h, segments=18, mat_idx=mat_idx)

    # Wall mounting clamp collars + standoff pins (控え金具) every 0.68m
    n_clamps = max(3, int(v_h / 0.68))
    for c_i in range(n_clamps):
        cz = bot_z + 0.18 + (c_i / float(max(1, n_clamps - 1))) * (v_h - 0.32)
        add_torus(bm, (down_x, wall_y, cz), 0.032, 0.005, major_segs=18, minor_segs=6, mat_idx=mat_idx)
        add_box(bm, (down_x, wall_y + 0.035, cz), (0.016, 0.065, 0.018), mat_idx=mat_idx, uv_scale=0.5)

    # Bottom curved drainage shoe (排水エルボ) directing rainwater into street gutter
    add_sphere(bm, (down_x, wall_y, bot_z), 0.031, u_segs=14, v_segs=10, mat_idx=mat_idx)
    add_cylinder(bm, (down_x, wall_y - 0.045, bot_z - 0.035), 0.028, 0.030, 0.11, segments=16, mat_idx=mat_idx, rot_euler=(0.78, 0, 0))


def add_wrinkled_trash_bag(bm, center, radius, height, seed, mat_idx, uv_rect=(0.77, 0.52, 0.98, 0.98)):
    """
    Sculpted high-resolution polyethylene garbage bag (NO sphere+cone primitive look!):
    - Gravity-squashed flat base sitting on ground,
    - Bulging asymmetric garbage contents inside,
    - 9 radial tension pleats/wrinkles converging into a pinched tie-neck,
    - 2 floppy tied 'rabbit-ear' knot flaps at the top.
    """
    cx, cy, cz = center
    uv_layer = bm.loops.layers.uv.verify()
    u0, v0, u1, v1 = uv_rect
    u_segs = 32
    v_segs = 20
    rng = random.Random(seed)
    phase1 = rng.uniform(0, 6.28)
    phase2 = rng.uniform(0, 6.28)

    grid = []
    for iv in range(v_segs + 1):
        tv = iv / float(v_segs)
        # Height profile from flat bottom (tv=0) through pinched neck (tv=0.82) to flared knot top (tv=1.0)
        z = cz + tv * height
        if tv < 0.14:
            # Rounded flat bottom resting on ground
            base_r = radius * math.sin((tv / 0.14) * math.pi * 0.5) ** 0.55
        elif tv < 0.82:
            # Slumped bulging middle tapering into pinched neck
            s = (tv - 0.14) / 0.68
            base_r = radius * (1.0 - 0.80 * (s ** 1.55)) * (1.0 + 0.12 * math.sin(s * math.pi))
        else:
            # Flared tied knot ruffle above neck
            s = (tv - 0.82) / 0.18
            base_r = radius * (0.20 + 0.24 * math.sin(s * math.pi * 0.75))

        ring = []
        for iu in range(u_segs):
            ang = (iu / float(u_segs)) * 2.0 * math.pi
            # Lumpy internal trash bulges (low frequency)
            bulge = 1.0 + (0.11 * math.sin(ang * 3.0 + phase1 + tv * 4.0) + 0.07 * math.cos(ang * 5.0 + phase2 - tv * 3.0)) * math.sin(tv * math.pi)
            # Radial tension stretch folds converging toward the tied neck (high frequency)
            neck_prox = math.exp(-((tv - 0.80) / 0.24) ** 2)
            pleats = 1.0 + 0.14 * neck_prox * math.cos(ang * 9.0 + tv * 5.0 + phase1) + 0.06 * math.sin(ang * 15.0 - tv * 8.0)
            r = max(0.012, base_r * bulge * pleats)
            # Slight gravity slump offset
            slump_x = 0.025 * radius * math.sin(tv * math.pi) * math.cos(phase1)
            slump_y = 0.025 * radius * math.sin(tv * math.pi) * math.sin(phase2)
            ring.append(bm.verts.new((cx + slump_x + math.cos(ang) * r, cy + slump_y + math.sin(ang) * r, z)))
        grid.append(ring)

    # Cap bottom & top
    v_bot = bm.verts.new((cx, cy, cz))
    v_top = bm.verts.new((cx, cy, cz + height * 0.94))
    for iu in range(u_segs):
        iun = (iu + 1) % u_segs
        fb = bm.faces.new((grid[0][iun], grid[0][iu], v_bot))
        ft = bm.faces.new((grid[v_segs][iu], grid[v_segs][iun], v_top))
        for f in (fb, ft):
            f.material_index = mat_idx
            f.smooth = True
            for loop in f.loops:
                loop[uv_layer].uv = (0.5 * (u0 + u1), 0.5 * (v0 + v1))

    for iv in range(v_segs):
        for iu in range(u_segs):
            iun = (iu + 1) % u_segs
            f = bm.faces.new((grid[iv][iu], grid[iv][iun], grid[iv + 1][iun], grid[iv + 1][iu]))
            f.material_index = mat_idx
            f.smooth = True
            for k, loop in enumerate(f.loops):
                lu = (iu + (1 if k in (1, 2) else 0)) / float(u_segs)
                lv = (iv + (1 if k in (2, 3) else 0)) / float(v_segs)
                loop[uv_layer].uv = (u0 + lu * (u1 - u0), v0 + lv * (v1 - v0))

    # Add 2 tied 'rabbit-ear' plastic knot loops flaring out from the pinched neck!
    for side in (-1.0, 1.0):
        ear_yaw = phase1 + (0.4 if side > 0 else 3.54)
        add_curved_leaf_card(
            bm,
            (cx, cy, cz + height * 0.83),
            length=radius * 0.55,
            width=radius * 0.28,
            yaw=ear_yaw,
            pitch=0.62,
            arch_droop=radius * 0.24,
            v_fold=0.015,
            roll=side * 0.25,
            mat_idx=mat_idx,
            uv_rect=uv_rect,
            segs_l=4,
            segs_w=2,
        )


def add_plastic_beer_crate(bm, center, rot_z=0.25, mat_idx=0):
    """
    Authentic Japanese molded plastic beer crate (ビールケース - 0.44m x 0.36m x 0.32m)
    with hollow walls, corner structural ribs, inner bottle grid dividers, and 9 3D glass beer bottles inside!
    """
    cx, cy, cz = center
    w, d, h = 0.44, 0.36, 0.32
    uv_yellow = (0.52, 0.52, 0.74, 0.70)
    uv_dark_bottle = (0.78, 0.55, 0.96, 0.92)
    crate_verts = []

    # Bottom grid base & 4 corner pillars
    crate_verts.extend(add_box(bm, (0, 0, 0.02), (w, d, 0.04), mat_idx=mat_idx, uv_rect=uv_yellow))
    for sx in (-1, 1):
        for sy in (-1, 1):
            crate_verts.extend(
                add_box(bm, (sx * (w * 0.5 - 0.022), sy * (d * 0.5 - 0.022), h * 0.5), (0.044, 0.044, h), mat_idx=mat_idx, uv_rect=uv_yellow)
            )
        # Front/back top & bottom rails (leaving handle slot open in middle!)
        for rz in (0.09, 0.27):
            crate_verts.extend(add_box(bm, (0, sx * (d * 0.5 - 0.015), rz), (w - 0.04, 0.03, 0.09), mat_idx=mat_idx, uv_rect=uv_yellow))
            crate_verts.extend(add_box(bm, (sx * (w * 0.5 - 0.015), 0, rz), (0.03, d - 0.04, 0.09), mat_idx=mat_idx, uv_rect=uv_yellow))

    # Inner honeycombed bottle partition grid (4x3 cells)
    for gx in (-0.11, 0.0, 0.11):
        crate_verts.extend(add_box(bm, (gx, 0, 0.12), (0.008, d - 0.04, 0.18), mat_idx=mat_idx, uv_rect=uv_yellow))
    for gy in (-0.06, 0.06):
        crate_verts.extend(add_box(bm, (0, gy, 0.12), (w - 0.04, 0.008, 0.18), mat_idx=mat_idx, uv_rect=uv_yellow))

    # 9 3D Glass Beer Bottles (Dai-bin 633ml) sitting in the crate cells (body + tapered shoulder + neck + crown cap)
    bottle_cells = [(-0.16, -0.11), (-0.055, -0.11), (0.055, -0.11), (0.16, -0.11), (-0.16, 0.0), (0.055, 0.0), (-0.16, 0.11), (-0.055, 0.11), (0.16, 0.11)]
    for b_idx, (bx, by) in enumerate(bottle_cells):
        tilt = (0.08, -0.05, 0) if b_idx == 5 else (0, 0, 0)
        crate_verts.extend(add_cylinder(bm, (bx, by, 0.13), 0.034, 0.034, 0.18, segments=14, mat_idx=mat_idx, rot_euler=tilt, uv_rect=uv_dark_bottle))
        crate_verts.extend(add_cylinder(bm, (bx, by, 0.25), 0.034, 0.013, 0.07, segments=14, mat_idx=mat_idx, rot_euler=tilt, uv_rect=uv_dark_bottle))
        crate_verts.extend(add_cylinder(bm, (bx, by, 0.31), 0.013, 0.014, 0.06, segments=12, mat_idx=mat_idx, rot_euler=tilt, uv_rect=uv_dark_bottle))

    valid_v = list({v for v in crate_verts if v.is_valid})
    if rot_z != 0.0:
        bmesh.ops.rotate(bm, matrix=Euler((0, 0, rot_z), "XYZ").to_matrix(), verts=valid_v)
    bmesh.ops.translate(bm, vec=(cx, cy, cz), verts=valid_v)


def add_corrugated_canopy(bm, center, width, depth, z_drop, mat_top, mat_wood_soffit):
    """High-poly 3D sinusoidal corrugated sheet metal canopy with timber frame & rafters underneath."""
    cx, cy, cz = center
    nx = 56
    ny = 8
    thickness = 0.016
    wave_amp = 0.018
    uv_layer = bm.loops.layers.uv.verify()

    top_grid = []
    bot_grid = []
    for iy in range(ny + 1):
        ty = iy / ny
        y = cy - depth * 0.5 + ty * depth
        z_slope = cz - (1.0 - ty) * z_drop
        t_row = []
        b_row = []
        for ix in range(nx + 1):
            tx = (ix / nx) - 0.5
            x = cx + tx * width
            wave = math.sin(tx * width * 16.0 * math.pi) * wave_amp
            t_row.append(bm.verts.new((x, y, z_slope + wave + thickness)))
            b_row.append(bm.verts.new((x, y, z_slope + wave)))
        top_grid.append(t_row)
        bot_grid.append(b_row)

    for iy in range(ny):
        for ix in range(nx):
            ft = bm.faces.new((top_grid[iy][ix], top_grid[iy][ix + 1], top_grid[iy + 1][ix + 1], top_grid[iy + 1][ix]))
            ft.material_index = mat_top
            ft.smooth = True
            for loop in ft.loops:
                co = loop.vert.co
                loop[uv_layer].uv = ((co.x - cx) * 0.5, (co.y - cy) * 0.5)

            fb = bm.faces.new((bot_grid[iy][ix + 1], bot_grid[iy][ix], bot_grid[iy + 1][ix], bot_grid[iy + 1][ix + 1]))
            fb.material_index = mat_top
            fb.smooth = True
            for loop in fb.loops:
                co = loop.vert.co
                loop[uv_layer].uv = ((co.x - cx) * 0.5, (co.y - cy) * 0.5)

    add_box(bm, (cx, cy, cz - z_drop * 0.5 - 0.035), (width - 0.06, depth - 0.06, 0.03), mat_idx=mat_wood_soffit, uv_scale=0.5)
    num_rafters = max(5, int(width * 2.2))
    for r_i in range(num_rafters):
        rx = cx - (width * 0.46) + (r_i / (num_rafters - 1)) * (width * 0.92)
        add_box(bm, (rx, cy, cz - z_drop * 0.5 - 0.065), (0.045, depth - 0.04, 0.05), mat_idx=mat_wood_soffit, uv_scale=0.5)


def add_braided_shimenawa(bm, center, span_w, base_r, sag, mat_idx, uv_rect=(0.05, 0.28, 0.95, 0.48)):
    """High-poly 3-strand helical twisted sacred straw Shimenawa rope with tapered ends and hanging Shide."""
    cx, cy, cz = center
    uv_layer = bm.loops.layers.uv.verify()
    n_steps = 56
    n_ring = 10
    twists = 7.5

    for strand in range(3):
        phase = strand * (2.0 * math.pi / 3.0)
        grid = []
        for i in range(n_steps + 1):
            t = (i / n_steps) - 0.5
            x = cx + t * span_w
            taper = math.cos(t * math.pi * 0.88)
            z_center = cz - sag * (1.0 - (t * 2.0) ** 2)
            strand_orbit = base_r * 0.48 * taper
            strand_r = base_r * 0.56 * taper
            ang = t * twists * 2.0 * math.pi + phase
            oy = cy + math.cos(ang) * strand_orbit
            oz = z_center + math.sin(ang) * strand_orbit

            ring = []
            for j in range(n_ring):
                va = (j / n_ring) * 2.0 * math.pi
                vy = oy + math.cos(va) * strand_r
                vz = oz + math.sin(va) * strand_r
                ring.append(bm.verts.new((x, vy, vz)))
            grid.append(ring)

        for i in range(n_steps):
            for j in range(n_ring):
                jn = (j + 1) % n_ring
                f = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][jn], grid[i][jn]))
                f.material_index = mat_idx
                f.smooth = True
                u0, v0, u1, v1 = uv_rect
                for k, loop in enumerate(f.loops):
                    lu = (i + (1 if k in (1, 2) else 0)) / n_steps
                    lv = (j + (1 if k in (2, 3) else 0)) / n_ring
                    loop[uv_layer].uv = (u0 + lu * (u1 - u0), v0 + lv * (v1 - v0))


def add_shide_zigzags(bm, positions_x, y_pos, z_top, mat_idx, uv_rect=(0.05, 0.02, 0.45, 0.22)):
    """3D multi-segment folded zig-zag white paper Shide streamers."""
    for sx in positions_x:
        curr_x = sx
        curr_z = z_top
        for seg in range(4):
            dx = 0.045 if (seg % 2 == 0) else -0.045
            dz = -0.105
            mx = curr_x + dx * 0.5
            mz = curr_z + dz * 0.5
            tilt = 0.32 if (seg % 2 == 0) else -0.32
            add_box(
                bm,
                (mx, y_pos - (seg * 0.004), mz),
                (0.085, 0.012, 0.13),
                mat_idx=mat_idx,
                uv_rect=uv_rect,
                bevel=0.002,
                rot_euler=(0, tilt, 0),
            )
            curr_x += dx
            curr_z += dz


def add_pitched_kawara_roof(bm, center, width, depth, pitch_h, mat_tile, mat_wood, mat_gable=None, curve_sag=0.09, add_rafters=True):
    """High-poly traditional Japanese Kawara tiled roof with 3D ridge tiles, eave drip tiles, demon end-caps, and exposed rafters."""
    cx, cy, cz = center
    if mat_gable is None:
        mat_gable = mat_wood
    nx = 26
    ny = 28
    thickness = 0.12
    uv_layer = bm.loops.layers.uv.verify()

    def roof_z(tx):
        return (1.0 - tx) * pitch_h - math.sin(tx * math.pi) * curve_sag

    for side in (-1, 1):
        top_grid = []
        bot_grid = []
        for iy in range(ny + 1):
            ty = (iy / ny) - 0.5
            y = cy + ty * depth
            corrug = math.sin(ty * depth * 11.0 * math.pi) * 0.026
            t_row = []
            b_row = []
            for ix in range(nx + 1):
                tx = ix / nx
                x = cx + side * tx * (width * 0.5)
                tier_step = (1.0 - ((tx * 10.0) % 1.0)) * 0.012
                zt = cz + roof_z(tx) + corrug + tier_step
                zb = cz + roof_z(tx) - thickness
                t_row.append(bm.verts.new((x, y, zt)))
                b_row.append(bm.verts.new((x, y, zb)))
            top_grid.append(t_row)
            bot_grid.append(b_row)

        for iy in range(ny):
            for ix in range(nx):
                v00, v10, v11, v01 = top_grid[iy][ix], top_grid[iy][ix + 1], top_grid[iy + 1][ix + 1], top_grid[iy + 1][ix]
                ft = bm.faces.new((v00, v10, v11, v01) if side == 1 else (v01, v11, v10, v00))
                ft.material_index = mat_tile
                ft.smooth = True
                for loop in ft.loops:
                    co = loop.vert.co
                    loop[uv_layer].uv = ((co.y - cy) * 0.65, (co.x - cx) * side * 0.65)

                b00, b10, b11, b01 = bot_grid[iy][ix], bot_grid[iy][ix + 1], bot_grid[iy + 1][ix + 1], bot_grid[iy + 1][ix]
                fb = bm.faces.new((b01, b11, b10, b00) if side == 1 else (b00, b10, b11, b01))
                fb.material_index = mat_wood
                fb.smooth = False
                for loop in fb.loops:
                    co = loop.vert.co
                    loop[uv_layer].uv = ((co.y - cy) * 0.5, (co.x - cx) * side * 0.5)

            te0, te1 = top_grid[iy][nx], top_grid[iy + 1][nx]
            be0, be1 = bot_grid[iy][nx], bot_grid[iy + 1][nx]
            fe = bm.faces.new((te0, be0, be1, te1) if side == 1 else (te1, be1, be0, te0))
            fe.material_index = mat_tile

        for iy_edge, flip in ((0, False), (ny, True)):
            for ix in range(nx):
                t0, t1 = top_grid[iy_edge][ix], top_grid[iy_edge][ix + 1]
                b0, b1 = bot_grid[iy_edge][ix], bot_grid[iy_edge][ix + 1]
                fg = bm.faces.new((t0, b0, b1, t1) if (side == 1) ^ flip else (t1, b1, b0, t0))
                fg.material_index = mat_wood

        if width > 1.2:
            num_drip = max(8, int(depth * 3.2))
            eave_x = cx + side * (width * 0.5 - 0.02)
            eave_z = cz + 0.015
            for d_i in range(num_drip):
                dy = cy - depth * 0.48 + (d_i / max(1, num_drip - 1)) * (depth * 0.96)
                add_cylinder(
                    bm,
                    (eave_x, dy, eave_z),
                    0.048,
                    0.045,
                    0.18,
                    segments=12,
                    mat_idx=mat_tile,
                    rot_euler=(0, math.pi * 0.5, 0),
                )

        if add_rafters and width > 1.8:
            num_rafters = max(7, int(depth * 2.2))
            slope_ang = math.atan2(pitch_h, width * 0.5) * side
            rafter_len = math.hypot(width * 0.5, pitch_h)
            for r_i in range(num_rafters):
                ry = cy - depth * 0.47 + (r_i / max(1, num_rafters - 1)) * (depth * 0.94)
                rx = cx + side * (width * 0.25)
                rz = cz + roof_z(0.5) - thickness - 0.045
                add_box(
                    bm,
                    (rx, ry, rz),
                    (rafter_len, 0.055, 0.065),
                    mat_idx=mat_wood,
                    uv_scale=0.5,
                    rot_euler=(0, slope_ang, 0),
                )

    gable_w = width * 0.78
    gable_d = depth * 0.78
    for sy in (-1, 1):
        gy = cy + sy * (gable_d * 0.5)
        v_left = bm.verts.new((cx - gable_w * 0.5, gy, cz - 0.08))
        v_right = bm.verts.new((cx + gable_w * 0.5, gy, cz - 0.08))
        v_peak = bm.verts.new((cx, gy, cz + pitch_h - 0.04))
        fg = bm.faces.new((v_left, v_right, v_peak) if sy == -1 else (v_right, v_left, v_peak))
        fg.material_index = mat_gable
        for loop in fg.loops:
            co = loop.vert.co
            loop[uv_layer].uv = ((co.x - cx) * 0.35, (co.z - cz) * 0.35)

    for tier in range(3):
        tw = 0.34 - tier * 0.05
        tz = cz + pitch_h + 0.03 + tier * 0.055
        add_box(bm, (cx, cy, tz), (tw, depth + 0.08, 0.05), mat_idx=mat_tile, uv_scale=0.5)
    add_cylinder(
        bm,
        (cx, cy, cz + pitch_h + 0.21),
        0.09,
        0.09,
        depth + 0.14,
        segments=16,
        mat_idx=mat_tile,
        rot_euler=(math.pi * 0.5, 0, 0),
    )

    for sy in (-1, 1):
        oy = cy + sy * (depth * 0.5 + 0.06)
        add_box(bm, (cx, oy, cz + pitch_h + 0.14), (0.42, 0.14, 0.32), mat_idx=mat_tile, uv_scale=0.5, bevel=0.025)
        add_cylinder(bm, (cx, oy + sy * 0.04, cz + pitch_h + 0.28), 0.14, 0.08, 0.12, segments=14, mat_idx=mat_tile, rot_euler=(math.pi * 0.5, 0, 0))


def finalize_and_export(bm, name: str, mat_keys: list[str], export_fbx: bool = True, preview_offset=(0, 0, 0)):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for k in mat_keys:
        obj.data.materials.append(MATERIALS[k])

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    for e in bm.edges:
        if len(e.link_faces) == 2:
            ang = e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0)
            if ang > math.radians(42.0):
                e.smooth = False
            else:
                e.smooth = True

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    try:
        wn = obj.modifiers.new(name="WeightedNormal", type="WEIGHTED_NORMAL")
        wn.mode = "FACE_AREA_WITH_ANGLE"
        wn.weight = 50
        wn.keep_sharp = True
    except Exception:
        pass

    if export_fbx:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        obj.location = (0.0, 0.0, 0.0)
        fbx_path = MODELS_DIR / f"{name}.fbx"
        bpy.ops.export_scene.fbx(
            filepath=str(fbx_path),
            use_selection=True,
            global_scale=1.0,
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_ALL",
            axis_forward="-Z",
            axis_up="Y",
            use_mesh_modifiers=True,
            mesh_smooth_type="EDGE",
            path_mode="AUTO",
        )
    obj.location = preview_offset
    return obj


def build_alley_road_and_gutters():
    bm = bmesh.new()
    # Materials: 0=WetAsphalt, 1=StonePaving, 2=ConcreteWall, 3=RustedMetal, 4=FoliageLeafCutout
    nx, ny = 36, 150
    w = 4.25
    y_start, y_end = -24.0, 20.0
    uv_layer = bm.loops.layers.uv.verify()

    verts = []
    for iy in range(ny + 1):
        ty = iy / ny
        y = y_start + ty * (y_end - y_start)
        row = []
        for ix in range(nx + 1):
            tx = (ix / nx) - 0.5
            x = tx * w
            crown = (1.0 - (tx * 2.0) ** 2) * 0.032
            rut = -0.011 * math.exp(-((abs(x) - 0.95) / 0.42) ** 2)
            ripple = math.sin(y * 0.55 + x * 1.3) * 0.006 + math.cos(y * 1.4 - x * 2.1) * 0.004
            v = bm.verts.new((x, y, crown + rut + ripple))
            row.append(v)
        verts.append(row)

    for iy in range(ny):
        for ix in range(nx):
            f = bm.faces.new((verts[iy][ix], verts[iy][ix + 1], verts[iy + 1][ix + 1], verts[iy + 1][ix]))
            f.material_index = 0
            f.smooth = True
            for loop in f.loops:
                co = loop.vert.co
                loop[uv_layer].uv = (co.x * 0.35, co.y * 0.35)

    # High-poly Individual Beveled Granite Curb Stones & Slotted Cast-Iron Gutter Grates with human-scale age settling!
    rng = random.Random(42)
    for side in (-1, 1):
        gx = side * 2.35
        add_box(bm, (gx, -2.0, -0.04), (0.42, 44.0, 0.04), mat_idx=2, uv_scale=0.4)
        num_curbs = 55
        curb_len = 44.0 / num_curbs
        for c_i in range(num_curbs):
            cy = -23.6 + c_i * curb_len
            jit_z = rng.uniform(-0.006, 0.006)
            jit_x = rng.uniform(-0.005, 0.005)
            tilt_r = (rng.uniform(-0.018, 0.018), rng.uniform(-0.018, 0.018), rng.uniform(-0.012, 0.012))
            add_box(
                bm,
                (side * 2.58 + jit_x, cy, 0.075 + jit_z),
                (0.18, curb_len - 0.015, 0.21),
                mat_idx=2,
                uv_scale=0.45,
                bevel=0.014,
                rot_euler=tilt_r,
            )
            # Sprout wild roadside grass/fern tufts out of damp curb joints!
            if c_i % 4 == (0 if side == -1 else 2):
                add_fern_and_weed_rosette(
                    bm,
                    (side * 2.48, cy + 0.2, 0.02),
                    scale=rng.uniform(0.45, 0.72),
                    seed=200 + c_i * 7 + (0 if side < 0 else 1),
                    mat_idx=4,
                    include_ferns=(c_i % 8 == 0),
                    include_broadleaf=True,
                    include_grass=True,
                )

        for seg in range(44):
            sy = -23.5 + seg * 1.0
            is_grate = (seg % 5 == 2)
            if is_grate:
                add_box(bm, (gx, sy - 0.46, 0.018), (0.36, 0.04, 0.045), mat_idx=3, uv_scale=0.6)
                add_box(bm, (gx, sy + 0.46, 0.018), (0.36, 0.04, 0.045), mat_idx=3, uv_scale=0.6)
                add_box(bm, (gx - 0.16, sy, 0.018), (0.04, 0.92, 0.045), mat_idx=3, uv_scale=0.6)
                add_box(bm, (gx + 0.16, sy, 0.018), (0.04, 0.92, 0.045), mat_idx=3, uv_scale=0.6)
                for bar_i in range(11):
                    by = sy - 0.40 + bar_i * 0.08
                    add_box(bm, (gx, by, 0.020), (0.30, 0.028, 0.038), mat_idx=3, uv_scale=0.6, bevel=0.004)
            else:
                jit_z = rng.uniform(-0.005, 0.005)
                # Human imperfection: some concrete Dobu-ita gutter covers are slightly skewed or shifted!
                skew_yaw = rng.uniform(-0.035, 0.035) if (seg % 7 == 0) else rng.uniform(-0.01, 0.01)
                shift_x = rng.uniform(-0.018, 0.018) if (seg % 7 == 0) else 0.0
                add_box(
                    bm,
                    (gx + shift_x, sy, 0.016 + jit_z),
                    (0.36, 0.95, 0.052),
                    mat_idx=1,
                    uv_scale=0.6,
                    bevel=0.010,
                    rot_euler=(rng.uniform(-0.01, 0.01), rng.uniform(-0.01, 0.01), skew_yaw),
                )

    # North Sando Approach Flagstone Plaza (individual beveled stone slabs with subtle settling & crevice weeds)
    for px_i in(-4, -3, -2, -1, 0, 1, 2, 3, 4):
        for py_i in range(4):
            sx = px_i * 0.72 + (0.18 if (py_i % 2 == 1) else -0.18)
            sy = 19.0 + py_i * 0.95
            add_box(
                bm,
                (sx, sy, 0.025 + rng.uniform(-0.004, 0.004)),
                (0.69, 0.92, 0.07),
                mat_idx=1,
                uv_scale=0.45,
                bevel=0.012,
                rot_euler=(rng.uniform(-0.012, 0.012), rng.uniform(-0.012, 0.012), rng.uniform(-0.015, 0.015)),
            )

    return finalize_and_export(
        bm,
        "AlleyRoadAndGutters",
        ["WetAsphalt", "StonePaving", "ConcreteWall", "RustedMetal", "FoliageLeafCutout"],
        preview_offset=(0, 0, 0),
    )


def build_machiya_house(name: str, width=6.2, depth=5.8, h1=2.9, h2=2.6, eerie_upper=False, preview_offset=(0, 0, 0)):
    bm = bmesh.new()
    # Materials: 0=DarkWood, 1=AgedPlaster, 2=KawaraTile, 3=StonePaving, 4=ShojiWindow, 5=ShojiWindowEerie, 6=RustedMetal, 7=PropsAtlas
    rng = random.Random(101 if not eerie_upper else 202)
    # Granite foundation plinth with chiseled water-table ledge & ventilation grilles (床下換気口)
    add_box(bm, (0, 0, 0.18), (width + 0.16, depth + 0.16, 0.36), mat_idx=3, uv_scale=0.4, bevel=0.016)
    fy = -depth * 0.5
    for vx in (-width * 0.32, width * 0.32):
        add_box(bm, (vx, fy - 0.085, 0.18), (0.42, 0.03, 0.16), mat_idx=6, uv_scale=0.5, bevel=0.005)
        for vb in range(5):
            add_box(bm, (vx - 0.16 + vb * 0.08, fy - 0.095, 0.18), (0.012, 0.02, 0.13), mat_idx=6, uv_scale=0.5)

    # 1st floor timber body & 2nd floor Shikkui plaster body
    add_box(bm, (0, 0, 0.36 + h1 * 0.5), (width, depth, h1), mat_idx=0, uv_scale=0.35, bevel=0.012)
    z2_center = 0.36 + h1 + h2 * 0.5
    add_box(bm, (0, 0, z2_center), (width - 0.10, depth - 0.10, h2), mat_idx=1, uv_scale=0.35, bevel=0.012)

    # 3D Vertical Yakisugi Board-and-Batten Siding Ribs (Sasara-ko) on 1st floor front & sides
    num_battens = int(width / 0.24)
    for b_i in range(num_battens + 1):
        bx = -width * 0.48 + (b_i / num_battens) * (width * 0.96)
        if abs(bx - (-width * 0.24)) < 0.80 or abs(bx - (width * 0.24)) < 0.84:
            continue
        warp_rot = (rng.uniform(-0.005, 0.005), rng.uniform(-0.007, 0.007), 0)
        add_box(bm, (bx, fy - 0.018, 0.36 + h1 * 0.5), (0.034, 0.036, h1 - 0.06), mat_idx=0, uv_scale=0.5, bevel=0.005, rot_euler=warp_rot)
    # Side wall vertical battens + 2nd floor timber studs (Makabe-zukuri) so side walls have rich 3D relief!
    for sx in (-1, 1):
        wx_side = sx * width * 0.5
        for sy_i in range(13):
            by = -depth * 0.46 + (sy_i / 12.0) * (depth * 0.92)
            add_box(bm, (wx_side + sx * 0.016, by, 0.36 + h1 * 0.5), (0.032, 0.035, h1 - 0.06), mat_idx=0, uv_scale=0.5, bevel=0.005)
        for stud_y in (-depth * 0.25, 0.0, depth * 0.25):
            add_box(bm, (sx * (width * 0.45), stud_y, z2_center), (0.12, 0.12, h2), mat_idx=0, uv_scale=0.4, bevel=0.010)
        add_box(bm, (sx * (width * 0.46), 0, z2_center - 0.15), (0.09, depth - 0.08, 0.09), mat_idx=0, uv_scale=0.4, bevel=0.008)

    # Corner & central structural timber pillars (Hashira) & horizontal tie beams (Nageshi / Dozashi)
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_box(bm, (sx * width * 0.49, sy * depth * 0.49, 0.36 + (h1 + h2) * 0.5), (0.19, 0.19, h1 + h2), mat_idx=0, uv_scale=0.4, bevel=0.015)
    for post_x in (-width * 0.24 - 0.84, 0.0, width * 0.24 + 0.88):
        add_box(bm, (post_x, fy, 0.36 + (h1 + h2) * 0.5), (0.15, 0.15, h1 + h2), mat_idx=0, uv_scale=0.4, bevel=0.012)
    add_box(bm, (0, 0, 0.36 + h1), (width + 0.16, depth + 0.16, 0.19), mat_idx=0, uv_scale=0.4, bevel=0.015)
    add_box(bm, (0, 0, 0.36 + h1 + h2 - 0.08), (width + 0.10, depth + 0.10, 0.16), mat_idx=0, uv_scale=0.4, bevel=0.014)

    # 1st floor Left Bay: Sliding Lattice Door (Koshido) + granite entrance step stone + wooden entrance lantern (Genkan Andon)
    dx = -width * 0.24
    add_box(bm, (dx, fy - 0.24, 0.12), (1.42, 0.42, 0.24), mat_idx=3, uv_scale=0.5, bevel=0.018)
    add_box(bm, (dx, fy - 0.03, 1.66), (1.55, 0.08, 1.45), mat_idx=4, uv_rect=(0.0, 0.0, 1.0, 1.0))
    add_box(bm, (dx, fy - 0.055, 0.68), (1.60, 0.12, 0.64), mat_idx=0, uv_scale=0.5, bevel=0.010)
    for k_p in range(4):
        add_box(bm, (dx - 0.57 + k_p * 0.38, fy - 0.095, 0.68), (0.32, 0.025, 0.50), mat_idx=0, uv_scale=0.5, bevel=0.006)
    add_box(bm, (dx - 0.80, fy - 0.08, 1.38), (0.07, 0.14, 2.08), mat_idx=0, uv_scale=0.5, bevel=0.010)
    add_box(bm, (dx + 0.80, fy - 0.08, 1.38), (0.07, 0.14, 2.08), mat_idx=0, uv_scale=0.5, bevel=0.010)
    add_box(bm, (dx, fy - 0.08, 2.42), (1.68, 0.16, 0.08), mat_idx=0, uv_scale=0.5, bevel=0.010)
    for i in range(15):
        lx = dx - 0.72 + i * (1.44 / 14.0)
        add_box(bm, (lx, fy - 0.09, 1.38), (0.026, 0.09, 2.04), mat_idx=0, uv_scale=0.5, bevel=0.004)
    for hz in (0.98, 1.32, 1.66, 2.00, 2.34):
        add_box(bm, (dx, fy - 0.09, hz), (1.58, 0.08, 0.032), mat_idx=0, uv_scale=0.5, bevel=0.004)

    # Wall-mounted wooden lattice entrance lantern (玄関行灯) & protective paper talisman (Ofuda)
    lx_and = dx - 0.96
    add_box(bm, (lx_and, fy - 0.14, 2.05), (0.18, 0.18, 0.32), mat_idx=4, uv_rect=(0.2, 0.2, 0.8, 0.8))
    add_box(bm, (lx_and, fy - 0.14, 2.23), (0.24, 0.24, 0.04), mat_idx=0, uv_scale=0.5, bevel=0.006)
    add_box(bm, (lx_and, fy - 0.14, 1.87), (0.22, 0.22, 0.04), mat_idx=0, uv_scale=0.5, bevel=0.006)
    for cx_a in (-0.09, 0.09):
        for cy_a in (-0.09, 0.09):
            add_box(bm, (lx_and + cx_a, fy - 0.14 + cy_a, 2.05), (0.022, 0.022, 0.34), mat_idx=0, uv_scale=0.5)
    add_box(bm, (dx + 0.80, fy - 0.155, 1.88), (0.09, 0.006, 0.24), mat_idx=7, uv_rect=(0.51, 0.02, 0.74, 0.23), rot_euler=(0, 0.045, 0))

    # 1st floor Right Bay: Protruding Degoshi Lattice Cage Window (出格子) with copper roof flashing
    wx = width * 0.24
    add_box(bm, (wx, fy - 0.05, 1.65), (1.65, 0.10, 1.25), mat_idx=4, uv_rect=(0.0, 0.0, 1.0, 1.0))
    for i in range(17):
        lx = wx - 0.78 + i * (1.56 / 16.0)
        add_box(bm, (lx, fy - 0.17, 1.65), (0.024, 0.18, 1.28), mat_idx=0, uv_scale=0.5, bevel=0.004)
    for hz_g in (1.12, 1.65, 2.18):
        add_box(bm, (wx, fy - 0.17, hz_g), (1.68, 0.16, 0.028), mat_idx=0, uv_scale=0.5, bevel=0.004)
    for sy_bar in (-1, 1):
        add_box(bm, (wx + sy_bar * 0.84, fy - 0.11, 1.65), (0.045, 0.20, 1.28), mat_idx=0, uv_scale=0.5, bevel=0.006)
    add_box(bm, (wx, fy - 0.14, 1.00), (1.80, 0.26, 0.08), mat_idx=0, uv_scale=0.5, bevel=0.010)
    add_box(bm, (wx, fy - 0.15, 2.31), (1.82, 0.28, 0.07), mat_idx=2, uv_scale=0.5, bevel=0.010, rot_euler=(0.18, 0, 0))
    for br_x in (wx - 0.65, wx - 0.22, wx + 0.22, wx + 0.65):
        add_box(bm, (br_x, fy - 0.11, 0.90), (0.055, 0.20, 0.14), mat_idx=0, uv_scale=0.5, bevel=0.008)

    # 2nd floor Shoji windows with 3D exterior wooden mullions, safety handrail (高欄), AND wooden storm-shutter box (戸袋 / Tobukuro)!
    win2_mat = 5 if eerie_upper else 4
    for side_u, ux in ((-1, -width * 0.24), (1, width * 0.24)):
        add_box(bm, (ux, fy - 0.03, z2_center), (1.36, 0.10, 1.18), mat_idx=win2_mat, uv_rect=(0.0, 0.0, 1.0, 1.0))
        add_box(bm, (ux, fy - 0.09, z2_center - 0.62), (1.52, 0.18, 0.08), mat_idx=0, uv_scale=0.5, bevel=0.010)
        add_box(bm, (ux, fy - 0.09, z2_center + 0.62), (1.52, 0.18, 0.08), mat_idx=0, uv_scale=0.5, bevel=0.010)
        add_box(bm, (ux - 0.72, fy - 0.08, z2_center), (0.07, 0.15, 1.24), mat_idx=0, uv_scale=0.5, bevel=0.008)
        add_box(bm, (ux + 0.72, fy - 0.08, z2_center), (0.07, 0.15, 1.24), mat_idx=0, uv_scale=0.5, bevel=0.008)
        for mx in (-0.45, -0.15, 0.15, 0.45):
            add_box(bm, (ux + mx, fy - 0.07, z2_center), (0.024, 0.06, 1.18), mat_idx=0, uv_scale=0.5, bevel=0.004)
        for mz in (-0.30, 0.0, 0.30):
            add_box(bm, (ux, fy - 0.07, z2_center + mz), (1.38, 0.06, 0.024), mat_idx=0, uv_scale=0.5, bevel=0.004)
        # Exterior 2nd-floor wooden window guardrail (手すり)
        add_box(bm, (ux, fy - 0.16, z2_center - 0.34), (1.48, 0.05, 0.045), mat_idx=0, uv_scale=0.5, bevel=0.006)
        for bal_i in range(7):
            bx_bal = ux - 0.60 + bal_i * 0.20
            add_box(bm, (bx_bal, fy - 0.16, z2_center - 0.48), (0.025, 0.03, 0.26), mat_idx=0, uv_scale=0.5)
        # Wooden storm-shutter storage box (戸袋 / Tobukuro) flanking the window
        tb_x = ux + side_u * 0.90
        add_box(bm, (tb_x, fy - 0.08, z2_center), (0.34, 0.14, 1.24), mat_idx=0, uv_scale=0.5, bevel=0.008)
        for sl_i in range(8):
            add_box(bm, (tb_x, fy - 0.155, z2_center - 0.52 + sl_i * 0.15), (0.30, 0.018, 0.11), mat_idx=0, uv_scale=0.5, bevel=0.003)

    # Slanted front entrance awning roof (Hisashi) with 3D rafters, wooden soffit, and round eave drip tiles
    hisashi_z = 0.36 + h1 - 0.06
    add_box(bm, (0, fy - 0.50, hisashi_z - 0.03), (width + 0.48, 1.06, 0.05), mat_idx=0, uv_scale=0.5, bevel=0.008, rot_euler=(0.10, 0, 0))
    add_box(bm, (0, fy - 0.52, hisashi_z + 0.02), (width + 0.54, 1.12, 0.055), mat_idx=2, uv_scale=0.5, bevel=0.010, rot_euler=(0.10, 0, 0))
    num_hisashi_rafters = 15
    for r_i in range(num_hisashi_rafters):
        rx = -width * 0.48 + (r_i / (num_hisashi_rafters - 1)) * (width * 0.96)
        add_box(bm, (rx, fy - 0.48, hisashi_z - 0.08), (0.042, 1.02, 0.05), mat_idx=0, uv_scale=0.5, bevel=0.005, rot_euler=(0.10, 0, 0))
        add_cylinder(bm, (rx, fy - 1.06, hisashi_z - 0.02), 0.040, 0.038, 0.14, segments=12, mat_idx=2, rot_euler=(math.pi * 0.5 + 0.10, 0, 0))
    for bx in (-width * 0.45, -width * 0.15, width * 0.15, width * 0.45):
        add_box(bm, (bx, fy - 0.35, hisashi_z - 0.16), (0.08, 0.72, 0.10), mat_idx=0, uv_scale=0.5, bevel=0.008)

    # Authentic Japanese Architectural Eave Gutter (軒樋) + S-bend Elbow (呼び樋) + Wall-Clamped Downspout (竪樋)!
    add_architectural_gutter_and_downspout(
        bm,
        eave_x0=-width * 0.52,
        eave_x1=width * 0.52,
        eave_y=fy - 1.08,
        eave_z=hisashi_z - 0.06,
        down_x=-width * 0.48,
        wall_y=fy - 0.06,
        ground_z=0.04,
        mat_idx=6,
    )

    # Main 2-story High-Poly Kawara Roof
    add_pitched_kawara_roof(
        bm,
        (0, 0, 0.36 + h1 + h2 - 0.04),
        width + 1.35,
        depth + 1.25,
        1.45,
        mat_tile=2,
        mat_wood=0,
        mat_gable=1,
        curve_sag=0.09,
        add_rafters=True,
    )

    # Side-wall utilities: 3D Electric Watt-Hour Meter Box + Twin Household LP Gas Cylinders & Regulator Piping!
    add_cylinder(bm, (width * 0.52, fy + 0.18, 0.36 + (h1 + h2) * 0.5), 0.036, 0.036, h1 + h2, segments=18, mat_idx=6)
    for bz in (1.0, 2.2, 3.4, 4.6, 5.4):
        add_torus(bm, (width * 0.52, fy + 0.18, bz), 0.040, 0.006, major_segs=16, minor_segs=6, mat_idx=6)
    # Electric meter box + glass dial dome + dual conduit risers on left side wall
    add_box(bm, (-width * 0.52, -1.10, 1.65), (0.14, 0.28, 0.38), mat_idx=6, uv_scale=0.5, bevel=0.012)
    add_cylinder(bm, (-width * 0.58, -1.10, 1.70), 0.075, 0.070, 0.08, segments=18, mat_idx=4, rot_euler=(0, math.pi * 0.5, 0), uv_rect=(0.2, 0.2, 0.8, 0.8))
    add_cylinder(bm, (-width * 0.52, -1.02, 2.45), 0.018, 0.018, 1.40, segments=12, mat_idx=6)
    add_cylinder(bm, (-width * 0.52, -1.18, 1.00), 0.016, 0.016, 1.10, segments=12, mat_idx=6)
    # Twin LP Gas Cylinders (プロパンガスボンベ) with valve collars, regulator & wall chain on left wall!
    for gy_gas in (-0.25, 0.25):
        gx_gas = -width * 0.52 - 0.16
        add_cylinder(bm, (gx_gas, gy_gas, 0.52), 0.15, 0.15, 0.88, segments=24, mat_idx=6)
        add_sphere(bm, (gx_gas, gy_gas, 0.96), 0.15, scale=(1.0, 1.0, 0.45), u_segs=24, v_segs=12, mat_idx=6)
        add_cylinder(bm, (gx_gas, gy_gas, 1.08), 0.065, 0.065, 0.12, segments=16, mat_idx=6)
        add_cylinder(bm, (gx_gas, gy_gas, 1.09), 0.022, 0.022, 0.10, segments=12, mat_idx=7, uv_rect=(0.27, 0.52, 0.31, 0.56))
    add_box(bm, (-width * 0.52, 0.0, 1.36), (0.12, 0.22, 0.26), mat_idx=6, uv_scale=0.5, bevel=0.010)

    return finalize_and_export(
        bm,
        name,
        ["DarkWood", "AgedPlaster", "KawaraTile", "StonePaving", "ShojiWindow", "ShojiWindowEerie", "RustedMetal", "PropsAtlas"],
        preview_offset=preview_offset,
    )


def build_corner_store():
    bm = bmesh.new()
    # Materials: 0=DarkWood, 1=AgedPlaster, 2=KawaraTile, 3=ShopShutterSign, 4=RustedMetal, 5=ShojiWindow, 6=StonePaving
    w, d, h1, h2 = 6.6, 5.8, 3.0, 2.5
    add_box(bm, (0, 0, 0.16), (w + 0.18, d + 0.18, 0.32), mat_idx=6, uv_scale=0.4, bevel=0.016)
    add_box(bm, (0, 0, 0.32 + h1 * 0.5), (w, d, h1), mat_idx=0, uv_scale=0.35, bevel=0.012)
    add_box(bm, (0, 0, 0.32 + h1 + h2 * 0.5), (w - 0.1, d - 0.1, h2), mat_idx=1, uv_scale=0.35, bevel=0.012)

    # Corner & side structural timber pillars + horizontal tie beams
    fy = -d * 0.5
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_box(bm, (sx * w * 0.49, sy * d * 0.49, 0.32 + (h1 + h2) * 0.5), (0.18, 0.18, h1 + h2), mat_idx=0, uv_scale=0.4, bevel=0.014)
        for sy_i in range(13):
            by = -d * 0.46 + (sy_i / 12.0) * (d * 0.92)
            add_box(bm, (sx * w * 0.505, by, 0.32 + h1 * 0.5), (0.032, 0.035, h1 - 0.06), mat_idx=0, uv_scale=0.5, bevel=0.005)
    add_box(bm, (0, 0, 0.32 + h1), (w + 0.14, d + 0.14, 0.18), mat_idx=0, uv_scale=0.4, bevel=0.014)

    # High-Poly 28-Slat Rolling Steel Shop Shutter (シャッター) with 3D curved interlocking joints & bottom lock bar!
    shutter_w = 3.85
    shutter_h = 2.35
    shutter_cx = -0.55
    shutter_z0 = 0.34
    num_slats = 28
    slat_h = shutter_h / num_slats
    for s_i in range(num_slats):
        tz0 = s_i / num_slats
        tz1 = (s_i + 1) / num_slats
        v0 = 0.02 + tz0 * 0.46
        v1 = 0.02 + tz1 * 0.46
        sz = shutter_z0 + (s_i + 0.5) * slat_h
        add_box(
            bm,
            (shutter_cx, fy - 0.055, sz),
            (shutter_w, 0.052, slat_h - 0.005),
            mat_idx=3,
            uv_rect=(0.02, v0, 0.98, v1),
        )
        # 3D cylindrical interlocking hinge curl along the top of every slat!
        add_cylinder(
            bm,
            (shutter_cx, fy - 0.076, sz + slat_h * 0.44),
            0.011,
            0.011,
            shutter_w - 0.02,
            segments=10,
            mat_idx=4,
            rot_euler=(0, math.pi * 0.5, 0),
        )
    # Heavy bottom steel locking rail (座板) + 2 slide-bolt latches + keyhole escutcheons!
    add_box(bm, (shutter_cx, fy - 0.072, shutter_z0 + 0.035), (shutter_w + 0.02, 0.085, 0.07), mat_idx=4, uv_scale=0.5, bevel=0.008)
    for lx_lock in (shutter_cx - 1.1, shutter_cx + 1.1):
        add_box(bm, (lx_lock, fy - 0.095, shutter_z0 + 0.42), (0.18, 0.03, 0.09), mat_idx=4, uv_scale=0.5, bevel=0.006)
        add_cylinder(bm, (lx_lock, fy - 0.11, shutter_z0 + 0.42), 0.018, 0.018, 0.03, segments=12, mat_idx=4, rot_euler=(math.pi * 0.5, 0, 0))
    # Side U-channel guide rails & top rolled-shutter hood box (シャッターケース) with maintenance bolts
    for sx in (-1, 1):
        add_box(bm, (shutter_cx + sx * (shutter_w * 0.5 + 0.05), fy - 0.08, 1.52), (0.09, 0.15, 2.40), mat_idx=4, uv_scale=0.5, bevel=0.010)
    add_box(bm, (shutter_cx, fy - 0.15, 2.78), (4.08, 0.30, 0.34), mat_idx=4, uv_scale=0.4, bevel=0.018)

    # Right-side Shopkeeper Entrance Door Bay (店舗通用口) & Vintage Tile Wainscoting (`x = 2.15`) so the right facade isn't blank!
    door_x = 2.15
    add_box(bm, (door_x, fy - 0.03, 1.38), (1.18, 0.08, 2.10), mat_idx=5, uv_rect=(0.0, 0.0, 1.0, 1.0))
    add_box(bm, (door_x, fy - 0.055, 0.65), (1.22, 0.11, 0.64), mat_idx=0, uv_scale=0.5, bevel=0.008)
    for d_post in (-0.62, 0.62):
        add_box(bm, (door_x + d_post, fy - 0.08, 1.38), (0.07, 0.14, 2.12), mat_idx=0, uv_scale=0.5, bevel=0.008)
    for d_mull in (-0.30, 0.0, 0.30):
        add_box(bm, (door_x + d_mull, fy - 0.07, 1.65), (0.025, 0.07, 1.45), mat_idx=0, uv_scale=0.5, bevel=0.004)
    for d_rail in (1.02, 1.38, 1.74, 2.10, 2.42):
        add_box(bm, (door_x, fy - 0.07, d_rail), (1.24, 0.09, 0.035), mat_idx=0, uv_scale=0.5, bevel=0.004)
    # Protruding retro cylindrical "たばこ (Tobacco)" sign mounted on the right corner pillar!
    add_cylinder(bm, (3.08, fy - 0.34, 2.25), 0.16, 0.16, 0.52, segments=24, mat_idx=3, uv_rect=(0.02, 0.76, 0.15, 0.98))
    for tz_cap in (1.98, 2.52):
        add_cylinder(bm, (3.08, fy - 0.34, tz_cap), 0.175, 0.175, 0.04, segments=24, mat_idx=4)
        add_box(bm, (3.08, fy - 0.16, tz_cap), (0.04, 0.34, 0.035), mat_idx=4, uv_scale=0.5)

    # Illuminated retro signboard "たばこ・駄菓子 夕霧商店" with subtle aged tilt & gooseneck lamp brackets
    add_box(bm, (-0.35, fy - 0.26, 3.45), (4.20, 0.14, 0.92), mat_idx=3, uv_rect=(0.01, 0.755, 0.665, 0.99), rot_euler=(0, 0.008, 0))
    add_box(bm, (-0.35, fy - 0.23, 3.45), (4.28, 0.12, 0.98), mat_idx=4, uv_scale=0.4, bevel=0.014, rot_euler=(0, 0.008, 0))
    for bx in (-2.1, -0.95, 0.25, 1.4):
        add_box(bm, (bx, fy - 0.10, 3.45), (0.07, 0.24, 0.75), mat_idx=4, uv_scale=0.5, bevel=0.008)
        # Gooseneck sign reflector lamps over the signboard
        add_cylinder(bm, (bx, fy - 0.36, 4.02), 0.016, 0.016, 0.34, segments=12, mat_idx=4, rot_euler=(math.pi * 0.42, 0, 0))
        add_cylinder(bm, (bx, fy - 0.50, 3.98), 0.085, 0.03, 0.07, segments=18, mat_idx=4, rot_euler=(0.35, 0, 0))

    add_corrugated_canopy(bm, (0, fy - 0.54, 2.98), w + 0.50, 1.14, 0.14, mat_top=4, mat_wood_soffit=0)
    add_architectural_gutter_and_downspout(
        bm,
        eave_x0=-w * 0.52,
        eave_x1=w * 0.52,
        eave_y=fy - 1.12,
        eave_z=2.84,
        down_x=-w * 0.48,
        wall_y=fy - 0.06,
        ground_z=0.04,
        mat_idx=4,
    )

    z2_win = 0.32 + h1 + 1.25
    for side_u, ux in ((-1, -1.6), (1, 1.6)):
        add_box(bm, (ux, fy - 0.02, z2_win), (1.45, 0.10, 1.15), mat_idx=5, uv_rect=(0.0, 0.0, 1.0, 1.0))
        add_box(bm, (ux, fy - 0.08, z2_win - 0.60), (1.58, 0.16, 0.08), mat_idx=0, uv_scale=0.5, bevel=0.010)
        add_box(bm, (ux, fy - 0.08, z2_win + 0.60), (1.58, 0.16, 0.08), mat_idx=0, uv_scale=0.5, bevel=0.010)
        for mx in (-0.36, 0.0, 0.36):
            add_box(bm, (ux + mx, fy - 0.06, z2_win), (0.028, 0.06, 1.15), mat_idx=0, uv_scale=0.5, bevel=0.004)
        for mz in (-0.28, 0.28):
            add_box(bm, (ux, fy - 0.06, z2_win + mz), (1.45, 0.06, 0.024), mat_idx=0, uv_scale=0.5, bevel=0.004)
        # 2nd floor storm-shutter box (Tobukuro)
        tb_x = ux + side_u * 0.94
        add_box(bm, (tb_x, fy - 0.07, z2_win), (0.32, 0.13, 1.20), mat_idx=0, uv_scale=0.5, bevel=0.008)

    add_pitched_kawara_roof(bm, (0, 0, 0.32 + h1 + h2 - 0.05), w + 1.35, d + 1.25, 1.40, mat_tile=2, mat_wood=0, mat_gable=1, curve_sag=0.09, add_rafters=True)

    return finalize_and_export(
        bm,
        "CornerStore_Dagashiya",
        ["DarkWood", "AgedPlaster", "KawaraTile", "ShopShutterSign", "RustedMetal", "ShojiWindow", "StonePaving"],
        preview_offset=(9.0, -8.0, 0.0),
    )


def build_rural_bus_stop():
    bm = bmesh.new()
    # Materials: 0=DarkWood, 1=RustedMetal, 2=ShopShutterSign, 3=StonePaving, 4=ShojiWindowEerie, 5=FoliageLeafCutout
    rng = random.Random(305)
    # Stepped concrete platform foundation with beveled curb edge & cast-iron post shoes (柱脚金物)
    add_box(bm, (0, 0, 0.08), (3.18, 1.90, 0.16), mat_idx=3, uv_scale=0.5, bevel=0.018)
    for sx in (-1.35, 1.35):
        for sy in (-0.75, 0.75):
            add_box(bm, (sx, sy, 0.22), (0.17, 0.17, 0.14), mat_idx=1, uv_scale=0.5, bevel=0.010)
            add_box(bm, (sx, sy, 1.28), (0.13, 0.13, 2.38), mat_idx=0, uv_scale=0.5, bevel=0.012)
        add_box(bm, (sx, 0, 2.36), (0.12, 1.66, 0.12), mat_idx=0, uv_scale=0.5, bevel=0.010)
        # Diagonal carpenter knee braces (方杖 - Hozue) at front and rear posts
        add_box(bm, (sx - (0.22 if sx > 0 else -0.22), -0.75, 2.15), (0.48, 0.08, 0.08), mat_idx=0, uv_scale=0.5, bevel=0.008, rot_euler=(0, 0.78 if sx > 0 else -0.78, 0))
        add_box(bm, (sx, -0.48, 2.15), (0.08, 0.48, 0.08), mat_idx=0, uv_scale=0.5, bevel=0.008, rot_euler=(0.78, 0, 0))
    add_box(bm, (0, -0.75, 2.38), (2.86, 0.12, 0.12), mat_idx=0, uv_scale=0.5, bevel=0.010)
    add_box(bm, (0, 0.75, 2.32), (2.86, 0.12, 0.12), mat_idx=0, uv_scale=0.5, bevel=0.010)

    # Back & side wooden walls with individual 3D weather-warped horizontal clapboard planks (下見板張り) + framed window!
    add_box(bm, (0, 0.75, 1.25), (2.76, 0.06, 2.22), mat_idx=0, uv_scale=0.4, bevel=0.008)
    add_box(bm, (-1.35, 0, 1.25), (0.06, 1.50, 2.22), mat_idx=0, uv_scale=0.4, bevel=0.008)
    for v_stud in (-0.90, -0.45, 0.0, 0.45, 0.90):
        add_box(bm, (v_stud, 0.78, 1.25), (0.06, 0.06, 2.20), mat_idx=0, uv_scale=0.5, bevel=0.006)
    for p_i in range(13):
        pz = 0.24 + p_i * 0.17
        warp = rng.uniform(-0.012, 0.012)
        add_box(bm, (0, 0.71, pz), (2.68, 0.028, 0.155), mat_idx=0, uv_scale=0.5, bevel=0.004, rot_euler=(0.08, warp, 0))
        add_box(bm, (-1.31, 0, pz), (0.028, 1.44, 0.155), mat_idx=0, uv_scale=0.5, bevel=0.004, rot_euler=(warp, -0.08, 0))
    # Side wall framed lattice window with wooden mullions
    add_box(bm, (-1.35, -0.05, 1.52), (0.09, 0.88, 0.74), mat_idx=4, uv_rect=(0.1, 0.1, 0.9, 0.9))
    for wf_z in (1.14, 1.52, 1.90):
        add_box(bm, (-1.35, -0.05, wf_z), (0.12, 0.94, 0.045), mat_idx=0, uv_scale=0.5, bevel=0.006)
    for wf_y in (-0.50, -0.05, 0.40):
        add_box(bm, (-1.35, wf_y, 1.52), (0.12, 0.045, 0.78), mat_idx=0, uv_scale=0.5, bevel=0.006)

    # Contoured Wooden Waiting Bench with slatted seat, angled backrest & bolted iron brackets!
    for slat_y in (0.24, 0.36, 0.48, 0.60):
        add_box(bm, (0.1, slat_y, 0.50), (2.38, 0.095, 0.042), mat_idx=0, uv_scale=0.5, bevel=0.006)
    for back_z in (0.68, 0.82, 0.96):
        add_box(bm, (0.1, 0.67, back_z), (2.38, 0.035, 0.095), mat_idx=0, uv_scale=0.5, bevel=0.006, rot_euler=(-0.12, 0, 0))
    for leg_x in (-0.98, -0.26, 0.46, 1.18):
        add_box(bm, (leg_x, 0.42, 0.27), (0.08, 0.44, 0.44), mat_idx=0, uv_scale=0.5, bevel=0.008)
        add_box(bm, (leg_x, 0.22, 0.56), (0.055, 0.08, 0.16), mat_idx=1, uv_scale=0.5, bevel=0.005)
    for arm_x in (-1.06, 1.26):
        add_box(bm, (arm_x, 0.40, 0.64), (0.075, 0.48, 0.045), mat_idx=0, uv_scale=0.5, bevel=0.008)
        add_box(bm, (arm_x, 0.20, 0.56), (0.065, 0.065, 0.16), mat_idx=0, uv_scale=0.5, bevel=0.006)

    # Glass-framed Timetable & Route Notice Cabinet ("夕霧村 停留所") with small protective wooden visor hood
    add_box(bm, (0.15, 0.67, 1.52), (1.25, 0.03, 0.78), mat_idx=2, uv_rect=(0.01, 0.505, 0.488, 0.745), rot_euler=(0, 0.018, 0))
    add_box(bm, (0.15, 0.685, 1.52), (1.34, 0.045, 0.86), mat_idx=0, uv_scale=0.5, bevel=0.008, rot_euler=(0, 0.018, 0))
    add_box(bm, (0.15, 0.64, 1.96), (1.40, 0.12, 0.04), mat_idx=1, uv_scale=0.5, bevel=0.006, rot_euler=(0.18, 0.018, 0))

    add_corrugated_canopy(bm, (0, -0.02, 2.52), 3.28, 2.12, 0.12, mat_top=1, mat_wood_soffit=0)
    add_architectural_gutter_and_downspout(
        bm,
        eave_x0=-1.64,
        eave_x1=1.64,
        eave_y=-1.08,
        eave_z=2.38,
        down_x=-1.42,
        wall_y=-0.82,
        ground_z=0.04,
        mat_idx=1,
    )

    # Flickering ceiling fluorescent fixture with starter capacitor, end sockets & hanging chain mounts
    add_box(bm, (0, -0.15, 2.40), (1.42, 0.22, 0.05), mat_idx=1, uv_scale=0.5, bevel=0.008)
    for sx_end in (-0.68, 0.68):
        add_box(bm, (sx_end, -0.15, 2.36), (0.04, 0.20, 0.06), mat_idx=1, uv_scale=0.5)
    for ty_off in (-0.05, 0.05):
        add_cylinder(bm, (0, -0.15 + ty_off, 2.35), 0.022, 0.022, 1.32, segments=16, mat_idx=4, rot_euler=(0, math.pi * 0.5, 0), uv_rect=(0.2, 0.2, 0.8, 0.8))

    # Standalone iconic Japanese round Bus Stop Signpost beside shelter (x = 1.95, with cast-iron ribbed base & schedule case!)
    add_cylinder(bm, (1.95, -0.55, 0.12), 0.30, 0.26, 0.24, segments=36, mat_idx=3)
    add_torus(bm, (1.95, -0.55, 0.24), 0.26, 0.032, major_segs=32, minor_segs=12, mat_idx=1)
    add_cylinder(bm, (1.95, -0.55, 0.32), 0.14, 0.08, 0.14, segments=24, mat_idx=1)
    add_cylinder(bm, (1.95, -0.55, 1.24), 0.036, 0.036, 2.18, segments=24, mat_idx=1, rot_euler=(0.015, -0.02, 0))
    # Metal schedule box frame clamped to the pole with U-bolts
    add_box(bm, (1.95, -0.55, 1.36), (0.44, 0.04, 0.56), mat_idx=2, uv_rect=(0.01, 0.505, 0.488, 0.745), rot_euler=(0.015, -0.02, 0))
    add_box(bm, (1.95, -0.55, 1.36), (0.48, 0.032, 0.60), mat_idx=1, uv_scale=0.5, bevel=0.008, rot_euler=(0.015, -0.02, 0))
    for ub_z in (1.12, 1.60):
        add_torus(bm, (1.95, -0.55, ub_z), 0.045, 0.008, major_segs=18, minor_segs=8, mat_idx=1)
    # Top round bus emblem disc + bolted perimeter hoop
    add_cylinder(bm, (1.95, -0.55, 2.18), 0.27, 0.27, 0.055, segments=36, mat_idx=2, rot_euler=(math.pi * 0.5, 0, 0), uv_rect=(0.01, 0.505, 0.488, 0.745))
    add_torus(bm, (1.95, -0.55, 2.18), 0.275, 0.024, major_segs=36, minor_segs=12, mat_idx=1, rot_euler=(math.pi * 0.5, 0, 0))

    # Wild ferns & grass sprouting around the concrete pad & rusty signpost base!
    add_fern_and_weed_rosette(bm, (-1.45, -0.68, 0.02), scale=0.85, seed=311, mat_idx=5)
    add_fern_and_weed_rosette(bm, (1.82, -0.42, 0.02), scale=0.72, seed=312, mat_idx=5)

    return finalize_and_export(
        bm,
        "RuralBusStop",
        ["DarkWood", "RustedMetal", "ShopShutterSign", "StonePaving", "ShojiWindowEerie", "FoliageLeafCutout"],
        preview_offset=(-6.0, -14.0, 0.0),
    )


def build_retro_vending_machine():
    """
    Ultra-High-Poly Japanese Beverage Vending Machine (自動販売機) + Companion Can Recycling Bin (空き缶入れ):
    - NO flat front box! True recessed 3D upper showcase cavity (depth = 0.14m) with backlit interior wall & top lamp,
    - 3 tiered stainless-steel angled shelves holding 30 multi-part 3D cans & contoured PET bottles:
      * Top shelf: 10 contoured 500ml PET bottles with waist rings, tapered shoulders, necks & screw caps,
      * Middle shelf: 10 350ml aluminum beverage cans with silver top/bottom rims & pull-tab rings,
      * Bottom shelf: 10 short 190ml hot-coffee cans ("あたたかい") with tapered rims,
    - 30 individual 3D price rails ("130円") & curved 3D push-buttons with LED lenses below each product,
    - Non-emissive off-white & red enameled steel cabinet panels with beveled door seams & chrome T-handle lock latch,
    - Protruding 3D payment console (digital 7-seg readout bezel, 1000-yen bill validator throat, chromed coin slot,
      sculpted coin return lever & recessed coin return cup),
    - Deeply recessed drink pickup chute (取出口) with hinged angled 3D dark-acrylic flap door ("PUSH"),
    - Side cooling louver grilles (14 individual 3D slats) + embossed stiffening ribs,
    - Companion 3D Twin-Hole Beverage Recycling Bin (リサイクルボックス) standing beside the right side!
    """
    bm = bmesh.new()
    # Materials: 0=VendingMachineFront, 1=ACUnitMetal, 2=PropsAtlas, 3=RustedMetal
    w, d, h = 1.18, 0.76, 1.90
    fy = -d * 0.5  # -0.38 is the front plane of the outer door bezel
    uv_red_enamel = (0.02, 0.86, 0.22, 0.98)
    uv_white_steel = (0.04, 0.962, 0.20, 0.972)
    uv_dark_trim = (0.27, 0.52, 0.31, 0.56)

    # 1. Rear & Side Cabinet Body (leaving the front showcase & pickup cavities open!)
    # Rear main cabinet housing (y from -0.22 to +0.38)
    add_box(bm, (0, 0.08, h * 0.5 + 0.06), (w, 0.60, h), mat_idx=1, uv_scale=0.5, bevel=0.020)
    # Left & Right Outer Red Enamel Side Walls extending forward to fy (-0.38)
    for sx in (-1, 1):
        wall_x = sx * (w * 0.5 - 0.032)
        add_box(bm, (wall_x, fy + 0.09, h * 0.5 + 0.06), (0.064, 0.18, h), mat_idx=2, uv_rect=uv_red_enamel, bevel=0.010)
        # Subtle stamped vertical seam ribs on the exterior side panels
        for rib_y in (-0.06, 0.22):
            add_box(bm, (sx * (w * 0.5 + 0.003), rib_y, h * 0.5 + 0.06), (0.006, 0.024, h - 0.18), mat_idx=1, uv_scale=0.5, bevel=0.002)
        # Side ventilation louver grille at lower side (14 individual 3D angled louver slats!)
        add_box(bm, (sx * (w * 0.5 + 0.006), 0.10, 0.38), (0.014, 0.34, 0.42), mat_idx=3, uv_scale=0.5, bevel=0.004)
        for lv_i in range(14):
            lz = 0.20 + lv_i * 0.027
            add_box(bm, (sx * (w * 0.5 + 0.012), 0.10, lz), (0.012, 0.30, 0.016), mat_idx=1, uv_scale=0.5, rot_euler=(0, sx * 0.45, 0))

    # 2. Top Header Canopy & Backlit Sign Box ("24時間営業 お飲み物 DRINK", z = 1.74..1.94)
    add_box(bm, (0, fy + 0.08, 1.85), (w, 0.18, 0.22), mat_idx=2, uv_rect=uv_red_enamel, bevel=0.012)
    add_box(bm, (0, fy - 0.005, 1.84), (w - 0.10, 0.03, 0.15), mat_idx=0, uv_rect=(0.047, 0.877, 0.953, 0.957))
    # Top overhanging rain drip visor with rounded front lip
    add_box(bm, (0, fy - 0.02, 1.95), (w + 0.02, 0.14, 0.045), mat_idx=2, uv_rect=uv_red_enamel, bevel=0.010)

    # 3. Deeply Recessed 3D Upper Product Showcase Cavity (z = 0.94..1.73, cavity back at y = fy + 0.15 = -0.23)
    cav_back_y = fy + 0.15
    # Softly backlit showcase rear diffuser panel (UV v: 0.842..0.874)
    add_box(bm, (0, cav_back_y, 1.335), (w - 0.12, 0.02, 0.78), mat_idx=0, uv_rect=(0.055, 0.842, 0.945, 0.874))
    # Top internal fluorescent light tube illuminating the 3D cans from above
    add_cylinder(bm, (0, fy + 0.06, 1.71), 0.016, 0.016, w - 0.16, segments=14, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0), uv_rect=(0.1, 0.845, 0.9, 0.870))
    # Showcase top & bottom stainless frame rails
    add_box(bm, (0, fy + 0.04, 1.735), (w - 0.08, 0.10, 0.032), mat_idx=1, uv_scale=0.5, bevel=0.005)
    add_box(bm, (0, fy + 0.04, 0.935), (w - 0.08, 0.12, 0.036), mat_idx=1, uv_scale=0.5, bevel=0.006)

    # 3 Tiered Shelves + 30 Multi-Part 3D Cans & Contoured PET Bottles + 30 3D Price Rails & Push Buttons!
    shelf_configs = [
        # (row_idx, shelf_z, v_can0, v_can1, v_tag0, v_tag1, v_btn0, v_btn1, is_pet_row, is_short_hot)
        (0, 1.50, 0.750, 0.828, 0.730, 0.748, 0.710, 0.726, True, False),
        (1, 1.24, 0.605, 0.684, 0.586, 0.604, 0.565, 0.581, False, False),
        (2, 0.98, 0.461, 0.539, 0.441, 0.459, 0.421, 0.437, False, True),
    ]
    for row_i, sz, vc0, vc1, vt0, vt1, vb0, vb1, is_pet, is_short in shelf_configs:
        # Stainless steel shelf plate + front price-tag bar + button housing rail
        add_box(bm, (0, fy + 0.085, sz + 0.042), (w - 0.12, 0.11, 0.014), mat_idx=1, uv_scale=0.5, bevel=0.003)
        add_box(bm, (0, fy + 0.025, sz + 0.012), (w - 0.12, 0.035, 0.052), mat_idx=3, uv_scale=0.5, bevel=0.004)
        for col_i in range(10):
            cx = -0.45 + col_i * 0.10
            u0_c = 0.082 + (col_i % 8) * 0.1055
            u1_c = u0_c + 0.074
            can_y = fy + 0.082
            if is_pet:
                # 500ml Contoured PET Bottle: lower body + waist grip ring + upper body + conical shoulder + neck + colored cap!
                add_cylinder(bm, (cx, can_y, sz + 0.088), 0.029, 0.027, 0.075, segments=18, mat_idx=0, uv_rect=(u0_c, vc0, u1_c, vc1))
                add_torus(bm, (cx, can_y, sz + 0.130), 0.026, 0.004, major_segs=18, minor_segs=6, mat_idx=0, uv_rect=(u0_c, vc0, u1_c, vc1))
                add_cylinder(bm, (cx, can_y, sz + 0.155), 0.028, 0.028, 0.045, segments=18, mat_idx=0, uv_rect=(u0_c, vc0, u1_c, vc1))
                add_cylinder(bm, (cx, can_y, sz + 0.192), 0.028, 0.012, 0.032, segments=16, mat_idx=1)
                add_cylinder(bm, (cx, can_y, sz + 0.216), 0.013, 0.013, 0.020, segments=14, mat_idx=2, uv_rect=uv_red_enamel if (col_i % 2 == 0) else uv_dark_trim)
            elif is_short:
                # 190ml Short Hot Coffee / Soup Can with tapered aluminum top/bottom rims
                add_cylinder(bm, (cx, can_y, sz + 0.055), 0.024, 0.027, 0.010, segments=16, mat_idx=1)
                add_cylinder(bm, (cx, can_y, sz + 0.102), 0.027, 0.027, 0.086, segments=18, mat_idx=0, uv_rect=(u0_c, vc0, u1_c, vc1))
                add_cylinder(bm, (cx, can_y, sz + 0.150), 0.027, 0.023, 0.012, segments=16, mat_idx=1)
                add_torus(bm, (cx, can_y, sz + 0.156), 0.022, 0.0025, major_segs=16, minor_segs=6, mat_idx=1)
            else:
                # 350ml Standard Tall Aluminum Beverage Can with tapered silver neck & top chime rim
                add_cylinder(bm, (cx, can_y, sz + 0.055), 0.025, 0.029, 0.010, segments=16, mat_idx=1)
                add_cylinder(bm, (cx, can_y, sz + 0.115), 0.029, 0.029, 0.110, segments=18, mat_idx=0, uv_rect=(u0_c, vc0, u1_c, vc1))
                add_cylinder(bm, (cx, can_y, sz + 0.176), 0.029, 0.024, 0.014, segments=16, mat_idx=1)
                add_torus(bm, (cx, can_y, sz + 0.183), 0.023, 0.0025, major_segs=16, minor_segs=6, mat_idx=1)

            # Vertical clear acrylic product divider fins between columns
            if col_i < 9:
                add_box(bm, (cx + 0.05, can_y, sz + 0.10), (0.004, 0.07, 0.09), mat_idx=1, uv_scale=0.5)

            # Individual 3D "130円" Hot/Cold price plate & 3D protruding curved selection push-button with LED lens!
            add_box(bm, (cx, fy + 0.006, sz + 0.026), (0.076, 0.014, 0.022), mat_idx=0, uv_rect=(u0_c, vt0, u1_c, vt1))
            add_box(bm, (cx, fy - 0.004, sz - 0.002), (0.068, 0.024, 0.024), mat_idx=0, uv_rect=(u0_c, vb0, u1_c, vb1), bevel=0.004)
            add_cylinder(bm, (cx, fy - 0.014, sz - 0.002), 0.026, 0.026, 0.058, segments=12, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0), uv_rect=(u0_c, vb0, u1_c, vb1))

    # 4. Lower Front Enameled Steel Door Panel (z = 0.08..0.92) — NON-EMISSIVE painted steel with recessed pickup bay!
    # Left/Center upper apron between showcase and pickup chute (z = 0.46..0.92, x = -0.52..+0.20)
    add_box(bm, (-0.16, fy + 0.03, 0.69), (0.72, 0.06, 0.46), mat_idx=0, uv_rect=uv_white_steel, bevel=0.010)
    # Illuminated "つめたい COLD / あたたかい HOT" status bar inset on the apron
    add_box(bm, (-0.18, fy - 0.004, 0.78), (0.58, 0.018, 0.065), mat_idx=0, uv_rect=(0.078, 0.314, 0.605, 0.363))
    # Right lower steel door column (x = +0.20..+0.53, z = 0.08..0.92)
    add_box(bm, (0.365, fy + 0.03, 0.50), (0.33, 0.06, 0.84), mat_idx=0, uv_rect=uv_white_steel, bevel=0.010)
    # Bottom steel skirt below pickup bay (z = 0.08..0.18) & left side pillar of pickup bay (x = -0.53..-0.42, z = 0.08..0.46)
    add_box(bm, (-0.16, fy + 0.03, 0.13), (0.72, 0.06, 0.10), mat_idx=0, uv_rect=uv_white_steel, bevel=0.008)
    add_box(bm, (-0.475, fy + 0.03, 0.32), (0.11, 0.06, 0.28), mat_idx=0, uv_rect=uv_white_steel, bevel=0.008)

    # Chrome T-Handle Door Lock Latch (T型ハンドル錠) on the right door edge (x = 0.50, z = 0.88)
    add_box(bm, (0.50, fy - 0.005, 0.88), (0.045, 0.02, 0.12), mat_idx=1, uv_scale=0.5, bevel=0.004)
    add_cylinder(bm, (0.50, fy - 0.02, 0.88), 0.012, 0.012, 0.03, segments=12, mat_idx=1, rot_euler=(math.pi * 0.5, 0, 0))
    add_box(bm, (0.50, fy - 0.032, 0.88), (0.018, 0.014, 0.075), mat_idx=1, uv_scale=0.5, bevel=0.003)

    # 5. Protruding 3D Payment Console (x = 0.35, z = 0.52..0.90):
    # - Main dark cast-metal console bezel
    add_box(bm, (0.34, fy - 0.015, 0.72), (0.26, 0.05, 0.36), mat_idx=3, uv_scale=0.5, bevel=0.008)
    # - Digital 7-segment LED price readout ("130")
    add_box(bm, (0.29, fy - 0.042, 0.82), (0.11, 0.012, 0.055), mat_idx=0, uv_rect=(0.664, 0.312, 0.791, 0.365))
    # - 3D Bill Validator Throat ("1000円札挿入口") with protruding feeder guides
    add_box(bm, (0.29, fy - 0.052, 0.71), (0.11, 0.045, 0.052), mat_idx=3, uv_scale=0.5, bevel=0.006)
    add_box(bm, (0.29, fy - 0.075, 0.71), (0.085, 0.012, 0.014), mat_idx=0, uv_rect=(0.45, 0.565, 0.52, 0.581))
    # - 3D Chromed Coin Slot Bezel & Sculpted Coin Return Lever (返却レバー)
    add_cylinder(bm, (0.41, fy - 0.045, 0.81), 0.028, 0.028, 0.025, segments=18, mat_idx=1, rot_euler=(math.pi * 0.5, 0, 0))
    add_cylinder(bm, (0.41, fy - 0.048, 0.73), 0.010, 0.010, 0.04, segments=12, mat_idx=1, rot_euler=(math.pi * 0.5, 0, 0))
    add_box(bm, (0.41, fy - 0.062, 0.71), (0.022, 0.016, 0.055), mat_idx=1, uv_scale=0.5, bevel=0.004, rot_euler=(0.25, 0, 0))
    # - Recessed Coin Return Cup (つり銭口) at z = 0.58
    add_box(bm, (0.34, fy - 0.018, 0.58), (0.14, 0.045, 0.095), mat_idx=1, uv_scale=0.5, bevel=0.006)
    add_box(bm, (0.34, fy - 0.032, 0.59), (0.11, 0.012, 0.065), mat_idx=3, uv_scale=0.5, rot_euler=(-0.22, 0, 0))

    # 6. Deeply Recessed Drink Pickup Chute (取出口, x = -0.42..+0.20, z = 0.18..0.46)
    # Dark interior chute floor & back wall + angled 3D hinged dark-acrylic flap door ("P U S H 取出口")!
    add_box(bm, (-0.11, fy + 0.10, 0.19), (0.62, 0.16, 0.025), mat_idx=1, uv_scale=0.5, rot_euler=(-0.15, 0, 0))
    add_box(bm, (-0.11, fy + 0.17, 0.32), (0.62, 0.02, 0.28), mat_idx=3, uv_scale=0.5)
    # Top & side stainless trim bezel around the pickup opening
    add_box(bm, (-0.11, fy - 0.01, 0.45), (0.66, 0.05, 0.032), mat_idx=1, uv_scale=0.5, bevel=0.005)
    add_box(bm, (-0.11, fy - 0.01, 0.17), (0.66, 0.05, 0.028), mat_idx=1, uv_scale=0.5, bevel=0.005)
    for px_side in (-0.425, 0.205):
        add_box(bm, (px_side, fy - 0.01, 0.31), (0.032, 0.05, 0.28), mat_idx=1, uv_scale=0.5, bevel=0.005)
    # Hinged 3D Dark-Acrylic Anti-Theft Flap Door (pushed slightly inward at bottom with top hinge rod!)
    add_cylinder(bm, (-0.11, fy + 0.02, 0.425), 0.010, 0.010, 0.60, segments=12, mat_idx=1, rot_euler=(0, math.pi * 0.5, 0))
    add_box(
        bm,
        (-0.11, fy + 0.045, 0.31),
        (0.58, 0.018, 0.23),
        mat_idx=0,
        uv_rect=(0.088, 0.072, 0.785, 0.228),
        bevel=0.004,
        rot_euler=(-0.24, 0, 0),
    )

    # 7. Adjustable leveling feet & bottom steel skid rails
    for sx in (-0.48, 0.48):
        add_box(bm, (sx, 0.0, 0.04), (0.08, d - 0.08, 0.04), mat_idx=3, uv_scale=0.5, bevel=0.006)
        for sy in (-0.28, 0.28):
            add_cylinder(bm, (sx, sy, 0.02), 0.052, 0.042, 0.04, segments=16, mat_idx=3)

    # 8. Companion 3D Beverage Can/Bottle Recycling Bin (空き缶・ペットボトル リサイクルボックス) beside the machine (x = +0.76)!
    rx_bin = 0.76
    add_box(bm, (rx_bin, -0.04, 0.42), (0.30, 0.44, 0.82), mat_idx=1, uv_scale=0.5, bevel=0.014)
    # Sloped top hood with 2 circular bottle/can insertion rings (投入口)
    add_box(bm, (rx_bin, -0.04, 0.88), (0.31, 0.45, 0.14), mat_idx=2, uv_rect=(0.52, 0.72, 0.73, 0.98), bevel=0.012)
    for hole_y in (-0.14, 0.06):
        add_cylinder(bm, (rx_bin - 0.06, hole_y, 0.92), 0.052, 0.052, 0.06, segments=20, mat_idx=3, rot_euler=(0, -0.25, 0))
        add_torus(bm, (rx_bin - 0.07, hole_y, 0.94), 0.055, 0.010, major_segs=20, minor_segs=8, mat_idx=2, rot_euler=(0, -0.25, 0), uv_rect=uv_red_enamel)

    return finalize_and_export(
        bm,
        "RetroVendingMachine",
        ["VendingMachineFront", "ACUnitMetal", "PropsAtlas", "RustedMetal"],
        preview_offset=(4.0, -12.0, 0.0),
    )


def build_walls_and_fences():
    # 1. High-Poly Concrete Block Wall (CB塀) with individual beveled blocks, recessed mortar,
    # ornamental hollow-core breeze blocks (透かしブロック), coping stones & basal weeds!
    bm1 = bmesh.new()
    rng1 = random.Random(401)
    add_box(bm1, (0, 0, 0.10), (4.04, 0.24, 0.20), mat_idx=0, uv_scale=0.45, bevel=0.014)
    # Inner dark mortar core plate so deep mortar joints & breeze-block cutouts have real 3D depth!
    add_box(bm1, (0, 0, 0.96), (3.82, 0.15, 1.52), mat_idx=0, uv_scale=0.45)
    for r_i in range(8):
        bz = 0.20 + (r_i + 0.5) * 0.19
        cols = 9
        for c_i in range(cols):
            bx = -1.72 + c_i * 0.43 + (0.10 if (r_i % 2 == 1 and c_i not in (0, cols - 1)) else 0.0)
            jit_rot = (rng1.uniform(-0.005, 0.005), rng1.uniform(-0.006, 0.006), rng1.uniform(-0.005, 0.005))
            # In row 6, every even block is a traditional Japanese hollow-core breeze block (透かしブロック) with 3D diamond frame!
            if r_i == 6 and c_i in (1, 3, 5, 7):
                add_box(bm1, (bx, 0, bz + 0.072), (0.415, 0.195, 0.034), mat_idx=0, uv_scale=0.45, bevel=0.006)
                add_box(bm1, (bx, 0, bz - 0.072), (0.415, 0.195, 0.034), mat_idx=0, uv_scale=0.45, bevel=0.006)
                add_box(bm1, (bx - 0.18, 0, bz), (0.055, 0.195, 0.14), mat_idx=0, uv_scale=0.45, bevel=0.006)
                add_box(bm1, (bx + 0.18, 0, bz), (0.055, 0.195, 0.14), mat_idx=0, uv_scale=0.45, bevel=0.006)
                # Inner diamond grille struts inside the hollow block
                for d_ang in (0.55, -0.55):
                    add_box(bm1, (bx, 0, bz), (0.22, 0.16, 0.024), mat_idx=0, uv_scale=0.5, rot_euler=(0, d_ang, 0))
            else:
                add_box(bm1, (bx, rng1.uniform(-0.002, 0.002), bz), (0.415, 0.195, 0.178), mat_idx=0, uv_scale=0.45, bevel=0.010, rot_euler=jit_rot)
    # Individual beveled coping capstones along top of wall
    for cap_i in range(8):
        cx_cap = -1.75 + cap_i * 0.50
        add_box(bm1, (cx_cap, 0, 1.78), (0.485, 0.27, 0.085), mat_idx=0, uv_scale=0.45, bevel=0.014)
    for px_pil in (-1.95, 1.95):
        add_box(bm1, (px_pil, 0, 0.92), (0.28, 0.28, 1.84), mat_idx=0, uv_scale=0.45, bevel=0.016)
        add_box(bm1, (px_pil, 0, 1.87), (0.34, 0.34, 0.07), mat_idx=0, uv_scale=0.45, bevel=0.014)
    add_fern_and_weed_rosette(bm1, (-1.15, -0.16, 0.02), scale=0.65, seed=402, mat_idx=1)
    add_fern_and_weed_rosette(bm1, (0.95, 0.16, 0.02), scale=0.60, seed=403, mat_idx=1)
    finalize_and_export(bm1, "ConcreteBlockWall_Segment", ["ConcreteWall", "FoliageLeafCutout"], preview_offset=(-8.0, 0.0, 0.0))

    # 2. High-Poly Traditional Wooden Fence (Itabei) with stone plinths, individual vertical planks, battens & Kawara roof
    bm2 = bmesh.new()
    rng2 = random.Random(405)
    add_box(bm2, (0, 0, 0.15), (3.52, 0.23, 0.30), mat_idx=2, uv_scale=0.5, bevel=0.016)
    # Individual vertical cedar planks (縦板) instead of a single flat board!
    for p_i in range(14):
        px_plank = -1.56 + p_i * 0.24
        add_box(bm2, (px_plank, 0, 1.02), (0.232, 0.055, 1.48), mat_idx=0, uv_scale=0.45, bevel=0.006, rot_euler=(rng2.uniform(-0.008, 0.008), 0, 0))
    for b_i in range(15):
        bx = -1.58 + b_i * 0.225
        for sy in (-1, 1):
            tilt_y = rng2.uniform(-0.018, 0.018)
            add_box(bm2, (bx, sy * 0.042, 1.02), (0.034, 0.026, 1.46), mat_idx=0, uv_scale=0.5, bevel=0.004, rot_euler=(0, tilt_y, 0))
    for hz in (0.46, 1.02, 1.58):
        add_box(bm2, (0, 0, hz), (3.50, 0.115, 0.068), mat_idx=0, uv_scale=0.5, bevel=0.008)
    for px in (-1.68, 0.0, 1.68):
        add_box(bm2, (px, 0, 0.18), (0.20, 0.26, 0.34), mat_idx=2, uv_scale=0.5, bevel=0.014)
        add_box(bm2, (px, 0, 0.98), (0.145, 0.165, 1.84), mat_idx=0, uv_scale=0.5, bevel=0.012)
    add_pitched_kawara_roof(bm2, (0, 0, 1.78), 0.48, 3.66, 0.18, mat_tile=1, mat_wood=0, curve_sag=0.015, add_rafters=False)
    add_fern_and_weed_rosette(bm2, (0.65, -0.15, 0.02), scale=0.68, seed=408, mat_idx=3)
    finalize_and_export(bm2, "WoodenFence_Segment", ["DarkWood", "KawaraTile", "StonePaving", "FoliageLeafCutout"], preview_offset=(-8.0, 5.0, 0.0))


def build_utility_pole_and_cables():
    # 1. High-Poly Utility Pole (Denchu) with Transformer, Coiled Slack Cable Loop (余長ループ),
    # Telecom Junction Box, Guy-Wire Guard, Crooked Flyers & Base Weeds!
    bm = bmesh.new()
    # Materials: 0=UtilityConcrete, 1=ACUnitMetal, 2=ShojiWindow, 3=RustedMetal, 4=PropsAtlas, 5=FoliageLeafCutout
    add_cylinder(bm, (0, 0, 4.3), 0.21, 0.13, 8.6, segments=36, mat_idx=0, uv_scale=1.0)
    for b_z in (1.8, 2.6, 3.8, 5.15, 6.25, 7.4, 8.1):
        r_at_z = 0.21 - (b_z / 8.6) * 0.08
        add_torus(bm, (0, 0, b_z), r_at_z + 0.008, 0.015, major_segs=28, minor_segs=10, mat_idx=3)
    for step_i in range(12):
        sz = 2.0 + step_i * 0.45
        sx = (0.18 - (sz / 8.6) * 0.06) * (1 if step_i % 2 == 0 else -1)
        add_cylinder(bm, (sx, 0, sz), 0.012, 0.012, 0.16, segments=10, mat_idx=3, rot_euler=(0, math.pi * 0.5, 0))

    # Vertical galvanized riser conduit pipe + telecom junction box + coiled slack fiber loop (余長ループ)
    add_cylinder(bm, (0.0, 0.20, 2.8), 0.022, 0.022, 5.4, segments=14, mat_idx=3)
    add_box(bm, (-0.19, 0.0, 3.45), (0.12, 0.22, 0.36), mat_idx=1, uv_scale=0.5, bevel=0.012)
    for loop_i in range(3):
        add_torus(
            bm,
            (0.0, -0.24 - loop_i * 0.015, 5.55),
            0.22,
            0.012,
            major_segs=28,
            minor_segs=8,
            mat_idx=3,
            rot_euler=(math.pi * 0.5 + 0.08 * loop_i, 0.05, 0),
        )

    # Diagonal yellow/black guy-wire anchor guard (支線ガード) bracing the pole at ground level
    add_cylinder(
        bm,
        (0.0, 0.58, 1.35),
        0.028,
        0.028,
        2.85,
        segments=16,
        mat_idx=0,
        rot_euler=(0.38, 0, 0),
        uv_rect=(0.1, 0.25, 0.9, 0.39),
    )

    # 2 Crookedly Pasted Weathered Flyers ("尋ね人" Missing Person notice) wrapped onto the concrete pole!
    add_box(
        bm,
        (-0.195, -0.06, 1.62),
        (0.012, 0.21, 0.29),
        mat_idx=4,
        uv_rect=(0.51, 0.01, 0.74, 0.23),
        rot_euler=(0.06, 0.03, 0.28),
    )
    add_box(
        bm,
        (0.05, -0.202, 1.44),
        (0.19, 0.012, 0.26),
        mat_idx=4,
        uv_rect=(0.51, 0.01, 0.74, 0.23),
        rot_euler=(-0.05, -0.07, -0.18),
    )

    # Double crossarms at top with diagonal V-braces & ribbed porcelain insulators
    for z_arm in (7.4, 8.1):
        add_box(bm, (0, -0.19, z_arm), (1.78, 0.08, 0.09), mat_idx=3, uv_scale=0.5, bevel=0.008)
        for s_brace in (-1, 1):
            add_box(bm, (s_brace * 0.35, -0.18, z_arm - 0.18), (0.55, 0.02, 0.035), mat_idx=3, uv_scale=0.5, rot_euler=(0, s_brace * 0.48, 0))
        for ix in (-0.72, -0.28, 0.28, 0.72):
            add_cylinder(bm, (ix, -0.19, z_arm + 0.08), 0.022, 0.022, 0.12, segments=12, mat_idx=3)
            for rib in range(3):
                add_torus(bm, (ix, -0.19, z_arm + 0.10 + rib * 0.038), 0.042 - rib * 0.004, 0.014, major_segs=18, minor_segs=10, mat_idx=1)

    # Pole-mounted Cylindrical Transformer (Hen'atsuki) with cooling fins, oil sight glass & porcelain bushings
    add_cylinder(bm, (0.36, 0.0, 6.25), 0.24, 0.25, 0.88, segments=32, mat_idx=1)
    add_cylinder(bm, (0.36, 0.0, 6.71), 0.26, 0.24, 0.06, segments=32, mat_idx=1)
    for fin_ang in range(8):
        ang = fin_ang * (math.pi / 4.0)
        fx = 0.36 + math.cos(ang) * 0.25
        fy = math.sin(ang) * 0.25
        add_box(bm, (fx, fy, 6.22), (0.04, 0.018, 0.68), mat_idx=1, uv_scale=0.5, rot_euler=(0, 0, ang))
    for bx_off in (-0.08, 0.08):
        add_cylinder(bm, (0.36 + bx_off, -0.08, 6.82), 0.032, 0.022, 0.18, segments=14, mat_idx=1, rot_euler=(0.25, 0, 0))
    add_box(bm, (0.16, 0.0, 6.25), (0.32, 0.12, 0.55), mat_idx=3, uv_scale=0.5, bevel=0.010)

    # Curved Streetlamp Bracket & Ribbed Enamel Hood extending over road (-X direction)
    add_cylinder(bm, (-0.64, 0.0, 5.16), 0.022, 0.022, 1.28, segments=16, mat_idx=3, rot_euler=(0, math.pi * 0.5, 0))
    add_cylinder(bm, (-0.42, 0.0, 4.98), 0.016, 0.016, 0.88, segments=14, mat_idx=3, rot_euler=(0, math.pi * 0.36, 0))
    add_cylinder(bm, (-1.22, 0.0, 5.14), 0.08, 0.05, 0.10, segments=24, mat_idx=3)
    add_cylinder(bm, (-1.22, 0.0, 5.06), 0.28, 0.08, 0.10, segments=32, mat_idx=3)
    add_torus(bm, (-1.22, 0.0, 5.01), 0.28, 0.014, major_segs=32, minor_segs=10, mat_idx=3)
    add_sphere(bm, (-1.22, 0.0, 4.98), 0.095, scale=(1.0, 1.0, 1.15), u_segs=24, v_segs=16, mat_idx=2, uv_rect=(0.2, 0.2, 0.8, 0.8))

    # Wild ferns & weeds around the base of the utility pole!
    add_fern_and_weed_rosette(bm, (0.0, -0.22, 0.02), scale=0.75, seed=509, mat_idx=5)

    finalize_and_export(
        bm,
        "UtilityPole_Denchu",
        ["UtilityConcrete", "ACUnitMetal", "ShojiWindow", "RustedMetal", "PropsAtlas", "FoliageLeafCutout"],
        preview_offset=(-3.0, -5.0, 0.0),
    )

    # 2. High-Poly Overhead Catenary Cables Span (with spiral cable drop-loops & damper weights)
    bm_c = bmesh.new()
    segs = 32
    span = 11.0
    for wire_x, wire_z, sag, rad in [(-0.65, 0.0, 0.42, 0.015), (-0.22, 0.0, 0.38, 0.015), (0.22, 0.0, 0.45, 0.015), (0.65, -0.55, 0.55, 0.024)]:
        for i in range(segs):
            t0 = (i / segs) - 0.5
            t1 = ((i + 1) / segs) - 0.5
            y0, y1 = t0 * span, t1 * span
            z0 = wire_z - sag * (1.0 - 4.0 * t0 * t0)
            z1 = wire_z - sag * (1.0 - 4.0 * t1 * t1)
            ym = 0.5 * (y0 + y1)
            zm = 0.5 * (z0 + z1)
            dy = y1 - y0
            dz = z1 - z0
            seg_len = math.hypot(dy, dz) * 1.03
            pitch = math.atan2(dz, dy)
            add_cylinder(bm_c, (wire_x, ym, zm), rad, rad, seg_len, segments=10, mat_idx=0, rot_euler=(math.pi * 0.5 - pitch, 0, 0))
    # Messenger-wire suspension rings along the lower telecom bundle (x = 0.65)
    for ring_y in (-4.0, -2.5, -1.0, 0.5, 2.0, 3.5):
        ty = ring_y / span
        rz = -0.55 - 0.55 * (1.0 - 4.0 * ty * ty)
        add_torus(bm_c, (0.65, ring_y, rz - 0.03), 0.035, 0.006, major_segs=14, minor_segs=6, mat_idx=0, rot_euler=(math.pi * 0.5, 0, 0))
    finalize_and_export(bm_c, "OverheadCables_Span", ["RustedMetal"], preview_offset=(-3.0, 2.0, 7.5))


def build_shrine_steps_and_torii():
    # 1. High-Poly Shrine Stone Steps (Ishidan) with hand-quarried settling variations & wild ferns growing in step crevices!
    bm_s = bmesh.new()
    # Materials: 0=StonePaving, 1=MossyGranite, 2=FoliageLeafCutout
    num_steps = 18
    step_d = 0.48
    step_h = 0.18
    step_w = 4.2
    rng = random.Random(108)

    total_d = num_steps * step_d
    total_h = num_steps * step_h

    for i in range(num_steps):
        sy = i * step_d
        sz_top = (i + 1) * step_h
        if i > 0:
            sub_h = i * step_h
            add_box(bm_s, (0, sy, sub_h * 0.5), (step_w - 0.04, step_d + 0.04, sub_h), mat_idx=1, uv_scale=0.35, bevel=0.008)
        num_blocks = 7
        blk_w = step_w / num_blocks
        for b_i in range(num_blocks):
            bx = -step_w * 0.5 + (b_i + 0.5) * blk_w
            jit_z = rng.uniform(-0.008, 0.008)
            jit_y = rng.uniform(-0.006, 0.006)
            tilt = (rng.uniform(-0.016, 0.016), rng.uniform(-0.018, 0.018), rng.uniform(-0.012, 0.012))
            add_box(
                bm_s,
                (bx, sy + jit_y, sz_top - step_h * 0.5 + jit_z),
                (blk_w - 0.012, step_d + 0.04, step_h + 0.02),
                mat_idx=0,
                uv_scale=0.45,
                bevel=0.016,
                rot_euler=tilt,
            )
        # Sprout woodland ferns & wild grass along the mossy step corners!
        if i % 2 == 0:
            side_f = -1 if (i % 4 == 0) else 1
            add_fern_and_weed_rosette(
                bm_s,
                (side_f * (step_w * 0.5 - 0.18), sy - 0.06, sz_top + 0.01),
                scale=rng.uniform(0.55, 0.85),
                seed=600 + i,
                mat_idx=2,
            )

    for side in (-1, 1):
        wx_center = side * (step_w * 0.5 + 0.45)
        for i in range(6):
            wy = (i + 0.5) * (total_d / 6.0)
            wh = (i + 1) * (total_h / 6.0) + 0.55
            add_box(bm_s, (wx_center, wy, wh * 0.5), (0.86, total_d / 6.0 + 0.06, wh), mat_idx=1, uv_scale=0.35, bevel=0.022)
            add_box(bm_s, (wx_center, wy, wh + 0.04), (0.92, total_d / 6.0 + 0.08, 0.09), mat_idx=0, uv_scale=0.4, bevel=0.018)

    add_box(bm_s, (0, total_d + 6.2, total_h * 0.5), (14.5, 13.0, total_h), mat_idx=0, uv_scale=0.30, bevel=0.025)
    for path_i in range(16):
        py = total_d + 0.4 + path_i * 0.52
        for px in (-0.85, 0.0, 0.85):
            add_box(
                bm_s,
                (px, py, total_h + 0.012),
                (0.82, 0.49, 0.03),
                mat_idx=0,
                uv_scale=0.5,
                bevel=0.010,
                rot_euler=(rng.uniform(-0.008, 0.008), rng.uniform(-0.008, 0.008), rng.uniform(-0.01, 0.01)),
            )

    add_box(bm_s, (-7.0, total_d + 6.2, total_h + 0.45), (0.52, 13.0, 0.9), mat_idx=1, uv_scale=0.35, bevel=0.022)
    add_box(bm_s, (7.0, total_d + 6.2, total_h + 0.45), (0.52, 13.0, 0.9), mat_idx=1, uv_scale=0.35, bevel=0.022)
    add_box(bm_s, (0.0, total_d + 12.5, total_h + 0.45), (14.5, 0.52, 0.9), mat_idx=1, uv_scale=0.35, bevel=0.022)
    finalize_and_export(bm_s, "ShrineStoneSteps_Sando", ["StonePaving", "MossyGranite", "FoliageLeafCutout"], preview_offset=(0, 22.0, 0.0))

    # 2. High-Poly Grand Myojin Torii Gate
    bm_t = bmesh.new()
    # Materials: 0=ToriiVermilion, 1=MossyGranite, 2=KawaraTile, 3=ShrineWoodOrnament, 4=ShopShutterSign, 5=FoliageLeafCutout
    for side in (-1, 1):
        px = side * 1.85
        add_cylinder(bm_t, (px, 0, 0.24), 0.38, 0.32, 0.48, segments=24, mat_idx=1)
        add_torus(bm_t, (px, 0, 0.50), 0.30, 0.045, major_segs=32, minor_segs=12, mat_idx=1)
        add_cylinder(bm_t, (px, 0, 0.82), 0.25, 0.24, 0.65, segments=36, mat_idx=2)
        add_cylinder(bm_t, (px, 0, 2.40), 0.23, 0.195, 4.42, segments=48, mat_idx=0)
        add_fern_and_weed_rosette(bm_t, (px - side * 0.32, -0.18, 0.02), scale=0.80, seed=700 + side, mat_idx=5)

    add_box(bm_t, (0, 0, 3.48), (4.88, 0.22, 0.28), mat_idx=0, uv_scale=0.4, bevel=0.016)
    for side in (-1, 1):
        for kx_off in (-0.24, 0.24):
            add_box(bm_t, (side * 1.85 + kx_off, 0, 3.48), (0.08, 0.30, 0.36), mat_idx=0, uv_scale=0.5, bevel=0.010)

    n_lintel = 28
    for i in range(n_lintel):
        tx = (i / (n_lintel - 1)) - 0.5
        x = tx * 5.55
        curve_z = (tx * 2.0) ** 2 * 0.28 + (abs(tx * 2.0) ** 4) * 0.08
        tilt_y = -tx * 0.24
        seg_w = (5.65 / n_lintel) * 1.12
        add_box(bm_t, (x, 0, 4.30 + curve_z), (seg_w, 0.32, 0.24), mat_idx=0, uv_scale=0.4, bevel=0.012, rot_euler=(0, tilt_y, 0))
        add_box(bm_t, (x, 0, 4.49 + curve_z), (seg_w * 1.04, 0.42, 0.15), mat_idx=2, uv_scale=0.4, bevel=0.012, rot_euler=(0, tilt_y, 0))

    add_box(bm_t, (0, 0, 3.92), (0.28, 0.20, 0.72), mat_idx=0, uv_scale=0.4, bevel=0.012)
    add_box(bm_t, (0, -0.14, 3.92), (0.72, 0.10, 0.92), mat_idx=4, uv_rect=(0.51, 0.505, 0.99, 0.745))
    add_box(bm_t, (0, -0.16, 4.40), (0.82, 0.14, 0.07), mat_idx=0, uv_scale=0.5, bevel=0.010)
    add_box(bm_t, (0, -0.16, 3.44), (0.82, 0.14, 0.07), mat_idx=0, uv_scale=0.5, bevel=0.010)
    add_box(bm_t, (-0.38, -0.16, 3.92), (0.07, 0.14, 0.96), mat_idx=0, uv_scale=0.5, bevel=0.010)
    add_box(bm_t, (0.38, -0.16, 3.92), (0.07, 0.14, 0.96), mat_idx=0, uv_scale=0.5, bevel=0.010)

    add_braided_shimenawa(bm_t, (0, -0.24, 3.36), span_w=3.55, base_r=0.14, sag=0.18, mat_idx=3)
    add_shide_zigzags(bm_t, (-1.15, -0.38, 0.38, 1.15), y_pos=-0.28, z_top=3.26, mat_idx=3)

    finalize_and_export(
        bm_t,
        "ToriiGate_Grand",
        ["ToriiVermilion", "MossyGranite", "KawaraTile", "ShrineWoodOrnament", "ShopShutterSign", "FoliageLeafCutout"],
        preview_offset=(0, 21.0, 0.0),
    )


def add_sculpted_lotus_petals(bm, center_z, ring_radius, petal_len, petal_w, num_petals, pitch_up, mat_idx):
    """Sculpted 3D cupped stone lotus petals (Rengeza / Kaeribana) around a pedestal."""
    for i in range(num_petals):
        ang = (i / float(num_petals)) * 2.0 * math.pi
        px = math.cos(ang) * ring_radius
        py = math.sin(ang) * ring_radius
        add_curved_leaf_card(
            bm,
            (px, py, center_z),
            length=petal_len,
            width=petal_w,
            yaw=ang - math.pi * 0.5,
            pitch=pitch_up,
            arch_droop=-0.025,
            v_fold=-0.018,
            roll=0.0,
            mat_idx=mat_idx,
            uv_rect=(0.1, 0.1, 0.9, 0.9),
            segs_l=4,
            segs_w=2,
        )


def build_stone_lantern_and_shrine():
    # 1. Soul-Sculpted Stone Lantern (Kasuga / Yukimi Ishidoro) - NO stacked cones or floating spheres!
    bm_l = bmesh.new()
    uv_l = bm_l.loops.layers.uv.verify()
    # Materials: 0=MossyGranite, 1=ShojiWindow, 2=FoliageLeafCutout
    # Hexagonal stepped base (Kiso) & carved inverted lotus seat (Kaeribana)
    add_cylinder(bm_l, (0, 0, 0.08), 0.46, 0.43, 0.16, segments=6, mat_idx=0, smooth=False)
    add_cylinder(bm_l, (0, 0, 0.23), 0.39, 0.28, 0.16, segments=18, mat_idx=0, smooth=True)
    add_sculpted_lotus_petals(bm_l, 0.28, 0.24, 0.13, 0.11, num_petals=12, pitch_up=-0.45, mat_idx=0)
    add_torus(bm_l, (0, 0, 0.34), 0.24, 0.036, major_segs=24, minor_segs=10, mat_idx=0)

    # Tapered cylindrical shaft (Sao) with central nodal ring (Fushi)
    add_cylinder(bm_l, (0, 0, 0.80), 0.165, 0.145, 0.92, segments=28, mat_idx=0, smooth=True)
    add_torus(bm_l, (0, 0, 0.80), 0.162, 0.028, major_segs=28, minor_segs=10, mat_idx=0)

    # Upper lotus platform (Chudai) with 12 upward-cupped lotus petals
    add_cylinder(bm_l, (0, 0, 1.32), 0.20, 0.37, 0.15, segments=18, mat_idx=0, smooth=True)
    add_sculpted_lotus_petals(bm_l, 1.26, 0.22, 0.16, 0.12, num_petals=12, pitch_up=0.52, mat_idx=0)
    add_cylinder(bm_l, (0, 0, 1.42), 0.39, 0.39, 0.05, segments=6, mat_idx=0, smooth=False)

    # Hollowed hexagonal fire chamber (Hibukuro) with glowing inner core, 6 corner pillars & window lattice bars
    add_cylinder(bm_l, (0, 0, 1.60), 0.22, 0.22, 0.34, segments=18, mat_idx=1, uv_rect=(0.2, 0.2, 0.8, 0.8))
    for i in range(6):
        ang = i * (math.pi / 3.0) + (math.pi / 6.0)
        px, py = math.cos(ang) * 0.275, math.sin(ang) * 0.275
        add_cylinder(bm_l, (px, py, 1.60), 0.038, 0.038, 0.36, segments=12, mat_idx=0)
        # Carved bottom wall panel (Renji) on alternating faces
        ang_face = i * (math.pi / 3.0)
        fx, fy = math.cos(ang_face) * 0.24, math.sin(ang_face) * 0.24
        add_box(bm_l, (fx, fy, 1.48), (0.04, 0.24, 0.10), mat_idx=0, uv_scale=0.5, rot_euler=(0, 0, ang_face))

    # Continuous Sculpted Hexagonal Pagoda Umbrella Roof (Kasa) with 6 raised hip ridges & upturned Warabite scrolls!
    u_segs_kasa = 36
    v_segs_kasa = 12
    kasa_grid = []
    for iv in range(v_segs_kasa + 1):
        tv = iv / float(v_segs_kasa)  # 0 at top apex (r=0.08), 1 at outer eave rim (r=0.56)
        ring = []
        for iu in range(u_segs_kasa):
            ang = (iu / float(u_segs_kasa)) * 2.0 * math.pi
            # Hexagonal contour modulation + 6 raised hip ribs (Kudari-mune)
            hex_mod = 1.0 / math.cos((ang % (math.pi / 3.0)) - (math.pi / 6.0))
            rib = max(0.0, math.cos(ang * 6.0)) ** 6
            r = (0.07 + 0.45 * (tv ** 1.08)) * (0.86 + 0.14 * hex_mod)
            # Sweeping S-curve pagoda roof profile + upturned Warabite scroll curl at corners
            z_base = 2.04 - 0.26 * (tv ** 0.85) + 0.04 * math.sin(tv * math.pi)
            warabite_curl = 0.065 * (tv ** 3.2) * rib
            rib_ridge = 0.024 * math.sin(tv * math.pi) * rib
            ring.append(bm_l.verts.new((math.cos(ang) * r, math.sin(ang) * r, z_base + warabite_curl + rib_ridge)))
        kasa_grid.append(ring)

    # Bottom soffit of Kasa roof
    kasa_bot_ring = []
    for iu in range(u_segs_kasa):
        co = kasa_grid[v_segs_kasa][iu].co
        kasa_bot_ring.append(bm_l.verts.new((co.x * 0.96, co.y * 0.96, co.z - 0.045)))
    v_kasa_bot_c = bm_l.verts.new((0.0, 0.0, 1.76))

    for iv in range(v_segs_kasa):
        for iu in range(u_segs_kasa):
            iun = (iu + 1) % u_segs_kasa
            f = bm_l.faces.new((kasa_grid[iv][iu], kasa_grid[iv + 1][iu], kasa_grid[iv + 1][iun], kasa_grid[iv][iun]))
            f.material_index = 0
            f.smooth = True
            for loop in f.loops:
                co = loop.vert.co
                loop[uv_l].uv = (co.x * 0.8 + 0.5, co.y * 0.8 + 0.5)

    for iu in range(u_segs_kasa):
        iun = (iu + 1) % u_segs_kasa
        fe = bm_l.faces.new((kasa_grid[v_segs_kasa][iu], kasa_bot_ring[iu], kasa_bot_ring[iun], kasa_grid[v_segs_kasa][iun]))
        fb = bm_l.faces.new((kasa_bot_ring[iun], kasa_bot_ring[iu], v_kasa_bot_c))
        for f in (fe, fb):
            f.material_index = 0
            f.smooth = True
            for loop in f.loops:
                co = loop.vert.co
                loop[uv_l].uv = (co.x * 0.8 + 0.5, co.y * 0.8 + 0.5)

    # Sacred flame jewel finial (Hoju) with lotus base (Ukebana)
    add_torus(bm_l, (0, 0, 2.05), 0.085, 0.025, major_segs=24, minor_segs=10, mat_idx=0)
    add_sphere(bm_l, (0, 0, 2.13), 0.075, scale=(1.0, 1.0, 1.35), u_segs=24, v_segs=16, mat_idx=0)
    add_cylinder(bm_l, (0, 0, 2.23), 0.038, 0.004, 0.09, segments=16, mat_idx=0)

    # Wild ferns & grass growing at the mossy base of the stone lantern!
    add_fern_and_weed_rosette(bm_l, (0.32, -0.22, 0.02), scale=0.65, seed=801, mat_idx=2)
    finalize_and_export(bm_l, "StoneLantern_Ishidoro", ["MossyGranite", "ShojiWindow", "FoliageLeafCutout"], preview_offset=(-2.5, 22.0, 0.0))

    # 2. High-Poly Main Village Shrine (YugiriShrine_Hokora)
    bm_h = bmesh.new()
    # Materials: 0=DarkWood, 1=ToriiVermilion, 2=KawaraTile, 3=MossyGranite, 4=ShrineWoodOrnament, 5=ShojiWindow, 6=ShopShutterSign
    add_box(bm_h, (0, 0, 0.42), (5.6, 4.8, 0.84), mat_idx=3, uv_scale=0.35, bevel=0.024)
    add_box(bm_h, (0, 0, 0.82), (5.76, 4.96, 0.08), mat_idx=3, uv_scale=0.4, bevel=0.016)
    add_box(bm_h, (0, -0.2, 0.90), (6.05, 5.25, 0.12), mat_idx=0, uv_scale=0.4, bevel=0.014)
    for sx in (-2.92, 2.92):
        add_box(bm_h, (sx, -0.2, 1.38), (0.09, 5.20, 0.08), mat_idx=1, uv_scale=0.5, bevel=0.010)
        add_box(bm_h, (sx, -0.2, 1.15), (0.06, 5.15, 0.05), mat_idx=1, uv_scale=0.5, bevel=0.008)
        for py in (-2.75, -1.35, 0.05, 1.45, 2.35):
            add_cylinder(bm_h, (sx, py, 1.22), 0.055, 0.055, 0.56, segments=16, mat_idx=1)
            add_sphere(bm_h, (sx, py, 1.54), 0.062, scale=(1.0, 1.0, 1.25), u_segs=16, v_segs=12, mat_idx=4, uv_rect=(0.62, 0.02, 0.98, 0.23))
    for rx_side in (-1, 1):
        rx_mid = rx_side * 1.98
        add_box(bm_h, (rx_mid, -2.75, 1.38), (1.88, 0.09, 0.08), mat_idx=1, uv_scale=0.5, bevel=0.010)
        add_cylinder(bm_h, (rx_side * 1.02, -2.75, 1.22), 0.055, 0.055, 0.56, segments=16, mat_idx=1)
        add_sphere(bm_h, (rx_side * 1.02, -2.75, 1.54), 0.062, scale=(1.0, 1.0, 1.25), u_segs=16, v_segs=12, mat_idx=4, uv_rect=(0.62, 0.02, 0.98, 0.23))

    for i in range(5):
        add_box(bm_h, (0, -2.8 - i * 0.28, (4.5 - i) * 0.17), (1.88, 0.30, 0.16), mat_idx=0, uv_scale=0.5, bevel=0.012)
    for sx in (-0.98, 0.98):
        add_box(bm_h, (sx, -3.35, 0.52), (0.10, 1.65, 0.22), mat_idx=0, uv_scale=0.5, bevel=0.012, rot_euler=(0.52, 0, 0))

    add_box(bm_h, (0, 0.15, 2.25), (4.6, 3.6, 2.65), mat_idx=0, uv_scale=0.35, bevel=0.016)
    for bx_i in range(17):
        bx = -2.20 + bx_i * 0.275
        if abs(bx) < 1.05:
            continue
        add_box(bm_h, (bx, -1.66, 2.25), (0.035, 0.04, 2.58), mat_idx=0, uv_scale=0.5, bevel=0.005)
    for sx in (-2.5, -1.1, 1.1, 2.5):
        add_cylinder(bm_h, (sx, -2.1, 2.22), 0.14, 0.125, 2.65, segments=32, mat_idx=1)
        # 3D Stepped Traditional Masugumi Bracket Complex (斗栱: 大斗 Daito + 肘木 Hijiki + 巻斗 Makito) atop each pillar!
        add_box(bm_h, (sx, -2.1, 3.38), (0.34, 0.34, 0.10), mat_idx=1, uv_scale=0.5, bevel=0.010)
        add_box(bm_h, (sx, -2.1, 3.47), (0.72, 0.22, 0.09), mat_idx=1, uv_scale=0.5, bevel=0.010)
        add_box(bm_h, (sx, -2.1, 3.47), (0.22, 0.72, 0.09), mat_idx=1, uv_scale=0.5, bevel=0.010)
        for mx_off in (-0.26, 0.0, 0.26):
            add_box(bm_h, (sx + mx_off, -2.1, 3.55), (0.14, 0.16, 0.08), mat_idx=4, uv_rect=(0.62, 0.02, 0.98, 0.23), bevel=0.008)
    # Penetrating tie beam (頭貫 - Kashiranuki) with protruding carved wooden beam ends (木鼻 - Kibana)
    add_box(bm_h, (0, -2.1, 3.24), (5.68, 0.18, 0.18), mat_idx=1, uv_scale=0.4, bevel=0.014)
    for sx_end in (-2.92, 2.92):
        add_cylinder(bm_h, (sx_end, -2.1, 3.24), 0.09, 0.06, 0.22, segments=16, mat_idx=4, rot_euler=(0, math.pi * 0.5, 0), uv_rect=(0.05, 0.55, 0.95, 0.95))

    add_box(bm_h, (0, -1.66, 2.15), (1.95, 0.08, 2.10), mat_idx=5, uv_rect=(0.0, 0.0, 1.0, 1.0))
    for lx in (-0.96, -0.64, -0.32, 0.0, 0.32, 0.64, 0.96):
        add_box(bm_h, (lx, -1.71, 2.15), (0.045, 0.08, 2.12), mat_idx=0, uv_scale=0.5, bevel=0.006)
    for lz in (1.15, 1.48, 1.81, 2.15, 2.48, 2.81, 3.15):
        add_box(bm_h, (0, -1.71, lz), (1.98, 0.08, 0.042), mat_idx=0, uv_scale=0.5, bevel=0.006)
    # Ornate gilt-brass corner hardware fittings (錺金具) on the shrine doors
    for dh_z in (1.48, 2.15, 2.81):
        for dh_x in (-0.94, -0.04, 0.04, 0.94):
            add_box(bm_h, (dh_x, -1.755, dh_z), (0.065, 0.015, 0.055), mat_idx=4, uv_rect=(0.62, 0.02, 0.98, 0.23))

    add_box(bm_h, (0, -1.78, 3.28), (1.15, 0.10, 0.52), mat_idx=6, uv_rect=(0.51, 0.505, 0.99, 0.745))
    add_box(bm_h, (0, -1.76, 3.28), (1.25, 0.08, 0.60), mat_idx=0, uv_scale=0.5, bevel=0.010)
    add_braided_shimenawa(bm_h, (0, -2.26, 3.22), span_w=4.6, base_r=0.12, sag=0.14, mat_idx=4)
    add_shide_zigzags(bm_h, (-1.5, -0.5, 0.5, 1.5), y_pos=-2.30, z_top=3.14, mat_idx=4)

    # Detailed Saisenbako (賽銭箱 - Wooden Coin Offering Box) with beveled coin-grid bars, iron corner straps & side handles!
    add_box(bm_h, (0, -2.15, 1.26), (1.32, 0.70, 0.64), mat_idx=4, uv_rect=(0.05, 0.55, 0.95, 0.95), bevel=0.012)
    add_box(bm_h, (0, -2.15, 0.96), (1.38, 0.76, 0.06), mat_idx=0, uv_scale=0.5, bevel=0.008)
    for slat_i in range(9):
        sy_slat = -2.43 + slat_i * 0.07
        add_box(bm_h, (0, sy_slat, 1.60), (1.20, 0.032, 0.042), mat_idx=0, uv_scale=0.5, bevel=0.005)
    for sb_side in (-0.67, 0.67):
        add_box(bm_h, (sb_side, -2.15, 1.26), (0.04, 0.36, 0.05), mat_idx=0, uv_scale=0.5, bevel=0.006)

    add_sphere(bm_h, (0, -2.05, 3.12), 0.21, scale=(1.0, 1.0, 0.95), u_segs=28, v_segs=18, mat_idx=4, uv_rect=(0.62, 0.02, 0.98, 0.23))
    add_torus(bm_h, (0, -2.05, 3.12), 0.215, 0.028, major_segs=28, minor_segs=12, mat_idx=4, uv_rect=(0.62, 0.02, 0.98, 0.23))
    for r_seg in range(18):
        rz = 1.48 + r_seg * 0.085
        r_rad = 0.055 - (r_seg / 18.0) * 0.015
        twist_x = math.sin(r_seg * 0.9) * 0.012
        add_sphere(bm_h, (twist_x, -2.05, rz), r_rad, scale=(1.0, 1.0, 1.1), u_segs=14, v_segs=10, mat_idx=4, uv_rect=(0.05, 0.28, 0.95, 0.48))

    add_pitched_kawara_roof(bm_h, (0, -0.1, 3.55), 6.8, 6.2, 1.85, mat_tile=2, mat_wood=0, curve_sag=0.14, add_rafters=True)
    for ky in (-1.8, -0.9, 0.0, 0.9, 1.8):
        add_cylinder(bm_h, (0, ky, 5.55), 0.115, 0.115, 0.98, segments=24, mat_idx=4, rot_euler=(0, math.pi * 0.5, 0), uv_rect=(0.05, 0.55, 0.95, 0.95))
    for sy_chigi in (-2.7, 2.5):
        for sx_chigi in (-1, 1):
            add_box(bm_h, (sx_chigi * 0.35, sy_chigi, 5.65), (0.09, 0.14, 1.45), mat_idx=4, uv_rect=(0.05, 0.55, 0.95, 0.95), bevel=0.010, rot_euler=(0, sx_chigi * 0.52, 0))

    finalize_and_export(
        bm_h,
        "YugiriShrine_Hokora",
        ["DarkWood", "ToriiVermilion", "KawaraTile", "MossyGranite", "ShrineWoodOrnament", "ShojiWindow", "ShopShutterSign"],
        preview_offset=(0, 36.0, 3.24),
    )


def build_street_and_shrine_props():
    # 1. Ultra-High-Poly Prop_ACUnit (室外機):
    # - Stamped sheet-metal cabinet with recessed top stiffening channels & side louver intake slots,
    # - Deep circular fan shroud + 3D 5-blade swept propeller fan + central hub nut,
    # - Concentric & radial wire finger-guard cage (6 concentric torus rings + 12 radial wire ribs),
    # - Right-side stamped valve cover (配管カバー) + wrapped dual refrigerant lines + drain hose + concrete mounting blocks (プラロック)!
    bm_ac = bmesh.new()
    # Materials: 0=ACUnitMetal, 1=RustedMetal
    add_box(bm_ac, (0, 0, 0.36), (0.82, 0.32, 0.58), mat_idx=0, uv_rect=(0.0, 0.0, 1.0, 1.0), bevel=0.018)
    # Stamped top lid with overhang lip & 3 recessed stiffening ribs
    add_box(bm_ac, (0, 0, 0.655), (0.84, 0.34, 0.025), mat_idx=0, uv_scale=0.5, bevel=0.008)
    for tx_rib in (-0.26, 0.0, 0.26):
        add_box(bm_ac, (tx_rib, 0, 0.67), (0.14, 0.26, 0.010), mat_idx=0, uv_scale=0.5, bevel=0.004)
    # Left-side intake louver slots
    for lv_z in range(8):
        add_box(bm_ac, (-0.415, 0, 0.18 + lv_z * 0.052), (0.012, 0.22, 0.028), mat_idx=1, uv_scale=0.5, rot_euler=(0, -0.35, 0))

    # Fan shroud + swept 5-blade propeller + concentric wire guard cage
    fan_cx, fan_cy, fan_cz = -0.13, -0.162, 0.36
    add_cylinder(bm_ac, (fan_cx, fan_cy + 0.015, fan_cz), 0.215, 0.215, 0.03, segments=32, mat_idx=1, rot_euler=(math.pi * 0.5, 0, 0))
    add_torus(bm_ac, (fan_cx, fan_cy, fan_cz), 0.215, 0.016, major_segs=32, minor_segs=10, mat_idx=0, rot_euler=(math.pi * 0.5, 0, 0), uv_rect=(0.72, 0.1, 0.95, 0.9))
    add_cylinder(bm_ac, (fan_cx, fan_cy + 0.005, fan_cz), 0.048, 0.042, 0.045, segments=18, mat_idx=1, rot_euler=(math.pi * 0.5, 0, 0))
    for b_i in range(5):
        ang = b_i * (2.0 * math.pi / 5.0)
        bx = fan_cx + math.cos(ang) * 0.115
        bz = fan_cz + math.sin(ang) * 0.115
        add_box(bm_ac, (bx, fan_cy + 0.010, bz), (0.13, 0.012, 0.072), mat_idx=1, uv_scale=0.5, bevel=0.003, rot_euler=(0.38, -ang, 0))
    # 6 Concentric wire guard rings + 8 radial wire struts in front of the fan!
    for r_ring in (0.04, 0.075, 0.11, 0.145, 0.18, 0.21):
        add_torus(bm_ac, (fan_cx, fan_cy - 0.012, fan_cz), r_ring, 0.0035, major_segs=28, minor_segs=6, mat_idx=1, rot_euler=(math.pi * 0.5, 0, 0))
    for r_i in range(8):
        ang = r_i * (math.pi / 8.0)
        add_cylinder(bm_ac, (fan_cx, fan_cy - 0.012, fan_cz), 0.0035, 0.0035, 0.42, segments=6, mat_idx=1, rot_euler=(0, ang, 0))

    # Molded concrete/resin mounting blocks (プラロック) + bolted steel feet
    for sx in (-0.29, 0.29):
        add_box(bm_ac, (sx, 0, 0.035), (0.11, 0.40, 0.07), mat_idx=1, uv_scale=0.5, bevel=0.010)
        add_box(bm_ac, (sx, 0, 0.075), (0.06, 0.34, 0.02), mat_idx=0, uv_scale=0.5, bevel=0.004)
    # Right-side service valve cover (配管カバー) + foam-insulated twin copper pipes + corrugated drain hose
    add_box(bm_ac, (0.425, -0.02, 0.34), (0.055, 0.14, 0.28), mat_idx=0, uv_scale=0.5, bevel=0.010)
    add_cylinder(bm_ac, (0.45, 0.04, 0.46), 0.026, 0.026, 0.68, segments=16, mat_idx=1)
    add_cylinder(bm_ac, (0.49, 0.08, 0.42), 0.018, 0.018, 0.62, segments=14, mat_idx=1)
    for tie_z in (0.24, 0.40, 0.56, 0.72):
        add_torus(bm_ac, (0.47, 0.06, tie_z), 0.042, 0.005, major_segs=16, minor_segs=6, mat_idx=1)
    # Corrugated drain hose trailing along the ground at the right base
    for dh_i in range(8):
        add_cylinder(bm_ac, (0.45 + dh_i * 0.025, 0.04 + dh_i * 0.015, 0.06 - dh_i * 0.005), 0.012, 0.012, 0.035, segments=10, mat_idx=0, rot_euler=(0, 1.35, 0))
    finalize_and_export(bm_ac, "Prop_ACUnit", ["ACUnitMetal", "RustedMetal"], preview_offset=(5.0, 0.0, 0.0))

    # 2. High-Poly Prop_Postbox (郵便差出箱1号丸型 - Showa Retro Pillar Postbox)
    bm_pb = bmesh.new()
    # Stepped cast-iron octagonal/cylindrical base + lower collection door with hinge knuckles & brass lock plate
    add_cylinder(bm_pb, (0, 0, 0.08), 0.31, 0.29, 0.16, segments=36, mat_idx=1)
    add_cylinder(bm_pb, (0, 0, 0.21), 0.28, 0.26, 0.12, segments=36, mat_idx=1)
    add_torus(bm_pb, (0, 0, 0.28), 0.26, 0.028, major_segs=36, minor_segs=12, mat_idx=0, uv_rect=(0.02, 0.52, 0.23, 0.98))
    add_cylinder(bm_pb, (0, 0, 0.78), 0.245, 0.245, 1.02, segments=40, mat_idx=0, uv_rect=(0.02, 0.52, 0.23, 0.98))
    # Lower collection door frame & hinge knuckles on front (-Y)
    add_box(bm_pb, (0, -0.242, 0.56), (0.22, 0.02, 0.34), mat_idx=0, uv_rect=(0.02, 0.52, 0.23, 0.98), bevel=0.006)
    for hk_z in (0.44, 0.68):
        add_cylinder(bm_pb, (-0.11, -0.25, hk_z), 0.012, 0.012, 0.045, segments=10, mat_idx=1)
    add_cylinder(bm_pb, (0.08, -0.252, 0.56), 0.016, 0.016, 0.02, segments=12, mat_idx=1, rot_euler=(math.pi * 0.5, 0, 0))
    # Molded body rings + domed cap + recessed mail slot with curved rain visor hood
    add_torus(bm_pb, (0, 0, 0.92), 0.248, 0.018, major_segs=36, minor_segs=10, mat_idx=0, uv_rect=(0.02, 0.85, 0.23, 0.98))
    add_torus(bm_pb, (0, 0, 1.24), 0.255, 0.022, major_segs=36, minor_segs=12, mat_idx=0, uv_rect=(0.02, 0.85, 0.23, 0.98))
    add_sphere(bm_pb, (0, 0, 1.26), 0.275, scale=(1.0, 1.0, 0.52), u_segs=36, v_segs=16, mat_idx=0, uv_rect=(0.02, 0.85, 0.23, 0.98))
    add_box(bm_pb, (0, -0.245, 1.08), (0.24, 0.07, 0.11), mat_idx=0, uv_rect=(0.02, 0.85, 0.23, 0.98), bevel=0.010)
    add_box(bm_pb, (0, -0.26, 1.135), (0.26, 0.09, 0.025), mat_idx=0, uv_rect=(0.02, 0.85, 0.23, 0.98), bevel=0.006, rot_euler=(0.18, 0, 0))
    add_box(bm_pb, (0, -0.24, 1.06), (0.20, 0.06, 0.04), mat_idx=1, uv_scale=0.5)
    # Collection timetable plate holder on lower front
    add_box(bm_pb, (0, -0.248, 0.81), (0.15, 0.02, 0.11), mat_idx=1, uv_scale=0.5, bevel=0.004)
    finalize_and_export(bm_pb, "Prop_Postbox", ["PropsAtlas", "RustedMetal"], preview_offset=(5.0, 2.0, 0.0))

    # 3. High-Poly Prop_CurveMirror (道路反射鏡 - Convex Roadside Mirror with Top Visor Hood & Bolted Brackets)
    bm_cm = bmesh.new()
    add_cylinder(bm_cm, (0, 0, 1.48), 0.042, 0.042, 2.96, segments=24, mat_idx=2)
    add_cylinder(bm_cm, (0, 0, 0.12), 0.12, 0.08, 0.24, segments=20, mat_idx=2)
    add_cylinder(bm_cm, (0, 0, 0.015), 0.16, 0.16, 0.03, segments=24, mat_idx=2)
    # Pole-top cap + ribbed cast-iron mirror mounting bracket
    add_sphere(bm_cm, (0, 0, 2.96), 0.048, scale=(1.0, 1.0, 0.6), u_segs=16, v_segs=10, mat_idx=2)
    add_box(bm_cm, (0, -0.07, 2.55), (0.10, 0.16, 0.14), mat_idx=2, uv_scale=0.5, bevel=0.008)
    for cl_z in (2.49, 2.61):
        add_torus(bm_cm, (0, 0, cl_z), 0.048, 0.010, major_segs=20, minor_segs=8, mat_idx=2)
    # Orange cushioned mirror rim + convex mirror dome + top rain visor hood (フード)
    add_torus(bm_cm, (0, -0.13, 2.55), 0.40, 0.042, major_segs=40, minor_segs=14, mat_idx=0, rot_euler=(math.pi * 0.5, 0, 0), uv_rect=(0.27, 0.52, 0.31, 0.56))
    add_cylinder(bm_cm, (0, -0.11, 2.55), 0.41, 0.39, 0.08, segments=40, mat_idx=0, rot_euler=(math.pi * 0.5, 0, 0), uv_rect=(0.27, 0.52, 0.31, 0.56))
    add_sphere(bm_cm, (0, -0.11, 2.55), 0.37, scale=(1.0, 0.24, 1.0), u_segs=36, v_segs=18, mat_idx=0, uv_rect=(0.30, 0.56, 0.45, 0.94))
    # Curved upper rain visor hood overhanging the top half of the mirror
    for v_i in range(11):
        vang = -0.35 + (v_i / 10.0) * (math.pi + 0.70)
        vx = math.cos(vang) * 0.425
        vz = 2.55 + math.sin(vang) * 0.425
        if vz > 2.52:
            add_box(bm_cm, (vx, -0.17, vz), (0.13, 0.11, 0.016), mat_idx=0, uv_rect=(0.27, 0.52, 0.31, 0.56), rot_euler=(0, vang - math.pi * 0.5, 0))
    # Warning sign ("立入禁止") with metal frame & U-bolt pole clamps
    add_box(bm_cm, (0, -0.055, 1.55), (0.52, 0.022, 0.38), mat_idx=1, uv_rect=(0.675, 0.755, 0.99, 0.99), rot_euler=(0, 0.022, 0))
    add_box(bm_cm, (0, -0.045, 1.55), (0.55, 0.018, 0.41), mat_idx=2, uv_scale=0.5, bevel=0.006, rot_euler=(0, 0.022, 0))
    for ub_z in (1.40, 1.70):
        add_torus(bm_cm, (0, 0, ub_z), 0.046, 0.008, major_segs=18, minor_segs=6, mat_idx=2)
    finalize_and_export(bm_cm, "Prop_CurveMirror", ["PropsAtlas", "ShopShutterSign", "RustedMetal"], preview_offset=(5.0, 4.0, 0.0))

    # 4. Ultra-High-Poly Prop_Bicycle (Japanese Mamachari ママチャリ City Bicycle):
    # - Smooth 28-segment curved tubular mudguards/fenders (NO blocky rectangles!) with thin fender stays,
    # - 24-spoke laced wheels with hub flanges & valve stems,
    # - Curved swan-neck step-through frame, front fork crown & block dynamo headlight (ダイナモライト),
    # - Sprung saddle with 2 coiled chrome springs, crankset with pedals, kickstand (両立スタンド),
    # - Rear tubular steel luggage carrier rack (荷台) with rear reflector,
    # - Swept-back kamakiri/city handlebars with brake levers, bell (ベル), bowed brake cables & fine-wire front basket!
    bm_bi = bmesh.new()
    # Materials: 0=RustedMetal, 1=PropsAtlas
    uv_tire = (0.78, 0.55, 0.98, 0.95)
    uv_frame = (0.55, 0.72, 0.72, 0.96)
    uv_orange = (0.27, 0.52, 0.31, 0.56)

    for w_idx, wy in enumerate((-0.55, 0.55)):
        # Rubber tire + chrome steel rim + hub + axle nuts
        add_torus(bm_bi, (0, wy, 0.34), 0.31, 0.028, major_segs=48, minor_segs=14, mat_idx=1, rot_euler=(0, math.pi * 0.5, 0), uv_rect=uv_tire)
        add_torus(bm_bi, (0, wy, 0.34), 0.282, 0.011, major_segs=48, minor_segs=10, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
        add_cylinder(bm_bi, (0, wy, 0.34), 0.024, 0.024, 0.095, segments=18, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
        for fl_x in (-0.032, 0.032):
            add_cylinder(bm_bi, (fl_x, wy, 0.34), 0.034, 0.034, 0.006, segments=18, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
        # 24 crossed wire spokes per wheel!
        for sp_i in range(24):
            ang = sp_i * (math.pi / 12.0)
            sy = wy + math.cos(ang) * 0.14
            sz = 0.34 + math.sin(ang) * 0.14
            sx_off = 0.014 if (sp_i % 2 == 0) else -0.014
            add_cylinder(bm_bi, (sx_off, sy, sz), 0.0028, 0.0028, 0.28, segments=6, mat_idx=0, rot_euler=(ang + math.pi * 0.5, sx_off * 0.6, 0))
        # Smooth 28-segment curved tubular mudguard/fender (泥除け) hugging the wheel arc + V-stay rods!
        f_start = -0.25 if w_idx == 1 else -0.10
        f_end = math.pi + (0.35 if w_idx == 1 else 0.15)
        n_fsegs = 28
        for f_i in range(n_fsegs):
            fa0 = f_start + (f_i / float(n_fsegs)) * (f_end - f_start)
            fa1 = f_start + ((f_i + 1) / float(n_fsegs)) * (f_end - f_start)
            fam = 0.5 * (fa0 + fa1)
            fy_m = wy + math.cos(fam) * 0.346
            fz_m = 0.34 + math.sin(fam) * 0.346
            arc_len = 0.346 * abs(fa1 - fa0) * 1.08
            add_cylinder(bm_bi, (0, fy_m, fz_m), 0.030, 0.030, arc_len, segments=12, mat_idx=0, rot_euler=(fam, 0, 0))
        # Fender support stay wires (ドロヨケステー) connecting axle to fender
        for sx_st in (-0.042, 0.042):
            add_cylinder(bm_bi, (sx_st, wy + (0.17 if w_idx == 1 else -0.17), 0.34), 0.0035, 0.0035, 0.34, segments=6, mat_idx=0, rot_euler=(math.pi * 0.5, 0, 0))

    # Front Fork Blades + Crown + Block Dynamo Headlight (ダイナモライト)
    for fk_x in (-0.045, 0.045):
        add_cylinder(bm_bi, (fk_x, -0.50, 0.49), 0.013, 0.010, 0.36, segments=12, mat_idx=1, rot_euler=(-0.22, 0, 0), uv_rect=uv_frame)
    add_box(bm_bi, (0, -0.46, 0.66), (0.11, 0.038, 0.032), mat_idx=1, uv_rect=uv_frame, bevel=0.006)
    add_cylinder(bm_bi, (-0.075, -0.52, 0.58), 0.024, 0.018, 0.075, segments=16, mat_idx=0, rot_euler=(math.pi * 0.45, 0, 0))
    add_sphere(bm_bi, (-0.075, -0.555, 0.585), 0.022, scale=(1.0, 0.4, 1.0), u_segs=14, v_segs=10, mat_idx=1, uv_rect=(0.30, 0.56, 0.45, 0.94))

    # Head Tube + Curved Step-Through Swan Down-Tube + Seat Tube + Chainstays & Seatstays
    add_cylinder(bm_bi, (0, -0.43, 0.78), 0.019, 0.019, 0.24, segments=16, mat_idx=1, rot_euler=(-0.22, 0, 0), uv_rect=uv_frame)
    for dt_i in range(10):
        t_d = dt_i / 9.0
        dy0 = -0.42 + t_d * 0.52
        dz0 = 0.76 - 0.38 * math.sin(t_d * math.pi * 0.68) - 0.08 * t_d
        pitch_d = 1.05 + 0.35 * t_d
        add_cylinder(bm_bi, (0, dy0, dz0), 0.017, 0.017, 0.075, segments=14, mat_idx=1, rot_euler=(pitch_d, 0, 0), uv_rect=uv_frame)
    add_cylinder(bm_bi, (0, 0.14, 0.58), 0.018, 0.018, 0.54, segments=16, mat_idx=1, rot_euler=(0.18, 0, 0), uv_rect=uv_frame)
    for cs_x in (-0.038, 0.038):
        add_cylinder(bm_bi, (cs_x, 0.32, 0.34), 0.011, 0.009, 0.44, segments=10, mat_idx=1, rot_euler=(math.pi * 0.5, 0, 0), uv_rect=uv_frame)
        add_cylinder(bm_bi, (cs_x, 0.34, 0.52), 0.010, 0.009, 0.48, segments=10, mat_idx=1, rot_euler=(0.98, 0, 0), uv_rect=uv_frame)

    # Full stamped sheet-metal Chain Case (チェーンケース) + Crank Arms & Pedals with orange reflectors!
    add_box(bm_bi, (0.042, 0.28, 0.34), (0.028, 0.46, 0.11), mat_idx=0, uv_scale=0.5, bevel=0.014)
    add_cylinder(bm_bi, (0.042, 0.09, 0.34), 0.085, 0.085, 0.030, segments=24, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
    add_cylinder(bm_bi, (0, 0.09, 0.34), 0.022, 0.022, 0.14, segments=14, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
    for pd_side in (-1, 1):
        px_c = pd_side * 0.075
        pz_c = 0.34 + pd_side * 0.08
        py_c = 0.09 + pd_side * 0.12
        add_cylinder(bm_bi, (px_c, 0.09 + pd_side * 0.06, 0.34 + pd_side * 0.04), 0.008, 0.008, 0.16, segments=10, mat_idx=0, rot_euler=(0.95, 0, 0))
        add_box(bm_bi, (px_c + pd_side * 0.035, py_c, pz_c), (0.075, 0.055, 0.018), mat_idx=1, uv_rect=uv_tire, bevel=0.004)

    # Rear Hinged Double-Leg Kickstand (両立スタンド) resting firmly on the ground + Rear Luggage Rack (荷台) & Reflector
    for ks_x in (-0.09, 0.09):
        add_cylinder(bm_bi, (ks_x, 0.58, 0.17), 0.008, 0.008, 0.36, segments=10, mat_idx=0, rot_euler=(-0.18, ks_x * 1.4, 0))
    add_cylinder(bm_bi, (0, 0.61, 0.012), 0.008, 0.008, 0.22, segments=10, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
    # Tubular rear carrier rack (荷台)
    for rk_x in (-0.085, 0.085):
        add_cylinder(bm_bi, (rk_x, 0.50, 0.72), 0.008, 0.008, 0.44, segments=10, mat_idx=0, rot_euler=(math.pi * 0.5, 0, 0))
        add_cylinder(bm_bi, (rk_x, 0.56, 0.53), 0.007, 0.007, 0.38, segments=10, mat_idx=0, rot_euler=(0.08, 0, 0))
    for rk_y in (0.32, 0.44, 0.56, 0.68):
        add_cylinder(bm_bi, (0, rk_y, 0.72), 0.007, 0.007, 0.17, segments=10, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
    # Rear red safety reflector under the carrier rack
    add_cylinder(bm_bi, (0, 0.89, 0.44), 0.022, 0.022, 0.016, segments=16, mat_idx=1, rot_euler=(math.pi * 0.42, 0, 0), uv_rect=uv_orange)

    # Sprung Comfort Saddle (サドル) with chrome seatpost & 2 coiled suspension springs underneath!
    add_cylinder(bm_bi, (0, 0.18, 0.82), 0.013, 0.013, 0.14, segments=14, mat_idx=0, rot_euler=(0.18, 0, 0))
    for sp_x in (-0.045, 0.045):
        for coil_z in (0.81, 0.825, 0.84):
            add_torus(bm_bi, (sp_x, 0.22, coil_z), 0.018, 0.004, major_segs=14, minor_segs=6, mat_idx=0)
    add_sphere(bm_bi, (0, 0.19, 0.87), 0.115, scale=(0.88, 1.18, 0.34), u_segs=24, v_segs=14, mat_idx=1, uv_rect=uv_tire)

    # Quill Stem + Swept-Back City Handlebars + Brake Levers + Bell (ベル) + Bowed Brake Cables + Wire Front Basket!
    add_cylinder(bm_bi, (0, -0.45, 0.96), 0.013, 0.013, 0.22, segments=14, mat_idx=0, rot_euler=(-0.18, 0, 0))
    add_cylinder(bm_bi, (0, -0.45, 1.05), 0.012, 0.012, 0.34, segments=14, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
    for hb_side in (-1, 1):
        add_cylinder(bm_bi, (hb_side * 0.20, -0.39, 1.05), 0.012, 0.012, 0.16, segments=12, mat_idx=0, rot_euler=(math.pi * 0.5, 0, hb_side * 0.42))
        add_cylinder(bm_bi, (hb_side * 0.24, -0.31, 1.05), 0.017, 0.017, 0.12, segments=14, mat_idx=1, rot_euler=(math.pi * 0.5, 0, hb_side * 0.15), uv_rect=uv_tire)
        # Brake levers & bowed brake cables
        add_cylinder(bm_bi, (hb_side * 0.21, -0.36, 1.03), 0.004, 0.004, 0.10, segments=8, mat_idx=0, rot_euler=(math.pi * 0.5, 0, -hb_side * 0.25))
        add_torus(bm_bi, (hb_side * 0.11, -0.48, 0.88), 0.15, 0.003, major_segs=20, minor_segs=6, mat_idx=1, rot_euler=(0.2, math.pi * 0.4, 0), uv_rect=uv_tire)
    # Chrome bicycle bell on right handlebar
    add_sphere(bm_bi, (0.14, -0.43, 1.075), 0.022, scale=(1.0, 1.0, 0.65), u_segs=16, v_segs=10, mat_idx=0)
    # Fine-mesh Wire Front Basket (前カゴ) with top rim hoop & vertical/horizontal wire grid!
    bsk_y, bsk_z = -0.60, 0.85
    for rz_b, wx_b, wy_b in ((0.73, 0.30, 0.22), (0.81, 0.33, 0.24), (0.89, 0.36, 0.26), (0.97, 0.38, 0.28)):
        add_box(bm_bi, (0, bsk_y - wy_b * 0.5, rz_b), (wx_b, 0.008, 0.008), mat_idx=0, uv_scale=0.5)
        add_box(bm_bi, (0, bsk_y + wy_b * 0.5, rz_b), (wx_b, 0.008, 0.008), mat_idx=0, uv_scale=0.5)
        add_box(bm_bi, (-wx_b * 0.5, bsk_y, rz_b), (0.008, wy_b, 0.008), mat_idx=0, uv_scale=0.5)
        add_box(bm_bi, (wx_b * 0.5, bsk_y, rz_b), (0.008, wy_b, 0.008), mat_idx=0, uv_scale=0.5)
    for wv_i in range(-3, 4):
        vx_b = wv_i * 0.048
        add_box(bm_bi, (vx_b, bsk_y - 0.125, 0.85), (0.005, 0.005, 0.24), mat_idx=0, uv_scale=0.5, rot_euler=(-0.12, 0, 0))
        add_box(bm_bi, (vx_b, bsk_y + 0.125, 0.85), (0.005, 0.005, 0.24), mat_idx=0, uv_scale=0.5, rot_euler=(0.12, 0, 0))
        add_box(bm_bi, (vx_b, bsk_y, 0.73), (0.005, 0.22, 0.005), mat_idx=0, uv_scale=0.5)
    finalize_and_export(bm_bi, "Prop_Bicycle", ["RustedMetal", "PropsAtlas"], preview_offset=(5.0, 6.0, 0.0))

    # 5. Soul-Crafted Prop_AlleyClutter:
    # - Ribbed blue poly bin with slightly askew lid & side carrying handles,
    # - 2 multi-frequency wrinkled LDPE trash bags with rabbit-ear knot ties (NO sphere+cone!),
    # - 1 Japanese plastic beer crate ("夕霧麦酒") with 9 3D glass bottles inside,
    # - Terracotta plant pot overflowing with 35 individual 3D arched fern fronds, veined Hosta leaves & grass blades!
    bm_cl = bmesh.new()
    # Materials: 0=PropsAtlas, 1=FoliageLeafCutout
    add_cylinder(bm_cl, (-0.42, -0.05, 0.38), 0.23, 0.28, 0.74, segments=32, mat_idx=0, uv_rect=(0.52, 0.72, 0.73, 0.98))
    for rib_z in (0.22, 0.42, 0.62, 0.74):
        r_rib = 0.23 + (rib_z / 0.74) * 0.055
        add_torus(bm_cl, (-0.42, -0.05, rib_z), r_rib, 0.014, major_segs=32, minor_segs=10, mat_idx=0, uv_rect=(0.52, 0.72, 0.73, 0.98))
    for h_side in (-1, 1):
        add_torus(bm_cl, (-0.42 + h_side * 0.28, -0.05, 0.66), 0.045, 0.010, major_segs=16, minor_segs=8, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0), uv_rect=(0.52, 0.72, 0.73, 0.98))
    # Slightly tilted/askew lid on top of the blue garbage bin for human realism!
    add_cylinder(bm_cl, (-0.40, -0.03, 0.77), 0.30, 0.25, 0.06, segments=32, mat_idx=0, rot_euler=(0.06, -0.08, 0.2), uv_rect=(0.52, 0.72, 0.73, 0.98))
    add_box(bm_cl, (-0.40, -0.03, 0.82), (0.16, 0.04, 0.04), mat_idx=0, uv_rect=(0.52, 0.72, 0.73, 0.98), bevel=0.008, rot_euler=(0.06, -0.08, 0.2))

    # 2 Sculpted multi-frequency wrinkled polyethylene trash bags with rabbit-ear knot ties!
    add_wrinkled_trash_bag(bm_cl, (0.12, -0.22, 0.0), radius=0.25, height=0.52, seed=901, mat_idx=0)
    add_wrinkled_trash_bag(bm_cl, (0.42, 0.05, 0.0), radius=0.21, height=0.44, seed=902, mat_idx=0)

    # Molded Japanese plastic beer crate with 9 3D glass beer bottles inside!
    add_plastic_beer_crate(bm_cl, (0.26, 0.48, 0.0), rot_z=0.32, mat_idx=0)

    # Terracotta plant pot with rim collar + dark soil mound + 32-leaf 3D fern & Hosta rosette (NO stacked cones!)
    pot_x, pot_y = -0.08, 0.36
    add_cylinder(bm_cl, (pot_x, pot_y, 0.16), 0.14, 0.19, 0.32, segments=28, mat_idx=0, uv_rect=(0.02, 0.02, 0.45, 0.46))
    add_torus(bm_cl, (pot_x, pot_y, 0.31), 0.19, 0.024, major_segs=28, minor_segs=10, mat_idx=0, uv_rect=(0.02, 0.02, 0.45, 0.46))
    add_sphere(bm_cl, (pot_x, pot_y, 0.29), 0.17, scale=(1.0, 1.0, 0.25), u_segs=16, v_segs=10, mat_idx=0, uv_rect=(0.02, 0.02, 0.20, 0.20))
    add_fern_and_weed_rosette(bm_cl, (pot_x, pot_y, 0.31), scale=1.05, seed=905, mat_idx=1, include_ferns=True, include_broadleaf=True, include_grass=True)

    finalize_and_export(bm_cl, "Prop_AlleyClutter", ["PropsAtlas", "FoliageLeafCutout"], preview_offset=(5.0, 8.0, 0.0))

    # 6. Soul-Sculpted Prop_JizoStatue:
    # Continuous lathe-sculpted monk robe & shoulders + spherical ovoid head with serene facial relief & Fukumimi ears +
    # 16 cupped 3D lotus petals + non-clipping outer draped red cotton bib + stacked prayer pebbles (賽の河原の小石) & base fern!
    bm_jz = bmesh.new()
    uv_jz = bm_jz.loops.layers.uv.verify()
    # Materials: 0=MossyGranite, 1=PropsAtlas, 2=FoliageLeafCutout
    # Octagonal/cylindrical stepped stone base & 16 sculpted 3D lotus petals (Rengeza)
    add_cylinder(bm_jz, (0, 0, 0.07), 0.31, 0.28, 0.14, segments=24, mat_idx=0)
    add_torus(bm_jz, (0, 0, 0.16), 0.23, 0.042, major_segs=28, minor_segs=12, mat_idx=0)
    add_sculpted_lotus_petals(bm_jz, 0.15, 0.21, 0.14, 0.10, num_petals=16, pitch_up=0.58, mat_idx=0)

    def jizo_robe_xy(z_val, ang):
        s = max(0.0, min(1.0, (z_val - 0.20) / 0.58))
        rx = 0.195 * (1.0 - 0.16 * s) + 0.022 * math.sin(s * math.pi)
        ry = 0.165 * (1.0 - 0.18 * s) + 0.016 * math.sin(s * math.pi)
        if s > 0.76:
            sh = (s - 0.76) / 0.24
            sh_smooth = sh * sh * (3.0 - 2.0 * sh)
            rx = rx * (1.0 - sh_smooth) + 0.076 * sh_smooth
            ry = ry * (1.0 - sh_smooth) + 0.074 * sh_smooth
        ca, sa = math.cos(ang), math.sin(ang)
        frontness = max(0.0, -sa)
        shoulder_fade = 1.0 - max(0.0, (s - 0.72) / 0.28)
        drape = 0.008 * math.cos(ang * 7.0) * math.sin(s * math.pi) * shoulder_fade
        sleeve_env = math.exp(-((s - 0.42) / 0.16) ** 2) * (frontness ** 2.2)
        hands_bump = 0.028 * sleeve_env * (0.65 + 0.35 * math.cos(ca * 10.0))
        return ca * (rx + drape), sa * (ry + drape + hands_bump)

    # Sculpted Stone Monk Robe, Clasped Hands, Shoulders & Neck (z=0.20 to z=0.78)
    u_jz = 36
    v_jz = 24
    jz_grid = []
    for iv in range(v_jz + 1):
        tv = iv / float(v_jz)
        z = 0.20 + tv * 0.58
        ring = []
        for iu in range(u_jz):
            ang = (iu / float(u_jz)) * 2.0 * math.pi
            x, y = jizo_robe_xy(z, ang)
            ring.append(bm_jz.verts.new((x, y, z)))
        jz_grid.append(ring)

    for iv in range(v_jz):
        for iu in range(u_jz):
            iun = (iu + 1) % u_jz
            f = bm_jz.faces.new((jz_grid[iv][iu], jz_grid[iv][iun], jz_grid[iv + 1][iun], jz_grid[iv + 1][iu]))
            f.material_index = 0
            f.smooth = True
            for k, loop in enumerate(f.loops):
                lu = (iu + (1 if k in (1, 2) else 0)) / float(u_jz)
                lv = (iv + (1 if k in (2, 3) else 0)) / float(v_jz) * 0.7
                loop[uv_jz].uv = (lu, lv)

    # Serene Spherical-Ovoid Monk Head (Jizo Bosatsu) with carved brow, meditating eyes, gentle nose & Fukumimi ears!
    u_hd = 36
    v_hd = 18
    hd_grid = []
    for iv in range(v_hd + 1):
        tv = iv / float(v_hd)
        theta = (0.16 + tv * 0.80) * math.pi
        sin_t = math.sin(theta)
        cos_t = math.cos(theta)
        z_h = 0.905 - cos_t * 0.152
        rx_h = 0.136 * sin_t
        ry_h = 0.142 * sin_t
        ring = []
        for iu in range(u_hd):
            ang = (iu / float(u_hd)) * 2.0 * math.pi
            ca, sa = math.cos(ang), math.sin(ang)
            x = ca * rx_h
            y = -0.008 + sa * ry_h
            front_face = max(0.0, -sa) ** 2.8
            ear_side = max(0.0, abs(ca) - 0.80) / 0.20
            ear_env = math.exp(-((tv - 0.44) / 0.20) ** 2) * (ear_side ** 1.4)
            x += (1.0 if ca > 0 else -1.0) * 0.025 * ear_env
            nose_env = math.exp(-((tv - 0.45) / 0.13) ** 2) * math.exp(-((ca) / 0.18) ** 2) * front_face
            brow_env = math.exp(-((tv - 0.56) / 0.06) ** 2) * math.exp(-((ca) / 0.52) ** 2) * front_face
            eye_recess = math.exp(-((tv - 0.49) / 0.05) ** 2) * math.exp(-((abs(ca) - 0.25) / 0.13) ** 2) * front_face
            y -= (0.016 * nose_env + 0.009 * brow_env - 0.007 * eye_recess)
            ring.append(bm_jz.verts.new((x, y, z_h)))
        hd_grid.append(ring)

    v_hd_top = bm_jz.verts.new((0.0, -0.008, 1.058))
    for iv in range(v_hd):
        for iu in range(u_hd):
            iun = (iu + 1) % u_hd
            f = bm_jz.faces.new((hd_grid[iv][iu], hd_grid[iv][iun], hd_grid[iv + 1][iun], hd_grid[iv + 1][iu]))
            f.material_index = 0
            f.smooth = True
            for k, loop in enumerate(f.loops):
                lu = (iu + (1 if k in (1, 2) else 0)) / float(u_hd)
                lv = 0.70 + (iv + (1 if k in (2, 3) else 0)) / float(v_hd) * 0.28
                loop[uv_jz].uv = (lu, lv)
    for iu in range(u_hd):
        iun = (iu + 1) % u_hd
        ft = bm_jz.faces.new((hd_grid[v_hd][iu], hd_grid[v_hd][iun], v_hd_top))
        ft.material_index = 0
        ft.smooth = True
        for loop in ft.loops:
            loop[uv_jz].uv = (0.5, 0.99)

    # Contoured 3D Draped Red Woven Cotton Bib (Yodarekake) strictly outside jizo_robe_xy (+2.4cm clearance) so ZERO clipping occurs!
    u0_b, v0_b, u1_b, v1_b = (0.78, 0.05, 0.98, 0.45)
    add_torus(bm_jz, (0.0, -0.005, 0.765), 0.092, 0.018, major_segs=32, minor_segs=10, mat_idx=1, uv_rect=(u0_b, v0_b, u1_b, v1_b))
    u_bib = 36
    v_bib = 12
    bib_grid = []
    for iv in range(v_bib + 1):
        tv = iv / float(v_bib)
        ring = []
        for iu in range(u_bib):
            ang = (iu / float(u_bib)) * 2.0 * math.pi
            ca, sa = math.cos(ang), math.sin(ang)
            front_bias = 0.55 + 0.45 * (-sa)
            drop = tv * (0.065 + 0.165 * front_bias)
            z_b = 0.765 - drop
            bx_body, by_body = jizo_robe_xy(z_b, ang)
            pleat = 0.007 * math.sin(tv * math.pi) * math.sin(ang * 11.0)
            clearance = 0.024 + 0.008 * tv + pleat
            ring.append(bm_jz.verts.new((bx_body + ca * clearance, by_body + sa * clearance, z_b)))
        bib_grid.append(ring)

    for iv in range(v_bib):
        for iu in range(u_bib):
            iun = (iu + 1) % u_bib
            f = bm_jz.faces.new((bib_grid[iv][iu], bib_grid[iv + 1][iu], bib_grid[iv + 1][iun], bib_grid[iv][iun]))
            f.material_index = 1
            f.smooth = True
            for k, loop in enumerate(f.loops):
                lu = (iu + (1 if k in (2, 3) else 0)) / float(u_bib)
                lv = (iv + (1 if k in (1, 2) else 0)) / float(v_bib)
                loop[uv_jz].uv = (u0_b + lu * (u1_b - u0_b), v0_b + lv * (v1_b - v0_b))

    pebble_stacks = [
        (0.21, -0.14, 0.14, 0.042),
        (0.21, -0.14, 0.18, 0.033),
        (0.21, -0.14, 0.21, 0.024),
        (-0.22, -0.12, 0.14, 0.038),
        (-0.22, -0.12, 0.175, 0.028),
    ]
    for px, py, pz, pr in pebble_stacks:
        add_sphere(bm_jz, (px, py, pz), pr, scale=(1.2, 1.0, 0.62), u_segs=14, v_segs=10, mat_idx=0)
    add_fern_and_weed_rosette(bm_jz, (-0.24, 0.18, 0.02), scale=0.55, seed=915, mat_idx=2)

    finalize_and_export(bm_jz, "Prop_JizoStatue", ["MossyGranite", "PropsAtlas", "FoliageLeafCutout"], preview_offset=(5.0, 10.0, 0.0))

    # 7. High-Poly Prop_EmaRackAndWell (Wooden Ema Votive Rack + Stone Well with Pulley & Wooden Stave Bucket 釣瓶!)
    bm_ew = bmesh.new()
    # Materials: 0=DarkWood, 1=PropsAtlas, 2=MossyGranite, 3=KawaraTile, 4=FoliageLeafCutout
    rng_ew = random.Random(920)
    for sx in (-0.85, 0.85):
        add_box(bm_ew, (sx, 0, 1.05), (0.11, 0.11, 2.10), mat_idx=0, uv_scale=0.5, bevel=0.010)
        add_box(bm_ew, (sx, 0, 0.12), (0.22, 0.36, 0.24), mat_idx=2, uv_scale=0.5, bevel=0.014)
    add_pitched_kawara_roof(bm_ew, (0, 0, 2.02), 0.68, 2.15, 0.24, mat_tile=3, mat_wood=0, curve_sag=0.02, add_rafters=False)
    for row_z in (1.15, 1.55):
        add_box(bm_ew, (0, 0, row_z), (1.68, 0.045, 0.045), mat_idx=0, uv_scale=0.5, bevel=0.006)
        for ex in (-0.6, -0.3, 0.0, 0.3, 0.6):
            ema_rot = (rng_ew.uniform(-0.08, 0.08), rng_ew.uniform(-0.09, 0.09), rng_ew.uniform(-0.06, 0.06))
            # Pentagonal Ema plaque (rectangular lower body + pitched roof top edges + red hanging cord)
            add_box(bm_ew, (ex, -0.03, row_z - 0.125), (0.20, 0.018, 0.12), mat_idx=1, uv_rect=(0.52, 0.24, 0.74, 0.44), bevel=0.003, rot_euler=ema_rot)
            for er_s in (-1, 1):
                add_box(bm_ew, (ex + er_s * 0.052, -0.03, row_z - 0.055), (0.11, 0.020, 0.024), mat_idx=0, uv_scale=0.5, rot_euler=(ema_rot[0], er_s * 0.42, ema_rot[2]))
            add_cylinder(bm_ew, (ex, -0.03, row_z - 0.02), 0.005, 0.005, 0.07, segments=6, mat_idx=1, uv_rect=(0.78, 0.05, 0.98, 0.45))

    well_x = 2.4
    add_cylinder(bm_ew, (well_x, 0, 0.45), 0.66, 0.66, 0.88, segments=32, mat_idx=2)
    for ring_z in (0.16, 0.45, 0.74):
        for st_i in range(16):
            ang = st_i * (math.pi / 8.0) + (0.18 if ring_z == 0.45 else 0.0)
            sx = well_x + math.cos(ang) * 0.68
            sy = math.sin(ang) * 0.68
            add_box(bm_ew, (sx, sy, ring_z), (0.14, 0.27, 0.27), mat_idx=2, uv_scale=0.5, bevel=0.016, rot_euler=(0, 0, ang))
    for pl_i in (-3, -2, -1, 1, 2, 3):
        py = pl_i * 0.19
        pw = 2.0 * math.sqrt(max(0.05, 0.68**2 - py**2))
        add_box(bm_ew, (well_x, py, 0.91), (pw, 0.175, 0.055), mat_idx=0, uv_scale=0.5, bevel=0.008, rot_euler=(0, 0, rng_ew.uniform(-0.025, 0.025)))
    for sx in (1.78, 3.02):
        add_box(bm_ew, (sx, 0, 1.28), (0.12, 0.12, 2.56), mat_idx=0, uv_scale=0.5, bevel=0.012)
    add_box(bm_ew, (well_x, 0, 2.25), (1.38, 0.10, 0.10), mat_idx=0, uv_scale=0.5, bevel=0.010)
    # Iron Pulley Wheel (滑車) + Rope + Wooden Stave Well-Bucket (釣瓶 / Tsurube) bound with hoops!
    add_torus(bm_ew, (well_x, 0, 2.05), 0.13, 0.028, major_segs=24, minor_segs=10, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
    add_cylinder(bm_ew, (well_x, 0, 2.05), 0.11, 0.11, 0.03, segments=20, mat_idx=0, rot_euler=(0, math.pi * 0.5, 0))
    add_cylinder(bm_ew, (well_x, 0, 1.62), 0.010, 0.010, 0.86, segments=10, mat_idx=1, uv_rect=(0.52, 0.24, 0.74, 0.44))
    # Wooden stave bucket resting partly on the well cover
    add_cylinder(bm_ew, (well_x, 0, 1.08), 0.13, 0.16, 0.28, segments=20, mat_idx=0)
    for bh_z in (1.00, 1.16):
        add_torus(bm_ew, (well_x, 0, bh_z), 0.148, 0.008, major_segs=20, minor_segs=8, mat_idx=3)
    add_box(bm_ew, (well_x, 0, 1.25), (0.31, 0.022, 0.08), mat_idx=0, uv_scale=0.5, bevel=0.004)
    add_pitched_kawara_roof(bm_ew, (well_x, 0, 2.45), 1.72, 1.72, 0.46, mat_tile=3, mat_wood=0, curve_sag=0.04, add_rafters=True)
    add_fern_and_weed_rosette(bm_ew, (well_x - 0.72, -0.35, 0.02), scale=0.82, seed=925, mat_idx=4)
    finalize_and_export(bm_ew, "Prop_EmaRackAndWell", ["DarkWood", "PropsAtlas", "MossyGranite", "KawaraTile", "FoliageLeafCutout"], preview_offset=(5.0, 12.0, 0.0))

    # 8. Soul-Crafted Tree_SugiCedar:
    # ZERO solid polygon cones! 100% real 3D gnarled buttress roots, furrowed bark trunk, 84 3D woody branches,
    # AND 290 overlapping 3D arched Alpha-Cutout Sugi cedar needle branch sprays (Mat_FoliageLeafCutout)!
    bm_tr = bmesh.new()
    rng_tr = random.Random(950)
    # Materials: 0=FoliageBark, 1=FoliageLeafCutout
    add_cylinder(bm_tr, (0, 0, 4.3), 0.39, 0.08, 8.6, segments=28, mat_idx=0, uv_rect=(0.05, 0.05, 0.45, 0.95))
    for r_i in range(6):
        ang = r_i * (2.0 * math.pi / 6.0) + rng_tr.uniform(-0.12, 0.12)
        rx, ry = math.cos(ang) * 0.25, math.sin(ang) * 0.25
        add_cylinder(
            bm_tr,
            (rx, ry, 0.34),
            0.20,
            0.04,
            0.92,
            segments=14,
            mat_idx=0,
            rot_euler=(0, -0.34, ang),
            uv_rect=(0.05, 0.05, 0.45, 0.95),
        )
    # Woodland ferns & grass growing between the gnarled cedar roots!
    for f_i in range(4):
        fang = f_i * (math.pi * 0.5) + 0.35
        add_fern_and_weed_rosette(bm_tr, (math.cos(fang) * 0.42, math.sin(fang) * 0.42, 0.02), scale=0.95, seed=960 + f_i, mat_idx=1)

    # 14 tiers of real 3D wooden limbs + inner & outer rings of 3D Alpha-Cutout Sugi Cedar Needle Sprays!
    for tier in range(14):
        tz_base = 2.25 + tier * 0.44
        base_rad = 2.35 * (1.0 - (tier / 16.5))
        phase = tier * 0.83
        trunk_r_here = 0.39 - (tz_base / 8.6) * 0.31

        # 6 real 3D woody branches radiating from the trunk per tier
        for b_i in range(6):
            ang_b = (b_i / 6.0) * 2.0 * math.pi + phase + rng_tr.uniform(-0.14, 0.14)
            limb_len = base_rad * rng_tr.uniform(0.48, 0.62)
            r_center = trunk_r_here * 0.45 + limb_len * 0.46
            lx = math.cos(ang_b) * r_center
            ly = math.sin(ang_b) * r_center
            add_cylinder(
                bm_tr,
                (lx, ly, tz_base + 0.12),
                max(0.015, 0.052 * (1.0 - tier * 0.055)),
                0.010,
                limb_len,
                segments=8,
                mat_idx=0,
                rot_euler=(0, 1.36, ang_b),
                uv_rect=(0.05, 0.05, 0.45, 0.95),
            )

        # Inner canopy ring (8 dense arched needle sprays starting close to trunk for deep interior fullness)
        for s_in in range(8):
            ang = (s_in / 8.0) * 2.0 * math.pi + phase + 0.25 + rng_tr.uniform(-0.12, 0.12)
            sx = math.cos(ang) * (trunk_r_here * 0.85)
            sy = math.sin(ang) * (trunk_r_here * 0.85)
            spray_len = base_rad * rng_tr.uniform(0.75, 0.95)
            spray_w = spray_len * 0.84
            add_curved_leaf_card(
                bm_tr,
                (sx, sy, tz_base + rng_tr.uniform(0.05, 0.22)),
                length=spray_len,
                width=spray_w,
                yaw=ang - math.pi * 0.5,
                pitch=rng_tr.uniform(0.18, 0.48),
                arch_droop=spray_len * 0.36,
                v_fold=0.10,
                roll=rng_tr.uniform(-0.35, 0.35),
                mat_idx=1,
                uv_rect=UV_CEDAR_SPRAY,
                segs_l=4,
                segs_w=2,
            )

        # Outer canopy ring (12 lush arching Sugi needle branch sprays extending out along the limbs)
        for s_out in range(12):
            ang = (s_out / 12.0) * 2.0 * math.pi + phase + rng_tr.uniform(-0.10, 0.10)
            spray_r = base_rad * rng_tr.uniform(0.22, 0.36)
            sx = math.cos(ang) * spray_r
            sy = math.sin(ang) * spray_r
            spray_len = base_rad * rng_tr.uniform(0.84, 1.12)
            spray_w = spray_len * 0.82
            add_curved_leaf_card(
                bm_tr,
                (sx, sy, tz_base + rng_tr.uniform(0.08, 0.28)),
                length=spray_len,
                width=spray_w,
                yaw=ang - math.pi * 0.5,
                pitch=rng_tr.uniform(0.04, 0.32),
                arch_droop=spray_len * 0.35,
                v_fold=0.09,
                roll=rng_tr.uniform(-0.32, 0.32),
                mat_idx=1,
                uv_rect=UV_CEDAR_SPRAY,
                segs_l=4,
                segs_w=2,
            )

    # Top crown tuft of 10 Sugi needle sprays at the apex of the cedar tree
    for c_i in range(10):
        ang = (c_i / 10.0) * 2.0 * math.pi + rng_tr.uniform(-0.15, 0.15)
        add_curved_leaf_card(
            bm_tr,
            (math.cos(ang) * 0.06, math.sin(ang) * 0.06, 8.35 + (c_i % 3) * 0.12),
            length=0.95,
            width=0.78,
            yaw=ang - math.pi * 0.5,
            pitch=rng_tr.uniform(0.42, 0.85),
            arch_droop=0.28,
            v_fold=0.08,
            roll=rng_tr.uniform(-0.25, 0.25),
            mat_idx=1,
            uv_rect=UV_CEDAR_SPRAY,
            segs_l=4,
            segs_w=2,
        )

    finalize_and_export(bm_tr, "Tree_SugiCedar", ["FoliageBark", "FoliageLeafCutout"], preview_offset=(-8.0, 12.0, 0.0))

    # 9. NEW Model: Prop_WetFoliageCluster (Lush roadside & shrine-step 3D botanical cluster with 50+ individual leaves/fronds!)
    bm_fc = bmesh.new()
    # Materials: 0=FoliageLeafCutout, 1=MossyGranite
    # Small mossy boundary stones + 3 overlapping multi-species botanical rosettes
    add_sphere(bm_fc, (-0.28, 0.05, 0.05), 0.14, scale=(1.3, 0.9, 0.55), u_segs=16, v_segs=12, mat_idx=1)
    add_sphere(bm_fc, (0.32, -0.06, 0.04), 0.11, scale=(1.2, 1.0, 0.50), u_segs=14, v_segs=10, mat_idx=1)
    add_fern_and_weed_rosette(bm_fc, (0.0, 0.0, 0.01), scale=1.15, seed=981, mat_idx=0)
    add_fern_and_weed_rosette(bm_fc, (-0.38, 0.08, 0.01), scale=0.85, seed=982, mat_idx=0)
    add_fern_and_weed_rosette(bm_fc, (0.38, -0.05, 0.01), scale=0.80, seed=983, mat_idx=0)
    finalize_and_export(bm_fc, "Prop_WetFoliageCluster", ["FoliageLeafCutout", "MossyGranite"], preview_offset=(5.0, 14.0, 0.0))


def main():
    clear_scene()
    init_materials()

    build_alley_road_and_gutters()
    build_machiya_house("MachiyaHouse_A", width=6.2, depth=5.8, h1=2.9, h2=2.6, eerie_upper=False, preview_offset=(-5.6, -4.0, 0.0))
    build_machiya_house("MachiyaHouse_B", width=5.6, depth=5.4, h1=2.8, h2=2.5, eerie_upper=True, preview_offset=(5.6, 3.0, 0.0))
    build_corner_store()
    build_rural_bus_stop()
    build_retro_vending_machine()
    build_walls_and_fences()
    build_utility_pole_and_cables()
    build_shrine_steps_and_torii()
    build_stone_lantern_and_shrine()
    build_street_and_shrine_props()

    cam_data = bpy.data.cameras.new("ShowcaseCam")
    cam_obj = bpy.data.objects.new("ShowcaseCam", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (0.0, -19.0, 2.2)
    cam_obj.rotation_euler = (math.radians(84.0), 0.0, 0.0)
    bpy.context.scene.camera = cam_obj

    blend_path = MODELS_DIR.parent.parent / "YugiriVillage_MasterAssets.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f"SUCCESS: Exported all 20 soul-crafted FBX models to {MODELS_DIR} and saved {blend_path}")


main()
