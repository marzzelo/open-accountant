"""Domain errors used by backend services."""


class ServiceError(Exception):
    """Base class for service-layer errors."""


class ValidationError(ServiceError):
    """Raised when request data violates business rules."""


class NotFoundError(ServiceError):
    """Raised when a requested domain entity does not exist."""


class ConflictError(ServiceError):
    """Raised when an operation conflicts with existing state."""


class IntegrityError(ServiceError):
    """Raised when integrity or tamper checks fail."""


class ExternalServiceError(ServiceError):
    """Raised when an external dependency cannot be reached or parsed."""
