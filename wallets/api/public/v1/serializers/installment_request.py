# wallets/api/public/v1/serializers/installment_request.py

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from wallets.api.public.v1.serializers import InstallmentSerializer
from wallets.models import InstallmentRequest
from wallets.services import calculate_installments
from wallets.utils.choices import InstallmentRequestStatus


class InstallmentRequestListItemSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source="store.name", read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    installments = serializers.SerializerMethodField()

    @extend_schema_field(
        serializers.ListField(child=InstallmentSerializer())
    )
    def get_installments(self, obj):
        if obj.status != InstallmentRequestStatus.COMPLETED:
            return None
        plan = obj.get_installment_plan()
        if not plan:
            return None
        installments = plan.installments.order_by("due_date")
        return InstallmentSerializer(installments, many=True).data

    class Meta:
        model = InstallmentRequest
        fields = [
            "reference_code",
            "store_name",
            "status_display",
            "store_proposed_amount",
            "user_requested_amount",
            "system_approved_amount",
            "requested_at",
            "evaluated_at",
            "user_confirmed_at",
            "store_confirmed_at",
            "cancelled_at",
            "duration_months",
            "period_months",
            "created_at",
            "installments",
        ]


class InstallmentRequestDetailSerializer(InstallmentRequestListItemSerializer):
    min_credit = serializers.IntegerField(
        source="contract.min_credit_per_user", read_only=True
    )
    min_repayment_months = serializers.IntegerField(
        source="contract.min_repayment_months", read_only=True
    )
    max_repayment_months = serializers.IntegerField(
        source="contract.max_repayment_months", read_only=True
    )
    allowed_periods = serializers.ListField(
        source="contract.allowed_period_months", read_only=True
    )
    interest_rate = serializers.FloatField(
        source="contract.interest_rate", read_only=True
    )

    class Meta(InstallmentRequestListItemSerializer.Meta):
        fields = InstallmentRequestListItemSerializer.Meta.fields + [
            "min_credit",
            "min_repayment_months",
            "max_repayment_months",
            "allowed_periods",
            "interest_rate",
        ]


class InstallmentRequestUnderwriteSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    duration_months = serializers.IntegerField(min_value=1)
    period_months = serializers.IntegerField(min_value=1)

    def validate(self, data):
        request_obj = self.context["installment_request"]
        contract = request_obj.contract

        if request_obj.status != InstallmentRequestStatus.CREATED:
            raise serializers.ValidationError(
                "این درخواست در مرحله‌ی اولیه نیست."
            )

        if data["amount"] < contract.min_credit_per_user:
            raise serializers.ValidationError(
                "مبلغ کمتر از حداقل مجاز قرارداد است."
            )
        if data["amount"] > contract.max_credit_per_user:
            raise serializers.ValidationError("مبلغ بیش از سقف قرارداد است.")

        if data["amount"] > request_obj.store_proposed_amount:
            raise serializers.ValidationError(
                "مبلغ بیش از مبلغ درخواست شده است."
            )

        if data["duration_months"] < contract.min_repayment_months:
            raise serializers.ValidationError(
                "مدت بازپرداخت کمتر از حداقل مجاز است."
            )
        if data["duration_months"] > contract.max_repayment_months:
            raise serializers.ValidationError(
                "مدت بازپرداخت بیش از حد مجاز است."
            )
        if data["period_months"] not in contract.allowed_period_months:
            raise serializers.ValidationError("پریود انتخابی نامعتبر است.")
        if data["period_months"] > data["duration_months"]:
            raise serializers.ValidationError(
                "پریود از مدت بازپرداخت بزرگ‌تر است."
            )

        return data

    def persist_and_enqueue(self):
        from wallets.tasks import run_underwriting_for_request

        req: InstallmentRequest = self.context["installment_request"]
        req.user_requested_amount = self.validated_data["amount"]
        req.duration_months = self.validated_data["duration_months"]
        req.period_months = self.validated_data["period_months"]
        req.requested_at = timezone.localtime(timezone.now())
        req.mark_underwriting()
        req.save()

        run_underwriting_for_request.delay(req.id)

        return {
            "status": req.status,
            "reference_code": req.reference_code,
            "message": "اعتبارسنجی آغاز شد؛ لطفاً بعداً نتیجه را بررسی کنید.",
        }


class InstallmentRequestCalculationSerializer(serializers.Serializer):
    duration_months = serializers.IntegerField(min_value=1)
    period_months = serializers.IntegerField(min_value=1)

    def validate(self, data):
        req: InstallmentRequest = self.context["installment_request"]
        c = req.contract

        # قیود قرارداد
        if data["duration_months"] < c.min_repayment_months:
            raise serializers.ValidationError(
                "مدت بازپرداخت کمتر از حداقل مجاز است."
            )
        if data["duration_months"] > c.max_repayment_months:
            raise serializers.ValidationError(
                "مدت بازپرداخت بیش از حد مجاز است."
            )
        if data["period_months"] not in c.allowed_period_months:
            raise serializers.ValidationError("پریود انتخابی نامعتبر است.")
        if data["period_months"] > data["duration_months"]:
            raise serializers.ValidationError(
                "پریود از مدت بازپرداخت بزرگ‌تر است."
            )
        if req.system_approved_amount and req.status == InstallmentRequestStatus.VALIDATED:
            amount = req.system_approved_amount
        elif req.user_requested_amount:
            amount = req.user_requested_amount
        else:
            amount = req.store_proposed_amount
        amount = max(c.min_credit_per_user, min(amount, c.max_credit_per_user))

        data["amount_for_preview"] = amount
        return data

    def preview(self):
        req: InstallmentRequest = self.context["installment_request"]
        amount = self.validated_data["amount_for_preview"]
        duration = self.validated_data["duration_months"]
        period = self.validated_data["period_months"]
        ir = req.contract.interest_rate

        plan = calculate_installments(
            amount=amount,
            duration_months=duration,
            period_months=period,
            annual_interest_rate=ir,
        )
        return plan


class InstallmentRequestConfirmSerializer(serializers.Serializer):
    def validate(self, data):
        req: InstallmentRequest = self.context["installment_request"]

        if req.status != InstallmentRequestStatus.VALIDATED:
            raise serializers.ValidationError(
                "درخواست در وضعیت اعتبارسنجی‌شده نیست."
            )
        if not req.system_approved_amount:
            raise serializers.ValidationError("نتیجه اعتبارسنجی موجود نیست.")

        return data

    def confirm(self):
        req: InstallmentRequest = self.context["installment_request"]
        req.mark_user_accepted()
        print(            req.system_approved_amount,
            req.duration_months,
            req.period_months,
            req.contract.interest_rate)
        plan_preview = calculate_installments(
            req.system_approved_amount,
            req.duration_months,
            req.period_months,
            req.contract.interest_rate
        )
        return {
            "reference_code": req.reference_code,
            "status": req.status,
            "approved_amount": req.system_approved_amount,
            "duration_months": req.duration_months,
            "period_months": req.period_months,
            "installment_plan": plan_preview,
        }
