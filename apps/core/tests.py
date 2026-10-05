"""Shared shell navigation tests; feature authorization lives in its own suite."""
from html.parser import HTMLParser
from urllib.parse import urlsplit
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse

from apps.visits.models import Salesperson


class NavigationParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_navigation = False
        self.links = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav" and attrs.get("aria-label") == "ناوبری اصلی":
            self.in_navigation = True
        if tag == "a" and self.in_navigation:
            self.links[attrs["href"]] = attrs.get("aria-current")

    def handle_endtag(self, tag):
        if tag == "nav":
            self.in_navigation = False


class ProductShellTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.rep_user = users.objects.create_user(username="shell-rep")
        cls.staff = users.objects.create_user(username="shell-staff", is_staff=True)
        cls.inactive = users.objects.create_user(username="shell-inactive")
        cls.missing = users.objects.create_user(username="shell-missing")
        for user, active in ((cls.rep_user, True), (cls.inactive, False)):
            Salesperson.objects.create(user=user, employee_code=user.username,
                                       first_name="آزمایشی", last_name="فروش", is_active=active)

    def render_shell(self, user, path="/customers/"):
        request = RequestFactory().get(path)
        request.user = user
        request.resolver_match = resolve(path)
        return render_to_string("base.html", request=request)

    def test_active_salesperson_navigation_and_real_identity(self):
        html = self.render_shell(self.rep_user)
        self.assertEqual(set(NavigationParser(html).links), {
            reverse("salesperson-dashboard"), reverse("follow-up-dashboard"), "/customers/",
        })
        self.assertIn("آزمایشی فروش", html)
        self.assertIn("نماینده فروش", html)

    def test_staff_without_salesperson_has_only_supported_management_and_customer_links(self):
        html = self.render_shell(self.staff)
        self.assertEqual(set(NavigationParser(html).links), {
            reverse("management-dashboard"), reverse("recommendation-performance-dashboard"), "/customers/",
        })
        self.assertIn("shell-staff", html)
        self.assertIn("کاربر مدیریت", html)

    def test_staff_with_active_salesperson_can_navigate_both_existing_workspaces(self):
        Salesperson.objects.create(user=self.staff, employee_code="shell-dual",
                                   first_name="مدیریت", last_name="فروش")
        self.assertEqual(len(NavigationParser(self.render_shell(self.staff)).links), 5)

    def test_anonymous_missing_inactive_and_nonstaff_superuser_do_not_get_business_links(self):
        superuser = get_user_model().objects.create_user(username="shell-super", is_superuser=True)
        for user in (AnonymousUser(), self.missing, self.inactive, superuser):
            with self.subTest(user=str(user)):
                self.assertEqual(NavigationParser(self.render_shell(user)).links, {})

    def test_exactly_one_active_link_for_each_existing_page_and_customer_alias(self):
        for name, user in (
            ("salesperson-dashboard", self.rep_user), ("follow-up-dashboard", self.rep_user),
            ("management-dashboard", self.staff), ("recommendation-performance-dashboard", self.staff),
        ):
            path = reverse(name)
            links = NavigationParser(self.render_shell(user, path)).links
            self.assertEqual([url for url, current in links.items() if current == "page"], [path])
        for path in ("/customers/", "/api/customers/"):
            links = NavigationParser(self.render_shell(self.rep_user, path)).links
            self.assertEqual([url for url, current in links.items() if current == "page"], ["/customers/"])

    def test_existing_pages_share_base_and_keep_their_feature_scripts(self):
        for user, path, script in (
            (self.rep_user, reverse("salesperson-dashboard"), None),
            (self.rep_user, reverse("follow-up-dashboard"), "core/js/follow_up_dashboard.js"),
            (self.rep_user, "/customers/", "core/js/customer_360.js"),
            (self.staff, reverse("management-dashboard"), "management/js/dashboard.js"),
            (self.staff, reverse("recommendation-performance-dashboard"), "management/js/recommendation_performance.js"),
        ):
            with self.subTest(path=path):
                self.client.force_login(user)
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "base.html")
                self.assertContains(response, '<html lang="fa" dir="rtl">')
                self.assertContains(response, 'aria-label="ناوبری اصلی"')
                if script:
                    self.assertContains(response, script)

    @override_settings(DEBUG=True)
    def test_rendered_shell_stylesheet_is_versioned_and_serves_matching_selectors(self):
        from django.contrib.staticfiles.views import serve

        html = self.render_shell(self.rep_user)
        href = re.search(r'href="([^\"]*css/app\.css[^\"]*)"', html).group(1)
        url = urlsplit(href)
        self.assertEqual(url.path, "/static/css/app.css")
        self.assertEqual(url.query, "v=002b-1")
        response = serve(RequestFactory().get(href), "css/app.css")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "text/css")
            css = b"".join(response.streaming_content).decode("utf-8")
        finally:
            response.close()
        for selector in (".shell-header-inner", ".shell-nav", ".shell-brand", ".shell-content"):
            self.assertIn(selector, css)
        self.assertNotIn('class="shell-sidebar"', html)

    @override_settings(DEBUG=True)
    def test_design_foundation_loads_before_shell_and_help_search_matches_access(self):
        from django.contrib.staticfiles.views import serve

        html = self.render_shell(self.rep_user)
        self.assertLess(html.index("css/design-system.css"), html.index("css/app.css"))
        response = serve(RequestFactory().get("/static/css/design-system.css?v=002b-1"),
                         "css/design-system.css")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "text/css")
        finally:
            response.close()
        for user in (self.rep_user, self.staff):
            html = self.render_shell(user)
            self.assertIn('label class="ds-label" for="shell-customer-search"', html)
            self.assertIn('action="/customers/" method="get"', html)
        for user in (AnonymousUser(), self.inactive, self.missing):
            self.assertNotIn('id="shell-customer-search"', self.render_shell(user))
