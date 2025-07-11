"""
Тесты эндпоинтов кластеров
"""
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock


@pytest.mark.unit
class TestClustersEndpoints:
    """Тесты эндпоинтов кластеров"""
    
    def test_get_clusters_empty(self, client: TestClient):
        """Тест получения пустого списка кластеров"""
        response = client.get("/api/clusters")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_create_cluster_success(self, client: TestClient, sample_cluster_data):
        """Тест успешного создания кластера"""
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        
        cluster = response.json()
        assert cluster["name"] == sample_cluster_data["name"]
        assert cluster["url"] == sample_cluster_data["url"]
        assert cluster["description"] == sample_cluster_data["description"]
        assert cluster["is_active"] == sample_cluster_data["is_active"]
        assert "id" in cluster
        assert "created_at" in cluster
    
    def test_create_cluster_duplicate_name(self, client: TestClient, sample_cluster_data):
        """Тест создания кластера с дублирующимся именем"""
        # Создаем первый кластер
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        
        # Пытаемся создать второй кластер с тем же именем
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 400
        assert "уже существует" in response.json()["detail"]
    
    def test_get_clusters_with_data(self, client: TestClient, multiple_clusters_data):
        """Тест получения списка кластеров с данными"""
        created_clusters = []
        
        # Создаем несколько кластеров
        for cluster_data in multiple_clusters_data:
            response = client.post("/api/clusters", json=cluster_data)
            assert response.status_code == 200
            created_clusters.append(response.json())
        
        # Получаем список кластеров
        response = client.get("/api/clusters")
        assert response.status_code == 200
        
        clusters = response.json()
        assert len(clusters) == len(multiple_clusters_data)
        
        # Проверяем, что все кластеры присутствуют
        cluster_names = {cluster["name"] for cluster in clusters}
        expected_names = {cluster["name"] for cluster in multiple_clusters_data}
        assert cluster_names == expected_names
    
    def test_get_cluster_by_id_success(self, client: TestClient, sample_cluster_data):
        """Тест получения кластера по ID"""
        # Создаем кластер
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        cluster = response.json()
        cluster_id = cluster["id"]
        
        # Получаем кластер по ID
        response = client.get(f"/api/clusters/{cluster_id}")
        assert response.status_code == 200
        
        retrieved_cluster = response.json()
        assert retrieved_cluster["id"] == cluster_id
        assert retrieved_cluster["name"] == sample_cluster_data["name"]
    
    def test_get_cluster_by_id_not_found(self, client: TestClient):
        """Тест получения несуществующего кластера"""
        response = client.get("/api/clusters/999999")
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]
    
    def test_update_cluster_success(self, client: TestClient, sample_cluster_data):
        """Тест успешного обновления кластера"""
        # Создаем кластер
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        cluster = response.json()
        cluster_id = cluster["id"]
        
        # Обновляем кластер
        update_data = {
            "description": "Updated description",
            "url": "http://localhost:8082"
        }
        response = client.put(f"/api/clusters/{cluster_id}", json=update_data)
        assert response.status_code == 200
        
        updated_cluster = response.json()
        assert updated_cluster["description"] == update_data["description"]
        assert updated_cluster["url"] == update_data["url"]
        assert updated_cluster["name"] == sample_cluster_data["name"]  # Не должно измениться
    
    def test_update_cluster_not_found(self, client: TestClient):
        """Тест обновления несуществующего кластера"""
        update_data = {"description": "Updated description"}
        response = client.put("/api/clusters/999999", json=update_data)
        assert response.status_code == 404
    
    def test_delete_cluster_success(self, client: TestClient, sample_cluster_data):
        """Тест успешного удаления кластера"""
        # Создаем кластер
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        cluster = response.json()
        cluster_id = cluster["id"]
        
        # Удаляем кластер
        response = client.delete(f"/api/clusters/{cluster_id}")
        assert response.status_code == 200
        
        # Проверяем, что кластер удален
        response = client.get(f"/api/clusters/{cluster_id}")
        assert response.status_code == 404
    
    def test_delete_cluster_not_found(self, client: TestClient):
        """Тест удаления несуществующего кластера"""
        response = client.delete("/api/clusters/999999")
        assert response.status_code == 404
    
    def test_activate_cluster_success(self, client: TestClient, sample_cluster_data):
        """Тест успешной активации кластера"""
        # Создаем неактивный кластер
        sample_cluster_data["is_active"] = False
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        cluster = response.json()
        cluster_id = cluster["id"]
        
        # Активируем кластер
        response = client.post(f"/api/clusters/{cluster_id}/activate")
        assert response.status_code == 200
        
        # Проверяем, что кластер активирован
        response = client.get(f"/api/clusters/{cluster_id}")
        assert response.status_code == 200
        cluster = response.json()
        assert cluster["is_active"] is True
    
    def test_deactivate_cluster_success(self, client: TestClient, sample_cluster_data):
        """Тест успешной деактивации кластера"""
        # Создаем активный кластер
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        cluster = response.json()
        cluster_id = cluster["id"]
        
        # Деактивируем кластер
        response = client.post(f"/api/clusters/{cluster_id}/deactivate")
        assert response.status_code == 200
        
        # Проверяем, что кластер деактивирован
        response = client.get(f"/api/clusters/{cluster_id}")
        assert response.status_code == 200
        cluster = response.json()
        assert cluster["is_active"] is False
    
    def test_get_cluster_summary_empty(self, client: TestClient, sample_cluster_data):
        """Тест получения сводки кластера без джобов"""
        # Создаем кластер
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        cluster = response.json()
        cluster_id = cluster["id"]
        
        # Получаем сводку
        response = client.get(f"/api/clusters/{cluster_id}/summary")
        assert response.status_code == 200
        
        summary = response.json()
        assert summary["cluster_name"] == sample_cluster_data["name"]
        assert summary["total_jobs"] == 0
        assert summary["running_jobs"] == 0
        assert summary["failed_jobs"] == 0
        assert summary["finished_jobs"] == 0
        assert summary["last_update"] is None
    
    def test_get_cluster_summary_with_jobs(self, client: TestClient, cluster_repo, job_repo, test_utils):
        """Тест получения сводки кластера с джобами"""
        # Создаем кластер
        cluster = test_utils.create_cluster(cluster_repo, name="summary-cluster")
        
        # Создаем джобы с разными состояниями
        job_states = ["RUNNING", "RUNNING", "FAILED", "FINISHED"]
        for i, state in enumerate(job_states):
            test_utils.create_job_snapshot(
                job_repo,
                job_id=f"job-{i}",
                cluster_name="summary-cluster",
                job_state=state
            )
        
        # Получаем сводку
        response = client.get(f"/api/clusters/{cluster.id}/summary")
        assert response.status_code == 200
        
        summary = response.json()
        assert summary["cluster_name"] == "summary-cluster"
        assert summary["total_jobs"] == 4
        assert summary["running_jobs"] == 2
        assert summary["failed_jobs"] == 1
        assert summary["finished_jobs"] == 1
        assert summary["last_update"] is not None
    
    def test_get_active_clusters_only(self, client: TestClient, multiple_clusters_data):
        """Тест получения только активных кластеров"""
        # Создаем кластеры
        for cluster_data in multiple_clusters_data:
            response = client.post("/api/clusters", json=cluster_data)
            assert response.status_code == 200
        
        # Получаем только активные кластеры
        response = client.get("/api/clusters?active_only=true")
        assert response.status_code == 200
        
        clusters = response.json()
        # Проверяем, что все возвращенные кластеры активны
        for cluster in clusters:
            assert cluster["is_active"] is True
        
        # Проверяем количество активных кластеров
        active_count = sum(1 for c in multiple_clusters_data if c["is_active"])
        assert len(clusters) == active_count


