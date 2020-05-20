""" Production settings """

import os

import django_heroku

from api.settings.common import *


DEBUG = False

SECRET_KEY = os.environ['SECRET_KEY']

ALLOWED_HOSTS = ['loteria-cr.herokuapp.com']  # fill in w host url/ip addr

CACHES = {  # run this to create the cache table: 'python manage.py createcachetable'
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'reserved_tickets',
    }
}

DIALOGFLOW_PROJECT_ID = 'newagent-lyssbi'  # use prod chatbot here. TODO change.

django_heroku.settings(locals())
