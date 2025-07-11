import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class JobMetrics:
    """
    Represents metrics related to a specific job.

    This class holds detailed information about a job's metrics, such as its
    identifier, name, state, type, and various timing and configuration details.
    It provides a convenient way to encapsulate and manage job-related data.

    :ivar job_id: Identifier of the job.
    :type job_id: Optional[str]
    :ivar name: Name of the job.
    :type name: Optional[str]
    :ivar state: State of the job.
    :type state: Optional[str]
    :ivar job_type: Type of the job.
    :type job_type: Optional[str]
    :ivar is_stoppable: Indicates whether the job can be stopped.
    :type is_stoppable: bool
    :ivar start_time: Start time of the job.
    :type start_time: Optional[int]
    :ivar end_time: End time of the job.
    :type end_time: Optional[int]
    :ivar duration: Duration of the job.
    :type duration: Optional[int]
    :ivar max_parallelism: Maximum parallelism for the job.
    :type max_parallelism: Optional[int]
    :ivar now: Current time with reference to the job.
    :type now: Optional[int]
    """
    job_id: Optional[str] = None
    name: Optional[str] = None
    state: Optional[str] = None
    job_type: Optional[str] = None
    is_stoppable: bool = False
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    duration: Optional[int] = None
    max_parallelism: Optional[int] = None
    now: Optional[int] = None

    @classmethod
    def from_job_details(cls, job_details: Dict[str, Any]) -> 'JobMetrics':
        """
        Creates an instance of the JobMetrics class using the provided job details.
        """
        if not job_details:
            return cls()

        return cls(
            job_id=job_details.get("jid"),
            name=job_details.get("name"),
            state=job_details.get("state"),
            job_type=job_details.get("job-type"),
            is_stoppable=job_details.get("isStoppable", False),
            start_time=job_details.get("start-time"),
            end_time=job_details.get("end-time"),
            duration=job_details.get("duration"),
            max_parallelism=job_details.get("maxParallelism"),
            now=job_details.get("now")
        )


