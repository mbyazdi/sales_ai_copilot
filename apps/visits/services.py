from collections import defaultdict

from django.db.models import (
    Count,
    Sum,
    Avg,
    Q,
)

from apps.recommendations.models import (
    CustomerRecommendation,
)

from .models import (
    Visit,
    FollowUpTask,
    SalesOutcome,
)

from apps.core.commercial_context import (
    build_product_commercial_contexts,
)
from apps.core.commercial_decision import (
    build_base_sales_session,
)
from apps.targets.services import (
    get_salesperson_target_progress,
)

OUTCOME_PRIORITY = {
    "PURCHASED": 5,
    "INTERESTED": 4,
    "FOLLOW_UP": 3,
    "REJECTED": 2,
    "NOT_PRESENTED": 1,
}

def build_pre_visit_briefs(
    visits,
    salesperson,
    target_progress=None,
    as_of_date=None,
):
    """
    Build normalized pre-visit briefs for a batch
    of visits.

    This is intentionally based only on existing,
    authoritative backend data.

    Commercial Target, Promotion and Inventory
    will be added in later V2 stages.
    """

    visits = list(visits)

    if not visits:
        return {}

    target_progress = list(
        target_progress or []
    )

    customer_ids = {
        visit.customer_id
        for visit in visits
    }

    # =====================================================
    # PRIMARY RECOMMENDATIONS
    # =====================================================

    primary_recommendations = {}

    recommendations = (
        CustomerRecommendation.objects
        .filter(
            customer_id__in=customer_ids,
            is_active=True,
        )
        .select_related(
            "product",
            "product__category",
        )
        .order_by(
            "customer_id",
            "rank",
            "-score",
            "id",
        )
    )

    for recommendation in recommendations:

        if (
            recommendation.customer_id
            not in primary_recommendations
        ):
            primary_recommendations[
                recommendation.customer_id
            ] = recommendation

    # =====================================================
    # COMMERCIAL CONTEXT
    # =====================================================

    commercial_pairs = []

    for visit in visits:

        primary = (
            primary_recommendations.get(
                visit.customer_id
            )
        )

        if not primary:
            continue

        commercial_pairs.append(
            (
                primary.product,
                visit.customer,
            )
        )

    commercial_contexts = (
        build_product_commercial_contexts(
            product_customer_pairs=(
                commercial_pairs
            ),
            as_of_date=as_of_date,
        )
    )

    # =====================================================
    # OPEN FOLLOW-UPS
    # =====================================================

    followups_by_customer = defaultdict(
        list
    )

    followups = (
        FollowUpTask.objects
        .filter(
            salesperson=salesperson,
            customer_id__in=customer_ids,
            status=FollowUpTask.Status.OPEN,
        )
        .order_by(
            "customer_id",
            "due_date",
            "id",
        )
    )

    for followup in followups:

        followups_by_customer[
            followup.customer_id
        ].append(
            followup
        )

    # =====================================================
    # BUILD BRIEFS
    # =====================================================

    briefs = {}

    for visit in visits:

        customer = visit.customer

        customer_360 = getattr(
            customer,
            "customer_360",
            None,
        )

        primary = primary_recommendations.get(
            customer.id
        )

        commercial_context = None

        if primary:

            commercial_context = (
                commercial_contexts.get(
                    (
                        primary.product_id,
                        customer.id,
                    )
                )
            )

        target_relevance = []

        if primary:

            primary_product = (
                primary.product
            )

            for target in target_progress:

                scope = target.get(
                    "scope",
                    {},
                )

                scope_type = scope.get(
                    "type"
                )

                scope_code = scope.get(
                    "code"
                )

                is_relevant = False

                if (
                    scope_type
                    == "PRODUCT"
                    and scope_code
                    == primary_product.product_code
                ):
                    is_relevant = True

                elif (
                    scope_type
                    == "CATEGORY"
                    and primary_product.category
                    and scope_code
                    == primary_product.category.code
                ):
                    is_relevant = True

                elif (
                    scope_type
                    == "PRODUCT_GROUP"
                    and scope_code
                    == primary_product.product_group
                ):
                    is_relevant = True

                if is_relevant:

                    target_relevance.append({
                        "target_id": (
                            target["id"]
                        ),

                        "scope_type": (
                            scope_type
                        ),

                        "scope_code": (
                            scope_code
                        ),

                        "scope_name": (
                            scope.get(
                                "name",
                                "",
                            )
                        ),

                        "target_unit": (
                            target[
                                "target_unit"
                            ]
                        ),

                        "target_value": (
                            target[
                                "target_value"
                            ]
                        ),

                        "actual_value": (
                            target[
                                "actual_value"
                            ]
                        ),

                        "remaining_value": (
                            target[
                                "remaining_value"
                            ]
                        ),

                        "achievement_percent": (
                            target[
                                "achievement_percent"
                            ]
                        ),
                    })

        customer_followups = (
            followups_by_customer.get(
                customer.id,
                [],
            )
        )

        commercial_decision = (
            build_base_sales_session(
                customer=customer,
                customer_360=customer_360,
                primary_recommendation=primary,
                target_relevance=(
                    target_relevance
                ),
                commercial_context=(
                    commercial_context
                ),
            )
        )

        next_followup = (
            customer_followups[0]
            if customer_followups
            else None
        )

        priority_score = 0
        priority_reasons = []

        if primary:

            recommendation_score = float(
                primary.score or 0
            )

            confidence_score = float(
                primary.confidence_score or 0
            )

            if recommendation_score >= 80:
                priority_score += 3
                priority_reasons.append(
                    "Strong recommendation score"
                )

            elif recommendation_score >= 50:
                priority_score += 2
                priority_reasons.append(
                    "Good recommendation score"
                )

            elif recommendation_score > 0:
                priority_score += 1
                priority_reasons.append(
                    "Active recommendation"
                )

            if confidence_score >= 80:
                priority_score += 2
                priority_reasons.append(
                    "High recommendation confidence"
                )

            elif confidence_score >= 60:
                priority_score += 1
                priority_reasons.append(
                    "Moderate recommendation confidence"
                )

        if customer_360:

            if (
                customer_360.segment
                == "HIGH_VALUE"
            ):
                priority_score += 2
                priority_reasons.append(
                    "High-value customer"
                )

            elif (
                customer_360.segment
                == "GROWTH"
            ):
                priority_score += 1
                priority_reasons.append(
                    "Growth customer"
                )

        if customer_followups:
            priority_score += 2
            priority_reasons.append(
                "Open follow-up exists"
            )

        if priority_score >= 6:
            priority_level = "HIGH"

        elif priority_score >= 3:
            priority_level = "MEDIUM"

        else:
            priority_level = "NORMAL"

        briefs[visit.id] = {
            "visit_id": visit.id,
            "priority_score":
                priority_score,

            "priority_level":
                priority_level,

            "priority_reasons":
                priority_reasons,

            "target_relevance": (
                target_relevance
            ),
            "commercial_context": (
                commercial_context
            ),
            "commercial_decision": {
                "commercial_score": (
                    commercial_decision[
                        "commercial_score"
                    ]
                ),

                "commercial_priority": (
                    commercial_decision[
                        "commercial_priority"
                    ]
                ),

                "decision_reasons": (
                    commercial_decision[
                        "decision_reasons"
                    ]
                ),

                "why_now": (
                    commercial_decision[
                        "why_now"
                    ]
                ),

                "commercial_blocked": (
                    commercial_decision[
                        "commercial_blocked"
                    ]
                ),

                "next_best_action": (
                    commercial_decision[
                        "next_best_action"
                    ]
                ),

                "talking_point": (
                    commercial_decision[
                        "talking_point"
                    ]
                ),
            },
            "customer": {
                "customer_code":
                    customer.customer_code,

                "name":
                    customer.name,

                "grade": (
                    customer.grade.code
                    if customer.grade
                    else None
                ),

                "segment": (
                    customer_360.segment
                    if customer_360
                    else None
                ),

                "days_since_last_purchase": (
                    customer_360
                    .days_since_last_purchase
                    if customer_360
                    else None
                ),

                "top_category": (
                    customer_360.top_category
                    if customer_360
                    else None
                ),
            },

            "primary_recommendation": (
                {
                    "id":
                        primary.id,

                    "product_code":
                        primary.product.product_code,

                    "product_name":
                        primary.product.name,

                    "recommendation_type":
                        primary.recommendation_type,

                    "score":
                        primary.score,

                    "confidence_score":
                        primary.confidence_score,

                    "evidence_quality":
                        primary.evidence_quality,

                    "reason":
                        primary.reason,
                }
                if primary
                else None
            ),

            "open_follow_up_count": (
                len(
                    customer_followups
                )
            ),

            "next_follow_up": (
                {
                    "id":
                        next_followup.id,

                    "due_date":
                        next_followup.due_date,

                    "notes":
                        next_followup.notes,
                }
                if next_followup
                else None
            ),
        }

    return briefs

def build_pre_visit_intelligence_window(
    salesperson,
    start_date,
    end_date,
    statuses=None,
):
    """
    Build canonical pre-visit intelligence for a
    salesperson over a date window.

    No intelligence is persisted here.
    This is the orchestration layer used by
    runtime and future nightly-ready workflows.
    """

    if start_date > end_date:
        raise ValueError(
            "start_date cannot be after end_date."
        )

    if statuses is None:
        statuses = [
            Visit.VisitStatus.PLANNED,
            Visit.VisitStatus.IN_PROGRESS,
        ]

    visits = list(
        Visit.objects
        .filter(
            salesperson=salesperson,
            visit_date__gte=start_date,
            visit_date__lte=end_date,
            status__in=statuses,
        )
        .select_related(
            "customer",
            "customer__grade",
            "customer__customer_360",
        )
        .order_by(
            "visit_date",
            "id",
        )
    )

    if not visits:
        return {
            "salesperson": {
                "employee_code":
                    salesperson.employee_code,
                "full_name":
                    salesperson.full_name,
            },
            "start_date": start_date,
            "end_date": end_date,
            "visit_count": 0,
            "items": [],
        }

    # ==========================================
    # GROUP VISITS BY DATE
    # ==========================================

    visits_by_date = {}

    for visit in visits:

        visits_by_date.setdefault(
            visit.visit_date,
            [],
        ).append(
            visit
        )

    items = []

    # Target progress is date-sensitive.
    # Build briefs separately for each visit date.
    for visit_date, date_visits in (
        visits_by_date.items()
    ):

        target_progress = (
            get_salesperson_target_progress(
                salesperson=salesperson,
                as_of_date=visit_date,
            )
        )

        briefs = build_pre_visit_briefs(
            visits=date_visits,
            salesperson=salesperson,
            target_progress=target_progress,
            as_of_date=visit_date,
        )

        for visit in date_visits:

            brief = briefs.get(
                visit.id,
                {},
            )

            items.append({
                "visit": {
                    "id": visit.id,
                    "visit_date":
                        visit.visit_date,
                    "status":
                        visit.status,
                },

                "customer": (
                    brief.get(
                        "customer"
                    )
                ),

                "primary_recommendation": (
                    brief.get(
                        "primary_recommendation"
                    )
                ),

                "visit_priority": {
                    "score": (
                        brief.get(
                            "priority_score"
                        )
                    ),
                    "level": (
                        brief.get(
                            "priority_level"
                        )
                    ),
                    "reasons": (
                        brief.get(
                            "priority_reasons",
                            [],
                        )
                    ),
                },

                "target_relevance": (
                    brief.get(
                        "target_relevance",
                        [],
                    )
                ),

                "commercial_context": (
                    brief.get(
                        "commercial_context"
                    )
                ),

                "commercial_decision": (
                    brief.get(
                        "commercial_decision"
                    )
                ),

                "follow_up": {
                    "open_count": (
                        brief.get(
                            "open_follow_up_count",
                            0,
                        )
                    ),
                    "next_due_date": (
                        brief.get(
                            "next_follow_up_date"
                        )
                    ),
                },
            })

    items.sort(
        key=lambda item: (
            item["visit"]["visit_date"],
            -(
                item[
                    "visit_priority"
                ][
                    "score"
                ]
                or 0
            ),
            item["visit"]["id"],
        )
    )

    return {
        "salesperson": {
            "employee_code":
                salesperson.employee_code,
            "full_name":
                salesperson.full_name,
        },
        "start_date": start_date,
        "end_date": end_date,
        "visit_count": len(items),
        "items": items,
    }

def resolve_recommendation_outcome(
    visit_id,
    recommendation_id,
):
    """
    Resolve all raw SalesOutcome records belonging to
    one Visit + one Recommendation into one final outcome.

    Raw outcome records are NOT modified or deleted.
    """

    outcomes = list(
        SalesOutcome.objects
        .filter(
            visit_id=visit_id,
            recommendation_id=recommendation_id,
        )
        .order_by("-created_at", "-id")
    )

    if not outcomes:
        return None

    final_outcome = max(
        outcomes,
        key=lambda item: OUTCOME_PRIORITY.get(
            item.outcome,
            0,
        ),
    )

    quantity = 0
    sales_amount = 0

    if final_outcome.outcome == "PURCHASED":

        purchase_records = [
            item
            for item in outcomes
            if item.outcome == "PURCHASED"
        ]

        purchase_with_value = next(
            (
                item
                for item in purchase_records
                if (
                    (item.quantity or 0) > 0
                    or (item.sales_amount or 0) > 0
                )
            ),
            None,
        )

        if purchase_with_value:
            quantity = purchase_with_value.quantity or 0
            sales_amount = (
                purchase_with_value.sales_amount or 0
            )

    return {
        "visit_id": visit_id,
        "recommendation_id": recommendation_id,
        "outcome": final_outcome.outcome,
        "quantity": quantity,
        "sales_amount": sales_amount,
        "events_count": len(outcomes),
        "last_event_id": outcomes[0].id,
        "last_event_at": outcomes[0].created_at,
    }

