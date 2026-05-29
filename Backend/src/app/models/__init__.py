"""Models package — exposes :class:`Base` and registers every model.

Every ORM model in the project MUST be imported into this module.
Alembic's autogenerate walks ``Base.metadata`` to discover tables, and
SQLAlchemy only registers a mapped class once its module has been
imported. Forgetting to import a new model here is the most common
cause of autogenerate producing an empty revision.

The model imports below will look unused to linters — that is expected;
they exist for their import side effect of registering with the metadata.
"""

from app.core.database import Base
from app.models.user import User

__all__ = ["Base", "User"]
