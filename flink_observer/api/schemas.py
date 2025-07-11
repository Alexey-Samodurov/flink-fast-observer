from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class ClusterBase(BaseModel):
    """Базовая модель кластера"""
    name: str = Field(..., min_length=1, max_length=100, description="Имя кластера")
    url: str = Field(..., description="URL кластера")
    description: Optional[str] = Field(None, max_length=500, description="Описание кластера")
    is_active: bool = Field(True, description="Активен ли кластер")
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL должен начинаться с http:// или https://')
        return v


class ClusterCreate(ClusterBase):
    """Модель для создания кластера"""
    pass


class ClusterUpdate(BaseModel):
    """Модель для обновления кластера"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    url: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    
    @validator('url')
    def validate_url(cls, v):
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URL должен начинаться с http:// или https://')
        return v


class ClusterResponse(ClusterBase):
    """Модель ответа кластера"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ClusterSummary(BaseModel):
    """Сводка по кластеру"""
    cluster_name: str
    total_jobs: int
    running_jobs: int
    failed_jobs: int
    finished_jobs: int
    last_update: Optional[datetime] = None


class JobSnapshotResponse(BaseModel):
    """Модель ответа снимка джоба"""
    job_id: str
    cluster_name: str
    job_name: Optional[str] = None
    job_state: str
    job_type: Optional[str] = None
    is_stoppable: bool = False
    max_parallelism: Optional[int] = None
    job_start_time: Optional[int] = None
    job_end_time: Optional[int] = None
    job_duration: Optional[int] = None
    snapshot_time: datetime
    
    class Config:
        from_attributes = True


class JobDetails(JobSnapshotResponse):
    """Детальная информация о джобе"""
    job_details: Optional[Dict[str, Any]] = None


class JobStatistics(BaseModel):
    """Статистика по джобам"""
    total_jobs: int
    states: Dict[str, int]
    clusters: Dict[str, int]
    job_types: Dict[str, int]


class CollectionResult(BaseModel):
    """Результат сбора данных"""
    cluster_name: str
    status: str
    jobs_processed: int
    jobs_found: Optional[int] = None
    error: Optional[str] = None


class CollectionSummary(BaseModel):
    """Сводка по сбору данных"""
    total_clusters: int
    active_clusters: int
    total_jobs: int
    job_states: Dict[str, int]
    cluster_distribution: Dict[str, int]
    last_collection: str


class HealthCheck(BaseModel):
    """Статус здоровья приложения"""
    status: str
    timestamp: datetime
    database_connected: bool
    active_clusters: int
    total_jobs: int


class ErrorResponse(BaseModel):
    """Модель ошибки"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class SuccessResponse(BaseModel):
    """Модель успешного ответа"""
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
