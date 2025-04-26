#!/bin/bash
#
# RabbitMQ Health Check Script
# Monitors RabbitMQ and identifies connection issues
#

# Log function with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Set variables
RABBITMQ_HOST=${RABBITMQ_HOST:-"rabbitmq"}
RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
RABBITMQ_USER=${RABBITMQ_USER:-"admin"}
RABBITMQ_PASS=${RABBITMQ_PASS:-"changeme"}
MAX_RETRIES=5
SLEEP_INTERVAL=30
LOG_FILE="/var/log/rabbitmq/health_check.log"

# Create log directory if it doesn't exist
mkdir -p $(dirname $LOG_FILE)

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Ensure we have required tools
check_required_tools() {
    for cmd in rabbitmqctl timeout grep awk; do
        if ! command_exists $cmd; then
            log_message "ERROR: Required command '$cmd' not found"
            return 1
        fi
    done
    return 0
}

# Check RabbitMQ status
check_rabbitmq() {
    log_message "Checking RabbitMQ health..."
    
    # Check if RabbitMQ is responding
    if ! timeout 10 rabbitmqctl status > /dev/null 2>&1; then
        log_message "ERROR: RabbitMQ is not responding"
        return 1
    fi
    
    # Check for connection issues
    CONNECTION_COUNT=$(rabbitmqctl list_connections | grep -c "running" || echo "0")
    log_message "RabbitMQ has $CONNECTION_COUNT active connections"
    
    # Check for blocked connections
    BLOCKED_CONNECTIONS=$(rabbitmqctl list_connections state | grep -c "blocked" || echo "0")
    if [ "$BLOCKED_CONNECTIONS" -gt 0 ]; then
        log_message "WARNING: Found $BLOCKED_CONNECTIONS blocked connections"
    fi
    
    # Check connection rates for spikes
    NEW_CONNECTIONS=$(rabbitmqctl list_connections | wc -l)
    CLOSED_CONNECTIONS=$(rabbitmqctl list_connection_channels | wc -l)
    log_message "Connection stats: New=$NEW_CONNECTIONS, Active channels=$CLOSED_CONNECTIONS"
    
    # Check for memory high watermark
    MEMORY_ALARM=$(rabbitmqctl list_alarms | grep -c "memory" || echo "0")
    if [ "$MEMORY_ALARM" -gt 0 ]; then
        log_message "WARNING: Memory alarm is active"
        # Get memory details
        MEMORY_DETAILS=$(rabbitmqctl status | grep -A 10 "memory")
        log_message "Memory details: $MEMORY_DETAILS"
        return 1
    fi
    
    # Check for disk space high watermark
    DISK_ALARM=$(rabbitmqctl list_alarms | grep -c "disk" || echo "0")
    if [ "$DISK_ALARM" -gt 0 ]; then
        log_message "WARNING: Disk alarm is active"
        # Get disk details
        DISK_DETAILS=$(rabbitmqctl status | grep -A 5 "disk_free")
        log_message "Disk details: $DISK_DETAILS"
        return 1
    fi
    
    # Check queue backlog
    QUEUE_STATS=$(rabbitmqctl list_queues name messages messages_ready messages_unacknowledged 2>/dev/null)
    HIGH_QUEUE_COUNT=$(echo "$QUEUE_STATS" | awk 'NR>1 && $2 > 10000 {print $1}' | wc -l)
    if [ "$HIGH_QUEUE_COUNT" -gt 0 ]; then
        log_message "WARNING: $HIGH_QUEUE_COUNT queues have more than 10000 messages"
        # Print queue details for high message counts
        echo "$QUEUE_STATS" | awk 'NR>1 && $2 > 10000'
    fi
    
    # Monitor for socket errors
    SOCKET_ERRORS=$(rabbitmqctl eval 'rabbit_networking:connections_local().' | grep -c "error" || echo "0")
    if [ "$SOCKET_ERRORS" -gt 0 ]; then
        log_message "WARNING: Found $SOCKET_ERRORS socket errors"
        return 1
    fi
    
    # Monitor for TCP keepalive timeouts
    TCP_TIMEOUTS=$(netstat -ant | grep $RABBITMQ_PORT | grep -c "CLOSE_WAIT" || echo "0")
    if [ "$TCP_TIMEOUTS" -gt 5 ]; then
        log_message "WARNING: Found $TCP_TIMEOUTS connections in CLOSE_WAIT state"
        return 1
    fi
    
    log_message "RabbitMQ appears to be healthy"
    return 0
}

