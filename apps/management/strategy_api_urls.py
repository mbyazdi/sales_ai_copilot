from django.urls import path

from .strategy_api_views import (
    StrategyCommandView, StrategyComparisonsView, StrategyComparisonView, StrategyDraftView,
    StrategyOptionsView, StrategyOverviewView, StrategyPublishView, StrategyRollbackView, StrategyVersionsView,
)


app_name = "strategy"
urlpatterns = [
    path("overview/", StrategyOverviewView.as_view(), name="overview"),
    path("options/", StrategyOptionsView.as_view(), name="options"),
    path("versions/", StrategyVersionsView.as_view(), name="versions"),
    path("draft/", StrategyDraftView.as_view(), name="draft"),
    path("comparisons/", StrategyComparisonsView.as_view(), name="comparisons"),
    path("comparisons/<int:comparison_id>/", StrategyComparisonView.as_view(), name="comparison"),
    path("publish/", StrategyPublishView.as_view(), name="publish"),
    path("rollback/", StrategyRollbackView.as_view(), name="rollback"),
    path("commands/<str:command_uuid>/", StrategyCommandView.as_view(), name="command"),
]
