from flask import Flask, jsonify
from app.config import Config
from app.scheduler import Scheduler
import logging
import os
import click
from pathlib import Path

app = Flask(__name__)
app.config.from_object(Config)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the appropriate database module based on the configuration
if Config.DB_TYPE == 'mysql':
    from app.modules.mysql_module import MySQLModule as DatabaseModule
elif Config.DB_TYPE == 'postgis':
    from app.modules.postgis_module import PostGISModule as DatabaseModule
elif Config.DB_TYPE == 'postgres':
    from app.modules.postgres_module import PostgresModule as DatabaseModule
elif Config.DB_TYPE == 'mongodb':
    from app.modules.mongodb_module import MongoDBModule as DatabaseModule
elif Config.DB_TYPE == 'graphdb':
    from app.modules.graphdb_module import GraphDBModule as DatabaseModule
elif Config.DB_TYPE == 'redis':
    from app.modules.redis_module import RedisModule as DatabaseModule 
else:
    raise ValueError("Unsupported DB_TYPE. Use 'mysql', 'postgis', 'postgres', 'mongodb', 'graphdb' or 'redis'.")

db_module = DatabaseModule(
    host=Config.DB_HOST,
    port=Config.DB_PORT,
    username=Config.DB_USER,
    password=Config.DB_PASSWORD,
    maintenance_db=Config.DB_MAINTENANCE_NAME
)

# Initialize the scheduler with multiple cron configurations
scheduler = Scheduler(
    db_module=db_module,
    cron_configs=Config.CRON_CONFIGS,
    backup_dir=Config.BACKUP_DIR
)


@app.route('/health', methods=['GET'])
def health():
    """Endpoint to get the current health state of the last backup operation."""
    if scheduler.get_health():
        return jsonify({"health": "healthy"}), 200
    else:
        return jsonify({"health": "failed"}), 500


@app.cli.command("restore")
@click.argument("name_or_path")
def restore(name_or_path):
    """
    Restore the database from a given configuration name or backup file path.

    Args:
        name_or_path (str): The configuration name or the path to the backup file.
    """
    if os.path.exists(name_or_path):
        # If a file path is provided
        backup_path = Path(name_or_path)
        restore_db_name = backup_path.name.rsplit('.', 1)[0]  # Extract the database name from the file name
        logger.info(f"Attempting to restore database '{restore_db_name}' from file '{name_or_path}'")
        restore_success = db_module.restore_database(restore_db_name, backup_path)
        if restore_success:
            logger.info(f"Restore successful for '{name_or_path}'")
        else:
            logger.error(f"Restore failed for '{name_or_path}'")
    else:
        # If a configuration name is provided
        restore_cron_name = name_or_path
        restore_backup_dir = Config.BACKUP_DIR / restore_cron_name
        backup_file = max(restore_backup_dir.glob('**/*.backup'), key=os.path.getmtime, default=None)
        if backup_file:
            backup_file_path = Path(backup_file)
            restore_db_name = backup_file_path.name.rsplit('.', 1)[0]  # Extract the database name from the file name
            logger.info(f"Attempting to restore database '{restore_db_name}' from latest backup '{backup_file}' for "
                        f"configuration '{restore_cron_name}'")
            restore_success = db_module.restore_database(restore_db_name, backup_file_path)
            if restore_success:
                logger.info(f"Restore successful for configuration '{restore_cron_name}' "
                            f"using backup file '{backup_file}'")
            else:
                logger.error(f"Restore failed for configuration '{restore_cron_name}' "
                             f"using backup file '{backup_file}'")
        else:
            logger.warning(f"No backups found for configuration '{restore_cron_name}'")


if __name__ == '__main__':
    if Config.RESTORE_CONFIG_NAME:
        logger.info(f"Startup restore is configured at {Config.RESTORE_CONFIG_NAME}")
        cron_name = Config.RESTORE_CONFIG_NAME
        backup_dir = Config.BACKUP_DIR / cron_name
        latest_backup = max(backup_dir.glob('**/*.backup'), key=os.path.getmtime, default=None)
        logger.info(f"Detected latest backup: {latest_backup}")
        if latest_backup:
            latest_backup_path = Path(latest_backup)
            db_name = latest_backup_path.name.rsplit('.', 2)[0]  # Extract the database name from the file name
            logger.info(f"Attempting to restore database '{db_name}' from latest backup '{latest_backup}' for "
                        f"configuration '{cron_name}' at startup")
            success = db_module.restore_database(db_name, latest_backup_path)
            if success:
                logger.info(f"Restore successful at startup for configuration '{cron_name}'")
            else:
                logger.error(f"Restore failed at startup for configuration '{cron_name}'")
    scheduler.start()
    app.run(host='0.0.0.0', port=5000)