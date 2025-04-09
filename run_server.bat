@echo off
cd /d %~dp0
set PYTHONPATH=%CD%
python server\tests\test_api\test_temperature_endpoints.py
pause 