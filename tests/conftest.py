"""
Конфигурация тестов и фикстуры для Flink Observer
"""
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool, text
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

# Импорты из нашего приложения
from flink_observer.api.main import app
from flink_observer.data.models import Base
from flink_observer.data.database import get_database
from flink_observer.data.repositories import ClusterRepository, JobRepository


# Тестовая база данных в памяти
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создаем таблицы
Base.metadata.create_all(bind=engine)


def override_get_database():
    """Переопределяем подключение к БД для тестов"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Переопределяем зависимость
app.dependency_overrides[get_database] = override_get_database


@pytest.fixture(scope="session")
def event_loop():
    """Создаем event loop для всех тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client():
    """Синхронный тестовый клиент"""
    with TestClient(app) as client:
        yield client


@pytest_asyncio.fixture
async def async_client():
    """Асинхронный тестовый клиент"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def db_session():
    """Сессия базы данных для тестов"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def cluster_repo(db_session):
    """Репозиторий кластеров"""
    return ClusterRepository(db_session)


@pytest.fixture
def job_repo(db_session):
    """Репозиторий джобов"""
    return JobRepository(db_session)


@pytest.fixture
def sample_cluster_data():
    """Образец данных кластера"""
    return {
        "name": "test-cluster",
        "url": "http://localhost:8081",
        "description": "Test cluster for testing",
        "is_active": True
    }


@pytest.fixture
def sample_job_data():
    """Образец данных джоба"""
    return {
        "job_id": "test-job-123",
        "cluster_name": "test-cluster",
        "job_name": "Test Job",
        "job_state": "RUNNING",
        "job_type": "STREAMING",
        "job_duration": 3600000,  # 1 час
        "job_start_time": int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
        "job_end_time": None,
        "max_parallelism": 8,
        "is_stoppable": False,
        "job_details": {
            "jid": "test-job-123",
            "name": "Test Job",
            "state": "RUNNING",
            "vertices": [],
            "status-counts": {},
            "plan": {}
        }
    }


@pytest.fixture
def multiple_clusters_data():
    """Множество кластеров для тестирования"""
    return [
        {
            "name": "cluster-1",
            "url": "http://localhost:8081",
            "description": "First test cluster",
            "is_active": True
        },
        {
            "name": "cluster-2",
            "url": "http://localhost:8082",
            "description": "Second test cluster",
            "is_active": False
        },
        {
            "name": "cluster-3",
            "url": "http://localhost:8083",
            "description": "Third test cluster",
            "is_active": True
        }
    ]


@pytest.fixture
def multiple_jobs_data():
    """Множество джобов для тестирования"""
    base_time = datetime.now()
    return [
        {
            "job_id": "job-1",
            "cluster_name": "cluster-1",
            "job_name": "Streaming Job 1",
            "job_state": "RUNNING",
            "job_type": "STREAMING",
            "job_duration": 3600000,
            "job_start_time": int((base_time - timedelta(hours=2)).timestamp() * 1000),
            "job_end_time": None,
            "max_parallelism": 4,
            "is_stoppable": False,
            "job_details": {"jid": "job-1", "name": "Streaming Job 1", "state": "RUNNING"}
        },
        {
            "job_id": "job-2",
            "cluster_name": "cluster-1",
            "job_name": "Batch Job 1",
            "job_state": "FAILED",
            "job_type": "BATCH",
            "job_duration": 1800000,
            "job_start_time": int((base_time - timedelta(hours=1)).timestamp() * 1000),
            "job_end_time": int((base_time - timedelta(minutes=30)).timestamp() * 1000),
            "max_parallelism": 8,
            "is_stoppable": False,
            "job_details": {"jid": "job-2", "name": "Batch Job 1", "state": "FAILED"}
        },
        {
            "job_id": "job-3",
            "cluster_name": "cluster-2",
            "job_name": "Streaming Job 2",
            "job_state": "FINISHED",
            "job_type": "STREAMING",
            "job_duration": 7200000,
            "job_start_time": int((base_time - timedelta(hours=3)).timestamp() * 1000),
            "job_end_time": int((base_time - timedelta(hours=1)).timestamp() * 1000),
            "max_parallelism": 2,
            "is_stoppable": False,
            "job_details": {"jid": "job-3", "name": "Streaming Job 2", "state": "FINISHED"}
        }
    ]


@pytest.fixture
def mock_flink_response():
    """Мок ответа от Flink API"""
    return {
        "jobs": [
            {
                "id": "test-job-123",
                "name": "Test Job",
                "state": "RUNNING",
                "start-time": int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
                "end-time": -1,
                "duration": 3600000,
                "last-modification": int(datetime.now().timestamp() * 1000),
                "tasks": {
                    "total": 4,
                    "running": 4,
                    "finished": 0,
                    "canceling": 0,
                    "canceled": 0,
                    "failed": 0
                }
            }
        ]
    }


