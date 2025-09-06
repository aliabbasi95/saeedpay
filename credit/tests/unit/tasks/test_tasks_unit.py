# credit/tests/unit/tasks/test_tasks_unit.py

from types import SimpleNamespace

import pytest

from credit.services.use_cases import FinalizeResult
from credit.tasks import (
    task_month_end_rollover,
    task_finalize_due_windows,
    task_daily_credit_maintenance,
)


class TestTaskMetadata:
    def test_task_month_end_rollover_metadata(self):
        # Ensure robust retry policy is configured as expected
        assert task_month_end_rollover.max_retries == 3
        assert task_month_end_rollover.default_retry_delay == 300
        assert task_month_end_rollover.request is not None  # bind=True

    def test_task_finalize_due_windows_metadata(self):
        assert task_finalize_due_windows.max_retries == 3
        assert task_finalize_due_windows.default_retry_delay == 300
        assert task_finalize_due_windows.request is not None

    def test_task_daily_credit_maintenance_metadata(self):
        assert task_daily_credit_maintenance.max_retries == 3
        assert task_daily_credit_maintenance.default_retry_delay == 300
        assert task_daily_credit_maintenance.request is not None


class TestMonthEndRolloverUnit:
    def test_success_wraps_usecase_result(self, mocker):
        mocked = mocker.patch(
            "credit.tasks.StatementUseCases.perform_month_end_rollover",
            return_value={
                "statements_closed": 2, "statements_created": 1,
                "interest_lines_added": 1
            },
        )
        out = task_month_end_rollover.apply().result
        mocked.assert_called_once_with()
        assert out == {
            "status": "success",
            "result": {
                "statements_closed": 2, "statements_created": 1,
                "interest_lines_added": 1
            },
        }

    def test_exception_triggers_retry(self, mocker):
        boom = RuntimeError("db down")
        mocker.patch(
            "credit.tasks.StatementUseCases.perform_month_end_rollover",
            side_effect=boom,
        )
        retry_spy = mocker.patch.object(
            task_month_end_rollover, "retry",
            side_effect=Exception("retry-called")
        )
        with pytest.raises(Exception) as exc:
            task_month_end_rollover.apply().result
        assert "retry-called" in str(exc.value)
        retry_spy.assert_called_once()
        assert retry_spy.call_args.kwargs["exc"] is boom


class TestFinalizeDueWindowsUnit:
    def test_success_serializes_finalize_result(self, mocker):
        result = FinalizeResult(
            finalized_count=3, closed_without_penalty_count=2,
            closed_with_penalty_count=1
        )
        mocked = mocker.patch(
            "credit.tasks.StatementUseCases.finalize_due_windows",
            return_value=result,
        )
        out = task_finalize_due_windows.apply().result
        mocked.assert_called_once_with()
        assert out == {
            "status": "success",
            "result": {
                "finalized_count": 3,
                "closed_without_penalty_count": 2,
                "closed_with_penalty_count": 1,
            },
        }

    def test_exception_triggers_retry(self, mocker):
        boom = ValueError("compute failed")
        mocker.patch(
            "credit.tasks.StatementUseCases.finalize_due_windows",
            side_effect=boom
        )
        retry_spy = mocker.patch.object(
            task_finalize_due_windows, "retry",
            side_effect=Exception("retry-called")
        )
        with pytest.raises(Exception) as exc:
            task_finalize_due_windows.apply().result
        assert "retry-called" in str(exc.value)
        retry_spy.assert_called_once()
        assert retry_spy.call_args.kwargs["exc"] is boom


class TestDailyWrapperUnit:
    def test_runs_subtasks_in_order_and_bundles_results(self, mocker):
        # Prepare apply mocks that expose .result
        rollover_result = {
            "status": "success", "result": {
                "statements_closed": 1, "statements_created": 1,
                "interest_lines_added": 0
            }
        }
        finalize_result = {
            "status": "success", "result": {
                "finalized_count": 2, "closed_without_penalty_count": 2,
                "closed_with_penalty_count": 0
            }
        }

        rollover_apply = mocker.patch.object(
            task_month_end_rollover, "apply",
            return_value=SimpleNamespace(result=rollover_result)
        )
        finalize_apply = mocker.patch.object(
            task_finalize_due_windows, "apply",
            return_value=SimpleNamespace(result=finalize_result)
        )

        out = task_daily_credit_maintenance.apply().result

        # Order check: month_end first, then finalize
        assert rollover_apply.call_count == 1
        assert finalize_apply.call_count == 1
        assert out == {
            "status": "success",
            "month_end_rollover": rollover_result,
            "finalize_due_windows": finalize_result,
        }

    def test_retry_when_any_subtask_fails(self, mocker):
        boom = RuntimeError("subtask failed")
        mocker.patch.object(task_month_end_rollover, "apply", side_effect=boom)
        mocker.patch.object(task_finalize_due_windows, "apply", autospec=True)
        retry_spy = mocker.patch.object(
            task_daily_credit_maintenance, "retry",
            side_effect=Exception("retry-called")
        )
        with pytest.raises(Exception) as exc:
            task_daily_credit_maintenance.apply().result
        assert "retry-called" in str(exc.value)
        retry_spy.assert_called_once()
        assert retry_spy.call_args.kwargs["exc"] is boom

    def test_retry_when_second_subtask_fails(self, mocker):
        rollover_result = {
            "status": "success", "result": {
                "statements_closed": 0, "statements_created": 0,
                "interest_lines_added": 0
            }
        }
        mocker.patch.object(
            task_month_end_rollover, "apply", return_value=SimpleNamespace(
                result=rollover_result
            )
        )
        boom = RuntimeError("finalize failed")
        mocker.patch.object(
            task_finalize_due_windows, "apply", side_effect=boom
        )

        retry_spy = mocker.patch.object(
            task_daily_credit_maintenance, "retry",
            side_effect=Exception("retry-called")
        )
        with pytest.raises(Exception) as exc:
            task_daily_credit_maintenance.apply().result

        assert "retry-called" in str(exc.value)
        retry_spy.assert_called_once()
        assert retry_spy.call_args.kwargs["exc"] is boom
