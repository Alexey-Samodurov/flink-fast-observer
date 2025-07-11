from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, BigInteger
from sqlalchemy.sql import func

from flink_observer.data.database import Base


class FlinkCluster(Base):
    __tablename__ = "flink_clusters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True, nullable=False)
    url = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<FlinkCluster(name='{self.name}', url='{self.url}')>"


class JobSnapshot(Base):
    __tablename__ = "job_snapshots"

    job_id = Column(String(100), primary_key=True, nullable=False)
    cluster_name = Column(String(100), nullable=False)
    job_name = Column(String(255), nullable=True)
    job_state = Column(String(50), nullable=False, index=True)
    job_type = Column(String(50), nullable=True)
    is_stoppable = Column(Boolean, default=False)
    max_parallelism = Column(Integer, nullable=True)
    
    job_start_time = Column(BigInteger, nullable=True)
    job_end_time = Column(BigInteger, nullable=True)
    job_duration = Column(BigInteger, nullable=True)
    
    job_details = Column(JSON, nullable=True)
    
    snapshot_time = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)
    
    def __repr__(self):
        return f"<JobSnapshot(job_id='{self.job_id}', cluster='{self.cluster_name}', state='{self.job_state}')>"
    
    def is_running(self) -> bool:
        return self.job_state == "RUNNING"
    
    def is_finished(self) -> bool:
        return self.job_state in ["FINISHED", "CANCELED", "FAILED"]
    
    def is_failed(self) -> bool:
        return self.job_state == "FAILED"
    
    def get_duration_seconds(self) -> int:
        if self.job_duration:
            return self.job_duration // 1000
        return 0
