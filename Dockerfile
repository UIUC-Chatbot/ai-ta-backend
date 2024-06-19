# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the local directory contents into the container
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Set the Python path to include the ai_ta_backend directory
ENV PYTHONPATH="${PYTHONPATH}:/usr/src/app/ai_ta_backend"

RUN echo $PYTHONPATH
RUN ls -la /usr/src/app/

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable for Gunicorn to bind to 0.0.0.0:8000
ENV GUNICORN_CMD_ARGS="--bind=0.0.0.0:8000"

# Run the application using Gunicorn with specified configuration
CMD ["gunicorn", "--workers=1", "--threads=100", "--worker-class=gthread", "ai_ta_backend.main:app", "--timeout=1800", "--bind=0.0.0.0:8000"]
