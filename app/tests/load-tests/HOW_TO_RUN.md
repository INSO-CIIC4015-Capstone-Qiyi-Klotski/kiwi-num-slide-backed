locust -f app/tests/load-tests/locust_backend_db.py --host https://api.kiwinumslide.com



locust -f app/tests/load-tests/locust_backend_nodb.py --host https://api.kiwinumslide.com



locust -f app/tests/load-tests/locust_frontend.py --host https://api.kiwinumslide.com