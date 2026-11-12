"""
Database connection management - async SQLAlchemy supporting PostgreSQL (asyncpg)
with automatic fallback to SQLite (aiosqlite) for standalone local development.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, text
from backend.core.config import settings
from backend.models.database import Base
import structlog

logger = structlog.get_logger(__name__)

# Connection state tracker
db_connection_state = {
    "is_connected": False,
    "dialect": "unknown",
    "fallback_active": False,
    "engine_url": settings.database_url,
    "last_error": None,
}


def _create_engine_pair(async_url: str, sync_url: str = None):
    """Create async and sync engine pair for a database URL."""
    is_sqlite = "sqlite" in async_url
    if is_sqlite:
        a_eng = create_async_engine(
            async_url,
            echo=settings.debug,
            connect_args={"check_same_thread": False},
        )
        s_url = sync_url or async_url.replace("+aiosqlite", "")
        s_eng = create_engine(
            s_url,
            echo=settings.debug,
            connect_args={"check_same_thread": False},
        )
    else:
        a_eng = create_async_engine(
            async_url,
            echo=settings.debug,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        s_url = sync_url or settings.sync_database_url
        s_eng = create_engine(
            s_url,
            echo=settings.debug,
            pool_size=5,
            max_overflow=10,
        )

    session_maker = async_sessionmaker(
        bind=a_eng,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return a_eng, s_eng, session_maker


# Initialize primary engines based on configured settings
async_engine, sync_engine, AsyncSessionLocal = _create_engine_pair(
    settings.database_url, settings.sync_database_url
)


async def get_db() -> AsyncSession:
    """FastAPI dependency yielding an active async DB session."""
    if not db_connection_state["is_connected"]:
        try:
            await init_db()
        except Exception:
            pass

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize database tables.
    Attempts primary PostgreSQL connection; if unreachable, falls back to local SQLite.
    """
    global async_engine, sync_engine, AsyncSessionLocal, db_connection_state

    # 1. Try primary database connection
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db_connection_state["is_connected"] = True
        db_connection_state["dialect"] = async_engine.dialect.name
        db_connection_state["fallback_active"] = False
        db_connection_state["engine_url"] = settings.database_url
        logger.info("Database initialized successfully", dialect=async_engine.dialect.name)
        return
    except Exception as primary_exc:
        db_connection_state["last_error"] = str(primary_exc)
        logger.warning(
            "Primary database connection failed. Falling back to local SQLite",
            configured_url=settings.database_url,
            error=str(primary_exc),
        )

    # 2. Fallback to local SQLite so development and tests never break
    try:
        fallback_async = "sqlite+aiosqlite:///./reverse_engineering.db"
        fallback_sync = "sqlite:///./reverse_engineering.db"
        async_engine, sync_engine, AsyncSessionLocal = _create_engine_pair(
            fallback_async, fallback_sync
        )
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        db_connection_state["is_connected"] = True
        db_connection_state["dialect"] = "sqlite"
        db_connection_state["fallback_active"] = True
        db_connection_state["engine_url"] = fallback_async
        logger.info(
            "Local SQLite database initialized successfully",
            database="reverse_engineering.db",
        )
    except Exception as fallback_exc:
        db_connection_state["is_connected"] = False
        db_connection_state["last_error"] = str(fallback_exc)
        logger.error("Database initialization failed completely", error=str(fallback_exc))
        raise fallback_exc


async def check_db_health() -> dict:
    """Check database liveness."""
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "dialect": db_connection_state["dialect"],
            "fallback_active": db_connection_state["fallback_active"],
        }
    except Exception as e:
        return {
            "status": "unavailable",
            "error": str(e),
            "fallback_active": db_connection_state["fallback_active"],
        }


async def close_db():
    """Close engine connections on shutdown."""
    await async_engine.dispose()
    logger.info("Database connections closed")
