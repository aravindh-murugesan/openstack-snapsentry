"""Manages cloud connection with reliable retry logic"""

import time
from typing import Optional

import structlog
from keystoneauth1.exceptions.connection import ConnectTimeout
from openstack.connection import Connection
from openstack.exceptions import SDKException


class OpenstackConnectionManager:
    """Manages connection to OpenStack cloud service with retry mechanism.

    This class handles the connection to OpenStack cloud services, implementing
    connection retry logic with exponential backoff.

    Attributes:
        cloud_name (str): Name of the OpenStack cloud to connect to
        timeout (int): Connection timeout in seconds
        max_retries (int): Maximum number of connection retry attempts
        logger (structlog.BoundLogger): Structured logger instance for the class
        _connection (Optional[Connection]): Internal connection object

    Methods:
        connection: Property that returns an established connection, creating one if needed
        connect: Establishes connection to OpenStack with retry mechanism

    Raises:
        RuntimeError: When all connection attempts fail
    """

    def __init__(
        self, cloud_name: str, timeout: int = 10, max_retries: int = 3
    ) -> None:
        self.cloud_name: str = cloud_name
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.logger: structlog.BoundLogger = structlog.get_logger(__name__).bind(
            cloud_name=cloud_name
        )
        self._connection: Optional[Connection] = None

    @property
    def connection(self) -> Connection:
        """
        Gets the OpenStack connection instance.

        This property ensures a singleton connection instance is maintained.
        If no connection exists, it creates one using the connect() method.

        Returns:
            Connection: An authenticated OpenStack connection object

        Note:
            The connection is lazily initialized on first access
        """

        if self._connection is None:
            self._connection = self.connect()
        return self._connection

    def connect(self) -> Connection:
        """
        Establish and return an authorized OpenStack Connection.

        This method attempts to create and authorize an OpenStack Connection.
        It will retry on transient connection errors up to self.max_retries times.

        Returns:
                Connection: An authorized openstack.connection.Connection instance.

        Raises:
                RuntimeError: If all connection attempts fail (i.e., the cloud is
                        unreachable after self.max_retries attempts).
        """
        for attempt in range(self.max_retries):
            try:
                self.logger.info(
                    "Attempting to connect to openstack",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    timeout=self.timeout,
                )

                cloud_connection = Connection(
                    cloud=self.cloud_name, api_timeout=self.timeout
                )
                cloud_connection.authorize()

                self.logger.info(
                    "Connection to Openstack established",
                    status="success",
                    user_id=cloud_connection.current_user_id,
                    project_id=cloud_connection.current_project_id,
                )

                return cloud_connection
            except (ConnectTimeout, SDKException) as e:
                self.logger.error(
                    "Connection attempt to Openstack failed",
                    status="failed",
                    attempt=attempt + 1,
                    reason=str(e),
                )

                ## Exponential backoff for retry
                if attempt + 1 == self.max_retries:
                    continue

                wait_time = 2**attempt
                self.logger.info(
                    "Retrying to connect to Openstack",
                    wait_time=wait_time,
                    next_attempt=attempt + 2,
                )
                time.sleep(wait_time)

        raise RuntimeError(
            "OpenstackCloudUnreachable: All attempts to connect to openstack has failed. "
        )
