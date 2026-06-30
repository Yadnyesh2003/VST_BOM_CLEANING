import pandas as pd
import numpy as np
import time
from config import FILES, BOM_SCHEMA, TC_SCHEMA, IGNORE_SCHEMA, BOM_PARENT_CHILD_SCHEMA
from loader import read_bom, read_csv
from validator import validate_schema
from logger import setup_logger
from exporter import export_df
import logging


# Initialize logger
logger = setup_logger()
log = logging.getLogger(__name__)


# LOAD
log.info("Starting BOM cleaning run")
bom_df = read_bom(FILES["BOM"])
tc_df = read_csv(FILES["TC"])
ig_df = read_csv(FILES["IGNORE"])
vst_df = read_csv(FILES["BOM_PARENT_CHILD"])

log.info("Files loaded: BOM=%s, TC=%s, IGNORE=%s, PARENT_CHILD=%s", FILES["BOM"], FILES["TC"], FILES["IGNORE"], FILES["BOM_PARENT_CHILD"])


# df=pd.read_excel("BOM_20260616 - Copy.xlsx" ,sheet_name="BOMvstin")
# Tc=pd.read_excel("TC Master.xlsx")
# IG=pd.read_excel("IgnoreMaster.xlsx")
# vst_df=pd.read_excel("vstparent&child.xlsx", sheet_name="output1")

# VALIDATE SCHEMA
log.info("Validating schemas for input files")
validate_schema(bom_df, BOM_SCHEMA, "BOM")
validate_schema(tc_df, TC_SCHEMA, "TC")
validate_schema(ig_df, IGNORE_SCHEMA, "IGNORE")
validate_schema(vst_df, BOM_PARENT_CHILD_SCHEMA, "BOM_PARENT_CHILD")

log.info("Schema validation complete")

# Cleaning TC Master
tc_df = tc_df[['ET code', 'Remark']].drop_duplicates().reset_index(drop=True)
# Rename Remark column to avoid confusion during merge with Ignore Master
tc_df = tc_df.rename(columns={'Remark': 'TC_Master_Remark'})

# Cleaning Ignore Master
ig_df = ig_df[['Unpainted parts', 'Remark']].drop_duplicates().reset_index(drop=True)
# Rename Remark column to avoid confusion during merge with TC Master
ig_df = ig_df.rename(columns={'Remark': 'Ignore_Master_Remark'})

# Add original row number for traceability in error export
bom_df["Original_Row_Number"] = range(1, len(bom_df) + 1)

# Filter 1 - Remove child rows under the parent component with remark "Engine", "Transmission", "FRONT AXLE ASSY"
log.info("Starting Filter 1: Remove child rows under Engine / Transmission / Front Axle")

bom_df = bom_df.merge(tc_df[['ET code', 'TC_Master_Remark']], left_on='Component', right_on='ET code', how='left')

bom_df['TC_Master_Remark'] = bom_df['TC_Master_Remark'].fillna('No Remark').str.strip()

target_remarks = {"Engine", "Transmission", "FRONT AXLE ASSY"}

bom_df['is_parent'] = bom_df['TC_Master_Remark'].isin(target_remarks)

bom_df["Rejection Reason"] = ""
bom_df["keep"] = True


# def filter_1_bom(group):
#     material, plant = group.name
#     log.info("Processing Material=%s | Plant=%s | Rows=%d",
#              material, plant,
#              len(group))

#     active_parent_level = None
#     delete_mode = False
#     active_parent_component = None

#     for idx in group.index:

#         row = bom_df.loc[idx]
#         lvl = row["Level"]
#         is_parent = row["is_parent"]
#         comp = row["Component"]

#         log.debug(
#             "Row idx=%s | Component=%s | Level=%s | is_parent=%s | delete_mode=%s",
#             idx, comp, lvl, is_parent, delete_mode
#         )

#         # CASE 1: Parent found
#         if is_parent:
#             log.info("PARENT FOUND -> %s at level %s", comp, lvl)

#             active_parent_level = lvl
#             active_parent_component = comp
#             delete_mode = True
#             continue  # keep parent

#         # CASE 2: Inside deletion window
#         if delete_mode:
#             if lvl > active_parent_level:

