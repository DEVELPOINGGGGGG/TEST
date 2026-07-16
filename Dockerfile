# Use the official Microsoft Playwright image which has Python and Chromium pre-installed
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app files into the container
COPY . .

# Start the Flask server
CMD ["python", "app.py"]
