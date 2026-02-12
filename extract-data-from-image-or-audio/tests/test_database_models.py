"""Tests for templates/database_models.py"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent / "templates"))

from database_models import (
    ADMIN_EXTRACTION_LIMIT,
    DAILY_EXTRACTION_LIMIT,
    Base,
    ExtractionLog,
    ExtractionUsage,
    can_extract,
    get_daily_extraction_count,
    get_extraction_limit,
    get_extraction_stats,
    get_extraction_usage_stats,
    increment_extraction_count,
    log_extraction,
)


# =========================================================================
# 2.1  Rate Limiting — Core Functions
# =========================================================================

class TestRateLimiting:
    """Test rate limiting core functions."""

    def test_2_1_1_no_usage_record(self, db_session):
        count = get_daily_extraction_count(db_session, "new_user@test.com")
        assert count == 0

    def test_2_1_2_existing_usage(self, db_session):
        usage = ExtractionUsage(
            user_id="user@test.com",
            usage_date=date.today(),
            extraction_count=5,
        )
        db_session.add(usage)
        db_session.commit()

        count = get_daily_extraction_count(db_session, "user@test.com")
        assert count == 5

    def test_2_1_3_can_extract_under_limit(self, db_session):
        usage = ExtractionUsage(
            user_id="user@test.com",
            usage_date=date.today(),
            extraction_count=5,
        )
        db_session.add(usage)
        db_session.commit()

        allowed, remaining = can_extract(db_session, "user@test.com")
        assert allowed is True
        assert remaining == 15  # 20 - 5

    def test_2_1_4_cannot_extract_at_limit(self, db_session):
        usage = ExtractionUsage(
            user_id="user@test.com",
            usage_date=date.today(),
            extraction_count=20,
        )
        db_session.add(usage)
        db_session.commit()

        allowed, remaining = can_extract(db_session, "user@test.com")
        assert allowed is False
        assert remaining == 0

    def test_2_1_5_admin_higher_limit(self):
        limit = get_extraction_limit("admin@test.com", is_admin=True)
        assert limit == ADMIN_EXTRACTION_LIMIT
        assert limit == 100

    def test_2_1_6_regular_user_limit(self):
        limit = get_extraction_limit("user@test.com", is_admin=False)
        assert limit == DAILY_EXTRACTION_LIMIT
        assert limit == 20

    def test_2_1_7_increment_from_zero(self, db_session):
        result = increment_extraction_count(db_session, "new_user@test.com")
        assert result is True

        count = get_daily_extraction_count(db_session, "new_user@test.com")
        assert count == 1

    def test_2_1_8_increment_at_limit(self, db_session):
        usage = ExtractionUsage(
            user_id="user@test.com",
            usage_date=date.today(),
            extraction_count=20,
        )
        db_session.add(usage)
        db_session.commit()

        result = increment_extraction_count(db_session, "user@test.com")
        assert result is False

        # Count should remain at 20
        count = get_daily_extraction_count(db_session, "user@test.com")
        assert count == 20

    def test_2_1_9_increment_existing_record(self, db_session):
        usage = ExtractionUsage(
            user_id="user@test.com",
            usage_date=date.today(),
            extraction_count=10,
        )
        db_session.add(usage)
        db_session.commit()

        result = increment_extraction_count(db_session, "user@test.com")
        assert result is True

        count = get_daily_extraction_count(db_session, "user@test.com")
        assert count == 11


# =========================================================================
# 2.2  Usage Statistics
# =========================================================================

class TestUsageStatistics:
    """Test extraction usage stats retrieval."""

    def test_2_2_1_fresh_user(self, db_session):
        stats = get_extraction_usage_stats(db_session, "new_user@test.com")
        assert stats["today_count"] == 0
        assert stats["daily_limit"] == 20
        assert stats["remaining"] == 20
        assert stats["limit_reached"] is False

    def test_2_2_2_partial_usage(self, db_session):
        usage = ExtractionUsage(
            user_id="user@test.com",
            usage_date=date.today(),
            extraction_count=10,
        )
        db_session.add(usage)
        db_session.commit()

        stats = get_extraction_usage_stats(db_session, "user@test.com")
        assert stats["today_count"] == 10
        assert stats["remaining"] == 10
        assert stats["limit_reached"] is False

    def test_2_2_3_limit_reached(self, db_session):
        usage = ExtractionUsage(
            user_id="user@test.com",
            usage_date=date.today(),
            extraction_count=20,
        )
        db_session.add(usage)
        db_session.commit()

        stats = get_extraction_usage_stats(db_session, "user@test.com")
        assert stats["limit_reached"] is True
        assert stats["remaining"] == 0


# =========================================================================
# 2.3  Logging
# =========================================================================

class TestLogging:
    """Test extraction logging."""

    def test_2_3_1_successful_log(self, db_session):
        log_extraction(
            session=db_session,
            user_id="user@test.com",
            file_type="image",
            input_tokens=1000,
            output_tokens=100,
            cost_usd=0.00014,
            extraction_time_ms=2500.0,
            success=True,
        )

        logs = db_session.query(ExtractionLog).all()
        assert len(logs) == 1
        assert logs[0].user_id == "user@test.com"
        assert logs[0].file_type == "image"
        assert logs[0].success is True

    def test_2_3_2_error_message_truncation(self, db_session):
        long_error = "x" * 600
        log_extraction(
            session=db_session,
            user_id="user@test.com",
            file_type="image",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            extraction_time_ms=0.0,
            success=False,
            error_message=long_error,
        )

        logs = db_session.query(ExtractionLog).all()
        assert len(logs[0].error_message) == 500

    def test_2_3_3_null_error_message(self, db_session):
        log_extraction(
            session=db_session,
            user_id="user@test.com",
            file_type="pdf",
            input_tokens=500,
            output_tokens=50,
            cost_usd=0.00007,
            extraction_time_ms=3000.0,
            success=True,
            error_message=None,
        )

        logs = db_session.query(ExtractionLog).all()
        assert logs[0].error_message is None


# =========================================================================
# 2.4  Aggregate Statistics
# =========================================================================

class TestAggregateStatistics:
    """Test aggregate extraction stats."""

    def test_2_4_1_empty_log(self, db_session):
        stats = get_extraction_stats(db_session, days=7)
        assert stats["total_extractions"] == 0
        assert stats["total_cost_usd"] == 0.0

    def test_2_4_2_with_records(self, db_session):
        for i in range(3):
            log = ExtractionLog(
                user_id="user@test.com",
                file_type="image",
                input_tokens=1000,
                output_tokens=100,
                cost_usd=0.00014,
                extraction_time_ms=2000.0 + i * 100,
                success=True,
                created_at=datetime.utcnow(),
            )
            db_session.add(log)
        db_session.commit()

        stats = get_extraction_stats(db_session, days=7)
        assert stats["total_extractions"] == 3
        assert stats["total_input_tokens"] == 3000
        assert stats["total_output_tokens"] == 300
        assert abs(stats["total_cost_usd"] - 0.00042) < 1e-10


# =========================================================================
# 2.5  Model Definitions
# =========================================================================

class TestModelDefinitions:
    """Test SQLAlchemy model structure."""

    def test_2_5_1_extraction_usage_tablename(self):
        assert ExtractionUsage.__tablename__ == "extraction_usage"

    def test_2_5_2_extraction_log_tablename(self):
        assert ExtractionLog.__tablename__ == "extraction_log"

    def test_2_5_3_extraction_usage_columns(self, db_session):
        mapper = inspect(ExtractionUsage)
        column_names = {col.key for col in mapper.columns}
        expected = {"id", "user_id", "usage_date", "extraction_count"}
        assert expected.issubset(column_names)

    def test_2_5_4_extraction_log_columns(self, db_session):
        mapper = inspect(ExtractionLog)
        column_names = {col.key for col in mapper.columns}
        expected = {
            "id", "user_id", "file_type", "input_tokens", "output_tokens",
            "cost_usd", "extraction_time_ms", "success", "error_message", "created_at",
        }
        assert expected.issubset(column_names)


# =========================================================================
# Edge cases
# =========================================================================

class TestEdgeCases:
    """Test boundary and edge conditions."""

    def test_different_day_usage_not_counted(self, db_session):
        """Yesterday's usage should not count against today's limit."""
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        usage = ExtractionUsage(
            user_id="user@test.com",
            usage_date=yesterday,
            extraction_count=20,
        )
        db_session.add(usage)
        db_session.commit()

        count = get_daily_extraction_count(db_session, "user@test.com")
        assert count == 0  # Today's count should be 0

    def test_admin_can_extract_beyond_regular_limit(self, db_session):
        """Admin should be able to extract even when at regular user limit."""
        usage = ExtractionUsage(
            user_id="admin@test.com",
            usage_date=date.today(),
            extraction_count=25,
        )
        db_session.add(usage)
        db_session.commit()

        allowed, remaining = can_extract(db_session, "admin@test.com", is_admin=True)
        assert allowed is True
        assert remaining == 75  # 100 - 25

    def test_multiple_users_independent(self, db_session):
        """Usage for one user should not affect another."""
        usage_a = ExtractionUsage(
            user_id="user_a@test.com",
            usage_date=date.today(),
            extraction_count=20,
        )
        db_session.add(usage_a)
        db_session.commit()

        allowed, remaining = can_extract(db_session, "user_b@test.com")
        assert allowed is True
        assert remaining == 20

    def test_increment_creates_record_for_new_user(self, db_session):
        """Incrementing for a user with no record should create one."""
        result = increment_extraction_count(db_session, "brand_new@test.com")
        assert result is True

        usage = db_session.query(ExtractionUsage).filter(
            ExtractionUsage.user_id == "brand_new@test.com"
        ).first()
        assert usage is not None
        assert usage.extraction_count == 1
