#!/usr/bin/env python3
"""Load-balancing and autoscaling test for the deployed agent stack, narrated step by step.

    python scripts/load_test.py lab-new --dry-run          # show the account, scaling policies and plan; send nothing
    python scripts/load_test.py lab-new --yes              # 5 min of load, then watch it scale back in
    python scripts/load_test.py lab-new --rps 18 --duration 420 --watch-minutes 25 --yes

What it does
  1. Names the AWS account/role/region it acts on (and refuses the wrong account), then lists the autoscaling policies
     (targets and bounds) that will react to the load.
  2. Sends steady GET traffic (default /health, which costs no LLM tokens) through the public API, at --rps.
  3. Every --interval seconds prints one table row: request results (2xx / 429 / 5xx / errors, p50, p95), ECS tasks as
     running/desired/pending, healthy ALB targets, how many distinct tasks answered, and CloudWatch alarms in ALARM.
     Between rows it prints ">>" lines that say in words what just changed in the account (a new task starting, autoscaling
     deciding to scale out, an alarm firing, a task becoming healthy, scale-in...).
  4. After the load stops it keeps watching (--watch-minutes) until the service scales back in.
  5. Prints a summary: peak task count, how long scale-out and scale-in took, which task answered how many requests
     (proof of load balancing), alarms seen, the autoscaling activity log, and a PASS / "----" verdict list.

Why /health scales the service: the stack scales on ALB requests per task per minute (RequestsPerTarget, default 60) and on
CPU. 12 req/s is 720 requests/min on one task, far above 60, so it scales out toward MaxCount. The API Gateway throttle
(ApiThrottleRate, default 20 req/s) caps what gets through; 429s mean it worked. The tasks are ECS Fargate tasks.

Expected timing: scale-out about 3-5 min after load starts (the target-tracking alarm needs 3 one-minute data points, then a
new task needs 1-2 min to start and pass health checks); scale-in only starts after about 15 min of low load plus the 180 s
cooldown, so use --watch-minutes 20 or more to see it. Nothing here is LLM-billed; AWS charges are cents.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awsctx  # noqa: E402
import deploy  # noqa: E402
from awsctx import Aws, stack_resources  # noqa: E402,F401

ALARM_MEANINGS = {
    "autoscaling-scale-out": "load per task is above its target, so autoscaling is about to ADD tasks",
    "autoscaling-scale-in": "load has been low for a long time, so autoscaling is about to REMOVE a task",
    "Alb5xxAlarm": "the load balancer itself returned 5xx (no healthy target, or a timeout)",
    "AlbTarget5xxAlarm": "the agent returned 5xx responses",
    "LatencyAlarm": "p95 response time is above 20 s (API Gateway cuts requests at 30 s)",
    "UnhealthyHostsAlarm": "at least one task is failing its health check",
    "NoHealthyHostsAlarm": "no healthy task is serving traffic (an outage)",
    "CpuHighAlarm": "average CPU is above 85%; autoscaling may be at its maximum",
    "ApiGateway5xxAlarm": "API Gateway returned 5xx (includes the 30 s integration timeout)",
}


# ---------------------------------------------------------------- pure helpers
def percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile; None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def summarize(rows: list[tuple]) -> dict:
    """rows are (timestamp, status_code, latency_seconds, instance)."""
    codes = [r[1] for r in rows]
    latencies = [r[2] for r in rows if 200 <= r[1] < 300]
    return {
        "n": len(rows),
        "ok": sum(1 for c in codes if 200 <= c < 300),
        "throttled": sum(1 for c in codes if c == 429),
        "client_err": sum(1 for c in codes if 400 <= c < 500 and c != 429),
        "server_err": sum(1 for c in codes if c >= 500),
        "net_err": sum(1 for c in codes if c == 0),
        "p50": percentile(latencies, 50),
        "p95": percentile(latencies, 95),
        "p99": percentile(latencies, 99),
        "instances": Counter(r[3] for r in rows if r[3]),
    }


def short_alarm_name(name: str) -> str:
    """'weatherbuddy-container-Alb5xxAlarm-AB12' -> 'Alb5xxAlarm'; target-tracking alarms get a readable label."""
    if "AlarmHigh" in name:
        return "autoscaling-scale-out"
    if "AlarmLow" in name:
        return "autoscaling-scale-in"
    head = name.rsplit("-", 1)[0]
    return head.split("-")[-1] or name


def fmt_seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def verdict(condition: bool, ok: str, bad: str) -> str:
    return f"PASS  {ok}" if condition else f"----  {bad}"


def narrate(elapsed: float, prev: dict, state: dict) -> list[str]:
    """Plain-language lines describing what changed in the account between two snapshots."""
    lines: list[str] = []
    at = f">> {elapsed:>4.0f}s "
    if state["desired"] != prev["desired"]:
        up = state["desired"] > prev["desired"]
        lines.append(f"{at}ECS desired task count {prev['desired']} -> {state['desired']}: autoscaling decided to scale "
                     + ("OUT because load per task is above its target" if up else "IN because load has been low for a long time"))
    if state["pending"] > prev["pending"]:
        lines.append(f"{at}{state['pending']} task(s) are starting (pulling the image and passing health checks takes about 1-2 minutes)")
    if state["running"] != prev["running"]:
        lines.append(f"{at}running tasks {prev['running']} -> {state['running']}"
                     + (": a new task is up" if state["running"] > prev["running"] else ": a task was stopped by scale-in"))
    if state["healthy"] != prev["healthy"]:
        lines.append(f"{at}healthy ALB targets {prev['healthy']} -> {state['healthy']}: the load balancer now spreads traffic over "
                     f"{state['healthy']} task(s)")
    for name in sorted(set(state["alarms"]) - set(prev["alarms"])):
        lines.append(f"{at}ALARM {name}: {ALARM_MEANINGS.get(name, 'see the CloudWatch console')}")
    for name in sorted(set(prev["alarms"]) - set(state["alarms"])):
        lines.append(f"{at}alarm {name} is back to OK")
    return lines


# ---------------------------------------------------------------- traffic
class Recorder:
    def __init__(self):
        self._lock = threading.Lock()
        self._rows: list[tuple] = []

    def add(self, code: int, latency: float, instance: str) -> None:
        with self._lock:
            self._rows.append((time.time(), code, latency, instance))

    def window(self, start: float, end: float) -> list[tuple]:
        with self._lock:
            return [r for r in self._rows if start <= r[0] < end]

    def all(self) -> list[tuple]:
        with self._lock:
            return list(self._rows)


def fire(url: str, recorder: Recorder) -> None:
    started = time.time()
    code, body = 0, ""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "weatherbuddy-load-test"})
        with urllib.request.urlopen(request, timeout=20) as response:
            code, body = response.status, response.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        code = exc.code
    except Exception:  # noqa: BLE001 - timeouts and connection errors count as network errors
        code = 0
    instance = ""
    if code == 200 and body.lstrip().startswith("{"):
        try:
            instance = str(json.loads(body).get("instance", ""))
        except ValueError:
            pass
    recorder.add(code, time.time() - started, instance)


def generate_load(url: str, rps: float, stop: threading.Event, recorder: Recorder) -> None:
    pool = ThreadPoolExecutor(max_workers=max(10, int(rps * 4)))
    interval = 1.0 / rps
    next_at = time.time()
    while not stop.is_set():
        pool.submit(fire, url, recorder)
        next_at += interval
        delay = next_at - time.time()
        if delay > 0:
            stop.wait(delay)
        else:
            next_at = time.time()     # fell behind: do not burst to catch up
    pool.shutdown(wait=False, cancel_futures=True)


# ---------------------------------------------------------------- AWS state
def snapshot(aws: Aws, cluster: str, service: str, target_group: str | None, alarm_prefixes: list[str]) -> dict:
    svc = aws.json("ecs", "describe-services", "--cluster", cluster, "--services", service)["services"][0]
    healthy, total = 0, 0
    if target_group:
        targets = aws.json("elbv2", "describe-target-health", "--target-group-arn", target_group)["TargetHealthDescriptions"]
        total = len(targets)
        healthy = sum(1 for t in targets if t["TargetHealth"]["State"] == "healthy")
    firing: list[str] = []
    for prefix in alarm_prefixes:
        out = aws.json("cloudwatch", "describe-alarms", "--alarm-name-prefix", prefix, "--state-value", "ALARM", check=False)
        firing += [short_alarm_name(a["AlarmName"]) for a in (out or {}).get("MetricAlarms", [])]
    return {"running": svc["runningCount"], "desired": svc["desiredCount"], "pending": svc["pendingCount"],
            "healthy": healthy, "targets": total, "alarms": sorted(set(firing))}


HEADER = (f"{'time':>6} {'phase':<9} {'req/s':>5} {'2xx':>5} {'429':>5} {'5xx':>4} {'err':>4} "
          f"{'p50 s':>6} {'p95 s':>6}  {'tasks r/d/p':<11} {'healthy':<8} {'tasks answering':<15} alarms in ALARM")


def format_row(elapsed: float, phase: str, window_s: float, stats: dict, state: dict) -> str:
    rate = stats["n"] / window_s if window_s > 0 else 0.0
    tasks = f"{state['running']}/{state['desired']}/{state['pending']}"
    healthy = f"{state['healthy']}/{state['targets']}"
    return (f"{elapsed:>5.0f}s {phase:<9} {rate:>5.1f} {stats['ok']:>5} {stats['throttled']:>5} {stats['server_err']:>4} "
            f"{stats['net_err']:>4} {fmt_seconds(stats['p50']):>6} {fmt_seconds(stats['p95']):>6}  {tasks:<11} {healthy:<8} "
            f"{len(stats['instances']):<15} {', '.join(state['alarms']) or '-'}")


def describe_policies(aws: Aws, resource_id: str) -> list[str]:
    """What autoscaling will react to, in words (target-tracking policies of the service)."""
    out = aws.json("application-autoscaling", "describe-scaling-policies", "--service-namespace", "ecs",
                   "--resource-id", resource_id, check=False) or {}
    lines = []
    for p in out.get("ScalingPolicies", []):
        cfg = p.get("TargetTrackingScalingPolicyConfiguration", {})
        metric = (cfg.get("PredefinedMetricSpecification") or {}).get("PredefinedMetricType", "?")
        what = {"ALBRequestCountPerTarget": "ALB requests per task per minute",
                "ECSServiceAverageCPUUtilization": "average CPU %"}.get(metric, metric)
        lines.append(f"policy {p.get('PolicyName', '?').split('-')[-1]}: keeps {what} near {cfg.get('TargetValue', '?')} "
                     f"(scale-out cooldown {cfg.get('ScaleOutCooldown', '?')} s, scale-in cooldown {cfg.get('ScaleInCooldown', '?')} s)")
    return lines


# ---------------------------------------------------------------- main flow
def run(args) -> int:
    cfg, aws, who, envs = awsctx.open_session(args.env, "load balancing and autoscaling test")
    if cfg["stack"] != "agent":
        print("error: this test needs an agent environment (the platform stack has no tasks to scale).", file=sys.stderr)
        return 1
    outputs, params = deploy.stack_info(aws.runner)
    base_url = outputs.get("FrontendApiUrl", "").rstrip("/")
    cluster, service = outputs["ClusterName"], outputs["ServiceName"]
    min_count, max_count = int(params.get("MinCount") or 1), int(params.get("MaxCount") or 3)
    resource_id = f"service/{cluster}/{service}"

    print(f"  target:      {base_url}{args.path}   (API Gateway -> VPC link -> internal ALB -> ECS tasks in this account)")
    print(f"  service:     {cluster}/{service}   autoscaling bounds: min {min_count}, max {max_count}")
    print(f"  load:        {args.rps:g} req/s for {args.duration}s, then watch {args.watch_minutes} min for scale-in")
    print(f"  throttle:    API Gateway allows {params.get('ApiThrottleRate') or 20} req/s (429s above that are expected)")
    print("  expected:    scale-out in ~3-5 min; scale-in only after ~15+ min of low load (+3 min cooldown)")
    for line in describe_policies(aws, resource_id):
        print(f"  {line}")
    if args.dry_run:
        print("\n  dry run: nothing was sent (the lines above were read from the account).")
        return 0
    if (params.get("EnableAutoScaling") or "true") != "true" or min_count >= max_count:
        print(f"\nerror: autoscaling is off or MinCount ({min_count}) >= MaxCount ({max_count}); there is nothing to scale. "
              "Deploy with EnableAutoScaling=true and MaxCount greater than MinCount.", file=sys.stderr)
        return 1
    if not args.yes:
        print("\n  re-run with --yes to start sending traffic.")
        return 0

    resources = stack_resources(aws, cfg["stack_name"])
    target_group = resources.get("TargetGroup", {}).get("PhysicalResourceId")
    prefixes = [cfg["stack_name"], f"TargetTracking-service/{cluster}/{service}"]

    first = snapshot(aws, cluster, service, target_group, prefixes)
    if first["desired"] == 0:
        print("\nerror: the service is stopped (desired count 0). Run: python scripts/deploy.py start " + args.env, file=sys.stderr)
        return 1
    baseline = first["desired"]
    print(f"\n  baseline: {first['running']} running / {first['desired']} desired task(s), {first['healthy']} healthy target(s)\n")
    print(HEADER)

    recorder, stop = Recorder(), threading.Event()
    worker = threading.Thread(target=generate_load, args=(f"{base_url}{args.path}", args.rps, stop, recorder), daemon=True)

    t0 = time.time()
    events: dict[str, float] = {}
    peak_running, peak_desired = first["running"], first["desired"]
    alarms_seen: set[str] = set(first["alarms"])
    load_end = t0 + args.duration
    watch_end = load_end + args.watch_minutes * 60
    window_start, phase, prev = t0, "load", first
    worker.start()

    try:
        while True:
            time.sleep(args.interval)
            now = time.time()
            if phase == "load" and now >= load_end:
                stop.set()
                phase = "cooldown"
                events["load_stopped"] = load_end - t0
                print(f">> {now - t0:>4.0f}s load stopped; now watching how long the service takes to scale back in")
            state = snapshot(aws, cluster, service, target_group, prefixes)
            stats = summarize(recorder.window(window_start, now))
            print(format_row(now - t0, phase, now - window_start, stats, state), flush=True)
            for line in narrate(now - t0, prev, state):
                print(line, flush=True)
            window_start, prev = now, state

            alarms_seen.update(state["alarms"])
            peak_running, peak_desired = max(peak_running, state["running"]), max(peak_desired, state["desired"])
            elapsed = now - t0
            if state["desired"] > baseline and "scale_out_decided" not in events:
                events["scale_out_decided"] = elapsed
            if state["running"] > first["running"] and "scale_out_running" not in events:
                events["scale_out_running"] = elapsed
            if phase == "cooldown" and "scale_in_started" not in events and state["desired"] < peak_desired:
                events["scale_in_started"] = elapsed
            if phase == "cooldown" and state["desired"] <= baseline and state["running"] <= baseline and peak_desired > baseline:
                events["back_to_baseline"] = elapsed
                break
            if phase == "cooldown" and peak_desired <= baseline and now >= load_end + 300:
                print("  no scale-out happened within 5 min after the load stopped; ending early")
                break
            if now >= watch_end:
                break
    except KeyboardInterrupt:
        print("\n  interrupted; summarizing what was collected")
    finally:
        stop.set()

    print_summary(aws, resource_id, recorder, events, baseline, peak_running, peak_desired, max_count, alarms_seen, who)
    return 0


def print_summary(aws: Aws, resource_id: str, recorder: Recorder, events: dict, baseline: int, peak_running: int,
                  peak_desired: int, max_count: int, alarms_seen: set, who: dict) -> None:
    overall = summarize(recorder.all())
    print(f"\n== summary (account {who['account']})")
    print(f"  requests sent: {overall['n']}  ok {overall['ok']}  throttled(429) {overall['throttled']}  "
          f"5xx {overall['server_err']}  network errors {overall['net_err']}  other 4xx {overall['client_err']}")
    print(f"  latency (successful): p50 {fmt_seconds(overall['p50'])}s  p95 {fmt_seconds(overall['p95'])}s  p99 {fmt_seconds(overall['p99'])}s")
    print(f"  peak tasks: {peak_running} running, {peak_desired} desired (baseline {baseline}, max allowed {max_count})")
    for key, label in (("scale_out_decided", "scale-out decided (desired count rose)"), ("scale_out_running", "extra task running"),
                       ("scale_in_started", "scale-in started (desired count fell)"), ("back_to_baseline", "back to baseline")):
        if key in events:
            print(f"  {label}: {events[key]:.0f}s after the test started")
    print(f"  alarms seen in ALARM: {', '.join(sorted(alarms_seen)) or 'none'}")
    for name in sorted(alarms_seen):
        print(f"    {name}: {ALARM_MEANINGS.get(name, 'see the CloudWatch console')}")

    instances = overall["instances"]
    if instances:
        total = sum(instances.values())
        print(f"\n  load balancing: {len(instances)} distinct task(s) answered {total} requests")
        for name, count in instances.most_common():
            print(f"    {name:<44} {count:>6}  {100.0 * count / total:5.1f}%  " + "#" * int(40 * count / total))
    else:
        print("\n  load balancing: no task identity seen (redeploy: /health reports 'instance' only in newer images)")

    activities = aws.json("application-autoscaling", "describe-scaling-activities", "--service-namespace", "ecs",
                          "--resource-id", resource_id, "--max-results", "10", check=False) or {}
    items = activities.get("ScalingActivities", [])
    if items:
        print("\n  autoscaling activity log (newest first):")
        for item in items[:8]:
            print(f"    {str(item.get('StartTime', ''))[:19]}  {item.get('StatusCode', ''):<11} {item.get('Description', '')[:90]}")

    print("\n  verdict:")
    print("   ", verdict(len(instances) >= 2, f"load was spread across {len(instances)} tasks", "only one task answered (never scaled out, or too short)"))
    print("   ", verdict(peak_desired > baseline, f"scaled out from {baseline} to {peak_desired} task(s)", "no scale-out observed (raise --rps/--duration, or check MaxCount)"))
    print("   ", verdict("scale_in_started" in events, "scaled back in after the load stopped",
                         "scale-in not observed yet (it needs ~15-20 min of low load; use a larger --watch-minutes)"))
    print("   ", verdict(overall["server_err"] == 0 and overall["net_err"] == 0, "no 5xx or network errors during the test",
                         f"{overall['server_err']} 5xx / {overall['net_err']} network errors: check the app logs and alarms"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("env", help="agent environment name from infra/environments.json")
    parser.add_argument("--rps", type=float, default=12.0, help="requests per second (default 12; the API throttle is 20)")
    parser.add_argument("--duration", type=int, default=300, help="seconds of load (default 300)")
    parser.add_argument("--watch-minutes", type=int, default=20, help="minutes to keep watching after the load for scale-in (default 20)")
    parser.add_argument("--interval", type=int, default=15, help="seconds between table rows (default 15)")
    parser.add_argument("--path", default="/health", help="path to request (default /health: cheap, no LLM cost)")
    parser.add_argument("--yes", action="store_true", help="actually send traffic")
    parser.add_argument("--dry-run", action="store_true", help="print the plan only")
    args = parser.parse_args(argv)
    if args.rps <= 0 or args.duration <= 0:
        parser.error("--rps and --duration must be positive")
    if not args.path.startswith("/"):
        args.path = "/" + args.path
    try:
        return run(args)
    except deploy.DeployError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
