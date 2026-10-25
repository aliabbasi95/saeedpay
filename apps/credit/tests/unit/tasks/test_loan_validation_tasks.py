from unittest.mock import Mock

import pytest
from django.core.cache import cache

from apps.credit.models import LoanRiskReport
from apps.credit.tasks_loan_validation import (
    _otp_cache_key,
    check_loan_report_result,
    verify_loan_otp_and_request_report,
)
from apps.credit.utils.choices import LoanReportStatus
from apps.profiles.models.profile import Profile
from apps.profiles.utils.choices import AuthenticationStage


@pytest.fixture
def verified_profile(db, user_factory):
    user = user_factory(username="loan_user")
    return Profile.objects.create(
        user=user,
        phone_number="09125095450",
        national_id="0018812503",
        birth_date="1370/01/01",
        auth_stage=AuthenticationStage.VIDEO_VERIFIED,
    )


@pytest.fixture
def otp_report(verified_profile):
    report = LoanRiskReport.objects.create(
        profile=verified_profile,
        national_code=verified_profile.national_id,
        mobile_number=verified_profile.phone_number,
    )
    report.mark_otp_sent("provider-uid")
    return report


@pytest.mark.django_db
def test_verify_task_keeps_frontend_contract_and_completes_immediately(
    mocker, otp_report
):
    service = Mock()
    service.loan_verify_otp_and_request_report.return_value = {
        "success": True,
        "completed": True,
        "unique_id": "provider-uid",
        "score": 646,
        "risk": "A3",
        "grade_description": None,
        "report_data": {
            "reportInformation": {"reportLevel": "advanced"},
            "creditScore": {"score": "646", "risk": "A3"},
        },
        "report_types": ["advanced"],
        "timestamp": "2026-10-25 09:18:26",
        "message": "گزارش اعتبارسنجی با موفقیت انجام شد.",
    }
    mocker.patch(
        "apps.credit.tasks_loan_validation.get_identity_auth_service",
        return_value=service,
    )

    result = verify_loan_otp_and_request_report.apply(
        args=[otp_report.id, "123456"]
    ).result

    otp_report.refresh_from_db()
    assert result["success"] is True
    assert result["credit_score"] == 646
    assert result["risk_level"] == "A3"
    assert otp_report.status == LoanReportStatus.COMPLETED
    assert otp_report.credit_score == 646
    assert otp_report.risk_level == "A3"
    assert otp_report.grade_description == "ریسک بسیار پایین (A3)"
    assert otp_report.report_types == ["advanced"]
    assert otp_report.report_data["creditScore"]["risk"] == "A3"
    assert cache.get(_otp_cache_key(otp_report.id)) is None


@pytest.mark.django_db
def test_check_task_polls_with_cached_otp_and_completes(mocker, otp_report):
    otp_report.mark_report_requested("provider-uid")
    cache.set(_otp_cache_key(otp_report.id), "123456", timeout=60)

    service = Mock()
    service.loan_get_report_result.return_value = {
        "success": True,
        "completed": True,
        "score": 646,
        "risk": "A3",
        "grade_description": None,
        "report_data": {
            "reportInformation": {"reportLevel": "advanced"},
            "creditScore": {"score": "646", "risk": "A3"},
        },
        "report_types": ["advanced"],
        "timestamp": "2026-10-25 09:18:26",
    }
    mocker.patch(
        "apps.credit.tasks_loan_validation.get_identity_auth_service",
        return_value=service,
    )

    result = check_loan_report_result.apply(args=[otp_report.id]).result

    otp_report.refresh_from_db()
    assert result["success"] is True
    assert otp_report.status == LoanReportStatus.COMPLETED
    assert otp_report.credit_score == 646
    assert otp_report.risk_level == "A3"
    service.loan_get_report_result.assert_called_once_with(
        unique_id="provider-uid",
        otp_code="123456",
    )
    assert cache.get(_otp_cache_key(otp_report.id)) is None


@pytest.mark.django_db
def test_check_task_fails_cleanly_when_polling_context_expired(otp_report):
    otp_report.mark_report_requested("provider-uid")
    cache.delete(_otp_cache_key(otp_report.id))

    result = check_loan_report_result.apply(args=[otp_report.id]).result

    otp_report.refresh_from_db()
    assert result["success"] is False
    assert result["error"] == "otp_context_expired"
    assert otp_report.status == LoanReportStatus.FAILED
    assert otp_report.error_code == "OTP_CONTEXT_EXPIRED"


def test_a3_is_classified_as_low_risk():
    report = LoanRiskReport(risk_level="A3")
    assert report.is_low_risk is True
    assert report.is_medium_risk is False
    assert report.is_high_risk is False


def test_c3_is_classified_as_medium_risk():
    report = LoanRiskReport(risk_level="C3")
    assert report.is_low_risk is False
    assert report.is_medium_risk is True
    assert report.is_high_risk is False
