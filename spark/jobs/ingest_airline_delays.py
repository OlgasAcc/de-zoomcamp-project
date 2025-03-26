import sys
import logging
import traceback
import json
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, concat_ws

GCP_BUCKET = sys.argv[2]

logger = logging.getLogger("ingest_from_postgres")
logging.basicConfig(level=logging.INFO)

def log_and_exit(msg, code=1):
    logger.error(msg)
    traceback.print_exc()
    sys.exit(code)

try:
    postgres_creds_json = sys.argv[1]
    postgres_creds = json.loads(postgres_creds_json)

    POSTGRES_HOST = postgres_creds.get("host")
    POSTGRES_PORT = postgres_creds.get("port")
    POSTGRES_DBNAME = postgres_creds.get("dbname")
    POSTGRES_USER = postgres_creds.get("user")
    POSTGRES_PASSWORD = postgres_creds.get("password")

    if not all([POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DBNAME, POSTGRES_USER, POSTGRES_PASSWORD]):
        raise ValueError("Missing PostgreSQL credentials in JSON.")

    POSTGRES_URL = f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DBNAME}"

    logger.info("Starting Spark session...")
    spark = (SparkSession.builder
             .appName("Airline Delay Ingestion")
             .config("spark.master", "spark://spark-master:7077")
             .config("spark.hadoop.fs.gs.impl", "com.google.cloud.hadoop.fs.gcs.GoogleHadoopFileSystem")
             .config("spark.hadoop.google.cloud.auth.service.account.enable", "true")
             .config("spark.hadoop.google.cloud.auth.service.account.json.keyfile", "/opt/keys/gcp-creds.json")
             .getOrCreate())

    logger.info("Reading data from Postgres via JDBC...")
    df = (
        spark.read.format("jdbc")
        .option("url", POSTGRES_URL)
        .option("dbtable", "delayed_flights_raw")
        .option("user", POSTGRES_USER)
        .option("password", POSTGRES_PASSWORD)
        .option("driver", "org.postgresql.Driver")
        .load()
    )
    logger.info("Successfully read data from Postgres")

    logger.info("Transforming data...")
    df_clean = df \
        .withColumn("flight_date", to_date(concat_ws("-", col("Year"), col("Month"), col("DayofMonth")), "yyyy-M-d")) \
        .withColumn("year", col("Year")) \
        .withColumn("month", col("Month")) \
        .select(
            "flight_date", "year", "month",
            "UniqueCarrier", "Origin", "Dest",
            "ArrDelay", "DepDelay", "Cancelled", "Diverted"
        ) \
        .filter(col("flight_date").isNotNull()) \
        .repartition(12, "year", "month")

    logger.info("Writing transformed data to GCS...")
    df_clean.repartition(10) \
        .write \
        .mode("overwrite") \
        .parquet(f"gs://{GCP_BUCKET}/raw/airline_delays/")

    logger.info("Done.")
except Exception:
    log_and_exit("Spark ingestion failed.")
finally:
    if 'spark' in locals():
        spark.stop()