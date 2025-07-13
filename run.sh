#!/bin/bash
# -*- coding: utf-8 -*-
"""
Convenient Run Script
Automatically activate virtual environment and run programs
"""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment does not exist, please run setup_venv.sh first"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if activation was successful
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: Failed to activate virtual environment"
    exit 1
fi

echo "Virtual environment activated: $VIRTUAL_ENV"

# Parse command line arguments
MODE=${1:-monitor}
shift

case $MODE in
    "monitor")
        echo "Starting continuous monitoring mode..."
        python main.py --mode monitor "$@"
        ;;
    "single")
        echo "Running single monitoring cycle..."
        python main.py --mode single "$@"
        ;;
    "dashboard")
        echo "Starting Web dashboard..."
        python main.py --mode dashboard "$@"
        ;;
    "status")
        echo "Showing status summary..."
        python main.py --mode status "$@"
        ;;
    "stats")
        echo "Showing alert statistics..."
        python main.py --mode stats "$@"
        ;;
    "analyze")
        echo "Running route analysis..."
        python main.py --mode analyze "$@"
        ;;
    "demo")
        echo "Running demo program..."
        python run_example.py "$@"
        ;;
    "shell")
        echo "Starting Python interactive environment..."
        python
        ;;
    *)
        echo "Usage: $0 {monitor|single|dashboard|status|stats|analyze|demo|shell} [arguments...]"
        echo ""
        echo "Mode descriptions:"
        echo "  monitor   - Start continuous monitoring"
        echo "  single    - Run single monitoring cycle"
        echo "  dashboard - Start Web dashboard"
        echo "  status    - Show status summary"
        echo "  stats     - Show alert statistics"
        echo "  analyze   - Run route analysis"
        echo "  demo      - Run demo program"
        echo "  shell     - Start Python interactive environment"
        echo ""
        echo "Examples:"
        echo "  $0 monitor                    # Start continuous monitoring"
        echo "  $0 dashboard --port 8080      # Start Web dashboard on port 8080"
        echo "  $0 analyze --targets 8.8.8.8  # Analyze route to 8.8.8.8"
        echo "  $0 demo                       # Run demo program"
        exit 1
        ;;
esac

# Deactivate virtual environment
deactivate
echo "Virtual environment deactivated" 