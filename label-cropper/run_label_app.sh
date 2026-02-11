#!/bin/bash
# Activate virtual environment and run the Label Generator app

# Absolute path to your virtual environment
VENV_PATH="/home/aatman/Documents/e-com-application/label-cropper/venv"

# Absolute path to your UI Python file
# APP_PATH="/home/aatman/Documents/e-com-application/label-cropper/ui_test_v3.py"


APP_PATH="/home/aatman/Documents/e-com-application/label-cropper/label_cropper_courier_wise_ui.py"

# Activate virtual env
source "$VENV_PATH/bin/activate"

# Run the app
python3 "$APP_PATH"
