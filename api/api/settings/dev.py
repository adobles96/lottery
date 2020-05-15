""" Development settings """

import os

from api.settings.common import *

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'd+9xgdki%+n%ri%pkjowdn9ybbvof_%g-1r6vo-9@$ox@jyl86'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '0.0.0.0', 'loteria-cr.herokuapp.com']

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
    # 'default': {
    #     'ENGINE': 'django.db.backends.postgresql',
    #     'HOST': os.environ.get('DB_HOST'),
    #     'NAME': os.environ.get('DB_NAME'),
    #     'USER': os.environ.get('DB_USER'),
    #     'PASSWORD': os.environ.get('DB_PASSWORD'),
    # }
}
