import os
import time
import logging
import gc
import threading
import psutil
import re
from modules.helper.rabbit import RabbitHelper


# env
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "changeme")
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = os.environ.get("RABBITMQ_PORT", 5672)
RABBITMQ_TLS = os.environ.get("RABBITMQ_TLS", "0")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "landscape_analysis_treq")

# Get brain URL with validation
raw_brain_url = os.environ.get("BRAIN_URL", "http://brain:8080")
# Ensure the URL has a proper format
if not raw_brain_url.startswith(('http://', 'https://')):
    raw_brain_url = f"http://{raw_brain_url}"
# Remove trailing slash if present to avoid double slashes in requests
BRAIN_URL = raw_brain_url.rstrip('/')
# Validate port if not specified
if not re.search(r':\d+', BRAIN_URL):
    # Add default port if not in URL
    BRAIN_URL = f"{BRAIN_URL}:8080"

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng:8080")
TMP_PATH = os.environ.get("TMP_PATH", "/tmpfs")


# logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper()),
    format="%(asctime)s:%(name)s:%(levelname)s:%(message)s"
)

# Log configuration details at startup
logger.info("Worker starting with configuration:")
logger.info(f"RABBITMQ_HOST: {RABBITMQ_HOST}")
logger.info(f"RABBITMQ_PORT: {RABBITMQ_PORT}")
logger.info(f"RABBITMQ_QUEUE: {RABBITMQ_QUEUE}")
logger.info(f"BRAIN_URL: {BRAIN_URL}")
logger.info(f"LOG_LEVEL: {LOG_LEVEL}")


# Memory monitoring thread
def monitor_memory():
    """
    Monitor memory usage and perform periodic cleanup
    """
    while True:
        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            logger.info(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB ({memory_percent:.1f}%)")
            
            # Force garbage collection periodically
            collected = gc.collect()
            logger.debug(f"Garbage collected {collected} objects")
            
            # Check if memory usage is too high, restart RabbitMQ connection if needed
            if memory_percent > 80:
                logger.warning(f"Memory usage is high: {memory_percent:.1f}%. Consider restarting the worker.")
                
            time.sleep(300)  # Check every 5 minutes
        except Exception as e:
            logger.error(f"Error in memory monitoring: {e}")
            time.sleep(600)  # Wait longer if there was an error


# main
def main():
    # Start memory monitoring in background
    memory_thread = threading.Thread(target=monitor_memory, daemon=True)
    memory_thread.start()
    
    rabbit = None
    while True:
        try:
            logger.info(f"Connecting to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}")
            logger.info(f"Using Brain service at {BRAIN_URL}")
            
            rabbit = RabbitHelper(
                ADMIN_USER, ADMIN_PASS,
                RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_TLS, RABBITMQ_QUEUE, BRAIN_URL
            )
            logger.info(f"Start consuming messages on: {RABBITMQ_QUEUE}")
            rabbit.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info(f"Stop consuming messages on: {RABBITMQ_QUEUE}")
            rabbit.channel.stop_consuming()
            break
        except Exception as e:
            logger.error(f"Error consuming messages on: {RABBITMQ_QUEUE}")
            logger.debug(e)
            # Force garbage collection on error
            gc.collect()
            time.sleep(30)
    rabbit.connection.close()


if __name__ == "__main__":
    main()
