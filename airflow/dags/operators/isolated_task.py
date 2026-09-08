from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from airflow.decorators.base import task_decorator_factory
from airflow.decorators.external_python import _PythonExternalDecoratedOperator

if TYPE_CHECKING:
    from airflow.decorators.base import TaskDecorator

ETL_PYTHON = os.environ.get("ETL_PYTHON", "/opt/venvs/etl/bin/python")


class _IsolatedTaskOperator(_PythonExternalDecoratedOperator):
    custom_operator_name = "@isolated_task"


def isolated_task(python_callable: Callable | None = None, **kwargs) -> TaskDecorator:
    kwargs.setdefault("python", ETL_PYTHON)
    kwargs.setdefault("expect_airflow", False)

    return task_decorator_factory(
        python_callable=python_callable,
        multiple_outputs=kwargs.pop("multiple_outputs", None),
        decorated_operator_class=_IsolatedTaskOperator,
        **kwargs,
    )
