class AppError(Exception):
    """Base exception for controlled application failures."""


class ValidationException(AppError):
    pass


class AuthorizationException(AppError):
    pass


class NotFoundException(AppError):
    pass


class ConflictException(AppError):
    pass


class ExternalServiceException(AppError):
    pass


class WorkflowException(AppError):
    pass
