from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_STATE_CHANGED


ACTIVE_ROUTINE_HELPER = "input_text.kilian_rutina_activa"


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Crea las entidades de las rutinas."""

    data = hass.data[DOMAIN]

    manager = data["manager"]
    registry = data["registry"]

    entities = []

    # ---------------------------------------------------------
    # Sensor individual para cada rutina
    # ---------------------------------------------------------

    for routine_id in registry.get_all():
        entities.append(
            KilianRoutineSensor(
                hass,
                routine_id,
                manager,
                registry,
            )
        )

    # ---------------------------------------------------------
    # Sensor dinámico de la rutina seleccionada
    # ---------------------------------------------------------

    entities.append(
        KilianActiveRoutineSensor(
            hass,
            manager,
            registry,
        )
    )

    async_add_entities(entities, True)


# =============================================================
# SENSOR DE UNA RUTINA
# =============================================================


class KilianRoutineSensor(SensorEntity):
    """Representa el estado de una rutina de Kilian."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        routine_id: str,
        manager,
        registry,
    ) -> None:
        self.hass = hass
        self._routine_id = routine_id
        self._manager = manager
        self._registry = registry

        routine = registry.get_routine(routine_id)

        self._attr_unique_id = f"kilian_routine_{routine_id}"
        self._attr_name = routine["name"]
        self._remove_listener = None

    @property
    def native_value(self) -> str:
        """Estado principal de la entidad."""

        state = self._manager.get_state(self._routine_id)

        if state is None:
            return "unknown"

        if state["completed"]:
            return "completed"

        return "active"

    @property
    def icon(self) -> str | None:
        """Icono configurado para la rutina."""

        routine = self._registry.get_routine(self._routine_id)

        if routine is None:
            return "mdi:format-list-checks"

        return routine.get(
            "icon",
            "mdi:format-list-checks",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Datos que utilizará Lovelace."""

        return _build_routine_attributes(
            self._routine_id,
            self._manager,
            self._registry,
        )

    @callback
    def async_update_from_manager(self) -> None:
        """Actualiza la entidad."""

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Empieza a escuchar cambios del motor."""

        @callback
        def handle_state_changed(event) -> None:

            if event.data.get("routine_id") != self._routine_id:
                return

            self.async_write_ha_state()

        self._remove_listener = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED,
            handle_state_changed,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Elimina el listener."""

        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None


# =============================================================
# SENSOR DE RUTINA ACTIVA
# =============================================================


class KilianActiveRoutineSensor(SensorEntity):
    """Representa dinámicamente la rutina seleccionada."""

    _attr_has_entity_name = True
    _attr_name = "Rutina activa"
    _attr_unique_id = "kilian_active_routine"

    def __init__(
        self,
        hass: HomeAssistant,
        manager,
        registry,
    ) -> None:

        self.hass = hass
        self._manager = manager
        self._registry = registry

        self._remove_routine_listener = None
        self._remove_helper_listener = None

    def _get_active_routine_id(self) -> str | None:
        """Obtiene el ID de la rutina seleccionada."""

        helper = self.hass.states.get(
            ACTIVE_ROUTINE_HELPER
        )

        if helper is None:
            return None

        routine_id = helper.state

        if routine_id in (
            "",
            "unknown",
            "unavailable",
        ):
            return None

        if self._registry.get_routine(routine_id) is None:
            return None

        return routine_id

    @property
    def native_value(self) -> str:
        """Estado de la rutina actualmente seleccionada."""

        routine_id = self._get_active_routine_id()

        if routine_id is None:
            return "unknown"

        state = self._manager.get_state(routine_id)

        if state is None:
            return "unknown"

        if state["completed"]:
            return "completed"

        return "active"

    @property
    def icon(self) -> str | None:
        """Icono de la rutina seleccionada."""

        routine_id = self._get_active_routine_id()

        if routine_id is None:
            return "mdi:format-list-checks"

        routine = self._registry.get_routine(
            routine_id
        )

        if routine is None:
            return "mdi:format-list-checks"

        return routine.get(
            "icon",
            "mdi:format-list-checks",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expone los datos de la rutina seleccionada."""

        routine_id = self._get_active_routine_id()

        if routine_id is None:
            return {}

        return _build_routine_attributes(
            routine_id,
            self._manager,
            self._registry,
        )

    async def async_added_to_hass(self) -> None:
        """Escucha cambios de rutina y del selector."""

        # -----------------------------------------------------
        # Cambios producidos por Kilian Routines
        # -----------------------------------------------------

        @callback
        def handle_routine_changed(event) -> None:

            active_routine_id = (
                self._get_active_routine_id()
            )

            if active_routine_id is None:
                return

            if (
                event.data.get("routine_id")
                != active_routine_id
            ):
                return

            self.async_write_ha_state()

        self._remove_routine_listener = (
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                handle_routine_changed,
            )
        )

        # -----------------------------------------------------
        # Cambio de input_text.kilian_rutina_activa
        # -----------------------------------------------------

        @callback
        def handle_helper_changed(event) -> None:

            if (
                event.data.get("entity_id")
                != ACTIVE_ROUTINE_HELPER
            ):
                return

            self.async_write_ha_state()

        self._remove_helper_listener = (
            self.hass.bus.async_listen(
                "state_changed",
                handle_helper_changed,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Elimina los listeners."""

        if self._remove_routine_listener is not None:
            self._remove_routine_listener()
            self._remove_routine_listener = None

        if self._remove_helper_listener is not None:
            self._remove_helper_listener()
            self._remove_helper_listener = None


# =============================================================
# ATRIBUTOS COMUNES
# =============================================================


def _build_routine_attributes(
    routine_id: str,
    manager,
    registry,
) -> dict[str, Any]:
    """Construye los atributos comunes de cualquier rutina."""

    routine = registry.get_routine(routine_id)
    state = manager.get_state(routine_id)

    if routine is None or state is None:
        return {}

    step_number = state["step"]
    total_steps = state["total_steps"]

    step = registry.get_step(
        routine_id,
        step_number,
    )

    if step is None:
        step = {}

    if total_steps > 0:
        progress = round(
            step_number / total_steps * 100
        )
    else:
        progress = 0

    rewards = routine.get("rewards", {})
    completion = routine.get("completion", {})

    return {
        "routine_id": routine_id,

        # Datos generales
        "routine_name": routine.get(
            "name",
            routine_id,
        ),

        "icon": routine.get(
            "icon",
            "mdi:format-list-checks",
        ),

        "color": routine.get(
            "color",
            "",
        ),

        # Estado
        "step": step_number,
        "total_steps": total_steps,
        "completed": state["completed"],
        "progress": progress,

        # Paso actual
        "step_title": step.get(
            "title",
            "",
        ),

        "step_text": step.get(
            "text",
            "",
        ),

        "step_emoji": step.get(
            "emoji",
            "",
        ),

        # Pantalla final
        "completion_title": completion.get(
            "title",
            "COMPLETADO",
        ),

        "completion_text": completion.get(
            "text",
            "¡Buen trabajo!",
        ),

        "completion_emoji": completion.get(
            "emoji",
            "🎉",
        ),

        # Recompensas
        "reward_between_steps": rewards.get(
            "between_steps",
            "none",
        ),

        "reward_completion": rewards.get(
            "completion",
            "none",
        ),
    }