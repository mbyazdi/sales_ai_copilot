"""Pure evaluator contract tests; runnable without Django setup or a database."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_DOWN, localcontext
import json
import os
import subprocess
import sys
import unittest

from .strategy_evaluator import (
    CommercialFacts, ProductFacts, PromotionFacts, SavedRecommendation, StrategyInputError,
    StrategyRules, StrategySnapshot, TargetFacts, evaluate_strategy,
)


DAY = date(2026, 10, 16)


def config(**kwargs):
    return {"schema_version": 1, "priority_rules": [], "target_weight": 0, "promotion_rules": [], **kwargs}


def priority(scope, identity, points):
    return {"scope_type": scope, "scope_id": identity, "points": points}


def target(**kwargs):
    return TargetFacts(**{
        "target_id": 1, "salesperson_id": 7, "scope_type": "PRODUCT", "scope_id": 3, "unit": "QUANTITY",
        "target_value": Decimal("100.00"), "actual_value": Decimal("0.00"),
        "period_start": DAY, "period_end": DAY, "is_active": True, **kwargs,
    })


def promotion(**kwargs):
    return PromotionFacts(**{
        "promotion_id": 1, "product_ids": (3,), "grade_ids": (1,), "start_date": DAY, "end_date": DAY,
        "minimum_quantity": 1, "maximum_quantity": None, "is_active": True, **kwargs,
    })


def snapshot(strategy=None, **kwargs):
    products = tuple(ProductFacts(i, f"P{i}", 10 + i, 20 + i, "HOME_APPLIANCE", True) for i in range(1, 5))
    recommendations = tuple(SavedRecommendation(
        100 + i, i, i, Decimal(score), f"دلیل ذخیره‌شده {i}",
        CommercialFacts("AVAILABLE", 10, "AVAILABLE", True, None),
        '{"promotion_score":20.0,"synthetic":true}',
    ) for i, score in enumerate(("40.0000", "90.0000", "70.0000", "60.0000"), 1))
    return StrategySnapshot(**{
        "customer_id": 1, "salesperson_id": 7, "customer_grade_id": 1, "evaluation_date": DAY,
        "recommendations": recommendations, "products": products, "brand_ids": (11, 12, 13, 14),
        "category_ids": (21, 22, 23, 24), "grade_ids": (1, 2), "targets": (), "promotions": (),
        "strategy": StrategyRules.from_config(strategy or config()), **kwargs,
    })


def rows(result):
    return {row.source.product_id: row for row in result.rows}


def codes(contribution):
    return {reason.code for reason in contribution.reasons}


class StrategyEvaluatorTests(unittest.TestCase):
    def test_neutral_parity_despite_score_disagreement(self):
        frozen = snapshot()
        result = evaluate_strategy(frozen)
        self.assertEqual(result.before_ids, (101, 102, 103, 104))
        self.assertEqual(result.before_ids, result.after_ids)
        self.assertEqual([row.base_priority for row in result.rows], list(map(Decimal, (30, 20, 10, 0))))
        self.assertEqual([row.source.base_score for row in result.rows], [row.base_score for row in frozen.recommendations])

    def test_input_position_not_saved_rank_value_controls_baseline(self):
        frozen = snapshot()
        recommendations = tuple(replace(row, saved_rank=rank) for row, rank in zip(frozen.recommendations, (9, 2, 2, 0)))
        result = evaluate_strategy(replace(frozen, recommendations=recommendations))
        self.assertEqual(result.after_ids, (101, 102, 103, 104))
        self.assertEqual([row.source.saved_rank for row in result.rows], [9, 2, 2, 0])

    def test_empty_shortlist_does_not_generate_candidates(self):
        result = evaluate_strategy(snapshot(recommendations=()))
        self.assertEqual((result.before_ids, result.after_ids, result.rows), ((), (), ()))

    def test_worked_priority_target_promotion_example_and_cap(self):
        strategy = config(priority_rules=[priority("CATEGORY", 23, 12), priority("BRAND", 13, 16),
                                          priority("PRODUCT", 3, 20), priority("PRODUCT", 2, 8)],
                          target_weight=5, promotion_rules=[{"promotion_id": 1, "points": 5}])
        result = evaluate_strategy(snapshot(strategy, targets=(target(),), promotions=(promotion(),)))
        self.assertEqual(result.after_ids, (103, 101, 102, 104))
        by_product = rows(result)
        self.assertEqual(by_product[3].overlay_adjustment, Decimal("30.00"))
        self.assertEqual(by_product[3].effective_priority, Decimal("40.00"))
        self.assertEqual([by_product[i].effective_priority for i in range(1, 5)], list(map(Decimal, (30, 28, 40, 0))))
        self.assertTrue(all(row.overlay_adjustment <= Decimal(30) for row in result.rows))

    def test_worked_tie_example_uses_original_position_not_score(self):
        strategy = config(priority_rules=[priority("PRODUCT", 3, 20), priority("PRODUCT", 4, 20)], target_weight=5,
                          promotion_rules=[{"promotion_id": 1, "points": 5}])
        result = evaluate_strategy(snapshot(strategy, targets=(target(scope_id=2, actual_value=Decimal("50")),
                                                              target(target_id=2, scope_id=4)),
                                            promotions=(promotion(product_ids=(4,)),)))
        self.assertEqual(result.after_ids, (101, 103, 104, 102))
        self.assertEqual(rows(result)[2].effective_priority, Decimal("22.50"))

    def test_specificity_and_product_zero_override(self):
        for product_points in (0, 7, 20):
            strategy = config(priority_rules=[priority("CATEGORY", 23, 20), priority("BRAND", 13, 19), priority("PRODUCT", 3, product_points)])
            contribution = rows(evaluate_strategy(snapshot(strategy)))[3].priority
            self.assertEqual(contribution.points, Decimal(product_points))
            self.assertEqual(contribution.source_id, 3)
            self.assertEqual(dict(contribution.reasons[0].data)["overridden_rules"], 2)
            if product_points == 0:
                self.assertIn("PRIORITY_EXPLICIT_ZERO", codes(contribution))

    def test_brand_zero_overrides_category_and_category_matches_only_exact_id(self):
        strategy = config(priority_rules=[priority("CATEGORY", 23, 20), priority("BRAND", 13, 0)])
        result = rows(evaluate_strategy(snapshot(strategy)))
        self.assertEqual(result[3].priority.points, Decimal(0))
        self.assertEqual(result[2].priority.points, Decimal(0))
        self.assertIn("NO_PRIORITY_RULE", codes(result[2].priority))

    def test_known_reference_outside_shortlist_is_never_added(self):
        frozen = snapshot(config(priority_rules=[priority("PRODUCT", 5, 20)]))
        frozen = replace(frozen, products=frozen.products + (ProductFacts(5, "EXTRA", 11, 21, "HOME_APPLIANCE", True),))
        result = evaluate_strategy(frozen)
        self.assertEqual(result.after_ids, (101, 102, 103, 104))
        self.assertEqual(len(result.rows), 4)

    def test_partial_target_and_rounding_half_up_tie(self):
        for actual, expected in (("50", "2.50"), ("99.90", "0.01"), ("99.91", "0.00")):
            with self.subTest(actual=actual):
                result = evaluate_strategy(snapshot(config(target_weight=5), targets=(target(actual_value=Decimal(actual)),)))
                self.assertEqual(rows(result)[3].target.points, Decimal(expected))

    def test_achieved_and_overachieved_targets_have_no_boost(self):
        for actual in ("100", "125"):
            contribution = rows(evaluate_strategy(snapshot(config(target_weight=5), targets=(target(actual_value=Decimal(actual)),))))[3].target
            self.assertEqual(contribution.points, Decimal(0))
            self.assertIn("TARGET_ACHIEVED", codes(contribution))

    def test_ineligible_target_states(self):
        cases = (
            (target(is_active=False), "TARGET_INACTIVE"),
            (target(period_start=DAY - timedelta(days=2), period_end=DAY - timedelta(days=1)), "TARGET_OUTSIDE_PERIOD"),
            (target(period_start=DAY + timedelta(days=1), period_end=DAY + timedelta(days=2)), "TARGET_OUTSIDE_PERIOD"),
            (target(unit="MSU"), "TARGET_UNIT_UNSUPPORTED"),
            (target(salesperson_id=8), "TARGET_OTHER_SALESPERSON"),
        )
        for fact, expected in cases:
            with self.subTest(expected=expected):
                contribution = rows(evaluate_strategy(snapshot(config(target_weight=5), targets=(fact,))))[3].target
                self.assertEqual(contribution.points, Decimal(0))
                self.assertIn(expected, codes(contribution))

    def test_target_overlap_uses_maximum_then_specificity_then_id(self):
        facts = (target(target_id=9), target(target_id=1, scope_type="CATEGORY", scope_id=23),
                 target(target_id=2, scope_type="PRODUCT_GROUP", scope_id="HOME_APPLIANCE"))
        contribution = rows(evaluate_strategy(snapshot(config(target_weight=5), targets=facts)))[3].target
        self.assertEqual((contribution.points, contribution.source_id), (Decimal(5), 9))
        self.assertIn("TARGET_OVERLAP_NOT_STACKED", codes(contribution))
        # Highest actual contribution wins even over a more-specific target.
        facts = (target(actual_value=Decimal(90)), target(target_id=2, scope_type="CATEGORY", scope_id=23))
        self.assertEqual(rows(evaluate_strategy(snapshot(config(target_weight=5), targets=facts)))[3].target.source_id, 2)
        facts = (target(target_id=7), target(target_id=3))
        self.assertEqual(rows(evaluate_strategy(snapshot(config(target_weight=5), targets=facts)))[3].target.source_id, 3)

    def test_target_zero_weight_is_not_a_measured_actual(self):
        contribution = rows(evaluate_strategy(snapshot(targets=(target(),))))[3].target
        self.assertIn("TARGET_INFLUENCE_DISABLED", codes(contribution))
        self.assertNotIn("actual_value", dict(contribution.reasons[0].data))

    def test_promotion_inclusive_dates_grade_and_quantity_one(self):
        strategy = config(promotion_rules=[{"promotion_id": 1, "points": 5}])
        result = rows(evaluate_strategy(snapshot(strategy, promotions=(promotion(maximum_quantity=1),))))
        self.assertEqual(result[3].promotion.points, Decimal(5))
        self.assertIn("PROMOTION_APPLIED", codes(result[3].promotion))
        self.assertEqual(result[2].promotion.points, Decimal(0))

    def test_ineligible_promotion_states(self):
        strategy = config(promotion_rules=[{"promotion_id": 1, "points": 5}])
        cases = (
            (promotion(is_active=False), "PROMOTION_INACTIVE"),
            (promotion(start_date=DAY - timedelta(days=2), end_date=DAY - timedelta(days=1)), "PROMOTION_OUTSIDE_PERIOD"),
            (promotion(start_date=DAY + timedelta(days=1), end_date=DAY + timedelta(days=2)), "PROMOTION_OUTSIDE_PERIOD"),
            (promotion(grade_ids=(2,)), "PROMOTION_GRADE_INELIGIBLE"),
            (promotion(minimum_quantity=2), "PROMOTION_QUANTITY_ONE_INELIGIBLE"),
            (promotion(minimum_quantity=0, maximum_quantity=0), "PROMOTION_QUANTITY_ONE_INELIGIBLE"),
        )
        for fact, expected in cases:
            with self.subTest(expected=expected):
                contribution = rows(evaluate_strategy(snapshot(strategy, promotions=(fact,))))[3].promotion
                self.assertEqual(contribution.points, Decimal(0))
                self.assertIn(expected, codes(contribution))

    def test_missing_grade_is_not_zero_and_unrestricted_promotion_remains_eligible(self):
        strategy = config(promotion_rules=[{"promotion_id": 1, "points": 5}])
        restricted = rows(evaluate_strategy(snapshot(strategy, customer_grade_id=None, promotions=(promotion(),))))[3]
        unrestricted = rows(evaluate_strategy(snapshot(strategy, customer_grade_id=None, promotions=(promotion(grade_ids=()),))))[3]
        self.assertEqual(restricted.promotion.points, Decimal(0))
        self.assertEqual(unrestricted.promotion.points, Decimal(5))

    def test_promotion_overlap_does_not_stack_and_lowest_id_breaks_tie(self):
        strategy = config(promotion_rules=[{"promotion_id": 2, "points": 5}, {"promotion_id": 1, "points": 5}])
        contribution = rows(evaluate_strategy(snapshot(strategy, promotions=(promotion(promotion_id=2), promotion()))))[3].promotion
        self.assertEqual((contribution.points, contribution.source_id), (Decimal(5), 1))
        self.assertIn("PROMOTION_OVERLAP_NOT_STACKED", codes(contribution))

    def test_zero_promotion_emphasis_is_not_presented_as_a_positive_boost(self):
        strategy = config(promotion_rules=[{"promotion_id": 1, "points": 0}])
        contribution = rows(evaluate_strategy(snapshot(strategy, promotions=(promotion(),))))[3].promotion
        self.assertEqual(contribution.points, Decimal(0))
        self.assertIn("PROMOTION_EMPHASIS_ZERO", codes(contribution))
        self.assertNotIn("PROMOTION_APPLIED", codes(contribution))

    def test_commercial_constraints_never_change_ranking_or_become_enabled(self):
        strategy = config(priority_rules=[priority("PRODUCT", 3, 20)])
        cases = (
            CommercialFacts("UNKNOWN", None, "AVAILABLE", False, "INVENTORY_UNKNOWN"),
            CommercialFacts("UNAVAILABLE", 0, "AVAILABLE", False, "OUT_OF_STOCK"),
            CommercialFacts("AVAILABLE", 10, "UNAVAILABLE", False, "PRICE_UNAVAILABLE", "MISSING_PRICE"),
            CommercialFacts("AVAILABLE", 10, "CONFIGURATION_ERROR", False, "PRICE_CONFIGURATION_ERROR", "FRACTIONAL_BASE_PRICE"),
            CommercialFacts("AVAILABLE", 10, "AVAILABLE", False, "VISIT_NOT_ACTIVE"),
        )
        for facts in cases:
            with self.subTest(reason=facts.non_addable_reason):
                frozen = snapshot(strategy)
                frozen = replace(frozen, recommendations=tuple(replace(row, commercial=facts) if row.product_id == 3 else row for row in frozen.recommendations))
                result = rows(evaluate_strategy(frozen))[3]
                self.assertEqual(result.effective_priority, Decimal(30))
                self.assertEqual(result.source.commercial, facts)
                self.assertFalse(result.source.commercial.can_add)

    def test_inactive_product_is_retained_as_disabled_audit_evidence(self):
        frozen = snapshot(config(priority_rules=[priority("PRODUCT", 3, 20)]))
        frozen = replace(frozen, products=tuple(replace(row, is_active=False) if row.product_id == 3 else row for row in frozen.products),
                         recommendations=tuple(replace(row, commercial=replace(row.commercial, can_add=False, non_addable_reason="INACTIVE_PRODUCT"))
                                               if row.product_id == 3 else row for row in frozen.recommendations))
        result = rows(evaluate_strategy(frozen))[3]
        self.assertFalse(result.product.is_active)
        self.assertFalse(result.source.commercial.can_add)
        self.assertEqual(result.source.recommendation_id, 103)

    def test_input_and_source_evidence_never_change_and_output_is_detached(self):
        frozen = snapshot()
        before = deepcopy(frozen)
        result = evaluate_strategy(frozen)
        self.assertEqual(frozen, before)
        self.assertEqual(result.rows[0].source.source_evidence_json, frozen.recommendations[0].source_evidence_json)
        # Saved promotion_score 20.0 is opaque and is not subtracted/recalculated.
        self.assertEqual(result.rows[0].source.base_score, Decimal("40.0000"))
        output = result.as_dict()
        output["rows"][0]["source"]["stored_reason"] = "changed response copy"
        self.assertEqual(frozen, before)
        with self.assertRaises(FrozenInstanceError):
            result.rows[0].source.saved_rank = 99

    def test_equal_snapshots_and_unordered_fact_sets_have_equal_evidence(self):
        strategy = config(target_weight=5, promotion_rules=[{"promotion_id": 2, "points": 4}, {"promotion_id": 1, "points": 5}],
                          priority_rules=[priority("PRODUCT", 3, 7), priority("BRAND", 14, 3)])
        frozen = snapshot(strategy, targets=(target(target_id=2), target()),
                          promotions=(promotion(promotion_id=2, product_ids=(4, 3), grade_ids=(2, 1)), promotion()))
        other = replace(frozen, products=frozen.products[::-1], brand_ids=frozen.brand_ids[::-1], category_ids=frozen.category_ids[::-1],
                        grade_ids=frozen.grade_ids[::-1], targets=frozen.targets[::-1], promotions=frozen.promotions[::-1],
                        strategy=replace(frozen.strategy, priority_rules=frozen.strategy.priority_rules[::-1], promotion_rules=frozen.strategy.promotion_rules[::-1]))
        first, second = evaluate_strategy(frozen), evaluate_strategy(other)
        self.assertEqual(first, second)
        self.assertEqual(first.result_digest, second.result_digest)
        self.assertEqual(first, evaluate_strategy(deepcopy(frozen)))

    def test_caller_decimal_context_does_not_affect_results_or_get_modified(self):
        frozen = snapshot(config(target_weight=5), targets=(target(actual_value=Decimal("99.90")),))
        expected = evaluate_strategy(frozen)
        with localcontext() as ambient:
            ambient.prec, ambient.rounding = 2, ROUND_DOWN
            self.assertEqual(evaluate_strategy(frozen), expected)
            self.assertEqual((ambient.prec, ambient.rounding), (2, ROUND_DOWN))

    def test_equivalent_decimal_encodings_have_identical_input_and_output_digests(self):
        frozen = snapshot(config(target_weight=5), targets=(target(actual_value=Decimal("50.00")),))
        equivalent = replace(frozen, targets=(target(target_value=Decimal("100"), actual_value=Decimal("50")),),
                             recommendations=tuple(replace(row, base_score=row.base_score.normalize()) for row in frozen.recommendations))
        first, second = evaluate_strategy(frozen), evaluate_strategy(equivalent)
        self.assertEqual(first.input_digest, second.input_digest)
        self.assertEqual(first.as_dict(), second.as_dict())
        self.assertEqual(first.result_digest, second.result_digest)
        zero = replace(frozen.recommendations[0], base_score=Decimal("-0.0000"))
        positive_zero = replace(zero, base_score=Decimal("0"))
        self.assertEqual(evaluate_strategy(replace(frozen, recommendations=(zero,))).result_digest,
                         evaluate_strategy(replace(frozen, recommendations=(positive_zero,))).result_digest)

    def test_required_data_missing_is_rejected_not_substituted_with_zero(self):
        for frozen in (snapshot(targets=None), snapshot(promotions=None), snapshot(targets=(target(actual_value=None),)),
                       replace(snapshot(), recommendations=(replace(snapshot().recommendations[0], base_score=None),))):
            with self.subTest(snapshot=frozen), self.assertRaises(StrategyInputError):
                evaluate_strategy(frozen)
        facts = rows(evaluate_strategy(snapshot()))[3].source
        self.assertIsNone(replace(facts, source_evidence_json=None).source_evidence_json)

    def test_invalid_types_bounds_and_duplicate_rules(self):
        invalid = (
            config(schema_version=True), config(target_weight=6), config(target_weight=True),
            config(priority_rules=[priority("PRODUCT", 3, -1)]), config(priority_rules=[priority("PRODUCT", 3, 21)]),
            config(priority_rules=[priority("PRODUCT", 3, 1.0)]), config(priority_rules=[priority("PRODUCT", 3, 1)] * 2),
            config(promotion_rules=[{"promotion_id": 1, "points": 6}]),
            config(promotion_rules=[{"promotion_id": 1, "points": 0}] * 2),
            config(unknown=1),
        )
        for value in invalid:
            with self.subTest(config=value), self.assertRaises(StrategyInputError):
                StrategyRules.from_config(value)
        with self.assertRaises(StrategyInputError):
            StrategyRules.from_config(config(), "UNKNOWN")

    def test_invalid_references_and_duplicate_fact_identities(self):
        frozen = snapshot()
        invalid = (
            snapshot(config(priority_rules=[priority("PRODUCT", 999, 1)])),
            snapshot(config(promotion_rules=[{"promotion_id": 999, "points": 1}])),
            snapshot(customer_grade_id=9), snapshot(brand_ids=(11, 11)),
            snapshot(targets=(target(scope_id=999),)), snapshot(promotions=(promotion(product_ids=(999,)),)),
            snapshot(promotions=(promotion(grade_ids=(999,)),)), snapshot(targets=(target(), target())),
            snapshot(promotions=(promotion(), promotion())),
            snapshot(recommendations=frozen.recommendations + (frozen.recommendations[0],)),
            snapshot(recommendations=frozen.recommendations + (replace(frozen.recommendations[0], recommendation_id=999),)),
            snapshot(products=frozen.products + (frozen.products[0],)),
        )
        for value in invalid:
            with self.subTest(snapshot=value), self.assertRaises(StrategyInputError):
                evaluate_strategy(value)

    def test_malformed_commercial_and_source_evidence_are_rejected(self):
        frozen = snapshot()
        invalid = (
            replace(frozen.recommendations[0], base_score=float("nan")),
            replace(frozen.recommendations[0], base_score=Decimal("Infinity")),
            replace(frozen.recommendations[0], saved_rank=True),
            replace(frozen.recommendations[0], source_evidence_json='{ "x": NaN }'),
            replace(frozen.recommendations[0], source_evidence_json="[]"),
            replace(frozen.recommendations[0], commercial=CommercialFacts("UNKNOWN", 0, "AVAILABLE", False, "UNKNOWN")),
            replace(frozen.recommendations[0], commercial=CommercialFacts("AVAILABLE", 0, "AVAILABLE", True, None)),
            replace(frozen.recommendations[0], commercial=CommercialFacts("UNAVAILABLE", 0, "AVAILABLE", True, None)),
            replace(frozen.recommendations[0], commercial=CommercialFacts("AVAILABLE", 10, "UNAVAILABLE", True, None)),
            replace(frozen.recommendations[0], commercial=CommercialFacts("AVAILABLE", 10, "AVAILABLE", False, None)),
        )
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(StrategyInputError):
                evaluate_strategy(replace(frozen, recommendations=(row,)))

    def test_malformed_target_promotion_periods_units_and_amounts(self):
        invalid = (
            snapshot(targets=(target(target_value=Decimal(0)),)),
            snapshot(targets=(target(actual_value=Decimal(-1)),)),
            snapshot(targets=(target(actual_value=Decimal("0.001")),)),
            snapshot(targets=(target(unit="CURRENCY"),)),
            snapshot(targets=(target(period_end=DAY - timedelta(days=1)),)),
            snapshot(promotions=(promotion(maximum_quantity=0),)),
            snapshot(promotions=(promotion(minimum_quantity=True),)),
            snapshot(promotions=(promotion(end_date=DAY - timedelta(days=1)),)),
            snapshot(evaluation_date=datetime(2026, 10, 16)),
            snapshot(recommendations=list(snapshot().recommendations)),
        )
        for value in invalid:
            with self.subTest(snapshot=value), self.assertRaises(StrategyInputError):
                evaluate_strategy(value)

    def test_persian_reasons_and_wire_decimal_values_are_stable(self):
        result = evaluate_strategy(snapshot(config(target_weight=5), targets=(target(actual_value=Decimal(50)),)))
        wire = result.as_dict()
        row = next(row for row in wire["rows"] if row["source"]["product_id"] == 3)
        self.assertEqual(row["target"]["points"], "2.50")
        self.assertEqual(row["source"]["base_score"], "70.0000")
        self.assertEqual(row["target"]["reasons"][0]["code"], "TARGET_APPLIED")
        self.assertEqual(row["target"]["reasons"][0]["data"]["actual_value"], "50")
        self.assertIn("فروش", row["target"]["reasons"][0]["text_fa"])
        self.assertEqual(json.loads(json.dumps(wire, ensure_ascii=False)), wire)

    def test_fresh_process_and_hash_seed_determinism_without_django_setup(self):
        code = (
            "import sys; from apps.management.tests_strategy_evaluator import snapshot; "
            "from apps.management.strategy_evaluator import evaluate_strategy; "
            "from django.conf import settings; "
            "assert not settings.configured and 'django.db' not in sys.modules; "
            "print(evaluate_strategy(snapshot()).result_digest)"
        )
        hashes = []
        for seed in ("1", "97"):
            env = {key: value for key, value in os.environ.items() if key != "DJANGO_SETTINGS_MODULE"}
            child = subprocess.run([sys.executable, "-B", "-c", code], env={**env, "PYTHONHASHSEED": seed},
                                   text=True, capture_output=True, timeout=20, check=True)
            hashes.append(child.stdout.strip())
        self.assertEqual(hashes, [evaluate_strategy(snapshot()).result_digest] * 2)


if __name__ == "__main__":
    unittest.main()
