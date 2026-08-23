from apps.customers.services import (
    get_customer_by_code,
)

from .engine import RecommendationEngine
from django.utils import timezone

def generate_customer_recommendations(
    customer_code
):

    customer = get_customer_by_code(
        customer_code
    )

    if not customer:

        return None

    engine = RecommendationEngine(
        customer
    )

    recommendations = (
        engine.generate()
    )

    return {
        "customer": customer,

        "recommendations": recommendations,
    }

def generate_tuning_suggestions(
    performance=None,
):
    """
    Generate conservative recommendation tuning suggestions
    from resolved recommendation performance.

    Suggestions are never applied automatically.
    """

    from decimal import Decimal

    from apps.visits.services import (
        get_recommendation_performance,
    )

    from .models import (
        RecommendationConfig,
        RecommendationTuningSuggestion,
    )

    if performance is None:

        performance = (
            get_recommendation_performance(
                customer=None
            )
        )

    config = (
        RecommendationConfig.objects
        .filter(
            is_active=True,
        )
        .order_by(
            "-updated_at",
            "-id",
        )
        .first()
    )

    if not config:
        return []

    created = []

    for item in performance:

        if (
            item["data_quality"]
            != "SUFFICIENT_DATA"
        ):
            continue

        recommendation_type = (
            item["recommendation_type"]
        )

        learning_signal = (
            item["learning_signal"]
        )

        metric = None
        current_value = None
        suggested_value = None
        reason = ""

        if recommendation_type == "CROSS_SELL":

            metric = "association_max_score"

            current_value = (
                config.association_max_score
            )

        elif recommendation_type == "CATEGORY":

            metric = "category_rank_1_score"

            current_value = (
                config.category_rank_1_score
            )

        elif recommendation_type == "UP_SELL":

            metric = "upsell_25_percent_score"

            current_value = (
                config.upsell_25_percent_score
            )

        elif recommendation_type == "SIMILAR_PRODUCT":

            metric = "similar_product_score"

            current_value = (
                config.similar_product_score
            )

        elif recommendation_type == "REPEAT_PURCHASE":

            metric = "repurchase_no_cycle_score"

            current_value = (
                config.repurchase_no_cycle_score
            )

        if (
            not metric
            or current_value is None
        ):
            continue

        if learning_signal == "POSITIVE":

            suggested_value = (
                current_value
                + Decimal("2")
            )

            reason = (
                "Performance data shows a positive "
                "learning signal for this recommendation type."
            )

        elif learning_signal == "WEAK":

            suggested_value = max(
                Decimal("0"),
                current_value
                - Decimal("2"),
            )

            reason = (
                "Performance data shows a weak "
                "learning signal for this recommendation type."
            )

        else:
            continue

        existing = (
            RecommendationTuningSuggestion.objects
            .filter(
                recommendation_type=(
                    recommendation_type
                ),
                metric=metric,
                status=(
                    RecommendationTuningSuggestion
                    .Status
                    .PENDING
                ),
            )
            .exists()
        )

        if existing:
            continue

        suggestion = (
            RecommendationTuningSuggestion.objects
            .create(
                recommendation_type=(
                    recommendation_type
                ),

                metric=metric,

                current_value=(
                    current_value
                ),

                suggested_value=(
                    suggested_value
                ),

                reason=reason,

                performance_snapshot={
                    "presented": (
                        item["presented"]
                    ),
                    "purchased": (
                        item["purchased"]
                    ),
                    "interested": (
                        item["interested"]
                    ),
                    "follow_up": (
                        item["follow_up"]
                    ),
                    "rejected": (
                        item["rejected"]
                    ),
                    "conversion_rate": (
                        item["conversion_rate"]
                    ),
                    "interest_rate": (
                        item["interest_rate"]
                    ),
                    "engagement_rate": (
                        item["engagement_rate"]
                    ),
                    "learning_signal": (
                        item["learning_signal"]
                    ),
                    "performance_level": (
                        item["performance_level"]
                    ),
                    "data_quality": (
                        item["data_quality"]
                    ),
                },
            )
        )

        created.append(
            suggestion
        )

    return created

from django.utils import timezone


