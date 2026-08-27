from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.services import (
    generate_management_executive_narrative,
)

from apps.visits.services import (
    build_management_dashboard_contract,
    build_management_kpi_trend_contract,
    build_management_performance_sections_contract,
    build_management_sales_team_contract,
    build_management_executive_intelligence_context,
    build_management_decision_support_context,
)


class ManagementDashboardAPIView(APIView):
    """
    V3.0.8.3 management dashboard API.

    The API exposes backend-generated management contracts
    together with controlled executive intelligence.

    Important:
    - Existing management KPI values remain authoritative.
    - Existing backend rankings remain authoritative.
    - Executive facts come from V3.0.8.1.
    - Executive narrative comes from V3.0.8.2.
    - The authoritative narrative is deterministic.
    - Raw LLM draft is never exposed to the frontend.
    - No KPI calculation is performed here.
    - No ranking calculation is performed here.
    - No ML prediction is performed here.
    """

    def get(self, request):

        # =====================================================
        # EXISTING MANAGEMENT CONTRACTS
        # =====================================================

        dashboard = (
            build_management_dashboard_contract(
                customer=None
            )
        )

        kpi_trend = (
            build_management_kpi_trend_contract(
                customer=None
            )
        )

        performance = (
            build_management_performance_sections_contract(
                customer=None
            )
        )

        sales_team = (
            build_management_sales_team_contract(
                customer=None
            )
        )

        # =====================================================
        # EXECUTIVE INTELLIGENCE
        # =====================================================

        executive_context = (
            build_management_executive_intelligence_context(
                customer=None
            )
        )

        executive_narrative = (
            generate_management_executive_narrative(
                executive_context
            )
        )

        executive_intelligence = {
            "ready": (
                executive_context.get(
                    "ready",
                    False,
                )
                and executive_narrative.get(
                    "ready",
                    False,
                )
            ),

            "reason": (
                "EXECUTIVE_INTELLIGENCE_READY"
                if (
                    executive_context.get(
                        "ready",
                        False,
                    )
                    and executive_narrative.get(
                        "ready",
                        False,
                    )
                )
                else "EXECUTIVE_INTELLIGENCE_NOT_READY"
            ),

            "schema_version": (
                "V3.0.8.4"
            ),

            "source_versions": {
                "context": (
                    executive_context.get(
                        "schema_version"
                    )
                ),

                "narrative": (
                    executive_narrative.get(
                        "schema_version"
                    )
                ),
            },

            "narrative": (
                executive_narrative.get(
                    "narrative"
                )
                or ""
            ),

            "data_quality": (
                executive_narrative.get(
                    "data_quality"
                )
                or {}
            ),

            "semantic_validation": (
                executive_narrative.get(
                    "semantic_validation"
                )
                or {}
            ),

            "llm_status": (
                executive_narrative.get(
                    "llm_status"
                )
                or {}
            ),

            "rules": {
                "source_context_is_authoritative": True,

                "backend_facts_authoritative": True,

                "authoritative_narrative_is_deterministic": True,

                "llm_draft_exposed_to_frontend": False,

                "kpi_calculation_performed": False,

                "ranking_calculation_performed": False,

                "trend_interpretation_performed": False,

                "causal_inference_used": False,

                "future_prediction_used": False,

                "ml_prediction_used": False,

                "ml_training_performed": False,

                "ollama_optional": True,

                "llm_failure_blocks_dashboard": False,
            },
        }

        # =====================================================
        # MANAGEMENT DECISION SUPPORT
        # =====================================================

        decision_support = (
            build_management_decision_support_context(
                customer=None
            )
        )

        # =====================================================
        # API READINESS
        # =====================================================

        ready = all([
            dashboard.get(
                "ready",
                False,
            ),
            kpi_trend.get(
                "ready",
                False,
            ),
            performance.get(
                "ready",
                False,
            ),
            sales_team.get(
                "ready",
                False,
            ),
            executive_intelligence.get(
                "ready",
                False,
            ),
            decision_support.get(
                "ready",
                False,
            ),
        ])

        # =====================================================
        # FINAL API CONTRACT
        # =====================================================

        return Response({
            "ready": ready,

            "reason": (
                "MANAGEMENT_DASHBOARD_API_READY"
                if ready
                else "MANAGEMENT_DASHBOARD_API_NOT_READY"
            ),

            "schema_version": (
                "V3.0.9.2"
            ),

            "source_versions": {
                "dashboard": (
                    dashboard.get(
                        "schema_version"
                    )
                ),

                "kpi_trend": (
                    kpi_trend.get(
                        "schema_version"
                    )
                ),

                "performance": (
                    performance.get(
                        "schema_version"
                    )
                ),

                "sales_team": (
                    sales_team.get(
                        "schema_version"
                    )
                ),

                "executive_context": (
                    executive_context.get(
                        "schema_version"
                    )
                ),

                "executive_narrative": (
                    executive_narrative.get(
                        "schema_version"
                    )
                ),

                "decision_support": (
                    decision_support.get(
                        "schema_version"
                    )
                ),

            },

            "scope": (
                dashboard.get(
                    "scope"
                )
                or {}
            ),

            "dashboard": (
                dashboard
            ),

            "kpi_trend": (
                kpi_trend
            ),

            "performance": (
                performance
            ),

            "sales_team": (
                sales_team
            ),

            "executive_intelligence": (
                executive_intelligence
            ),

            "decision_support": (
                decision_support
            ),

            "api_rules": {
                "backend_contracts_only": True,

                "kpi_calculation_performed": False,

                "ranking_calculation_performed": False,

                "frontend_business_calculation_required": False,

                "executive_facts_backend_controlled": True,

                "executive_narrative_deterministic": True,

                "llm_draft_exposed_to_frontend": False,

                "ml_prediction_used": False,

                "ml_training_performed": False,

                "causal_inference_used": False,

                "ollama_required_for_existing_dashboard": False,

                "ollama_optional": True,

                "ollama_failure_blocks_dashboard": False,

                "decision_support_backend_controlled": True,

                "attention_rules_deterministic": True,

                "decision_support_prediction_used": False,

            },
        })