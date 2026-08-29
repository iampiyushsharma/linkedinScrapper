FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./app ./app

# Create a blank .env file so slowapi/starlette doesn't crash when it can't find it
RUN touch .env

# Expose port
EXPOSE 8000

# Run the FastAPI application using Uvicorn
# Use shell form to allow parsing of the $PORT environment variable (required by Render/Heroku)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
