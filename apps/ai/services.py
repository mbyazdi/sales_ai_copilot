from .ollama_client import (
    OllamaClient,
)

from .prompts import (
    SALES_COPILOT_SYSTEM_PROMPT,
)


def generate_sales_copilot_response(
    sales_ai_context,
    user_message=None,
):
    """
    Generate a controlled Sales Copilot response.

    Business facts and recommendation decisions are
    controlled by Backend.

    The LLM is only used to produce a short,
    salesperson-friendly wording.
    """

    sales_session = (
        sales_ai_context.get(
            "sales_session"
        )
        or {}
    )

    recommendations = (
        sales_ai_context.get(
            "recommendations"
        )
        or []
    )

    primary = (
        recommendations[0]
        if recommendations
        else {}
    )

    # =====================================================
    # CONTROLLED BACKEND FACTS
    # =====================================================

    product_name = (
        primary.get("product_name")
        or "—"
    )

    product_code = (
        primary.get("product_code")
        or "—"
    )

    recommendation_type = (
        primary.get(
            "recommendation_type"
        )
        or "—"
    )

    score = float(
        primary.get("score")
        or 0
    )

    authoritative_explanation = (
        primary.get(
            "authoritative_explanation"
        )
        or primary.get("reason")
        or ""
    )

    next_best_action = (
        sales_session.get(
            "next_best_action"
        )
        or ""
    )

    talking_point = (
        sales_session.get(
            "talking_point"
        )
        or ""
    )

    # =====================================================
    # LIMITED LLM TASK
    # =====================================================

    language_prompt = (
        "فقط جمله پیشنهادی زیر را به فارسی روان، "
        "کوتاه و حرفه‌ای برای استفاده فروشنده "
        "در جلسه بازنویسی کن.\n\n"

        "هیچ واقعیت، محصول، دلیل، سابقه خرید، "
        "قیمت، تخفیف یا اطلاعات جدیدی اضافه نکن.\n\n"

        f"APPROVED TALKING POINT:\n"
        f"{talking_point}\n\n"

        f"APPROVED NEXT ACTION:\n"
        f"{next_best_action}\n\n"

        "فقط یک جمله کوتاه، طبیعی و کاربردی فارسی برگردان."
    )

    if user_message:

        language_prompt += (
            "\n\n"
            "SALESPERSON REQUEST:\n"
            f"{user_message.strip()}\n\n"
            "در پاسخ به درخواست فروشنده نیز "
            "فقط همین دو متن تاییدشده را "
            "بازنویسی کن و اطلاعات جدید نساز."
        )

    client = OllamaClient()

    ai_result = client.generate(
        prompt=language_prompt,
        system=(
            SALES_COPILOT_SYSTEM_PROMPT
        ),
    )

    suggested_wording = (
        ai_result.get("response")
        or talking_point
    ).strip()

    # =====================================================
    # FINAL CONTROLLED RESPONSE
    # =====================================================

    response_text = (
        f"پیشنهاد اصلی: "
        f"{product_name} "
        f"({product_code})\n\n"

        f"نوع پیشنهاد: "
        f"{recommendation_type}\n"

        f"امتیاز موتور پیشنهاددهی: "
        f"{score}\n\n"

        f"اقدام پیشنهادی: "
        f"{next_best_action}\n\n"

        f"دلیل ثبت‌شده توسط موتور پیشنهاددهی: "
        f"{authoritative_explanation}\n\n"

        f"جمله پیشنهادی برای فروشنده: "
        f"{suggested_wording}"
    )

    return {
        "response": response_text,
        "model": ai_result.get(
            "model"
        ),
        "done": ai_result.get(
            "done",
            True,
        ),
    }