# Function to fix common issues
fix_common_issues() {
    # Check for TCP socket issues and try to fix
    log_message "Attempting to fix common issues..."
    
    # Clear stale connections
    STALE_CONNECTIONS=$(rabbitmqctl list_connections | grep -i "10 min" | awk '{print $1}')
    if [ -n "$STALE_CONNECTIONS" ]; then
        log_message "Found stale connections, attempting to close them"
        for conn in $STALE_CONNECTIONS; do
            rabbitmqctl close_connection "$conn" "Closed by health check due to inactivity" || true
        done
    fi
    
    # Restart management agent if it's unresponsive
    if ! curl -s -u $RABBITMQ_USER:$RABBITMQ_PASS http://localhost:15672/api/overview > /dev/null; then
        log_message "Management API is unresponsive, restarting management plugin"
        rabbitmqctl eval 'application:stop(rabbitmq_management).' || true
        sleep 2
        rabbitmqctl eval 'application:start(rabbitmq_management).' || true
    fi
    
    # Check for memory pressure
    MEMORY_USED_PCT=$(rabbitmqctl status | grep -A 5 "memory" | grep "total" | awk -F',' '{print $1}' | awk -F':' '{print $2}')
    if [ "$MEMORY_USED_PCT" -gt 80 ]; then
        log_message "Memory pressure detected, forcing garbage collection"
        rabbitmqctl eval 'rabbit_gc:force_major_gc().' || true
    fi
    
    return 0
}

restart_rabbitmq() {
    log_message "Attempting to restart RabbitMQ..."
    
    if docker restart "$RABBITMQ_HOST"; then
        log_message "RabbitMQ restart initiated"
        # Wait for RabbitMQ to start up
        sleep 30
        
        # Check if restart fixed the issue
        if check_rabbitmq; then
            log_message "RabbitMQ successfully restarted and is healthy"
            return 0
        else
            log_message "RabbitMQ is still unhealthy after restart"
            return 1
        fi
    else
        log_message "Failed to restart RabbitMQ"
        return 1
    fi
}

# Handle signals properly
trap 'log_message "Received signal to terminate, exiting health check monitor"; exit 0' TERM INT

# Check for required tools
if ! check_required_tools; then
    log_message "Missing required tools, cannot continue"
    exit 1
fi

# Main loop
log_message "Starting RabbitMQ health check monitor"

while true; do
    # Redirect output to log file
    (
    if ! check_rabbitmq; then
        log_message "RabbitMQ health check failed"
        
        # Try to fix common issues first
        fix_common_issues
        
        # Check again after fixes
        sleep 10
        if ! check_rabbitmq; then
            log_message "Issues persist after attempted fixes"
            
            # Try restarting RabbitMQ as last resort
            if ! restart_rabbitmq; then
                log_message "Failed to recover RabbitMQ after restart"
                
                # Alert via email if configured
                if [ -n "$ALERT_EMAIL" ]; then
                    echo "RabbitMQ is down and restart failed. Please check the server." | \
                    mail -s "RabbitMQ Alert: Service Down" "$ALERT_EMAIL"
                fi
            fi
        else
            log_message "Issues resolved after fixes"
        fi
    fi
    ) >> $LOG_FILE 2>&1
    
    # Sleep before next check
    log_message "Sleeping for $SLEEP_INTERVAL seconds before next check"
    sleep $SLEEP_INTERVAL
done 