def capture_visit_customer_snapshot(
    visit,
):
    """
    Capture the immutable customer feature snapshot
    for a visit at visit-start time.

    The operation is idempotent:
    an existing snapshot is returned unchanged.
    """

    if visit is None:

        raise ValueError(
            "visit is required."
        )

    from apps.visits.models import (
        VisitCustomerSnapshot,
    )

    existing_snapshot = (
        VisitCustomerSnapshot.objects
        .filter(
            visit=visit
        )
        .first()
    )

    if existing_snapshot:

        return existing_snapshot

    customer = visit.customer

    customer_360 = getattr(
        customer,
        "customer_360",
        None,
    )

    snapshot = (
        VisitCustomerSnapshot.objects.create(
            visit=visit,

            customer=customer,

            customer_grade_code=(
                customer.grade.code
                if customer.grade
                else None
            ),

            segment=(
                customer_360.segment
                if customer_360
                else None
            ),

            total_orders=(
                customer_360.total_orders
                if customer_360
                else 0
            ),

            total_sales_amount=(
                customer_360.total_sales_amount
                if customer_360
                else 0
            ),

            average_order_value=(
                customer_360.average_order_value
                if customer_360
                else 0
            ),

            days_since_last_purchase=(
                customer_360
                .days_since_last_purchase
                if customer_360
                else 0
            ),

            recency_score=(
                customer_360.recency_score
                if customer_360
                else 0
            ),

            frequency_score=(
                customer_360.frequency_score
                if customer_360
                else 0
            ),

            monetary_score=(
                customer_360.monetary_score
                if customer_360
                else 0
            ),

            rfm_score=(
                customer_360.rfm_score
                if customer_360
                else 0
            ),

            top_category=(
                customer_360.top_category
                if customer_360
                else None
            ),

            top_product_code=(
                customer_360.top_product_code
                if customer_360
                else None
            ),

            source_customer360_calculated_at=(
                customer_360.calculated_at
                if customer_360
                else None
            ),
        )
    )

    return snapshot

def capture_visit_commercial_snapshot(
    visit,
):
    """
    Capture the immutable commercial decision snapshot
    for a visit at visit-start time.

    The operation is idempotent:
    an existing snapshot is returned unchanged.

    The snapshot uses the same canonical pre-visit
    intelligence pipeline used by runtime guidance.
    """

    if visit is None:

        raise ValueError(
            "visit is required."
        )

    import json

    from django.core.serializers.json import (
        DjangoJSONEncoder,
    )

    from apps.visits.models import (
        VisitCommercialSnapshot,
    )

    existing_snapshot = (
        VisitCommercialSnapshot.objects
        .filter(
            visit=visit
        )
        .first()
    )

    if existing_snapshot:

        return existing_snapshot

    customer = visit.customer
    salesperson = visit.salesperson

    target_progress = (
        get_salesperson_target_progress(
            salesperson=salesperson,
            as_of_date=visit.visit_date,
        )
    )

    briefs = (
        build_pre_visit_briefs(
            visits=[
                visit,
            ],
            salesperson=salesperson,
            target_progress=(
                target_progress
            ),
            as_of_date=visit.visit_date,
        )
    )

    brief = (
        briefs.get(
            visit.id
        )
        or {}
    )

    commercial_decision = (
        brief.get(
            "commercial_decision"
        )
        or {}
    )

    primary_recommendation = (
        brief.get(
            "primary_recommendation"
        )
        or {}
    )

    commercial_context = (
        brief.get(
            "commercial_context"
        )
        or {}
    )

    target_context = (
        brief.get(
            "target_relevance"
        )
        or []
    )

    inventory_context = (
        commercial_context.get(
            "inventory"
        )
        or {}
    )

    promotion_context = (
        commercial_context.get(
            "promotions"
        )
        or []
    )

    commercial_signals = []

    if target_context:

        commercial_signals.append(
            "TARGET_RELEVANT"
        )

    if promotion_context:

        commercial_signals.append(
            "ELIGIBLE_PROMOTION"
        )

    if (
        inventory_context.get(
            "is_in_stock"
        )
        is True
    ):

        commercial_signals.append(
            "IN_STOCK"
        )

    if (
        inventory_context.get(
            "is_low_stock"
        )
        is True
    ):

        commercial_signals.append(
            "LOW_STOCK"
        )

    if (
        inventory_context.get(
            "is_in_stock"
        )
        is False
    ):

        commercial_signals.append(
            "OUT_OF_STOCK"
        )

    def to_json_safe(value):

        return json.loads(
            json.dumps(
                value,
                cls=DjangoJSONEncoder,
            )
        )

    snapshot = (
        VisitCommercialSnapshot.objects.create(
            visit=visit,

            customer=customer,

            salesperson=salesperson,

            primary_product_code=(
                primary_recommendation.get(
                    "product_code"
                )
            ),

            recommendation_type=(
                primary_recommendation.get(
                    "recommendation_type"
                )
            ),

            commercial_score=(
                commercial_decision.get(
                    "commercial_score"
                )
            ),

            commercial_priority=(
                commercial_decision.get(
                    "commercial_priority"
                )
            ),

            commercial_blocked=bool(
                commercial_decision.get(
                    "commercial_blocked",
                    False,
                )
            ),

            target_context=(
                to_json_safe(
                    target_context
                )
            ),

            inventory_context=(
                to_json_safe(
                    inventory_context
                )
            ),

            promotion_context=(
                to_json_safe(
                    promotion_context
                )
            ),

            commercial_signals=(
                to_json_safe(
                    commercial_signals
                )
            ),

            decision_reasons=(
                to_json_safe(
                    commercial_decision.get(
                        "decision_reasons"
                    )
                    or []
                )
            ),

            why_now=(
                to_json_safe(
                    commercial_decision.get(
                        "why_now"
                    )
                    or []
                )
            ),
        )
    )

    return snapshot

def build_post_visit_intelligence(
    visit,
):
    """
    Build canonical post-visit intelligence for one visit.

    This service does not modify raw SalesOutcome records.

    Final recommendation outcomes are resolved through
    resolve_recommendation_outcome(), which remains the
    authoritative outcome-resolution rule.

    The returned structure is intentionally normalized so
    it can later be consumed by:

    - Customer 360
    - Sales Copilot
    - Management analytics
    - Learning dataset generation
    - Future ML feature pipelines
    """

    if visit is None:

        raise ValueError(
            "visit is required."
        )

    # =====================================================
    # RECOMMENDATION OUTCOME PAIRS
    # =====================================================

    outcome_pairs = list(
        SalesOutcome.objects
        .filter(
            visit=visit,
            recommendation__isnull=False,
        )
        .order_by()
        .values(
            "recommendation_id",
        )
        .distinct()
    )

    recommendation_ids = [
        item["recommendation_id"]
        for item in outcome_pairs
        if item["recommendation_id"]
    ]

    recommendations = {
        recommendation.id: recommendation
        for recommendation in (
            CustomerRecommendation.objects
            .filter(
                id__in=recommendation_ids,
                customer=visit.customer,
            )
            .select_related(
                "product",
                "product__category",
            )
        )
    }

    # =====================================================
    # RESOLVED RECOMMENDATION OUTCOMES
    # =====================================================

    recommendation_outcomes = []

    summary = {
        "resolved_recommendations": 0,
        "purchased": 0,
        "interested": 0,
        "follow_up": 0,
        "rejected": 0,
        "not_presented": 0,
        "total_quantity": 0,
        "total_revenue": 0.0,
    }

    for recommendation_id in recommendation_ids:

        recommendation = (
            recommendations.get(
                recommendation_id
            )
        )

        if recommendation is None:
            continue

        resolved = (
            resolve_recommendation_outcome(
                visit_id=visit.id,
                recommendation_id=(
                    recommendation_id
                ),
            )
        )

        if not resolved:
            continue

        outcome_name = (
            resolved["outcome"]
        )

        quantity = int(
            resolved["quantity"] or 0
        )

        sales_amount = float(
            resolved["sales_amount"] or 0
        )

        product = (
            recommendation.product
        )

        recommendation_outcomes.append({
            "recommendation_id": (
                recommendation.id
            ),

            "recommendation_type": (
                recommendation
                .recommendation_type
            ),

            "recommendation_rank": (
                recommendation.rank
            ),

            "recommendation_score": (
                float(
                    recommendation.score
                    or 0
                )
            ),

            "product": {
                "id": product.id,

                "code": (
                    product.product_code
                ),

                "name": (
                    product.name
                ),

                "category": (
                    product.category.name
                    if product.category
                    else None
                ),
            },

            "final_outcome": (
                outcome_name
            ),

            "quantity": quantity,

            "sales_amount": (
                sales_amount
            ),

            "events_count": (
                resolved[
                    "events_count"
                ]
            ),

            "last_event_id": (
                resolved[
                    "last_event_id"
                ]
            ),

            "last_event_at": (
                resolved[
                    "last_event_at"
                ]
            ),
        })

        summary[
            "resolved_recommendations"
        ] += 1

        if outcome_name == "PURCHASED":

            summary["purchased"] += 1

        elif outcome_name == "INTERESTED":

            summary["interested"] += 1

        elif outcome_name == "FOLLOW_UP":

            summary["follow_up"] += 1

        elif outcome_name == "REJECTED":

            summary["rejected"] += 1

        elif outcome_name == "NOT_PRESENTED":

            summary[
                "not_presented"
            ] += 1

        summary[
            "total_quantity"
        ] += quantity

        summary[
            "total_revenue"
        ] += sales_amount

    # =====================================================
    # UNATTRIBUTED OUTCOME EVENTS
    # =====================================================

    unattributed_outcome_events = (
        SalesOutcome.objects
        .filter(
            visit=visit,
            recommendation__isnull=True,
        )
        .count()
    )

    # =====================================================
    # FOLLOW-UP STATE
    # =====================================================

    follow_up_tasks = list(
        FollowUpTask.objects
        .filter(
            visit=visit,
        )
        .order_by(
            "due_date",
            "id",
        )
    )

    follow_up_summary = {
        "total": len(
            follow_up_tasks
        ),

        "open": 0,
        "done": 0,
        "cancelled": 0,

        "next_open_task": None,
    }

    for task in follow_up_tasks:

        if (
            task.status
            == FollowUpTask.Status.OPEN
        ):

            follow_up_summary[
                "open"
            ] += 1

            if (
                follow_up_summary[
                    "next_open_task"
                ]
                is None
            ):

                follow_up_summary[
                    "next_open_task"
                ] = {
                    "id": task.id,
                    "due_date": (
                        task.due_date
                    ),
                    "notes": (
                        task.notes
                    ),
                }

        elif (
            task.status
            == FollowUpTask.Status.DONE
        ):

            follow_up_summary[
                "done"
            ] += 1

        elif (
            task.status
            == FollowUpTask.Status.CANCELLED
        ):

            follow_up_summary[
                "cancelled"
            ] += 1

    # =====================================================
    # LEARNING READINESS
    # =====================================================

    is_final_visit = (
        visit.status
        in {
            Visit.VisitStatus.COMPLETED,
            Visit.VisitStatus.CANCELLED,
        }
    )

    learning_ready = (
        is_final_visit
        and bool(
            recommendation_outcomes
        )
    )

    # =====================================================
    # FINAL NORMALIZED RECORD
    # =====================================================

    return {
        "visit": {
            "id": visit.id,

            "visit_date": (
                visit.visit_date
            ),

            "status": (
                visit.status
            ),

            "is_final": (
                is_final_visit
            ),

            "customer": {
                "id": (
                    visit.customer_id
                ),

                "customer_code": (
                    visit
                    .customer
                    .customer_code
                ),

                "name": (
                    visit
                    .customer
                    .name
                ),
            },

            "salesperson": {
                "id": (
                    visit.salesperson_id
                ),

                "employee_code": (
                    visit
                    .salesperson
                    .employee_code
                ),

                "full_name": (
                    visit
                    .salesperson
                    .full_name
                ),
            },
        },

        "recommendation_outcomes": (
            recommendation_outcomes
        ),

        "summary": (
            summary
        ),

        "follow_up": (
            follow_up_summary
        ),

        "unattributed_outcome_events": (
            unattributed_outcome_events
        ),

        "learning": {
            "ready": (
                learning_ready
            ),

            "reason": (
                "FINAL_VISIT_WITH_RESOLVED_OUTCOME"
                if learning_ready
                else (
                    "VISIT_NOT_FINAL"
                    if not is_final_visit
                    else "NO_RESOLVED_RECOMMENDATION_OUTCOME"
                )
            ),

            "ml_prediction_used": False,

            "model_version": None,
        },
    }

def build_customer_outcome_history(
    customer,
    limit=10,
):
    """
    Build factual historical outcome context for one customer.

    Only completed/cancelled visits are considered historical.

    No prediction or interpretation is performed here.
    The output is intentionally normalized for:

    - Sales AI Context
    - Customer 360
    - Post-Visit Intelligence
    - Future learning dataset generation
    """

    if customer is None:

        raise ValueError(
            "customer is required."
        )

    if limit is None or limit < 1:

        raise ValueError(
            "limit must be at least 1."
        )

    # =====================================================
    # HISTORICAL FINAL VISITS
    # =====================================================

    visits = list(
        Visit.objects
        .filter(
            customer=customer,
            status__in=[
                Visit.VisitStatus.COMPLETED,
                Visit.VisitStatus.CANCELLED,
            ],
        )
        .select_related(
            "customer",
            "salesperson",
        )
        .order_by(
            "-visit_date",
            "-id",
        )[:limit]
    )

    history = []

    totals = {
        "visits": 0,
        "resolved_recommendations": 0,
        "purchased": 0,
        "interested": 0,
        "follow_up": 0,
        "rejected": 0,
        "not_presented": 0,
        "total_quantity": 0,
        "total_revenue": 0.0,
    }

    for visit in visits:

        intelligence = (
            build_post_visit_intelligence(
                visit=visit
            )
        )

        summary = (
            intelligence[
                "summary"
            ]
        )

        history.append({
            "visit": (
                intelligence[
                    "visit"
                ]
            ),

            "summary": summary,

            "recommendation_outcomes": (
                intelligence[
                    "recommendation_outcomes"
                ]
            ),

            "follow_up": (
                intelligence[
                    "follow_up"
                ]
            ),
        })

        totals["visits"] += 1

        totals[
            "resolved_recommendations"
        ] += (
            summary[
                "resolved_recommendations"
            ]
        )

        totals[
            "purchased"
        ] += (
            summary[
                "purchased"
            ]
        )

        totals[
            "interested"
        ] += (
            summary[
                "interested"
            ]
        )

        totals[
            "follow_up"
        ] += (
            summary[
                "follow_up"
            ]
        )

        totals[
            "rejected"
        ] += (
            summary[
                "rejected"
            ]
        )

        totals[
            "not_presented"
        ] += (
            summary[
                "not_presented"
            ]
        )

        totals[
            "total_quantity"
        ] += (
            summary[
                "total_quantity"
            ]
        )

        totals[
            "total_revenue"
        ] += (
            summary[
                "total_revenue"
            ]
        )

    return {
        "customer": {
            "id": (
                customer.id
            ),

            "customer_code": (
                customer.customer_code
            ),

            "name": (
                customer.name
            ),
        },

        "history_count": (
            len(history)
        ),

        "totals": (
            totals
        ),

        "history": (
            history
        ),
    }

