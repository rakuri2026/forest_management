@echo off
echo Moving unnecessary files to dumping_files...
echo.

REM Test files
move test_*.py dumping_files\ 2>nul
move test_*.txt dumping_files\ 2>nul
move test_*.csv dumping_files\ 2>nul
move test_*.json dumping_files\ 2>nul

REM Error logs
move error*.txt dumping_files\ 2>nul

REM Old batch files (keeping only active ones)
move cleanup_old_batch_files.bat dumping_files\ 2>nul
move diagnose_upload.bat dumping_files\ 2>nul
move FIX_INVENTORY_UPLOAD.bat dumping_files\ 2>nul
move FORCE_RESTART.bat dumping_files\ 2>nul
move FORCE_RESTART_BACKEND.bat dumping_files\ 2>nul
move KILL_AND_RESTART.bat dumping_files\ 2>nul
move RESTART_BACKEND.bat dumping_files\ 2>nul
move RESTART_BACKEND_NOW.bat dumping_files\ 2>nul
move START_FRESH.bat dumping_files\ 2>nul
move start_backend.bat dumping_files\ 2>nul
move start_frontend.bat dumping_files\ 2>nul
move stop_all.bat dumping_files\ 2>nul

REM Temporary tokens
move token.json dumping_files\ 2>nul
move token2.json dumping_files\ 2>nul
move "D:forest_managementtoken.json" dumping_files\ 2>nul

REM Old Python scripts
move add_geology_access_features_ui.py dumping_files\ 2>nul
move add_location_detection.py dumping_files\ 2>nul
move add_location_ui.py dumping_files\ 2>nul
move check_db.py dumping_files\ 2>nul
move check_routes.py dumping_files\ 2>nul
move create_simple_user.py dumping_files\ 2>nul
move fix_password.py dumping_files\ 2>nul
move inventoryCalculation.py dumping_files\ 2>nul
move reset_newuser_password.py dumping_files\ 2>nul
move reset_password.py dumping_files\ 2>nul

REM Temporary exports and results
move exported_inventory.csv dumping_files\ 2>nul
move girth_result.json dumping_files\ 2>nul
move mother_trees_test_*.csv dumping_files\ 2>nul
move testyfy_result.json dumping_files\ 2>nul
move typo_result.json dumping_files\ 2>nul
move upload_debug_result.json dumping_files\ 2>nul
move upload_result.json dumping_files\ 2>nul
move validation_result.json dumping_files\ 2>nul

REM Text files (temporary)
move analysis.txt dumping_files\ 2>nul
move forest_management_conversession.txt dumping_files\ 2>nul
move frontend_inventory_updates.txt dumping_files\ 2>nul
move project_structure.txt dumping_files\ 2>nul
move species.txt dumping_files\ 2>nul
move DEBUG_PROMPT_FOR_AI.txt dumping_files\ 2>nul
move PROBLEM_SUMMARY_FOR_AI.txt dumping_files\ 2>nul
move START_HERE_AFTER_RESTART.txt dumping_files\ 2>nul
move ROLLBACK_INSTRUCTIONS.txt dumping_files\ 2>nul

REM Old documentation (keeping main ones)
move ABBREVIATED_CODES_GUIDE.md dumping_files\ 2>nul
move AUTO_UTM_FIX.md dumping_files\ 2>nul
move BACKUP_SUCCESS.md dumping_files\ 2>nul
move BATCH_FILES_GUIDE.md dumping_files\ 2>nul
move BAT_FILES_README.md dumping_files\ 2>nul
move FIELDBOOK_SAMPLING_FIXES.md dumping_files\ 2>nul
move FINAL_SOLUTION.md dumping_files\ 2>nul
move FIX_UPLOAD_ISSUE.md dumping_files\ 2>nul
move FRONTEND_INVENTORY_COMPLETE.md dumping_files\ 2>nul
move FRONTEND_INVENTORY_WORKFLOW.md dumping_files\ 2>nul
move INTEGRATION_STATUS_UPDATE.md dumping_files\ 2>nul
move INVENTORY_DATA_QUALITY_ISSUES.md dumping_files\ 2>nul
move INVENTORY_DATA_VALIDATION_GUIDE.md dumping_files\ 2>nul
move INVENTORY_FIX_SUMMARY.md dumping_files\ 2>nul
move INVENTORY_INTEGRATION_PROGRESS.md dumping_files\ 2>nul
move INVENTORY_VALIDATION_TECHNICAL_SPEC.md dumping_files\ 2>nul
move LOGIN_FIX_SUMMARY.md dumping_files\ 2>nul
move MILESTONE_SESSION_SUMMARY.md dumping_files\ 2>nul
move MOTHER_TREE_IDENTIFICATION.md dumping_files\ 2>nul
move PHASE_2A_COMPLETE.md dumping_files\ 2>nul
move PHASE_2A_IMPLEMENTATION_STATUS.md dumping_files\ 2>nul
move SUGGESTIONS_COMPARISON.md dumping_files\ 2>nul
move TEMPLATE_UPDATE_SUMMARY.md dumping_files\ 2>nul
move TESTING_GUIDE.md dumping_files\ 2>nul
move TESTING_SPECIES_MATCHER.md dumping_files\ 2>nul
move TEST_RESULTS.md dumping_files\ 2>nul
move TRANSACTION_FIX_APPLIED.md dumping_files\ 2>nul
move SPECIES_MATCHER_GUIDE.md dumping_files\ 2>nul

echo.
echo Done! Files moved to dumping_files folder.
pause
