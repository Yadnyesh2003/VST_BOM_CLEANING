import pandas as pd
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

# Filter 1 - Remove child rows under the parent component with remark "Engine", "Transmission", "FRONT AXLE ASSY"
log.info("Starting Filter 1: Remove child rows under parent component with remark 'Engine', 'Transmission', 'FRONT AXLE ASSY'")

bom_df = bom_df.merge(tc_df[['ET code', 'Remark']], left_on='Component', right_on='ET code', how='left')
bom_df['Remark'] = bom_df['Remark'].fillna('No Remark').str.strip()

rows_to_delete = set()


# remark_lookup = dict(zip(Tc['ET code'], Tc['Remark']))

# rows_to_delete = set()

# for idx in range(len(df)):
#     part = df.loc[idx, 'Component']

#     if part in remark_lookup and remark_lookup[part] in ['Engine', 'Transmission', 'FRONT AXLE ASSY']:

#         base_level = df.loc[idx, 'Level']

#         # Start from next row (keep matched row)
#         j = idx + 1

#         while j < len(df):
#             current_level = df.loc[j, 'Level']

#             if current_level <= base_level:
#                 break

#             rows_to_delete.add(j)
#             j += 1

log.info("Filter 1: identified %d rows to remove", len(rows_to_delete))
df_clean = df.drop(index=list(rows_to_delete)).reset_index(drop=True)
log.info("After Filter 1 shape: %s", df_clean.shape)
export_df(df_clean, "output/outputtest1.csv")
log.info("Wrote intermediate output: output/outputtest1.csv")


#Filter condition 2
master_lookup = set(IG['Unpainted parts'].dropna())

rows_to_delete_2 = set()

for idx in range(len(df_clean)):

    part = df_clean.loc[idx, 'Component']

    if part in master_lookup:

        base_level = df_clean.loc[idx, 'Level']

        rows_to_delete_2.add(idx)

        j = idx + 1
        while j < len(df_clean):

            if df_clean.loc[j, 'Level'] <= base_level:
                break

            rows_to_delete_2.add(j)
            j += 1


# After Filter 2
df_final = df_clean.drop(index=list(rows_to_delete_2)).reset_index(drop=True)
log.info("Filter 2: removed %d rows", len(rows_to_delete_2))
log.info("After Filter 2 shape: %s", df_final.shape)
export_df(df_final, "output/outputfiltertest2.csv")
log.info("Wrote intermediate output: output/outputfiltertest2.csv")
# Parent lookup from vstparent&child file
parent_lookup = dict(zip(vst_df['Child'], vst_df['Parent']))

rows_to_delete_3 = set()

for idx in range(len(df_final)):

    component = str(df_final.loc[idx, 'Component'])

    # Check 3rd-last digit
    if len(component) >= 3 and component[-3] in ['1', '9']:

        # Find parent
        if component in parent_lookup:

            parent = parent_lookup[component]

            # Search parent in File1
            parent_rows = df_final[df_final['Component'] == parent]

            if not parent_rows.empty:

                parent_material_type = parent_rows.iloc[0]['Material type']

                component_level = df_final.loc[idx, 'Level']

                if parent_material_type != 'ZSFG' and component_level != 1:

                    # CURRENT REQUIREMENT
                    # Delete only component row
                    rows_to_delete_3.add(idx)

                    # --------------------------------------------------
                    # FUTURE REQUIREMENT (currently disabled)
                    # Uncomment if you want to delete component hierarchy
                    # as well.
                    #
                    # base_level = component_level
                    #
                    # j = idx + 1
                    #
                    # while j < len(df_after_cond2):
                    #
                    #     if df_after_cond2.loc[j, 'L'] <= base_level:
                    #         break
                    #
                    #     rows_to_delete_3.add(j)
                    #     j += 1
                    # --------------------------------------------------
# After Filter 3
log.info("Filter 3: identified %d rows to remove", len(rows_to_delete_3))
df_filter3 = df_final.drop(index=list(rows_to_delete_3)).reset_index(drop=True)
log.info("After Filter 3 shape: %s", df_filter3.shape)
export_df(df_filter3, "output/outputfiltertest3.csv")
log.info("Wrote intermediate output: output/outputfiltertest3.csv")

exceptions = {'Engine', 'Transmission', 'FRONT AXLE ASSY'}

rows_to_delete_4 = set()
tc_remark_lookup = dict(zip(
    Tc['ET code'].astype(str).str.strip(),
    Tc['Remark'].astype(str).str.strip()
))
#this peace of code not require remark in input
for idx in range(len(df_filter3)):

    material_type = str(df_filter3.loc[idx, 'Material type']).strip()

    if material_type != 'ZSFG':
        continue

    material = str(df_filter3.loc[idx, 'Component']).strip()

    if material in tc_remark_lookup:
        continue
    else:
        rows_to_delete_4.add(idx)
#/  below code required remark column in input file
# for idx in range(len(df_filter3)):

#     material_type = str(df_filter3.loc[idx, 'Material type']).strip().upper()

#     if material_type != 'ZSFG':
#         continue

#     et_match = str(df_filter3.loc[idx, 'ET Match']).strip()

#     if et_match not in exceptions:
#         rows_to_delete_4.add(idx)


# After Filter 4
log.info("Filter 4: identified %d rows to remove", len(rows_to_delete_4))
df_after_cond4 = (
    df_filter3
    .drop(index=list(rows_to_delete_4))
    .reset_index(drop=True)
)

log.info("After Filter 4 shape: %s", df_after_cond4.shape)
export_df(df_after_cond4, "output/outputfiltertest4.csv")
log.info("Wrote intermediate output: output/outputfiltertest4.csv")
#c
agg_dict = {col: 'first' for col in df_after_cond4.columns}

agg_dict['Comp. Qty'] = 'sum'

df_final_output = (
    df_after_cond4
    .groupby(['Plant','Material', 'Component'], as_index=False)
    .agg(agg_dict)
)
log.info("Aggregation complete. Final output shape: %s", df_final_output.shape)
export_df(df_final_output, 'output/final_BOM_output_filter.csv')
log.info("Wrote final output: output/final_BOM_output_filter.csv")