def get_recommendation_performance(customer=None):
    """
    Calculate recommendation performance using
    resolved final outcomes per Visit + Recommendation.
    """

    from collections import defaultdict

    from apps.visits.models import SalesOutcome

    queryset = (
        SalesOutcome.objects
        .filter(
            recommendation__isnull=False,
        )
        .select_related(
            "visit",
            "recommendation",
        )
    )

    if customer is not None:
        queryset = queryset.filter(
            visit__customer=customer
        )

    pairs = (
        queryset
        .order_by()
        .values(
            "visit_id",
            "recommendation_id",
            "recommendation__recommendation_type",
        )
        .distinct()
    )

    performance = defaultdict(
        lambda: {
            "recommendation_type": None,
            "presented": 0,
            "purchased": 0,
            "interested": 0,
            "rejected": 0,
            "follow_up": 0,
            "not_presented": 0,
            "revenue": 0.0,
            "purchase_revenues": [],
        }
    )

    for pair in pairs:

        visit_id = pair["visit_id"]
        recommendation_id = pair["recommendation_id"]

        resolved = resolve_recommendation_outcome(
            visit_id=visit_id,
            recommendation_id=recommendation_id,
        )

        if not resolved:
            continue

        recommendation_type = (
            pair[
                "recommendation__recommendation_type"
            ]
        )

        if not recommendation_type:
            continue

        item = performance[
            recommendation_type
        ]

        item["recommendation_type"] = (
            recommendation_type
        )

        item["presented"] += 1

        outcome_name = resolved["outcome"]

        if outcome_name == "PURCHASED":

            item["purchased"] += 1

            revenue = float(
                resolved["sales_amount"] or 0
            )

            item["revenue"] += revenue

            if revenue > 0:
                item[
                    "purchase_revenues"
                ].append(
                    revenue
                )

        elif outcome_name == "INTERESTED":

            item["interested"] += 1

        elif outcome_name == "REJECTED":

            item["rejected"] += 1

        elif outcome_name == "FOLLOW_UP":

            item["follow_up"] += 1

        elif outcome_name == "NOT_PRESENTED":

            item["not_presented"] += 1

    result = []

    for item in performance.values():

        presented = item["presented"]
        purchased = item["purchased"]
        interested = item["interested"]
        rejected = item["rejected"]
        follow_up = item["follow_up"]
        not_presented = item["not_presented"]
        revenue = item["revenue"]

        purchase_revenues = (
            item["purchase_revenues"]
        )

        average_revenue = (
            sum(purchase_revenues)
            / len(purchase_revenues)
            if purchase_revenues
            else 0
        )

        conversion_rate = (
            (purchased / presented) * 100
            if presented
            else 0
        )

        interest_rate = (
            (interested / presented) * 100
            if presented
            else 0
        )

        engagement_rate = (
            (
                purchased
                + interested
                + follow_up
            )
            / presented
            * 100
            if presented
            else 0
        )

        if presented < 3:
            data_quality = "INSUFFICIENT_DATA"

        elif presented < 10:
            data_quality = "LIMITED_DATA"

        else:
            data_quality = "SUFFICIENT_DATA"

        if presented < 3:
            performance_level = "UNKNOWN"

        elif conversion_rate >= 40:
            performance_level = "HIGH"

        elif conversion_rate >= 20:
            performance_level = "MEDIUM"

        else:
            performance_level = "LOW"

        if presented < 3:
            learning_signal = "INSUFFICIENT_DATA"

        elif conversion_rate >= 40:
            learning_signal = "POSITIVE"

        elif (
            conversion_rate < 20
            and interest_rate >= 40
        ):
            learning_signal = "PROMISING"

        elif (
            conversion_rate < 20
            and interest_rate < 40
        ):
            learning_signal = "WEAK"

        else:
            learning_signal = "NEUTRAL"

        result.append({
            "recommendation_type": (
                item["recommendation_type"]
            ),
            "presented": presented,
            "purchased": purchased,
            "interested": interested,
            "rejected": rejected,
            "follow_up": follow_up,
            "not_presented": not_presented,
            "revenue": round(
                revenue,
                2,
            ),
            "average_revenue": round(
                average_revenue,
                2,
            ),
            "conversion_rate": round(
                conversion_rate,
                2,
            ),
            "interest_rate": round(
                interest_rate,
                2,
            ),
            "engagement_rate": round(
                engagement_rate,
                2,
            ),
            "performance_level": (
                performance_level
            ),
            "learning_signal": (
                learning_signal
            ),
            "data_quality": (
                data_quality
            ),
        })

    result.sort(
        key=lambda item: (
            item["recommendation_type"]
            or ""
        )
    )

    return result

def build_outcome_analytics_contract(
    customer=None,
):
    """
    Build the canonical V2.9 outcome analytics contract.

    Important:
    - Raw SalesOutcome rows are never counted directly
      as final recommendation outcomes.
    - Final outcomes are resolved per Visit + Recommendation
      using resolve_recommendation_outcome().
    - NOT_PRESENTED is excluded from the presented denominator.
    - No ML prediction or causal inference is performed.
    """

    from collections import defaultdict
    from datetime import timedelta

    queryset = (
        SalesOutcome.objects
        .filter(
            recommendation__isnull=False,
        )
        .select_related(
            "visit",
            "visit__customer",
            "recommendation",
        )
    )

    if customer is not None:

        queryset = queryset.filter(
            visit__customer=customer
        )

    pairs = (
        queryset
        .order_by()
        .values(
            "visit_id",
            "recommendation_id",

            "visit__visit_date",

            "visit__salesperson_id",
            "visit__salesperson__employee_code",
            "visit__salesperson__first_name",
            "visit__salesperson__last_name",

            "recommendation__recommendation_type",

            "recommendation__product_id",
            "recommendation__product__product_code",
            "recommendation__product__name",

            "recommendation__product__brand__code",
            "recommendation__product__brand__name",

            "recommendation__product__category__code",
            "recommendation__product__category__name",

            "recommendation__product__product_group",
        )
        .distinct()
    )

    def empty_metrics():

        return {
            "resolved_recommendations": 0,
            "presented": 0,
            "purchased": 0,
            "interested": 0,
            "follow_up": 0,
            "rejected": 0,
            "not_presented": 0,
            "total_quantity": 0,
            "total_revenue": 0.0,
        }

    summary_metrics = empty_metrics()

    grouped_metrics = defaultdict(
        empty_metrics
    )

    product_metrics = defaultdict(
        empty_metrics
    )

    product_dimensions = {}

    salesperson_metrics = defaultdict(
        empty_metrics
    )

    brand_metrics = defaultdict(
        empty_metrics
    )

    brand_dimensions = {}

    salesperson_dimensions = {}

    day_metrics = defaultdict(
        empty_metrics
    )

    week_metrics = defaultdict(
        empty_metrics
    )

    month_metrics = defaultdict(
        empty_metrics
    )
    # =====================================================
    # CANONICAL RESOLVED OUTCOMES
    # =====================================================

    for pair in pairs:

        recommendation_type = (
            pair[
                "recommendation__recommendation_type"
            ]
        )

        if not recommendation_type:
            continue

        product_id = (
            pair.get(
                "recommendation__product_id"
            )
        )

        if product_id is not None:

            product_dimensions[
                product_id
            ] = {
                "product_id": (
                    product_id
                ),

                "product_code": (
                    pair.get(
                        "recommendation__product__product_code"
                    )
                ),

                "product_name": (
                    pair.get(
                        "recommendation__product__name"
                    )
                ),

                "brand_code": (
                    pair.get(
                        "recommendation__product__brand__code"
                    )
                ),

                "brand_name": (
                    pair.get(
                        "recommendation__product__brand__name"
                    )
                ),

                "category_code": (
                    pair.get(
                        "recommendation__product__category__code"
                    )
                ),

                "category_name": (
                    pair.get(
                        "recommendation__product__category__name"
                    )
                ),

                "product_group": (
                    pair.get(
                        "recommendation__product__product_group"
                    )
                ),
            }

        brand_code = (
            pair.get(
                "recommendation__product__brand__code"
            )
        )

        if brand_code:

            brand_dimensions[
                brand_code
            ] = {
                "brand_code": (
                    brand_code
                ),

                "brand_name": (
                    pair.get(
                        "recommendation__product__brand__name"
                    )
                ),
            }

        salesperson_id = (
            pair.get(
                "visit__salesperson_id"
            )
        )

        if salesperson_id is not None:

            first_name = (
                pair.get(
                    "visit__salesperson__first_name"
                )
                or ""
            )

            last_name = (
                pair.get(
                    "visit__salesperson__last_name"
                )
                or ""
            )

            salesperson_dimensions[
                salesperson_id
            ] = {
                "salesperson_id": (
                    salesperson_id
                ),

                "employee_code": (
                    pair.get(
                        "visit__salesperson__employee_code"
                    )
                ),

                "first_name": (
                    first_name
                ),

                "last_name": (
                    last_name
                ),

                "full_name": (
                    f"{first_name} {last_name}"
                    .strip()
                ),
            }

        visit_date = (
            pair.get(
                "visit__visit_date"
            )
        )

        day_key = None
        week_key = None
        month_key = None

        if visit_date is not None:

            day_key = (
                visit_date
            )

            week_key = (
                visit_date
                - timedelta(
                    days=(
                        visit_date.weekday()
                    )
                )
            )

            month_key = (
                visit_date.replace(
                    day=1
                )
            )

        resolved = (
            resolve_recommendation_outcome(
                visit_id=(
                    pair["visit_id"]
                ),
                recommendation_id=(
                    pair["recommendation_id"]
                ),
            )
        )

        if not resolved:
            continue

        outcome_name = (
            resolved.get(
                "outcome"
            )
        )

        quantity = int(
            resolved.get(
                "quantity"
            )
            or 0
        )

        sales_amount = float(
            resolved.get(
                "sales_amount"
            )
            or 0
        )

        targets = [
            summary_metrics,
            grouped_metrics[
                recommendation_type
            ],
        ]

        if product_id is not None:

            targets.append(
                product_metrics[
                    product_id
                ]
            )

        if brand_code:

            targets.append(
                brand_metrics[
                    brand_code
                ]
            )

        if salesperson_id is not None:

            targets.append(
                salesperson_metrics[
                    salesperson_id
                ]
            )

        if day_key is not None:

            targets.append(
                day_metrics[
                    day_key
                ]
            )

        if week_key is not None:

            targets.append(
                week_metrics[
                    week_key
                ]
            )

        if month_key is not None:

            targets.append(
                month_metrics[
                    month_key
                ]
            )

        for metrics in targets:

            metrics[
                "resolved_recommendations"
            ] += 1

            if outcome_name == "PURCHASED":

                metrics[
                    "presented"
                ] += 1

                metrics[
                    "purchased"
                ] += 1

                metrics[
                    "total_quantity"
                ] += quantity

                metrics[
                    "total_revenue"
                ] += sales_amount

            elif outcome_name == "INTERESTED":

                metrics[
                    "presented"
                ] += 1

                metrics[
                    "interested"
                ] += 1

            elif outcome_name == "FOLLOW_UP":

                metrics[
                    "presented"
                ] += 1

                metrics[
                    "follow_up"
                ] += 1

            elif outcome_name == "REJECTED":

                metrics[
                    "presented"
                ] += 1

                metrics[
                    "rejected"
                ] += 1

            elif outcome_name == "NOT_PRESENTED":

                metrics[
                    "not_presented"
                ] += 1

    # =====================================================
    # NORMALIZATION
    # =====================================================

    def normalize_metrics(
        metrics,
    ):

        resolved_recommendations = (
            metrics[
                "resolved_recommendations"
            ]
        )

        presented = (
            metrics[
                "presented"
            ]
        )

        purchased = (
            metrics[
                "purchased"
            ]
        )

        interested = (
            metrics[
                "interested"
            ]
        )

        follow_up = (
            metrics[
                "follow_up"
            ]
        )

        rejected = (
            metrics[
                "rejected"
            ]
        )

        not_presented = (
            metrics[
                "not_presented"
            ]
        )

        total_quantity = (
            metrics[
                "total_quantity"
            ]
        )

        total_revenue = float(
            metrics[
                "total_revenue"
            ]
            or 0
        )

        conversion_rate = (
            (
                purchased
                / presented
            )
            * 100
            if presented
            else 0
        )

        interest_rate = (
            (
                interested
                / presented
            )
            * 100
            if presented
            else 0
        )

        follow_up_rate = (
            (
                follow_up
                / presented
            )
            * 100
            if presented
            else 0
        )

        rejection_rate = (
            (
                rejected
                / presented
            )
            * 100
            if presented
            else 0
        )

        engagement_rate = (
            (
                purchased
                + interested
                + follow_up
            )
            / presented
            * 100
            if presented
            else 0
        )

        average_revenue = (
            total_revenue
            / purchased
            if purchased
            else 0
        )

        if presented == 0:

            data_quality = (
                "NO_PRESENTED_DATA"
            )

        elif presented < 3:

            data_quality = (
                "INSUFFICIENT_DATA"
            )

        elif presented < 10:

            data_quality = (
                "LIMITED_DATA"
            )

        else:

            data_quality = (
                "SUFFICIENT_DATA"
            )

        return {
            "resolved_recommendations": (
                resolved_recommendations
            ),

            "presented": presented,

            "purchased": purchased,

            "interested": interested,

            "follow_up": follow_up,

            "rejected": rejected,

            "not_presented": (
                not_presented
            ),

            "total_quantity": (
                total_quantity
            ),

            "total_revenue": round(
                total_revenue,
                2,
            ),

            "average_revenue": round(
                average_revenue,
                2,
            ),

            "conversion_rate": round(
                conversion_rate,
                2,
            ),

            "interest_rate": round(
                interest_rate,
                2,
            ),

            "follow_up_rate": round(
                follow_up_rate,
                2,
            ),

            "rejection_rate": round(
                rejection_rate,
                2,
            ),

            "engagement_rate": round(
                engagement_rate,
                2,
            ),

            "data_quality": (
                data_quality
            ),
        }

    # =====================================================
    # GROUPS
    # =====================================================

    groups = []

    for (
        recommendation_type,
        metrics,
    ) in grouped_metrics.items():

        normalized = (
            normalize_metrics(
                metrics
            )
        )

        groups.append({
            "recommendation_type": (
                recommendation_type
            ),
            **normalized,
        })

    groups.sort(
        key=lambda item: (
            item[
                "recommendation_type"
            ]
            or ""
        )
    )

    # =====================================================
    # PRODUCT GROUPS
    # =====================================================

    product_groups = []

    for (
        product_id,
        metrics,
    ) in product_metrics.items():

        normalized = (
            normalize_metrics(
                metrics
            )
        )

        dimension = (
            product_dimensions.get(
                product_id,
                {},
            )
        )

        product_groups.append({
            "product_id": (
                dimension.get(
                    "product_id"
                )
            ),

            "product_code": (
                dimension.get(
                    "product_code"
                )
            ),

            "product_name": (
                dimension.get(
                    "product_name"
                )
            ),

            "brand_code": (
                dimension.get(
                    "brand_code"
                )
            ),

            "brand_name": (
                dimension.get(
                    "brand_name"
                )
            ),

            "category_code": (
                dimension.get(
                    "category_code"
                )
            ),

            "category_name": (
                dimension.get(
                    "category_name"
                )
            ),

            "product_group": (
                dimension.get(
                    "product_group"
                )
            ),

            **normalized,
        })

    product_groups.sort(
        key=lambda item: (
            item[
                "product_code"
            ]
            or ""
        )
    )

    # =====================================================
    # BRAND GROUPS
    # =====================================================

    brand_groups = []

    for (
        brand_code,
        metrics,
    ) in brand_metrics.items():

        normalized = (
            normalize_metrics(
                metrics
            )
        )

        dimension = (
            brand_dimensions.get(
                brand_code,
                {},
            )
        )

        brand_groups.append({
            "brand_code": (
                dimension.get(
                    "brand_code"
                )
            ),

            "brand_name": (
                dimension.get(
                    "brand_name"
                )
            ),

            **normalized,
        })

    brand_groups.sort(
        key=lambda item: (
            item[
                "brand_code"
            ]
            or ""
        )
    )

    # =====================================================
    # SALESPERSON GROUPS
    # =====================================================

    salesperson_groups = []

    for (
        salesperson_id,
        metrics,
    ) in salesperson_metrics.items():

        normalized = (
            normalize_metrics(
                metrics
            )
        )

        dimension = (
            salesperson_dimensions.get(
                salesperson_id,
                {},
            )
        )

        salesperson_groups.append({
            "salesperson_id": (
                dimension.get(
                    "salesperson_id"
                )
            ),

            "employee_code": (
                dimension.get(
                    "employee_code"
                )
            ),

            "first_name": (
                dimension.get(
                    "first_name"
                )
            ),

            "last_name": (
                dimension.get(
                    "last_name"
                )
            ),

            "full_name": (
                dimension.get(
                    "full_name"
                )
            ),

            **normalized,
        })

    salesperson_groups.sort(
        key=lambda item: (
            item[
                "employee_code"
            ]
            or ""
        )
    )

    summary = (
        normalize_metrics(
            summary_metrics
        )
    )

    # =====================================================
    # PERIOD GROUPS
    # =====================================================

    day_groups = []

    for (
        period_start,
        metrics,
    ) in day_metrics.items():

        day_groups.append({
            "period_start": (
                period_start
            ),

            "period_end": (
                period_start
            ),

            **normalize_metrics(
                metrics
            ),
        })

    day_groups.sort(
        key=lambda item: (
            item[
                "period_start"
            ]
        )
    )


    week_groups = []

    for (
        period_start,
        metrics,
    ) in week_metrics.items():

        week_groups.append({
            "period_start": (
                period_start
            ),

            "period_end": (
                period_start
                + timedelta(
                    days=6
                )
            ),

            **normalize_metrics(
                metrics
            ),
        })

    week_groups.sort(
        key=lambda item: (
            item[
                "period_start"
            ]
        )
    )


    month_groups = []

    for (
        period_start,
        metrics,
    ) in month_metrics.items():

        if period_start.month == 12:

            next_month = (
                period_start.replace(
                    year=(
                        period_start.year
                        + 1
                    ),
                    month=1,
                    day=1,
                )
            )

        else:

            next_month = (
                period_start.replace(
                    month=(
                        period_start.month
                        + 1
                    ),
                    day=1,
                )
            )

        period_end = (
            next_month
            - timedelta(
                days=1
            )
        )

        month_groups.append({
            "period_start": (
                period_start
            ),

            "period_end": (
                period_end
            ),

            **normalize_metrics(
                metrics
            ),
        })

    month_groups.sort(
        key=lambda item: (
            item[
                "period_start"
            ]
        )
    )

    # =====================================================
    # CONTRACT
    # =====================================================

    return {
        "ready": (
            summary[
                "resolved_recommendations"
            ]
            > 0
        ),

        "reason": (
            "OUTCOME_ANALYTICS_READY"
            if (
                summary[
                    "resolved_recommendations"
                ]
                > 0
            )
            else "NO_RESOLVED_RECOMMENDATION_OUTCOMES"
        ),

        "schema_version": (
            "V2.9.1"
        ),

        "scope": {
            "customer_id": (
                customer.id
                if customer is not None
                else None
            ),

            "customer_code": (
                customer.customer_code
                if customer is not None
                else None
            ),

            "outcome_resolution": (
                "VISIT_RECOMMENDATION_CANONICAL"
            ),

            "presented_definition": (
                "RESOLVED_EXCLUDING_NOT_PRESENTED"
            ),
        },

        "summary": summary,

        "groups": groups,

        "product_groups": (
            product_groups
        ),

        "brand_groups": (
            brand_groups
        ),

        "salesperson_groups": (
            salesperson_groups
        ),

        "period_groups": {
            "day": (
                day_groups
            ),

            "week": (
                week_groups
            ),

            "month": (
                month_groups
            ),
        },

        "analytics_rules": {
            "raw_outcome_rows_used_as_final": (
                False
            ),

            "not_presented_in_denominator": (
                False
            ),

            "ml_prediction_used": False,

            "causal_inference_used": False,
        },
    }

