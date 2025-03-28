import asyncio
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI

from shared.logger_setup import get_logger

logger = get_logger(__name__)


async def background_monitor(
    read_func: Callable,
    store_func: Callable,
    sensor_name: str = "sensor",
    sleep_seconds: int = 10,
):
    """Continuously read and store sensor data in the background."""
    logger.info(f"Starting background {sensor_name} monitor")
    while True:
        try:
            logger.debug(f"Reading {sensor_name}...")

            # Call the provided read function
            results = read_func()

            # Format results for logging
            results_str = (
                str(results)
                if not isinstance(results, tuple)
                else ", ".join(str(val) for val in results)
            )
            logger.info(f"Storing {sensor_name} data: {results_str}")

            # Pass results to the store function, unpacking if it's a tuple
            if isinstance(results, tuple):
                stored_reading = store_func(*results)
            else:
                stored_reading = store_func(results)

            if not stored_reading:
                logger.warning(f"{sensor_name} data stored but not verified")
        except Exception as e:
            logger.error(f"Error in background {sensor_name} monitoring: {e}")
        logger.debug(f"Sleeping for {sleep_seconds} seconds")
        await asyncio.sleep(sleep_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI, background_tasks: list[Callable] | None = None):
    running_tasks = []
    if background_tasks:
        running_tasks = [asyncio.create_task(task) for task in background_tasks]
        logger.info(f"Started {len(running_tasks)} background tasks")
    else:
        logger.info("No background tasks provided")

    yield

    # Cancel tasks on shutdown
    for task in running_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Background task cancelled")
