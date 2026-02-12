"""
Database Models Template for AI Extraction Pipeline

This template provides rate limiting models and functions.
Integrate these into your existing database module.
"""

from datetime import date
from sqlalchemy import Column, Integer, String, Date, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime

# If you have an existing Base, import it instead
Base = declarative_base()

# =============================================================================
# CONFIGURATION
# =============================================================================

DAILY_EXTRACTION_LIMIT = 20   # Regular users
ADMIN_EXTRACTION_LIMIT = 100  # Admin users


# =============================================================================
# MODELS
# =============================================================================

class ExtractionUsage(Base):
    """Track daily AI extraction usage per user for rate limiting."""
    __tablename__ = "extraction_usage"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(254), nullable=False, index=True)
    usage_date = Column(Date, nullable=False, default=date.today)
    extraction_count = Column(Integer, default=0)


class ExtractionLog(Base):
    """Optional: Log extraction metrics for observability."""
    __tablename__ = "extraction_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(254), nullable=False, index=True)
    file_type = Column(String(20))  # "image", "pdf", "audio"
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    cost_usd = Column(Float)
    extraction_time_ms = Column(Float)
    success = Column(Boolean, default=True)
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# RATE LIMITING FUNCTIONS
# =============================================================================

def get_daily_extraction_count(session, user_id: str) -> int:
    """Get today's AI extraction count for a user."""
    usage = session.query(ExtractionUsage).filter(
        ExtractionUsage.user_id == user_id,
        ExtractionUsage.usage_date == date.today()
    ).first()
    return usage.extraction_count if usage else 0


def get_extraction_limit(user_id: str, is_admin: bool = False) -> int:
    """Get extraction limit for user. Override this for custom logic."""
    if is_admin:
        return ADMIN_EXTRACTION_LIMIT
    return DAILY_EXTRACTION_LIMIT


def can_extract(session, user_id: str, is_admin: bool = False) -> tuple[bool, int]:
    """Check if extraction is allowed. Returns (allowed, remaining_count)."""
    count = get_daily_extraction_count(session, user_id)
    limit = get_extraction_limit(user_id, is_admin)
    remaining = limit - count
    return remaining > 0, max(0, remaining)


def increment_extraction_count(session, user_id: str, is_admin: bool = False) -> bool:
    """Increment extraction count. Returns True if successful (under limit)."""
    limit = get_extraction_limit(user_id, is_admin)

    usage = session.query(ExtractionUsage).filter(
        ExtractionUsage.user_id == user_id,
        ExtractionUsage.usage_date == date.today()
    ).first()

    if not usage:
        usage = ExtractionUsage(
            user_id=user_id,
            usage_date=date.today(),
            extraction_count=0
        )
        session.add(usage)

    if usage.extraction_count >= limit:
        return False

    usage.extraction_count += 1
    session.commit()
    return True


def get_extraction_usage_stats(session, user_id: str, is_admin: bool = False) -> dict:
    """Get extraction usage statistics for user."""
    count = get_daily_extraction_count(session, user_id)
    limit = get_extraction_limit(user_id, is_admin)
    return {
        "today_count": count,
        "daily_limit": limit,
        "remaining": max(0, limit - count),
        "limit_reached": count >= limit
    }


# =============================================================================
# LOGGING FUNCTIONS (Optional)
# =============================================================================

def log_extraction(
    session,
    user_id: str,
    file_type: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    extraction_time_ms: float,
    success: bool = True,
    error_message: str = None
):
    """Log an extraction for observability. Non-blocking recommended."""
    log_entry = ExtractionLog(
        user_id=user_id,
        file_type=file_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        extraction_time_ms=extraction_time_ms,
        success=success,
        error_message=error_message[:500] if error_message else None
    )
    session.add(log_entry)
    session.commit()


def get_extraction_stats(session, days: int = 7) -> dict:
    """Get aggregate extraction statistics."""
    from sqlalchemy import func
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)

    stats = session.query(
        func.count(ExtractionLog.id).label('total'),
        func.sum(ExtractionLog.input_tokens).label('input_tokens'),
        func.sum(ExtractionLog.output_tokens).label('output_tokens'),
        func.sum(ExtractionLog.cost_usd).label('total_cost'),
        func.avg(ExtractionLog.extraction_time_ms).label('avg_time')
    ).filter(
        ExtractionLog.created_at >= cutoff
    ).first()

    return {
        "total_extractions": stats.total or 0,
        "total_input_tokens": stats.input_tokens or 0,
        "total_output_tokens": stats.output_tokens or 0,
        "total_cost_usd": float(stats.total_cost or 0),
        "avg_extraction_time_ms": float(stats.avg_time or 0)
    }