def build_recommendation_type_analytics(
    customer=None,
):
    """
    Build V2.9.2 recommendation-type performance analytics.

    This layer is descriptive only.

    It uses the canonical V2.9.1 outcome analytics contract
    and does not modify recommendation decisions.

    Important:
    - NOT_PRESENTED is excluded from presented denominators.
    - No causal inference is performed.
    - No ML prediction or training is performed.
    """

    base_contract = (
        build_outcome_analytics_contract(
            customer=customer
        )
    )

    groups = (
        base_contract.get(
            "groups"
        )
        or []
    )

    items = []

    for group in groups:

        item = {
            "recommendation_type": (
                group.get(
                    "recommendation_type"
                )
            ),

            "resolved_recommendations": (
                group.get(
                    "resolved_recommendations",
                    0,
                )
            ),

            "presented": (
                group.get(
                    "presented",
                    0,
                )
            ),

            "purchased": (
                group.get(
                    "purchased",
                    0,
                )
            ),

            "interested": (
                group.get(
                    "interested",
                    0,
                )
            ),

            "follow_up": (
                group.get(
                    "follow_up",
                    0,
                )
            ),

            "rejected": (
                group.get(
                    "rejected",
                    0,
                )
            ),

            "not_presented": (
                group.get(
                    "not_presented",
                    0,
                )
            ),

            "total_quantity": (
                group.get(
                    "total_quantity",
                    0,
                )
            ),

            "total_revenue": (
                group.get(
                    "total_revenue",
                    0,
                )
            ),

            "average_revenue": (
                group.get(
                    "average_revenue",
                    0,
                )
            ),

            "conversion_rate": (
                group.get(
                    "conversion_rate",
                    0,
                )
            ),

            "interest_rate": (
                group.get(
                    "interest_rate",
                    0,
                )
            ),

            "follow_up_rate": (
                group.get(
                    "follow_up_rate",
                    0,
                )
            ),

            "rejection_rate": (
                group.get(
                    "rejection_rate",
                    0,
                )
            ),

            "engagement_rate": (
                group.get(
                    "engagement_rate",
                    0,
                )
            ),

            "data_quality": (
                group.get(
                    "data_quality"
                )
            ),
        }

        items.append(
            item
        )

    # =====================================================
    # RANKINGS
    # =====================================================

    eligible_for_ranking = [
        item
        for item in items
        if item[
            "presented"
        ] > 0
    ]

    best_conversion = None
    best_revenue = None
    best_engagement = None

    if eligible_for_ranking:

        best_conversion = max(
            eligible_for_ranking,
            key=lambda item: (
                item[
                    "conversion_rate"
                ],
                item[
                    "presented"
                ],
                item[
                    "recommendation_type"
                ]
                or "",
            ),
        )

        best_revenue = max(
            eligible_for_ranking,
            key=lambda item: (
                item[
                    "total_revenue"
                ],
                item[
                    "purchased"
                ],
                item[
                    "recommendation_type"
                ]
                or "",
            ),
        )

        best_engagement = max(
            eligible_for_ranking,
            key=lambda item: (
                item[
                    "engagement_rate"
                ],
                item[
                    "presented"
                ],
                item[
                    "recommendation_type"
                ]
                or "",
            ),
        )

    # =====================================================
    # DISPLAY ORDER
    # =====================================================

    items.sort(
        key=lambda item: (
            -item[
                "conversion_rate"
            ],
            -item[
                "presented"
            ],
            item[
                "recommendation_type"
            ]
            or "",
        )
    )

    # =====================================================
    # CONTRACT
    # =====================================================

    return {
        "ready": (
            base_contract.get(
                "ready",
                False,
            )
        ),

        "reason": (
            "RECOMMENDATION_TYPE_ANALYTICS_READY"
            if base_contract.get(
                "ready"
            )
            else (
                base_contract.get(
                    "reason"
                )
                or "NO_ANALYTICS_DATA"
            )
        ),

        "schema_version": (
            "V2.9.2"
        ),

        "source_contract_schema_version": (
            base_contract.get(
                "schema_version"
            )
        ),

        "scope": (
            base_contract.get(
                "scope"
            )
            or {}
        ),

        "summary": (
            base_contract.get(
                "summary"
            )
            or {}
        ),

        "ranking": {
            "best_conversion_type": (
                best_conversion[
                    "recommendation_type"
                ]
                if best_conversion
                else None
            ),

            "best_revenue_type": (
                best_revenue[
                    "recommendation_type"
                ]
                if best_revenue
                else None
            ),

            "best_engagement_type": (
                best_engagement[
                    "recommendation_type"
                ]
                if best_engagement
                else None
            ),
        },

        "items": items,

        "analytics_rules": {
            "source_is_canonical_v2_9_1": (
                True
            ),

            "not_presented_in_denominator": (
                False
            ),

            "ranking_is_descriptive": (
                True
            ),

            "causal_inference_used": (
                False
            ),

            "ml_prediction_used": (
                False
            ),

            "ml_training_performed": (
                False
            ),
        },
    }

def build_product_performance_analytics(
    customer=None,
):
    """
    Build V2.9.3 product-level performance analytics.

    This layer is descriptive only and uses
    the canonical V2.9.1 product groups.

    Important:
    - Final outcomes are not resolved again here.
    - NOT_PRESENTED remains excluded from presented.
    - No causal inference is performed.
    - No ML prediction or training is performed.
    """

    base_contract = (
        build_outcome_analytics_contract(
            customer=customer
        )
    )

    product_groups = (
        base_contract.get(
            "product_groups"
        )
        or []
    )

    items = []

    for group in product_groups:

        items.append({
            "product_id": (
                group.get(
                    "product_id"
                )
            ),

            "product_code": (
                group.get(
                    "product_code"
                )
            ),

            "product_name": (
                group.get(
                    "product_name"
                )
            ),

            "brand_code": (
                group.get(
                    "brand_code"
                )
            ),

            "brand_name": (
                group.get(
                    "brand_name"
                )
            ),

            "category_code": (
                group.get(
                    "category_code"
                )
            ),

            "category_name": (
                group.get(
                    "category_name"
                )
            ),

            "product_group": (
                group.get(
                    "product_group"
                )
            ),

            "resolved_recommendations": (
                group.get(
                    "resolved_recommendations",
                    0,
                )
            ),

            "presented": (
                group.get(
                    "presented",
                    0,
                )
            ),

            "purchased": (
                group.get(
                    "purchased",
                    0,
                )
            ),

            "interested": (
                group.get(
                    "interested",
                    0,
                )
            ),

            "follow_up": (
                group.get(
                    "follow_up",
                    0,
                )
            ),

            "rejected": (
                group.get(
                    "rejected",
                    0,
                )
            ),

            "not_presented": (
                group.get(
                    "not_presented",
                    0,
                )
            ),

            "total_quantity": (
                group.get(
                    "total_quantity",
                    0,
                )
            ),

            "total_revenue": (
                group.get(
                    "total_revenue",
                    0,
                )
            ),

            "average_revenue": (
                group.get(
                    "average_revenue",
                    0,
                )
            ),

            "conversion_rate": (
                group.get(
                    "conversion_rate",
                    0,
                )
            ),

            "interest_rate": (
                group.get(
                    "interest_rate",
                    0,
                )
            ),

            "follow_up_rate": (
                group.get(
                    "follow_up_rate",
                    0,
                )
            ),

            "rejection_rate": (
                group.get(
                    "rejection_rate",
                    0,
                )
            ),

            "engagement_rate": (
                group.get(
                    "engagement_rate",
                    0,
                )
            ),

            "data_quality": (
                group.get(
                    "data_quality"
                )
            ),
        })

    eligible_for_ranking = [
        item
        for item in items
        if item[
            "presented"
        ] > 0
    ]

    best_conversion = None
    best_revenue = None
    best_engagement = None

    if eligible_for_ranking:

        best_conversion = max(
            eligible_for_ranking,
            key=lambda item: (
                item[
                    "conversion_rate"
                ],
                item[
                    "presented"
                ],
                item[
                    "product_code"
                ]
                or "",
            ),
        )

        best_revenue = max(
            eligible_for_ranking,
            key=lambda item: (
                item[
                    "total_revenue"
                ],
                item[
                    "purchased"
                ],
                item[
                    "product_code"
                ]
                or "",
            ),
        )

        best_engagement = max(
            eligible_for_ranking,
            key=lambda item: (
                item[
                    "engagement_rate"
                ],
                item[
                    "presented"
                ],
                item[
                    "product_code"
                ]
                or "",
            ),
        )

    items.sort(
        key=lambda item: (
            -item[
                "conversion_rate"
            ],
            -item[
                "presented"
            ],
            item[
                "product_code"
            ]
            or "",
        )
    )

    return {
        "ready": (
            base_contract.get(
                "ready",
                False,
            )
        ),

        "reason": (
            "PRODUCT_PERFORMANCE_ANALYTICS_READY"
            if base_contract.get(
                "ready"
            )
            else (
                base_contract.get(
                    "reason"
                )
                or "NO_ANALYTICS_DATA"
            )
        ),

        "schema_version": (
            "V2.9.3"
        ),

        "source_contract_schema_version": (
            base_contract.get(
                "schema_version"
            )
        ),

        "scope": (
            base_contract.get(
                "scope"
            )
            or {}
        ),

        "summary": (
            base_contract.get(
                "summary"
            )
            or {}
        ),

        "ranking": {
            "best_conversion_product_code": (
                best_conversion[
                    "product_code"
                ]
                if best_conversion
                else None
            ),

            "best_revenue_product_code": (
                best_revenue[
                    "product_code"
                ]
                if best_revenue
                else None
            ),

            "best_engagement_product_code": (
                best_engagement[
                    "product_code"
                ]
                if best_engagement
                else None
            ),
        },

        "items": items,

        "analytics_rules": {
            "source_is_canonical_v2_9_1": True,

            "product_dimension_from_canonical_contract": (
                True
            ),

            "not_presented_in_denominator": False,

            "ranking_is_descriptive": True,

            "causal_inference_used": False,

            "ml_prediction_used": False,

            "ml_training_performed": False,
        },
    }

