FROM apache/airflow:2.10.5-python3.12

USER root
RUN apt-get update && apt-get install -y openjdk-17-jdk

USER airflow
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt