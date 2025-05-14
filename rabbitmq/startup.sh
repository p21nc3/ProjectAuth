#!/bin/bash
set -eo pipefail

# RabbitMQ startup script with stability enhancements
echo "Starting RabbitMQ with stability enhancements"

# Signal handling for graceful shutdown
graceful_shutdown() {
    echo "Received shutdown signal, stopping RabbitMQ gracefully..."
    
    # Stop health check monitor if running
    if [ -n "$HEALTHCHECK_PID" ] && ps -p $HEALTHCHECK_PID > /dev/null; then
        echo "Stopping health check monitor"
        kill -TERM $HEALTHCHECK_PID 2>/dev/null || true
    fi
    
    # Stop RabbitMQ gracefully
    if [ -n "$RABBITMQ_PID" ] && ps -p $RABBITMQ_PID > /dev/null; then
        echo "Stopping RabbitMQ server"
        rabbitmqctl stop
        
        # Wait for RabbitMQ to stop
        echo "Waiting for RabbitMQ to stop gracefully..."
        timeout=60
        count=0
        while ps -p $RABBITMQ_PID > /dev/null && [ $count -lt $timeout ]; do
            sleep 1
            count=$((count + 1))
        done
        
        # If still running, force kill
        if ps -p $RABBITMQ_PID > /dev/null; then
            echo "RabbitMQ did not stop gracefully, forcing shutdown"
            kill -9 $RABBITMQ_PID
        else
            echo "RabbitMQ stopped gracefully"
        fi
    fi
    
    exit 0
}

# Set up signal handlers
trap graceful_shutdown SIGTERM SIGINT

# Set TCP keepalive settings (if not set via sysctls in docker-compose)
echo "Setting kernel parameters for TCP stability"
sysctl -w net.ipv4.tcp_keepalive_time=600 || echo "WARNING: Failed to set tcp_keepalive_time"
sysctl -w net.ipv4.tcp_keepalive_intvl=60 || echo "WARNING: Failed to set tcp_keepalive_intvl"
sysctl -w net.ipv4.tcp_keepalive_probes=10 || echo "WARNING: Failed to set tcp_keepalive_probes"
sysctl -w net.core.somaxconn=4096 || echo "WARNING: Failed to set somaxconn"

# Ensure data directory permissions are correct
if [ -d "/var/lib/rabbitmq/mnesia" ]; then
    echo "Setting permissions on mnesia directory"
    chown -R rabbitmq:rabbitmq /var/lib/rabbitmq/mnesia
fi

# Start RabbitMQ server in the background
echo "Starting RabbitMQ server"
rabbitmq-server &
RABBITMQ_PID=$!

# Wait for RabbitMQ to be fully started
echo "Waiting for RabbitMQ to start"
timeout=120
count=0
while ! rabbitmqctl status > /dev/null 2>&1 && [ $count -lt $timeout ]; do
    echo "Waiting for RabbitMQ to become available... ($count/$timeout)"
    sleep 5
    count=$((count + 5))
done

if [ $count -ge $timeout ]; then
    echo "ERROR: RabbitMQ failed to start within timeout period"
    exit 1
fi

echo "RabbitMQ started successfully"

# Set up RabbitMQ policies for message TTL and queue limits
echo "Setting up RabbitMQ policies"

# First create the dead letter exchange using the CLI
rabbitmqctl set_parameter exchange-type "direct" '{"name":"dlx"}' || echo "WARNING: Failed to create dead letter exchange"

# Create a policy for message TTL (24 hours)
rabbitmqctl set_policy TTL ".*" '{"message-ttl":86400000}' --apply-to queues || echo "WARNING: Failed to set TTL policy"

# Create a policy to limit queue size
rabbitmqctl set_policy MaxLength ".*" '{"max-length":1000000, "max-length-bytes":1073741824}' --apply-to queues || echo "WARNING: Failed to set MaxLength policy"

# Create a policy for dead-letter exchange
rabbitmqctl set_policy DLX ".*" '{"dead-letter-exchange":"dlx"}' --apply-to queues || echo "WARNING: Failed to set DLX policy"

# Additional configuration for high availability 
echo "Setting up high availability policies"
# These need to be uncommented when running in a cluster
# rabbitmqctl set_policy HA ".*" '{"ha-mode":"all"}' --priority 1 --apply-to queues || echo "WARNING: Failed to set HA policy"

# Start the health check in the background
echo "Starting health check monitor"
/usr/local/bin/healthcheck.sh &
HEALTHCHECK_PID=$!

# Keep the container running by waiting for the RabbitMQ process
echo "RabbitMQ setup complete, monitoring process"
wait $RABBITMQ_PID 