def build_category_performance_analytics(
    customer=None,
):
    """
    Build V2.9.4 category-level performance analytics.

    This layer aggregates canonical V2.9.1 product groups.

    Important:
    - Final outcomes are not resolved again here.
    - NOT_PRESENTED remains excluded from presented.
    - No causal inference is performed.
    - No ML prediction or training is performed.
    """

    base_contract = (
        build_outcome_analytics_contract(
            customer=customer
        )
    )

    product_groups = (
        base_contract.get(
            "product_groups"
        )
        or []
    )

    category_metrics = {}

    for product in product_groups:

        category_code = (
            product.get(
                "category_code"
            )
        )

        category_name = (
            product.get(
                "category_name"
            )
        )

        category_key = (
            category_code
            or category_name
            or "UNCLASSIFIED"
        )

        if category_key not in category_metrics:

            category_metrics[
                category_key
            ] = {
                "category_code": (
                    category_code
                ),

                "category_name": (
                    category_name
                ),

                "resolved_recommendations": 0,
                "presented": 0,
                "purchased": 0,
                "interested": 0,
                "follow_up": 0,
                "rejected": 0,
                "not_presented": 0,
                "total_quantity": 0,
                "total_revenue": 0.0,
            }

        item = (
            category_metrics[
                category_key
            ]
        )

        item[
            "resolved_recommendations"
        ] += (
            product.get(
                "resolved_recommendations",
                0,
            )
            or 0
        )

        item["presented"] += (
            product.get(
                "presented",
                0,
            )
            or 0
        )

        item["purchased"] += (
            product.get(
                "purchased",
                0,
            )
            or 0
        )

        item["interested"] += (
            product.get(
                "interested",
                0,
            )
            or 0
        )

        item["follow_up"] += (
            product.get(
                "follow_up",
                0,
            )
            or 0
        )

        item["rejected"] += (
            product.get(
                "rejected",
                0,
            )
            or 0
        )

        item["not_presented"] += (
            product.get(
                "not_presented",
                0,
            )
            or 0
        )

        item["total_quantity"] += (
            product.get(
                "total_quantity",
                0,
            )
            or 0
        )

        item["total_revenue"] += float(
            product.get(
                "total_revenue",
                0,
            )
            or 0
        )

    items = []

    for item in category_metrics.values():

        presented = (
            item["presented"]
        )

        purchased = (
            item["purchased"]
        )

        interested = (
            item["interested"]
        )

        follow_up = (
            item["follow_up"]
        )

        rejected = (
            item["rejected"]
        )

        total_revenue = float(
            item["total_revenue"]
            or 0
        )

        conversion_rate = (
            (
                purchased
                / presented
            )
            * 100
            if presented
            else 0
        )

        interest_rate = (
            (
                interested
                / presented
            )
            * 100
            if presented
            else 0
        )

        follow_up_rate = (
            (
                follow_up
                / presented
            )
            * 100
            if presented
            else 0
        )

        rejection_rate = (
            (
                rejected
                / presented
            )
            * 100
            if presented
            else 0
        )

        engagement_rate = (
            (
                purchased
                + interested
                + follow_up
            )
            / presented
            * 100
            if presented
            else 0
        )

        average_revenue = (
            total_revenue
            / purchased
            if purchased
            else 0
        )

        if presented == 0:

            data_quality = (
                "NO_PRESENTED_DATA"
            )

        elif presented < 3:

            data_quality = (
                "INSUFFICIENT_DATA"
            )

        elif presented < 10:

            data_quality = (
                "LIMITED_DATA"
            )

        else:

            data_quality = (
                "SUFFICIENT_DATA"
            )

        items.append({
            "category_code": (
                item[
                    "category_code"
                ]
            ),

            "category_name": (
                item[
                    "category_name"
                ]
            ),

            "resolved_recommendations": (
                item[
                    "resolved_recommendations"
                ]
            ),

            "presented": presented,

            "purchased": purchased,

            "interested": interested,

            "follow_up": follow_up,

            "rejected": rejected,

            "not_presented": (
                item[
                    "not_presented"
                ]
            ),

            "total_quantity": (
                item[
                    "total_quantity"
                ]
            ),

            "total_revenue": round(
                total_revenue,
                2,
            ),

            "average_revenue": round(
                average_revenue,
                2,
            ),

            "conversion_rate": round(
                conversion_rate,
                2,
            ),

            "interest_rate": round(
                interest_rate,
                2,
            ),

            "follow_up_rate": round(
                follow_up_rate,
                2,
            ),

            "rejection_rate": round(
                rejection_rate,
                2,
            ),

            "engagement_rate": round(
                engagement_rate,
                2,
            ),

            "data_quality": (
                data_quality
            ),
        })

    eligible_for_ranking = [
        item
        for item in items
        if item[
            "presented"
        ] > 0
    ]

    best_conversion = None
    best_revenue = None
    best_engagement = None

    if eligible_for_ranking:

        best_conversion = max(
            eligible_for_ranking,
            key=lambda item: (
                item[
                    "conversion_rate"
                ],
                item[
                    "presented"
                ],
                item[
                    "category_code"
                ]
                or item[
                    "category_name"
                ]
                or "",
            ),
        )

        best_revenue = max(
            eligible_for_ranking,
            key=lambda item: (
                item[
                    "total_revenue"
                ],
                item[
                    "purchased"
                ],
                item[
                    "category_code"
                ]
                or item[
                    "category_name"
                ]
                or "",
            ),
        )

        best_engagement = max(
            eligible_for_ranking,
            key=lambda item: (
                item[
                    "engagement_rate"
                ],
                item[
                    "presented"
                ],
                item[
                    "category_code"
                ]
                or item[
                    "category_name"
                ]
                or "",
            ),
        )

    items.sort(
        key=lambda item: (
            -item[
                "conversion_rate"
            ],
            -item[
                "presented"
            ],
            item[
                "category_code"
            ]
            or item[
                "category_name"
            ]
            or "",
        )
    )

    return {
        "ready": (
            base_contract.get(
                "ready",
                False,
            )
        ),

        "reason": (
            "CATEGORY_PERFORMANCE_ANALYTICS_READY"
            if base_contract.get(
                "ready"
            )
            else (
                base_contract.get(
                    "reason"
                )
                or "NO_ANALYTICS_DATA"
            )
        ),

        "schema_version": (
            "V2.9.4"
        ),

        "source_contract_schema_version": (
            base_contract.get(
                "schema_version"
            )
        ),

        "scope": (
            base_contract.get(
                "scope"
            )
            or {}
        ),

        "summary": (
            base_contract.get(
                "summary"
            )
            or {}
        ),

        "ranking": {
            "best_conversion_category_code": (
                best_conversion[
                    "category_code"
                ]
                if best_conversion
                else None
            ),

            "best_revenue_category_code": (
                best_revenue[
                    "category_code"
                ]
                if best_revenue
                else None
            ),

            "best_engagement_category_code": (
                best_engagement[
                    "category_code"
                ]
                if best_engagement
                else None
            ),
        },

        "items": items,

        "analytics_rules": {
            "source_is_canonical_v2_9_1": True,

            "category_dimension_from_product_groups": (
                True
            ),

            "not_presented_in_denominator": False,

            "ranking_is_descriptive": True,

            "causal_inference_used": False,

            "ml_prediction_used": False,

            "ml_training_performed": False,
        },
    }

def build_salesperson_performance_analytics(
    customer=None,
):
    """
    Build V2.9.5 salesperson-level performance analytics.

    This layer uses canonical V2.9.1 salesperson groups.

    Important:
    - Final outcomes are not resolved again here.
    - Attribution is based on Visit.salesperson.
    - NOT_PRESENTED remains excluded from presented.
    - No causal inference is performed.
    - No ML prediction or training is performed.
    """

    base_contract = (
        build_outcome_analytics_contract(
            customer=customer
        )
    )

    salesperson_groups = (
        base_contract.get(
            "salesperson_groups"
        )
        or []
    )

    items = []

    for group in salesperson_groups:

        items.append({
            "salesperson_id": (
                group.get(
                    "salesperson_id"
                )
            ),

            "employee_code": (
                group.get(
                    "employee_code"
                )
            ),

            "first_name": (
                group.get(
                    "first_name"
                )
            ),

            "last_name": (
                group.get(
                    "last_name"
                )
            ),

            "full_name": (
                group.get(
                    "full_name"
                )
            ),

            "resolved_recommendations": (
                group.get(
                    "resolved_recommendations",
                    0,
                )
            ),

            "presented": (
                group.get(
                    "presented",
                    0,
                )
            ),

            "purchased": (
                group.get(
                    "purchased",
                    0,
                )
            ),

            "interested": (
                group.get(
                    "interested",
                    0,
                )
            ),

            "follow_up": (
                group.get(
                    "follow_up",
                    0,
                )
            ),

            "rejected": (
                group.get(
                    "rejected",
                    0,
                )
            ),

            "not_presented": (
                group.get(
                    "not_presented",
                    0,
                )
            ),

            "total_quantity": (
                group.get(
                    "total_quantity",
                    0,
                )
            ),

            "total_revenue": (
                group.get(
                    "total_revenue",
                    0,
                )
            ),

            "average_revenue": (
                group.get(
                    "average_revenue",
                    0,
                )
            ),

            "conversion_rate": (
                group.get(
                    "conversion_rate",
                    0,
                )
            ),

            "interest_rate": (
                group.get(
                    "interest_rate",
                    0,
                )
            ),

            "follow_up_rate": (
                group.get(
                    "follow_up_rate",
                    0,
                )
            ),

            "rejection_rate": (
                group.get(
                    "rejection_rate",
                    0,
                )
            ),

            "engagement_rate": (
                group.get(
                    "engagement_rate",
                    0,
                )
            ),

            "data_quality": (
                group.get(
                    "data_quality"
                )
            ),
        })

    eligible_for_ranking = [
        item
        for item in items
        if item["presented"] > 0
    ]

    best_conversion = None
    best_revenue = None
    best_engagement = None

    if eligible_for_ranking:

        best_conversion = max(
            eligible_for_ranking,
            key=lambda item: (
                item["conversion_rate"],
                item["presented"],
                item["employee_code"]
                or "",
            ),
        )

        best_revenue = max(
            eligible_for_ranking,
            key=lambda item: (
                item["total_revenue"],
                item["purchased"],
                item["employee_code"]
                or "",
            ),
        )

        best_engagement = max(
            eligible_for_ranking,
            key=lambda item: (
                item["engagement_rate"],
                item["presented"],
                item["employee_code"]
                or "",
            ),
        )

    items.sort(
        key=lambda item: (
            -item["conversion_rate"],
            -item["presented"],
            item["employee_code"]
            or "",
        )
    )

    return {
        "ready": (
            base_contract.get(
                "ready",
                False,
            )
        ),

        "reason": (
            "SALESPERSON_PERFORMANCE_ANALYTICS_READY"
            if base_contract.get(
                "ready"
            )
            else (
                base_contract.get(
                    "reason"
                )
                or "NO_ANALYTICS_DATA"
            )
        ),

        "schema_version": (
            "V2.9.5"
        ),

        "source_contract_schema_version": (
            base_contract.get(
                "schema_version"
            )
        ),

        "scope": (
            base_contract.get(
                "scope"
            )
            or {}
        ),

        "summary": (
            base_contract.get(
                "summary"
            )
            or {}
        ),

        "ranking": {
            "best_conversion_salesperson_code": (
                best_conversion[
                    "employee_code"
                ]
                if best_conversion
                else None
            ),

            "best_revenue_salesperson_code": (
                best_revenue[
                    "employee_code"
                ]
                if best_revenue
                else None
            ),

            "best_engagement_salesperson_code": (
                best_engagement[
                    "employee_code"
                ]
                if best_engagement
                else None
            ),
        },

        "items": items,

        "analytics_rules": {
            "source_is_canonical_v2_9_1": True,

            "salesperson_dimension_from_visit": True,

            "not_presented_in_denominator": False,

            "ranking_is_descriptive": True,

            "causal_inference_used": False,

            "ml_prediction_used": False,

            "ml_training_performed": False,
        },
    }

