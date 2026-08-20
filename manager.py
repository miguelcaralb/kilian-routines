from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


class KilianRoutineManager:

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

        self._store = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
        )

        self._states: dict[str, dict] = {}

    async def async_load(self) -> None:
        """Carga los estados guardados."""

        data = await self._store.async_load()

        if data is None:
            self._states = {}
            return

        self._states = data.get("states", {})

    async def async_save(self) -> None:
        """Guarda todos los estados."""

        await self._store.async_save({
            "states": self._states
        })

    async def async_register_routine(
        self,
        routine_id: str,
        total_steps: int,
    ) -> None:
        """Registra una rutina si todavía no existe."""

        if routine_id in self._states:
            return

        self._states[routine_id] = {
            "step": 1,
            "total_steps": total_steps,
            "completed": False,
        }

        await self.async_save()

    def get_state(self, routine_id: str) -> dict | None:
        """Devuelve el estado de una rutina."""

        return self._states.get(routine_id)

    def get_all_states(self) -> dict[str, dict]:
        """Devuelve el estado de todas las rutinas."""

        return self._states

    async def async_complete_step(
        self,
        routine_id: str,
    ) -> dict | None:
        """Completa el paso actual."""

        state = self._states.get(routine_id)

        if state is None:
            return None

        if state["completed"]:
            return state

        if state["step"] >= state["total_steps"]:
            state["completed"] = True
        else:
            state["step"] += 1

        await self.async_save()
        
        self.hass.bus.async_fire(
            "kilian_routines_state_changed",
            {
                "routine_id": routine_id
            },
        )

        return state

    async def async_reset(
        self,
        routine_id: str,
    ) -> dict | None:
        """Reinicia una rutina."""

        state = self._states.get(routine_id)

        if state is None:
            return None

        state["step"] = 1
        state["completed"] = False

        await self.async_save()
        self.hass.bus.async_fire(
            "kilian_routines_state_changed",
            {
                "routine_id": routine_id
            },
        )
        return state