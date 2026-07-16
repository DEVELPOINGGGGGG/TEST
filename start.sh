#!/bin/bash
# Install the missing system system libraries inside Render's host environment
playwright install-deps chromium
playwright install chromium

# Fire up the application
python app.py
