from decimal import Decimal

from django.db.models import Avg, Count, Max
from django.utils import timezone

from apps.products.models import Product
from apps.sales.models import SaleItem
from apps.promotions.models import PromotionProduct

from apps.recommendations.models import (
    CustomerRecommendation,
    ProductAssociation,
    RecommendationConfig,
)


class RecommendationEngine:
    """
    Rule-based recommendation engine.

    Responsibilities:
        1. Candidate generation
        2. Product scoring
        3. Recommendation type determination
        4. Saving recommendations

    Important:
        Ollama does NOT make recommendation decisions.

    The scoring parameters are centralized here so that
    they can later be moved to an Expert/Admin configuration
    without changing the recommendation logic.
    """

    # =====================================================
    # ENGINE CONFIGURATION
    # =====================================================

    # -----------------------------------------------------
    # General
    # -----------------------------------------------------

    MIN_RECOMMENDATION_SCORE = Decimal("20")
    MAX_RECOMMENDATIONS = 5

    MAX_FINAL_SCORE = Decimal("100")

    def _get_config(self):
        """
        Return active recommendation configuration.

        If no active configuration exists,
        use the engine's built-in defaults.
        """

        return (
            RecommendationConfig.objects
            .filter(
                is_active=True,
            )
            .order_by(
                "-updated_at",
                "-id",
            )
            .first()
        )
    # -----------------------------------------------------
    # Category affinity
    #
    # Default values.
    # Later these can be moved to an Expert configuration.
    # -----------------------------------------------------

    CATEGORY_SCORES = {
        1: Decimal("30"),
        2: Decimal("25"),
        3: Decimal("20"),
        4: Decimal("15"),
        5: Decimal("10"),
        6: Decimal("10"),
        7: Decimal("8"),
        8: Decimal("8"),
        9: Decimal("5"),
        10: Decimal("5"),
        11: Decimal("5"),
    }

    # -----------------------------------------------------
    # Customer Grade
    # -----------------------------------------------------

    GRADE_SCORES = {
        "A": Decimal("15"),
        "B": Decimal("10"),
        "C": Decimal("5"),
    }

    # -----------------------------------------------------
    # Promotion
    # -----------------------------------------------------

    PROMOTION_SCORE = Decimal("20")

    # -----------------------------------------------------
    # Association
    # -----------------------------------------------------

    ASSOCIATION_MAX_SCORE = Decimal("15")

    ASSOCIATION_LIFT_MAX_SCORE = Decimal("10")

    ASSOCIATION_EVIDENCE_SCORES = {
        1: Decimal("1"),
        2: Decimal("3"),
        3: Decimal("5"),
    }

    # -----------------------------------------------------
    # Repurchase
    # -----------------------------------------------------

    REPURCHASE_NO_CYCLE_SCORE = Decimal("20")

    REPURCHASE_OVERDUE_30_SCORE = Decimal("35")

    REPURCHASE_OVERDUE_90_SCORE = Decimal("40")

    REPURCHASE_OVERDUE_HIGH_SCORE = Decimal("45")

    # -----------------------------------------------------
    # Durable product
    # -----------------------------------------------------

    DURABLE_PREVIOUS_PURCHASE_SCORE = Decimal("5")

    # -----------------------------------------------------
    # Up-sell
    # -----------------------------------------------------

    UPSELL_10_PERCENT_SCORE = Decimal("10")

    UPSELL_25_PERCENT_SCORE = Decimal("20")

    UPSELL_50_PERCENT_SCORE = Decimal("30")

    UPSELL_HIGH_SCORE = Decimal("35")

    # -----------------------------------------------------
    # Similar product
    # -----------------------------------------------------

    SIMILAR_PRODUCT_SCORE = Decimal("15")

    # =====================================================
    # INITIALIZATION
    # =====================================================

    def __init__(self, customer):

        self.customer = customer

        self.config = self._get_config()

        self.customer_360 = getattr(
            customer,
            "customer_360",
            None,
        )

        # =================================================
        # Customer purchase cache
        # =================================================

        self.last_purchase_dates = {}

        last_purchases = (
            SaleItem.objects
            .filter(
                sale__customer=self.customer,
            )
            .select_related(
                "sale",
            )
            .order_by(
                "product_id",
                "-sale__sale_date",
            )
        )

        for item in last_purchases:

            if item.product_id not in self.last_purchase_dates:

                self.last_purchase_dates[
                    item.product_id
                ] = item.sale.sale_date

        # Set of products previously purchased
        self.purchased_product_ids = set(
            self.last_purchase_dates.keys()
        )

        # =================================================
        # Association cache
        # =================================================

        self.association_lifts = {}

        if self.purchased_product_ids:

            associations = (
                ProductAssociation.objects
                .filter(
                    product_id__in=self.purchased_product_ids,
                    is_active=True,
                    lift__gt=Decimal("1"),
                )
                .values(
                    "product_id",
                    "associated_product_id",
                    "lift",
                )
            )

            for association in associations:

                key = (
                    association["product_id"],
                    association["associated_product_id"],
                )

                current_lift = self.association_lifts.get(
                    key
                )

                if (
                    current_lift is None
                    or association["lift"] > current_lift
                ):

                    self.association_lifts[key] = (
                        association["lift"]
                    )

    # =====================================================
    # PUBLIC API
    # =====================================================

    def generate(self):

        if not self.customer_360:
            return []

        candidates = self._get_candidates()

        recommendations = []

        min_score = (
            self.config.min_recommendation_score
            if self.config
            else self.MIN_RECOMMENDATION_SCORE
        )

        max_recommendations = (
            self.config.max_recommendations
            if self.config
            else self.MAX_RECOMMENDATIONS
        )

        for product in candidates:

            result = self._score_product(product)

            if result["score"] >= min_score:
                recommendations.append(result)

        recommendations.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        recommendations = recommendations[
            :max_recommendations
        ]

        return self._save_recommendations(
            recommendations
        )

    # =====================================================
    # CANDIDATE GENERATION
    # =====================================================

    def _get_candidates(self):

        products = (
            Product.objects
            .filter(
                is_active=True,
            )
            .select_related(
                "brand",
                "category",
            )
        )

        candidates = []

        for product in products:

            previously_purchased = (
                product.id
                in self.purchased_product_ids
            )

            # ---------------------------------------------
            # Never purchased
            # ---------------------------------------------

            if not previously_purchased:

                candidates.append(product)

                continue

            # ---------------------------------------------
            # Previously purchased
            # Only if repurchase is due
            # ---------------------------------------------

            if self._is_repurchase_due(product):

                candidates.append(product)

        return candidates

    # =====================================================
    # ASSOCIATION CANDIDATES
    # =====================================================

    def _association_candidates(self):

        if not self.purchased_product_ids:

            return Product.objects.none()

        associated_product_ids = (
            ProductAssociation.objects
            .filter(
                product_id__in=self.purchased_product_ids,
                is_active=True,
                lift__gt=Decimal("1"),
            )
            .exclude(
                associated_product_id__in=(
                    self.purchased_product_ids
                ),
            )
            .values_list(
                "associated_product_id",
                flat=True,
            )
            .distinct()
        )

        return (
            Product.objects
            .filter(
                id__in=associated_product_ids,
                is_active=True,
            )
            .select_related(
                "brand",
                "category",
            )
        )

    # =====================================================
    # ASSOCIATION SCORE
    # =====================================================

    def _association_score(self, product):

        associations = (
            ProductAssociation.objects
            .filter(
                product_id__in=self.last_purchase_dates.keys(),
                associated_product=product,
                is_active=True,
                lift__gt=Decimal("1"),
            )
            .order_by("-lift")
        )

        if not associations.exists():
            return Decimal("0")

        # -------------------------------------------------
        # Strongest association
        # -------------------------------------------------

        best_lift = associations.first().lift

        # -------------------------------------------------
        # Lift score
        # -------------------------------------------------

        lift_score = (
            best_lift - Decimal("1")
        ) * Decimal("100")

        if self.config:
            lift_max_score = (
                self.config.association_lift_max_score
            )
        else:
            lift_max_score = (
                self.ASSOCIATION_LIFT_MAX_SCORE
            )

        lift_score = min(
            lift_score,
            lift_max_score,
        )

        # -------------------------------------------------
        # Number of supporting purchased products
        # -------------------------------------------------

        supporting_count = associations.count()

        if self.config:

            evidence_scores = {
                1: self.config.association_evidence_1_score,
                2: self.config.association_evidence_2_score,
                3: self.config.association_evidence_3_score,
            }

            if supporting_count >= 3:
                evidence_score = (
                    self.config.association_evidence_3_score
                )
            else:
                evidence_score = evidence_scores.get(
                    supporting_count,
                    Decimal("0"),
                )

            association_max_score = (
                self.config.association_max_score
            )

        else:

            if supporting_count >= 3:
                evidence_score = Decimal("5")

            elif supporting_count == 2:
                evidence_score = Decimal("3")

            elif supporting_count == 1:
                evidence_score = Decimal("1")

            else:
                evidence_score = Decimal("0")

            association_max_score = (
                self.ASSOCIATION_MAX_SCORE
            )

        # -------------------------------------------------
        # Final association score
        # -------------------------------------------------

        return min(
            lift_score + evidence_score,
            association_max_score,
        )
    # =====================================================
    # PRODUCT SCORING
    # =====================================================

    def _score_product(self, product):

        score = Decimal("0")

        reasons = []

        # -------------------------------------------------
        # 1. Category / Group Affinity
        # -------------------------------------------------

        group_score = self._group_affinity(
            product
        )

        score += group_score

        if group_score > 0:

            reasons.append(
                "دسته محصول با الگوی خرید مشتری "
                "همخوانی دارد."
            )

        # -------------------------------------------------
        # 2. Previous Purchase / Repurchase
        # -------------------------------------------------

        purchase_score = (
            self._previous_purchase(
                product
            )
        )

        score += purchase_score

        if purchase_score > 0:

            reasons.append(
                "زمان خرید مجدد این محصول فرا رسیده است."
            )

        # -------------------------------------------------
        # 3. Product Association
        # -------------------------------------------------

        association_score = (
            self._association_score(
                product
            )
        )

        score += association_score

        if association_score > 0:

            reasons.append(
                "این محصول بر اساس خریدهای قبلی "
                "مشتری با محصولات خریداری‌شده مرتبط است."
            )

        # -------------------------------------------------
        # 4. Up-Sell
        # -------------------------------------------------

        upsell_score = (
            self._upsell_score(
                product
            )
        )

        score += upsell_score

        if upsell_score > 0:

            reasons.append(
                "این محصول نسبت به سطح خرید قبلی مشتری "
                "گزینه گران‌تری محسوب می‌شود."
            )

        # -------------------------------------------------
        # 5. Customer Grade
        # -------------------------------------------------

        grade_score = (
            self._grade_score(
                product
            )
        )

        score += grade_score

        if grade_score > 0:

            reasons.append(
                "محصول برای گرید مشتری مناسب است."
            )

        # -------------------------------------------------
        # 6. Promotion
        # -------------------------------------------------

        promotion_score = (
            self._promotion_score(
                product
            )
        )

        score += promotion_score

        if promotion_score > 0:

            reasons.append(
                "برای این محصول Promotion فعال وجود دارد."
            )

        # -------------------------------------------------
        # 7. Similar Product
        # -------------------------------------------------

        similar_score = (
            self._similar_product_score(
                product
            )
        )

        score += similar_score

        if similar_score > 0:

            reasons.append(
                "این محصول از نظر ویژگی‌های محصولی "
                "به محصولات خریداری‌شده مشتری شباهت دارد."
            )

        # -------------------------------------------------
        # Final Score
        # -------------------------------------------------

        score = min(
            score,
            self.MAX_FINAL_SCORE,
        )

        recommendation_type = (
            self._determine_type(
                product
            )
        )

        return {
            "product": product,

            "score": score,

            "reason": " ".join(
                reasons
            ),

            "recommendation_type": (
                recommendation_type
            ),
        }

    # =====================================================
    # RECOMMENDATION TYPE
    # =====================================================

    def _determine_type(self, product):

        # -------------------------------------------------
        # 1. Repeat Purchase
        # -------------------------------------------------

        previously_purchased = (
            product.id
            in self.last_purchase_dates
        )

        if previously_purchased:

            if self._is_repurchase_due(
                product
            ):

                return (
                    CustomerRecommendation
                    .RecommendationType
                    .REPEAT_PURCHASE
                )

        # -------------------------------------------------
        # 2. Up Sell
        # -------------------------------------------------

        upsell_score = (
            self._upsell_score(
                product
            )
        )

        if upsell_score > 0:

            return (
                CustomerRecommendation
                .RecommendationType
                .UP_SELL
            )

        # -------------------------------------------------
        # 3. Association / Cross Sell
        # -------------------------------------------------

        association_score = (
            self._association_score(
                product
            )
        )

        if association_score > 0:

            return (
                CustomerRecommendation
                .RecommendationType
                .CROSS_SELL
            )

        # -------------------------------------------------
        # 4. Similar Product
        # -------------------------------------------------

        similar_score = (
            self._similar_product_score(
                product
            )
        )

        if similar_score > 0:

            return (
                CustomerRecommendation
                .RecommendationType
                .SIMILAR_PRODUCT
            )

        # -------------------------------------------------
        # 5. Category
        # -------------------------------------------------

        category_rank = (
            self._category_rank(
                product
            )
        )

        if category_rank is not None:

            if category_rank <= 8:

                return (
                    CustomerRecommendation
                    .RecommendationType
                    .CATEGORY
                )

        # -------------------------------------------------
        # 6. Default Cross Sell
        # -------------------------------------------------

        return (
            CustomerRecommendation
            .RecommendationType
            .CROSS_SELL
        )

    # =====================================================
    # REPURCHASE DUE
    # =====================================================

    def _is_repurchase_due(self, product):

        last_purchase_date = (
            self.last_purchase_dates.get(
                product.id
            )
        )

        if not last_purchase_date:

            return False

        if not product.is_consumable:

            return False

        if not product.repurchase_cycle_days:

            return False

        today = timezone.localdate()

        days_since_purchase = (
            today - last_purchase_date
        ).days

        return (
            days_since_purchase
            >= product.repurchase_cycle_days
        )

    # =====================================================
    # PRODUCT GROUP AFFINITY
    # =====================================================

    def _group_affinity(self, product):

        category_rank = self._category_rank(product)

        if category_rank is None:
            return Decimal("0")

        if self.config:

            category_scores = {
                1: self.config.category_rank_1_score,
                2: self.config.category_rank_2_score,
                3: self.config.category_rank_3_score,
                4: self.config.category_rank_4_score,
                5: self.config.category_rank_5_score,
                6: self.config.category_rank_6_score,
                7: self.config.category_rank_7_score,
                8: self.config.category_rank_8_score,
                9: self.config.category_rank_9_score,
                10: self.config.category_rank_10_score,
                11: self.config.category_rank_11_score,
            }

            return category_scores.get(
                category_rank,
                Decimal("0"),
            )

        # Fallback
        return self.CATEGORY_SCORES.get(
            category_rank,
            Decimal("0"),
        )

    # =====================================================
    # PREVIOUS PURCHASE
    # =====================================================

    def _previous_purchase(self, product):

        last_purchase_date = (
            self.last_purchase_dates.get(
                product.id
            )
        )

        if not last_purchase_date:
            return Decimal("0")

        if product.is_consumable:

            if not product.repurchase_cycle_days:

                if self.config:
                    return (
                        self.config.repurchase_no_cycle_score
                    )

                return (
                    self.REPURCHASE_NO_CYCLE_SCORE
                )

            today = timezone.localdate()

            days_since_purchase = (
                today - last_purchase_date
            ).days

            cycle = product.repurchase_cycle_days

            if days_since_purchase >= cycle:

                overdue_days = (
                    days_since_purchase - cycle
                )

                if overdue_days <= 30:

                    if self.config:
                        return (
                            self.config.repurchase_overdue_30_score
                        )

                    return (
                        self.REPURCHASE_OVERDUE_30_SCORE
                    )

                if overdue_days <= 90:

                    if self.config:
                        return (
                            self.config.repurchase_overdue_90_score
                        )

                    return (
                        self.REPURCHASE_OVERDUE_90_SCORE
                    )

                if self.config:
                    return (
                        self.config.repurchase_overdue_high_score
                    )

                return (
                    self.REPURCHASE_OVERDUE_HIGH_SCORE
                )

            return Decimal("0")

        if product.is_durable:

            if self.config:
                return (
                    self.config.durable_previous_purchase_score
                )

            return (
                self.DURABLE_PREVIOUS_PURCHASE_SCORE
            )

        return Decimal("0")

        # -------------------------------------------------
        # Durable
        # -------------------------------------------------

        if product.is_durable:

            return (
                self.DURABLE_PREVIOUS_PURCHASE_SCORE
            )

        return Decimal("0")

    # =====================================================
    # CUSTOMER GRADE
    # =====================================================

    def _grade_score(self, product):

        grade = self.customer.grade

        if not grade:
            return Decimal("0")

        if self.config:

            grade_scores = {
                "A": self.config.grade_a_score,
                "B": self.config.grade_b_score,
                "C": self.config.grade_c_score,
            }

            return grade_scores.get(
                grade.code,
                Decimal("0"),
            )

        # Fallback
        return self.GRADE_SCORES.get(
            grade.code,
            Decimal("0"),
        )

    # =====================================================
    # PROMOTION
    # =====================================================

    def _promotion_score(self, product):

        active_promotions = (
            PromotionProduct.objects
            .filter(
                product=product,
                promotion__is_active=True,
            )
            .exists()
        )

        if not active_promotions:
            return Decimal("0")

        if self.config:
            return self.config.promotion_score

        # Fallback
        return self.PROMOTION_SCORE

    # =====================================================
    # UP-SELL
    # =====================================================

    def _upsell_score(self, product):

        max_price = (
            SaleItem.objects
            .filter(
                sale__customer=self.customer,
            )
            .aggregate(
                max_price=Max("unit_price"),
            )["max_price"]
        )

        if not max_price:
            return Decimal("0")

        candidate_price = (
            SaleItem.objects
            .filter(
                product=product,
            )
            .aggregate(
                avg_price=Avg("unit_price"),
            )["avg_price"]
        )

        if not candidate_price:
            return Decimal("0")

        if candidate_price <= max_price:
            return Decimal("0")

        price_ratio = (
            candidate_price / max_price
        )

        if self.config:

            if price_ratio <= Decimal("1.10"):
                return self.config.upsell_10_percent_score

            if price_ratio <= Decimal("1.25"):
                return self.config.upsell_25_percent_score

            if price_ratio <= Decimal("1.50"):
                return self.config.upsell_50_percent_score

            return self.config.upsell_high_score

        # Fallback to engine defaults

        if price_ratio <= Decimal("1.10"):
            return self.UPSELL_10_PERCENT_SCORE

        if price_ratio <= Decimal("1.25"):
            return self.UPSELL_25_PERCENT_SCORE

        if price_ratio <= Decimal("1.50"):
            return self.UPSELL_50_PERCENT_SCORE

        return self.UPSELL_HIGH_SCORE
    # =====================================================
    # SIMILAR PRODUCT
    # =====================================================

    def _similar_product_score(self, product):

        purchased_product_ids = (
            self.purchased_product_ids
        )

        if not purchased_product_ids:

            return Decimal("0")

        # -------------------------------------------------
        # Same Brand + Same Category
        # -------------------------------------------------

        if product.brand and product.category:

            same_brand_category = (
                Product.objects
                .filter(
                    brand=product.brand,
                    category=product.category,
                    id__in=purchased_product_ids,
                )
                .exclude(
                    id=product.id,
                )
                .exists()
            )

            if same_brand_category:

                return (
                    self.SIMILAR_PRODUCT_SCORE
                )

        return Decimal("0")

    # =====================================================
    # CATEGORY RANK
    # =====================================================

    def _category_rank(self, product):

        if not product.category:

            return None

        category_name = (
            product.category.name
        )

        category_counts = (
            SaleItem.objects
            .filter(
                sale__customer=self.customer,
            )
            .values(
                "product__category__name",
            )
            .annotate(
                purchase_count=Count(
                    "id"
                ),
            )
            .order_by(
                "-purchase_count",
                "product__category__name",
            )
        )

        for rank, item in enumerate(
            category_counts,
            start=1,
        ):

            if (
                item[
                    "product__category__name"
                ]
                == category_name
            ):

                return rank

        return None

    # =====================================================
    # SAVE RECOMMENDATIONS
    # =====================================================

    def _save_recommendations(
        self,
        recommendations,
    ):

        # Deactivate previous recommendations
        CustomerRecommendation.objects.filter(
            customer=self.customer,
            is_active=True,
        ).update(
            is_active=False
        )

        result = []

        for rank, item in enumerate(
            recommendations,
            start=1,
        ):

            recommendation = (
                CustomerRecommendation.objects.create(

                    customer=self.customer,

                    product=item[
                        "product"
                    ],

                    recommendation_type=(
                        item[
                            "recommendation_type"
                        ]
                    ),

                    score=item[
                        "score"
                    ],

                    rank=rank,

                    reason=item[
                        "reason"
                    ],

                    is_active=True,
                )
            )

            result.append(
                recommendation
            )

        return result