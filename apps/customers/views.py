from django.shortcuts import render

from .services import get_customer_360


def customer_search(request):

    customer_code = request.GET.get(
        "customer_code",
        ""
    ).strip()

    context = {
        "customer_code": customer_code,
        "customer": None,
        "customer_360": None,
        "not_found": False,
    }

    if customer_code:

        result = get_customer_360(
            customer_code
        )

        if result:

            context.update(result)

        else:

            context["not_found"] = True

    return render(
        request,
        "core/customer_360.html",
        context,
    )