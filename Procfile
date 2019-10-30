web: bin/start-nginx bin/start-stunnel gunicorn -c config/gunicorn.conf app:server 
main_worker: bin/start-stunnel celery -A tasks worker --beat --loglevel=info