@pytest.mark.unit
class TestClustersValidation:
    """Тесты валидации данных кластеров"""
    
    def test_create_cluster_missing_name(self, client: TestClient):
        """Тест создания кластера без имени"""
        cluster_data = {
            "url": "http://localhost:8081",
            "description": "Test cluster",
            "is_active": True
        }
        
        response = client.post("/api/clusters", json=cluster_data)
        assert response.status_code == 422
        
        error_detail = response.json()["detail"]
        assert any("name" in str(error).lower() for error in error_detail)
    
    def test_create_cluster_missing_url(self, client: TestClient):
        """Тест создания кластера без URL"""
        cluster_data = {
            "name": "test-cluster",
            "description": "Test cluster",
            "is_active": True
        }
        
        response = client.post("/api/clusters", json=cluster_data)
        assert response.status_code == 422
        
        error_detail = response.json()["detail"]
        assert any("url" in str(error).lower() for error in error_detail)
    
    def test_create_cluster_invalid_url(self, client: TestClient):
        """Тест создания кластера с некорректным URL"""
        cluster_data = {
            "name": "test-cluster",
            "url": "invalid-url",
            "description": "Test cluster",
            "is_active": True
        }
        
        response = client.post("/api/clusters", json=cluster_data)
        # Может быть 422 (валидация) или 400 (бизнес-логика)
        assert response.status_code in [400, 422]
    
    def test_create_cluster_empty_name(self, client: TestClient):
        """Тест создания кластера с пустым именем"""
        cluster_data = {
            "name": "",
            "url": "http://localhost:8081",
            "description": "Test cluster",
            "is_active": True
        }
        
        response = client.post("/api/clusters", json=cluster_data)
        assert response.status_code == 422
    
    def test_update_cluster_invalid_data(self, client: TestClient, sample_cluster_data):
        """Тест обновления кластера с некорректными данными"""
        # Создаем кластер
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        cluster = response.json()
        cluster_id = cluster["id"]
        
        # Пытаемся обновить с некорректными данными
        update_data = {
            "url": "invalid-url"
        }
        response = client.put(f"/api/clusters/{cluster_id}", json=update_data)
        assert response.status_code in [400, 422]


