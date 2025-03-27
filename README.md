# de-zoomcamp-project

<p align="left">
  <img src="images/datatalks_club_logo.png" alt="DataTalksClub Logo" width="200"/>
</p>

**Project author:** Olha Krasnozhon

**Course:** [DataTalksClub Data Engineering Zoomcamp](https://github.com/DataTalksClub/data-engineering-zoomcamp)

## End-to-End Data Pipeline:

![Animated data pipeline flow](images/pipeline.gif)

```mermaid
graph TD
    subgraph T[Terraform Infrastructure]
        direction TB
        T1[GCP Project Setup]
        T2[GCS Bucket Creation]
        T3[BigQuery Dataset Creation]
        T4[Service Account Creation]
        T5[IAM Role Assignment]
        T6[Creds file generation]
    end

    subgraph A[Airflow Orchestration]
        direction TB
        A1[Kaggle: extract dataset .csv]
        A2[Postgres: upload dataset .csv]
        A3[Spark Job: clean + format data from Postgres]
        A4[Spark Job: upload processed data to GCS .parquet files]
        A5[Push data to BigQuery: 'raw_flight_delays']
        A6[dbt: staging.stg_flight_delays.sql]
        A7[dbt: marts.delays_by_carrier.sql]
        A8[dbt: marts.delays_over_time.sql]
        A9[BigQuery: 'airline_data.delays_by_carrier']
        A10[BigQuery: 'airline_data.delays_over_time']

        A1 --> A2
        A2 --> A3
        A3 --> A4
        A4 --> A5
        A5 --> A6
        A6 --> A7
        A6 --> A8
        A7 --> A9
        A8 --> A10

    end

    T --> A
    A9 --> B[Looker Studio Dashboard]
    A10 --> B
```
📌 All steps except the final dashboard are orchestrated via Apache Airflow, including:
- A single Spark job for cleaning & formatting the Postgres data
- Loading to GCS & BigQuery
- dbt transformations

## Setup

### Terraform

1.  Install `gcloud` (MacOS):
    ```bash
    brew install gcloud
    ```
2.  Set your GCP project ID (replace `terraform-demo-452019` with your actual project ID):
    ```bash
    gcloud config set project terraform-demo-452019
    ```
3.  Create a service account for Terraform:
    ```bash
    gcloud iam service-accounts create terraform-admin \
      --display-name "Terraform Admin"
    ```
4.  Grant the service account owner role (for demonstration purposes):
    ```bash
    gcloud projects add-iam-policy-binding terraform-demo-452019 \
      --member="serviceAccount:terraform-admin@terraform-demo-452019.iam.gserviceaccount.com" \
      --role="roles/owner"
    ```
    **Note:** In production environments, it is strongly recommended to grant only the necessary roles instead of the owner role. For example:
    -   `roles/storage.admin`
    -   `roles/bigquery.admin`
    -   `roles/iam.serviceAccountAdmin`
    -   `roles/iam.serviceAccountKeyAdmin`
5.  Create a credentials file (`gcp-creds.json`) for the service account in the `/terraform` directory:
    ```bash
    gcloud iam service-accounts keys create terraform/gcp-creds.json \
      --iam-account=terraform-admin@terraform-demo-452019.iam.gserviceaccount.com
    ```
6.  Copy the `gcp-creds.json` file to the root project's `keys` directory:
    ```bash
    cp terraform/gcp-creds.json keys
    ```
7.  Run Terraform commands to create the bucket and dataset in GCP:
    ```bash
    cd terraform
    terraform init
    terraform apply
    ```
Expected result:

<p align="left">
  <img src="images/img_terraform_result.png" alt="terraform_result"/>
</p>

### Docker Compose:

To start all the relevant services defined `docker-compose.yml` file, run the following command:

```bash
docker-compose up --build -d
```

### Airflow Connections

Once the services are up and running, you need to create the required Airflow connections. You can do this either through the Airflow UI or by running commands manually.

**Option 1: Airflow UI**

1.  Open the Airflow UI: `http://localhost:8082`
2.  Navigate to `Admin` -> `Connections`.
3.  Add the following connections:

    * `google-cloud-default` (Google Cloud Platform)
    * `spark-default` (Spark)
    * `postgres-default` (PostgreSQL)

**Option 2: Manual Commands**

Alternatively, you can create the connections using the following `docker exec` commands:

1.  **Google Cloud Platform Connection:**
    ```bash
    docker exec -it de-zoomcamp-project-airflow-webserver-1 airflow connections add 'google-cloud-default' \
        --conn-type 'google_cloud_platform' \
        --conn-extra '{"extra__google_cloud_platform__key_path":"/opt/keys/gcp-creds.json","extra__google_cloud_platform__project":"terraform-demo-452019"}'
    ```
    **Note:** Ensure `terraform-demo-452019` reflects your GCP project ID.

2.  **Spark Connection:**
    ```bash
    docker exec -it de-zoomcamp-project-airflow-webserver-1 airflow connections add 'spark-default' \
        --conn-type 'spark' \
        --conn-host 'spark-master' \
        --conn-port '7077' \
        --conn-extra '{"spark-binary": "spark-submit", "deploy-mode": "client"}'
    ```

3.  **PostgreSQL Connection:**
    ```bash
    docker exec -it de-zoomcamp-project-airflow-webserver-1 airflow connections add 'postgres-default' \
        --conn-type 'postgres' \
        --conn-login 'airflow' \
        --conn-password 'airflow' \
        --conn-host 'postgres' \
        --conn-port '5432' \
        --conn-schema 'airline_data'
    ```

<p align="left">
  <img src="images/img_airflow_connections.png" alt="airflow_connections"/>
</p>

**Trigger the Airflow DAG "airline_delay_pipeline"**:

<p align="left">
  <img src="images/img_airflow_trigger_dag.png" alt="airflow_trigger_dag"/>
</p>

Successful DAG run:
<p align="left">
  <img src="images/img_airflow_dag_progress.png" alt="airflow_dag_progress"/>
</p>

**Verification**

* **Airflow UI:** `http://localhost:8082` (username: `airflow`, password: `airflow`)
* **Spark UI:** `http://localhost:8080`

Expected result:
<p align="left">
  <img src="images/img_spark_progress.png" alt="spark_progress"/>
</p>

* **PostgreSQL:** Verify the table content using the following command:
    ```bash
    docker exec -it de-zoomcamp-project-postgres-1 psql -U airflow -d airline_data -c "SELECT * FROM delayed_flights_raw LIMIT 10;" | less -S
    ```
Expected result:
<p align="left">
  <img src="images/img_download_dataset_pg_result.png" alt="download_dataset_pg_result"/>
</p>

* **GCP Bucket and BigQuery Dataset:** Check the resources in the Google Cloud Console (Cloud Storage (--> Buckets) and BigQuery sections).

Expected results:
<p align="left">
  <img src="images/img_spark_job_result.png" alt="spark_job_result"/>
</p>

<p align="left">
  <img src="images/img_gcp_to_bigquery_result.png" alt="gcp_to_bigquery_result"/>
</p>

<p align="left">
  <img src="images/img_dbt_target_table_1.png" alt="dbt_target_table_1"/>
</p>

<p align="left">
  <img src="images/img_dbt_target_table_2.png" alt="dbt_target_table_2"/>
</p>

## Dashboard (Google Looker Studio):

This dashboard utilizes 2 target BigQuery tables:

* `airline_data.delays_by_carrier`
* `airline_data.delays_over_time`

These tables are queried within the Looker Studio dashboard to visualize the data.
The added resources in Looker (from "BigQuery"):

<p align="left">
  <img src="images/img_dashboard_added_resources.png" alt="dashboard_added_resources"/>
</p>

Access the dashboard using the following link:
[https://lookerstudio.google.com/reporting/a8117be3-4133-49ca-9015-a316edd96f88](https://lookerstudio.google.com/reporting/a8117be3-4133-49ca-9015-a316edd96f88)

![Dashboard Image](images/img_dashboard.png)
