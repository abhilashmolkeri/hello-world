model = ExtAPI.DataModel.Project.Model
geo = model.Geometry

# Ensure Named Selections folder exists
ns_group = model.NamedSelections
if not ns_group:
    ns_group = model.AddNamedSelections()

# --- 1. RECURSIVE GENERATOR FUNCTION ---
def generate_subgroup_ns(folder_node):
    if folder_node.Suppressed:
        return
    if folder_node.DataModelObjectCategory == DataModelObjectCategory.Body:
        return

    bodies = folder_node.GetChildren(DataModelObjectCategory.Body, True)
    if bodies.Count > 0:
        geo_bodies = [b.GetGeoBody() for b in bodies if b.GetGeoBody() is not None and not b.Suppressed]
        if geo_bodies:
            sel_info = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
            sel_info.Entities = geo_bodies
            ns = ns_group.AddNamedSelection()
            ns.Name = folder_node.Name
            ns.Location = sel_info

    for child in folder_node.Children:
        if child.DataModelObjectCategory != DataModelObjectCategory.Body:
            generate_subgroup_ns(child)

# --- 2. MAIN EXECUTION ---
target_parent_names = ["Stack1","Stack2"]
processed_parents = set()
all_active_geo_bodies = []

for top_part in geo.Children:
    if top_part.Suppressed:
        continue

    if top_part.Name in target_parent_names and top_part.Name not in processed_parents:

        for body in top_part.GetChildren(DataModelObjectCategory.Body, True):
            if not body.Suppressed and body.GetGeoBody() is not None:
                all_active_geo_bodies.append(body.GetGeoBody())

        for subgroup in top_part.Children:
            generate_subgroup_ns(subgroup)

# --- 3. CORRECTED APDL MACRO GROUPING ---
print("Generating APDL Macro Component Selections...")
macro_groups = {
    "NS_ELEM_BASE": [],
    "NS_ELEM_ASSY": [],
    "NS_ELEM_MOLD": [],
    "NS_ELEM_GRIND": [],
    "NS_PIC_GRIND": [],
    "NS_PIC_WAFER": [],
    "NS_ELEM_CW_ADH": [],
    "NS_ELEM_CW_GLASS": []
}

for ns in ns_group.Children:
    name = ns.Name
    # Skip topo nodes and completed macros so they don't get accidentally processed
    if name in macro_groups.keys() or name in ["Xsymm", "Ysymm", "NS_NODE_PLANE", "NS_NODE_ANCHOR", "NS_NODE_CHUCK_TOP"]:
        continue

    try:
        bodies = list(ns.Location.Entities)
    except:
        continue

    # Create safe flags to prevent "Mold_PIC_Keep" from being grabbed by the "PIC" rule
    is_mold = "Mold" in name
    is_glass_cw = "Glass_CW" in name
    is_base_silicon = ("PIC" in name or "Streets" in name) and not is_mold and not is_glass_cw

    # 1. NS_PIC_WAFER (Master tracker: gets ALL true PIC/Streets geometry, including their grind layers)
    if is_base_silicon:
        macro_groups["NS_PIC_WAFER"].extend(bodies)

    # 2. Backgrinding Silicon Layer (Step 15)
    if "Mold" not in name:
        if "PIC_Grind" in name or "Streets_Grind" in name:
            print(name)
            macro_groups["NS_PIC_GRIND"].extend(bodies)

    # 3. General Grind Layers (EIC, Dummy, Underfill, Mold - caught because PIC_Grind was filtered above)
    elif "Grind" in name and "PIC_Grind" != name and "Streets_Grind" != name:
        macro_groups["NS_ELEM_GRIND"].extend(bodies)

    # 4. Mold Layers (Catches Mold Keeps since Mold_Grind is safely caught above)
    elif is_mold:
        macro_groups["NS_ELEM_MOLD"].extend(bodies)

    # 5. Carrier Adhesive
    elif "Glass_CW_Adh" in name:
        macro_groups["NS_ELEM_CW_ADH"].extend(bodies)

    # 6. Carrier Glass
    elif is_glass_cw and "Glass_CW_Adh" not in name:
        macro_groups["NS_ELEM_CW_GLASS"].extend(bodies)

    # 7. Assembly Layers
    elif any(k in name for k in ["EIC", "Dummy", "DAF", "Bumps", "Underfill"]):
        macro_groups["NS_ELEM_ASSY"].extend(bodies)

    # 8. Base Layers (True silicon that survives backgrinding, plus optics/plate)
    elif is_base_silicon or any(k in name for k in ["SiLens", "GlassPlate", "Glue"]):
        # Note: PIC_Grind/Streets_Grind bodies were caught up at rule #2 and skip this block!
        macro_groups["NS_ELEM_BASE"].extend(bodies)


