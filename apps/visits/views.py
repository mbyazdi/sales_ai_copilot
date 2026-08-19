from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import (
    Visit,
    SalesOutcome,
    Salesperson,
    CustomerAssignment,
)
from apps.customers.models import Customer
from apps.recommendations.models import CustomerRecommendation
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils import timezone

def recommendation_performance_dashboard(request):
    return render(
        request,
        "management/recommendation_performance.html",
    )

def salesperson_dashboard(request):

    today = timezone.localdate()

    salesperson = (
        Salesperson.objects
        .filter(
            employee_code="SP001",
            is_active=True,
        )
        .first()
    )

    if salesperson is None:

        return render(
            request,
            "visits/dashboard.html",
            {
                "salesperson": None,
                "today": today,
                "visits": [],
                "summary": {
                    "total": 0,
                    "planned": 0,
                    "in_progress": 0,
                    "completed": 0,
                    "cancelled": 0,
                },
                "error": (
                    "فروشنده مورد نظر پیدا نشد."
                ),
            },
        )

    visits = (
        salesperson.visits
        .filter(
            visit_date=today,
        )
        .select_related(
            "customer",
            "customer__grade",
            "customer__customer_360",
        )
        .order_by(
            "id",
        )
    )

    summary = {
        "total": visits.count(),
        "planned": visits.filter(
            status=Visit.VisitStatus.PLANNED
        ).count(),
        "in_progress": visits.filter(
            status=Visit.VisitStatus.IN_PROGRESS
        ).count(),
        "completed": visits.filter(
            status=Visit.VisitStatus.COMPLETED
        ).count(),
        "cancelled": visits.filter(
            status=Visit.VisitStatus.CANCELLED
        ).count(),
    }

    return render(
        request,
        "visits/dashboard.html",
        {
            "salesperson": salesperson,
            "today": today,
            "visits": visits,
            "summary": summary,
            "error": None,
        },
    )
class CustomerVisitsAPIView(APIView):

    def get(self, request, customer_code):

        customer = get_object_or_404(
            Customer,
            customer_code=customer_code,
            is_active=True,
        )

        assignment = (
            CustomerAssignment.objects
            .filter(
                customer=customer,
                is_active=True,
            )
            .select_related("salesperson")
            .order_by("-start_date")
            .first()
        )

        visits = (
            Visit.objects
            .filter(customer=customer)
            .select_related("salesperson")
            .order_by("-visit_date", "-id")
        )

        visit_data = []

        for visit in visits:

            visit_data.append({
                "id": visit.id,
                "visit_date": visit.visit_date,
                "status": visit.status,
                "salesperson": {
                    "employee_code": (
                        visit.salesperson.employee_code
                    ),
                    "name": (
                        f"{visit.salesperson.first_name} "
                        f"{visit.salesperson.last_name}"
                    ),
                },
                "customer_request": (
                    visit.customer_request
                ),
                "customer_feedback": (
                    visit.customer_feedback
                ),
                "competitor_information": (
                    visit.competitor_information
                ),
                "notes": visit.notes,
                "order_created": visit.order_created,
                "order_amount": visit.order_amount,
                "follow_up_required": (
                    visit.follow_up_required
                ),
                "follow_up_date": (
                    visit.follow_up_date
                ),
            })

        assignment_data = None

        if assignment:

            salesperson = assignment.salesperson

            assignment_data = {
                "employee_code": (
                    salesperson.employee_code
                ),
                "name": (
                    f"{salesperson.first_name} "
                    f"{salesperson.last_name}"
                ),
                "phone": salesperson.phone,
                "start_date": assignment.start_date,
                "end_date": assignment.end_date,
            }

        return Response({

            "customer_code": customer.customer_code,

            "salesperson": assignment_data,

            "visit_count": len(visit_data),

            "visits": visit_data,

        })

