{{ config(materialized="view") }}

SELECT
  CAST(flight_date AS DATE) AS flight_date,
  UniqueCarrier AS carrier,
  Origin AS origin_airport,
  DEST AS destination_airport,
  SAFE_CAST(ArrDelay AS FLOAT64) AS arrival_delay,
  SAFE_CAST(DepDelay AS FLOAT64) AS departure_delay,
  SAFE_CAST(Cancelled AS INT64) AS is_cancelled,
  SAFE_CAST(Diverted AS INT64) AS is_diverted
FROM {{ source('airline_data', 'raw_flight_delays') }}