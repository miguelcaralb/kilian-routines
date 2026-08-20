from __future__ import annotations

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

                if "text" not in step:
                    raise ValueError(
                        f"Paso {index} de '{routine_id}' no tiene 'text'"
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