def build_brand_performance_analytics(
    customer=None,
):
    """
    Build V2.9.7 brand-level performance analytics.

    This layer uses canonical V2.9.1 brand groups.

    Important:
    - Final outcomes are not resolved again here.
    - Brand attribution comes from recommendation product brand.
    - NOT_PRESENTED remains excluded from presented.
    - No causal inference is performed.
    - No ML prediction or training is performed.
    """

    base_contract = (
        build_outcome_analytics_contract(
            customer=customer
        )
    )

    brand_groups = (
        base_contract.get(
            "brand_groups"
        )
        or []
    )

    items = []

    for group in brand_groups:

        items.append({
            "brand_code": (
                group.get(
                    "brand_code"
                )
            ),

            "brand_name": (
                group.get(
                    "brand_name"
                )
            ),

            "resolved_recommendations": (
                group.get(
                    "resolved_recommendations",
                    0,
                )
            ),

            "presented": (
                group.get(
                    "presented",
                    0,
                )
            ),

            "purchased": (
                group.get(
                    "purchased",
                    0,
                )
            ),

            "interested": (
                group.get(
                    "interested",
                    0,
                )
            ),

            "follow_up": (
                group.get(
                    "follow_up",
                    0,
                )
            ),

            "rejected": (
                group.get(
                    "rejected",
                    0,
                )
            ),

            "not_presented": (
                group.get(
                    "not_presented",
                    0,
                )
            ),

            "total_quantity": (
                group.get(
                    "total_quantity",
                    0,
                )
            ),

            "total_revenue": (
                group.get(
                    "total_revenue",
                    0,
                )
            ),

            "average_revenue": (
                group.get(
                    "average_revenue",
                    0,
                )
            ),

            "conversion_rate": (
                group.get(
                    "conversion_rate",
                    0,
                )
            ),

            "interest_rate": (
                group.get(
                    "interest_rate",
                    0,
                )
            ),

            "follow_up_rate": (
                group.get(
                    "follow_up_rate",
                    0,
                )
            ),

            "rejection_rate": (
                group.get(
                    "rejection_rate",
                    0,
                )
            ),

            "engagement_rate": (
                group.get(
                    "engagement_rate",
                    0,
                )
            ),

            "data_quality": (
                group.get(
                    "data_quality"
                )
            ),
        })

    eligible_for_ranking = [
        item
        for item in items
        if item["presented"] > 0
    ]

    best_conversion = None
    best_revenue = None
    best_engagement = None

    if eligible_for_ranking:

        best_conversion = max(
            eligible_for_ranking,
            key=lambda item: (
                item["conversion_rate"],
                item["presented"],
                item["brand_code"]
                or "",
            ),
        )

        best_revenue = max(
            eligible_for_ranking,
            key=lambda item: (
                item["total_revenue"],
                item["purchased"],
                item["brand_code"]
                or "",
            ),
        )

        best_engagement = max(
            eligible_for_ranking,
            key=lambda item: (
                item["engagement_rate"],
                item["presented"],
                item["brand_code"]
                or "",
            ),
        )

    items.sort(
        key=lambda item: (
            -item["conversion_rate"],
            -item["presented"],
            item["brand_code"]
            or "",
        )
    )

    return {
        "ready": (
            base_contract.get(
                "ready",
                False,
            )
        ),

        "reason": (
            "BRAND_PERFORMANCE_ANALYTICS_READY"
            if base_contract.get(
                "ready"
            )
            else (
                base_contract.get(
                    "reason"
                )
                or "NO_ANALYTICS_DATA"
            )
        ),

        "schema_version": (
            "V2.9.7"
        ),

        "source_contract_schema_version": (
            base_contract.get(
                "schema_version"
            )
        ),

        "scope": (
            base_contract.get(
                "scope"
            )
            or {}
        ),

        "summary": (
            base_contract.get(
                "summary"
            )
            or {}
        ),

        "ranking": {
            "best_conversion_brand_code": (
                best_conversion[
                    "brand_code"
                ]
                if best_conversion
                else None
            ),

            "best_revenue_brand_code": (
                best_revenue[
                    "brand_code"
                ]
                if best_revenue
                else None
            ),

            "best_engagement_brand_code": (
                best_engagement[
                    "brand_code"
                ]
                if best_engagement
                else None
            ),
        },

        "items": items,

        "analytics_rules": {
            "source_is_canonical_v2_9_1": True,

            "brand_dimension_from_recommendation_product": True,

            "not_presented_in_denominator": False,

            "ranking_is_descriptive": True,

            "causal_inference_used": False,

            "ml_prediction_used": False,

            "ml_training_performed": False,
        },
    }

def build_ml_learning_contract(
    visit,
):
    """
    Build a normalized ML-ready learning record
    for one finalized sales visit.

    Important:
    - No ML prediction is performed here.
    - No model is loaded here.
    - No recommendation decision is changed here.
    - This is only a stable feature/label contract
      for future dataset generation and ML training.
    """

    if visit is None:

        raise ValueError(
            "visit is required."
        )

    intelligence = (
        build_post_visit_intelligence(
            visit=visit
        )
    )

    learning = (
        intelligence.get(
            "learning"
        )
        or {}
    )

    if not learning.get(
        "ready"
    ):

        return {
            "ready": False,

            "reason": (
                learning.get(
                    "reason"
                )
                or "NOT_READY"
            ),

            "schema_version": (
                "V2.8.11"
            ),

            "ml_prediction_used": False,

            "model_version": None,

            "records": [],
        }

    visit_data = (
        intelligence.get(
            "visit"
        )
        or {}
    )

    customer_snapshot = getattr(
        visit,
        "customer_snapshot",
        None,
    )

    customer_snapshot_used = (
        customer_snapshot is not None
    )

    commercial_snapshot = getattr(
        visit,
        "commercial_snapshot",
        None,
    )

    commercial_snapshot_used = (
        commercial_snapshot is not None
    )

    recommendation_outcomes = (
        intelligence.get(
            "recommendation_outcomes"
        )
        or []
    )

    records = []

    for item in recommendation_outcomes:

        product = (
            item.get(
                "product"
            )
            or {}
        )

        outcome_name = (
            item.get(
                "final_outcome"
            )
        )

        label_purchased = (
            1
            if outcome_name == "PURCHASED"
            else 0
        )

        label_engaged = (
            1
            if outcome_name
            in {
                "PURCHASED",
                "INTERESTED",
                "FOLLOW_UP",
            }
            else 0
        )

        record = {
            "schema_version": (
                "V2.8.11"
            ),

            "entity": {
                "visit_id": (
                    visit_data.get(
                        "id"
                    )
                ),

                "visit_date": (
                    visit_data.get(
                        "visit_date"
                    )
                ),

                "customer_id": (
                    (
                        visit_data.get(
                            "customer"
                        )
                        or {}
                    ).get(
                        "id"
                    )
                ),

                "customer_code": (
                    (
                        visit_data.get(
                            "customer"
                        )
                        or {}
                    ).get(
                        "customer_code"
                    )
                ),

                "salesperson_id": (
                    (
                        visit_data.get(
                            "salesperson"
                        )
                        or {}
                    ).get(
                        "id"
                    )
                ),

                "salesperson_code": (
                    (
                        visit_data.get(
                            "salesperson"
                        )
                        or {}
                    ).get(
                        "employee_code"
                    )
                ),

                "recommendation_id": (
                    item.get(
                        "recommendation_id"
                    )
                ),

                "product_id": (
                    product.get(
                        "id"
                    )
                ),

                "product_code": (
                    product.get(
                        "code"
                    )
                ),
            },

            "features": {
                "recommendation_type": (
                    item.get(
                        "recommendation_type"
                    )
                ),

                "recommendation_score": (
                    item.get(
                        "recommendation_score"
                    )
                ),

                "recommendation_rank": (
                    item.get(
                        "recommendation_rank"
                    )
                ),

                "customer_segment": (
                    customer_snapshot.segment
                    if customer_snapshot
                    else None
                ),

                "customer_grade": (
                    customer_snapshot
                    .customer_grade_code
                    if customer_snapshot
                    else None
                ),

                "customer_total_orders": (
                    customer_snapshot.total_orders
                    if customer_snapshot
                    else None
                ),

                "customer_total_sales_amount": (
                    float(
                        customer_snapshot
                        .total_sales_amount
                    )
                    if customer_snapshot
                    else None
                ),

                "customer_average_order_value": (
                    float(
                        customer_snapshot
                        .average_order_value
                    )
                    if customer_snapshot
                    else None
                ),

                "customer_days_since_last_purchase": (
                    customer_snapshot
                    .days_since_last_purchase
                    if customer_snapshot
                    else None
                ),

                "customer_recency_score": (
                    customer_snapshot.recency_score
                    if customer_snapshot
                    else None
                ),

                "customer_frequency_score": (
                    customer_snapshot.frequency_score
                    if customer_snapshot
                    else None
                ),

                "customer_monetary_score": (
                    customer_snapshot.monetary_score
                    if customer_snapshot
                    else None
                ),

                "customer_rfm_score": (
                    customer_snapshot.rfm_score
                    if customer_snapshot
                    else None
                ),

                "customer_top_category": (
                    customer_snapshot.top_category
                    if customer_snapshot
                    else None
                ),

                "customer_top_product_code": (
                    customer_snapshot.top_product_code
                    if customer_snapshot
                    else None
                ),

                "commercial_score": (
                    float(
                        commercial_snapshot
                        .commercial_score
                    )
                    if (
                        commercial_snapshot
                        and commercial_snapshot
                        .commercial_score
                        is not None
                    )
                    else None
                ),

                "commercial_priority": (
                    commercial_snapshot
                    .commercial_priority
                    if commercial_snapshot
                    else None
                ),

                "commercial_blocked": (
                    commercial_snapshot
                    .commercial_blocked
                    if commercial_snapshot
                    else None
                ),

                "commercial_primary_product_code": (
                    commercial_snapshot
                    .primary_product_code
                    if commercial_snapshot
                    else None
                ),

                "commercial_recommendation_type": (
                    commercial_snapshot
                    .recommendation_type
                    if commercial_snapshot
                    else None
                ),

                "commercial_signals": (
                    commercial_snapshot
                    .commercial_signals
                    if commercial_snapshot
                    else []
                ),

                "commercial_decision_reasons": (
                    commercial_snapshot
                    .decision_reasons
                    if commercial_snapshot
                    else []
                ),

                "inventory_sellable_quantity": (
                    (
                        commercial_snapshot
                        .inventory_context
                        or {}
                    ).get(
                        "sellable_quantity"
                    )
                    if commercial_snapshot
                    else None
                ),

                "inventory_is_in_stock": (
                    (
                        commercial_snapshot
                        .inventory_context
                        or {}
                    ).get(
                        "is_in_stock"
                    )
                    if commercial_snapshot
                    else None
                ),

                "inventory_is_low_stock": (
                    (
                        commercial_snapshot
                        .inventory_context
                        or {}
                    ).get(
                        "is_low_stock"
                    )
                    if commercial_snapshot
                    else None
                ),

                "promotion_count": (
                    len(
                        commercial_snapshot
                        .promotion_context
                        or []
                    )
                    if commercial_snapshot
                    else None
                ),

                "has_eligible_promotion": (
                    bool(
                        commercial_snapshot
                        .promotion_context
                    )
                    if commercial_snapshot
                    else None
                ),

                "target_count": (
                    len(
                        commercial_snapshot
                        .target_context
                        or []
                    )
                    if commercial_snapshot
                    else None
                ),

                "has_target_relevance": (
                    bool(
                        commercial_snapshot
                        .target_context
                    )
                    if commercial_snapshot
                    else None
                ),

                "feature_source": {
                    "recommendation_type": (
                        "CUSTOMER_RECOMMENDATION"
                    ),

                    "recommendation_score": (
                        "CUSTOMER_RECOMMENDATION"
                    ),

                    "recommendation_rank": (
                        "CUSTOMER_RECOMMENDATION"
                    ),

                    "customer_segment": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_grade": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_total_orders": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_total_sales_amount": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_average_order_value": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_days_since_last_purchase": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_recency_score": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_frequency_score": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_monetary_score": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_rfm_score": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_top_category": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),

                    "customer_top_product_code": (
                        "VISIT_CUSTOMER_SNAPSHOT"
                        if customer_snapshot
                        else None
                    ),
                                        "commercial_score": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "commercial_priority": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "commercial_blocked": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "commercial_primary_product_code": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "commercial_recommendation_type": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "commercial_signals": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "commercial_decision_reasons": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "inventory_sellable_quantity": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "inventory_is_in_stock": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "inventory_is_low_stock": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "promotion_count": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "has_eligible_promotion": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "target_count": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),

                    "has_target_relevance": (
                        "VISIT_COMMERCIAL_SNAPSHOT"
                        if commercial_snapshot
                        else None
                    ),
                },
            },

            "feature_snapshot": {
                "customer": {
                    "snapshot_id": (
                        customer_snapshot.id
                        if customer_snapshot
                        else None
                    ),

                    "captured_at": (
                        customer_snapshot.captured_at
                        if customer_snapshot
                        else None
                    ),

                    "source_customer360_calculated_at": (
                        customer_snapshot
                        .source_customer360_calculated_at
                        if customer_snapshot
                        else None
                    ),

                },
                "commercial": {
                    "snapshot_id": (
                        commercial_snapshot.id
                        if commercial_snapshot
                        else None
                    ),

                    "captured_at": (
                        commercial_snapshot
                        .captured_at
                        if commercial_snapshot
                        else None
                    ),
                },
            },


            "labels": {
                "final_outcome": (
                    outcome_name
                ),

                "purchased": (
                    label_purchased
                ),

                "engaged": (
                    label_engaged
                ),

                "quantity": (
                    item.get(
                        "quantity",
                        0,
                    )
                ),

                "sales_amount": (
                    float(
                        item.get(
                            "sales_amount"
                        )
                        or 0
                    )
                ),
            },

            "ml": {
                "prediction_used": False,

                "prediction": None,

                "probability": None,

                "model_version": None,
            },
        }

        records.append(
            record
        )

    return {
        "ready": True,

        "reason": (
            "ML_LEARNING_CONTRACT_READY"
        ),

        "schema_version": (
            "V2.8.11"
        ),

        "ml_prediction_used": False,

        "model_version": None,

        "feature_provenance": {
            "point_in_time_safe": True,

            "snapshot_strategy": (
                "IMMUTABLE_SOURCE_ONLY"
            ),

            "customer_snapshot_used": (
                customer_snapshot_used
            ),

            "commercial_snapshot_used": (
                commercial_snapshot_used
            ),

            "inventory_snapshot_used": (
                commercial_snapshot_used
            ),

            "promotion_snapshot_used": (
                commercial_snapshot_used
            ),

            "target_snapshot_used": (
                commercial_snapshot_used
            ),
        },

        "records": records,
    }

