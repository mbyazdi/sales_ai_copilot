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
        "total_sales_amount",
        "average_order_value",
        "last_purchase_date",
        "days_since_last_purchase",
        "top_category",
        "top_product_code",
        "rfm_score",
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
        f"- Next Best Action: "
        f"{sales_session.get('next_best_action')}"
    )

    lines.append(
        f"- Talking Point: "
        f"{sales_session.get('talking_point')}"
    )

    lines.append(
        ""
    )

    lines.append(
        "RECOMMENDATIONS:"
    )

    if recommendations:

        for recommendation in recommendations:

            lines.append(
                (
                    f"- Rank {recommendation.get('rank')}: "
                    f"{recommendation.get('product_name')} "
                    f"({recommendation.get('product_code')}) | "
                    f"Type: "
                    f"{recommendation.get('recommendation_type')} | "
                    f"Score: "
                    f"{_serialize_value(recommendation.get('score'))}"
                )
            )

            if recommendation.get("reason"):

                lines.append(
                    f"  Reason: "
                    f"{recommendation.get('reason')}"
                )

    else:

        lines.append(
            "- No active recommendations."
        )

    lines.append(
        ""
    )

    lines.append(
        "Respond as a practical sales assistant."
    )

    lines.append(
        "Keep the response concise, actionable, "
        "and grounded only in the provided context."
    )

    return "\n".join(lines)