# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pre-migration script for sale_ai_agent 20.0.1.1.0.
    Ensures safe schema upgrades and backward-compatible columns.
    """
    _logger.info("Starting pre-migration for sale_ai_agent to %s", version)
