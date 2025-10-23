from typing import Optional
from openstack.connection import Connection
import structlog


def connect_to_openstack(
    cloud_name: str, timeout: int = 10, retries: int = 3
) -> Connection:
    logger = structlog.get_logger(__name__).bind(
        cloud=cloud_name,
        max_retries=retries,
    )
    try:
        logger.info(
            "Attempting to connect to openstack cloud",
            timeout=timeout,
        )
        cloud_connection = Connection(cloud=cloud_name, api_timeout=timeout)
        cloud_connection.authorize()
        logger.info(
            "Connection to Openstack",
            status="success",
            user_id=cloud_connection.current_user_id,
            project_id=cloud_connection.current_project_id,
        )
        return cloud_connection
    except Exception as e:
        logger.error(
            "Connection to Openstack",
            status="failed",
            reason=str(e),
        )
        if "timed out" in str(e).lower() and retries > 0:
            connect_to_openstack(cloud_name=cloud_name, retries=retries - 1)
        if retries == 0:
            raise
