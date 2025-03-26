import os
from datetime import datetime
from airflow import DAG
import logging
import json
import csv
import io
from sqlalchemy import create_engine, text
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from airflow.hooks.base import BaseHook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator

GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
GCP_BUCKET_NAME = os.getenv('GCP_BUCKET_NAME')
GCP_BQ_DATASET = os.getenv('GCP_BQ_DATASET')
GCP_BQ_TABLE = 'raw_flight_delays'
DBT_PROJECT_DIR = '/opt/airflow/dbt/airline_dbt'
DBT_PROFILE_DIR = '/home/airflow/.dbt'

POSTGRES_CONN_ID = "postgres-default"
GCP_CONN_ID = "google-cloud-default"

logger = logging.getLogger("airline_delay_pipeline")
logging.basicConfig(level=logging.INFO)

def get_postgres_creds():
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    conn = hook.get_connection(POSTGRES_CONN_ID)

    creds_dict = {
        "host": conn.host,
        "port": conn.port,
        "dbname": conn.schema,
        "user": conn.login,
        "password": conn.password
    }

    return json.dumps(creds_dict)

def prepare_spark_args(**kwargs):
    # Push Postgres credentials into XCom for Spark job
    creds_json = get_postgres_creds()
    kwargs["ti"].xcom_push(key="postgres_creds", value=creds_json)
    logger.info(f"Pushed Postgres creds to XCom: {creds_json}")

def upload_csv_to_postgres():
    csv_path = '/tmp/delayed-flights/DelayedFlights.csv'
    table_name = 'delayed_flights_raw'

    postgres_uri = BaseHook.get_connection("postgres-default").get_uri().replace("postgres://", "postgresql://")

    # Read headers and set 'ID' if first is blank
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        if headers[0].strip() == '':
            headers[0] = 'ID'
        clean_headers = [h.strip().replace('"', '').replace(' ', '_') for h in headers]

    # Create table dynamically
    engine = create_engine(postgres_uri)
    with engine.begin() as conn:
        conn.execute(text(f'DROP TABLE IF EXISTS {table_name}'))
        col_defs = ', '.join([f'"{col}" TEXT' for col in clean_headers])
        conn.execute(text(f'CREATE TABLE {table_name} ({col_defs})'))

    # Load entire CSV (including header) into memory as file-like
    with open(csv_path, 'r') as f:
        content = f.read()
    buffer = io.StringIO(content)

    # Load using psycopg2 COPY
    pg_conn = engine.raw_connection()
    with pg_conn.cursor() as cur:
        cur.copy_expert(f'COPY {table_name} FROM STDIN WITH CSV HEADER', buffer)
    pg_conn.commit()
    pg_conn.close()

with DAG(
    dag_id='airline_delay_pipeline',
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    description='ETL: Kaggle → Postgres → Spark → GCS → BigQuery → dbt → BigQuery',
    tags=['airline', 'postgres', 'spark', 'gcs'],
) as dag:

    prep_spark_task = PythonOperator(
        task_id="prepare_spark_args",
        python_callable=prepare_spark_args,
        provide_context=True
    )

    download_dataset = BashOperator(
        task_id='download_kaggle_csv',
        bash_command="""
        mkdir -p /tmp/delayed-flights && \
        export KAGGLE_CONFIG_DIR=/opt/airflow/kaggle && \
        kaggle datasets download -d abdurrehmankhalid/delayedflights -p /tmp/delayed-flights --unzip
        """,
    )

    upload_to_postgres = PythonOperator(
        task_id='upload_csv_to_postgres',
        python_callable=upload_csv_to_postgres,
    )

    spark_process = SparkSubmitOperator(
        task_id='spark_process_from_postgres',
        application='/opt/airflow/spark-jobs/ingest_airline_delays.py',
        conn_id='spark-default',
        executor_cores=1,
        executor_memory="1g",
        driver_memory="1g",
        conf={
            "spark.master": "spark://spark-master:7077",
            "spark.hadoop.google.cloud.auth.service.account.enable": "true",
            "spark.hadoop.google.cloud.auth.service.account.json.keyfile": "/opt/keys/gcp-creds.json"
        },
        application_args=[
            "{{ ti.xcom_pull(task_ids='prepare_spark_args', key='postgres_creds') }}",
            GCP_BUCKET_NAME
        ],
        jars="/opt/airflow/spark/jars/postgresql-42.7.3.jar,/opt/airflow/spark/jars/gcs-connector-hadoop3-latest.jar",
        verbose=True
    )

    load_to_bq = GCSToBigQueryOperator(
        task_id='load_gcs_to_bq',
        bucket=GCP_BUCKET_NAME,
        gcp_conn_id=GCP_CONN_ID,
        source_objects=["raw/airline_delays/*.parquet"],
        destination_project_dataset_table=f"{GCP_PROJECT_ID}.{GCP_BQ_DATASET}.{GCP_BQ_TABLE}",
        source_format='PARQUET',
        write_disposition='WRITE_TRUNCATE',
        autodetect=True
    )

    run_dbt = BashOperator(
        task_id='run_dbt_transformations',
        bash_command = (
            f'dbt run --project-dir {DBT_PROJECT_DIR} --profiles-dir {DBT_PROFILE_DIR} '
            '--full-refresh | tee /tmp/dbt_output.log && '
            'grep -q "Finished running" /tmp/dbt_output.log || '
            '(echo "No models were run!" && exit 1)'
        )
    )

    prep_spark_task >> download_dataset >> upload_to_postgres >> spark_process >> load_to_bq >> run_dbt