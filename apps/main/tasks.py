# apps/main/tasks.py

from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def say_hello_task(name="TownLIT"):
    logger.info(f"👋 Hello from Celery! Welcome, {name}!")
    return f"Greeting sent to {name}"
