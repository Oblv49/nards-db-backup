import time
import subprocess
import logging
from pathlib import Path
from typing import List

# Import the abstract module that enforces the interface
from app.modules.abstract_module import AbstractModule

# Configure the logger for useful runtime information
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MongoDBModule(AbstractModule):
    """
    Concrete implementation of AbstractModule for MongoDB databases, providing methods
    for listing, backing up, and restoring databases.
    """
    
    def __init__(self, host: str, port: str, username: str, password: str, maintenance_db: str):
        """
        Initializes the MongoDBModule with connection details.
        
        Args:
            host (str): The hostname of the MongoDB server.
            port (str): The port number of the MongoDB server.
            username (str): The username to connect to the MongoDB server.
            password (str): The password to connect to the MongoDB server.
            maintenance_db (str): Maintenance database used for connection verification.
        """
        super().__init__(host, port, username, password, maintenance_db)

    def _connect(self):
        """
        Establishes a connection to the MongoDB server.
        
        Attempts up to 6 times with increasing wait times (5 * attempt seconds)
        in case of failure, similar to the MySQL module.
        
        Returns:
            MongoClient: The MongoClient object if the connection is successful, None otherwise.
        """
        from pymongo import MongoClient

        client = None
        for attempt in range(1, 7):
            try:
                logger.info(f"Attempt {attempt}: Connecting to MongoDB at {self._host}:{self._port}")
                # Create the connection URI including credentials and the maintenance database
                uri = f"mongodb://{self._username}:{self._password}@{self._host}:{self._port}/{self._maintenance_db}"
                client = MongoClient(uri, serverSelectionTimeoutMS=5000)
                # Execute a simple command to verify the connection
                client.server_info()
                logger.info("Successfully connected to MongoDB.")
                return client
            except Exception as e:
                logger.error(f"Error connecting to MongoDB: {e}")
                wait_time = 5 * attempt
                logger.info(f"Waiting {wait_time} seconds before next attempt...")
                time.sleep(wait_time)
        logger.error("Unable to connect to MongoDB after multiple attempts.")
        return None

    def list_all_databases(self) -> List[str]:
        """
        Lists all databases on the MongoDB server, excluding system databases.
        
        Returns:
            List[str]: A list of non-system database names.
        """
        client = self._connect()
        if client:
            try:
                # Retrieve all database names
                databases = client.list_database_names()
                # Exclude system databases ('admin', 'local', 'config')
                system_dbs = ['admin', 'local', 'config']
                filtered = [db for db in databases if db not in system_dbs]
                return filtered
            except Exception as e:
                logger.error(f"Error listing MongoDB databases: {e}")
                return []
            finally:
                client.close()
                logger.info("MongoDB connection closed after listing databases.")
        else:
            logger.error("Failed to connect to MongoDB.")
            return []

    def backup_database(self, name: str, destination_file: Path) -> bool:
        """
        Performs a backup of the specified MongoDB database using the 'mongodump' utility.
        
        Utilizes:
          - the --archive option to create a single backup file
          - the --gzip option to compress the dump
        
        Args:
            name (str): The name of the database to back up.
            destination_file (Path): The path to the backup file.
        
        Returns:
            bool: True if the backup is successful, False otherwise.
        """
        command = (
            f"mongodump --host {self._host} --port {self._port} "
            f"--username {self._username} --password {self._password} "
            f"--db {name} --archive={destination_file} --gzip"
        )
        try:
            subprocess.run(command, shell=True, check=True, text=True)
            logger.info(f"Backup of MongoDB database '{name}' completed successfully to {destination_file}.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error backing up MongoDB database '{name}': {e}")
            return False

    def restore_database(self, name: str, source_file: Path) -> bool:
        """
        Restores the specified MongoDB database using the 'mongorestore' utility.
        
        The --drop option removes the existing database before restoration,
        ensuring a clean restore.
        
        Args:
            name (str): The name of the database to restore.
            source_file (Path): The path to the backup file.
        
        Returns:
            bool: True if the restoration is successful, False otherwise.
        """
        command = (
            f"mongorestore --host {self._host} --port {self._port} "
            f"--username {self._username} --password {self._password} "
            f"--db {name} --drop --archive={source_file} --gzip"
        )
        try:
            subprocess.run(command, shell=True, check=True, text=True)
            logger.info(f"Restore of MongoDB database '{name}' completed successfully from {source_file}.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error restoring MongoDB database '{name}': {e}")
            return False
