from rest_framework import status
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils import timezone

from .services import (
    build_target_summary,
    get_salesperson_target_progress,
)


class MySalesTargetProgressAPIView(APIView):
    """
    Return active Sales Target progress for the
    currently authenticated salesperson.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        salesperson = getattr(
            request.user,
            "salesperson_profile",
            None,
        )

        if (
            salesperson is None
            or not salesperson.is_active
        ):

            return Response(
                {
                    "detail": (
                        "Active salesperson profile "
                        "was not found."
                    ),
                },
                status=(
                    status.HTTP_403_FORBIDDEN
                ),
            )

        today = timezone.localdate()

        target_progress = (
            get_salesperson_target_progress(
                salesperson=salesperson,
                as_of_date=today,
            )
        )

        target_summary = (
            build_target_summary(
                target_progress
            )
        )

        return Response(
            {
                "as_of_date": today,

                "salesperson": {
                    "employee_code": (
                        salesperson.employee_code
                    ),

                    "full_name": (
                        salesperson.full_name
                    ),
                },

                "summary": (
                    target_summary
                ),

                "targets": (
                    target_progress
                ),
            },
            status=status.HTTP_200_OK,
        )