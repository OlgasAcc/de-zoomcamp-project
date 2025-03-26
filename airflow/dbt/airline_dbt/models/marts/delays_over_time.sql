{{ config(materialized="table") }}

SELECT
  DATE_TRUNC(flight_date, MONTH) AS flight_month,
  COUNT(*) AS total_flights,
  ROUND(AVG(arrival_delay), 2) AS avg_arrival_delay,
  ROUND(AVG(departure_delay), 2) AS avg_departure_delay
FROM {{ ref('stg_flight_delays') }}
WHERE is_cancelled = 0
GROUP BY flight_month
ORDER BY flight_month