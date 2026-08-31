"""Create all tables from the ORM metadata.

For a quick start without a migration tool:

    python -m scripts.init_db

For production, prefer a real migration tool (Alembic). The raw SQL in
migrations/0001_init.sql mirrors this schema if you'd rather apply SQL directly.
"""
from __future__ import annotations

from app.database import Base, engine
from app import models  # noqa: F401 - imported for side effect (registers tables)


def main() -> None:
    print("Creating tables on", engine.url)
    Base.metadata.create_all(bind=engine)
    print("Done. Tables:")
    for t in Base.metadata.sorted_tables:
        print("  -", t.name)


if __name__ == "__main__":
    main()
