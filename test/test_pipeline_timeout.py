"""
Self-check for the subprocess-isolation + timeout pattern in app.py's
_run_job (see _pipeline_worker). Exercises the exact same
start/join(timeout)/terminate/kill mechanism against toy workers instead of
the real (heavy) InsightFace pipeline, so it runs without those deps.

Run: python test/test_pipeline_timeout.py
"""
import multiprocessing as mp
import time


def run_with_timeout(target, args, timeout_sec):
    """Mirrors _run_job's subprocess-timeout block in app.py."""
    ctx = mp.get_context("fork")
    out_queue = ctx.Queue()
    proc = ctx.Process(target=target, args=(*args, out_queue), daemon=True)
    proc.start()
    proc.join(timeout_sec)

    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        if proc.is_alive():
            proc.kill()
            proc.join()
        return ("timeout", None)
    if out_queue.empty():
        return ("crashed", proc.exitcode)
    return out_queue.get()


def _worker_ok(out_queue):
    out_queue.put(("ok", ["fake decision"], {"frames_processed": 3}))


def _worker_hangs(out_queue):
    while True:
        time.sleep(1)


def _worker_errors(out_queue):
    out_queue.put(("error", "ValueError: bad video", None))


if __name__ == "__main__":
    t0 = time.time()
    kind, payload = run_with_timeout(_worker_ok, (), timeout_sec=5)[:2]
    assert kind == "ok" and payload == ["fake decision"], "normal completion should return its result"
    assert time.time() - t0 < 2, "a fast worker must not wait for the full timeout"

    t0 = time.time()
    result = run_with_timeout(_worker_hangs, (), timeout_sec=2)
    elapsed = time.time() - t0
    assert result[0] == "timeout", f"a hung worker must be reported as timed out, got {result!r}"
    assert elapsed < 10, f"terminate()/kill() must bound total wait time, took {elapsed:.1f}s"

    kind, payload = run_with_timeout(_worker_errors, (), timeout_sec=5)[:2]
    assert kind == "error" and "bad video" in payload, "a worker-reported error must surface, not hang"

    print("OK: normal completion, hang-timeout, and worker-error all behave correctly.")
