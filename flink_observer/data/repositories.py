from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from flink_observer.data.models import FlinkCluster, JobSnapshot


class JobRepository:
    """
    A repository for managing job snapshots in a database.

    This class provides methods to upsert, query, and manage job snapshots
    in the database. It allows interaction with the database for job-related
    functionalities, such as tracking job states, fetching job statistics,
    and cleaning up old snapshots.

    :ivar db: Database session used for performing queries and operations.
    :type db: Session
    """
    def __init__(self, db: Session):
        self.db = db

    def upsert_snapshot(self, job_data: Dict[str, Any]) -> JobSnapshot:
        job_id = job_data.get('job_id')
        cluster_name = job_data.get('cluster_name')
        
        if not job_id or not cluster_name:
            raise ValueError("job_id and cluster_name are required")
        
        existing_snapshot = self.db.query(JobSnapshot).filter(
            JobSnapshot.job_id == job_id,
            JobSnapshot.cluster_name == cluster_name
        ).first()
        
        if existing_snapshot:
            for key, value in job_data.items():
                if hasattr(existing_snapshot, key):
                    setattr(existing_snapshot, key, value)
            
            existing_snapshot.snapshot_time = datetime.now()
            
            self.db.commit()
            self.db.refresh(existing_snapshot)
            return existing_snapshot
        else:
            snapshot = JobSnapshot(**job_data)
            self.db.add(snapshot)
            self.db.commit()
            self.db.refresh(snapshot)
            return snapshot

    def get_snapshot(self, job_id: str, cluster_name: str) -> Optional[JobSnapshot]:
        return self.db.query(JobSnapshot).filter(
            JobSnapshot.job_id == job_id,
            JobSnapshot.cluster_name == cluster_name
        ).first()

    def get_all_snapshots(self, cluster_name: str = None) -> List[JobSnapshot]:
        query = self.db.query(JobSnapshot)
        
        if cluster_name:
            query = query.filter(JobSnapshot.cluster_name == cluster_name)
        
        return query.order_by(desc(JobSnapshot.snapshot_time)).all()

    def get_jobs_by_state(self, state: str, cluster_name: str = None) -> List[JobSnapshot]:
        query = self.db.query(JobSnapshot).filter(JobSnapshot.job_state == state)
        
        if cluster_name:
            query = query.filter(JobSnapshot.cluster_name == cluster_name)
        
        return query.all()

    def get_running_jobs(self, cluster_name: str = None) -> List[JobSnapshot]:
        return self.get_jobs_by_state("RUNNING", cluster_name)

    def get_failed_jobs(self, cluster_name: str = None) -> List[JobSnapshot]:
        return self.get_jobs_by_state("FAILED", cluster_name)

    def get_finished_jobs(self, cluster_name: str = None) -> List[JobSnapshot]:
        return self.get_jobs_by_state("FINISHED", cluster_name)

    def get_recently_updated_jobs(self, hours: int = 1, cluster_name: str = None) -> List[JobSnapshot]:
        since = datetime.now() - timedelta(hours=hours)
        query = self.db.query(JobSnapshot).filter(JobSnapshot.snapshot_time >= since)
        
        if cluster_name:
            query = query.filter(JobSnapshot.cluster_name == cluster_name)
        
        return query.order_by(desc(JobSnapshot.snapshot_time)).all()

    def get_long_running_jobs(self, hours: int = 24, cluster_name: str = None) -> List[JobSnapshot]:
        query = self.db.query(JobSnapshot).filter(
            JobSnapshot.job_state == "RUNNING",
            JobSnapshot.job_duration > (hours * 3600 * 1000)  # в миллисекундах
        )
        
        if cluster_name:
            query = query.filter(JobSnapshot.cluster_name == cluster_name)
        
        return query.order_by(desc(JobSnapshot.job_duration)).all()

    def get_jobs_statistics(self, cluster_name: str = None) -> Dict[str, Any]:
        query = self.db.query(JobSnapshot)
        
        if cluster_name:
            query = query.filter(JobSnapshot.cluster_name == cluster_name)
        
        snapshots = query.all()
        
        stats = {
            "total_jobs": len(snapshots),
            "states": {},
            "clusters": {},
            "job_types": {}
        }
        
        for snapshot in snapshots:
            state = snapshot.job_state
            stats["states"][state] = stats["states"].get(state, 0) + 1
            
            cluster = snapshot.cluster_name
            stats["clusters"][cluster] = stats["clusters"].get(cluster, 0) + 1
            
            job_type = snapshot.job_type or "Unknown"
            stats["job_types"][job_type] = stats["job_types"].get(job_type, 0) + 1
        
        return stats

    def get_cluster_summary(self, cluster_name: str) -> Dict[str, Any]:
        snapshots = self.get_all_snapshots(cluster_name)
        
        if not snapshots:
            return {
                "cluster_name": cluster_name,
                "total_jobs": 0,
                "running_jobs": 0,
                "failed_jobs": 0,
                "finished_jobs": 0,
                "last_update": None
            }
        
        running_count = len([s for s in snapshots if s.job_state == "RUNNING"])
        failed_count = len([s for s in snapshots if s.job_state == "FAILED"])
        finished_count = len([s for s in snapshots if s.job_state == "FINISHED"])
        
        return {
            "cluster_name": cluster_name,
            "total_jobs": len(snapshots),
            "running_jobs": running_count,
            "failed_jobs": failed_count,
            "finished_jobs": finished_count,
            "last_update": max(s.snapshot_time for s in snapshots)
        }

    def delete_snapshot(self, job_id: str, cluster_name: str) -> bool:
        snapshot = self.get_snapshot(job_id, cluster_name)
        if not snapshot:
            return False
        
        self.db.delete(snapshot)
        self.db.commit()
        return True

    def cleanup_old_snapshots(self, hours_to_keep: int = 168) -> int:
        cutoff_time = datetime.now() - timedelta(hours=hours_to_keep)
        
        deleted_count = self.db.query(JobSnapshot).filter(
            JobSnapshot.snapshot_time < cutoff_time
        ).delete()
        
        self.db.commit()
        return deleted_count

    def find_jobs_by_name_pattern(self, pattern: str, cluster_name: str = None) -> List[JobSnapshot]:
        query = self.db.query(JobSnapshot).filter(
            JobSnapshot.job_name.ilike(f"%{pattern}%")
        )
        
        if cluster_name:
            query = query.filter(JobSnapshot.cluster_name == cluster_name)
        
        return query.all()


