"""Standard application logout: genuine login, database sessions and enforced CSRF."""
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LogoutView
from django.contrib.sessions.models import Session
from django.test import Client, TestCase
from django.urls import resolve, reverse

from apps.visits.models import Salesperson


class ApplicationLogoutTests(TestCase):
    # Controlled test credential only; not an application/demo account password.
    PASSWORD = "logout-fixture-only"

    @classmethod
    def setUpTestData(cls):
        cls.salesperson = get_user_model().objects.create_user(username="logout-rep", password=cls.PASSWORD)
        cls.manager = get_user_model().objects.create_user(username="logout-manager", password=cls.PASSWORD, is_staff=True)
        Salesperson.objects.create(user=cls.salesperson, employee_code="LOGOUT-REP", first_name="فروشنده", last_name="آزمایشی")

    def logged_in(self, user=None):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("login"))
        response = client.post(reverse("login"), {
            "username": (user or self.salesperson).username, "password": self.PASSWORD,
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Session.objects.get(pk=client.cookies["sessionid"].value).get_decoded()["_auth_user_id"], str((user or self.salesperson).pk))
        return client

    def post_logout(self, client, **data):
        return client.post(reverse("logout"), data, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)

    def test_route_uses_standard_logout_view_and_database_sessions(self):
        match = resolve(reverse("logout"))
        self.assertIs(match.func.view_class, LogoutView)
        self.assertEqual(match.func.view_initkwargs, {"next_page": "login", "redirect_field_name": None})
        from django.conf import settings
        self.assertEqual(settings.SESSION_ENGINE, "django.contrib.sessions.backends.db")

    def test_salesperson_logout_invalidates_session_and_protected_access(self):
        client = self.logged_in()
        key = client.cookies["sessionid"].value
        self.assertRedirects(self.post_logout(client), reverse("login"), fetch_redirect_response=False)
        self.assertFalse(Session.objects.filter(pk=key).exists())
        self.assertEqual(client.get(reverse("salesperson-dashboard")).status_code, 302)
        replay = Client(); replay.cookies["sessionid"] = key
        self.assertEqual(replay.get(reverse("role-home")).status_code, 302)

    def test_manager_logout_invalidates_session_and_management_access(self):
        client = self.logged_in(self.manager)
        key = client.cookies["sessionid"].value
        self.assertRedirects(self.post_logout(client), reverse("login"), fetch_redirect_response=False)
        self.assertFalse(Session.objects.filter(pk=key).exists())
        self.assertEqual(client.get(reverse("management-dashboard")).status_code, 302)

    def test_get_cannot_log_out(self):
        client = self.logged_in(); key = client.cookies["sessionid"].value
        response = client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Session.objects.filter(pk=key).exists())
        self.assertEqual(client.get(reverse("salesperson-dashboard")).status_code, 200)

    def test_missing_csrf_is_rejected_without_invalidating_session(self):
        client = self.logged_in(); key = client.cookies["sessionid"].value
        self.assertEqual(client.post(reverse("logout")).status_code, 403)
        self.assertTrue(Session.objects.filter(pk=key).exists())

    def test_invalid_csrf_is_rejected_without_invalidating_session(self):
        client = self.logged_in(); key = client.cookies["sessionid"].value
        self.assertEqual(client.post(reverse("logout"), {"csrfmiddlewaretoken": "x" * 64}).status_code, 403)
        self.assertTrue(Session.objects.filter(pk=key).exists())

    def test_logout_always_redirects_to_existing_login(self):
        client = self.logged_in()
        self.assertRedirects(self.post_logout(client, next="/management/"), reverse("login"), fetch_redirect_response=False)

    def test_existing_staff_admin_logout_is_unchanged(self):
        client = self.logged_in(self.manager); key = client.cookies["sessionid"].value
        response = client.post(reverse("admin:logout"), {"next": reverse("login")}, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertFalse(Session.objects.filter(pk=key).exists())

    def test_admin_logout_still_does_not_act_as_salesperson_logout(self):
        client = self.logged_in(); key = client.cookies["sessionid"].value
        response = client.post(reverse("admin:logout"), {}, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertRedirects(response, reverse("admin:index"), fetch_redirect_response=False)
        self.assertTrue(Session.objects.filter(pk=key).exists())

    def test_shared_navigation_has_one_persian_post_form_for_each_role(self):
        for user, page in ((self.salesperson, "salesperson-dashboard"), (self.manager, "management-dashboard")):
            with self.subTest(user=user.username):
                response = self.logged_in(user).get(reverse(page))
                self.assertContains(response, 'class="shell-logout" method="post" action="/accounts/logout/"', count=1)
                self.assertContains(response, '<button type="submit">خروج از حساب</button>', count=1)
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                self.assertContains(response, '<html lang="fa" dir="rtl">')

    def test_anonymous_navigation_has_no_logout_action(self):
        from django.contrib.auth.models import AnonymousUser
        from django.template.loader import render_to_string
        from django.test import RequestFactory
        request = RequestFactory().get("/customers/"); request.user = AnonymousUser()
        self.assertNotIn('class="shell-logout"', render_to_string("base.html", request=request))
