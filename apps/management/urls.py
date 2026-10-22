from django.urls import path
from .strategy_ui_views import strategy_comparison, strategy_overview, strategy_control

from .views import (
    management_dashboard,
    recommendation_performance_dashboard,
)


urlpatterns = [
    path("strategy/", strategy_overview, name="strategy-overview"),
    path("strategy/control/", strategy_control, name="strategy-control"),
    path("strategy/comparisons/", strategy_comparison, name="strategy-comparison-create"),
    path("strategy/comparisons/<int:comparison_id>/", strategy_comparison, name="strategy-comparison"),

    path(
        "",
        management_dashboard,
        name="management-dashboard",
    ),

    path(
        "recommendations/performance/",
        recommendation_performance_dashboard,
        name="recommendation-performance-dashboard",
    ),

]
