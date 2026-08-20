from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from homeassistant.core import HomeAssistant


class RoutineRegistry:
    """Carga y gestiona las definiciones de las rutinas."""

    def __init__(
        self,
        hass: HomeAssistant,
        routines_file: Path,
    ) -> None:
        self.hass = hass
        self._routines_file = routines_file
        self._routines: dict[str, dict[str, Any]] = {}

    async def async_load(self) -> None:
        """Carga las rutinas sin bloquear Home Assistant."""

        data = await self.hass.async_add_executor_job(
            self._load_file
        )

        self._validate(data)
        self._routines = data

    def _load_file(self) -> dict[str, Any]:
        """Lee routines.yaml desde disco."""

        if not self._routines_file.exists():
            raise FileNotFoundError(
                f"No existe el archivo de rutinas: {self._routines_file}"
            )

        with self._routines_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = yaml.safe_load(file) or {}

        if not isinstance(data, dict):
            raise ValueError(
                "routines.yaml debe contener un diccionario de rutinas"
            )

        return data

    def _validate(self, routines: dict[str, Any]) -> None:
        """Valida la estructura de las rutinas."""

        for routine_id, routine in routines.items():

            if not isinstance(routine, dict):
                raise ValueError(
                    f"La rutina '{routine_id}' no tiene una definición válida"
                )

            if "name" not in routine:
                raise ValueError(
                    f"La rutina '{routine_id}' no tiene 'name'"
                )

            self._validate_reminders(routine_id, routine)

            steps = routine.get("steps")

            if not isinstance(steps, list) or not steps:
                raise ValueError(
                    f"La rutina '{routine_id}' debe tener al menos un paso"
                )

            for index, step in enumerate(steps, start=1):

                if not isinstance(step, dict):
                    raise ValueError(
                        f"Paso {index} de '{routine_id}' no es válido"
                    )

                if "title" not in step:
                    raise ValueError(
                        f"Paso {index} de '{routine_id}' no tiene 'title'"
                    )

                reminder_text = step.get("reminder_text")

                if (
                    reminder_text is not None
                    and not isinstance(reminder_text, str)
                ):
                    raise ValueError(
                        f"Paso {index} de '{routine_id}' tiene "
                        "'reminder_text' no válido"
                    )

    def _validate_reminders(
        self,
        routine_id: str,
        routine: dict[str, Any],
    ) -> None:
        """Valida la configuración opcional de recordatorios."""

        reminders = routine.get("reminders")

        if reminders is None:
            return

        if not isinstance(reminders, dict):
            raise ValueError(
                f"'reminders' de '{routine_id}' debe ser un diccionario"
            )

        enabled = reminders.get("enabled")

        if not isinstance(enabled, bool):
            raise ValueError(
                f"'reminders.enabled' de '{routine_id}' debe ser booleano"
            )

        required_fields = (
            "first_after",
            "repeat_every",
            "max_reminders",
        )

        if enabled:
            for field in required_fields:
                if field not in reminders:
                    raise ValueError(
                        f"Falta 'reminders.{field}' en '{routine_id}'"
                    )

        for field in ("first_after", "repeat_every"):
            if field not in reminders:
                continue

            value = reminders[field]

            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(
                    f"'reminders.{field}' de '{routine_id}' "
                    "debe ser un número mayor que 0"
                )

        if "max_reminders" in reminders:
            max_reminders = reminders["max_reminders"]

            if (
                isinstance(max_reminders, bool)
                or not isinstance(max_reminders, int)
                or max_reminders <= 0
            ):
                raise ValueError(
                    f"'reminders.max_reminders' de '{routine_id}' "
                    "debe ser un entero mayor que 0"
                )

    def get_routine(
        self,
        routine_id: str,
    ) -> dict[str, Any] | None:
        return self._routines.get(routine_id)

    def get_all(self) -> dict[str, dict[str, Any]]:
        return self._routines

    def get_total_steps(
        self,
        routine_id: str,
    ) -> int:
        routine = self.get_routine(routine_id)

        if routine is None:
            return 0

        return len(routine["steps"])

    def get_reminders(
        self,
        routine_id: str,
    ) -> dict[str, Any] | None:
        routine = self.get_routine(routine_id)

        if routine is None:
            return None

        return routine.get("reminders")

    def get_step(
        self,
        routine_id: str,
        step_number: int,
    ) -> dict[str, Any] | None:
        routine = self.get_routine(routine_id)

        if routine is None:
            return None

        steps = routine["steps"]

        if step_number < 1 or step_number > len(steps):
            return None

        return steps[step_number - 1]
