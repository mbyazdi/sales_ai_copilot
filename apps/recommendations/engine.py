from decimal import Decimal

from apps.products.models import Product
from apps.sales.models import SaleItem
from apps.promotions.models import PromotionProduct

from .models import CustomerRecommendation


class RecommendationEngine:
    """
    Rule-based recommendation engine.

    IMPORTANT:
    This engine decides WHICH products are candidates.

    Ollama / LLM will NOT make this decision.
    """

    MAX_RECOMMENDATIONS = 5

    def __init__(self, customer):

        self.customer = customer

        self.customer_360 = getattr(
            customer,
            "customer_360",
            None,
        )

    # ========================================================
    # Public API
    # ========================================================

    def generate(self):

        if not self.customer_360:
            return []

        candidates = self._get_candidates()

        recommendations = []

        for product in candidates:

            result = self._score_product(product)

            if result["score"] > 0:
                recommendations.append(result)

        recommendations.sort(
            key=lambda x: x["score"],
            reverse=True,
        )

        recommendations = recommendations[
            :self.MAX_RECOMMENDATIONS
        ]

        return self._save_recommendations(
            recommendations
        )

    # ========================================================
    # Candidate Generation
    # ========================================================

    def _get_candidates(self):

        """
        Select only real active products.

        No AI is involved here.
        """

        return (
            Product.objects
            .filter(
                is_active=True,
            )
            .select_related(
                "brand",
                "category",
            )
        )

    # ========================================================
    # Product Scoring
    # ========================================================

    def _score_product(self, product):

        score = Decimal("0")

        reasons = []

        # ----------------------------------------------------
        # 1. Product Group / Category Affinity
        # ----------------------------------------------------

        group_score = self._group_affinity(product)

        score += group_score

        if group_score > 0:

            reasons.append(
                "دسته محصول با الگوی خرید مشتری "
                "همخوانی دارد."
            )

        # ----------------------------------------------------
        # 2. Previous Purchase
        # ----------------------------------------------------

        purchase_score = self._previous_purchase(product)

        score += purchase_score

        if purchase_score > 0:

            reasons.append(
                "مشتری قبلاً این محصول را خریداری "
                "کرده است."
            )

        # ----------------------------------------------------
        # 3. Customer Grade
        # ----------------------------------------------------

        grade_score = self._grade_score(product)

        score += grade_score

        if grade_score > 0:

            reasons.append(
                "محصول برای گرید مشتری مناسب است."
            )

        # ----------------------------------------------------
        # 4. Promotion
        # ----------------------------------------------------

        promotion_score = self._promotion_score(product)

        score += promotion_score

        if promotion_score > 0:

            reasons.append(
                "برای این محصول Promotion فعال وجود دارد."
            )

        # ----------------------------------------------------
        # Final score
        # ----------------------------------------------------

        score = min(
            score,
            Decimal("100"),
        )

        return {
            "product": product,
            "score": score,
            "reason": " ".join(reasons),
        }

    # ========================================================
    # Product Group Affinity
    # ========================================================

    def _group_affinity(self, product):

        segment = self.customer_360.segment

        top_category = self.customer_360.top_category

        score = Decimal("0")

        if (
            top_category
            and product.category.name == top_category
        ):
            score += Decimal("30")

        if segment == "HIGH_VALUE":

            score += Decimal("10")

        elif segment == "GROWTH":

            score += Decimal("8")

        elif segment == "AT_RISK":

            score += Decimal("5")

        return score

    # ========================================================
    # Previous Purchase
    # ========================================================

    def _previous_purchase(self, product):

        exists = (
            SaleItem.objects
            .filter(
                sale__customer=self.customer,
                product=product,
            )
            .exists()
        )

        if exists:
            return Decimal("25")

        return Decimal("0")

    # ========================================================
    # Customer Grade
    # ========================================================

    def _grade_score(self, product):

        grade = self.customer.grade

        if not grade:
            return Decimal("0")

        if grade.code == "A":

            return Decimal("15")

        if grade.code == "B":

            return Decimal("10")

        if grade.code == "C":

            return Decimal("5")

        return Decimal("0")

    # ========================================================
    # Promotion
    # ========================================================

    def _promotion_score(self, product):

        active_promotions = (
            PromotionProduct.objects
            .filter(
                product=product,
                promotion__is_active=True,
            )
            .exists()
        )

        if active_promotions:
            return Decimal("20")

        return Decimal("0")

    # ========================================================
    # Save
    # ========================================================

    def _save_recommendations(
        self,
        recommendations,
    ):

        # فقط Recommendationهای قبلی تولیدشده
        # برای این مشتری غیرفعال می‌شوند.
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

                    product=item["product"],

                    recommendation_type=(
                        CustomerRecommendation
                        .RecommendationType
                        .CATEGORY
                    ),

                    score=item["score"],

                    rank=rank,

                    reason=item["reason"],

                    is_active=True,
                )
            )

            result.append(
                recommendation
            )

        return result