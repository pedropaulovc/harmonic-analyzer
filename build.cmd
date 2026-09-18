@rem Farm entry point: doit schedules locally; every cache-missing SolidWorks
@rem task -- parts, assemblies, drawings, verify:*, preflight, export and the
@rem release Pack-and-Go -- builds on the farm (see build.py --executor farm).
@cd /d "%~dp0" && uv run python build.py --executor farm %*
