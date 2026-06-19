import logging

logger = logging.getLogger(__name__)


def validate_schema(df, required_cols, name):
    missing = set(required_cols) - set(df.columns)
    extra = set(df.columns) - set(required_cols)

    if missing:
        logger.error("[%s] Missing columns: %s", name, missing)
        raise ValueError(f"[{name}] Missing columns: {missing}")

    logger.info("[%s] Schema OK", name)

    if extra:
        logger.warning("[%s] Extra columns: %s", name, extra)