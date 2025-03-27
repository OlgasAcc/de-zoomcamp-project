FROM apache/airflow:2.10.5-python3.12

USER root
# Install Java (required for Spark)
RUN apt-get update && apt-get install -y openjdk-17-jdk wget

USER airflow
COPY requirements.txt .
# Install Python dependencies
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Create directory for Spark jars
RUN mkdir -p /opt/airflow/spark/jars

# Download GCS and Postgres JDBC connectors
RUN wget https://storage.googleapis.com/hadoop-lib/gcs/gcs-connector-hadoop3-latest.jar -P /opt/airflow/spark/jars/ && \
    wget https://jdbc.postgresql.org/download/postgresql-42.7.3.jar -P /opt/airflow/spark/jars/