@pytest.fixture
def mock_flink_job_details():
    """Мок детальной информации о джобе"""
    return {
        "jid": "test-job-123",
        "name": "Test Job",
        "state": "RUNNING",
        "start-time": int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
        "end-time": -1,
        "duration": 3600000,
        "now": int(datetime.now().timestamp() * 1000),
        "timestamps": {
            "RUNNING": int((datetime.now() - timedelta(hours=1)).timestamp() * 1000)
        },
        "vertices": [
            {
                "id": "vertex-1",
                "name": "Source",
                "parallelism": 2,
                "status": "RUNNING",
                "start-time": int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
                "end-time": -1,
                "duration": 3600000,
                "tasks": {
                    "RUNNING": 2,
                    "FINISHED": 0,
                    "FAILED": 0,
                    "CANCELED": 0
                },
                "metrics": {
                    "read-bytes": 1024000,
                    "write-bytes": 2048000,
                    "read-records": 10000,
                    "write-records": 10000
                }
            }
        ],
        "status-counts": {
            "RUNNING": 4,
            "FINISHED": 0,
            "FAILED": 0,
            "CANCELED": 0
        },
        "plan": {
            "jid": "test-job-123",
            "name": "Test Job",
            "nodes": []
        }
    }


@pytest.fixture
def mock_httpx_client():
    """Мок HTTP клиента"""
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"jobs": []}
    mock_client.get.return_value = mock_response
    return mock_client


@pytest.fixture(autouse=True)
def clean_database(db_session):
    """Очищаем базу данных перед каждым тестом"""
    # Очищаем таблицы в правильном порядке (с учетом внешних ключей)
    db_session.execute(text("DELETE FROM job_snapshots"))
    db_session.execute(text("DELETE FROM flink_clusters"))
    db_session.commit()


@pytest.fixture
def mock_data_collector():
    """Мок коллектора данных"""
    mock_collector = MagicMock()
    mock_collector.collect_cluster_data = AsyncMock(return_value={
        "cluster_name": "test-cluster",
        "jobs_collected": 1,
        "success": True,
        "timestamp": datetime.now()
    })
    mock_collector.collect_all_clusters = AsyncMock(return_value=[
        {
            "cluster_name": "test-cluster",
            "jobs_collected": 1,
            "success": True,
            "timestamp": datetime.now()
        }
    ])
    return mock_collector


