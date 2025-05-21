runserver: python3 manage.py runserver 0.0.0.0:8000
daphne: daphne -b 0.0.0.0 -p 8001 townlit_b.asgi:application
worker: celery -A townlit_b worker -l info
beat: celery -A townlit_b beat -l info

