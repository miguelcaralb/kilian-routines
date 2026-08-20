from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import EVENT_ROUTINE_REMINDER


@dataclass
class ReminderSession:
    """Estado efímero de los recordatorios de un paso."""

    routine_id: str
    step: int
    generation: int
    max_reminders: int
    repeat_seconds: float
    reminder_count: int = 0
    timer_generation: int = 0
    cancel_timer: Callable[[], None] | None = None
    invalidated: bool = False


class RoutineReminderScheduler:
    """Programa recordatorios sin gestionar el avance de las rutinas."""

    def __init__(self, hass: HomeAssistant, manager, registry) -> None:
        self._hass = hass
        self._manager = manager
        self._registry = registry
        self._sessions: dict[str, ReminderSession] = {}
        self._generations: dict[str, int] = {}

    def start(self, routine_id: str) -> None:
        """Inicia desde cero los recordatorios del paso actual."""

        self.cancel(routine_id)

        config = self._registry.get_reminders(routine_id)
        state = self._manager.get_state(routine_id)

        if not config or not config.get("enabled"):
            return

        if state is None or state["completed"]:
            return

        generation = self._generations[routine_id]
        session = ReminderSession(
            routine_id=routine_id,
            step=state["step"],
            generation=generation,
            max_reminders=config["max_reminders"],
            repeat_seconds=config["repeat_every"] * 60,
        )
        self._sessions[routine_id] = session
        self._schedule(session, config["first_after"] * 60)

    def cancel(self, routine_id: str) -> None:
        """Cancela e invalida la sesión actual de una rutina."""

        self._generations[routine_id] = (
            self._generations.get(routine_id, 0) + 1
        )
        session = self._sessions.pop(routine_id, None)

        if session is None:
            return

        session.invalidated = True

        if session.cancel_timer is not None:
            session.cancel_timer()
            session.cancel_timer = None

    def cancel_all(self) -> None:
        """Cancela todas las sesiones activas."""

        for routine_id in list(self._sessions):
            self.cancel(routine_id)

    def _schedule(
        self,
        session: ReminderSession,
        delay_seconds: float,
    ) -> None:
        """Programa el siguiente callback de una sesión."""

        session.timer_generation += 1
        timer_generation = session.timer_generation

        @callback
        def handle_timer(_now) -> None:
            if session.timer_generation != timer_generation:
                return

            session.cancel_timer = None
            self._handle_session(session)

        session.cancel_timer = async_call_later(
            self._hass,
            delay_seconds,
            handle_timer,
        )

    def _handle_session(self, session: ReminderSession) -> None:
        current_session = self._sessions.get(session.routine_id)

        if current_session is not session:
            return

        if session.invalidated:
            return

        if self._generations.get(session.routine_id) != session.generation:
            return

        state = self._manager.get_state(session.routine_id)

        if state is None or state["completed"]:
            self.cancel(session.routine_id)
            return

        if state["step"] != session.step:
            self.cancel(session.routine_id)
            return

        if session.reminder_count >= session.max_reminders:
            self.cancel(session.routine_id)
            return

        routine = self._registry.get_routine(session.routine_id)
        step = self._registry.get_step(session.routine_id, session.step)

        if routine is None or step is None:
            self.cancel(session.routine_id)
            return

        session.reminder_count += 1
        self._hass.bus.async_fire(
            EVENT_ROUTINE_REMINDER,
            {
                "routine_id": session.routine_id,
                "routine_name": routine["name"],
                "step": session.step,
                "total_steps": state["total_steps"],
                "step_title": step.get("title", ""),
                "step_text": step.get("text", ""),
                "message": self._build_message(step),
                "reminder_number": session.reminder_count,
            },
        )

        if session.reminder_count >= session.max_reminders:
            self.cancel(session.routine_id)
            return

        self._schedule(session, session.repeat_seconds)

    @staticmethod
    def _build_message(step: dict) -> str:
        reminder_text = step.get("reminder_text")

        if isinstance(reminder_text, str) and reminder_text.strip():
            return reminder_text.strip()

        step_text = step.get("text")

        if isinstance(step_text, str) and step_text.strip():
            return f"Kilian, recuerda: {step_text.strip()}"

        title = step.get("title", "")
        return f"Kilian, recuerda completar: {title}"
