FROM python:3.10-slim AS builder

# Install compiling dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    mariadb-client \
    postgresql-client \
    python3-dev libpq-dev gcc \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Create the virtual environment
RUN python -m venv /opt/venv

# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements file
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


# Use the official Python image from the Docker Hub for production
FROM python:3.10-slim AS prod

# Install dumb-init, client tools and mongodb-database-tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    dumb-init \
    mariadb-client \
    postgresql-client \
    libpq-dev \
    ca-certificates \
    && curl -fsSL https://fastdl.mongodb.org/tools/db/mongodb-database-tools-ubuntu1804-x86_64-100.6.1.deb -o /tmp/mongodb-tools.deb \
    && dpkg -i /tmp/mongodb-tools.deb \
    && rm /tmp/mongodb-tools.deb \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the virtual environment from the builder image
COPY --from=builder /opt/venv /opt/venv

# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy the current directory contents into the container at /app
COPY . /app

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Healthcheck: verify the health endpoint
HEALTHCHECK --interval=60s --timeout=5s --start-period=0s --retries=12 \
  CMD curl -f http://127.0.0.1:5000/health || exit 1

# Use dumb-init as the entrypoint to handle signals and zombie reaping
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Run the application
CMD ["python", "app.py"]