@pytest.mark.integration
class TestClustersIntegration:
    """Интеграционные тесты кластеров"""
    
    @pytest.mark.asyncio
    async def test_cluster_lifecycle_integration(self, async_client: AsyncClient):
        """Тест полного жизненного цикла кластера"""
        # 1. Создаем кластер
        cluster_data = {
            "name": "integration-cluster",
            "url": "http://localhost:8081",
            "description": "Integration test cluster",
            "is_active": True
        }
        
        response = await async_client.post("/api/clusters", json=cluster_data)
        assert response.status_code == 200
        cluster = response.json()
        cluster_id = cluster["id"]
        
        # 2. Получаем кластер
        response = await async_client.get(f"/api/clusters/{cluster_id}")
        assert response.status_code == 200
        retrieved_cluster = response.json()
        assert retrieved_cluster["name"] == cluster_data["name"]
        
        # 3. Обновляем кластер
        update_data = {"description": "Updated description"}
        response = await async_client.put(f"/api/clusters/{cluster_id}", json=update_data)
        assert response.status_code == 200
        
        # 4. Получаем сводку
        response = await async_client.get(f"/api/clusters/{cluster_id}/summary")
        assert response.status_code == 200
        summary = response.json()
        assert summary["cluster_name"] == cluster_data["name"]
        
        # 5. Деактивируем кластер
        response = await async_client.post(f"/api/clusters/{cluster_id}/deactivate")
        assert response.status_code == 200
        
        # 6. Активируем кластер
        response = await async_client.post(f"/api/clusters/{cluster_id}/activate")
        assert response.status_code == 200
        
        # 7. Удаляем кластер
        response = await async_client.delete(f"/api/clusters/{cluster_id}")
        assert response.status_code == 200
        
        # 8. Проверяем, что кластер удален
        response = await async_client.get(f"/api/clusters/{cluster_id}")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_multiple_clusters_management(self, async_client: AsyncClient):
        """Тест управления множественными кластерами"""
        cluster_ids = []
        
        # Создаем несколько кластеров
        for i in range(3):
            cluster_data = {
                "name": f"multi-cluster-{i}",
                "url": f"http://localhost:808{i}",
                "description": f"Multi cluster {i}",
                "is_active": i % 2 == 0  # Чередуем активные и неактивные
            }
            
            response = await async_client.post("/api/clusters", json=cluster_data)
            assert response.status_code == 200
            cluster = response.json()
            cluster_ids.append(cluster["id"])
        
        # Получаем все кластеры
        response = await async_client.get("/api/clusters")
        assert response.status_code == 200
        clusters = response.json()
        assert len(clusters) == 3
        
        # Получаем только активные кластеры
        response = await async_client.get("/api/clusters?active_only=true")
        assert response.status_code == 200
        active_clusters = response.json()
        assert len(active_clusters) == 2  # Только четные индексы активны
        
        # Удаляем все кластеры
        for cluster_id in cluster_ids:
            response = await async_client.delete(f"/api/clusters/{cluster_id}")
            assert response.status_code == 200


