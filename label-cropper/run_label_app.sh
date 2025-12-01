#!/bin/bash
# Activate virtual environment and run the Label Generator app

# Absolute path to your virtual environment
VENV_PATH="/home/aatman/Documents/e-com-application/label-cropper/venv"

# Absolute path to your UI Python file
APP_PATH="/home/aatman/Documents/e-com-application/label-cropper/label_app_ui_dark_2.py"

# Activate virtual env
source "$VENV_PATH/bin/activate"

# Run the app
python3 "$APP_PATH"
