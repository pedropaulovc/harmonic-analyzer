@rem Farm entry point: doit schedules locally; every cache-missing part/assembly/
@rem drawing builds on the SolidWorks farm (see build.py --executor farm).
@cd /d "%~dp0" && uv run python build.py --executor farm %*
