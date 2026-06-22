import pandas as pd
import logging

logger = logging.getLogger(__name__)


def read_bom(path):
    logger.info("Reading BOM from %s", path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        sample = f.read(5000)

    sep = "|" if "|" in sample else "\t" if "\t" in sample else ","
    logger.info("Detected separator for %s: '%s'", path, sep)

    df = pd.read_csv(path, sep=sep, engine="python", on_bad_lines="skip")
    df.columns = df.columns.str.strip()
    logger.info("Loaded BOM with shape %s", df.shape)
    return df


def read_csv(path):
    logger.info("Reading CSV from %s", path)

    df = pd.read_csv(path)
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    # Clean string data (VERY important for merges)
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].astype(str).str.strip()
    
    logger.info("Loaded CSV with shape %s", df.shape)
    return df