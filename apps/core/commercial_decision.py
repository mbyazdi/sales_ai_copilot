def _build_commercial_priority(
    primary_recommendation,
    target_relevance,
    commercial_context,
):
    """
    Build an explainable commercial priority.

    Recommendation fit remains authoritative.
    Commercial signals only influence execution
    priority around that recommendation.
    """

    if primary_recommendation is None:

        return {
            "score": 0,
            "priority": "NORMAL",
            "reasons": [],
            "why_now": [],
            "is_blocked": False,
        }

    score = 0
    reasons = []
    why_now = []

    # ==========================================
    # RECOMMENDATION FIT
    # ==========================================

    recommendation_score = float(
        primary_recommendation.score or 0
    )

    confidence_score = float(
        primary_recommendation
        .confidence_score
        or 0
    )

    if recommendation_score >= 80:

        score += 3

        reasons.append(
            "STRONG_RECOMMENDATION"
        )

    elif recommendation_score >= 50:

        score += 2

        reasons.append(
            "GOOD_RECOMMENDATION"
        )

    elif recommendation_score > 0:

        score += 1

        reasons.append(
            "ACTIVE_RECOMMENDATION"
        )

    if confidence_score >= 80:

        score += 2

        reasons.append(
            "HIGH_CONFIDENCE"
        )

    elif confidence_score >= 60:

        score += 1

        reasons.append(
            "MODERATE_CONFIDENCE"
        )

    # ==========================================
    # TARGET
    # ==========================================

    if target_relevance:

        at_risk_targets = [
            target
            for target in target_relevance
            if (
                target.get(
                    "achievement_percent",
                    0,
                )
                < 70
            )
        ]

        if at_risk_targets:

            score += 2

            reasons.append(
                "AT_RISK_TARGET"
            )

            why_now.append(
                "The recommendation supports "
                "an at-risk sales target."
            )

        else:

            score += 1

            reasons.append(
                "TARGET_RELEVANT"
            )

            why_now.append(
                "The recommendation contributes "
                "to an active sales target."
            )

    # ==========================================
    # COMMERCIAL CONTEXT
    # ==========================================

    commercial_context = (
        commercial_context or {}
    )

    promotions = (
        commercial_context.get(
            "promotions"
        )
        or []
    )

    inventory = (
        commercial_context.get(
            "inventory"
        )
        or {}
    )

    if promotions:

        score += 2

        reasons.append(
            "ELIGIBLE_PROMOTION"
        )

        why_now.append(
            "An eligible active promotion "
            "is available."
        )

    is_in_stock = inventory.get(
        "is_in_stock"
    )

    is_low_stock = inventory.get(
        "is_low_stock"
    )

    if is_in_stock is True:

        score += 1

        reasons.append(
            "IN_STOCK"
        )

    # ==========================================
    # AVAILABILITY GUARDRAILS
    # ==========================================

    if is_in_stock is False:

        return {
            "score": score,
            "priority": "BLOCKED",
            "reasons": (
                reasons
                + [
                    "OUT_OF_STOCK"
                ]
            ),
            "why_now": (
                why_now
                + [
                    "The product is currently "
                    "out of stock."
                ]
            ),
            "is_blocked": True,
        }

    if score >= 7:

        priority = "HIGH"

    elif score >= 4:

        priority = "MEDIUM"

    else:

        priority = "NORMAL"

    if is_low_stock is True:

        reasons.append(
            "LOW_STOCK"
        )

        why_now.append(
            "Inventory is low, so availability "
            "should be confirmed before closing."
        )

        if priority == "HIGH":
            priority = "MEDIUM"

    return {
        "score": score,
        "priority": priority,
        "reasons": reasons,
        "why_now": why_now,
        "is_blocked": False,
    }

