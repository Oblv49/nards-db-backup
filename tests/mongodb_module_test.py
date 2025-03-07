import os
import sys
import pytest
import time
from pymongo import MongoClient
from pathlib import Path
from app.modules.mongodb_module import MongoDBModule

# Inserisce la root del progetto nel path per importare i moduli
sys.path.insert(1, os.getcwd())

@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    return os.path.join(str(pytestconfig.rootdir), "tests", "docker-compose.yml")

def check_mongo_connection(host, port, user, password):
    """ Controlla se MongoDB è pronto per le connessioni. """
    import time
    print(f"Checking MongoDB connection to {host}:{port}")
    try:
        client = MongoClient(
            f"mongodb://{user}:{password}@{host}:{port}/test_database",
            serverSelectionTimeoutMS=5000
        )
        info = client.server_info()
        print(f"MongoDB connection successful: {info}")
        return True
    except Exception as e:
        print(f"MongoDB connection failed: {e}")
        return False

@pytest.fixture(scope="session", autouse=True)
def mongodb_connection(docker_ip, docker_services):
    docker_port = docker_services.port_for("mongodb", 27017)
    print(f"MongoDB port mapped: {docker_port}")
    
    docker_services.wait_until_responsive(
        timeout=60.0, pause=0.5, check=lambda: check_mongo_connection(
            host=docker_ip, port=docker_port, user="testuser", password="testpassword"
        )
    )

    client = MongoClient(f"mongodb://testuser:testpassword@{docker_ip}:{docker_port}/test_database")
    db = client["test_database"]
    
    db.test_collection.insert_one({"key": "Original Data"})
    yield client
    
    db.test_collection.drop()
    client.close()

@pytest.fixture
def mongodb_module(docker_ip, docker_services):
    docker_port = docker_services.port_for("mongodb", 27017)
    return MongoDBModule(docker_ip, str(docker_port), "testuser", "testpassword", "test_database")

def test_list_all_databases(mongodb_module):
    """ Testa se il modulo MongoDB riesce a elencare i database. """
    databases = mongodb_module.list_all_databases()
    assert "test_database" in databases

def test_backup_and_restore_database(pytestconfig, mongodb_connection, mongodb_module):
    """ Testa il backup e il restore di MongoDB. """
    db = mongodb_connection["test_database"]
    backup_file = Path(str(pytestconfig.rootdir), "tests", "test_mongodb_backup.gz")

    if backup_file.exists():
        os.remove(backup_file)

    try:
        # Esegue il backup
        backup_result = mongodb_module.backup_database("test_database", backup_file)
        assert backup_result

        # Modifica i dati nel database
        db.test_collection.delete_many({})
        db.test_collection.insert_one({"key": "Modified Data"})

        # Ripristina il database
        restore_result = mongodb_module.restore_database("test_database", backup_file)
        assert restore_result

        # Controlla che i dati originali siano stati ripristinati
        restored_data = db.test_collection.find_one({})
        assert restored_data["key"] == "Original Data"

    finally:
        if backup_file.exists():
            os.remove(backup_file)