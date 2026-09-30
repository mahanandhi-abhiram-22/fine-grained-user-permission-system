import os
import secrets
import sys
from pathlib import Path

if os.environ.get('DJANGO_SETTINGS_MODULE') not in (None, 'config.settings'):
    raise SystemExit('Use the canonical config.settings module for isolated tests.')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DEBUG'] = 'False'
os.environ['SECRET_KEY'] = secrets.token_urlsafe(48)

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.dont_write_bytecode = True

import django

django.setup()

from django.conf import settings
from django.core.management import call_command

default_database = settings.DATABASES['default']
if default_database['ENGINE'] != 'django.db.backends.postgresql':
    raise SystemExit('Isolated tests require the canonical project PostgreSQL settings.')
if not default_database.get('NAME'):
    raise SystemExit('Isolated tests require DB_NAME to be configured in the project-root .env.')

test_database = settings.DATABASES['default'].setdefault('TEST', {})
test_database.update({
    'MIGRATE': True,
    'DEPENDENCIES': [],
    'SERIALIZE': True,
})

if len(sys.argv) > 1:
    call_command('test', *sys.argv[1:])
else:
    call_command('test', 'tests')