@pytest.mark.slow
class TestClustersPerformance:
    """Тесты производительности кластеров"""
    
    def test_create_many_clusters_performance(self, client: TestClient):
        """Тест производительности создания многих кластеров"""
        import time
        
        cluster_ids = []
        start_time = time.time()
        
        # Создаем 50 кластеров
        for i in range(50):
            cluster_data = {
                "name": f"perf-cluster-{i}",
                "url": f"http://localhost:808{i % 10}",
                "description": f"Performance cluster {i}",
                "is_active": True
            }
            
            response = client.post("/api/clusters", json=cluster_data)
            assert response.status_code == 200
            cluster = response.json()
            cluster_ids.append(cluster["id"])
        
        end_time = time.time()
        creation_time = end_time - start_time
        
        # Проверяем, что создание выполнилось достаточно быстро
        assert creation_time < 10.0  # Должно выполниться менее чем за 10 секунд
        
        # Получаем все кластеры
        start_time = time.time()
        response = client.get("/api/clusters")
        end_time = time.time()
        
        assert response.status_code == 200
        clusters = response.json()
        assert len(clusters) == 50
        
        # Проверяем время получения списка
        retrieval_time = end_time - start_time
        assert retrieval_time < 2.0  # Должно выполниться менее чем за 2 секунды
        
        # Очищаем данные
        for cluster_id in cluster_ids:
            client.delete(f"/api/clusters/{cluster_id}")
    
    def test_cluster_operations_performance(self, client: TestClient, sample_cluster_data):
        """Тест производительности операций с кластерами"""
        import time
        
        # Создаем кластер
        response = client.post("/api/clusters", json=sample_cluster_data)
        assert response.status_code == 200
        cluster = response.json()
        cluster_id = cluster["id"]
        
        # Тестируем получение кластера
        start_time = time.time()
        response = client.get(f"/api/clusters/{cluster_id}")
        end_time = time.time()
        
        assert response.status_code == 200
        get_time = end_time - start_time
        assert get_time < 0.5  # Должно выполниться менее чем за 0.5 секунды
        
        # Тестируем обновление кластера
        update_data = {"description": "Updated description"}
        start_time = time.time()
        response = client.put(f"/api/clusters/{cluster_id}", json=update_data)
        end_time = time.time()
        
        assert response.status_code == 200
        update_time = end_time - start_time
        assert update_time < 0.5  # Должно выполниться менее чем за 0.5 секунды
        
        # Тестируем получение сводки
        start_time = time.time()
        response = client.get(f"/api/clusters/{cluster_id}/summary")
        end_time = time.time()
        
        assert response.status_code == 200
        summary_time = end_time - start_time
        assert summary_time < 1.0  # Должно выполниться менее чем за 1 секунду
        
        # Удаляем кластер
        client.delete(f"/api/clusters/{cluster_id}")
