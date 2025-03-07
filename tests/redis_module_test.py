import os
import sys
import pytest
import subprocess
from pathlib import Path

# Inserisce la root directory nei moduli di ricerca
sys.path.insert(1, os.getcwd())

from app.modules.redis_module import RedisModule


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig):
    return os.path.join(str(pytestconfig.rootdir), "tests", "docker-compose.yml")


def check_redis_connection(host, port, password=None):
    """Check if Redis server is ready for connections."""
    try:
        command = f"redis-cli -h {host} -p {port} PING"
        if password:
            command = f"redis-cli -h {host} -p {port} -a {password} PING"
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout.strip() == "PONG"
    except Exception:
        return False


@pytest.fixture(scope='session', autouse=True)
def redis_connection(docker_ip, docker_services):
    docker_port = docker_services.port_for("redis", 6379)

    docker_services.wait_until_responsive(
        timeout=60.0, pause=0.1, check=lambda: check_redis_connection(
            host=docker_ip,
            port=docker_port,
            password="testpassword"
        )
    )

    yield


@pytest.fixture
def redis_module(docker_ip, docker_services):
    docker_port = docker_services.port_for("redis", 6379)
    return RedisModule(docker_ip, docker_port, "", "testpassword")


def test_list_all_databases(redis_module):
    result = redis_module.list_all_databases()
    assert "0" in result  # Redis usa database numerici


def test_backup_and_restore_database(pytestconfig, redis_module):
    backup_file = Path(str(pytestconfig.rootdir), "tests", "test_redis_backup.rdb")
    if backup_file.exists():
        os.remove(backup_file)

    try:
        # Eseguire il backup
        assert redis_module.backup_database("0", backup_file)

        # Simulare perdita dati
        subprocess.run("redis-cli FLUSHALL", shell=True, check=True, text=True)

        # Ripristinare il database
        assert redis_module.restore_database("0", backup_file)

        # Controllare che Redis sia di nuovo accessibile
        assert check_redis_connection(redis_module._host, redis_module._port, redis_module._password)

    finally:
        if backup_file.exists():
            os.remove(backup_file)
