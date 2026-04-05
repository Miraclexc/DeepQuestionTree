from __future__ import annotations

from typing import Any


class ApplicationError(Exception):
    """应用层基础异常。"""

    status_code = 500
    code = "application_error"

    def __init__(
        self,
        detail: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.extra = extra or {}


class NotFoundError(ApplicationError):
    status_code = 404
    code = "not_found"


class ContractError(ApplicationError):
    status_code = 400
    code = "contract_error"


class AuthError(ApplicationError):
    status_code = 401
    code = "auth_error"


class PersistenceError(ApplicationError):
    status_code = 500
    code = "persistence_error"


class ReportGenerationError(ApplicationError):
    status_code = 500
    code = "report_generation_error"


class RuntimeConflictError(ApplicationError):
    status_code = 409
    code = "runtime_conflict"
