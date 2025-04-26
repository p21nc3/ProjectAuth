import pika
import logging
import json
import time
import threading
import multiprocessing
import ssl
import requests
import gc
from pika.exceptions import StreamLostError, AMQPConnectionError, ConnectionClosedByBroker
from modules.analyzers import ANALYZER


logger = logging.getLogger(__name__)


class RabbitHelper:


    def __init__(
        self, admin_user: str, admin_password: str,
        rabbit_host: str, rabbit_port: int, rabbit_tls: str, rabbit_queue: str, brain_url: str
    ):
        logger.info(f"Connecting to rabbitmq: {admin_user}:{admin_password}@{rabbit_host}:{rabbit_port} (tls={rabbit_tls})")
        logger.info(f"Connecting to queue: {rabbit_queue}")
        logger.info(f"Connecting to brain: {admin_user}:{admin_password}@{brain_url}")

        # brain credentials
        self.brain_url = brain_url
        self.brain_user = admin_user
        self.brain_password = admin_password

        # rabbit credentials
        self.credentials = pika.PlainCredentials(admin_user, admin_password)
        
        # Connection parameters
        connection_params = {
            'host': rabbit_host,
            'port': rabbit_port,
            'credentials': self.credentials,
            'heartbeat': 60,
            'blocked_connection_timeout': 300,
            'connection_attempts': 5,
            'retry_delay': 5,
            'socket_timeout': 10
        }
        
        if rabbit_tls == "1": # tls
            ctx = ssl.SSLContext()
            ctx.verify_mode = ssl.CERT_REQUIRED
            ctx.check_hostname = True
            ctx.load_default_certs()
            connection_params['ssl_options'] = pika.SSLOptions(ctx)
            
        self.parameters = pika.ConnectionParameters(**connection_params)
        
        # Queue configuration
        self.queue = rabbit_queue
        self.analysis = rabbit_queue.replace("_treq", "")
        
        # Thread-safe management of connection
        self.connection_lock = threading.RLock()
        self.connection = None
        self.channel = None
        
        # Connection state
        self.should_reconnect = False
        self.was_consuming = False
        
        # Connect with retry logic
        self.connect_with_retry()
        
        # Start consumer thread
        self.consumer_thread = threading.Thread(target=self._consume_loop, daemon=True)
        self.consumer_thread.start()


    def connect_with_retry(self, max_retries=5):
        """Establish connection with retry logic"""
        retry_count = 0
        backoff_factor = 1.5
        initial_wait = 1
        
        with self.connection_lock:
            while retry_count < max_retries:
                try:
                    if retry_count > 0:
                        logger.info(f"Reconnection attempt {retry_count}/{max_retries} to RabbitMQ")
                    
                    # Close previous connection if exists
                    if self.connection and self.connection.is_open:
                        try:
                            self.connection.close()
                        except Exception:
                            pass
                    
                    self.connection = pika.BlockingConnection(self.parameters)
                    self.channel = self.connection.channel()
                    self.channel.basic_qos(prefetch_count=1)  # only fetch one message at a time
                    
                    # Queue setup
                    self.channel.queue_declare(queue=self.queue, durable=True)
                    
                    logger.info("Successfully connected to RabbitMQ")
                    self.should_reconnect = False
                    return True
                    
                except (StreamLostError, AMQPConnectionError, ConnectionClosedByBroker) as e:
                    retry_count += 1
                    wait_time = initial_wait * (backoff_factor ** retry_count)
                    
                    logger.warning(f"Failed to connect to RabbitMQ (attempt {retry_count}/{max_retries}): {e}")
                    
                    if retry_count < max_retries:
                        logger.info(f"Waiting {wait_time:.2f} seconds before next connection attempt")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Maximum connection attempts reached ({max_retries})")
                        self.should_reconnect = True
                        raise ConnectionError(f"Failed to connect to RabbitMQ after {max_retries} attempts: {e}")


    def _consume_loop(self):
        """Main consumption loop that handles reconnections"""
        while True:
            try:
                # Check if we need to reconnect
                if self.should_reconnect:
                    self.connect_with_retry()
                
                # Start consuming
                with self.connection_lock:
                    if self.channel and self.connection and self.connection.is_open:
                        try:
                            self.channel.basic_consume(
                                queue=self.queue, 
                                on_message_callback=self.on_message_callback
                            )
                            self.was_consuming = True
                            logger.info(f"Started consuming from queue: {self.queue}")
                            self.channel.start_consuming()
                        except (StreamLostError, AMQPConnectionError, ConnectionClosedByBroker) as e:
                            logger.error(f"Connection error while consuming: {e}")
                            self.should_reconnect = True
                            if self.channel and self.channel.is_open:
                                try:
                                    self.channel.stop_consuming()
                                except Exception:
                                    pass
                            self.was_consuming = False
                            time.sleep(5)  # Wait before reconnecting
            except Exception as e:
                logger.error(f"Unexpected error in consume loop: {e}")
                self.should_reconnect = True
                time.sleep(5)
            finally:
                # Force garbage collection to avoid memory leaks
                gc.collect()


    def on_message_callback(self, channel, method, properties, body):
        logger.info(f"Received message on queue: {self.queue}")
        t = threading.Thread(target=self.analyzer_executor, args=(channel, method, properties, body))
        t.daemon = True
        t.start()


    def analyzer_executor(self, channel, method, properties, body):
        logger.info(f"Executing message on queue: {self.queue}")

        tres = json.loads(body)

        tres["task_config"]["task_state"] = "REQUEST_RECEIVED"
        tres["task_config"]["task_timestamp_request_received"] = time.time()

        # Set resource limits for multiprocessing to avoid memory issues
        import resource
        # Limit the process to 8GB virtual memory (includes swap)
        resource.setrlimit(resource.RLIMIT_AS, (8 * 1024 * 1024 * 1024, 10 * 1024 * 1024 * 1024))

        # Use a more robust method with proper process isolation
        pool = multiprocessing.Pool(processes=1, maxtasksperchild=1)
        workers = pool.apply_async(self.analyzer_process, args=(self.analysis, tres["domain"], tres[f"{self.analysis}_config"]))

        try:
            # Reduce timeout to avoid long-running processes that may cause memory issues
            tres[f"{self.analysis}_result"] = workers.get(timeout=60*60*2) # 2 hours
            logger.info(f"Process finished executing message on queue: {self.queue}")
        except multiprocessing.TimeoutError:
            logger.error(f"Process timeout executing message on queue: {self.queue}")
            tres[f"{self.analysis}_result"] = {"exception": "Process timeout"}
            # Make sure we terminate the pool properly
            pool.terminate()
        except Exception as e:
            logger.error(f"Unexpected error in process execution: {e}")
            tres[f"{self.analysis}_result"] = {"exception": f"Process error: {e}"}
            pool.terminate()
        finally:
            pool.close()
            pool.join()
            # Force Python garbage collection
            gc.collect()

        tres["task_config"]["task_state"] = "RESPONSE_SENT"
        tres["task_config"]["task_timestamp_response_sent"] = time.time()

        self.reply_data_and_ack_msg(channel, method, properties, tres)


    @staticmethod
    def analyzer_process(analysis: str, domain: str, config: dict) -> dict:
        try:
            return ANALYZER[analysis](domain, config).start()
        except Exception as e:
            logger.error(f"Exception while executing analyzer process: {analysis}")
            logger.debug(e)
            return {"exception": f"{e}"}


    def reply_data_and_ack_msg(self, channel, method, properties, data):
        """Reply to the data and acknowledge the message with robust error handling"""
        logger.info(f"Reply data and acknowledge message from queue: {self.queue}")
        
        # First send the reply
        reply_success = False
        if properties.reply_to:
            max_retries = 5
            retry_count = 0
            backoff_factor = 1.5
            initial_wait = 1
            
            while retry_count < max_retries and not reply_success:
                reply_success = self.reply_data(properties.reply_to, data)
                
                if not reply_success:
                    retry_count += 1
                    wait_time = initial_wait * (backoff_factor ** retry_count)
                    
                    if retry_count < max_retries:
                        logger.warning(f"Failed to reply data, retrying in {wait_time:.2f} seconds (attempt {retry_count}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Failed to reply data after {max_retries} attempts")
        
        # Then acknowledge the message
        ack_success = False
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries and not ack_success:
            try:
                with self.connection_lock:
                    if channel.is_open:
                        channel.basic_ack(delivery_tag=method.delivery_tag)
                        ack_success = True
                        logger.info(f"Successfully acknowledged message from queue: {self.queue}")
                    else:
                        # Channel is closed, we need to reconnect
                        logger.warning("Channel is closed, reconnecting before acknowledgment")
                        self.should_reconnect = True
                        # If reply was successful but ack failed, the message will be redelivered and processed again
                        # But our system should be idempotent, so this is acceptable
                        return
            except (StreamLostError, AMQPConnectionError, ConnectionClosedByBroker) as e:
                logger.error(f"Failed to acknowledge message due to connection error: {e}")
                retry_count += 1
                
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)  # Exponential backoff
                else:
                    logger.error(f"Failed to acknowledge message after {max_retries} attempts")
                    # Mark for reconnection
                    self.should_reconnect = True
                    return
            except Exception as e:
                logger.error(f"Unexpected error during acknowledgment: {e}")
                retry_count += 1
                
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)
                else:
                    logger.error(f"Failed to acknowledge message after {max_retries} attempts due to unexpected error")
                    self.should_reconnect = True
                    return


    def reply_data(self, reply_to: str, data: dict) -> bool:
        """Send reply data to the brain service with robust error handling"""
        logger.info(f"Replying data from queue {self.queue} to: {reply_to}")
        try:
            # Log detailed information about the request (for debugging)
            full_url = f"{self.brain_url}{reply_to}"
            logger.info(f"Making PUT request to brain at URL: {full_url}")
            logger.info(f"Using credentials: {self.brain_user}:***")
            
            # Check data size for potential issues
            data_size = len(json.dumps(data))
            if data_size > 10 * 1024 * 1024:  # 10MB
                logger.warning(f"Data size is very large ({data_size / 1024 / 1024:.2f} MB), which may cause issues")
            
            # Make the request with detailed error handling
            r = requests.put(
                full_url, 
                json=data, 
                auth=(self.brain_user, self.brain_password),
                timeout=120,  # Increase timeout for large payloads
                headers={'Content-Type': 'application/json'},
                verify=False  # Disable SSL verification in case of self-signed certs
            )
            
            # Log response details
            logger.info(f"Response status: {r.status_code}")
            
            if r.status_code != 200:
                logger.warning(f"Invalid status code ({r.status_code}) while replying data to: {reply_to}")
                try:
                    # Try to log response content for debugging
                    logger.warning(f"Response content: {r.text[:500]}")
                except Exception:
                    pass
                return False
                
            logger.info(f"Successfully replied data to: {reply_to}")
            return True
            
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout while replying data to: {reply_to} - {str(e)}")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Connection error while replying data to: {reply_to} - {str(e)}")
            # Check if the brain URL is correct
            logger.warning(f"Please verify that the brain URL is correct: {self.brain_url}")
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request exception while replying data to: {reply_to} - {str(e)}")
            return False
        except Exception as e:
            logger.warning(f"Exception while replying data to: {reply_to} - {str(e)}")
            logger.debug(e, exc_info=True)  # Include full traceback
            return False
