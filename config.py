from pathlib import Path

BASE_PATH = Path(r"D:\000 VDL TESTING WORK\vst_bom_cleaning_automation\input")

FILES = {
    "BOM": BASE_PATH / "BOM_20260616.csv",
    "TC": BASE_PATH / "TC_Master.csv",
    "IGNORE": BASE_PATH / "IgnoreMaster.csv",
    "BOM_PARENT_CHILD": BASE_PATH / "BOM_Parent_Child.csv"
}

BOM_SCHEMA = [
    "Material type","Plant","Material","BOM Application",
    "Object description","Item category","Item Number",
    "Component","description","Comp. Qty","Unit","Level",
    "BOM Usage","Alternative BOM","Backflush","Valid from","Valid to"
]

TC_SCHEMA = [
    "FG Material Code",
    "FG code (short)",
    "ET code","Remark",
    "Description"
]

IGNORE_SCHEMA = [
    "Unpainted parts",
    "Remark"
]


BOM_PARENT_CHILD_SCHEMA = [
    "Finished Good (FG)",
    "Plant",
    "Level_Of_Child",
    "Parent",
    "Parent_Comp_Qty",
    "Child",
    "Child_Comp_Qty"
]