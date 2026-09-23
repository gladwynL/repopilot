import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PersistenceError(Exception):
    """The database could not complete an operation. Messages are safe to show to API clients."""

    message = "Review storage is unavailable."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


@contextmanager
def translate_db_errors(session: Session) -> Iterator[None]:
    """Roll back and replace driver errors with a safe ``PersistenceError``.

    Only the exception type is logged: driver messages can contain SQL and parameters.
    """
    try:
        yield
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("db.error type=%s", type(exc).__name__)
        raise PersistenceError() from exc
