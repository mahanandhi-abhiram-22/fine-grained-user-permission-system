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
expected_database = BACKEND_DIR / 'db.sqlite3'
if default_database['ENGINE'] != 'django.db.backends.sqlite3' or Path(default_database['NAME']).resolve() != expected_database.resolve():
    raise SystemExit('Isolated tests require the canonical project SQLite settings.')

test_database = settings.DATABASES['default'].setdefault('TEST', {})
test_database.update({
    'NAME': ':memory:',
    'MIRROR': None,
    'CHARSET': None,
    'COLLATION': None,
    'MIGRATE': True,
    'DEPENDENCIES': [],
    'SERIALIZE': True,
})

if len(sys.argv) > 1:
    call_command('test', *sys.argv[1:])
else:
    call_command('test', 'tests')