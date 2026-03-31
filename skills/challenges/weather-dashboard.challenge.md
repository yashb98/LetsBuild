---
name: weather-dashboard
display_name: "Weather Dashboard"
category: fullstack
difficulty: 5
requirements:
  - "Aggregate weather data from at least 2 API sources"
  - "Display current conditions, hourly and daily forecasts"
  - "Location search by city name or coordinates"
  - "Historical comparison (today vs same day last year)"
  - "Responsive design that works on mobile and desktop"
  - "Graceful degradation when one API source is down"
bonus_features:
  - "Weather alerts and severe weather warnings"
  - "Saved locations with quick switching"
  - "Forecast accuracy tracking over time"
time_limits:
  research: 1800
  architecture: 900
  build: 5400
  cross_review: 900
  fix_sprint: 900
judging_weights:
  functionality: 0.30
  code_quality: 0.20
  test_coverage: 0.15
  ux_design: 0.15
  architecture: 0.10
  innovation: 0.10
constraints:
  stack: "any"
  auth: false
  must_run: "docker-compose up or python main.py"
hidden_test_path: "tests/arena/hidden/weather_dashboard_tests.py"
---

# Weather Dashboard

Build a weather dashboard that aggregates data from multiple API sources, shows forecasts, and provides historical comparison.

The backend should implement a caching layer to avoid excessive API calls and handle source failures gracefully. When one provider is down, the dashboard should still work with reduced data rather than failing entirely.

The frontend should be clean and informative. Weather data visualization (temperature charts, precipitation probability) adds significant value.
