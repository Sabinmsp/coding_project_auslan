#!/bin/sh
# Every test, from the project root:   sh tests/run_all.sh [port]
#
#   node tests        planner, keywords, library, timeline, reliability, playback
#   python tests      catalog, keywords, manifest, ownership, validation,
#                     failed extraction, lossless storage (re-runs MediaPipe once)
#   LLM validation    offline, no network
#   browser tests     need the app served on [port] (default 8003) and Chrome;
#                     skipped with a message if nothing is listening
#
# These test the ENGINEERING. They say nothing about whether the signing is
# correct Auslan -- that needs Auslan users.
cd "$(dirname "$0")/.."
PORT=${1:-8003}
NODE=$(command -v node || ls ~/.nvm/versions/node/*/bin/node 2>/dev/null | tail -1)
PY=$(python3 -c "import sys; sys.path.insert(0, '.'); from backend import paths; print(paths.python_with_mediapipe())")
fail=0
run() { echo "== $1"; shift; "$@" || fail=1; }

run "node tests" "$NODE" --test tests/*.mjs
run "library integrity" python3 scripts/check_library.py
run "python tests" "$PY" -m unittest tests/test_pipeline.py
run "LLM validation tests" python3 -m unittest tests/test_llm_plan.py
run "AI summary endpoint (offline)" python3 -m unittest tests/test_summarize_llm.py
if curl -s -o /dev/null "http://localhost:$PORT/"; then
    run "browser: behaviour" python3 tests/browser/test_behaviour.py "$PORT"
    run "browser: robustness" python3 tests/browser/test_robustness.py "$PORT"
    run "browser: controls + end-to-end" python3 tests/browser/test_controls.py "$PORT"
    run "browser: PDF -> key points -> signing" python3 tests/browser/test_document.py "$PORT"
else
    echo "== browser tests SKIPPED: nothing on port $PORT (start: python3 backend/serve.py $PORT)"
fi
find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
[ $fail -eq 0 ] && echo "ALL TEST SUITES PASSED" || echo "SOME TESTS FAILED"
exit $fail
