"""Run validation with individual deadlines and captured diagnostic output."""
import os,subprocess,sys,time,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
LOGS=ROOT/'build_logs';LOGS.mkdir(exist_ok=True)
TESTS=['web_snapshot_test.py','web_dashboard_ui_test.py','web_dashboard_test.py','integrity_line_endings_test.py','no_count_reply_ui_test.py','no_count_reply_recovery_test.py','production_forecast_test.py','dashboard_performance_test.py','live_totals_test.py','management_reports_test.py','weekday_dashboard_test.py','tyre_weight_test.py','preview_performance_test.py','startup_support_test.py','celebration_shuffle_test.py','compare_builds_test.py','celebration_audio_test.py','database_upgrade_test.py','line_span_test.py','adjustable_bounds_test.py','video_preview_integration_test.py','onscreen_preview_test.py','video_test_ui_test.py','zigzag_test.py','three_line_test.py','production_schedule_test.py','schedule_metrics_test.py','production_ui_test.py','celebration_test.py','logic_test_isolation_test.py','no_count_replies_test.py','oak_foreign_worker_test.py','oak_integrity_test.py','oak_rvc2_test.py','oak_fov_test.py','oak_recording_test.py','gui_render_test.py','dashboard_async_test.py','oak_ai_test.py','oak_stream_test.py','oak_worker_test.py','tyretrack_report_sync_test.py','foreign_alarm_test.py']
for test in TESTS:
    print(f'\n=== START {test} ===',flush=True)
    start=time.monotonic()
    try:
        proc=subprocess.run([sys.executable,'-u',str(ROOT/test)],cwd=ROOT,
             stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',
             timeout=90,env={**os.environ,'PYTHONUNBUFFERED':'1','QT_QPA_PLATFORM':'offscreen'})
    except subprocess.TimeoutExpired as exc:
        output=exc.stdout or b''
        if isinstance(output,bytes):output=output.decode('utf-8','replace')
        (LOGS/(test+'.log')).write_text(output+'\nTIMEOUT after 90 seconds\n',encoding='utf-8')
        print(output[-12000:],flush=True)
        print(f'FAIL: {test} timed out after 90 seconds. Diagnostic log uploaded.',flush=True)
        sys.exit(124)
    (LOGS/(test+'.log')).write_text(proc.stdout,encoding='utf-8')
    print(proc.stdout[-12000:],flush=True)
    print(f'=== END {test}: exit={proc.returncode}, elapsed={time.monotonic()-start:.1f}s ===',flush=True)
    if proc.returncode:sys.exit(proc.returncode)
print('PASS: all source regression tests',flush=True)
