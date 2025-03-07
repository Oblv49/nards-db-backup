import time
import subprocess
import logging
import os
import redis
from pathlib import Path
from typing import List

from app.modules.abstract_module import AbstractModule

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class RedisModule(AbstractModule):
    """
    Concrete implementation of AbstractModule for Redis databases, providing methods
    for listing, backing up, and restoring databases.
    """

    def __init__(self, host: str, port: str, username: str, password: str, maintenance_db: str = "0"):
        """
        Initializes the RedisModule with connection details.

        Args:
            host (str): The hostname of the Redis server.
            port (str): The port number of the Redis server.
            username (str): The username (if authentication is required).
            password (str): The password for authentication.
            maintenance_db (str): The Redis database index (default is "0").
        """
        super().__init__(host, port, username, password, maintenance_db)
        self._db_number = int(maintenance_db)

    def _connect(self):
        """
        Establishes a connection to the Redis server using the Python Redis library.
        
        Returns:
            redis.Redis: A Redis connection if successful, None otherwise.
        """
        try:
            port = int(self._port)
            
            for attempt in range(1, 6):
                try:
                    logger.info(f"Attempt {attempt}: Connecting to Redis at {self._host}:{port}")
                    
                    client = redis.Redis(
                        host=self._host,
                        port=port,
                        password=self._password,
                        db=self._db_number,
                        socket_timeout=5.0
                    )
                    
                    if client.ping():
                        logger.info("Successfully connected to Redis.")
                        return client
                    else:
                        logger.error("Redis ping failed.")
                except redis.RedisError as e:
                    logger.error(f"Error connecting to Redis: {e}")
                    wait_time = 3 * attempt
                    logger.info(f"Waiting {wait_time} seconds before next attempt...")
                    time.sleep(wait_time)
            
            logger.error("Failed to connect to Redis after multiple attempts.")
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            return None

    def list_all_databases(self) -> List[str]:
        """
        Lists available Redis databases.
        
        For Redis, we return the current selected database index as it doesn't
        support multiple databases in the same way as other database engines.
        
        Returns:
            List[str]: A list containing Redis database indexes.
        """
        return [str(self._db_number)]

    def backup_database(self, name: str, destination_file: Path) -> bool:
        """
        Performs a backup of the Redis database.
        
        This method triggers a SAVE command on Redis to create an RDB dump file, 
        then copies that file to the specified destination.
        
        Args:
            name (str): The Redis database index (ignored, uses the one specified during initialization).
            destination_file (Path): The path to store the backup.
        
        Returns:
            bool: True if the backup is successful, False otherwise.
        """
        client = self._connect()
        if not client:
            return False
            
        try:
            if client.save():
                logger.info("Redis SAVE command successful.")
                
                config = client.config_get('dir')
                redis_dir = config.get('dir', '/var/lib/redis')
                rdb_path = os.path.join(redis_dir, 'dump.rdb')
                
                try:
                    with open(rdb_path, 'rb') as source_file:
                        os.makedirs(os.path.dirname(destination_file), exist_ok=True)
                        with open(destination_file, 'wb') as dest_file:
                            dest_file.write(source_file.read())
                    logger.info(f"Redis database backup saved to {destination_file}.")
                    return True
                except (PermissionError, FileNotFoundError) as e:
                    logger.warning(f"Failed to copy RDB file with Python: {e}. Falling back to subprocess.")
                    subprocess.run(f"cp {rdb_path} {destination_file}", shell=True, check=True)
                    logger.info(f"Redis database backup saved to {destination_file} using subprocess.")
                    return True
            else:
                logger.error("Redis SAVE command failed.")
                return False
                
        except Exception as e:
            logger.error(f"Error backing up Redis database: {e}")
            return False
        finally:
            client.close()

    def restore_database(self, name: str, source_file: Path) -> bool:
        """
        Restores a Redis database from a backup file.
        
        This method:
        1. Shuts down the Redis server
        2. Replaces the dump.rdb file with the backup file
        3. Restarts the Redis server
        
        Args:
            name (str): The Redis database index (ignored).
            source_file (Path): The path of the backup file.
        
        Returns:
            bool: True if the restoration is successful, False otherwise.
        """
        client = self._connect()
        if not client:
            return False
            
        try:
            config = client.config_get('dir')
            redis_dir = config.get('dir', '/var/lib/redis')
            rdb_path = os.path.join(redis_dir, 'dump.rdb')
            
            logger.info("Shutting down Redis server for restoration...")
            client.shutdown(save=True)
            
            time.sleep(5)
            
            try:
                with open(source_file, 'rb') as source:
                    with open(rdb_path, 'wb') as dest:
                        dest.write(source.read())
            except (PermissionError, FileNotFoundError) as e:
                logger.warning(f"Failed to copy RDB file with Python: {e}. Falling back to subprocess.")
                subprocess.run(f"cp {source_file} {rdb_path}", shell=True, check=True)
            
            logger.info("Restarting Redis server...")
            subprocess.run("redis-server --daemonize yes", shell=True, check=True)
            
            time.sleep(5)
            
            test_client = redis.Redis(
                host=self._host,
                port=int(self._port),
                password=self._password,
                db=self._db_number,
                socket_timeout=5.0
            )
            
            if test_client.ping():
                logger.info(f"Redis database restored successfully from {source_file}.")
                test_client.close()
                return True
            else:
                logger.error("Failed to verify Redis is running after restoration.")
                return False
                
        except Exception as e:
            logger.error(f"Error restoring Redis database: {e}")
            return False