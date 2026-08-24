from decimal import Decimal
from datetime import date, datetime


def _serialize_value(value):

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (date, datetime)):
        return value.isoformat()

    return value


def build_sales_copilot_prompt(
    sales_ai_context,
):
    """
    Build a controlled prompt for Sales AI Copilot.

    The LLM must NOT change recommendation decisions.
    It only explains and assists the salesperson.
    """

    customer = (
        sales_ai_context.get("customer")
        or {}
    )

    customer_360 = (
        sales_ai_context.get("customer_360")
        or {}
    )

    current_visit = (
        sales_ai_context.get("current_visit")
        or {}
    )

    sales_session = (
        sales_ai_context.get("sales_session")
        or {}
    )

    recommendations = (
        sales_ai_context.get("recommendations")
        or []
    )

    lines = []

    lines.append(
        "You are a Sales AI Copilot."
    )

    lines.append(
        ""
    )

    lines.append(
        "IMPORTANT RULES:"
    )

    lines.append(
        "- Commercial Priority, Commercial Score, "
        "Decision Reasons, Why Now, Target Context, "
        "Inventory Context, and Promotion Context are "
        "authoritative backend facts."
    )

    lines.append(
        "- Do NOT recalculate, override, reinterpret, "
        "or invent Commercial Priority or Commercial Score."
    )

    lines.append(
        "- Do NOT infer a promotion benefit beyond the "
        "explicit promotion fields provided in context."
    )

    lines.append(
        "- Do NOT infer inventory availability beyond the "
        "explicit inventory fields provided in context."
    )

    lines.append(
        "- If Commercial Blocked is true, do not encourage "
        "the salesperson to close the sale without resolving "
        "the blocking condition."
    )

    lines.append(
        "- Product recommendations have already been "
        "decided by a Rule-Based Recommendation Engine."
    )

    lines.append(
        "- Do NOT replace, reorder, or invent recommendations."
    )

    lines.append(
        "- Do NOT make pricing, inventory, promotion, "
        "or product claims that are not present in the context."
    )

    lines.append(
        "- Your role is to explain the recommendation, "
        "summarize the customer context, and help the "
        "salesperson conduct the meeting."
    )

    lines.append(
        "- Answer in Persian unless the salesperson "
        "explicitly requests another language."
    )

    lines.append(
        ""
    )

    lines.append(
        "CUSTOMER:"
    )

    lines.append(
        f"- Code: {customer.get('customer_code')}"
    )

    lines.append(
        f"- Name: {customer.get('name')}"
    )

    lines.append(
        f"- Type: {customer.get('customer_type')}"
    )

    lines.append(
        f"- City: {customer.get('city')}"
    )

    lines.append(
        f"- Grade: {customer.get('grade')}"
    )

    lines.append(
        ""
    )

    lines.append(
        "CUSTOMER 360:"
    )

    for key in [
        "segment",
        "total_orders",
        "last_purchase_date",
        "days_since_last_purchase",
    ]:

        value = _serialize_value(
            customer_360.get(key)
        )

        lines.append(
            f"- {key}: {value}"
        )

    lines.append(
        ""
    )

    lines.append(
        "CURRENT VISIT:"
    )

    if current_visit:

        lines.append(
            f"- Visit ID: "
            f"{current_visit.get('visit_id')}"
        )

        lines.append(
            f"- Visit Date: "
            f"{_serialize_value(current_visit.get('visit_date'))}"
        )

        lines.append(
            f"- Status: "
            f"{current_visit.get('status')}"
        )

        salesperson = (
            current_visit.get("salesperson")
            or {}
        )

        lines.append(
            f"- Salesperson: "
            f"{salesperson.get('full_name')}"
        )

    else:

        lines.append(
            "- No current visit context."
        )

    lines.append(
        ""
    )

    lines.append(
        "SALES SESSION:"
    )

    lines.append(
        f"- Customer Status: "
        f"{sales_session.get('customer_status')}"
    )

    lines.append(
        f"- Sales Opportunity: "
        f"{sales_session.get('sales_opportunity')}"
    )

    lines.append(
        f"- Approved Next Best Action: "
        f"{sales_session.get('next_best_action')}"
    )

    lines.append(
        f"- Approved Talking Point: "
        f"{sales_session.get('talking_point')}"
    )

    lines.append(
        f"- Commercial Priority: "
        f"{sales_session.get('commercial_priority')}"
    )

    lines.append(
        f"- Commercial Score: "
        f"{sales_session.get('commercial_score')}"
    )

    lines.append(
        f"- Commercial Blocked: "
        f"{sales_session.get('commercial_blocked')}"
    )

    decision_reasons = (
        sales_session.get(
            "decision_reasons"
        )
        or []
    )

    if decision_reasons:

        lines.append(
            "- Decision Reasons:"
        )

        for reason in decision_reasons:

            lines.append(
                f"  - {reason}"
            )

    why_now = (
        sales_session.get(
            "why_now"
        )
        or []
    )

    if why_now:

        lines.append(
            "- Why Now:"
        )

        for item in why_now:

            lines.append(
                f"  - {item}"
            )

    target_context = (
        sales_session.get(
            "target_context"
        )
        or []
    )

    inventory_context = (
        sales_session.get(
            "inventory_context"
        )
        or {}
    )

    promotion_context = (
        sales_session.get(
            "promotion_context"
        )
        or []
    )

    lines.append(
        ""
    )

    lines.append(
        "COMMERCIAL CONTEXT:"
    )

    if target_context:

        lines.append(
            "- Target Context:"
        )

        for target in target_context:

            scope = (
                target.get(
                    "scope"
                )
                or {}
            )

            lines.append(
                "  - "
                f"{scope.get('type')} "
                f"{scope.get('code')} "
                f"| Achievement: "
                f"{_serialize_value(target.get('achievement_percent'))}% "
                f"| Remaining: "
                f"{_serialize_value(target.get('remaining_value'))}"
            )

    else:

        lines.append(
            "- Target Context: none"
        )

    if inventory_context:

        lines.append(
            f"- Inventory Sellable Quantity: "
            f"{_serialize_value(inventory_context.get('sellable_quantity'))}"
        )

        lines.append(
            f"- Inventory Low Stock: "
            f"{inventory_context.get('is_low_stock')}"
        )

        lines.append(
            f"- Inventory In Stock: "
            f"{inventory_context.get('is_in_stock')}"
        )

    else:

        lines.append(
            "- Inventory Context: not available"
        )

    if promotion_context:

        lines.append(
            "- Eligible Promotions:"
        )

        for promotion in promotion_context:

            lines.append(
                "  - "
                f"{promotion.get('code')} "
                f"| {promotion.get('name')} "
                f"| Type: "
                f"{promotion.get('promotion_type')}"
            )

    else:

        lines.append(
            "- Eligible Promotions: none"
        )

    lines.append(
        ""
    )

    lines.append(
        "RECOMMENDATIONS:"
    )
    lines.append(
        ""
    )

    # =====================================================
    # AUTHORITATIVE RECOMMENDATION
    # =====================================================

    lines.append(
        "AUTHORITATIVE RECOMMENDATION:"
    )

    if recommendations:

        primary = recommendations[0]

        lines.append(
            f"- Product: "
            f"{primary.get('product_name')}"
        )

        lines.append(
            f"- Product Code: "
            f"{primary.get('product_code')}"
        )

        lines.append(
            f"- Recommendation Type: "
            f"{primary.get('recommendation_type')}"
        )

        lines.append(
            f"- Score: "
            f"{_serialize_value(primary.get('score'))}"
        )

        explanation = (
            primary.get(
                "authoritative_explanation"
            )
            or primary.get(
                "reason"
            )
        )

        if explanation:

            lines.append(
                f"- Authoritative Explanation: "
                f"{explanation}"
            )

    else:

        lines.append(
            "- No active recommendation."
        )


    # =====================================================
    # FINAL RESPONSE RULES
    # =====================================================
    lines.append(
        "- When asked what the salesperson should do, "
        "base the answer primarily on Approved Next Best Action."
    )

    lines.append(
        "- When suggesting what the salesperson should say, "
        "base the answer primarily on Approved Talking Point."
    )
    
    lines.append(
        "- You MAY use sales_session.next_best_action "
        "as approved sales guidance."
    )

    lines.append(
        "- You MAY use sales_session.talking_point "
        "as approved wording for the salesperson."
    )
    lines.append(
        ""
    )

    lines.append(
        "FINAL RESPONSE RULES:"
    )

    lines.append(
        "- Use only facts explicitly present "
        "in this context."
    )

    lines.append(
        "- The Authoritative Recommendation is "
        "the only product recommendation you may discuss."
    )

    lines.append(
        "- Treat Authoritative Explanation as the only "
        "authoritative source for why the recommendation exists."
    )

    lines.append(
        "- Do not extend, reinterpret, strengthen, "
        "or add meaning to Authoritative Explanation."
    )

    lines.append(
        "- Do not infer relationships between customer metrics "
        "and the recommended product unless explicitly stated."
    )

    lines.append(
        "- Do NOT say the customer previously purchased "
        "the recommended product unless that exact fact "
        "is explicitly present in the context."
    )

    lines.append(
        "- Do NOT say the recommended product belongs to "
        "the customer's historical or preferred category "
        "unless that exact relationship is explicitly provided."
    )

    lines.append(
        "- Do NOT infer anything from customer grade or segment "
        "about the recommended product."
    )

    lines.append(
        "- Treat Recommendation Type only as a label produced "
        "by the Recommendation Engine."
    )

    lines.append(
        "- Recommendation Type is NOT evidence of past "
        "or future customer behavior."
    )

    lines.append(
        "- Never predict that the customer will purchase "
        "the recommended product."
    )

    lines.append(
        "- Never convert recommendation evidence into "
        "a new fact about customer behavior."
    )

    lines.append(
        "- Do not invent prices, promotions, inventory, "
        "product relationships, purchase history, "
        "customer preferences, objections, or intent."
    )

    lines.append(
        "- When explaining why the product was recommended, "
        "attribute the explanation to the Recommendation Engine."
    )

    lines.append(
        "- Prefer wording such as: "
        "'طبق موتور پیشنهاددهی...' or "
        "'بر اساس دلیل ثبت‌شده برای این پیشنهاد...'."
    )

    lines.append(
        "- If the available context does not support a new factual claim, "
        "do not invent one. Instead, rely on Next Best Action, "
        "Talking Point, and Authoritative Explanation."
    )

    lines.append(
        "- Answer in concise, practical, professional Persian."
    )

    lines.append(
        "- Do not expose internal reasoning."
    )

    return "\n".join(lines)