#                 bom_df.at[idx, "keep"] = False
#                 bom_df.at[idx, "Rejection Reason"] = (
#                     f"Child of {active_parent_component} (Level {active_parent_level})"
#                 )

#                 log.info(
#                     "DELETING -> %s | Reason: child of %s",
#                     comp, active_parent_component
#                 )

#             else:
#                 log.info(
#                     "EXIT DELETE MODE at %s (Level %s <= %s)",
#                     comp, lvl, active_parent_level
#                 )

#                 delete_mode = False
#                 active_parent_level = None
#                 active_parent_component = None

def filter_1_bom(group, material, plant):

    log.info(
        "Filter 1 | Material=%s | Plant=%s | Rows=%d",
        material,
        plant,
        len(group)
    )

    idxs = group.index.tolist()

    pos = 0

    while pos < len(idxs):

        idx = idxs[pos]

        row = bom_df.loc[idx]

        comp = row["Component"]
        lvl = row["Level"]

        if not row["is_parent"]:
            pos += 1
            continue

        #################################################
        # TC MATCH FOUND
        #################################################

        log.info(
            "TC MATCH | Material=%s | Plant=%s | Row=%s | Component=%s | Level=%s",
            material,
            plant,
            idx,
            comp,
            lvl
        )

        parent_level = lvl
        parent_comp = comp

        deleted_count = 0

        #################################################
        # DELETE CHILDREN ONLY
        #################################################

        child_pos = pos + 1

        while child_pos < len(idxs):

            child_idx = idxs[child_pos]

            child_comp = bom_df.at[child_idx, "Component"]
            child_level = bom_df.at[child_idx, "Level"]

            if child_level > parent_level:

                bom_df.at[child_idx, "keep"] = False

                bom_df.at[child_idx, "Rejection Reason"] = (
                    f"Child of {parent_comp}"
                )

                deleted_count += 1

                log.debug(
                    "DELETE CHILD | Parent=%s(Level=%s) -> Child=%s(Level=%s)",
                    parent_comp,
                    parent_level,
                    child_comp,
                    child_level
                )

                child_pos += 1

            else:

                log.info(
                    "END SUBTREE | Parent=%s(Level=%s) | Stop at Component=%s(Level=%s)",
                    parent_comp,
                    parent_level,
                    child_comp,
                    child_level
                )

                break

        if child_pos >= len(idxs):

            log.info(
                "END SUBTREE | Parent=%s(Level=%s) | Reached end of BOM",
                parent_comp,
                parent_level
            )

        log.info(
            "CHILDREN REMOVED | Parent=%s | Deleted=%d",
            parent_comp,
            deleted_count
        )

        # Jump to next sibling
        pos = child_pos

# bom_df.groupby(["Material", "Plant"], group_keys=False, sort=False).apply(filter_1_bom)

for (material, plant), group in bom_df.groupby(
        ["Material", "Plant"],
        sort=False):

    filter_1_bom(group, material, plant)

df_rejected = bom_df[bom_df["keep"] == False].copy()
df_clean = bom_df[bom_df["keep"] == True].copy()

log.info("Total rejected rows: %d", len(df_rejected))
log.info("Final clean dataset shape: %s", df_clean.shape)

export_df(df_clean, "output/clean_bom_filter_1.csv")
export_df(df_rejected, "output/rejected_bom_filter_1.csv")

log.info("Exported clean_bom_filter_1.csv and rejected_bom_filter_1.csv")




#######################################################################################################################################


# Filter condition 2 - If parent in Ignore Master, then remove parent & child rows under that parent
log.info("Starting Filter 2: If parent in Ignore Master, then remove parent & child rows under that parent")

df_clean = df_clean.merge(ig_df[['Unpainted parts', 'Ignore_Master_Remark']], left_on='Component', right_on='Unpainted parts', how='left')
df_clean['Ignore_Master_Remark'] = df_clean['Ignore_Master_Remark'].fillna('No Remark').str.strip()

df_clean["is_ignore_parent"] = (
    (df_clean["Ignore_Master_Remark"] == "Ignore")
)

# def filter_2_bom(group):
#     material, plant = group.name
#     log.info("Processing Material=%s | Plant=%s | Rows=%d",
#              material, plant,
#              len(group))

#     active_parent_level = None
#     delete_mode = False
#     active_parent_component = None

#     for idx in group.index:

