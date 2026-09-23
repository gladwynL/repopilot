# Import ORM models here so Alembic autogenerate can discover them via Base.metadata.
from app.db.base import Base

__all__ = ["Base"]
