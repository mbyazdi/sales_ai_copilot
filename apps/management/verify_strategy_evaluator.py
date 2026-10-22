"""M-C2 focused selection, using the existing identity-guarded disposable runner.

PostgreSQL: python -B -m apps.management.verify_strategy_evaluator
SQLite:     python -B -m apps.management.verify_strategy_evaluator --sqlite
"""
from .verify_strategy_foundation import main


if __name__ == "__main__":
    main(test_labels=[
        "apps.management.tests_strategy_evaluator",
        "apps.management.tests_strategy_evaluator_db",
        "apps.management.tests_strategy.StrategySerializationTests",
        "apps.recommendations.tests.RecommendationBaselineTests",
    ])
