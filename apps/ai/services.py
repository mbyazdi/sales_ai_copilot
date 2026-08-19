from .ollama_client import (
    OllamaClient,
)

from .prompt_builder import (
    build_sales_copilot_prompt,
)

from .prompts import (
    SALES_COPILOT_SYSTEM_PROMPT,
)

def generate_sales_copilot_response(
    sales_ai_context,
    user_message=None,
):

    prompt = build_sales_copilot_prompt(
        sales_ai_context
    )

    if user_message:

        prompt += (
            "\n\n"
            "SALESPERSON QUESTION:\n"
            f"{user_message.strip()}\n\n"
            "Answer only using the provided context."
        )

    client = OllamaClient()

    return client.generate(
        prompt=prompt,
        system=(
            SALES_COPILOT_SYSTEM_PROMPT
        ),
    )

def generate_sales_copilot_response(
    sales_ai_context,
    user_message=None,
):
    """
    Generate a controlled Sales Copilot response.

    Recommendation decisions are already made
    by the Rule-Based Recommendation Engine.
    """

    prompt = build_sales_copilot_prompt(
        sales_ai_context
    )

    if user_message:

        prompt += (
            "\n\n"
            "SALESPERSON QUESTION:\n"
            f"{user_message.strip()}\n\n"
            "Answer only using the provided context."
        )

    client = OllamaClient()

    result = client.generate(
        prompt=prompt,
    )

    return result