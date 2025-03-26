{{ config(materialized="table") }}

SELECT
  carrier,
  COUNT(*) AS total_flights,
  COUNTIF(arrival_delay > 15) AS delayed_flights,
  ROUND(100 * COUNTIF(arrival_delay > 15) / COUNT(*), 2) AS delay_percent
FROM {{ ref('stg_flight_delays') }}
GROUP BY carrier
ORDER BY delayed_flights DESC