# Маркеры для категоризации тестов
def pytest_configure(config):
    """Конфигурация pytest"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Параметры для тестирования различных состояний джобов
JOB_STATES = ["RUNNING", "FINISHED", "FAILED", "CANCELED", "CANCELING", "SUSPENDED", "RESTARTING"]

# Утилиты для тестов
class TestUtils:
    """Вспомогательные утилиты для тестов"""

    @staticmethod
    def create_cluster(repo, **kwargs):
        """Создать тестовый кластер"""
        default_data = {
            "name": "test-cluster",
            "url": "http://localhost:8081",
            "description": "Test cluster",
            "is_active": True
        }
        default_data.update(kwargs)
        return repo.create(default_data)

    @staticmethod
    def create_job_snapshot(repo, **kwargs):
        """Создать тестовый снимок джоба"""
        default_data = {
            "job_id": "test-job-123",
            "cluster_name": "test-cluster",
            "job_name": "Test Job",
            "job_state": "RUNNING",
            "job_type": "STREAMING",
            "job_duration": 3600000,
            "job_start_time": int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
            "job_end_time": None,
            "max_parallelism": 8,
            "is_stoppable": False,
            "job_details": {
                "jid": "test-job-123",
                "name": "Test Job",
                "state": "RUNNING",
                "vertices": [],
                "status-counts": {},
                "plan": {}
            }
        }
        default_data.update(kwargs)
        # Используем upsert_snapshot вместо create_snapshot
        return repo.upsert_snapshot(default_data)

    @staticmethod
    def create_multiple_job_snapshots(repo, jobs_data):
        """Создать несколько снимков джобов"""
        snapshots = []
        for job_data in jobs_data:
            snapshot = repo.upsert_snapshot(job_data)
            snapshots.append(snapshot)
        return snapshots

    @staticmethod
    def create_test_cluster_with_jobs(cluster_repo, job_repo, cluster_name="test-cluster", job_count=3):
        """Создать тестовый кластер с джобами"""
        # Создаем кластер
        cluster = TestUtils.create_cluster(cluster_repo, name=cluster_name)

        # Создаем джобы
        jobs = []
        job_states = ["RUNNING", "FINISHED", "FAILED"]

        for i in range(job_count):
            state = job_states[i % len(job_states)]
            job = TestUtils.create_job_snapshot(
                job_repo,
                job_id=f"job-{i}",
                cluster_name=cluster_name,
                job_name=f"Job {i}",
                job_state=state
            )
            jobs.append(job)

        return cluster, jobs


@pytest.fixture
def test_utils():
    """Утилиты для тестов"""
    return TestUtils


@pytest.fixture
def test_cluster_with_jobs(cluster_repo, job_repo, test_utils):
    """Фикстура для создания кластера с джобами"""
    cluster, jobs = test_utils.create_test_cluster_with_jobs(
        cluster_repo, job_repo, "fixture-cluster", 5
    )
    return cluster, jobs


@pytest.fixture
def sample_job_snapshot_data():
    """Образец данных для создания снимка джоба (соответствует структуре БД)"""
    return {
        "job_id": "snapshot-test-job-123",
        "cluster_name": "snapshot-test-cluster",
        "job_name": "Snapshot Test Job",
        "job_state": "RUNNING",
        "job_type": "STREAMING",
        "is_stoppable": False,
        "max_parallelism": 8,
        "job_start_time": int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
        "job_end_time": None,
        "job_duration": 3600000,
        "job_details": {
            "jid": "snapshot-test-job-123",
            "name": "Snapshot Test Job",
            "state": "RUNNING",
            "vertices": [],
            "status-counts": {"RUNNING": 4},
            "plan": {"nodes": []}
        }
    }


@pytest.fixture
def job_snapshot_factory():
    """Фабрика для создания снимков джобов"""
    def _create_job_snapshot(job_repo, **kwargs):
        default_data = {
            "job_id": f"factory-job-{datetime.now().timestamp()}",
            "cluster_name": "factory-cluster",
            "job_name": "Factory Job",
            "job_state": "RUNNING",
            "job_type": "STREAMING",
            "is_stoppable": False,
            "max_parallelism": 4,
            "job_start_time": int((datetime.now() - timedelta(hours=1)).timestamp() * 1000),
            "job_end_time": None,
            "job_duration": 3600000,
            "job_details": {"jid": kwargs.get("job_id", "factory-job"), "state": kwargs.get("job_state", "RUNNING")}
        }
        default_data.update(kwargs)
        return job_repo.upsert_snapshot(default_data)

    return _create_job_snapshot


@pytest.fixture
def cluster_factory():
    """Фабрика для создания кластеров"""
    def _create_cluster(cluster_repo, **kwargs):
        default_data = {
            "name": f"factory-cluster-{datetime.now().timestamp()}",
            "url": "http://localhost:8081",
            "description": "Factory cluster",
            "is_active": True
        }
        default_data.update(kwargs)
        return cluster_repo.create(default_data)

    return _create_cluster


# Вспомогательные фикстуры для более сложных тестов
@pytest.fixture
def populated_database(cluster_repo, job_repo, test_utils):
    """Фикстура для заполнения БД тестовыми данными"""
    clusters = []
    jobs = []

    # Создаем 3 кластера
    for i in range(3):
        cluster = test_utils.create_cluster(
            cluster_repo,
            name=f"populated-cluster-{i}",
            is_active=i < 2  # Первые 2 активны
        )
        clusters.append(cluster)

        # Создаем джобы для каждого кластера
        for j in range(4):
            job_states = ["RUNNING", "FINISHED", "FAILED", "CANCELED"]
            job = test_utils.create_job_snapshot(
                job_repo,
                job_id=f"populated-job-{i}-{j}",
                cluster_name=f"populated-cluster-{i}",
                job_name=f"Job {j} in Cluster {i}",
                job_state=job_states[j]
            )
            jobs.append(job)

    return clusters, jobs


@pytest.fixture
def performance_test_data(cluster_repo, job_repo, test_utils):
    """Фикстура для тестов производительности"""
    cluster = test_utils.create_cluster(cluster_repo, name="performance-cluster")

    # Создаем много джобов для тестирования производительности
    jobs = []
    for i in range(100):
        job_states = ["RUNNING", "FINISHED", "FAILED"]
        job = test_utils.create_job_snapshot(
            job_repo,
            job_id=f"perf-job-{i}",
            cluster_name="performance-cluster",
            job_name=f"Performance Job {i}",
            job_state=job_states[i % len(job_states)]
        )
        jobs.append(job)

    return cluster, jobs
