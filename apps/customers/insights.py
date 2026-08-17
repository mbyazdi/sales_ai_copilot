def build_customer_insight(customer, customer_360, recommendations):
    """
    Build a sales insight from existing Customer 360
    and recommendation data.

    This version does NOT use an LLM.
    It creates deterministic insights for the demo.
    """

    if not customer_360:
        return {
            "headline": "Customer insight is not available.",
            "summary": "",
            "opportunity": "",
            "action": "",
        }

    segment = customer_360.segment

    days_since_purchase = (
        customer_360.days_since_last_purchase
    )

    top_category = (
        customer_360.top_category
    )

    top_product = (
        customer_360.top_product_code
    )

    recommendation = (
        recommendations[0]
        if recommendations
        else None
    )

    insight = {
        "headline": "",
        "summary": "",
        "opportunity": "",
        "action": "",
    }

    # -----------------------------------------
    # Headline
    # -----------------------------------------

    if segment == "HIGH_VALUE":

        insight["headline"] = (
            "High-value customer with strong "
            "sales potential"
        )

    else:

        insight["headline"] = (
            "Customer opportunity identified"
        )


    # -----------------------------------------
    # Summary
    # -----------------------------------------

    insight["summary"] = (
        f"{customer.name} is a {segment.replace('_', ' ').lower()} "
        f"customer. "
        f"The customer's top category is "
        f"{top_category}, with "
        f"{top_product} as the top product."
    )


    # -----------------------------------------
    # Opportunity
    # -----------------------------------------

    if days_since_purchase >= 20:

        insight["opportunity"] = (
            f"The customer has not purchased for "
            f"{days_since_purchase} days. "
            f"This may be a good opportunity for "
            f"a follow-up sales visit."
        )

    else:

        insight["opportunity"] = (
            "The customer has purchased recently. "
            "Focus on cross-sell and up-sell opportunities."
        )


    # -----------------------------------------
    # Recommended action
    # -----------------------------------------

    if recommendation:

        product = recommendation.product

        insight["action"] = (
            f"Recommend {product.name} "
            f"({product.product_code}) "
            f"as the primary product to discuss "
            f"with the customer."
        )

    else:

        insight["action"] = (
            "Review the customer's recent purchases "
            "and identify cross-sell opportunities."
        )


    return insight