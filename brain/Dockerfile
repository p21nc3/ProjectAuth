FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# update and upgrade
RUN apt update
RUN apt upgrade -y

# install dependencies
RUN apt install -y python3 python3-pip curl

# install pipenv
RUN pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1

# create app directory
RUN mkdir -p /app
WORKDIR /app

# install python dependencies
ADD Pipfile .
RUN pipenv install

# copy app
COPY . .

# install build dependencies and cleanup
RUN apt install -y build-essential python3-dev && \
    pipenv install jsonschema && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Install gevent worker dependency and run gunicorn
RUN pipenv install gevent

# Run gunicorn with proper app factory invocation
CMD ["pipenv", "run", "gunicorn", "--worker-class", "gevent", "-w", "1", "-b", "0.0.0.0:5000", "--log-level", "debug", "--timeout", "180", "--log-file", "-", "--access-logfile", "-", "--capture-output", "brain.app:create_app"]
