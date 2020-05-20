release: python api/manage.py migrate && python api/manage.py createcachetable
web: cd api && gunicorn api.wsgi --log-file -
