"""M-C4 focused suites; guarded disposable PostgreSQL or in-memory SQLite only."""
from .verify_strategy_foundation import main


if __name__ == "__main__":
    main(test_labels=[
        "apps.management.tests_strategy_services",
        "apps.management.tests_strategy_snapshots",
        "apps.management.tests_strategy.StrategyCommandTests",
        "apps.management.tests_strategy.StrategyIntegrityTests",
        "apps.management.tests_strategy.StrategySerializationTests",
        "apps.management.tests_strategy.StrategyConcurrencyTests",
        "apps.management.tests_strategy_evaluator",
        "apps.management.tests_strategy_evaluator_db",
        "apps.recommendations.tests.RecommendationBaselineTests",
    ], runtime_tests=True, publication_tests=True)
