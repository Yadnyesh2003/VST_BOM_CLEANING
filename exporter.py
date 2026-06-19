import pandas as pd
import logging

logger = logging.getLogger(__name__)


def export_errors(errors, path):
    if not errors:
        logger.info("No errors to export to %s", path)
        return

    df = pd.DataFrame(errors)
    df.to_csv(path, index=False)
    logger.info("Exported %d errors to %s", len(df), path)


def export_df(df: pd.DataFrame, path: str):
    if df is None:
        logger.warning("No DataFrame provided to export to %s", path)
        return

    df.to_csv(path, index=False)
    logger.info("Exported DataFrame with shape %s to %s", df.shape, path)