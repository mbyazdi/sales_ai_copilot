"""Focused SQLite compatibility, memory-only; original database cannot be opened."""
from common import *


def main():
    clean_database_environment()
    os.environ.update(DJANGO_SETTINGS_MODULE="sales_ai_copilot.settings", DB_ENGINE="sqlite")
    from django.conf import settings
    settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:", "TEST": {"NAME": ":memory:"}}}
    from django.db.backends.sqlite3.base import DatabaseWrapper
    original = DatabaseWrapper.get_new_connection
    def guarded(wrapper, params):
        require(params.get('database') in {':memory:', 'file:memorydb_default?mode=memory&cache=shared'},
                'Only the exact in-memory SQLite test database is permitted.')
        return original(wrapper, params)
    DatabaseWrapper.get_new_connection = guarded
    import django
    django.setup()
    from django.test.runner import DiscoverRunner
    result = DiscoverRunner(verbosity=1, interactive=False).run_tests([
        'apps.recommendations.tests_feedback.FeedbackAPITests',
        'apps.sales_requests.tests_submission.SubmissionAPITests',
    ])
    return int(bool(result))


if __name__ == '__main__':
    raise SystemExit(main())