def update_tuning_suggestion_status(
    suggestion,
    new_status,
):
    """
    Review or apply a tuning suggestion.

    APPROVED:
        marks the suggestion as approved.

    REJECTED:
        marks the suggestion as rejected.

    APPLIED:
        writes suggested_value to the active
        RecommendationConfig and marks the suggestion
        as applied.
    """

    from .models import (
        RecommendationConfig,
        RecommendationTuningSuggestion,
    )

    allowed_statuses = {
        RecommendationTuningSuggestion.Status.APPROVED,
        RecommendationTuningSuggestion.Status.REJECTED,
        RecommendationTuningSuggestion.Status.APPLIED,
    }

    if new_status not in allowed_statuses:
        raise ValueError(
            "Invalid tuning suggestion status."
        )

    if (
        suggestion.status
        == RecommendationTuningSuggestion.Status.APPLIED
    ):
        raise ValueError(
            "Applied tuning suggestion cannot be changed."
        )

    if (
        new_status
        == RecommendationTuningSuggestion.Status.APPLIED
    ):

        if (
            suggestion.status
            != RecommendationTuningSuggestion.Status.APPROVED
        ):
            raise ValueError(
                "Tuning suggestion must be approved before apply."
            )

        config = (
            RecommendationConfig.objects
            .filter(
                is_active=True,
            )
            .order_by(
                "-updated_at",
                "-id",
            )
            .first()
        )

        if not config:
            raise ValueError(
                "Active RecommendationConfig not found."
            )

        if not hasattr(
            config,
            suggestion.metric,
        ):
            raise ValueError(
                "RecommendationConfig metric not found."
            )

        previous_value = getattr(
            config,
            suggestion.metric,
        )

        from decimal import Decimal

        minimum_allowed_value = Decimal("0")
        maximum_allowed_value = Decimal("100")
        maximum_allowed_delta = Decimal("10")

        suggested_value = (
            suggestion.suggested_value
        )

        if suggested_value is None:
            raise ValueError(
                "Suggested tuning value is required."
            )

        if (
            suggested_value
            < minimum_allowed_value
            or suggested_value
            > maximum_allowed_value
        ):
            raise ValueError(
                "Suggested tuning value is outside "
                "the allowed range."
            )

        delta = abs(
            suggested_value
            - previous_value
        )

        if delta > maximum_allowed_delta:
            raise ValueError(
                "Suggested tuning change exceeds "
                "the maximum allowed delta."
            )

        if (
            suggestion.current_value is not None
            and previous_value != suggestion.current_value
        ):
            raise ValueError(
                "Tuning suggestion is stale because "
                "the active configuration value has changed."
            )
        setattr(
            config,
            suggestion.metric,
            suggestion.suggested_value,
        )

        config.save(
            update_fields=[
                suggestion.metric,
                "updated_at",
            ]
        )

        suggestion.status = (
            RecommendationTuningSuggestion
            .Status
            .APPLIED
        )

        suggestion.applied_previous_value = (
            previous_value
        )

        suggestion.applied_at = (
            timezone.now()
        )

        suggestion.save(
            update_fields=[
                "status",
                "applied_at",
                "updated_at",
                "applied_previous_value",
            ]
        )

        return suggestion

    suggestion.status = new_status

    suggestion.reviewed_at = (
        timezone.now()
    )

    suggestion.save(
        update_fields=[
            "status",
            "reviewed_at",
            "updated_at",
        ]
    )

    return suggestion

def rollback_tuning_suggestion(
    suggestion,
):
    """
    Roll back an applied tuning suggestion.

    The active RecommendationConfig value is restored
    to the value captured at apply time.
    """

    from django.utils import timezone

    from .models import (
        RecommendationConfig,
        RecommendationTuningSuggestion,
    )

    if (
        suggestion.status
        != RecommendationTuningSuggestion.Status.APPLIED
    ):
        raise ValueError(
            "Only applied tuning suggestions can be rolled back."
        )

    if suggestion.applied_previous_value is None:
        raise ValueError(
            "Previous applied value is not available for rollback."
        )

    config = (
        RecommendationConfig.objects
        .filter(
            is_active=True,
        )
        .order_by(
            "-updated_at",
            "-id",
        )
        .first()
    )

    if not config:
        raise ValueError(
            "Active RecommendationConfig not found."
        )

    if not hasattr(
        config,
        suggestion.metric,
    ):
        raise ValueError(
            "RecommendationConfig metric not found."
        )

    setattr(
        config,
        suggestion.metric,
        suggestion.applied_previous_value,
    )

    config.save(
        update_fields=[
            suggestion.metric,
            "updated_at",
        ]
    )

    suggestion.status = (
        RecommendationTuningSuggestion
        .Status
        .ROLLED_BACK
    )

    suggestion.rolled_back_at = (
        timezone.now()
    )

    suggestion.save(
        update_fields=[
            "status",
            "rolled_back_at",
            "updated_at",
        ]
    )

    return suggestion