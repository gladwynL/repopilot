from alembic import command
from sqlalchemy import Engine, inspect, text

from tests.postgres.conftest import alembic_config

APP_TABLES = {
    "reviews",
    "review_findings",
    "review_test_suggestions",
    "evaluation_runs",
    "evaluation_case_results",
}


def test_head_schema_has_tables_and_indexes(pg_engine: Engine) -> None:
    inspector = inspect(pg_engine)

    assert set(inspector.get_table_names()) >= APP_TABLES
    with pg_engine.connect() as connection:
        index_sql = dict(
            connection.execute(
                text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'reviews'")
            ).all()
        )
    assert "WHERE is_current" in index_sql["uq_reviews_current_cache_key"]
    assert "UNIQUE" in index_sql["uq_reviews_current_cache_key"]
    assert "lower((owner)::text)" in index_sql["ix_reviews_repo_pull_created"]
    assert "created_at DESC" in index_sql["ix_reviews_created_at"]
    fks = inspector.get_foreign_keys("review_findings")
    assert fks[0]["referred_table"] == "reviews"
    assert fks[0]["options"]["ondelete"] == "CASCADE"


def test_downgrade_and_upgrade_round_trip(pg_engine: Engine, pg_url: str) -> None:
    config = alembic_config(pg_url)

    command.downgrade(config, "base")
    assert not APP_TABLES & set(inspect(pg_engine).get_table_names())

    command.upgrade(config, "head")
    assert set(inspect(pg_engine).get_table_names()) >= APP_TABLES
