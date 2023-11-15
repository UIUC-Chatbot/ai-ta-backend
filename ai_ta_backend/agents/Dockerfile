# Use an official Ubuntu as a parent image
FROM ubuntu:jammy
# Set environment variables
ARG DEBIAN_FRONTEND=noninteractive
ARG TZ=America/Los_Angeles

# Install Python and other dependencies
RUN apt-get update && \
    apt-get install -y python3 python3-distutils curl git gcc python3-dev && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python get-pip.py && \
    rm get-pip.py && \
    rm -rf /var/lib/apt/lists/*

# Install R packages
# RUN R -e "install.packages(c('dplyr', 'ggplot2'), repos='http://cran.rstudio.com/')"

# Install PIP packages
COPY requirements.txt /tmp/
RUN pip install --upgrade pip && \
    # pip install virtualenv && \
    # virtualenv venv && \
    # . venv/bin/activate && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Set the working directory
WORKDIR /app
COPY . /app

# Make port 80 available to the world outside this container
# Change the port if your application uses a different port
# EXPOSE 8000

# Define environment variable (uncomment and modify as needed)
# ENV NAME=Value

# Run your application when the container launches
# Replace `app.py` with the script that runs your application
# CMD ["python3", "app.py"]

# Bake browsers into the image
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install --with-deps