"""Reproduce the report's ablations without changing production code or incident tapes."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameday_lab.client import ResilientClient
from gameday_lab.factory import build_client
from gameday_lab.sim.config import load_config
from gameday_lab.sim.engine import run_scenario


class UnfilteredClient(ResilientClient):
    """Deliberately unsafe control used only for the compatibility experiment."""

    def ladder(self, task: str) -> list[str]:
        return list(self.order)


def main() -> None:
    cfg = load_config()
    results = {}
    for budget in (True, False):
        settings = deepcopy(cfg.client)
        settings["breaker"]["min_calls"] = 1_000_000_000
        settings["max_attempts_per_provider"] = 5
        if not budget:
            settings.update(retry_budget_ratio=100, retry_budget_max_tokens=1e9,
                            retry_budget_min_per_s=1e6)
        control = replace(cfg, client=settings)
        for tape in ("G2_overload_storm", "G3_brownout"):
            key = f"budget_{'on' if budget else 'off'}_{tape}"
            results[key] = run_scenario(control, tape, build_client("resilient", control), 25).metrics()
    settings = deepcopy(cfg.client)
    settings["attempt_timeout_s"] = 30
    control = replace(cfg, client=settings)
    for tape in ("G6_provider_outage", "G4_slow_region"):
        results[f"timeout_30_{tape}"] = run_scenario(
            control, tape, build_client("resilient", control), 25).metrics()
    unsafe = UnfilteredClient(cfg.provider_infos(), cfg.fallback_order, cfg.client, seed=1)
    results["unfiltered_G6"] = run_scenario(cfg, "G6_provider_outage", unsafe, 25).metrics()
    cfg = load_config(scenarios_path="configs/scenarios_cache.yaml")
    for name, parameter, values in (
        ("similarity", "similarity_threshold", (0.80, 0.90, 0.97)),
        ("ttl", "ttl_s", (30, 60, 300)),
        ("stale", "max_stale_s", (0, 300)),
    ):
        for value in values:
            control = replace(cfg, cache={**cfg.cache, parameter: value})
            results[f"cache_{name}_{value}"] = run_scenario(
                control, "C1_faq_outage", build_client("cached", control), 25).metrics()
    out = Path("reports/experiments.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for key, metrics in results.items():
        fields = ("availability", "latency_p95_s", "amplification", "retry_ratio", "recovery_s",
                  "give_up_reasons", "incompatible_routes", "faq_availability", "cache_hit_ratio",
                  "wrong_answers", "wrong_answers_by_reason", "outdated_answers", "cost_per_good_turn")
        print(key, {field: metrics[field] for field in fields if field in metrics})


if __name__ == "__main__":
    main()
