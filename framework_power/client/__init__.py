"""Self-contained Dataverse client subpackage for framework_power."""

from .dataverse_client import DataverseClient
from .auth import AutoAuthenticator, AuthCache
from .retry_helper import retry_on_metadata_error, retry_on_404, MetadataPropagationError
from . import env_config

__all__ = [
    "DataverseClient",
    "AutoAuthenticator",
    "AuthCache",
    "retry_on_metadata_error",
    "retry_on_404",
    "MetadataPropagationError",
    "env_config",
]
