from unittest import TestCase
from unittest.mock import Mock, patch

from apps.kyc.services.loan_validation_service import LoanValidationService


POST_PATH = "apps.kyc.services.loan_validation_service.requests.post"


class LoanValidationServiceTestCase(TestCase):
    def setUp(self):
        self.service = LoanValidationService("https://provider.example:9091", timeout=5)

    @patch(POST_PATH)
    def test_request_report_processing_response(self, mock_post):
        response = Mock(status_code=200)
        response.json.return_value = {
            "timestamp": "2026-10-25 09:12:03",
            "uniqueId": "provider-uid",
            "data": {
                "message": "گزارش اعتبارسنجی در حال آماده سازی است.",
                "details": None,
            },
            "error": None,
        }
        mock_post.return_value = response

        result = self.service.verify_otp_and_request_report(
            otp_code="123456",
            unique_id="provider-uid",
            access_token="token",
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["completed"])
        self.assertTrue(result["processing"])
        self.assertEqual(result["status"], "IN_PROCESSING")
        self.assertEqual(result["unique_id"], "provider-uid")

        _, kwargs = mock_post.call_args
        self.assertEqual(
            kwargs["json"],
            {"otpCode": "123456", "uniqueId": "provider-uid"},
        )
        self.assertTrue(mock_post.call_args.args[0].endswith("/api/inq/loan-validation/request-report"))

    @patch(POST_PATH)
    def test_get_report_result_parses_new_done_json_schema(self, mock_post):
        response = Mock(status_code=200)
        response.json.return_value = {
            "timestamp": "2026-10-25 09:18:26",
            "uniqueId": "provider-uid",
            "data": {
                "message": "گزارش اعتبارسنجی با موفقیت انجام شد.",
                "details": {
                    "jsonData": {
                        "assessmentId": "assessment-1",
                        "status": "DONE",
                        "stage": None,
                        "progress": None,
                        "level": "advance",
                        "outputType": "json",
                        "data": {
                            "reportInformation": {
                                "reportLevel": "advanced",
                                "reportLevelDescription": "پیشرفته",
                            },
                            "creditScore": {
                                "score": "646",
                                "risk": "A3",
                                "riskDescription": None,
                                "scoreFactorList": [{"score": "530"}],
                                "scoreReasonList": [],
                            },
                            "facilityList": [],
                        },
                        "fileName": None,
                        "contentBase64": None,
                    }
                },
            },
            "error": None,
        }
        mock_post.return_value = response

        result = self.service.get_report_result(
            unique_id="provider-uid",
            otp_code="123456",
            access_token="token",
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["completed"])
        self.assertFalse(result["processing"])
        self.assertEqual(result["status"], "DONE")
        self.assertEqual(result["score"], 646)
        self.assertIsInstance(result["score"], int)
        self.assertEqual(result["risk"], "A3")
        self.assertIsNone(result["grade_description"])
        self.assertEqual(result["assessment_id"], "assessment-1")
        self.assertEqual(result["report_level"], "advanced")
        self.assertEqual(result["report_types"], ["advanced"])
        self.assertEqual(result["report_data"]["creditScore"]["score"], "646")

        _, kwargs = mock_post.call_args
        self.assertEqual(
            kwargs["json"],
            {"otpCode": "123456", "uniqueId": "provider-uid"},
        )
        self.assertTrue(mock_post.call_args.args[0].endswith("/api/inq/loan-validation/request-report"))

    def test_normalize_report_response_keeps_legacy_schema_compatible(self):
        result = self.service._normalize_report_response(
            {
                "timestamp": "2025-10-13 15:55:09",
                "uniqueId": "legacy-id",
                "data": {
                    "message": "ok",
                    "details": {
                        "jsonData": {
                            "score": {
                                "score": 604,
                                "risk": "B2",
                                "personInformation": {
                                    "gradeDescription": "ریسک پایین"
                                },
                            },
                            "reportTypes": ["Base", "Score"],
                        }
                    },
                },
                "error": None,
            }
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["completed"])
        self.assertEqual(result["score"], 604)
        self.assertEqual(result["risk"], "B2")
        self.assertEqual(result["grade_description"], "ریسک پایین")
        self.assertEqual(result["report_types"], ["Base", "Score"])

    def test_done_response_without_structured_data_fails_cleanly(self):
        result = self.service._normalize_report_response(
            {
                "uniqueId": "provider-uid",
                "data": {
                    "message": "done",
                    "details": {
                        "jsonData": {
                            "status": "DONE",
                            "level": "advance",
                            "outputType": "json",
                            "data": None,
                        }
                    },
                },
                "error": None,
            }
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["error_code"], "INVALID_COMPLETED_REPORT")
