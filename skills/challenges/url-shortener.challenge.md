---
name: url-shortener
display_name: "URL Shortener Service"
category: backend
difficulty: 5
requirements:
  - "POST /shorten accepts a long URL, returns a short code"
  - "GET /{code} redirects to the original URL with 301"
  - "GET /{code}/stats returns click analytics (count, referrers, timestamps)"
  - "Support custom aliases via optional alias parameter"
  - "URLs expire after a configurable TTL (default 30 days)"
  - "Expired links return HTTP 410 Gone"
bonus_features:
  - "QR code generation for shortened URLs"
  - "Bulk URL shortening via CSV upload"
  - "Rate limiting per API key"
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
hidden_test_path: "tests/arena/hidden/url_shortener_tests.py"
---

# URL Shortener Service

Build a production-ready URL shortener service with click analytics, custom aliases, and automatic expiration.

The service should handle high throughput with efficient storage. Short codes should be unique, URL-safe, and as short as possible while avoiding collisions.

Analytics should track every click with timestamp, referrer, and user-agent. The stats endpoint should support time-range filtering.

Consider edge cases: duplicate URLs, invalid URLs, very long URLs, unicode URLs, and concurrent access to the same short code.
