"""Whitelisted teaching calculations; bounded subprocess timeout, no device control."""

from pathlib import Path
import hashlib, json, math, subprocess, sys, time

UNITS = {
    "kWh": ("energy", 1),
    "Wh": ("energy", 0.001),
    "kW": ("power", 1),
    "W": ("power", 0.001),
    "m3": ("volume", 1),
    "L": ("volume", 0.001),
    "kg/m3": ("density", 1),
    "kJ/(kg K)": ("heat_capacity", 1),
    "K": ("difference", 1),
    "degC": ("difference", 1),
    "1": ("ratio", 1),
}
SCHEMAS = {
    "energy_runtime": {
        "energy": "energy",
        "power": "power",
        "soc": "ratio",
        "soc_min": "ratio",
        "eta": "ratio",
    },
    "water_sensible_heat": {
        "volume": "volume",
        "density": "density",
        "cp": "heat_capacity",
        "delta_t": "difference",
    },
}


def quantity(v, dimension):
    if not isinstance(v, dict) or set(v) != {"value", "unit"}:
        raise ValueError("quantity_schema")
    x = v["value"]
    unit = v["unit"]
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError("finite_number")
    if not isinstance(unit, str) or unit not in UNITS or UNITS[unit][0] != dimension:
        raise ValueError("unit_dimension")
    return x * UNITS[unit][1]


def normalize(request):
    if set(request) != {"request_id", "tool", "arguments"}:
        raise ValueError("request_schema")
    if not isinstance(request["request_id"], str) or not request["request_id"]:
        raise ValueError("request_id")
    name = request["tool"]
    args = request["arguments"]
    if name not in SCHEMAS:
        raise ValueError("tool_allowlist")
    if not isinstance(args, dict) or set(args) != set(SCHEMAS[name]):
        raise ValueError("argument_schema")
    p = {k: quantity(args[k], dim) for k, dim in SCHEMAS[name].items()}
    if name == "energy_runtime":
        if not (
            p["energy"] > 0
            and p["power"] > 0
            and 0 <= p["soc_min"] <= p["soc"] <= 1
            and 0 < p["eta"] <= 1
        ):
            raise ValueError("physical_range")
    elif any(v <= 0 for v in p.values()):
        raise ValueError("physical_range")
    return {"tool": name, "arguments": p}


def compute(normalized):
    p = normalized["arguments"]
    if normalized["tool"] == "energy_runtime":
        return {
            "value": p["energy"] * (p["soc"] - p["soc_min"]) * p["eta"] / p["power"],
            "unit": "h",
        }
    return {
        "value": p["volume"] * p["density"] * p["cp"] * p["delta_t"] / 3600,
        "unit": "kWh",
    }


def execute(request, fault="none"):
    log = []
    try:
        params = normalize(request)
    except (ValueError, TypeError, KeyError) as e:
        return {
            "status": "invalid_request",
            "reason": str(e),
            "attempts": log,
            "result": None,
        }
    expected = compute(params)
    encoded = json.dumps(params, sort_keys=True, allow_nan=False)
    h = hashlib.sha256(encoded.encode()).hexdigest()
    for attempt in (1, 2):
        timeout_case = fault == "timeout_twice" or (
            fault == "timeout_once" and attempt == 1
        )
        t = time.perf_counter()
        try:
            r = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker"],
                input=json.dumps(
                    {"params": params, "delay": 0.35 if timeout_case else 0}
                ),
                capture_output=True,
                text=True,
                timeout=0.1 if timeout_case else 5,
                check=True,
            )
            result = json.loads(r.stdout)
            if fault == "wrong_unit":
                result["unit"] = "kW"
            if fault == "wrong_value":
                result["value"] *= 10
            if fault == "extra_action":
                result["action"] = "set_soc"
            if fault == "malformed":
                result = {"value": "bad", "unit": expected["unit"]}
            good = (
                set(result) == {"value", "unit"}
                and type(result["value"]) in (int, float)
                and math.isfinite(result["value"])
                and result["unit"] == expected["unit"]
                and math.isclose(
                    result["value"], expected["value"], rel_tol=1e-10, abs_tol=1e-10
                )
            )
            log.append(
                {
                    "attempt": attempt,
                    "event": "validated" if good else "invalid_result",
                    "elapsed_s": time.perf_counter() - t,
                    "parameter_sha256": h,
                }
            )
            return {
                "status": "ok" if good else "invalid_result",
                "attempts": log,
                "result": result if good else None,
            }
        except subprocess.TimeoutExpired:
            log.append(
                {
                    "attempt": attempt,
                    "event": "timeout",
                    "elapsed_s": time.perf_counter() - t,
                    "parameter_sha256": h,
                }
            )
        except (ValueError, subprocess.CalledProcessError) as e:
            log.append(
                {
                    "attempt": attempt,
                    "event": "worker_error",
                    "elapsed_s": time.perf_counter() - t,
                    "parameter_sha256": h,
                }
            )
            return {"status": "worker_error", "attempts": log, "result": None}
    return {"status": "timeout", "attempts": log, "result": None}


def example_request(tool="energy_runtime"):
    p = (
        {
            "energy": (1000, "kWh"),
            "power": (300, "kW"),
            "soc": (0.8, "1"),
            "soc_min": (0.2, "1"),
            "eta": (0.95, "1"),
        }
        if tool == "energy_runtime"
        else {
            "volume": (20, "m3"),
            "density": (1000, "kg/m3"),
            "cp": (4.18, "kJ/(kg K)"),
            "delta_t": (6, "K"),
        }
    )
    return {
        "request_id": "lesson-09",
        "tool": tool,
        "arguments": {k: {"value": v, "unit": u} for k, (v, u) in p.items()},
    }


if __name__ == "__main__" and "--worker" in sys.argv:
    payload = json.load(sys.stdin)
    time.sleep(payload["delay"])
    print(json.dumps(compute(payload["params"]), allow_nan=False))
