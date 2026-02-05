@echo off
echo ========================================
echo Diagnosing Upload Issue
echo ========================================
echo.

cd backend

echo Checking required packages...
..\venv\Scripts\python -c "import pandas; print('✓ pandas installed')" 2>nul || echo ✗ pandas MISSING
..\venv\Scripts\python -c "import io; print('✓ io module OK')" 2>nul || echo ✗ io module MISSING
..\venv\Scripts\python -c "from app.services.inventory_validator import InventoryValidator; print('✓ InventoryValidator imported')" 2>nul || echo ✗ InventoryValidator import FAILED
..\venv\Scripts\python -c "from app.services.inventory import InventoryService; print('✓ InventoryService imported')" 2>nul || echo ✗ InventoryService import FAILED
..\venv\Scripts\python -c "from app.models.inventory import InventoryCalculation; print('✓ Models imported')" 2>nul || echo ✗ Models import FAILED

echo.
echo Checking API endpoint registration...
..\venv\Scripts\python -c "from app.main import app; routes = [r.path for r in app.routes if '/inventory' in r.path]; print(f'Found {len(routes)} inventory routes:'); [print(f'  - {r}') for r in routes]"

echo.
echo Checking backend server...
curl -s http://localhost:8001/health

echo.
echo ========================================
pause
