from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime
from pathlib import Path

from flink_observer.data.database import get_database, engine
from flink_observer.data.models import Base
from flink_observer.data.repositories import ClusterRepository, JobRepository
from flink_observer.service.data_collector import DataCollector, ScheduledCollector
from flink_observer.api.schemas import (
    ClusterCreate, ClusterUpdate, ClusterResponse, ClusterSummary,
    JobSnapshotResponse, JobDetails, JobStatistics, CollectionSummary, HealthCheck, SuccessResponse
)

# Создаем таблицы
Base.metadata.create_all(bind=engine)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем приложение
app = FastAPI(
    title="Flink Observer API",
    description="API для мониторинга Apache Flink кластеров и джобов",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальный планировщик
scheduler = None

# Статические файлы - создаем папки если не существуют
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
(static_dir / "css").mkdir(exist_ok=True)
(static_dir / "js").mkdir(exist_ok=True)
(static_dir / "templates").mkdir(exist_ok=True)

# Создаем пустой файл .gitkeep если папки пусты
for subdir in ["css", "js", "templates"]:
    subdir_path = static_dir / subdir
    if not any(subdir_path.iterdir()):
        (subdir_path / ".gitkeep").touch()

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
async def startup_event():
    """Инициализация приложения"""
    global scheduler
    logger.info("🚀 Запуск Flink Observer API")

    # Запускаем планировщик сбора данных
    scheduler = ScheduledCollector(interval_seconds=60)  # 5 минут
    await scheduler.start()
    logger.info("📊 Планировщик сбора данных запущен")


@app.on_event("shutdown")
async def shutdown_event():
    """Остановка приложения"""
    global scheduler
    logger.info("🛑 Остановка Flink Observer API")

    if scheduler:
        await scheduler.stop()
        logger.info("📊 Планировщик сбора данных остановлен")


# === МАРШРУТЫ ДЛЯ КЛАСТЕРОВ ===

@app.get("/api/clusters", response_model=List[ClusterResponse])
async def get_clusters(
    active_only: bool = False,
    db: Session = Depends(get_database)
):
    """Получить список кластеров"""
    cluster_repo = ClusterRepository(db)

    if active_only:
        clusters = cluster_repo.get_all_active()
    else:
        clusters = cluster_repo.get_all()

    return clusters


@app.get("/api/clusters/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(cluster_id: int, db: Session = Depends(get_database)):
    """Получить кластер по ID"""
    cluster_repo = ClusterRepository(db)
    cluster = cluster_repo.get_by_id(cluster_id)

    if not cluster:
        raise HTTPException(status_code=404, detail="Кластер не найден")

    return cluster


@app.post("/api/clusters", response_model=ClusterResponse)
async def create_cluster(
    cluster_data: ClusterCreate,
    db: Session = Depends(get_database)
):
    """Создать новый кластер"""
    cluster_repo = ClusterRepository(db)

    # Проверяем уникальность имени
    existing_cluster = cluster_repo.get_by_name(cluster_data.name)
    if existing_cluster:
        raise HTTPException(
            status_code=400,
            detail=f"Кластер с именем '{cluster_data.name}' уже существует"
        )

    try:
        cluster = cluster_repo.create(cluster_data.dict())
        logger.info(f"✅ Создан новый кластер: {cluster.name}")
        return cluster
    except Exception as e:
        logger.error(f"❌ Ошибка создания кластера: {e}")
        raise HTTPException(status_code=500, detail="Ошибка создания кластера")


@app.put("/api/clusters/{cluster_id}", response_model=ClusterResponse)
async def update_cluster(
    cluster_id: int,
    cluster_data: ClusterUpdate,
    db: Session = Depends(get_database)
):
    """Обновить кластер"""
    cluster_repo = ClusterRepository(db)

    # Проверяем уникальность имени (если меняется)
    if cluster_data.name:
        existing_cluster = cluster_repo.get_by_name(cluster_data.name)
        if existing_cluster and existing_cluster.id != cluster_id:
            raise HTTPException(
                status_code=400,
                detail=f"Кластер с именем '{cluster_data.name}' уже существует"
            )

    cluster = cluster_repo.update(cluster_id, cluster_data.dict(exclude_unset=True))

    if not cluster:
        raise HTTPException(status_code=404, detail="Кластер не найден")

    logger.info(f"✅ Обновлен кластер: {cluster.name}")
    return cluster


@app.delete("/api/clusters/{cluster_id}", response_model=SuccessResponse)
async def delete_cluster(cluster_id: int, db: Session = Depends(get_database)):
    """Удалить кластер"""
    cluster_repo = ClusterRepository(db)
    cluster = cluster_repo.get_by_id(cluster_id)

    if not cluster:
        raise HTTPException(status_code=404, detail="Кластер не найден")

    cluster_name = cluster.name

    if cluster_repo.delete(cluster_id):
        logger.info(f"✅ Удален кластер: {cluster_name}")
        return SuccessResponse(message=f"Кластер '{cluster_name}' успешно удален")
    else:
        raise HTTPException(status_code=500, detail="Ошибка удаления кластера")


@app.post("/api/clusters/{cluster_id}/activate", response_model=SuccessResponse)
async def activate_cluster(cluster_id: int, db: Session = Depends(get_database)):
    """Активировать кластер"""
    cluster_repo = ClusterRepository(db)

    if cluster_repo.activate(cluster_id):
        cluster = cluster_repo.get_by_id(cluster_id)
        logger.info(f"✅ Активирован кластер: {cluster.name}")
        return SuccessResponse(message=f"Кластер '{cluster.name}' активирован")
    else:
        raise HTTPException(status_code=404, detail="Кластер не найден")


@app.post("/api/clusters/{cluster_id}/deactivate", response_model=SuccessResponse)
async def deactivate_cluster(cluster_id: int, db: Session = Depends(get_database)):
    """Деактивировать кластер"""
    cluster_repo = ClusterRepository(db)

    if cluster_repo.deactivate(cluster_id):
        cluster = cluster_repo.get_by_id(cluster_id)
        logger.info(f"✅ Деактивирован кластер: {cluster.name}")
        return SuccessResponse(message=f"Кластер '{cluster.name}' деактивирован")
    else:
        raise HTTPException(status_code=404, detail="Кластер не найден")


@app.get("/api/clusters/{cluster_id}/summary", response_model=ClusterSummary)
async def get_cluster_summary(cluster_id: int, db: Session = Depends(get_database)):
    """Получить сводку по кластеру"""
    cluster_repo = ClusterRepository(db)
    job_repo = JobRepository(db)

    cluster = cluster_repo.get_by_id(cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Кластер не найден")

    summary = job_repo.get_cluster_summary(cluster.name)
    return summary


# === МАРШРУТЫ ДЛЯ ДЖОБОВ ===

@app.get("/api/jobs", response_model=List[JobSnapshotResponse])
async def get_jobs(
    cluster_name: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_database)
):
    """Получить список джобов"""
    job_repo = JobRepository(db)

    if state:
        jobs = job_repo.get_jobs_by_state(state, cluster_name)
    else:
        jobs = job_repo.get_all_snapshots(cluster_name)

    return jobs[:limit]


@app.get("/api/jobs/{job_id}/{cluster_name}", response_model=JobDetails)
async def get_job(
    job_id: str,
    cluster_name: str,
    db: Session = Depends(get_database)
):
    """Получить детали джоба"""
    job_repo = JobRepository(db)
    job = job_repo.get_snapshot(job_id, cluster_name)

    if not job:
        raise HTTPException(status_code=404, detail="Джоб не найден")

    return job


@app.get("/api/jobs/running", response_model=List[JobSnapshotResponse])
async def get_running_jobs(
    cluster_name: Optional[str] = None,
    db: Session = Depends(get_database)
):
    """Получить запущенные джобы"""
    job_repo = JobRepository(db)
    return job_repo.get_running_jobs(cluster_name)


@app.get("/api/jobs/failed", response_model=List[JobSnapshotResponse])
async def get_failed_jobs(
    cluster_name: Optional[str] = None,
    db: Session = Depends(get_database)
):
    """Получить упавшие джобы"""
    job_repo = JobRepository(db)
    return job_repo.get_failed_jobs(cluster_name)


@app.get("/api/jobs/statistics", response_model=JobStatistics)
async def get_jobs_statistics(
    cluster_name: Optional[str] = None,
    db: Session = Depends(get_database)
):
    """Получить статистику по джобам"""
    job_repo = JobRepository(db)
    return job_repo.get_jobs_statistics(cluster_name)


@app.get("/api/jobs/search", response_model=List[JobSnapshotResponse])
async def search_jobs(
    pattern: str,
    cluster_name: Optional[str] = None,
    db: Session = Depends(get_database)
):
    """Поиск джобов по имени"""
    job_repo = JobRepository(db)
    return job_repo.find_jobs_by_name_pattern(pattern, cluster_name)


# === МАРШРУТЫ ДЛЯ СБОРА ДАННЫХ ===

@app.post("/api/collect", response_model=dict)
async def collect_data(background_tasks: BackgroundTasks):
    """Запустить сбор данных вручную"""

    async def run_collection():
        try:
            async with DataCollector() as collector:
                results = await collector.collect_all_clusters()
                logger.info(f"📊 Ручной сбор данных завершен: {len(results)} кластеров обработано")
                return results
        except Exception as e:
            logger.error(f"❌ Ошибка ручного сбора данных: {e}")
            raise

    # Запускаем в фоне
    background_tasks.add_task(run_collection)

    return {"message": "Сбор данных запущен в фоновом режиме"}


@app.get("/api/collect/summary", response_model=CollectionSummary)
async def get_collection_summary(db: Session = Depends(get_database)):
    """Получить сводку по сбору данных"""
    async with DataCollector() as collector:
        return collector.get_collection_summary()


# === СЛУЖЕБНЫЕ МАРШРУТЫ ===

@app.get("/api/health", response_model=HealthCheck)
async def health_check(db: Session = Depends(get_database)):
    """Проверка здоровья приложения"""
    try:
        # Проверяем подключение к БД
        cluster_repo = ClusterRepository(db)
        job_repo = JobRepository(db)

        clusters = cluster_repo.get_all_active()
        stats = job_repo.get_jobs_statistics()

        return HealthCheck(
            status="healthy",
            timestamp=datetime.now(),
            database_connected=True,
            active_clusters=len(clusters),
            total_jobs=stats.get("total_jobs", 0)
        )
    except Exception as e:
        logger.error(f"❌ Ошибка проверки здоровья: {e}")
        return HealthCheck(
            status="unhealthy",
            timestamp=datetime.now(),
            database_connected=False,
            active_clusters=0,
            total_jobs=0
        )


@app.post("/api/cleanup", response_model=SuccessResponse)
async def cleanup_old_data(hours: int = 168, db: Session = Depends(get_database)):
    """Очистить старые данные"""
    job_repo = JobRepository(db)

    try:
        deleted_count = job_repo.cleanup_old_snapshots(hours)
        logger.info(f"🧹 Очищено {deleted_count} старых снимков")
        return SuccessResponse(
            message=f"Удалено {deleted_count} снимков старше {hours} часов"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка очистки данных: {e}")
        raise HTTPException(status_code=500, detail="Ошибка очистки данных")


# === ВЕБ-ИНТЕРФЕЙС ===

@app.get("/", response_class=HTMLResponse)
async def get_web_interface():
    """Главная страница веб-интерфейса"""
    return FileResponse("static/templates/dashboard.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Дашборд"""
    return FileResponse("static/templates/dashboard.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
