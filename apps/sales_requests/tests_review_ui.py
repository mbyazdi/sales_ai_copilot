"""Review/result shells, safe navigation and unchanged frozen message evidence."""
from django.apps import apps
from django.test import TestCase
from django.urls import reverse
from urllib.parse import parse_qs, urlsplit

from apps.products import tests_catalog
from apps.sales_requests.models import SalesRequest
from .tests_submission import SubmissionFixtures
from .submission import MESSAGE_DISCLOSURE


class SalesRequestReviewUITests(SubmissionFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        tests_catalog.CatalogBackendTests.setUpTestData.__func__(cls)

    def setUp(self):
        self.prepare()
        self.client.force_login(self.user)

    def url(self, result=False):
        return reverse('sales-request-result' if result else 'sales-request-review', args=[self.customer.customer_code,self.visit.pk])

    def page(self, result=False, **query):
        return self.client.get(self.url(result), {'catalog_context':self.context, **query})

    def test_review_page_is_get_only_no_creation_and_uses_authorized_api(self):
        before=self.rows();response=self.page()
        self.assertEqual(response.status_code,200)
        for value in ('lang="fa" dir="rtl"','data-request-page="review"','id="requestConfirmDialog"',
                      'id="requestPrepare"','id="requestRecover"','id="requestRetry"','name="csrfmiddlewaretoken"',
                      'core/js/sales_request_review.js','core/css/sales_request_review.css'):
            self.assertContains(response,value)
        self.assertContains(response,reverse('visit-request-review-v1',args=[self.visit.pk]))
        self.assertContains(response,reverse('visit-request-submit-v1',args=[self.visit.pk]))
        self.assertEqual(self.rows(),before)
        self.assertEqual(self.client.head(self.url()).status_code,200)
        self.assertEqual(self.client.post(self.url()).status_code,405)
        self.assertEqual(self.rows(),before)

    def test_basket_return_preserves_signed_context_filters_and_has_no_arbitrary_redirect(self):
        response=self.page(q='محصول',priority='ordinary',page='2',category_id=str(self.other_category.pk),return_url='https://evil.example/')
        url=response.context['basket_url'];query=parse_qs(urlsplit(url).query)
        self.assertEqual(query['catalog_context'],[self.context])
        self.assertEqual(query['priority'],['ordinary'])
        self.assertEqual(query['q'],['محصول'])
        self.assertEqual(query['page'],['2'])
        self.assertEqual(urlsplit(url).fragment,'basketPanel')
        self.assertFalse(urlsplit(url).netloc)
        self.assertNotContains(response,'evil.example')

    def test_wrong_context_invalid_filter_and_foreign_visits_fail_safely(self):
        self.assertEqual(self.page(catalog_context='tampered').status_code,409)
        self.assertEqual(self.page(priority='invalid').status_code,409)
        self.assertEqual(self.client.get(reverse('sales-request-review',args=[self.customer.customer_code,self.foreign_visit.pk])).status_code,404)

    def test_authentication_roles_and_assignment_protect_both_pages(self):
        for actor in (self.foreign_user,self.staff,self.no_profile):
            self.client.force_login(actor)
            for result in (False,True):
                self.assertIn(self.page(result).status_code,(403,404))
        self.client.logout()
        self.assertEqual(self.client.get(self.url()).status_code,302)
        self.assertEqual(self.client.get(self.url(True)).status_code,302)

    def test_submitted_result_copy_omits_delivery_disclosure_without_altering_snapshot(self):
        self.add();self.assertEqual(self.submit().status_code,201)
        request=SalesRequest.objects.get();stored=request.prepared_message_snapshot;before=self.rows()
        response=self.page(True)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'data-request-page="result"')
        self.assertContains(response,request.number)
        self.assertContains(response,'id="requestCopy"')
        self.assertContains(response,'id="visitCompletionGuidance"')
        self.assertContains(response,'پایان ویزیت مرحله‌ای جداگانه است.')
        self.assertContains(response,MESSAGE_DISCLOSURE)
        self.assertNotIn(MESSAGE_DISCLOSURE,response.context['copy_message'])
        self.assertEqual(response.context['copy_message'],stored.removesuffix('\n'+MESSAGE_DISCLOSURE))
        self.assertNotContains(response,'id="requestConfirm"')
        self.assertNotContains(response,'visit-complete')
        self.assertEqual(response['Cache-Control'],'no-store, private')
        self.assertEqual(self.rows(),before)
        request.refresh_from_db();self.assertEqual(request.prepared_message_snapshot,stored)

    def test_result_uses_stored_customer_identity_and_escapes_names_message(self):
        self.customer.name='<script>مشتری</script>';self.customer.save(update_fields=['name'])
        self.add();self.submit();self.customer.name='نام جدید';self.customer.save(update_fields=['name'])
        response=self.page(True)
        self.assertContains(response,'&lt;script&gt;مشتری&lt;/script&gt;')
        self.assertNotContains(response,'<script>مشتری</script>')
        self.assertEqual(response.context['customer']['name'],'<script>مشتری</script>')

    def test_draft_result_redirects_to_review_without_submission(self):
        self.add();before=self.rows();response=self.page(True)
        self.assertEqual(response.status_code,302)
        self.assertTrue(response.url.startswith(self.url()))
        self.assertEqual(self.rows(),before)
        self.assertEqual(SalesRequest.objects.get().status,'DRAFT')

    def test_guided_review_action_preserves_existing_card_slots(self):
        response=self.client.get(reverse('recommendation-presentation',args=[self.customer.customer_code]),{'visit_id':self.visit.pk})
        self.assertContains(response,'id="basketReview"')
        self.assertContains(response,'مرور و ثبت درخواست')
        for value in ('gc-quantity-slot','gc-price-slot','data-basket-add','basketDialog','data-feedback-reject'):
            self.assertContains(response,value)