def build_base_sales_session(
    customer,
    customer_360,
    primary_recommendation=None,
    target_relevance=None,
    commercial_context=None,
):
    """
    Build the canonical deterministic sales-session
    guidance used by Customer 360 and AI Copilot.

    Phase 1 preserves the existing behavior.
    Commercial signals are added in later V2.5 steps.
    """

    # ==========================================
    # CUSTOMER STATUS
    # ==========================================

    if (
        customer_360
        and customer_360.segment
        == "HIGH_VALUE"
    ):
        target_relevance = list(
            target_relevance or []
        )

        commercial_context = (
            commercial_context or {}
        )
        customer_status = (
            "مشتری با ارزش بالا و دارای "
            "پتانسیل مناسب برای فروش مجدد"
        )

    else:
        customer_status = (
            "مشتری فعال با فرصت‌های فروش "
            "قابل بررسی"
        )

    # ==========================================
    # SALES OPPORTUNITY
    # ==========================================

    days_since_last_purchase = (
        customer_360.days_since_last_purchase
        if customer_360
        else None
    )

    if (
        days_since_last_purchase
        is not None
        and days_since_last_purchase >= 20
    ):
        sales_opportunity = (
            f"مشتری {days_since_last_purchase} "
            "روز است که خریدی نداشته است. "
            "این موضوع می‌تواند یک فرصت مناسب "
            "برای پیگیری فروش باشد."
        )

    else:
        sales_opportunity = (
            "مشتری اخیراً خرید داشته است. "
            "تمرکز روی فروش مکمل و محصولات مرتبط "
            "پیشنهاد می‌شود."
        )

    # ==========================================
    # PRIMARY PRODUCT
    # ==========================================

    if primary_recommendation:

        product = (
            primary_recommendation.product
        )

        primary_product = (
            product.name
        )

        primary_product_code = (
            product.product_code
        )

        primary_reason = (
            primary_recommendation.reason
        )

        recommendation_type = (
            primary_recommendation
            .recommendation_type
        )

    else:

        primary_product = None
        primary_product_code = None
        primary_reason = None
        recommendation_type = None

    # ==========================================
    # NEXT BEST ACTION
    # ==========================================

    if primary_recommendation:

        if (
            recommendation_type
            == "REPEAT_PURCHASE"
        ):
            next_best_action = (
                f"پیشنهاد خرید مجدد "
                f"{primary_product} "
                "را مطرح کنید."
            )

        elif (
            recommendation_type
            == "CROSS_SELL"
        ):
            next_best_action = (
                f"محصول مکمل "
                f"{primary_product} "
                "را مطرح کنید."
            )

        elif (
            recommendation_type
            == "UP_SELL"
        ):
            next_best_action = (
                f"مشتری را به گزینه بالاتر "
                f"{primary_product} "
                "هدایت کنید."
            )

        elif (
            recommendation_type
            == "CATEGORY"
        ):
            next_best_action = (
                f"محصول {primary_product} "
                "را از دسته مورد علاقه مشتری "
                "معرفی کنید."
            )

        elif (
            recommendation_type
            == "SIMILAR_PRODUCT"
        ):
            next_best_action = (
                f"{primary_product} "
                "را به عنوان گزینه مشابه "
                "مطرح کنید."
            )

        else:
            next_best_action = (
                f"{primary_product} "
                "را به عنوان پیشنهاد اصلی "
                "مطرح کنید."
            )

    else:
        next_best_action = (
            "در حال حاضر پیشنهاد مشخصی "
            "برای این مشتری وجود ندارد."
        )

    # ==========================================
    # TALKING POINT
    # ==========================================

    if primary_recommendation:

        if (
            recommendation_type
            == "REPEAT_PURCHASE"
        ):
            talking_point = (
                "با توجه به سابقه خرید مشتری، "
                f"درباره خرید مجدد "
                f"{primary_product} "
                "با مشتری صحبت کنید."
            )

        elif (
            recommendation_type
            == "CROSS_SELL"
        ):
            talking_point = (
                "با توجه به خریدهای قبلی مشتری، "
                f"{primary_product} "
                "را به عنوان محصول مکمل "
                "معرفی کنید."
            )

        elif (
            recommendation_type
            == "CATEGORY"
        ):
            talking_point = (
                "با توجه به علاقه مشتری "
                "به این دسته، "
                f"{primary_product} "
                "را به عنوان گزینه جدید "
                "مطرح کنید."
            )

        elif (
            recommendation_type
            == "SIMILAR_PRODUCT"
        ):
            talking_point = (
                f"{primary_product} "
                "را به عنوان جایگزین یا "
                "گزینه مشابه معرفی کنید."
            )

        else:
            talking_point = (
                f"محصول {primary_product} "
                "را به عنوان یکی از "
                "گزینه‌های اصلی معرفی کنید."
            )

    else:
        talking_point = (
            "ابتدا نیاز فعلی مشتری "
            "را بررسی کنید."
        )

    # ==========================================
    # COMMERCIAL SIGNALS
    # ==========================================

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

    has_eligible_promotion = bool(
        commercial_context.get(
            "has_eligible_promotion"
        )
    )

    in_stock = (
        inventory_context.get(
            "is_in_stock"
        )
    )

    low_stock = (
        inventory_context.get(
            "is_low_stock"
        )
    )

    commercial_signals = []

    if target_relevance:

        commercial_signals.append(
            "TARGET_RELEVANT"
        )

    if has_eligible_promotion:

        commercial_signals.append(
            "ELIGIBLE_PROMOTION"
        )

    if in_stock is True:

        commercial_signals.append(
            "IN_STOCK"
        )

    if low_stock is True:

        commercial_signals.append(
            "LOW_STOCK"
        )

    if in_stock is False:

        commercial_signals.append(
            "OUT_OF_STOCK"
        )

    commercial_priority = (
        _build_commercial_priority(
            primary_recommendation=(
                primary_recommendation
            ),
            target_relevance=(
                target_relevance
            ),
            commercial_context=(
                commercial_context
            ),
        )
    )
    return {
        "customer_status": (
            customer_status
        ),

        "sales_opportunity": (
            sales_opportunity
        ),

        "primary_product": (
            primary_product
        ),

        "primary_product_code": (
            primary_product_code
        ),

        "primary_reason": (
            primary_reason
        ),

        "recommendation_type": (
            recommendation_type
        ),

        "next_best_action": (
            next_best_action
        ),

        "talking_point": (
            talking_point
        ),
        "target_context": (
            target_relevance
        ),

        "inventory_context": (
            inventory_context
        ),

        "promotion_context": (
            promotion_context
        ),

        "commercial_signals": (
            commercial_signals
        ),
        "commercial_score": (
            commercial_priority[
                "score"
            ]
        ),

        "commercial_priority": (
            commercial_priority[
                "priority"
            ]
        ),

        "decision_reasons": (
            commercial_priority[
                "reasons"
            ]
        ),

        "why_now": (
            commercial_priority[
                "why_now"
            ]
        ),

        "commercial_blocked": (
            commercial_priority[
                "is_blocked"
            ]
        ),        
    }