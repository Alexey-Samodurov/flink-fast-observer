import logging
from datetime import datetime
from typing import List, Dict, Any
import asyncio

from flink_observer.data.database import SessionLocal
from flink_observer.data.models import FlinkCluster
from flink_observer.data.repositories import ClusterRepository, JobRepository
from flink_observer.service.flink_client import FlinkAPIClient

logger = logging.getLogger(__name__)


class DataCollector:
    """
    Handles data collection and processing for Flink clusters and jobs.

    This class is responsible for establishing database connections, gathering data
    from Flink clusters, validating and sanitizing job data, and maintaining statistics
    for job processing. It encapsulates the processes required to interact with clusters,
    fetch job data, and save snapshots or summaries to the database. Provides asynchronous
    interfaces for smooth and efficient data interaction.

    :ivar db: Database session established for repository operations.
    :type db: SessionLocal

    :ivar cluster_repo: Repository object for managing Flink clusters in the database.
    :type cluster_repo: ClusterRepository

    :ivar job_repo: Repository object for managing job data and snapshots in the database.
    :type job_repo: JobRepository
    """

    def __init__(self):
        self.db = SessionLocal()
        self.cluster_repo = ClusterRepository(self.db)
        self.job_repo = JobRepository(self.db)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.db.rollback()
        self.db.close()

    def _validate_and_sanitize_job_data(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            sanitized_data = job_data.copy()
            
            for time_field in ['job_start_time', 'job_end_time', 'job_duration']:
                value = sanitized_data.get(time_field)
                if value is not None:
                    if isinstance(value, (int, float)):
                        if value > 9223372036854775807:
                            logger.warning(f"Value {value} for {time_field} is too large, setting to None")
                            sanitized_data[time_field] = None
                        elif value < -9223372036854775808:
                            logger.warning(f"Value {value} for {time_field} is too small, setting to None")
                            sanitized_data[time_field] = None
                        else:
                            sanitized_data[time_field] = int(value)
                    else:
                        logger.warning(f"Invalid type for {time_field}: {type(value)}, setting to None")
                        sanitized_data[time_field] = None
            
            max_parallelism = sanitized_data.get('max_parallelism')
            if max_parallelism is not None:
                if isinstance(max_parallelism, (int, float)):
                    if max_parallelism > 2147483647 or max_parallelism < -2147483648:
                        logger.warning(f"max_parallelism {max_parallelism} is out of range, setting to None")
                        sanitized_data['max_parallelism'] = None
                    else:
                        sanitized_data['max_parallelism'] = int(max_parallelism)
                else:
                    logger.warning(f"Invalid type for max_parallelism: {type(max_parallelism)}, setting to None")
                    sanitized_data['max_parallelism'] = None
            
            for string_field in ['job_name', 'job_state', 'job_type']:
                value = sanitized_data.get(string_field)
                if value is not None and not isinstance(value, str):
                    sanitized_data[string_field] = str(value)
            
            if sanitized_data.get('job_name') and len(sanitized_data['job_name']) > 255:
                sanitized_data['job_name'] = sanitized_data['job_name'][:255]
            
            if sanitized_data.get('job_state') and len(sanitized_data['job_state']) > 50:
                sanitized_data['job_state'] = sanitized_data['job_state'][:50]
            
            if sanitized_data.get('job_type') and len(sanitized_data['job_type']) > 50:
                sanitized_data['job_type'] = sanitized_data['job_type'][:50]
            
            is_stoppable = sanitized_data.get('is_stoppable')
            if is_stoppable is not None:
                sanitized_data['is_stoppable'] = bool(is_stoppable)
            
            return sanitized_data
            
        except Exception as e:
            logger.error(f"Error validating job data: {e}")
            logger.error(f"Original data: {job_data}")
            raise

    async def collect_cluster_data(self, cluster: FlinkCluster) -> Dict[str, Any]:
        logger.info(f"Collecting data from cluster: {cluster.name} ({cluster.url})")
        
        try:
            async with FlinkAPIClient(cluster.url) as client:
                # Проверяем доступность кластера
                if not await client.health_check():
                    logger.warning(f"Cluster {cluster.name} is not healthy")
                    return {
                        "cluster_name": cluster.name,
                        "status": "unhealthy",
                        "jobs_processed": 0,
                        "error": "Health check failed"
                    }

                jobs_summary = await client.get_jobs_summary()
                logger.info(f"Found {len(jobs_summary)} jobs in cluster {cluster.name}")

                processed_jobs = []
                
                for job_summary in jobs_summary:
                    job_id = job_summary.get('id')
                    if not job_id:
                        continue

                    try:
                        job_details = await client.get_job_details(job_id)
                        if job_details:
                            metrics = client.extract_job_metrics(job_details)
                            
                            snapshot_data = {
                                "cluster_name": cluster.name,
                                "job_id": metrics.job_id,
                                "job_name": metrics.name,
                                "job_state": metrics.state,
                                "job_type": metrics.job_type,
                                "is_stoppable": metrics.is_stoppable,
                                "max_parallelism": metrics.max_parallelism,
                                "job_start_time": metrics.start_time,
                                "job_end_time": metrics.end_time,
                                "job_duration": metrics.duration,
                                "job_details": job_details
                            }
                            
                            sanitized_data = self._validate_and_sanitize_job_data(snapshot_data)
                            
                            snapshot = self.job_repo.upsert_snapshot(sanitized_data)
                            processed_jobs.append(snapshot)
                            
                            logger.debug(f"Processed job {job_id} ({metrics.name}) - {metrics.state}")
                            
                    except Exception as e:
                        logger.error(f"Error processing job {job_id}: {e}")
                        continue

                logger.info(f"Cluster {cluster.name}: {len(processed_jobs)} jobs processed")

                return {
                    "cluster_name": cluster.name,
                    "status": "healthy",
                    "jobs_processed": len(processed_jobs),
                    "jobs_found": len(jobs_summary)
                }

        except Exception as e:
            logger.error(f"Error collecting data from cluster {cluster.name}: {e}")
            self.db.rollback()
            
            return {
                "cluster_name": cluster.name,
                "status": "error",
                "jobs_processed": 0,
                "error": str(e)
            }

    async def collect_all_clusters(self) -> List[Dict[str, Any]]:
        logger.info("Starting data collection from all clusters")
        
        clusters = self.cluster_repo.get_all_active()
        logger.info(f"Found {len(clusters)} active clusters")

        if not clusters:
            logger.warning("No active clusters found")
            return []

        tasks = [self.collect_cluster_data(cluster) for cluster in clusters]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        collection_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error collecting from cluster {clusters[i].name}: {result}")
                collection_results.append({
                    "cluster_name": clusters[i].name,
                    "status": "error",
                    "jobs_processed": 0,
                    "error": str(result)
                })
            else:
                collection_results.append(result)

        total_jobs = sum(r.get("jobs_processed", 0) for r in collection_results)
        healthy_clusters = sum(1 for r in collection_results if r.get("status") == "healthy")
        
        logger.info(f"Data collection completed: {healthy_clusters}/{len(clusters)} clusters healthy, {total_jobs} jobs processed")
        
        return collection_results

    def get_collection_summary(self) -> Dict[str, Any]:
        stats = self.job_repo.get_jobs_statistics()
        clusters = self.cluster_repo.get_all_active()
        
        return {
            "total_clusters": len(clusters),
            "active_clusters": len([c for c in clusters if c.is_active]),
            "total_jobs": stats.get("total_jobs", 0),
            "job_states": stats.get("states", {}),
            "cluster_distribution": stats.get("clusters", {}),
            "last_collection": datetime.now().isoformat()
        }


class ScheduledCollector:
    """
    A class for managing scheduled data collection tasks.

    This class provides functionality to start and stop a scheduler that performs
    periodic data collection using an interval. It also supports running a single
    data collection task outside the scheduler.

    :ivar interval_seconds: The interval in seconds at which the scheduler runs
        data collection tasks.
    :type interval_seconds: int
    :ivar is_running: A boolean flag indicating whether the scheduler is currently
        running.
    :type is_running: bool
    """
    def __init__(self, interval_seconds: int = 300):
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._task = None

    async def start(self):
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        self.is_running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info(f"Scheduler started with interval {self.interval_seconds} seconds")

    async def stop(self):
        if not self.is_running:
            return

        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _run_scheduler(self):
        while self.is_running:
            try:
                logger.info("Starting scheduled data collection")
                
                async with DataCollector() as collector:
                    results = await collector.collect_all_clusters()
                    
                    # Логируем результаты
                    for result in results:
                        cluster_name = result.get("cluster_name")
                        status = result.get("status")
                        jobs_count = result.get("jobs_processed", 0)
                        
                        if status == "healthy":
                            logger.info(f"✅ {cluster_name}: {jobs_count} jobs processed")
                        else:
                            error = result.get("error", "Unknown error")
                            logger.error(f"❌ {cluster_name}: {error}")

                logger.info(f"Scheduled collection completed, next run in {self.interval_seconds} seconds")
                
            except Exception as e:
                logger.error(f"Error in scheduled collection: {e}")
                await asyncio.sleep(10)
            
            await asyncio.sleep(self.interval_seconds)

    async def run_once(self):
        async with DataCollector() as collector:
            return await collector.collect_all_clusters()


if __name__ == "__main__":
    import asyncio

    async def main():
        scheduler = ScheduledCollector(interval_seconds=60)
        
        try:
            await scheduler.start()
            print("🔄 Планировщик запущен. Нажмите Ctrl+C для остановки...")
            
            while scheduler.is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Остановка планировщика...")
            await scheduler.stop()
            print("✅ Планировщик остановлен")

    asyncio.run(main())