# Rebuild the final Macro Named Selections
for macro_name, body_list in macro_groups.items():
    for existing_ns in ns_group.Children:
        if existing_ns.Name == macro_name:
            existing_ns.Delete()

    # set() naturally handles the duplicates caused by recursively grouping folders
    unique_bodies = list(set(body_list))
    if unique_bodies:
        sel_info = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
        sel_info.Entities = unique_bodies
        ns = ns_group.AddNamedSelection()
        ns.Name = macro_name
        ns.Location = sel_info
        print("  -> Created APDL Macro NS: '{}' (Count: {})".format(macro_name, len(unique_bodies)))

# --- 4. TOPOLOGICAL BOUNDARY CONDITION EXTRACTION ---
print("Extracting Topological Boundary Conditions...")

xsymm_faces = []
ysymm_faces = []
bottom_faces = []
bottom_faces_TSV = []
anchor_verts = []
chuck_top_faces = []

tol = 1e-6
x_plane_target = 105.0E-6
y_plane_target = 0.0

z_plane_target = 0.0
z_anchor_target = 705.0E-6

for b in all_active_geo_bodies:
    for face in b.Faces:
        verts = face.Vertices
        if verts.Count > 0:
            if all(abs(v.X - x_plane_target) < tol for v in verts):
                xsymm_faces.append(face)
            if all(abs(v.Y - y_plane_target) < tol for v in verts):
                ysymm_faces.append(face)
            # Find the bottom Z=0 plane
            if all(abs(v.Z - z_plane_target) < tol for v in verts):
                bottom_faces.append(face)
            if all(abs(v.Z - z_anchor_target) < tol for v in verts):
                bottom_faces_TSV.append(face)

    for v in b.Vertices:
        if abs(v.X - x_plane_target) < tol and abs(v.Y - y_plane_target) < tol and abs(v.Z - z_anchor_target) < tol:
            anchor_verts.append(v)

# Dynamically find the absolute top face of the Carrier Glass for the Chuck
if macro_groups["NS_ELEM_CW_GLASS"]:
    max_z = -9999.0
    # First pass: find the max Z coordinate
    for b in macro_groups["NS_ELEM_CW_GLASS"]:
        for face in b.Faces:
            for v in face.Vertices:
                if v.Z > max_z:
                    max_z = v.Z

    # Second pass: grab all faces sitting exactly at that max Z height
    for b in macro_groups["NS_ELEM_CW_GLASS"]:
        for face in b.Faces:
            if all(abs(v.Z - max_z) < tol for v in face.Vertices):
                chuck_top_faces.append(face)

def create_topo_ns(name, entities):
    if not entities:
        return
    unique_entities = {e.Id: e for e in entities}.values()

    for existing_ns in ns_group.Children:
        if existing_ns.Name == name:
            existing_ns.Delete()

    sel_info = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    sel_info.Entities = list(unique_entities)
    ns = ns_group.AddNamedSelection()
    ns.Name = name
    ns.Location = sel_info
    print("  -> Created Topo NS: '{}' (Count: {})".format(name, len(unique_entities)))

#create_topo_ns("Xsymm", xsymm_faces)
#create_topo_ns("Ysymm", ysymm_faces)
create_topo_ns("NS_NODE_PLANE", bottom_faces)
create_topo_ns("NS_NODE_PLANE_TSV", bottom_faces_TSV)
create_topo_ns("NS_NODE_ANCHOR", anchor_verts)
create_topo_ns("NS_NODE_CHUCK_TOP", chuck_top_faces)

ExtAPI.SelectionManager.ClearSelection()
print("Success! Groups fixed.")
