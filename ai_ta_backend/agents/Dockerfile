# Use an official minimal Alpine Linux as a parent image
FROM alpine:latest
LABEL maintainer="kastanvday@gmail.com"

# APK packages
RUN apk add --no-cache python3 py3-pip R R-dev

# R packages
RUN R -e "install.packages(c('dplyr', 'ggplot2'), repos='http://cran.rstudio.com/')"

# PIP packages
RUN pip install --upgrade pip
COPY requirements.txt /tmp/
RUN export PYTHONPATH=/usr/bin/python \
 && pip install -r requirements.txt
# RUN pip install --no-cache-dir -r /tmp/requirements.txt

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