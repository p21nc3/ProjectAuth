import pika
import logging
import json
import time
import threading
from queue import Queue, Empty
from pika.exceptions import StreamLostError, AMQPConnectionError, ConnectionClosedByBroker


logger = logging.getLogger(__name__)


class ConnectionPool:
    """A simple connection pool for RabbitMQ connections"""
    
    def __init__(self, connection_params, pool_size=3, max_idle_time=300):
        self.connection_params = connection_params
        self.pool_size = pool_size
        self.max_idle_time = max_idle_time
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.RLock()
        self.current_connections = 0
        
        # Pre-populate the pool
        self._fill_pool()
        
        # Start pool maintenance thread
        self._maintenance_thread = threading.Thread(target=self._maintain_pool, daemon=True)
        self._maintenance_thread.start()
    
    def _create_connection(self):
        """Create a new connection and channel"""
        try:
            connection = pika.BlockingConnection(self.connection_params)
            channel = connection.channel()
            channel.basic_qos(prefetch_count=1)
            self.current_connections += 1
            return {
                'connection': connection,
                'channel': channel,
                'created_at': time.time(),
                'last_used': time.time(),
                'declared_queues': []
            }
        except Exception as e:
            logger.error(f"Failed to create connection: {e}")
            raise
    
    def _fill_pool(self):
        """Fill the pool with connections up to pool_size"""
        with self.lock:
            try:
                while not self.pool.full() and self.current_connections < self.pool_size:
                    self.pool.put(self._create_connection(), block=False)
            except Exception as e:
                logger.error(f"Error filling connection pool: {e}")
    
    def _maintain_pool(self):
        """Periodically check connections and replace stale ones"""
        while True:
            try:
                time.sleep(60)  # Check every minute
                self._check_connections()
            except Exception as e:
                logger.error(f"Error in pool maintenance: {e}")
    
    def _check_connections(self):
        """Check all connections and remove stale ones"""
        with self.lock:
            temp_queue = Queue()
            try:
                # Move all connections to temp queue
                while not self.pool.empty():
                    conn_data = self.pool.get(block=False)
                    # Check if connection is stale
                    if time.time() - conn_data['last_used'] > self.max_idle_time:
                        try:
                            conn_data['connection'].close()
                            self.current_connections -= 1
                        except Exception:
                            pass  # Already closed
                    else:
                        # Check if connection is still open
                        try:
                            if conn_data['connection'].is_open:
                                temp_queue.put(conn_data)
                            else:
                                self.current_connections -= 1
                        except Exception:
                            self.current_connections -= 1
                
                # Move back valid connections
                while not temp_queue.empty():
                    self.pool.put(temp_queue.get())
                
                # Refill pool if needed
                self._fill_pool()
            except Exception as e:
                logger.error(f"Error checking connections: {e}")
                # If something went wrong, restore connections from temp queue
                while not temp_queue.empty():
                    self.pool.put(temp_queue.get())
    
    def get_connection(self):
        """Get a connection from the pool or create a new one if pool is empty"""
        conn_data = None
        try:
            conn_data = self.pool.get(block=False)
            conn_data['last_used'] = time.time()
            return conn_data
        except Empty:
            # Create a new connection if pool is empty
            with self.lock:
                if self.current_connections < self.pool_size * 2:  # Allow up to double the connections in high demand
                    return self._create_connection()
                else:
                    # Wait for a connection to become available
                    conn_data = self.pool.get(block=True, timeout=30)
                    conn_data['last_used'] = time.time()
                    return conn_data
    
    def return_connection(self, conn_data):
        """Return a connection to the pool"""
        with self.lock:
            try:
                if conn_data['connection'].is_open:
                    conn_data['last_used'] = time.time()
                    if not self.pool.full():
                        self.pool.put(conn_data, block=False)
                    else:
                        # Pool is full, close this connection
                        conn_data['connection'].close()
                        self.current_connections -= 1
                else:
                    # Connection is closed, don't return to pool
                    self.current_connections -= 1
            except Exception as e:
                logger.error(f"Error returning connection to pool: {e}")
                try:
                    conn_data['connection'].close()
                except Exception:
                    pass
                self.current_connections -= 1


class Rabbit:

    def __init__(self, host, port, user, passwd):
        logger.info(f"Connecting to rabbitmq: {host}:{port} ({user}:{passwd})")
        self.credentials = pika.PlainCredentials(user, passwd)
        self.parameters = pika.ConnectionParameters(
            host=host, 
            port=port, 
            credentials=self.credentials,
            heartbeat=60,
            blocked_connection_timeout=300,
            connection_attempts=3,
            retry_delay=5,
            socket_timeout=10
        )
        # Create a connection pool
        self.connection_pool = ConnectionPool(self.parameters, pool_size=3)

    def queue_declare(self, conn_data, queue, durable=True):
        """Declare a queue, avoiding redundant declarations"""
        if queue not in conn_data['declared_queues']:
            conn_data['channel'].queue_declare(queue=queue, durable=durable)
            conn_data['declared_queues'].append(queue)

    #### producer of task requests ####

    def send_treq(self, queue, reply_to, correlation_id, treq):
        """Send a task request to RabbitMQ with connection pooling and retries"""
        max_retries = 3
        retry_count = 0
        backoff_factor = 1.5
        initial_wait = 1
        
        while retry_count < max_retries:
            conn_data = None
            try:
                if retry_count > 0:
                    wait_time = initial_wait * (backoff_factor ** retry_count)
                    logger.info(f"Retry attempt {retry_count}/{max_retries} for sending task request to {queue}, waiting {wait_time:.2f}s")
                    time.sleep(wait_time)
                else:
                    logger.info(f"Sending task request to {queue} (reply_to: {reply_to}, correlation_id: {correlation_id})")
                
                # Get a connection from the pool
                conn_data = self.connection_pool.get_connection()
                
                # Set up message properties
                properties = pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE,
                    reply_to=reply_to,
                    correlation_id=correlation_id
                )
                
                # Declare queue and publish message
                self.queue_declare(conn_data, queue)
                conn_data['channel'].basic_publish(
                    exchange="",
                    routing_key=queue,
                    body=json.dumps(treq),
                    properties=properties
                )
                
                logger.info(f"Successfully sent task request to {queue}")
                
                # Return connection to pool
                self.connection_pool.return_connection(conn_data)
                return {"success": True, "error": None, "data": None}
                
            except (StreamLostError, AMQPConnectionError, ConnectionClosedByBroker) as e:
                logger.error(f"Connection error while sending task request to {queue}: {e}")
                retry_count += 1
                
                # If we have a connection, don't return it to the pool
                if conn_data:
                    try:
                        conn_data['connection'].close()
                    except Exception:
                        pass
                
            except Exception as e:
                logger.error(f"Unexpected error while sending task request to {queue}: {e}")
                retry_count += 1
                
                # If we have a connection, don't return it to the pool
                if conn_data:
                    try:
                        conn_data['connection'].close()
                    except Exception:
                        pass
        
        # All retries failed
        logger.error(f"Max retries ({max_retries}) reached for sending task request to {queue}")
        return {"success": False, "error": f"Failed to send task after {max_retries} attempts", "data": None}
