from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse

    _langfuse: Optional[Langfuse] = (
        Langfuse() if os.getenv("LANGFUSE_SECRET_KEY") else None
    )
    if _langfuse:
        logger.info("Langfuse tracing enabled (host=%s)", os.getenv("LANGFUSE_HOST"))
    else:
        logger.info("Langfuse tracing disabled (LANGFUSE_SECRET_KEY not set)")
except Exception as e:
    logger.warning("Langfuse not available: %s", e)
    _langfuse = None


def get_langfuse() -> Optional[Langfuse]:
    return _langfuse
