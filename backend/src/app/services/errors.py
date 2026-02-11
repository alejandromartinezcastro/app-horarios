from __future__ import annotations


class ServiceError(Exception):
    """Base class for domain/service layer failures."""


class NotFoundError(ServiceError):
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' not found")


class BadRequestError(ServiceError):
    """Raised when request data is semantically invalid for the service."""