#         row = df_clean.loc[idx]
#         lvl = row["Level"]
#         is_parent = row["is_ignore_parent"]
#         comp = row["Component"]

#         # CASE 1: Parent found (IGNORE trigger)
#         if is_parent:

#             active_parent_level = lvl
#             active_parent_component = comp
#             delete_mode = True

#             # IMPORTANT: also delete parent itself
#             df_clean.at[idx, "keep"] = False
#             df_clean.at[idx, "Rejection Reason"] = "Ignore rule triggered"

#             continue

#         # CASE 2: delete children
#         if delete_mode:

#             if lvl > active_parent_level:

#                 df_clean.at[idx, "keep"] = False
#                 df_clean.at[idx, "Rejection Reason"] = (
#                     f"Child of Ignore parent {active_parent_component}"
#                 )

#             else:
#                 delete_mode = False
#                 active_parent_level = None
#                 active_parent_component = None

def filter_2_bom(group, material, plant):

    # material, plant = group.name

    # log.info(
    #     "Filter 2 | Material=%s | Plant=%s | Rows=%d",
    #     material,
    #     plant,
    #     len(group)
    # )

    idxs = group.index.tolist()

    pos = 0

    while pos < len(idxs):

        idx = idxs[pos]

        # Skip rows already deleted by previous subtree
        if not df_clean.at[idx, "keep"]:
            pos += 1
            continue

        row = df_clean.loc[idx]

        comp = row["Component"]
        lvl = row["Level"]

        # Not an ignore component
        if not row["is_ignore_parent"]:
            pos += 1
            continue

        #################################################
        # IGNORE MATCH FOUND
        #################################################

        log.info(
            "IGNORE MATCH | Material=%s | Plant=%s | Row=%s | Component=%s | Level=%s",
            material,
            plant,
            idx,
            comp,
            lvl
        )

        parent_level = lvl
        parent_comp = comp

        # Delete parent itself
        df_clean.at[idx, "keep"] = False
        df_clean.at[idx, "Rejection Reason"] = "Ignore rule triggered"

        deleted_count = 1

        #################################################
        # DELETE SUBTREE
        #################################################

        child_pos = pos + 1

        while child_pos < len(idxs):

            child_idx = idxs[child_pos]

            child_comp = df_clean.at[child_idx, "Component"]
            child_level = df_clean.at[child_idx, "Level"]

            # Still inside subtree
            if child_level > parent_level:

                df_clean.at[child_idx, "keep"] = False
                df_clean.at[child_idx, "Rejection Reason"] = (
                    f"Child of Ignore parent {parent_comp}"
                )

                deleted_count += 1

                log.debug(
                    "DELETE CHILD | Parent=%s(Level=%s) -> Child=%s(Level=%s) | Row=%s",
                    parent_comp,
                    parent_level,
                    child_comp,
                    child_level,
                    child_idx
                )

                child_pos += 1

            else:

                log.info(
                    "END SUBTREE | Parent=%s(Level=%s) | Stop at Row=%s Component=%s Level=%s",
                    parent_comp,
                    parent_level,
                    child_idx,
                    child_comp,
                    child_level
                )

                break

        log.info(
            "SUBTREE REMOVED | Parent=%s | Total Rows Deleted=%d",
            parent_comp,
            deleted_count
        )

        # Jump directly to next sibling/root row
        pos = child_pos

    # return group

# df_clean.groupby(["Material", "Plant"], group_keys=False, sort=False).apply(filter_2_bom)
for (material, plant), group in df_clean.groupby(
        ["Material", "Plant"],
        sort=False):

    filter_2_bom(group, material, plant)

df_rejected = df_clean[df_clean["keep"] == False].copy()
df_clean = df_clean[df_clean["keep"] == True].copy()

log.info("Total rejected rows: %d", len(df_rejected))
log.info("Final clean dataset shape: %s", df_clean.shape)

export_df(df_clean, "output/clean_bom_filter_2.csv")
export_df(df_rejected, "output/rejected_bom_filter_2.csv")

log.info("Exported clean_bom_filter_2.csv and rejected_bom_filter_2.csv")


#####################################################################################################################

# Filter 3 - Delete rows if Third Last Digit of Component is (1 or 9) AND Level != 1 AND Parent's Material Type != ZSFG