class FlinkAPIClient:
    """
    Client for interacting with a Flink API.

    This class provides methods for performing HTTP requests to interact with a Flink cluster,
    including health checks, retrieving cluster overviews, managing jobs, and extracting metrics.
    It simplifies asynchronous access to the Flink REST API endpoints and provides utilities for
    handling and processing API responses.

    :ivar base_url: The base URL for the Flink REST API.
    :type base_url: str
    """
    DEFAULT_TIMEOUT = 10
    MAX_KEEPALIVE_CONNECTIONS = 10
    MAX_CONNECTIONS = 20
    SUCCESS_STATUS_CODE = 200

    HTTP_GET = "GET"
    HTTP_POST = "POST"
    HTTP_PATCH = "PATCH"

    ENDPOINT_CONFIG = "/config"
    ENDPOINT_OVERVIEW = "/overview"
    ENDPOINT_JOBS = "/jobs"

    KEY_JOBS = "jobs"

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(
            timeout=self.DEFAULT_TIMEOUT,
            limits=httpx.Limits(
                max_keepalive_connections=self.MAX_KEEPALIVE_CONNECTIONS,
                max_connections=self.MAX_CONNECTIONS
            )
        )

    async def __aenter__(self):
        """
        Handles asynchronous context management for the associated object.

        This method is designed to be used with an asynchronous context manager (i.e.,
        `async with` statement). When entering the context, it returns the associated
        object or context.
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Handles asynchronous exit and cleanup by closing the client connection.

        This method is called when exiting an asynchronous context managed by the
        class. It ensures that the underlying client connection is properly closed
        to release any resources.
        """
        await self.client.aclose()

    async def _make_request(self, method: str, endpoint: str, error_message: str,
                            json_payload: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Executes an asynchronous HTTP request using the specified method, endpoint,
        and payload, and processes the response.

        This method supports HTTP GET, POST, and PATCH methods. It constructs
        the full URL using the base URL and the endpoint provided. If the method
        is not supported, an error is raised. For successful requests, the response
        is parsed as JSON and returned. In case of an error, it logs the error
        and returns None.

        :param method: The HTTP method to use for the request (e.g., 'GET', 'POST',
            or 'PATCH').
        :param endpoint: The endpoint (relative URL) to be appended to the base URL
            for the HTTP request.
        :param error_message: The message to log when an error occurs during the
            HTTP request.
        :param json_payload: Optional; The JSON payload to be included in the
            request body for POST and PATCH methods.
        :return: The JSON-decoded response data as a dictionary if the request is
            successful, or None if an error occurs during the request.
        """
        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            if method.upper() == self.HTTP_GET:
                response = await self.client.get(url)
            elif method.upper() == self.HTTP_POST:
                response = await self.client.post(url, json=json_payload)
            elif method.upper() == self.HTTP_PATCH:
                response = await self.client.patch(url, json=json_payload)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"{error_message}: {e}")
            return None

    async def health_check(self) -> bool:
        """
        Performs an asynchronous health check by making a GET request to a specified
        endpoint and validates the status code. Logs any encountered errors.

        This method is intended to verify the health and availability of the service
        accessible at the configured base URL.

        """
        try:
            response = await self.client.get(f"{self.base_url}{self.ENDPOINT_CONFIG}")
            return response.status_code == self.SUCCESS_STATUS_CODE
        except Exception as e:
            logger.error(f"Health check failed for {self.base_url}: {e}")
            return False

    async def get_cluster_overview(self) -> Optional[Dict[str, Any]]:
        """
        Fetch the cluster overview asynchronously.

        This method sends an asynchronous HTTP GET request to retrieve an overview of
        the cluster. It utilizes the pre-defined HTTP method and endpoint constants.
        In case of a failure to fetch the data, an exception is raised with a
        well-defined error message.
        """
        return await self._make_request(self.HTTP_GET,
                                        self.ENDPOINT_OVERVIEW,
                                        "Failed to get cluster overview")

    async def get_jobs_summary(self) -> List[Dict[str, Any]]:
        """
        Retrieve a summary of jobs from the service.

        This method fetches job data from a specified endpoint and returns a summary of the
        available jobs. It makes an asynchronous HTTP GET request to the jobs endpoint
        and parses the result to extract the job details.

        """
        result = await self._make_request(self.HTTP_GET,
                                          self.ENDPOINT_JOBS,
                                          f"Failed to get jobs from {self.base_url}")
        return result.get(self.KEY_JOBS, []) if result else []

    async def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches detailed information about a specific job asynchronously.

        This method retrieves job details based on the provided job ID. It uses an
        HTTP GET request to fetch the data from the respective endpoint. If the
        request fails, an error message indicating the failure is returned.
        """
        return await self._make_request(self.HTTP_GET,
                                        f"{self.ENDPOINT_JOBS}/{job_id}",
                                        f"Failed to get job details for {job_id}")

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancels a job asynchronously by sending a PATCH request to the job endpoint.

        This method attempts to cancel the specified job by making a PATCH request to
        the appropriate endpoint. If the operation is successful, the method logs the
        success and returns `True`. Otherwise, it returns `False`.
        """
        result = await self._make_request(self.HTTP_PATCH, f"{self.ENDPOINT_JOBS}/{job_id}",
                                          f"Failed to cancel job {job_id}")
        if result is not None:
            logger.info(f"Job {job_id} cancelled successfully")
            return True
        return False

    def extract_job_metrics(self, job_details: Dict[str, Any]) -> JobMetrics:
        """
        Extracts job metrics from the provided job details.

        This method processes the given `job_details` dictionary, extracts relevant
        metrics, and returns a `JobMetrics` object. The returned `JobMetrics` object
        encapsulates various metrics and information based on the provided job
        details.

        :param job_details: A dictionary containing job details and associated
             information.
        :type job_details: Dict[str, Any]
        :return: A `JobMetrics` object created using the extracted job details.
        :rtype: JobMetrics
        """
        return JobMetrics.from_job_details(job_details)

    async def close(self):
        """
        Closes the client connection asynchronously.

        This method is used to safely close the client's connection. It ensures that
        all resources used by the connection are released properly. This method
        should be called when the connection is no longer needed.

        """
        await self.client.aclose()


if __name__ == "__main__":
    async def monitor_clusters():
        async with FlinkAPIClient("http://localhost:8081") as client:
            jobs = await client.get_jobs_summary()
            for job in jobs:
                details = await client.get_job_details(job['id'])
                print(client.extract_job_metrics(details))

    asyncio.run(monitor_clusters())
