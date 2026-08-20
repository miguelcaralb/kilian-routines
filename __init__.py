from __future__ import annotations

from pathlib import Path

import voluptuous as vol
import logging

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .manager import KilianRoutineManager
from .registry import RoutineRegistry
from homeassistant.helpers import discovery

_LOGGER = logging.getLogger(__name__)

SERVICE_COMPLETE_STEP = "complete_step"
SERVICE_RESET_ROUTINE = "reset_routine"
SERVICE_FINISH_STEP = "finish_step"

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

    # Registrar automáticamente todas las rutinas definidas
    for routine_id in registry.get_all():
        await manager.async_register_routine(
            routine_id,
            registry.get_total_steps(routine_id),
        )

    hass.data[DOMAIN] = {
        "manager": manager,
        "registry": registry,
    }

    # ---------------------------------------------------------
    # Acción: completar paso
    # ---------------------------------------------------------

    async def handle_complete_step(call: ServiceCall) -> None:
        routine_id = call.data[ATTR_ROUTINE_ID]

        if registry.get_routine(routine_id) is None:
            raise ValueError(
                f"Rutina desconocida: {routine_id}"
            )

        await manager.async_complete_step(routine_id)

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

        await manager.async_reset(routine_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_ROUTINE,
        handle_reset_routine,
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
    