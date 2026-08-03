# ================================================================================
# UNIFIED NESTED VISUAL TREE GROUPING (MODEL-1 & MODEL-2 AGNOSTIC)
# ================================================================================
model = ExtAPI.DataModel.Project.Model
geo = model.Geometry

# --- 1. USER INPUTS (List top-level assembly names for both models here) ---
# The script will automatically find whichever one is currently imported/active.
target_parent_names = ["Stack1","Stack2"]
processed_grouping_parents = set()

print("--- STARTING UNIFIED NESTED VISUAL TREE GROUPING ---")

for top_part in geo.Children:
    # Skip suppressed/silent parts entirely
    if top_part.Suppressed:
        continue

    if top_part.Name in target_parent_names and top_part.Name not in processed_grouping_parents:
        print("Organizing bodies in active part: {}...".format(top_part.Name))

        # Grab bodies directly under the top part that aren't inside folders yet
        loose_bodies = top_part.GetChildren(DataModelObjectCategory.Body, False)

        if not loose_bodies:
            print("  -> No loose bodies found to group. Skipping.")
            continue

        # ----------------------------------------------------
        # TIER 1: Group bodies into their Sub-Folders
        # ----------------------------------------------------
        sub_groups_dict = {}
        for body in loose_bodies:
            name_parts = body.Name.split('\\')
            if len(name_parts) >= 3:
                sub_name = name_parts[1]
                if sub_name not in sub_groups_dict:
                    sub_groups_dict[sub_name] = []
                sub_groups_dict[sub_name].append(body)

        created_sub_folders = []
        for sub_name, body_list in sub_groups_dict.items():
            try:
                new_sub_group = ExtAPI.DataModel.Tree.Group(body_list)
                new_sub_group.Name = sub_name
                created_sub_folders.append(new_sub_group)
            except Exception:
                pass # Safely skip if locked

        # ----------------------------------------------------
        # TIER 2: Group Sub-Folders into Master Folders
        # ----------------------------------------------------
        master_groups_dict = {}
        for sub_folder in created_sub_folders:
            sub_name = sub_folder.Name

            # Master Routing Logic (Safely skips any rules that don't apply)
            if "DAF" in sub_name:
                master_name = "DAF_ALL"
            elif "Dummy" in sub_name:  # Catches Dummy and Partial_Dummy
                master_name = "Dummy_ALL"
            elif "Mold" in sub_name:
                master_name = "Mold_ALL"
            elif "Underfill" in sub_name:
                master_name = "Underfill_ALL"
            elif "EIC" in sub_name:
                master_name = "EIC_ALL"
            elif "Glass_CW" in sub_name: # Intercepts Carrier Wafer safely
                master_name = "Glass_CW_ALL"
            elif "Streets" in sub_name:
                master_name = "Streets_ALL"
            elif "PIC" in sub_name:
                master_name = "PIC_ALL"
            else:
                master_name = sub_name + "_ALL" # Safe fallback

            if master_name not in master_groups_dict:
                master_groups_dict[master_name] = []
            master_groups_dict[master_name].append(sub_folder)

        # Execute the Master grouping
        for master_name, folder_list in master_groups_dict.items():
            try:
                # We pass the list of Folder objects directly to the Group command to nest them
                new_master_group = ExtAPI.DataModel.Tree.Group(folder_list)
                new_master_group.Name = master_name
                print("  -> Created Master Folder: '{}' (Contains {} sub-folders)".format(master_name, len(folder_list)))
            except Exception as e:
                pass

print("Unified nested visual grouping complete!")
