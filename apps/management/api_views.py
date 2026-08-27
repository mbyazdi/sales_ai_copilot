from rest_framework.response import Response
from rest_framework.views import APIView

from apps.visits.services import (
    build_management_dashboard_contract,
    build_management_kpi_trend_contract,
    build_management_performance_sections_contract,
    build_management_sales_team_contract,
)


class ManagementDashboardAPIView(APIView):
    """
    V3.0.5 management dashboard API.

    The API exposes backend-generated management contracts.

    Important:
    - No KPI calculation is performed here.
    - No ranking calculation is performed here.
    - No ML prediction is performed here.
    - Ollama is not required.
    """

    def get(self, request):

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
        ])

        return Response({
            "ready": ready,

            "reason": (
                "MANAGEMENT_DASHBOARD_API_READY"
                if ready
                else "MANAGEMENT_DASHBOARD_API_NOT_READY"
            ),

            "schema_version": (
                "V3.0.5"
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

            "api_rules": {
                "backend_contracts_only": True,

                "kpi_calculation_performed": False,

                "ranking_calculation_performed": False,

                "frontend_business_calculation_required": False,

                "ml_prediction_used": False,

                "ml_training_performed": False,

                "causal_inference_used": False,

                "ollama_required": False,
            },
        })