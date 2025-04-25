#!/bin/bash

# Script to restart crashed worker containers and monitor memory usage

echo "Starting worker monitor..."

while true; do
  # Check for exited workers
  exited_workers=$(docker ps -a | grep "projectauth-worker" | grep "Exited" | awk '{print $1}')
  
  if [ -n "$exited_workers" ]; then
    echo "Found exited workers. Restarting..."
    
    # Print the failure reason
    for container in $exited_workers; do
      echo "Container $container exited with:"
      docker inspect $container --format='{{.State.ExitCode}}'
      docker logs --tail 50 $container
    done
    
    # Restart the compose service
    echo "Restarting worker service..."
    docker-compose restart worker
    
    echo "Workers restarted at $(date)"
  else
    echo "All workers running normally at $(date)"
  fi
  
  # Show memory usage of worker containers
  echo "Current memory usage:"
  docker stats --no-stream $(docker ps | grep "projectauth-worker" | awk '{print $1}')
  
  # Wait 5 minutes before checking again
  sleep 300
done 