class SalesOutcomeCreateAPIView(APIView):

    def post(self, request):

        visit_id = request.data.get("visit_id")
        recommendation_id = request.data.get(
            "recommendation_id"
        )
        outcome = request.data.get("outcome")

        quantity = request.data.get(
            "quantity",
            0
        )

        sales_amount = request.data.get(
            "sales_amount",
            0
        )

        notes = request.data.get(
            "notes",
            ""
        )

        # =========================================
        # VALIDATION
        # =========================================

        if not visit_id:
            return Response(
                {
                    "detail": "visit_id is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not outcome:
            return Response(
                {
                    "detail": "outcome is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # =========================================
        # VALIDATE OUTCOME
        # =========================================

        valid_outcomes = {
            value
            for value, label
            in SalesOutcome.Outcome.choices
        }

        if outcome not in valid_outcomes:

            return Response(
                {
                    "detail": (
                        f"Invalid outcome: {outcome}"
                    ),
                    "allowed_values": list(
                        valid_outcomes
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # =========================================
        # GET VISIT
        # =========================================

        try:

            visit = (
                Visit.objects
                .select_related(
                    "customer",
                    "salesperson",
                )
                .get(
                    id=visit_id
                )
            )

        except Visit.DoesNotExist:

            return Response(
                {
                    "detail": (
                        "Visit not found."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # =========================================
        # RECOMMENDATION
        # =========================================

        recommendation = None

        if recommendation_id:

            try:

                recommendation = (
                    CustomerRecommendation.objects
                    .select_related(
                        "customer",
                        "product",
                    )
                    .get(
                        id=recommendation_id,
                        customer=visit.customer,
                    )
                )

            except CustomerRecommendation.DoesNotExist:

                return Response(
                    {
                        "detail": (
                            "Recommendation not found "
                            "for this customer."
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

        # =========================================
        # CREATE SALES OUTCOME
        # =========================================

        sales_outcome = SalesOutcome.objects.create(

            visit=visit,

            recommendation=recommendation,

            outcome=outcome,

            quantity=quantity,

            sales_amount=sales_amount,

            notes=notes,
        )

        # =========================================
        # UPDATE VISIT
        # =========================================

        update_fields = []

        # -----------------------------------------
        # START VISIT AUTOMATICALLY
        # -----------------------------------------

        if (
            visit.status
            == Visit.VisitStatus.PLANNED
        ):

            visit.status = (
                Visit.VisitStatus.IN_PROGRESS
            )

            update_fields.append(
                "status"
            )


        # -----------------------------------------
        # PURCHASE RESULT
        # -----------------------------------------

        if outcome == SalesOutcome.Outcome.PURCHASED:

            visit.order_created = True

            visit.order_amount = (
                sales_amount
            )

            update_fields.extend([
                "order_created",
                "order_amount",
            ])


        # -----------------------------------------
        # FOLLOW-UP RESULT
        # -----------------------------------------

        if outcome == SalesOutcome.Outcome.FOLLOW_UP:

            visit.follow_up_required = True

            update_fields.append(
                "follow_up_required"
            )


        # -----------------------------------------
        # SAVE VISIT
        # -----------------------------------------

        if update_fields:

            update_fields.append(
                "updated_at"
            )

            visit.save(
                update_fields=list(
                    dict.fromkeys(
                        update_fields
                    )
                )
            )

        # =========================================
        # RESPONSE
        # =========================================

        return Response(
            {
                "success": True,

                "sales_outcome": {

                    "id": (
                        sales_outcome.id
                    ),

                    "visit_id": (
                        visit.id
                    ),

                    "recommendation_id": (
                        recommendation.id
                        if recommendation
                        else None
                    ),

                    "outcome": (
                        sales_outcome.outcome
                    ),

                    "quantity": (
                        sales_outcome.quantity
                    ),

                    "sales_amount": (
                        sales_outcome.sales_amount
                    ),

                    "notes": (
                        sales_outcome.notes
                    ),

                    "product": {

                        "code": (
                            recommendation.product.product_code
                            if recommendation
                            else None
                        ),

                        "name": (
                            recommendation.product.name
                            if recommendation
                            else None
                        ),
                    },

                    "created_at": (
                        sales_outcome.created_at
                    ),
                },

                "visit": {

                    "id": visit.id,

                    "status": (
                        visit.status
                    ),

                    "order_created": (
                        visit.order_created
                    ),

                    "order_amount": (
                        visit.order_amount
                    ),

                    "follow_up_required": (
                        visit.follow_up_required
                    ),
                },
            },
            status=status.HTTP_201_CREATED,
        )

class CustomerSalesOutcomeHistoryAPIView(APIView):

    def get(self, request, customer_code):

        from apps.customers.models import Customer
        from apps.visits.models import SalesOutcome

        customer = get_object_or_404(
            Customer,
            customer_code=customer_code,
            is_active=True,
        )

        outcomes = (
            SalesOutcome.objects
            .filter(
                visit__customer=customer
            )
            .select_related(
                "visit",
                "recommendation",
                "recommendation__product",
                "recommendation__product__category",
            )
            .order_by("-created_at")
        )

        data = []

        for outcome in outcomes:

            recommendation = outcome.recommendation
            product = (
                recommendation.product
                if recommendation
                else None
            )

            data.append({

                "id": outcome.id,

                "visit_id": outcome.visit_id,

                "visit_date": (
                    outcome.visit.visit_date
                ),

                "product": {
                    "code": (
                        product.product_code
                        if product
                        else None
                    ),
                    "name": (
                        product.name
                        if product
                        else None
                    ),
                    "category": (
                        str(product.category)
                        if product
                        else None
                    ),
                },

                "recommendation": {
                    "id": (
                        recommendation.id
                        if recommendation
                        else None
                    ),
                    "rank": (
                        recommendation.rank
                        if recommendation
                        else None
                    ),
                    "type": (
                        recommendation.recommendation_type
                        if recommendation
                        else None
                    ),
                    "score": (
                        recommendation.score
                        if recommendation
                        else None
                    ),
                },

                "outcome": outcome.outcome,

                "quantity": outcome.quantity,

                "sales_amount": outcome.sales_amount,

                "notes": outcome.notes,

                "created_at": outcome.created_at,
            })

        return Response({

            "customer": {
                "code": customer.customer_code,
                "name": customer.name,
            },

            "outcome_count": len(data),

            "sales_outcomes": data,
        })
    
class RecommendationPerformanceAPIView(APIView):

    def get(self, request, customer_code=None):

        from apps.customers.models import Customer
        from apps.visits.services import (
            get_recommendation_performance,
        )

        customer = None

        if customer_code:

            customer = get_object_or_404(
                Customer,
                customer_code=customer_code,
                is_active=True,
            )

        performance = get_recommendation_performance(
            customer=customer
        )

        total_presented = sum(
            item["presented"]
            for item in performance
        )

        total_purchased = sum(
            item["purchased"]
            for item in performance
        )

        total_interested = sum(
            item["interested"]
            for item in performance
        )

        total_revenue = sum(
            item["revenue"]
            for item in performance
        )

        total_conversion_rate = (
            round(
                (
                    total_purchased
                    / total_presented
                ) * 100,
                2,
            )
            if total_presented
            else 0
        )

        total_interest_rate = (
            round(
                (
                    total_interested
                    / total_presented
                ) * 100,
                2,
            )
            if total_presented
            else 0
        )

        return Response({

            "customer": (
                {
                    "code": customer.customer_code,
                    "name": customer.name,
                }
                if customer
                else None
            ),

            "summary": {

                "presented": (
                    total_presented
                ),

                "purchased": (
                    total_purchased
                ),

                "interested": (
                    total_interested
                ),

                "revenue": (
                    total_revenue
                ),

                "conversion_rate": (
                    total_conversion_rate
                ),

                "interest_rate": (
                    total_interest_rate
                ),
            },

            "performance": performance,

        })
    
    
class VisitCompleteAPIView(APIView):

    def post(self, request, visit_id):

        visit = get_object_or_404(
            Visit.objects.select_related(
                "customer",
                "salesperson",
            ),
            id=visit_id,
        )

        if (
            visit.status
            == Visit.VisitStatus.CANCELLED
        ):

            return Response(
                {
                    "detail": (
                        "Cancelled visit cannot "
                        "be completed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        visit.status = (
            Visit.VisitStatus.COMPLETED
        )

        visit.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return Response(
            {
                "success": True,

                "visit": {
                    "id": visit.id,
                    "status": visit.status,
                    "customer_code": (
                        visit.customer.customer_code
                    ),
                    "salesperson_code": (
                        visit.salesperson.employee_code
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

class VisitStartAPIView(APIView):

    def post(self, request, visit_id):

        visit = get_object_or_404(
            Visit.objects.select_related(
                "customer",
                "salesperson",
            ),
            id=visit_id,
        )

        if (
            visit.status
            == Visit.VisitStatus.CANCELLED
        ):

            return Response(
                {
                    "detail": (
                        "Cancelled visit cannot "
                        "be started."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            visit.status
            == Visit.VisitStatus.COMPLETED
        ):

            return Response(
                {
                    "detail": (
                        "Completed visit cannot "
                        "be started again."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        visit.status = (
            Visit.VisitStatus.IN_PROGRESS
        )

        visit.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return Response(
            {
                "success": True,

                "visit": {
                    "id": visit.id,
                    "status": visit.status,
                    "customer_code": (
                        visit.customer.customer_code
                    ),
                    "salesperson_code": (
                        visit.salesperson.employee_code
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )    