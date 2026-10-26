"""Диагностика без учётных данных и идентификаторов печи."""
async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    return {
        'device_count': len(entry.data['binding_ids']),
        'allow_control': entry.options.get('allow_control', False),
        'last_update_success': coordinator.last_update_success,
        'online_count': sum(s.online for s in (coordinator.data or {}).values()),
    }