class ClusterRepository:
    """
    Repository for managing FlinkCluster entities in the database.

    This class provides methods to perform CRUD operations on FlinkCluster
    entities, as well as additional operations like activation and deactivation
    of clusters. It interacts directly with a database session to query and
    manipulate FlinkCluster data.

    :ivar db: The database session used to interact with the database.
    :type db: Session
    """
    def __init__(self, db: Session):
        self.db = db

    def get_all_active(self) -> List[FlinkCluster]:
        return self.db.query(FlinkCluster).filter(FlinkCluster.is_active == True).all()

    def get_all(self) -> List[FlinkCluster]:
        return self.db.query(FlinkCluster).all()

    def get_by_id(self, cluster_id: int) -> Optional[FlinkCluster]:
        return self.db.query(FlinkCluster).filter(FlinkCluster.id == cluster_id).first()

    def get_by_name(self, name: str) -> Optional[FlinkCluster]:
        return self.db.query(FlinkCluster).filter(FlinkCluster.name == name).first()

    def create(self, cluster_data: Dict[str, Any]) -> FlinkCluster:
        cluster = FlinkCluster(**cluster_data)
        self.db.add(cluster)
        self.db.commit()
        self.db.refresh(cluster)
        return cluster

    def update(self, cluster_id: int, update_data: Dict[str, Any]) -> Optional[FlinkCluster]:
        cluster = self.get_by_id(cluster_id)
        if not cluster:
            return None

        for key, value in update_data.items():
            if hasattr(cluster, key):
                setattr(cluster, key, value)

        self.db.commit()
        self.db.refresh(cluster)
        return cluster

    def delete(self, cluster_id: int) -> bool:
        cluster = self.get_by_id(cluster_id)
        if not cluster:
            return False

        self.db.delete(cluster)
        self.db.commit()
        return True

    def activate(self, cluster_id: int) -> bool:
        return self.update(cluster_id, {"is_active": True}) is not None

    def deactivate(self, cluster_id: int) -> bool:
        return self.update(cluster_id, {"is_active": False}) is not None
