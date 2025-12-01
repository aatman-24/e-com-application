#!/bin/bash
# Navigate to project directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Run the main Python file
python3 main.py
