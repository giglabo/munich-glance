"""Background scheduler for plugin refresh."""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler() -> None:
    """Start the background scheduler."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started")


async def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped")
    _scheduler = None


def add_plugin_job(
    plugin_name: str,
    callback: Callable,
    interval_seconds: int,
    run_immediately: bool = True,
) -> str:
    """Add a plugin refresh job to the scheduler.

    Args:
        plugin_name: Unique plugin identifier
        callback: Async function to call on each refresh
        interval_seconds: Seconds between refreshes
        run_immediately: Whether to run once immediately

    Returns:
        Job ID
    """
    scheduler = get_scheduler()
    job_id = f"plugin_{plugin_name}"

    # Remove existing job if present
    existing = scheduler.get_job(job_id)
    if existing:
        existing.remove()
        logger.debug(f"Removed existing job: {job_id}")

    # Add new job
    trigger = IntervalTrigger(seconds=interval_seconds)
    scheduler.add_job(
        callback,
        trigger=trigger,
        id=job_id,
        name=f"Refresh {plugin_name}",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info(f"Added plugin job: {job_id} (every {interval_seconds}s)")

    # Run immediately if requested
    if run_immediately:
        asyncio.create_task(_run_job_now(callback, plugin_name))

    return job_id


async def _run_job_now(callback: Callable, plugin_name: str) -> None:
    """Run a job immediately in the background."""
    try:
        logger.debug(f"Running {plugin_name} immediately")
        await callback()
    except Exception as e:
        logger.error(f"Error in immediate run of {plugin_name}: {e}")


def remove_plugin_job(plugin_name: str) -> bool:
    """Remove a plugin refresh job.

    Args:
        plugin_name: Plugin identifier

    Returns:
        True if job was removed, False if not found
    """
    scheduler = get_scheduler()
    job_id = f"plugin_{plugin_name}"

    job = scheduler.get_job(job_id)
    if job:
        job.remove()
        logger.info(f"Removed plugin job: {job_id}")
        return True

    return False


def get_job_status(plugin_name: str) -> Optional[dict]:
    """Get status of a plugin job.

    Args:
        plugin_name: Plugin identifier

    Returns:
        Dict with job info or None if not found
    """
    scheduler = get_scheduler()
    job_id = f"plugin_{plugin_name}"

    job = scheduler.get_job(job_id)
    if job:
        return {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }

    return None


def list_jobs() -> list[dict]:
    """List all scheduled jobs.

    Returns:
        List of job info dicts
    """
    scheduler = get_scheduler()
    jobs = []

    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return jobs
