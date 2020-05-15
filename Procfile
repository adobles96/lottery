# web: cd api && gunicorn gettingstarted.wsgi --log-file -
web: cd api && python manage.py makemigrations && python manage.py migrate && python manage.py runserver 0.0.0.0:8000