def filter_3_bom(group):

    for i in group.index:

        row = group.loc[i]
        comp = str(row["Component"])

        lvl = row["Level"]

        # Condition 1: Level != 1
        if lvl == 1:
            continue

        # Condition 2: check 3rd last digit
        if len(comp) < 3:
            continue

        third_last_digit = comp[-3]

        # if comp == "BHG23A00021A0":
        #     log.info("DEBUG: Component %s | 3rd last digit: %s", comp, third_last_digit)
        #     # time.sleep(5)

        if third_last_digit not in ["1", "9"]:
            continue

        # FIND PARENT
        parent = None

        for j in reversed(group.loc[:i-1].index):
            if group.loc[j, "Level"] < lvl:
                parent = group.loc[j]
                break

        # safety check
        if parent is None:
            continue

        # Condition 3: parent material type check
        if parent["Material type"] != "ZSFG":
            df_clean.at[i, "keep"] = False
            df_clean.at[i, "Rejection Reason"] = (
                "3rd last digit rule + parent Material Type != ZSFG"
            )


for (material, plant), group in df_clean.groupby(["Material", "Plant"], sort=False):
    filter_3_bom(group)

df_rejected = df_clean[df_clean["keep"] == False].copy()
df_clean = df_clean[df_clean["keep"] == True].copy()

log.info("Total rejected rows: %d", len(df_rejected))
log.info("Final clean dataset shape: %s", df_clean.shape)

export_df(df_clean, "output/clean_bom_filter_3.csv")
export_df(df_rejected, "output/rejected_bom_filter_3.csv")

log.info("Exported clean_bom_filter_3.csv and rejected_bom_filter_3.csv")

missing_cols = [c for c in BOM_SCHEMA if c not in df_clean.columns]

if missing_cols:
    raise ValueError(
        f"Missing mandatory BOM columns before export: {missing_cols}"
    )

################################################################################################################################################################################################

# Special Condition - Delete SubTrees of the BOM and keep leaf nodes only. As discovered on Friday 19th June.

# def filter_4_bom(group):

#     group = group.sort_values("Original_Row_Number").copy()

#     i = 0
#     n = len(group)

#     while i < n:

#         # start new consecutive block
#         block = [i]

#         # build consecutive row-number block
#         while i + 1 < n and \
#               group.iloc[i + 1]["Original_Row_Number"] == group.iloc[i]["Original_Row_Number"] + 1:
#             i += 1
#             block.append(i)

#         block_df = group.iloc[block]

#         # skip if already invalid rows only
#         if len(block_df) == 0:
#             i += 1
#             continue

#         max_level = block_df["Level"].max()

#         # leaf nodes = rows with max level in this block
#         leaf_rows = block_df[block_df["Level"] == max_level].index

#         # everything except leaf nodes becomes parent candidates
#         for idx in block_df.index:

#             if idx not in leaf_rows and group.at[idx, "keep"]:

#                 group.at[idx, "keep"] = False
#                 group.at[idx, "Rejection Reason"] = (
#                     "Parent of leaf nodes in consecutive BOM chain"
#                 )

#         i += 1
    
#     return group

def filter_4_bom(group):

    group = group.sort_values("Original_Row_Number").copy()

    n = len(group)

    # if (group['Component'] == "ACA02A00000A0").any():
    #     log.info("Component ACA02A00000A0 found in group")
        # log.info("DEBUG: Group data:\n%s", group)
        # time.sleep(10)

    # track parent nodes
    has_child = set()

    for i in range(n - 1):

        current_level = group.iloc[i]["Level"]
        next_level = group.iloc[i + 1]["Level"]

        # if next node is deeper → current is parent
        if next_level > current_level:
            has_child.add(group.index[i])

    # now delete all parents (keep only leaf nodes)
    for idx in group.index:

        if idx in has_child and group.at[idx, "keep"]:

            group.at[idx, "keep"] = False
            group.at[idx, "Rejection Reason"] = (
                "Parent node in BOM subtree (leaf-only rule)"
            )

    return group

# for (material, plant), group in df_clean.groupby(["Material", "Plant"], sort=False):
#     # filter_4_bom(group)
#     updated_group = filter_4_bom(group)
#     df_clean.loc[updated_group.index, :] = updated_group

