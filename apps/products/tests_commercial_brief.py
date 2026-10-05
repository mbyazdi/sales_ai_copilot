"""Customer-context brief contracts; real builders, isolated test database."""

from datetime import timedelta
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.commercial_context import build_product_commercial_context
from apps.customers.models import CustomerGrade
from apps.inventory.models import Inventory
from apps.promotions.models import Promotion, PromotionProduct
from apps.recommendations.models import CustomerRecommendation
from apps.visits import tests_authorization
from apps.visits.models import Visit, VisitCommercialSnapshot, VisitCustomerSnapshot

from .models import Product


class BriefLinkParser(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.links = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href", "")
        if tag == "a" and href.startswith("/products/"):
            self.links.append(href)


class ProductCommercialBriefTests(TestCase):
    TODAY = tests_authorization.AuthorizationBaselineTests.TODAY

    @classmethod
    def setUpTestData(cls):
        tests_authorization.AuthorizationBaselineTests.setUpTestData.__func__(cls)
        cls.product.description = "توضیحات ثبت‌شده محصول"
        cls.product.package_size = "6 PCS"
        cls.product.save()
        cls.inventory = Inventory.objects.create(
            product=cls.product, available_quantity=20, reserved_quantity=3, minimum_stock=5,
        )
        cls.recommendation = cls.recommendations[0]
        cls.recommendation.reason = "دلیل ذخیره‌شده برای این مشتری"
        cls.recommendation.confidence_score = 72
        cls.recommendation.evidence_quality = "MEDIUM"
        cls.recommendation.explanation_snapshot = {
            "signals": [{"name": "repurchase", "score": 35, "active": True}],
            "active_signal_count": 1,
        }
        cls.recommendation.score_breakdown = {"purchase_score": 35, "feedback_score": 0}
        cls.recommendation.save()
        cls.alternative = Product.objects.create(
            product_code="BRIEF-ALT", name="گزینه جایگزین",
            brand=cls.product.brand, category=cls.product.category,
        )
        cls.alternative_recommendation = CustomerRecommendation.objects.create(
            customer=cls.customer, product=cls.alternative, recommendation_type="CATEGORY",
            score=99, rank=2,
        )

    def setUp(self):
        self.client.force_login(self.user)
        clock = patch("django.utils.timezone.localdate", return_value=self.TODAY)
        clock.start()
        self.addCleanup(clock.stop)

    def page(self, customer=None, product=None, **extra):
        query = {"customer_code": (customer or self.customer).customer_code, **extra}
        return self.client.get(reverse(
            "product-commercial-brief", args=[(product or self.product).product_code],
        ), query)

    def promotion(self, code, **fields):
        promotion = Promotion.objects.create(
            code=code, name=code, promotion_type="PERCENTAGE", discount_percent=10,
            start_date=fields.pop("start_date", self.TODAY),
            end_date=fields.pop("end_date", self.TODAY), **fields,
        )
        PromotionProduct.objects.create(promotion=promotion, product=self.product)
        return promotion

    def test_assigned_salesperson_sees_source_product_values_and_shared_shell(self):
        response = self.page()
        self.assertEqual(response.status_code, 200)
        for value in (self.product.name, self.product.product_code, self.product.description,
                      self.product.package_size, self.product.unit, self.product.brand.name,
                      self.product.category.name, self.customer.name):
            self.assertContains(response, value)
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, 'lang="fa" dir="rtl"')
        self.assertContains(response, "products/css/product_brief.css")
        self.assertContains(response, "شرایط تجاری فعلی")
        self.assertNotContains(response, "outcome-btn")

    def test_customer_required_and_no_global_product_workspace(self):
        response = self.client.get(reverse("product-commercial-brief", args=[self.product.product_code]))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, self.product.name, status_code=404)

    def test_unauthorized_and_missing_customers_have_identical_nonleaking_response(self):
        forbidden = self.page(customer=self.other_customer)
        absent = self.client.get(reverse("product-commercial-brief", args=[self.product.product_code]),
                                 {"customer_code": "DOES-NOT-EXIST"})
        self.assertEqual(forbidden.status_code, 404)
        self.assertEqual(forbidden.content, absent.content)
        for value in (self.other_customer.name, self.other_customer.phone, self.product.name,
                      self.recommendation.reason):
            self.assertNotIn(value.encode(), forbidden.content)

    def test_customer_scope_is_checked_before_product_or_visit_read(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.page(customer=self.other_customer, visit_id=self.visits[1].pk)
        self.assertEqual(response.status_code, 404)
        sql = " ".join(query["sql"] for query in queries)
        for table in ("products_product", "visits_visit", "inventory_inventory", "promotions_promotion"):
            self.assertNotIn(table, sql)

    def test_anonymous_and_missing_profile_denied_without_business_identity(self):
        self.client.logout()
        for user in (None, self.no_profile):
            if user:
                self.client.force_login(user)
            response = self.page()
            self.assertEqual(response.status_code, 403)
            self.assertNotIn(self.customer.name.encode(), response.content)
            self.assertNotIn(self.product.name.encode(), response.content)

    def test_inactive_profile_and_withdrawn_assignment_denied(self):
        self.rep.is_active = False
        self.rep.save()
        self.assertEqual(self.page().status_code, 403)
        self.rep.is_active = True
        self.rep.save()
        self.customer.salesperson_assignments.update(is_active=False)
        self.assertEqual(self.page(visit_id=self.visits[0].pk).status_code, 404)

    def test_staff_can_inspect_other_customer_without_operational_controls(self):
        self.client.force_login(self.staff)
        response = self.page(customer=self.other_customer)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["manager_inspection"])
        self.assertIsNone(response.context["visit"])
        self.assertContains(response, "فقط مشاهده")
        for marker in ("outcome-btn", "startVisitButton", "completeVisitButton", "salesCopilotGenerateButton"):
            self.assertNotContains(response, marker)
        self.assertNotIn("visit_id", response.context["return_url"])

    def test_staff_including_dual_role_cannot_carry_operational_visit(self):
        self.user.is_staff = True
        self.user.save()
        for user in (self.staff, self.user):
            self.client.force_login(user)
            self.assertEqual(self.page(visit_id=self.visits[0].pk).status_code, 404)

    def test_own_customer_visit_preserved_in_return_navigation(self):
        response = self.page(visit_id=self.visits[0].pk, next="https://example.invalid/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["visit"].pk, self.visits[0].pk)
        url = urlsplit(response.context["return_url"])
        self.assertEqual(url.path, "/customers/")
        self.assertEqual(url.fragment, "workspace-recommendations")
        self.assertEqual(parse_qs(url.query), {
            "customer_code": [self.customer.customer_code], "visit_id": [str(self.visits[0].pk)],
        })

    def test_invalid_foreign_or_mismatched_visit_context_has_same_response(self):
        foreign = Visit.objects.create(salesperson=self.other_rep, customer=self.customer, visit_date=self.TODAY)
        own_wrong_customer = Visit.objects.create(salesperson=self.rep, customer=self.other_customer, visit_date=self.TODAY)
        responses = [self.page(visit_id=value) for value in (
            "bad", "0", "-1", "9" * 40, "۱۲", 999999, foreign.pk,
            own_wrong_customer.pk, self.visits[1].pk,
        )]
        for response in responses:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.content, responses[0].content)

    def test_missing_and_inactive_products_are_unavailable(self):
        missing = self.client.get("/products/NO-SUCH-PRODUCT/", {"customer_code": self.customer.customer_code})
        self.product.is_active = False
        self.product.save()
        inactive = self.page()
        self.assertEqual(inactive.status_code, 404)
        self.assertEqual(missing.content, inactive.content)

    def test_commercial_values_match_existing_builder_and_api(self):
        self.promotion("ELIGIBLE")
        response = self.page()
        expected = build_product_commercial_context(self.product, self.customer, as_of_date=self.TODAY)
        self.assertEqual(response.context["commercial"], expected)
        api = self.client.get(reverse("product-commercial-context", args=[
            self.customer.customer_code, self.product.product_code,
        ]))
        self.assertEqual(api.status_code, 200)
        # API serializes dates/decimals; compare parsed HTML builder values before serialization.
        self.assertEqual(api.data["commercial_context"], expected)
        self.assertContains(response, "17")

    def test_promotion_date_active_product_and_grade_filters_reused(self):
        grade = CustomerGrade.objects.create(code="BRIEF-GRADE", name="Grade")
        self.promotion("PUBLIC")
        restricted = self.promotion("RESTRICTED")
        restricted.customer_grades.add(grade)
        self.promotion("EXPIRED", start_date=self.TODAY - timedelta(days=2), end_date=self.TODAY - timedelta(days=1))
        self.promotion("FUTURE", start_date=self.TODAY + timedelta(days=1), end_date=self.TODAY + timedelta(days=2))
        self.promotion("INACTIVE", is_active=False)
        other = self.promotion("OTHER-PRODUCT")
        PromotionProduct.objects.filter(promotion=other).update(product=self.alternative)
        response = self.page()
        self.assertEqual([p["code"] for p in response.context["commercial"]["promotions"]], ["PUBLIC"])
        for code in ("RESTRICTED", "EXPIRED", "FUTURE", "INACTIVE", "OTHER-PRODUCT"):
            self.assertNotContains(response, code)
        self.customer.grade = grade
        self.customer.save()
        self.assertEqual({p["code"] for p in self.page().context["commercial"]["promotions"]}, {"PUBLIC", "RESTRICTED"})

    def test_no_promotion_is_truthful_empty_state(self):
        response = self.page()
        self.assertEqual(response.context["commercial"]["promotions"], [])
        self.assertContains(response, "طرح واجد شرایطی")

    def test_zero_inventory_is_not_missing_inventory(self):
        self.inventory.available_quantity = 0
        self.inventory.reserved_quantity = 0
        self.inventory.save()
        response = self.page()
        self.assertTrue(response.context["commercial"]["inventory"]["has_record"])
        self.assertEqual(response.context["commercial"]["inventory"]["sellable_quantity"], 0)
        self.assertContains(response, "ناموجود برای فروش")
        self.assertNotContains(response, "نبود داده به معنی")

    def test_missing_inventory_is_unavailable_not_zero(self):
        self.inventory.delete()
        response = self.page()
        self.assertIsNone(response.context["commercial"]["inventory"]["sellable_quantity"])
        self.assertContains(response, "نبود داده به معنی موجودی صفر نیست")
        self.assertNotContains(response, "ناموجود برای فروش")

    def test_low_inventory_uses_existing_classification(self):
        self.inventory.available_quantity = 6
        self.inventory.save()
        self.assertContains(self.page(), "موجودی کم")

    def test_current_context_does_not_use_or_mutate_historical_visit_snapshots(self):
        visit = self.visits[0]
        visit.visit_date = self.TODAY - timedelta(days=10)
        visit.save()
        historical = VisitCommercialSnapshot.objects.create(
            visit=visit, customer=self.customer, salesperson=self.rep,
            inventory_context={"sellable_quantity": 999},
        )
        customer_snapshot = VisitCustomerSnapshot.objects.create(visit=visit, customer=self.customer, total_orders=99)
        original = VisitCommercialSnapshot.objects.filter(pk=historical.pk).values().get()
        self.promotion("OLD-VISIT-OFFER", start_date=visit.visit_date, end_date=visit.visit_date)
        response = self.page(visit_id=visit.pk)
        self.assertEqual(response.context["as_of_date"], self.TODAY)
        self.assertEqual(response.context["commercial"]["inventory"]["sellable_quantity"], 17)
        self.assertEqual(response.context["commercial"]["promotions"], [])
        self.assertEqual(VisitCommercialSnapshot.objects.filter(pk=historical.pk).values().get(), original)
        customer_snapshot.refresh_from_db()
        self.assertEqual(customer_snapshot.total_orders, 99)

    def test_saved_recommendation_reason_confidence_signals_and_scores_are_preserved(self):
        response = self.page()
        self.assertEqual(response.context["recommendation"].pk, self.recommendation.pk)
        self.assertContains(response, self.recommendation.reason)
        self.assertContains(response, "72٪")
        self.assertContains(response, "شواهد متوسط")
        self.assertEqual(response.context["signals"][0]["score"], 35)
        self.assertEqual(response.context["components"][1]["value"], 0)
        self.assertContains(response, "چرخه خرید مجدد")
        self.assertContains(response, "شواهد ذخیره‌شده")
        self.assertContains(response, "دوباره محاسبه نشده‌اند")

    def test_missing_evidence_reason_and_product_metadata_are_truthful(self):
        self.recommendation.reason = ""
        self.recommendation.explanation_snapshot = {}
        self.recommendation.score_breakdown = {}
        self.recommendation.evidence_quality = "UNKNOWN"
        self.recommendation.save()
        self.product.description = ""
        self.product.package_size = ""
        self.product.save()
        response = self.page()
        self.assertEqual(response.context["signals"], [])
        self.assertContains(response, "دلیل متنی برای این پیشنهاد ثبت نشده")
        self.assertContains(response, "شواهد تفصیلی برای این پیشنهاد ثبت نشده")
        self.assertContains(response, "کیفیت شواهد ثبت نشده")
        self.assertContains(response, "توضیحات محصول ثبت نشده")

    def test_absent_or_inactive_recommendation_does_not_invent_explanation(self):
        self.recommendation.is_active = False
        self.recommendation.save()
        response = self.page()
        self.assertIsNone(response.context["recommendation"])
        self.assertContains(response, "پیشنهاد فعالی برای این محصول و مشتری ثبت نشده")
        self.assertNotContains(response, self.recommendation.reason)

    def test_customer360_links_preserve_rank_and_valid_own_visit(self):
        response = self.client.get("/customers/", {"customer_code": self.customer.customer_code,
                                                   "visit_id": self.visits[0].pk})
        self.assertEqual(response.status_code, 200)
        links = BriefLinkParser(response.content.decode()).links
        self.assertEqual([urlsplit(link).path for link in links], [
            reverse("product-commercial-brief", args=[self.product.product_code]),
            reverse("product-commercial-brief", args=[self.alternative.product_code]),
        ])
        for link in links:
            self.assertEqual(parse_qs(urlsplit(link).query)["visit_id"], [str(self.visits[0].pk)])
            self.assertEqual(self.client.get(link).status_code, 200)
        self.assertEqual([r.pk for r in response.context["recommendations"]],
                         [self.recommendation.pk, self.alternative_recommendation.pk])

    def test_manager_and_foreign_visit_entry_links_do_not_carry_visit(self):
        foreign = Visit.objects.create(salesperson=self.other_rep, customer=self.customer, visit_date=self.TODAY)
        for user, visit in ((self.user, foreign), (self.staff, self.visits[0])):
            self.client.force_login(user)
            response = self.client.get("/customers/", {"customer_code": self.customer.customer_code, "visit_id": visit.pk})
            self.assertEqual(response.status_code, 200)
            links = BriefLinkParser(response.content.decode()).links
            self.assertEqual(len(links), 2)
            self.assertTrue(all("visit_id" not in link for link in links))

    def test_get_and_evidence_expansion_have_no_writes_or_ai_invocation(self):
        before = CustomerRecommendation.objects.filter(pk=self.recommendation.pk).values().get()
        with patch("apps.ai.ollama_client.OllamaClient.generate") as llm, CaptureQueriesContext(connection) as queries:
            response = self.page(visit_id=self.visits[0].pk)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "<details", html=False)
        llm.assert_not_called()
        writes = [q["sql"] for q in queries if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))]
        self.assertEqual(writes, [])
        self.assertEqual(CustomerRecommendation.objects.filter(pk=self.recommendation.pk).values().get(), before)

    def test_post_is_not_supported_and_stored_copy_is_escaped(self):
        url = reverse("product-commercial-brief", args=[self.product.product_code])
        self.assertEqual(self.client.post(url, {"customer_code": self.customer.customer_code}).status_code, 405)
        self.recommendation.reason = '<script>alert("unsafe")</script>'
        self.recommendation.save()
        response = self.page()
        self.assertNotContains(response, '<script>alert("unsafe")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_business_evidence_contains_saved_reason_identity_and_key_values(self):
        response = self.page()
        business = response.content.decode().split('pb-business-content">', 1)[1].split(
            '<details class="pb-disclosure pb-technical-disclosure">', 1,
        )[0]
        for value in (self.recommendation.reason, "فروش مکمل", "72٪", "رتبه ثبت‌شده پیشنهاد",
                      "امتیاز نهایی ثبت‌شده", "چرخه خرید مجدد", "35", "اثر ثبت‌شده"):
            self.assertIn(value, business)
        self.assertEqual(response.context["active_signals"], response.context["signals"])

    def test_business_signals_select_only_saved_active_nonzero_values_in_source_order(self):
        self.recommendation.explanation_snapshot = {"signals": [
            {"name": "repurchase", "score": 35, "active": True},
            {"name": "association", "score": 0, "active": True},
            {"name": "promotion", "score": 12, "active": False},
            {"name": "historical_feedback", "score": -3, "active": True},
            {"name": "upsell", "score": None, "active": True},
            {"name": "similar_product", "score": "unavailable", "active": True},
        ]}
        self.recommendation.save()
        response = self.page()
        self.assertEqual([s["score"] for s in response.context["active_signals"]], [35, -3])
        summary = response.content.decode().split('class="pb-signal-cards">', 1)[1].split("</ul>", 1)[0]
        self.assertIn("چرخه خرید مجدد", summary)
        self.assertIn("بازخورد تاریخی", summary)
        self.assertNotIn("هم‌خریدی", summary)
        self.assertNotIn("ترویج فروش", summary)
        self.assertNotIn("فروش ارتقایی", summary)
        self.assertEqual(len(response.context["signals"]), 6)

    def test_complete_technical_signals_and_zero_score_components_remain_available(self):
        self.recommendation.explanation_snapshot["signals"].append(
            {"name": "association", "score": 0, "active": False},
        )
        self.recommendation.save()
        response = self.page()
        technical = response.content.decode().split('<details class="pb-disclosure pb-technical-disclosure">', 1)[1]
        self.assertIn("فهرست کامل شواهد ثبت‌شده", technical)
        self.assertIn("هم‌خریدی و فروش مکمل", technical)
        self.assertIn("غیرفعال", technical)
        self.assertIn("<strong>0</strong>", technical)
        self.assertIn("ترکیب امتیاز ثبت‌شده", technical)
        self.assertEqual([component["value"] for component in response.context["components"]], [35, 0])

    def test_technical_disclosure_is_nested_and_collapsed_by_default(self):
        html = self.page().content.decode()
        business = html.index('<details class="pb-disclosure pb-business-disclosure">')
        technical = html.index('<details class="pb-disclosure pb-technical-disclosure">')
        self.assertLess(business, technical)
        self.assertNotIn("</details>", html[business:technical])
        self.assertNotIn('<details class="pb-disclosure pb-technical-disclosure" open', html)
        self.assertContains(self.page(), "جزئیات فنی امتیازدهی")

    def test_no_active_nonzero_signal_uses_explicit_empty_business_summary(self):
        self.recommendation.explanation_snapshot = {"signals": [{"name": "repurchase", "score": 0, "active": True}]}
        self.recommendation.save()
        response = self.page()
        self.assertEqual(response.context["active_signals"], [])
        self.assertContains(response, "سیگنال فعال با اثر غیرصفر در شواهد ثبت‌شده موجود نیست")
        self.assertEqual(response.context["signals"][0]["score"], 0)

    def test_duplicate_product_description_is_suppressed_without_source_mutation(self):
        for description in (self.product.name, "  " + self.product.name.upper().replace(" ", "   ") + "\n"):
            self.product.description = description
            self.product.save()
            response = self.page()
            self.assertFalse(response.context["show_product_description"])
            self.assertNotContains(response, 'class="pb-description"')
            self.assertNotContains(response, "توضیحات محصول ثبت نشده است")
            self.product.refresh_from_db()
            self.assertEqual(self.product.description, description)
        self.product.description = "توضیحات متفاوت و ثبت‌شده"
        self.product.save()
        self.assertContains(self.page(), self.product.description)
