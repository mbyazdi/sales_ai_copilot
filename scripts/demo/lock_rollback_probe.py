"""Explicit, rollback-only service probe; never used by normal Demo startup.

Allocate explicit IDs inside the transaction so PostgreSQL nextval is never
called. Business validation, real runtime grants and locking remain unchanged.
The disposable integration runner must validate this before persistent use.
"""
from contextlib import ExitStack
from unittest.mock import patch
from uuid import uuid4

from common import require


def exercise(user, visit, recommendation):
    from django.db import connection, transaction
    from django.db.models import Max
    from apps.products.catalog import build_catalog
    from apps.recommendations.feedback import record_feedback
    from apps.recommendations.models import RecommendationFeedbackEvent
    from apps.sales_requests.models import (
        SalesRequest, SalesRequestLine, SalesRequestMutationReceipt, SalesRequestAcknowledgement,
    )
    from apps.sales_requests.basket import basket_quote, mutate_basket
    from apps.sales_requests.submission import review_request, submit_request
    from apps.visits.completion import complete_visit

    require(connection.vendor == 'postgresql' and visit.status == 'IN_PROGRESS'
            and recommendation.customer_id == visit.customer_id
            and not SalesRequest.objects.filter(visit=visit).exists(), 'Rollback probe prerequisites differ.')
    models = (SalesRequest, SalesRequestLine, SalesRequestMutationReceipt,
              SalesRequestAcknowledgement, RecommendationFeedbackEvent)
    with transaction.atomic(), ExitStack() as stack:
        for model in models:
            next_id = (model.objects.aggregate(value=Max('pk'))['value'] or 0) + 1
            def allocate(instance, counter=iter(range(next_id, next_id + 32))):
                return next(counter)
            stack.enter_context(patch.object(model._meta.pk, 'get_pk_value_on_save', side_effect=allocate))
        code = visit.customer.customer_code
        token = build_catalog(user, code, visit.pk)['catalog_context']
        feedback = dict(customer_code=code, command_uuid=uuid4(), recommendation_id=recommendation.pk,
                        action='LATER', reason_code='LATER', note='', expected_request_revision=None,
                        catalog_context=token)
        result = record_feedback(user, visit.pk, feedback)
        require(result[1:] == (201, False), 'Feedback rollback probe failed.')
        require(record_feedback(user, visit.pk, feedback) == (result[0], 201, True), 'Feedback replay differs.')
        quote = basket_quote(user, code, visit.pk, recommendation.product_id, 1)
        add = dict(customer_code=code, command_uuid=uuid4(), product_id=recommendation.product_id,
                   quantity=1, catalog_context=token, expected_request_revision=None,
                   accepted_quote_fingerprint=quote['quote_fingerprint'])
        require(mutate_basket(user, visit.pk, 'ADD_PRODUCT', add)[1:] == (201, False), 'Basket probe failed.')
        review = review_request(user, code, visit.pk)
        submit = dict(customer_code=code, command_uuid=uuid4(), catalog_context=token,
                      expected_request_revision=review['request']['revision'],
                      accepted_review_fingerprint=review['review_fingerprint'])
        submitted = submit_request(user, visit.pk, submit)
        require(submitted[1:] == (201, False), 'Submit rollback probe failed.')
        require(submit_request(user, visit.pk, submit) == (submitted[0], 201, True), 'Submit replay differs.')
        command = dict(customer_code=code, command_uuid=uuid4())
        completed = complete_visit(user, visit.pk, command)
        require(completed[1:] == (200, False) and completed[0]['acknowledgement'] is not None,
                'Completion/acknowledgement rollback probe failed.')
        require(complete_visit(user, visit.pk, command) == (completed[0], 200, True), 'Completion replay differs.')
        evidence = dict(feedback='LATER', request_status=SalesRequest.objects.get(visit=visit).status,
                        completion=completed[0]['visit']['status'],
                        acknowledgements=SalesRequestAcknowledgement.objects.filter(sales_request__visit=visit).count(),
                        events=list(RecommendationFeedbackEvent.objects.filter(visit=visit)
                                    .order_by('pk').values_list('event_type', 'reason_code')))
        transaction.set_rollback(True)
    return evidence
