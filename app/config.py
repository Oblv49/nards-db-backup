import os
import json
from pathlib import Path
import logging

# Setup logging for configuration module
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Config:
    # Database configuration
    DB_TYPE = os.getenv('DB_TYPE', 'mysql')  # 'mysql' or 'postgis or mongoDB'
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    port_default = 3306 if DB_TYPE=='mysql' else 5432
    DB_PORT = os.getenv('DB_PORT', port_default)
    DB_USER = os.getenv('DB_USER', 'user')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
    DB_MAINTENANCE_NAME = os.getenv('DB_MAINTENANCE_NAME', DB_USER)

    # Backup configurations
    CRON_CONFIGS = os.getenv('CRON_CONFIGS', '0 0 * * *')
    BACKUP_DIR = Path('/backups')

    # Restore settings
    RESTORE_CONFIG_NAME = os.getenv('RESTORE_CONFIG_NAME', '')

    # Parse CRON_CONFIGS from environment variable
    try:
        cron_configs = json.loads(CRON_CONFIGS)
        if not isinstance(cron_configs, list):
            raise ValueError("CRON_CONFIGS must be a list of dictionaries.")
        for config in cron_configs:
            if 'cron' not in config:
                raise ValueError("Each configuration must contain a 'cron' key.")
            if len(cron_configs) > 1 and 'name' not in config:
                raise ValueError("Each configuration must contain a 'name' key if there are multiple configurations.")
            # Set default value for retention_max if not provided
            config.setdefault('retention_max', 90)
            if 'name' not in config:
                config['name'] = 'default'
        CRON_CONFIGS = cron_configs
        logger.info(f"Parsed CRON_CONFIGS: {CRON_CONFIGS}")
    except json.JSONDecodeError:
        # Assume the CRON_CONFIGS is a single cron string and wrap it in a list of dicts
        CRON_CONFIGS = [{"cron": CRON_CONFIGS, "retention_max": 90, "name": "default"}]
        logger.info(f"Using single cron configuration: {CRON_CONFIGS}")

    # Log final configurations
    logger.info(f"DB_HOST: {DB_HOST}")
    logger.info(f"DB_PORT: {DB_PORT}")
    logger.info(f"DB_USER: {DB_USER}")
    logger.info(f"DB_PASSWORD: {'*****' if DB_PASSWORD else ''}")
    logger.info(f"DB_NAME: {DB_MAINTENANCE_NAME}")
    logger.info(f"DB_TYPE: {DB_TYPE}")
    logger.info(f"BACKUP_DIR: {BACKUP_DIR}")
    logger.info(f"CRON_CONFIGS: {CRON_CONFIGS}")
    logger.info(f"RESTORE_CONFIG_NAME: {RESTORE_CONFIG_NAME}")
