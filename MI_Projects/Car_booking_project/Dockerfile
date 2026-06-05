# base image
FROM python:3.9-slim

# set working directory
WORKDIR /app

# install system dependencies for mysqlclient
RUN apt-get update && apt-get install -y \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# copy project files
COPY . /app

# install python dependencies
RUN pip install -r requirements.txt

# expose port
EXPOSE 5000

# run the application
CMD ["python", "app.py"]
