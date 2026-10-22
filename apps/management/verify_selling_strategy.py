"""M-D2 integration/strategy/commercial selection, disposable databases only."""
from .verify_strategy_foundation import main


if __name__ == "__main__":
    main(test_labels=[
        "apps.management.tests_selling_strategy",
        "apps.management.tests_strategy_services", "apps.management.tests_strategy_snapshots",
        "apps.management.tests_strategy_evaluator", "apps.management.tests_strategy_evaluator_db",
        "apps.management.tests_strategy.StrategyCommandTests", "apps.management.tests_strategy.StrategyIntegrityTests",
        "apps.management.tests_strategy_api.StrategyAPITests.test_all_first_use_gets_and_heads_are_zero_write",
        "apps.management.tests_strategy_api.StrategyAPITests.test_complete_http_draft_preview_publish_flow_preserves_all_business_rows",
        "apps.products.tests_pricing", "apps.products.tests_quotes",
        "apps.products.tests_catalog.CatalogBackendTests",
        "apps.customers.tests_salesperson_journey.SalespersonJourneyPresentationTests",
        "apps.sales_requests.tests_basket.BasketAPITests",
        "apps.recommendations.tests_feedback.FeedbackAPITests",
        "apps.sales_requests.tests_submission.SubmissionAPITests.test_success_persists_complete_snapshots_and_only_submission_effects",
        "apps.sales_requests.tests_submission.SubmissionAPITests.test_identical_replay_returns_frozen_result_without_writes_or_repricing",
        "apps.sales_requests.tests_submission.SubmissionAPITests.test_submitted_request_lines_and_basket_are_immutable",
        "apps.sales_requests.tests_submission.SubmissionAPITests.test_price_change_requires_explicit_basket_requote_then_new_review",
        "apps.visits.tests_completion.VisitCompletionAPITests.test_retained_draft_and_lines_stay_unchanged_and_become_read_only",
        "apps.visits.tests_completion.VisitCompletionAPITests.test_submitted_request_gets_one_separate_ack_without_changing_any_snapshots",
        "apps.visits.tests_completion.VisitCompletionAPITests.test_same_command_replays_frozen_result_without_any_new_write",
        "apps.visits.tests_completion.VisitCompletionAPITests.test_read_get_head_before_and_after_completion_are_zero_write",
    ], runtime_tests=True, publication_tests=True, api_tests=True, journey_tests=True)
