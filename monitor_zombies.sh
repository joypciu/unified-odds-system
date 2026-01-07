#!/bin/bash
echo "=== Extended Monitoring (5 minutes) ==="
echo "Checking every 15 seconds for zombie processes..."
echo ""

for i in {1..20}; do
    timestamp=$(date +%H:%M:%S)
    zombies=$(ps aux | grep defunct | grep -v grep | wc -l)
    python_procs=$(ps aux | grep -E 'oddportal|oddsmagnet|unified' | grep python | grep -v grep | wc -l)
    
    echo "Check $i at $timestamp"
    echo "  Zombies: $zombies"
    echo "  Python processes: $python_procs"
    echo ""
    
    sleep 15
done

echo "=== Monitoring Complete ==="
