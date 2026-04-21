# customers/api/public/v1/views/simple_status.py

from django.db import models
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from blogs.models.comment import Comment
from customers.api.public.v1.schema.simple_status import simple_status_schema
from customers.models.customer import Customer
from merchants.models.merchant import Merchant


class SimpleStatusView(APIView):
    permission_classes = [AllowAny]

    @simple_status_schema
    def get(self, request):
        active_users_count = Customer.objects.count()
        contracted_merchants_count = Merchant.objects.count()

        comments_without_article = Comment.objects.filter(
            is_approved=True,
            article__isnull=True,
        )

        total_comments = comments_without_article.count()

        if total_comments > 0:
            avg_rating = (
                comments_without_article.aggregate(avg_rating=models.Avg("rating"))[
                    "avg_rating"
                ]
                or 0
            )
            satisfaction_percentage = (
                ((avg_rating - 1) / 4) * 100 if avg_rating > 0 else 0
            )
        else:
            satisfaction_percentage = 100

        return Response(
            {
                "active_users": active_users_count,
                "contracted_merchants": contracted_merchants_count,
                "customer_satisfaction": round(satisfaction_percentage, 2),
            }
        )