# df_clean.groupby(
#     ["Material", "Plant"],
#     group_keys=False,
#     sort=False
# ).apply(filter_4_bom)

# df_rejected = df_clean[df_clean["keep"] == False].copy()
# df_clean = df_clean[df_clean["keep"] == True].copy()

# log.info("Total rejected rows: %d", len(df_rejected))
# log.info("Final clean dataset shape: %s", df_clean.shape)

# export_df(df_clean, "output/clean_bom_filter_4.csv")
# export_df(df_rejected, "output/rejected_bom_filter_4.csv")



##########################################################################################################################################

# Filter 5 - Delete rows where component = ZSFG but its TC_Master_Remark is not in target_remarks (Engine, Transmission, FRONT AXLE ASSY)

for (material, plant), group in df_clean.groupby(["Material", "Plant"], sort=False):

    for idx in group.index:

        row = group.loc[idx]
        material_type = row["Material type"]
        is_parent = row["is_parent"]
        tc_master_remark = row["TC_Master_Remark"]
        component = row["Component"]

        if material_type == "ZSFG" and is_parent == False:
            df_clean.at[idx, "keep"] = False
            df_clean.at[idx, "Rejection Reason"] = (
                f"Material type of {component} is ZSFG with TC Master Remark not in {target_remarks}"
            )

df_rejected = df_clean[df_clean["keep"] == False].copy()
df_clean = df_clean[df_clean["keep"] == True].copy()

log.info("Total rejected rows: %d", len(df_rejected))
log.info("Final clean dataset shape: %s", df_clean.shape)

export_df(df_clean, "output/clean_bom_filter_5.csv")
export_df(df_rejected, "output/rejected_bom_filter_5.csv")



# Drop Duplicates by summing up component quantity and keeping the first occurrence of other columns
final_dfs = []

agg_dict = {col: "first" for col in df_clean.columns}
agg_dict["Comp. Qty"] = "sum"

df_final_output = (
    df_clean
    .groupby(["Plant", "Material", "Component"], as_index=False, sort=False)
    .agg(agg_dict)
)

log.info("Final aggregation complete. Final output shape: %s", df_final_output.shape)

export_df(df_final_output, "output/VST_Flat_BOM_Automation_Output.csv")






# exceptions = {'Engine', 'Transmission', 'FRONT AXLE ASSY'}

# rows_to_delete_4 = set()
# tc_remark_lookup = dict(zip(
#     Tc['ET code'].astype(str).str.strip(),
#     Tc['Remark'].astype(str).str.strip()
# ))
# #this peace of code not require remark in input
# for idx in range(len(df_filter3)):

#     material_type = str(df_filter3.loc[idx, 'Material type']).strip()

#     if material_type != 'ZSFG':
#         continue

#     material = str(df_filter3.loc[idx, 'Component']).strip()

#     if material in tc_remark_lookup:
#         continue
#     else:
#         rows_to_delete_4.add(idx)
# #/  below code required remark column in input file
# # for idx in range(len(df_filter3)):

# #     material_type = str(df_filter3.loc[idx, 'Material type']).strip().upper()

# #     if material_type != 'ZSFG':
# #         continue

# #     et_match = str(df_filter3.loc[idx, 'ET Match']).strip()

# #     if et_match not in exceptions:
# #         rows_to_delete_4.add(idx)


# # After Filter 4
# log.info("Filter 4: identified %d rows to remove", len(rows_to_delete_4))
# df_after_cond4 = (
#     df_filter3
#     .drop(index=list(rows_to_delete_4))
#     .reset_index(drop=True)
# )

# log.info("After Filter 4 shape: %s", df_after_cond4.shape)
# export_df(df_after_cond4, "output/outputfiltertest4.csv")
# log.info("Wrote intermediate output: output/outputfiltertest4.csv")
# #c
# agg_dict = {col: 'first' for col in df_after_cond4.columns}

# agg_dict['Comp. Qty'] = 'sum'

# df_final_output = (
#     df_after_cond4
#     .groupby(['Plant','Material', 'Component'], as_index=False)
#     .agg(agg_dict)
# )
# log.info("Aggregation complete. Final output shape: %s", df_final_output.shape)
# export_df(df_final_output, 'output/final_BOM_output_filter.csv')
# log.info("Wrote final output: output/final_BOM_output_filter.csv")