def build_ml_learning_dataset(
    visits=None,
    limit=None,
):
    """
    Build a normalized training-ready dataset from
    finalized sales visits.

    Only point-in-time safe learning contracts are
    admitted to the dataset.

    Important:
    - No ML model is trained here.
    - No prediction is performed here.
    - Unsafe historical records are skipped.
    - Missing immutable snapshots are never replaced
      with current mutable state.
    """

    # =====================================================
    # VALIDATION
    # =====================================================

    if (
        limit is not None
        and limit < 1
    ):

        raise ValueError(
            "limit must be at least 1."
        )

    # =====================================================
    # FINAL VISITS
    # =====================================================

    if visits is None:

        queryset = (
            Visit.objects
            .filter(
                status__in=[
                    Visit.VisitStatus.COMPLETED,
                    Visit.VisitStatus.CANCELLED,
                ]
            )
            .select_related(
                "customer",
                "salesperson",
                "customer_snapshot",
                "commercial_snapshot",
            )
            .order_by(
                "visit_date",
                "id",
            )
        )

        if limit is not None:

            queryset = queryset[
                :limit
            ]

        visit_list = list(
            queryset
        )

    else:

        visit_list = list(
            visits
        )

        if limit is not None:

            visit_list = visit_list[
                :limit
            ]

    # =====================================================
    # DATASET ACCUMULATORS
    # =====================================================

    records = []

    skipped_visits = []

    eligible_visit_count = 0

    # =====================================================
    # BUILD CONTRACTS
    # =====================================================

    for visit in visit_list:

        contract = (
            build_ml_learning_contract(
                visit=visit
            )
        )

        if not contract.get(
            "ready"
        ):

            skipped_visits.append({
                "visit_id": visit.id,

                "reason": (
                    contract.get(
                        "reason"
                    )
                    or "LEARNING_CONTRACT_NOT_READY"
                ),
            })

            continue

        provenance = (
            contract.get(
                "feature_provenance"
            )
            or {}
        )

        # ==============================================
        # POINT-IN-TIME ELIGIBILITY
        # ==============================================

        required_snapshot_flags = {
            "customer_snapshot_used": (
                provenance.get(
                    "customer_snapshot_used"
                )
                is True
            ),

            "commercial_snapshot_used": (
                provenance.get(
                    "commercial_snapshot_used"
                )
                is True
            ),

            "inventory_snapshot_used": (
                provenance.get(
                    "inventory_snapshot_used"
                )
                is True
            ),

            "promotion_snapshot_used": (
                provenance.get(
                    "promotion_snapshot_used"
                )
                is True
            ),

            "target_snapshot_used": (
                provenance.get(
                    "target_snapshot_used"
                )
                is True
            ),
        }

        point_in_time_safe = (
            provenance.get(
                "point_in_time_safe"
            )
            is True
        )

        snapshot_complete = all(
            required_snapshot_flags.values()
        )

        if (
            not point_in_time_safe
            or not snapshot_complete
        ):

            missing_snapshots = [
                name
                for name, available
                in required_snapshot_flags.items()
                if not available
            ]

            skipped_visits.append({
                "visit_id": visit.id,

                "reason": (
                    "POINT_IN_TIME_SNAPSHOT_INCOMPLETE"
                ),

                "missing_snapshot_flags": (
                    missing_snapshots
                ),
            })

            continue

        contract_records = (
            contract.get(
                "records"
            )
            or []
        )

        if not contract_records:

            skipped_visits.append({
                "visit_id": visit.id,

                "reason": (
                    "NO_LEARNING_RECORDS"
                ),
            })

            continue

        records.extend(
            contract_records
        )

        eligible_visit_count += 1

    # =====================================================
    # RESULT
    # =====================================================

    processed_visit_count = len(
        visit_list
    )

    skipped_visit_count = len(
        skipped_visits
    )

    ready = bool(
        records
    )

    return {
        "ready": ready,

        "reason": (
            "ML_DATASET_READY"
            if ready
            else "NO_ELIGIBLE_LEARNING_RECORDS"
        ),

        "schema_version": (
            "V2.8.12"
        ),

        "source_contract_schema_version": (
            "V2.8.11"
        ),

        "ml_training_performed": False,

        "ml_prediction_used": False,

        "model_version": None,

        "summary": {
            "processed_visits": (
                processed_visit_count
            ),

            "eligible_visits": (
                eligible_visit_count
            ),

            "skipped_visits": (
                skipped_visit_count
            ),

            "record_count": (
                len(
                    records
                )
            ),
        },

        "skipped_visits": (
            skipped_visits
        ),

        "records": (
            records
        ),
    }

def build_ml_dataset_export(
    visits=None,
    limit=None,
):
    """
    Build a flat, export-ready ML dataset contract.

    This service converts the canonical learning dataset
    into flat rows suitable for:

    - CSV export
    - Pandas DataFrame
    - Offline ML training pipelines
    - Data warehouse ingestion

    Important:
    - No ML model is loaded here.
    - No training is performed here.
    - No prediction is performed here.
    - Only records admitted by build_ml_learning_dataset()
      are exported.
    - Labels and metadata are explicitly separated
      from training features.
    """

    import json

    from django.core.serializers.json import (
        DjangoJSONEncoder,
    )

    # =====================================================
    # CANONICAL DATASET
    # =====================================================

    dataset = (
        build_ml_learning_dataset(
            visits=visits,
            limit=limit,
        )
    )

    source_records = (
        dataset.get(
            "records"
        )
        or []
    )

    # =====================================================
    # COLUMN CONTRACT
    # =====================================================

    metadata_columns = [
        "visit_id",
        "visit_date",
        "customer_id",
        "customer_code",
        "salesperson_id",
        "salesperson_code",
        "recommendation_id",
        "product_id",
        "product_code",
        "customer_snapshot_id",
        "customer_snapshot_captured_at",
        "commercial_snapshot_id",
        "commercial_snapshot_captured_at",
    ]

    training_feature_columns = [
        "recommendation_type",
        "recommendation_score",
        "recommendation_rank",

        "customer_segment",
        "customer_grade",
        "customer_total_orders",
        "customer_total_sales_amount",
        "customer_average_order_value",
        "customer_days_since_last_purchase",
        "customer_recency_score",
        "customer_frequency_score",
        "customer_monetary_score",
        "customer_rfm_score",
        "customer_top_category",
        "customer_top_product_code",

        "commercial_score",
        "commercial_priority",
        "commercial_blocked",
        "commercial_primary_product_code",
        "commercial_recommendation_type",
        "commercial_signals",
        "commercial_decision_reasons",

        "inventory_sellable_quantity",
        "inventory_is_in_stock",
        "inventory_is_low_stock",

        "promotion_count",
        "has_eligible_promotion",

        "target_count",
        "has_target_relevance",
    ]

    label_columns = [
        "final_outcome",
        "purchased",
        "engaged",
        "quantity",
        "sales_amount",
    ]

    # =====================================================
    # FLATTEN RECORDS
    # =====================================================

    rows = []

    for record in source_records:

        entity = (
            record.get(
                "entity"
            )
            or {}
        )

        features = (
            record.get(
                "features"
            )
            or {}
        )

        labels = (
            record.get(
                "labels"
            )
            or {}
        )

        feature_snapshot = (
            record.get(
                "feature_snapshot"
            )
            or {}
        )

        customer_feature_snapshot = (
            feature_snapshot.get(
                "customer"
            )
            or {}
        )

        commercial_feature_snapshot = (
            feature_snapshot.get(
                "commercial"
            )
            or {}
        )

        # =============================================
        # ROW
        # =============================================

        row = {
            # -----------------------------------------
            # Metadata
            # -----------------------------------------

            "visit_id": (
                entity.get(
                    "visit_id"
                )
            ),

            "visit_date": (
                entity.get(
                    "visit_date"
                )
            ),

            "customer_id": (
                entity.get(
                    "customer_id"
                )
            ),

            "customer_code": (
                entity.get(
                    "customer_code"
                )
            ),

            "salesperson_id": (
                entity.get(
                    "salesperson_id"
                )
            ),

            "salesperson_code": (
                entity.get(
                    "salesperson_code"
                )
            ),

            "recommendation_id": (
                entity.get(
                    "recommendation_id"
                )
            ),

            "product_id": (
                entity.get(
                    "product_id"
                )
            ),

            "product_code": (
                entity.get(
                    "product_code"
                )
            ),

            "customer_snapshot_id": (
                customer_feature_snapshot.get(
                    "snapshot_id"
                )
            ),

            "customer_snapshot_captured_at": (
                customer_feature_snapshot.get(
                    "captured_at"
                )
            ),

            "commercial_snapshot_id": (
                commercial_feature_snapshot.get(
                    "snapshot_id"
                )
            ),

            "commercial_snapshot_captured_at": (
                commercial_feature_snapshot.get(
                    "captured_at"
                )
            ),

            # -----------------------------------------
            # Training Features
            # -----------------------------------------

            "recommendation_type": (
                features.get(
                    "recommendation_type"
                )
            ),

            "recommendation_score": (
                features.get(
                    "recommendation_score"
                )
            ),

            "recommendation_rank": (
                features.get(
                    "recommendation_rank"
                )
            ),

            "customer_segment": (
                features.get(
                    "customer_segment"
                )
            ),

            "customer_grade": (
                features.get(
                    "customer_grade"
                )
            ),

            "customer_total_orders": (
                features.get(
                    "customer_total_orders"
                )
            ),

            "customer_total_sales_amount": (
                features.get(
                    "customer_total_sales_amount"
                )
            ),

            "customer_average_order_value": (
                features.get(
                    "customer_average_order_value"
                )
            ),

            "customer_days_since_last_purchase": (
                features.get(
                    "customer_days_since_last_purchase"
                )
            ),

            "customer_recency_score": (
                features.get(
                    "customer_recency_score"
                )
            ),

            "customer_frequency_score": (
                features.get(
                    "customer_frequency_score"
                )
            ),

            "customer_monetary_score": (
                features.get(
                    "customer_monetary_score"
                )
            ),

            "customer_rfm_score": (
                features.get(
                    "customer_rfm_score"
                )
            ),

            "customer_top_category": (
                features.get(
                    "customer_top_category"
                )
            ),

            "customer_top_product_code": (
                features.get(
                    "customer_top_product_code"
                )
            ),

            "commercial_score": (
                features.get(
                    "commercial_score"
                )
            ),

            "commercial_priority": (
                features.get(
                    "commercial_priority"
                )
            ),

            "commercial_blocked": (
                features.get(
                    "commercial_blocked"
                )
            ),

            "commercial_primary_product_code": (
                features.get(
                    "commercial_primary_product_code"
                )
            ),

            "commercial_recommendation_type": (
                features.get(
                    "commercial_recommendation_type"
                )
            ),

            "commercial_signals": (
                json.dumps(
                    features.get(
                        "commercial_signals"
                    )
                    or [],
                    cls=DjangoJSONEncoder,
                    ensure_ascii=False,
                )
            ),

            "commercial_decision_reasons": (
                json.dumps(
                    features.get(
                        "commercial_decision_reasons"
                    )
                    or [],
                    cls=DjangoJSONEncoder,
                    ensure_ascii=False,
                )
            ),

            "inventory_sellable_quantity": (
                features.get(
                    "inventory_sellable_quantity"
                )
            ),

            "inventory_is_in_stock": (
                features.get(
                    "inventory_is_in_stock"
                )
            ),

            "inventory_is_low_stock": (
                features.get(
                    "inventory_is_low_stock"
                )
            ),

            "promotion_count": (
                features.get(
                    "promotion_count"
                )
            ),

            "has_eligible_promotion": (
                features.get(
                    "has_eligible_promotion"
                )
            ),

            "target_count": (
                features.get(
                    "target_count"
                )
            ),

            "has_target_relevance": (
                features.get(
                    "has_target_relevance"
                )
            ),

            # -----------------------------------------
            # Labels
            # -----------------------------------------

            "final_outcome": (
                labels.get(
                    "final_outcome"
                )
            ),

            "purchased": (
                labels.get(
                    "purchased"
                )
            ),

            "engaged": (
                labels.get(
                    "engaged"
                )
            ),

            "quantity": (
                labels.get(
                    "quantity"
                )
            ),

            "sales_amount": (
                labels.get(
                    "sales_amount"
                )
            ),
        }

        rows.append(
            row
        )

    # =====================================================
    # EXPORT RESULT
    # =====================================================

    ready = bool(
        rows
    )

    return {
        "ready": ready,

        "reason": (
            "ML_DATASET_EXPORT_READY"
            if ready
            else "NO_EXPORTABLE_ML_RECORDS"
        ),

        "schema_version": (
            "V2.8.13"
        ),

        "source_dataset_schema_version": (
            dataset.get(
                "schema_version"
            )
        ),

        "source_contract_schema_version": (
            dataset.get(
                "source_contract_schema_version"
            )
        ),

        "ml_training_performed": False,

        "ml_prediction_used": False,

        "model_version": None,

        "columns": {
            "metadata": (
                metadata_columns
            ),

            "features": (
                training_feature_columns
            ),

            "labels": (
                label_columns
            ),

            "all": (
                metadata_columns
                + training_feature_columns
                + label_columns
            ),
        },

        "summary": {
            "processed_visits": (
                (
                    dataset.get(
                        "summary"
                    )
                    or {}
                ).get(
                    "processed_visits",
                    0,
                )
            ),

            "eligible_visits": (
                (
                    dataset.get(
                        "summary"
                    )
                    or {}
                ).get(
                    "eligible_visits",
                    0,
                )
            ),

            "skipped_visits": (
                (
                    dataset.get(
                        "summary"
                    )
                    or {}
                ).get(
                    "skipped_visits",
                    0,
                )
            ),

            "row_count": (
                len(
                    rows
                )
            ),

            "metadata_column_count": (
                len(
                    metadata_columns
                )
            ),

            "feature_column_count": (
                len(
                    training_feature_columns
                )
            ),

            "label_column_count": (
                len(
                    label_columns
                )
            ),
        },

        "skipped_visits": (
            dataset.get(
                "skipped_visits"
            )
            or []
        ),

        "rows": (
            rows
        ),
    }

