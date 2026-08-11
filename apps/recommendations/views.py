from django.shortcuts import render

from .services import (
    generate_customer_recommendations,
)


def customer_recommendations(request):

    customer_code = request.GET.get(
        "customer_code",
        "",
    ).strip()

    context = {
        "customer_code": customer_code,
        "customer": None,
        "recommendations": [],
        "not_found": False,
    }

    if customer_code:

        result = (
            generate_customer_recommendations(
                customer_code
            )
        )

        if result:

            context.update(result)

        else:

            context["not_found"] = True

    return render(
        request,
        "core/recommendations.html",
        context,
    )