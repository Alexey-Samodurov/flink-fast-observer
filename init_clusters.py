from database import SessionLocal
from flink_observer.data.repositories import ClusterRepository

def init_clusters():
    """Инициализация кластеров в базе данных"""
    db = SessionLocal()
    
    try:
        cluster_repo = ClusterRepository(db)
        
        # Данные кластеров из docker-compose
        clusters_data = [
            {
                "name": "flink-cluster-1",
                "url": "http://localhost:8081",
                "description": "Первый Flink кластер",
                "is_active": True
            },
            {
                "name": "flink-cluster-2", 
                "url": "http://localhost:8082",
                "description": "Второй Flink кластер",
                "is_active": True
            }
        ]
        
        print("🚀 Инициализация кластеров...")
        
        for cluster_data in clusters_data:
            # Проверяем, существует ли кластер
            existing_cluster = cluster_repo.get_by_name(cluster_data["name"])
            
            if existing_cluster:
                print(f"⚠️  Кластер '{cluster_data['name']}' уже существует")
                # Можно обновить URL если изменился
                if existing_cluster.url != cluster_data["url"]:
                    cluster_repo.update(existing_cluster.id, {"url": cluster_data["url"]})
                    print(f"🔄 Обновлен URL для '{cluster_data['name']}'")
            else:
                # Создаем новый кластер
                cluster = cluster_repo.create(cluster_data)
                print(f"✅ Создан кластер '{cluster.name}' -> {cluster.url}")
        
        print("\n📊 Список всех кластеров:")
        all_clusters = cluster_repo.get_all_active()
        for cluster in all_clusters:
            status = "🟢 Активен" if cluster.is_active else "🔴 Неактивен"
            print(f"  • {cluster.name}: {cluster.url} ({status})")
        
        print(f"\n✅ Инициализация завершена! Добавлено {len(all_clusters)} кластеров")
        
    except Exception as e:
        print(f"❌ Ошибка при инициализации кластеров: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_clusters()
