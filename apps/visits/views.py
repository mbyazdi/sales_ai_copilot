from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from datetime import datetime

from .models import (
    Visit,
    SalesOutcome,
    Salesperson,
    CustomerAssignment,
    FollowUpTask,
)
from apps.customers.models import Customer
from apps.recommendations.models import CustomerRecommendation
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from rest_framework.permissions import IsAuthenticated

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
        follow_up_date = request.data.get(
            "follow_up_date"
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
        # FOLLOW-UP DATE VALIDATION
        # =========================================

        parsed_follow_up_date = None

        if outcome == SalesOutcome.Outcome.FOLLOW_UP:

            if not follow_up_date:

                return Response(
                    {
                        "detail": (
                            "follow_up_date is required "
                            "when outcome is FOLLOW_UP."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:

                parsed_follow_up_date = (
                    datetime.strptime(
                        follow_up_date,
                        "%Y-%m-%d",
                    ).date()
                )

            except (
                TypeError,
                ValueError,
            ):

                return Response(
                    {
                        "detail": (
                            "follow_up_date must use "
                            "YYYY-MM-DD format."
                        )
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
        # VISIT STATUS VALIDATION
        # =========================================

        if (
            visit.status
            != Visit.VisitStatus.IN_PROGRESS
        ):

            return Response(
                {
                    "detail": (
                        "Sales outcome can only be recorded "
                        "while the visit is in progress."
                    ),
                    "visit_status": (
                        visit.status
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
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

            visit.follow_up_date = (
                parsed_follow_up_date
            )

            update_fields.extend([
                "follow_up_required",
                "follow_up_date",
            ])
            FollowUpTask.objects.update_or_create(
                visit=visit,
                customer=visit.customer,
                salesperson=visit.salesperson,
                status=FollowUpTask.Status.OPEN,
                defaults={
                    "due_date": (
                        parsed_follow_up_date
                    ),
                    "notes": (
                        notes
                    ),
                },
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
class FollowUpTaskListAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        salesperson = getattr(
            request.user,
            "salesperson_profile",
            None,
        )

        if not salesperson:

            return Response(
                {
                    "detail": (
                        "Salesperson profile not found "
                        "for the current user."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        status_filter = request.GET.get(
            "status"
        )

        time_state_filter = request.GET.get(
            "time_state"
        )

        queryset = (
            FollowUpTask.objects
            .filter(
                salesperson=salesperson,
            )
            .select_related(
                "customer",
                "visit",
                "salesperson",
            )
            .order_by(
                "status",
                "due_date",
                "id",
            )
        )

        if status_filter:

            queryset = queryset.filter(
                status=status_filter
            )

        today = timezone.localdate()

        if time_state_filter == "OVERDUE":

            queryset = queryset.filter(
                status=FollowUpTask.Status.OPEN,
                due_date__lt=today,
            )

        elif time_state_filter == "TODAY":

            queryset = queryset.filter(
                status=FollowUpTask.Status.OPEN,
                due_date=today,
            )

        elif time_state_filter == "UPCOMING":

            queryset = queryset.filter(
                status=FollowUpTask.Status.OPEN,
                due_date__gt=today,
            )

        elif time_state_filter == "DONE":

            queryset = queryset.filter(
                status=FollowUpTask.Status.DONE,
            )

        elif time_state_filter == "CANCELLED":

            queryset = queryset.filter(
                status=FollowUpTask.Status.CANCELLED,
            )

        tasks = []

        for task in queryset:

            if task.status == FollowUpTask.Status.DONE:

                time_state = "DONE"

            elif task.status == FollowUpTask.Status.CANCELLED:

                time_state = "CANCELLED"

            elif task.due_date < today:

                time_state = "OVERDUE"

            elif task.due_date == today:

                time_state = "TODAY"

            else:

                time_state = "UPCOMING"

            tasks.append({
                "id": task.id,
                "status": task.status,
                "time_state": time_state,
                "due_date": task.due_date,

                "customer": {
                    "id": task.customer_id,
                    "customer_code": (
                        task.customer.customer_code
                    ),
                    "name": (
                        task.customer.name
                    ),
                },

                "salesperson": {
                    "id": task.salesperson_id,
                    "employee_code": (
                        task.salesperson.employee_code
                    ),
                    "full_name": (
                        task.salesperson.full_name
                    ),
                },

                "visit": {
                    "id": task.visit_id,
                    "status": task.visit.status,
                },

                "notes": task.notes,

                "completed_at": (
                    task.completed_at
                ),
            })

        return Response(
            {
                "count": len(tasks),
                "tasks": tasks,
            },
            status=status.HTTP_200_OK,
        )

class FollowUpTaskStatusAPIView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def post(self, request, task_id):

        salesperson = getattr(
            request.user,
            "salesperson_profile",
            None,
        )

        if not salesperson:

            return Response(
                {
                    "detail": (
                        "Salesperson profile not found "
                        "for the current user."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        new_status = request.data.get(
            "status"
        )

        allowed_statuses = {
            FollowUpTask.Status.DONE,
            FollowUpTask.Status.CANCELLED,
        }

        if new_status not in allowed_statuses:

            return Response(
                {
                    "detail": (
                        "status must be DONE "
                        "or CANCELLED."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            task = (
                FollowUpTask.objects
                .select_related(
                    "visit",
                )
                .get(
                    id=task_id,
                    salesperson=salesperson,
                )
            )

        except FollowUpTask.DoesNotExist:

            return Response(
                {
                    "detail": (
                        "Follow-up task not found."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        task.status = new_status

        if new_status == FollowUpTask.Status.DONE:

            task.completed_at = (
                timezone.now()
            )

        else:

            task.completed_at = None

        task.save(
            update_fields=[
                "status",
                "completed_at",
                "updated_at",
            ]
        )

        open_tasks = (
            FollowUpTask.objects
            .filter(
                visit=task.visit,
                status=FollowUpTask.Status.OPEN,
            )
            .order_by(
                "due_date",
                "id",
            )
        )

        next_open_task = (
            open_tasks.first()
        )

        if next_open_task:

            task.visit.follow_up_required = True

            task.visit.follow_up_date = (
                next_open_task.due_date
            )

        else:

            task.visit.follow_up_required = False

            task.visit.follow_up_date = None

        task.visit.save(
            update_fields=[
                "follow_up_required",
                "follow_up_date",
                "updated_at",
            ]
        )

        return Response(
            {
                "success": True,

                "task": {
                    "id": task.id,
                    "status": task.status,
                    "completed_at": (
                        task.completed_at
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

@login_required
def follow_up_dashboard(request):

    today = timezone.localdate()

    salespersons = (
        Salesperson.objects
        .all()
        .order_by(
            "first_name",
            "last_name",
            "employee_code",
        )
    )

    salesperson = getattr(
        request.user,
        "salesperson_profile",
        None,
    )

    if not salesperson:

        return render(
            request,
            "core/follow_up_dashboard.html",
            {
                "salesperson_missing": True,
            },
        )

    open_tasks = (
        FollowUpTask.objects
        .filter(
            status=FollowUpTask.Status.OPEN,
            salesperson=salesperson,
        )
        .select_related(
            "customer",
            "visit",
            "salesperson",
        )
        .order_by(
            "due_date",
            "id",
        )
    )

    overdue_tasks = open_tasks.filter(
        due_date__lt=today,
    )

    today_tasks = open_tasks.filter(
        due_date=today,
    )

    upcoming_tasks = open_tasks.filter(
        due_date__gt=today,
    )

    context = {
        "today": today,

        "overdue_tasks": overdue_tasks,
        "today_tasks": today_tasks,
        "upcoming_tasks": upcoming_tasks,

        "overdue_count": overdue_tasks.count(),
        "today_count": today_tasks.count(),
        "upcoming_count": upcoming_tasks.count(),
        "open_count": open_tasks.count(),
        "salesperson": salesperson,
    }

    return render(
        request,
        "core/follow_up_dashboard.html",
        context,
    )