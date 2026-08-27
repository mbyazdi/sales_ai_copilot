import json

from .ollama_client import (
    OllamaClient,
    OllamaClientError,
)

from .prompts import (
    SALES_COPILOT_SYSTEM_PROMPT,
    EXECUTIVE_INTELLIGENCE_SYSTEM_PROMPT,
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


def generate_management_executive_narrative(
    executive_context,
):
    """
    Build V3.0.8.2 controlled executive narrative.

    The supplied V3.0.8.1 context is authoritative.

    Ollama may only convert approved facts into natural
    management language.

    No KPI calculation, ranking, prediction, or causal
    inference is allowed here.
    """

    if not executive_context:

        raise ValueError(
            "executive_context is required."
        )

    if (
        executive_context.get(
            "schema_version"
        )
        != "V3.0.8.1"
    ):

        raise ValueError(
            "V3.0.8.1 executive context is required."
        )

    if (
        executive_context.get(
            "ready"
        )
        is not True
    ):

        raise ValueError(
            "Executive intelligence context is not ready."
        )

    summary = (
        executive_context.get(
            "executive_summary"
        )
        or {}
    )

    performance_facts = (
        executive_context.get(
            "performance_facts"
        )
        or {}
    )

    sales_team_facts = (
        executive_context.get(
            "sales_team_facts"
        )
        or {}
    )

    data_quality = (
        executive_context.get(
            "data_quality"
        )
        or {}
    )

    # =====================================================
    # APPROVED FACT LEDGER
    # =====================================================

    product_facts = (
        performance_facts.get(
            "product"
        )
        or {}
    )

    category_facts = (
        performance_facts.get(
            "category"
        )
        or {}
    )

    brand_facts = (
        performance_facts.get(
            "brand"
        )
        or {}
    )

    def entity_value(
        source,
        key,
        field,
    ):

        return (
            source.get(key)
            or {}
        ).get(field)

    approved_facts = [
        {
            "fact_id": "SUMMARY_PRESENTED",
            "text": (
                f"Presented recommendations: "
                f"{summary.get('presented', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_PURCHASED",
            "text": (
                f"Purchased recommendations: "
                f"{summary.get('purchased', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_INTERESTED",
            "text": (
                f"Interested outcomes: "
                f"{summary.get('interested', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_FOLLOW_UP",
            "text": (
                f"Follow-up outcomes: "
                f"{summary.get('follow_up', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_REVENUE",
            "text": (
                f"Total recorded revenue: "
                f"{summary.get('total_revenue', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_CONVERSION",
            "text": (
                f"Recorded conversion rate: "
                f"{summary.get('conversion_rate', 0)} percent"
            ),
        },
        {
            "fact_id": "SUMMARY_ENGAGEMENT",
            "text": (
                f"Recorded engagement rate: "
                f"{summary.get('engagement_rate', 0)} percent"
            ),
        },
        {
            "fact_id": "DATA_QUALITY",
            "text": (
                f"Data quality status: "
                f"{summary.get('data_quality')}"
            ),
        },
        {
            "fact_id": "BEST_CONVERSION_PRODUCT",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    product_facts,
                    'best_conversion',
                    'product_code',
                )} "
                "as the best-conversion product."
            ),
        },
        {
            "fact_id": "BEST_REVENUE_PRODUCT",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    product_facts,
                    'best_revenue',
                    'product_code',
                )} "
                "as the best-revenue product."
            ),
        },
        {
            "fact_id": "BEST_ENGAGEMENT_PRODUCT",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    product_facts,
                    'best_engagement',
                    'product_code',
                )} "
                "as the best-engagement product."
            ),
        },
        {
            "fact_id": "BEST_CONVERSION_CATEGORY",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    category_facts,
                    'best_conversion',
                    'category_code',
                )} "
                "as the best-conversion category."
            ),
        },
        {
            "fact_id": "BEST_REVENUE_BRAND",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    brand_facts,
                    'best_revenue',
                    'brand_code',
                )} "
                "as the best-revenue brand."
            ),
        },
        {
            "fact_id": "BEST_CONVERSION_SALESPERSON",
            "text": (
                "Backend ranking identifies "
                f"{(
                    sales_team_facts.get(
                        'best_conversion'
                    )
                    or {}
                ).get('employee_code')} "
                "as the best-conversion salesperson."
            ),
        },
    ]

    approved_json = json.dumps(
        {
            "schema_version": "V3.0.8.1",
            "approved_facts": approved_facts,
            "data_quality": data_quality,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    # =====================================================
    # CONTROLLED LLM TASK
    # =====================================================

    prompt = (
        "APPROVED FACT LEDGER:\n\n"
        f"{approved_json}\n\n"

        "Write a short Persian executive summary.\n"
        "Use ONLY the exact facts in APPROVED FACT LEDGER.\n"
        "Do not combine numbers from different facts.\n"
        "Do not attach a number to an entity unless that exact "
        "association exists in one fact.\n"
        "Do not use words such as strong, weak, good, poor, "
        "improving, declining, successful, or leading unless "
        "such evaluation is explicitly present in a fact.\n"
        "When mentioning a ranking, say that the BACKEND RANKING "
        "identifies the entity.\n"
        "Do not calculate anything.\n"
        "Do not infer causes.\n"
        "Do not predict anything.\n"
        "The output MUST be Persian.\n"
        "Because data quality is LIMITED_DATA, explicitly state "
        "that observations are based on limited available data."
    )

    client = OllamaClient()

    ai_result = client.generate(
        prompt=prompt,
        system=(
            EXECUTIVE_INTELLIGENCE_SYSTEM_PROMPT
        ),
    )

    narrative = (
        ai_result.get(
            "response"
        )
        or ""
    ).strip()

    if not narrative:

        raise ValueError(
            "Executive narrative is empty."
        )

    # =====================================================
    # DETERMINISTIC AUTHORITATIVE NARRATIVE
    # =====================================================

    def build_authoritative_narrative():

        summary_data = (
            executive_context.get(
                "executive_summary"
            )
            or {}
        )

        product_data = (
            executive_context.get(
                "performance_facts"
            )
            or {}
        ).get(
            "product"
        ) or {}

        category_data = (
            executive_context.get(
                "performance_facts"
            )
            or {}
        ).get(
            "category"
        ) or {}

        brand_data = (
            executive_context.get(
                "performance_facts"
            )
            or {}
        ).get(
            "brand"
        ) or {}

        salesperson_data = (
            executive_context.get(
                "sales_team_facts"
            )
            or {}
        )

        best_conversion_product = (
            product_data.get(
                "best_conversion"
            )
            or {}
        )

        best_revenue_product = (
            product_data.get(
                "best_revenue"
            )
            or {}
        )

        best_engagement_product = (
            product_data.get(
                "best_engagement"
            )
            or {}
        )

        best_conversion_category = (
            category_data.get(
                "best_conversion"
            )
            or {}
        )

        best_revenue_brand = (
            brand_data.get(
                "best_revenue"
            )
            or {}
        )

        best_conversion_salesperson = (
            salesperson_data.get(
                "best_conversion"
            )
            or {}
        )

        return (
            f"در داده‌های ثبت‌شده، "
            f"{summary_data.get('presented', 0)} پیشنهاد ارائه شده و "
            f"{summary_data.get('purchased', 0)} خرید ثبت شده است. "

            f"درآمد ثبت‌شده برابر "
            f"{summary_data.get('total_revenue', 0)} "
            f"و نرخ تبدیل ثبت‌شده "
            f"{summary_data.get('conversion_rate', 0)} درصد است. "

            f"نرخ تعامل ثبت‌شده "
            f"{summary_data.get('engagement_rate', 0)} درصد است. "

            f"طبق رتبه‌بندی Backend، "
            f"{best_conversion_product.get('product_code')} "
            f"در رتبه نخست محصول از نظر نرخ تبدیل، "
            f"{best_revenue_product.get('product_code')} "
            f"در رتبه نخست محصول از نظر درآمد و "
            f"{best_engagement_product.get('product_code')} "
            f"در رتبه نخست محصول از نظر تعامل قرار دارد. "

            f"در سایر ابعاد رتبه‌بندی Backend، "
            f"{best_conversion_category.get('category_code')} "
            f"برای نرخ تبدیل دسته‌بندی، "
            f"{best_revenue_brand.get('brand_code')} "
            f"برای درآمد برند و "
            f"{best_conversion_salesperson.get('employee_code')} "
            f"برای نرخ تبدیل فروشنده در رتبه نخست ثبت شده‌اند. "

            f"کیفیت داده در این تحلیل "
            f"{summary_data.get('data_quality')} است؛ "
            f"بنابراین این گزارش صرفاً توصیف داده‌های موجود است "
            f"و نباید به‌عنوان نتیجه‌گیری علّی یا پیش‌بینی آینده "
            f"تفسیر شود."
        )

    authoritative_narrative = (
        build_authoritative_narrative()
    )

    llm_draft = (
        narrative
    )

    narrative = (
        authoritative_narrative
    )

    # =====================================================
    # FINAL CONTRACT
    # =====================================================

    return {
        "ready": True,

        "reason": (
            "EXECUTIVE_NARRATIVE_READY"
        ),

        "schema_version": (
            "V3.0.8.2"
        ),

        "source_context_schema_version": (
            executive_context.get(
                "schema_version"
            )
        ),

        "model": (
            ai_result.get(
                "model"
            )
        ),

        "done": (
            ai_result.get(
                "done",
                True,
            )
        ),

        "narrative": (
            narrative
        ),

        "llm_draft": (
            llm_draft
        ),

        "data_quality": (
            data_quality
        ),

        "semantic_validation": {
            "valid": True,

            "issues": [],

            "authoritative_output_is_deterministic": True,

            "llm_draft_exposed_as_authoritative": False,
        },

        "narrative_rules": {
            "source_is_v3_0_8_1": True,

            "backend_facts_authoritative": True,

            "authoritative_narrative_is_deterministic": True,

            "llm_used_for_language_experiment": True,

            "llm_output_is_authoritative": False,

            "llm_output_direct_to_ui": False,

            "kpi_calculation_performed": False,

            "ranking_calculation_performed": False,

            "trend_interpretation_performed": False,

            "causal_inference_used": False,

            "future_prediction_used": False,

            "ml_prediction_used": False,

            "ml_training_performed": False,
        },
    }

def generate_management_executive_narrative(
    executive_context,
):
    """
    Build V3.0.8.4 graceful executive narrative.

    The supplied V3.0.8.1 context is authoritative.

    The final management narrative is deterministic and
    generated from backend-approved facts.

    Ollama is optional and may only produce a non-authoritative
    language draft.

    If Ollama is unavailable, the authoritative management
    narrative remains available.
    """

    # =====================================================
    # INPUT VALIDATION
    # =====================================================

    if not executive_context:

        raise ValueError(
            "executive_context is required."
        )

    if (
        executive_context.get(
            "schema_version"
        )
        != "V3.0.8.1"
    ):

        raise ValueError(
            "V3.0.8.1 executive context is required."
        )

    if (
        executive_context.get(
            "ready"
        )
        is not True
    ):

        raise ValueError(
            "Executive intelligence context is not ready."
        )

    summary = (
        executive_context.get(
            "executive_summary"
        )
        or {}
    )

    performance_facts = (
        executive_context.get(
            "performance_facts"
        )
        or {}
    )

    sales_team_facts = (
        executive_context.get(
            "sales_team_facts"
        )
        or {}
    )

    data_quality = (
        executive_context.get(
            "data_quality"
        )
        or {}
    )

    # =====================================================
    # APPROVED FACT LEDGER
    # =====================================================

    product_facts = (
        performance_facts.get(
            "product"
        )
        or {}
    )

    category_facts = (
        performance_facts.get(
            "category"
        )
        or {}
    )

    brand_facts = (
        performance_facts.get(
            "brand"
        )
        or {}
    )

    def entity_value(
        source,
        key,
        field,
    ):

        return (
            source.get(key)
            or {}
        ).get(field)

    approved_facts = [
        {
            "fact_id": "SUMMARY_PRESENTED",
            "text": (
                f"Presented recommendations: "
                f"{summary.get('presented', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_PURCHASED",
            "text": (
                f"Purchased recommendations: "
                f"{summary.get('purchased', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_INTERESTED",
            "text": (
                f"Interested outcomes: "
                f"{summary.get('interested', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_FOLLOW_UP",
            "text": (
                f"Follow-up outcomes: "
                f"{summary.get('follow_up', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_REVENUE",
            "text": (
                f"Total recorded revenue: "
                f"{summary.get('total_revenue', 0)}"
            ),
        },
        {
            "fact_id": "SUMMARY_CONVERSION",
            "text": (
                f"Recorded conversion rate: "
                f"{summary.get('conversion_rate', 0)} percent"
            ),
        },
        {
            "fact_id": "SUMMARY_ENGAGEMENT",
            "text": (
                f"Recorded engagement rate: "
                f"{summary.get('engagement_rate', 0)} percent"
            ),
        },
        {
            "fact_id": "DATA_QUALITY",
            "text": (
                f"Data quality status: "
                f"{summary.get('data_quality')}"
            ),
        },
        {
            "fact_id": "BEST_CONVERSION_PRODUCT",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    product_facts,
                    'best_conversion',
                    'product_code',
                )} "
                "as the best-conversion product."
            ),
        },
        {
            "fact_id": "BEST_REVENUE_PRODUCT",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    product_facts,
                    'best_revenue',
                    'product_code',
                )} "
                "as the best-revenue product."
            ),
        },
        {
            "fact_id": "BEST_ENGAGEMENT_PRODUCT",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    product_facts,
                    'best_engagement',
                    'product_code',
                )} "
                "as the best-engagement product."
            ),
        },
        {
            "fact_id": "BEST_CONVERSION_CATEGORY",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    category_facts,
                    'best_conversion',
                    'category_code',
                )} "
                "as the best-conversion category."
            ),
        },
        {
            "fact_id": "BEST_REVENUE_BRAND",
            "text": (
                "Backend ranking identifies "
                f"{entity_value(
                    brand_facts,
                    'best_revenue',
                    'brand_code',
                )} "
                "as the best-revenue brand."
            ),
        },
        {
            "fact_id": "BEST_CONVERSION_SALESPERSON",
            "text": (
                "Backend ranking identifies "
                f"{(
                    sales_team_facts.get(
                        'best_conversion'
                    )
                    or {}
                ).get('employee_code')} "
                "as the best-conversion salesperson."
            ),
        },
    ]

    approved_json = json.dumps(
        {
            "schema_version": (
                "V3.0.8.1"
            ),

            "approved_facts": (
                approved_facts
            ),

            "data_quality": (
                data_quality
            ),
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    # =====================================================
    # DETERMINISTIC AUTHORITATIVE NARRATIVE
    # =====================================================

    def build_authoritative_narrative():

        product_data = (
            performance_facts.get(
                "product"
            )
            or {}
        )

        category_data = (
            performance_facts.get(
                "category"
            )
            or {}
        )

        brand_data = (
            performance_facts.get(
                "brand"
            )
            or {}
        )

        best_conversion_product = (
            product_data.get(
                "best_conversion"
            )
            or {}
        )

        best_revenue_product = (
            product_data.get(
                "best_revenue"
            )
            or {}
        )

        best_engagement_product = (
            product_data.get(
                "best_engagement"
            )
            or {}
        )

        best_conversion_category = (
            category_data.get(
                "best_conversion"
            )
            or {}
        )

        best_revenue_brand = (
            brand_data.get(
                "best_revenue"
            )
            or {}
        )

        best_conversion_salesperson = (
            sales_team_facts.get(
                "best_conversion"
            )
            or {}
        )

        return (
            f"در داده‌های ثبت‌شده، "
            f"{summary.get('presented', 0)} پیشنهاد ارائه شده و "
            f"{summary.get('purchased', 0)} خرید ثبت شده است. "

            f"درآمد ثبت‌شده برابر "
            f"{summary.get('total_revenue', 0)} "
            f"و نرخ تبدیل ثبت‌شده "
            f"{summary.get('conversion_rate', 0)} درصد است. "

            f"نرخ تعامل ثبت‌شده "
            f"{summary.get('engagement_rate', 0)} درصد است. "

            f"طبق رتبه‌بندی Backend، "
            f"{best_conversion_product.get('product_code')} "
            f"در رتبه نخست محصول از نظر نرخ تبدیل، "
            f"{best_revenue_product.get('product_code')} "
            f"در رتبه نخست محصول از نظر درآمد و "
            f"{best_engagement_product.get('product_code')} "
            f"در رتبه نخست محصول از نظر تعامل قرار دارد. "

            f"در سایر ابعاد رتبه‌بندی Backend، "
            f"{best_conversion_category.get('category_code')} "
            f"برای نرخ تبدیل دسته‌بندی، "
            f"{best_revenue_brand.get('brand_code')} "
            f"برای درآمد برند و "
            f"{best_conversion_salesperson.get('employee_code')} "
            f"برای نرخ تبدیل فروشنده در رتبه نخست ثبت شده‌اند. "

            f"کیفیت داده در این تحلیل "
            f"{summary.get('data_quality')} است؛ "
            f"بنابراین این گزارش صرفاً توصیف داده‌های موجود است "
            f"و نباید به‌عنوان نتیجه‌گیری علّی یا پیش‌بینی آینده "
            f"تفسیر شود."
        )

    authoritative_narrative = (
        build_authoritative_narrative()
    )

    # =====================================================
    # OPTIONAL OLLAMA LANGUAGE DRAFT
    # =====================================================

    prompt = (
        "APPROVED FACT LEDGER:\n\n"
        f"{approved_json}\n\n"

        "Write a short Persian executive summary.\n"
        "Use ONLY the exact facts in APPROVED FACT LEDGER.\n"
        "Do not combine numbers from different facts.\n"
        "Do not attach a number to an entity unless that exact "
        "association exists in one fact.\n"
        "Do not calculate anything.\n"
        "Do not create rankings.\n"
        "Do not infer causes.\n"
        "Do not predict anything.\n"
        "The output MUST be Persian.\n"
        "The output is a non-authoritative language draft."
    )

    llm_available = False
    llm_error = None
    llm_draft = ""
    llm_model = None
    llm_done = False

    try:

        client = OllamaClient()

        ai_result = client.generate(
            prompt=prompt,
            system=(
                EXECUTIVE_INTELLIGENCE_SYSTEM_PROMPT
            ),
        )

        llm_draft = (
            ai_result.get(
                "response"
            )
            or ""
        ).strip()

        llm_model = (
            ai_result.get(
                "model"
            )
        )

        llm_done = (
            ai_result.get(
                "done",
                True,
            )
        )

        llm_available = (
            bool(
                llm_draft
            )
        )

    except OllamaClientError as exc:

        llm_available = False

        llm_error = (
            str(exc)
        )

    except Exception as exc:

        # Ollama is optional for the management dashboard.
        # Any unexpected LLM-layer failure must not prevent
        # deterministic executive intelligence from working.

        llm_available = False

        llm_error = (
            str(exc)
        )

    # =====================================================
    # FINAL AUTHORITATIVE OUTPUT
    # =====================================================

    narrative = (
        authoritative_narrative
    )

    return {
        "ready": True,

        "reason": (
            "EXECUTIVE_NARRATIVE_READY"
        ),

        "schema_version": (
            "V3.0.8.4"
        ),

        "source_context_schema_version": (
            executive_context.get(
                "schema_version"
            )
        ),

        "narrative": (
            narrative
        ),

        "data_quality": (
            data_quality
        ),

        "llm_status": {
            "available": (
                llm_available
            ),

            "model": (
                llm_model
            ),

            "done": (
                llm_done
            ),

            "error": (
                llm_error
            ),
        },

        "semantic_validation": {
            "valid": True,

            "issues": [],

            "authoritative_output_is_deterministic": True,

            "llm_draft_exposed_as_authoritative": False,
        },

        "narrative_rules": {
            "source_is_v3_0_8_1": True,

            "backend_facts_authoritative": True,

            "authoritative_narrative_is_deterministic": True,

            "ollama_optional": True,

            "llm_used_for_language_experiment": True,

            "llm_output_is_authoritative": False,

            "llm_output_direct_to_ui": False,

            "llm_failure_blocks_narrative": False,

            "llm_failure_blocks_dashboard": False,

            "kpi_calculation_performed": False,

            "ranking_calculation_performed": False,

            "trend_interpretation_performed": False,

            "causal_inference_used": False,

            "future_prediction_used": False,

            "ml_prediction_used": False,

            "ml_training_performed": False,
        },
    }