def build_ml_dataset_quality_report(
    visits=None,
    limit=None,
):
    """
    Validate the export-ready ML dataset and build
    a deterministic data-quality report.

    Important:
    - No data is repaired or mutated here.
    - No missing value is imputed here.
    - No ML model is loaded here.
    - No training or prediction is performed here.
    - Validation is performed only on the canonical
      V2.8.13 dataset export contract.
    """

    # =====================================================
    # EXPORT CONTRACT
    # =====================================================

    dataset_export = (
        build_ml_dataset_export(
            visits=visits,
            limit=limit,
        )
    )

    columns = (
        dataset_export.get(
            "columns"
        )
        or {}
    )

    metadata_columns = list(
        columns.get(
            "metadata"
        )
        or []
    )

    feature_columns = list(
        columns.get(
            "features"
        )
        or []
    )

    label_columns = list(
        columns.get(
            "labels"
        )
        or []
    )

    all_columns = list(
        columns.get(
            "all"
        )
        or []
    )

    rows = list(
        dataset_export.get(
            "rows"
        )
        or []
    )

    # =====================================================
    # VALIDATION RULES
    # =====================================================

    required_metadata_columns = [
        "visit_id",
        "visit_date",
        "customer_id",
        "customer_code",
        "salesperson_id",
        "salesperson_code",
        "recommendation_id",
        "product_id",
        "product_code",
        "customer_snapshot_id",
        "customer_snapshot_captured_at",
        "commercial_snapshot_id",
        "commercial_snapshot_captured_at",
    ]

    required_label_columns = [
        "final_outcome",
        "purchased",
        "engaged",
        "quantity",
        "sales_amount",
    ]

    allowed_final_outcomes = {
        "PURCHASED",
        "INTERESTED",
        "FOLLOW_UP",
        "REJECTED",
        "NOT_PRESENTED",
    }

    binary_label_columns = [
        "purchased",
        "engaged",
    ]

    boolean_feature_columns = [
        "commercial_blocked",
        "inventory_is_in_stock",
        "inventory_is_low_stock",
        "has_eligible_promotion",
        "has_target_relevance",
    ]

    non_negative_numeric_columns = [
        "recommendation_score",
        "recommendation_rank",
        "customer_total_orders",
        "customer_total_sales_amount",
        "customer_average_order_value",
        "customer_days_since_last_purchase",
        "customer_recency_score",
        "customer_frequency_score",
        "customer_monetary_score",
        "customer_rfm_score",
        "commercial_score",
        "inventory_sellable_quantity",
        "promotion_count",
        "target_count",
        "quantity",
        "sales_amount",
    ]

    # =====================================================
    # CONTRACT VALIDATION
    # =====================================================

    metadata_set = set(
        metadata_columns
    )

    feature_set = set(
        feature_columns
    )

    label_set = set(
        label_columns
    )

    all_set = set(
        all_columns
    )

    metadata_feature_overlap = sorted(
        metadata_set
        & feature_set
    )

    metadata_label_overlap = sorted(
        metadata_set
        & label_set
    )

    feature_label_overlap = sorted(
        feature_set
        & label_set
    )

    duplicate_column_names = sorted({
        column
        for column in all_columns
        if all_columns.count(
            column
        ) > 1
    })

    expected_all_columns = (
        metadata_columns
        + feature_columns
        + label_columns
    )

    missing_required_metadata_columns = [
        column
        for column
        in required_metadata_columns
        if column not in metadata_set
    ]

    missing_required_label_columns = [
        column
        for column
        in required_label_columns
        if column not in label_set
    ]

    contract_checks = {
        "metadata_feature_disjoint": (
            not metadata_feature_overlap
        ),

        "metadata_label_disjoint": (
            not metadata_label_overlap
        ),

        "feature_label_disjoint": (
            not feature_label_overlap
        ),

        "no_duplicate_column_names": (
            not duplicate_column_names
        ),

        "all_columns_match_groups": (
            all_columns
            == expected_all_columns
        ),

        "required_metadata_columns_present": (
            not missing_required_metadata_columns
        ),

        "required_label_columns_present": (
            not missing_required_label_columns
        ),
    }

    # =====================================================
    # ACCUMULATORS
    # =====================================================

    row_issues = []

    missing_value_counts = {
        column: 0
        for column in all_columns
    }

    duplicate_identity_count = 0

    seen_identities = set()

    valid_row_count = 0
    invalid_row_count = 0

    # =====================================================
    # ROW VALIDATION
    # =====================================================

    for row_index, row in enumerate(
        rows,
        start=1,
    ):

        issues = []

        row_keys = set(
            row.keys()
        )

        missing_columns = sorted(
            all_set
            - row_keys
        )

        unexpected_columns = sorted(
            row_keys
            - all_set
        )

        if missing_columns:

            issues.append({
                "code": (
                    "MISSING_COLUMNS"
                ),

                "columns": (
                    missing_columns
                ),
            })

        if unexpected_columns:

            issues.append({
                "code": (
                    "UNEXPECTED_COLUMNS"
                ),

                "columns": (
                    unexpected_columns
                ),
            })

        # ==============================================
        # MISSING VALUE PROFILE
        # ==============================================

        for column in all_columns:

            value = row.get(
                column
            )

            if value is None:

                missing_value_counts[
                    column
                ] += 1

        # ==============================================
        # REQUIRED METADATA
        # ==============================================

        missing_required_metadata = [
            column
            for column
            in required_metadata_columns
            if row.get(
                column
            )
            is None
        ]

        if missing_required_metadata:

            issues.append({
                "code": (
                    "MISSING_REQUIRED_METADATA"
                ),

                "columns": (
                    missing_required_metadata
                ),
            })

        # ==============================================
        # LABEL VALIDATION
        # ==============================================

        final_outcome = row.get(
            "final_outcome"
        )

        if (
            final_outcome
            not in allowed_final_outcomes
        ):

            issues.append({
                "code": (
                    "INVALID_FINAL_OUTCOME"
                ),

                "value": (
                    final_outcome
                ),
            })

        for column in binary_label_columns:

            value = row.get(
                column
            )

            if value not in {
                0,
                1,
            }:

                issues.append({
                    "code": (
                        "INVALID_BINARY_LABEL"
                    ),

                    "column": (
                        column
                    ),

                    "value": (
                        value
                    ),
                })

        # ==============================================
        # OUTCOME / LABEL CONSISTENCY
        # ==============================================

        expected_purchased = (
            1
            if final_outcome
            == "PURCHASED"
            else 0
        )

        expected_engaged = (
            1
            if final_outcome
            in {
                "PURCHASED",
                "INTERESTED",
                "FOLLOW_UP",
            }
            else 0
        )

        if (
            row.get(
                "purchased"
            )
            != expected_purchased
        ):

            issues.append({
                "code": (
                    "PURCHASED_LABEL_MISMATCH"
                ),
            })

        if (
            row.get(
                "engaged"
            )
            != expected_engaged
        ):

            issues.append({
                "code": (
                    "ENGAGED_LABEL_MISMATCH"
                ),
            })

        # ==============================================
        # BOOLEAN FEATURES
        # ==============================================

        for column in boolean_feature_columns:

            value = row.get(
                column
            )

            if (
                value is not None
                and not isinstance(
                    value,
                    bool,
                )
            ):

                issues.append({
                    "code": (
                        "INVALID_BOOLEAN_FEATURE"
                    ),

                    "column": (
                        column
                    ),

                    "value": (
                        value
                    ),
                })

        # ==============================================
        # NON-NEGATIVE NUMERIC VALUES
        # ==============================================

        for column in non_negative_numeric_columns:

            value = row.get(
                column
            )

            if value is None:
                continue

            if (
                not isinstance(
                    value,
                    (int, float)
                )
                or isinstance(
                    value,
                    bool
                )
            ):

                issues.append({
                    "code": (
                        "INVALID_NUMERIC_TYPE"
                    ),

                    "column": (
                        column
                    ),

                    "value": (
                        value
                    ),
                })

                continue

            if value < 0:

                issues.append({
                    "code": (
                        "NEGATIVE_NUMERIC_VALUE"
                    ),

                    "column": (
                        column
                    ),

                    "value": (
                        value
                    ),
                })

        # ==============================================
        # SNAPSHOT CONSISTENCY
        # ==============================================

        if (
            row.get(
                "customer_snapshot_id"
            )
            is None
        ):

            issues.append({
                "code": (
                    "CUSTOMER_SNAPSHOT_MISSING"
                ),
            })

        if (
            row.get(
                "commercial_snapshot_id"
            )
            is None
        ):

            issues.append({
                "code": (
                    "COMMERCIAL_SNAPSHOT_MISSING"
                ),
            })

        # ==============================================
        # DUPLICATE LEARNING IDENTITY
        # ==============================================

        identity = (
            row.get(
                "visit_id"
            ),
            row.get(
                "recommendation_id"
            ),
        )

        if identity in seen_identities:

            duplicate_identity_count += 1

            issues.append({
                "code": (
                    "DUPLICATE_LEARNING_IDENTITY"
                ),

                "identity": (
                    identity
                ),
            })

        else:

            seen_identities.add(
                identity
            )

        # ==============================================
        # ROW RESULT
        # ==============================================

        if issues:

            invalid_row_count += 1

            row_issues.append({
                "row_number": (
                    row_index
                ),

                "visit_id": (
                    row.get(
                        "visit_id"
                    )
                ),

                "recommendation_id": (
                    row.get(
                        "recommendation_id"
                    )
                ),

                "issues": (
                    issues
                ),
            })

        else:

            valid_row_count += 1

    # =====================================================
    # MISSING VALUE SUMMARY
    # =====================================================

    row_count = len(
        rows
    )

    missing_feature_values = {
        column: (
            missing_value_counts.get(
                column,
                0,
            )
        )
        for column in feature_columns
        if (
            missing_value_counts.get(
                column,
                0,
            )
            > 0
        )
    }

    missing_metadata_values = {
        column: (
            missing_value_counts.get(
                column,
                0,
            )
        )
        for column in metadata_columns
        if (
            missing_value_counts.get(
                column,
                0,
            )
            > 0
        )
    }

    missing_label_values = {
        column: (
            missing_value_counts.get(
                column,
                0,
            )
        )
        for column in label_columns
        if (
            missing_value_counts.get(
                column,
                0,
            )
            > 0
        )
    }

    # =====================================================
    # DATA QUALITY LEVEL
    # =====================================================

    contract_valid = all(
        contract_checks.values()
    )

    dataset_valid = (
        contract_valid
        and invalid_row_count == 0
    )

    if not dataset_export.get(
        "ready"
    ):

        quality_level = (
            "NO_DATA"
        )

    elif not contract_valid:

        quality_level = (
            "INVALID_CONTRACT"
        )

    elif invalid_row_count > 0:

        quality_level = (
            "INVALID_ROWS"
        )

    elif missing_feature_values:

        quality_level = (
            "VALID_WITH_MISSING_FEATURES"
        )

    else:

        quality_level = (
            "VALID"
        )

    # =====================================================
    # TRAINING READINESS
    # =====================================================

    training_ready = (
        dataset_export.get(
            "ready"
        )
        is True
        and dataset_valid
        and row_count > 0
    )

    # =====================================================
    # FINAL REPORT
    # =====================================================

    return {
        "ready": True,

        "reason": (
            "ML_DATASET_QUALITY_REPORT_READY"
        ),

        "schema_version": (
            "V2.8.14"
        ),

        "source_export_schema_version": (
            dataset_export.get(
                "schema_version"
            )
        ),

        "source_dataset_schema_version": (
            dataset_export.get(
                "source_dataset_schema_version"
            )
        ),

        "source_contract_schema_version": (
            dataset_export.get(
                "source_contract_schema_version"
            )
        ),

        "dataset_ready": (
            dataset_export.get(
                "ready"
            )
            is True
        ),

        "dataset_valid": (
            dataset_valid
        ),

        "training_ready": (
            training_ready
        ),

        "quality_level": (
            quality_level
        ),

        "ml_training_performed": False,

        "ml_prediction_used": False,

        "model_version": None,

        "contract_validation": {
            "valid": (
                contract_valid
            ),

            "checks": (
                contract_checks
            ),

            "metadata_feature_overlap": (
                metadata_feature_overlap
            ),

            "metadata_label_overlap": (
                metadata_label_overlap
            ),

            "feature_label_overlap": (
                feature_label_overlap
            ),

            "duplicate_column_names": (
                duplicate_column_names
            ),

            "missing_required_metadata_columns": (
                missing_required_metadata_columns
            ),

            "missing_required_label_columns": (
                missing_required_label_columns
            ),
        },

        "summary": {
            "row_count": (
                row_count
            ),

            "valid_rows": (
                valid_row_count
            ),

            "invalid_rows": (
                invalid_row_count
            ),

            "duplicate_learning_identities": (
                duplicate_identity_count
            ),

            "columns": (
                len(
                    all_columns
                )
            ),

            "metadata_columns": (
                len(
                    metadata_columns
                )
            ),

            "feature_columns": (
                len(
                    feature_columns
                )
            ),

            "label_columns": (
                len(
                    label_columns
                )
            ),
        },

        "missing_values": {
            "metadata": (
                missing_metadata_values
            ),

            "features": (
                missing_feature_values
            ),

            "labels": (
                missing_label_values
            ),
        },

        "row_issues": (
            row_issues
        ),

        "skipped_visits": (
            dataset_export.get(
                "skipped_visits"
            )
            or []
        ),
    }