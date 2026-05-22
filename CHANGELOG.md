# CHANGELOG

## Version 0.4.0

- Auth: cache session token, only re-authorize on 401 (no more cleartext credentials every 5 minutes)
- Config flow: prevent adding the same Jablotron account twice (`async_set_unique_id` on device serial)
- Entities: scope `unique_id` by device serial; existing entity registry rows auto-migrate
- Entities: use `_attr_has_entity_name = True` for friendly display names

## Version 0.3.2

- Security: enable TLS certificate verification on the Jablotron cloud API session (removed `verify_ssl=False`)


## Version 0.3.1

- Fix missing switches (bypass, cooling, heating, radon_protection)


## Version 0.3.0

- Added comprehensive README documentation
- Fixed crash caused by missing switch platform
- Modernized code to follow current Home Assistant patterns
- Improved API error handling with proper HA exception types
- Used EntityDescription dataclasses for sensor and binary sensor entities
- Switched to ConfigEntry.runtime_data for coordinator storage
- Added proper type annotations throughout

## Version 0.2.2

- fix version string in manifest.json

## Version 0.2.1

- fix config entries initialization

## Version 0.2.0

- added to HACS

## Version 0.1.1

- updated api calls

## Version 0.1.0

- fixed setting native values in number component
- removed deprecated calls and imports