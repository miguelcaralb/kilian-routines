from __future__ import annotations

from pathlib import Path

import voluptuous as vol
import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, EVENT_ROUTINE_STARTED
from .manager import KilianRoutineManager
from .reminders import RoutineReminderScheduler
from .registry import RoutineRegistry
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

SERVICE_COMPLETE_STEP = "complete_step"
SERVICE_RESET_ROUTINE = "reset_routine"
SERVICE_FINISH_STEP = "finish_step"
SERVICE_START_ROUTINE = "start_routine"

ATTR_ROUTINE_ID = "routine_id"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Configura Kilian Routines."""

    routines_file = Path(__file__).parent / "routines.yaml"

    # Cargar definiciones
    registry = RoutineRegistry(hass, routines_file)
    await registry.async_load()

    # Cargar estados persistentes
    manager = KilianRoutineManager(hass)
    await manager.async_load()

    reminder_scheduler = RoutineReminderScheduler(
        hass,
        manager,
        registry,
    )

    # Registrar automáticamente todas las rutinas definidas
    for routine_id in registry.get_all():
        await manager.async_register_routine(
            routine_id,
            registry.get_total_steps(routine_id),
        )

    hass.data[DOMAIN] = {
        "manager": manager,
        "registry": registry,
        "reminder_scheduler": reminder_scheduler,
    }

    @callback
    def handle_hass_stop(_event) -> None:
        reminder_scheduler.cancel_all()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP,
        handle_hass_stop,
    )

    # ---------------------------------------------------------
    # Acción: completar paso
    # ---------------------------------------------------------

    async def handle_complete_step(call: ServiceCall) -> None:
        routine_id = call.data[ATTR_ROUTINE_ID]

        if registry.get_routine(routine_id) is None:
            raise ValueError(
                f"Rutina desconocida: {routine_id}"
            )

        reminder_scheduler.cancel(routine_id)
        state = await manager.async_complete_step(routine_id)

        if state is not None and not state["completed"]:
            reminder_scheduler.start(routine_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPLETE_STEP,
        handle_complete_step,
        schema=vol.Schema({
            vol.Required(ATTR_ROUTINE_ID): cv.string,
        }),
    )

    # ---------------------------------------------------------
    # Acción: reiniciar rutina
    # ---------------------------------------------------------

    async def handle_reset_routine(call: ServiceCall) -> None:
        routine_id = call.data[ATTR_ROUTINE_ID]

        if registry.get_routine(routine_id) is None:
            raise ValueError(
                f"Rutina desconocida: {routine_id}"
            )

        reminder_scheduler.cancel(routine_id)
        await manager.async_reset(routine_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_ROUTINE,
        handle_reset_routine,
        schema=vol.Schema({
            vol.Required(ATTR_ROUTINE_ID): cv.string,
        }),
    )

    # ---------------------------------------------------------
    # Acción: iniciar o reanudar una rutina
    # ---------------------------------------------------------

    async def handle_start_routine(call: ServiceCall) -> None:
        routine_id = call.data[ATTR_ROUTINE_ID]
        routine = registry.get_routine(routine_id)
        state = manager.get_state(routine_id)

        if routine is None:
            raise ValueError(f"Rutina desconocida: {routine_id}")

        if state is None:
            raise ValueError(f"No existe estado para: {routine_id}")

        hass.bus.async_fire(
            EVENT_ROUTINE_STARTED,
            {
                "routine_id": routine_id,
                "routine_name": routine["name"],
                "step": state["step"],
                "total_steps": state["total_steps"],
                "completed": state["completed"],
            },
        )

        reminder_scheduler.start(routine_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_ROUTINE,
        handle_start_routine,
        schema=vol.Schema({
            vol.Required(ATTR_ROUTINE_ID): cv.string,
        }),
    )

    # Cargar la plataforma de sensores de las rutinas
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            "sensor",
            DOMAIN,
            {},
            config,
        )
    )
        # ---------------------------------------------------------
    # Acción: terminar paso
    # ---------------------------------------------------------

    async def handle_finish_step(call: ServiceCall) -> None:
        routine_id = call.data[ATTR_ROUTINE_ID]
        _LOGGER.warning(
            "FINISH_STEP recibido para rutina: %s",
            routine_id,
        )

        routine = registry.get_routine(routine_id)
        state = manager.get_state(routine_id)

        if routine is None:
            raise ValueError(f"Rutina desconocida: {routine_id}")

        if state is None:
            raise ValueError(f"No existe estado para: {routine_id}")

        if state["completed"]:
            return

        reminder_scheduler.cancel(routine_id)

        rewards = routine.get("rewards", {})

        is_last_step = state["step"] >= state["total_steps"]

        if is_last_step:
            reward_type = rewards.get("completion", "none")
        else:
            reward_type = rewards.get("between_steps", "none")

        _LOGGER.warning(
            "Solicitando recompensa: rutina=%s tipo=%s paso=%s ultimo=%s",
            routine_id,
            reward_type,
            state["step"],
            is_last_step,
        )
        # De momento solo generamos un evento.
        # En el siguiente paso conectaremos aquí los vídeos.
        hass.bus.async_fire(
            "kilian_routines_reward_requested",
            {
                "routine_id": routine_id,
                "reward_type": reward_type,
                "step": state["step"],
                "last_step": is_last_step,
            },
        )

        # IMPORTANTE:
        # Todavía NO avanzamos el paso.
        # El avance ocurrirá cuando termine la recompensa.

    hass.services.async_register(
        DOMAIN,
        SERVICE_FINISH_STEP,
        handle_finish_step,
        schema=vol.Schema({
            vol.Required(ATTR_ROUTINE_ID): cv.string,
        }),
    )
    return True
    
