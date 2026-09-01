"""Lightweight connectivity test for all providers in config/agents.yaml.

Sends a single 1-token request per provider (max_tokens=1) to verify
endpoint + API key + model reachability. Minimal token cost.
"""
import sys
import os
from pathlib import Path

# ── locate project root so this script runs from anywhere ──
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[3]  # evaluation/program -> evaluation -> tests -> backend -> root
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# ── load .env ──
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("AGENT_CONFIG_PATH", str(PROJECT_ROOT / "config" / "agents.yaml"))

import yaml
import httpx

AGENTS_YAML = PROJECT_ROOT / "config" / "agents.yaml"
TIMEOUT = 15

def main():
    with open(AGENTS_YAML, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    providers = cfg.get("providers", {})
    api_key = os.environ.get("SHKG_API_KEY", "")

    print(f"SHKG_API_KEY: {api_key[:8]}...{api_key[-4:]}")
    print(f"Endpoint base: {list(providers.values())[0].get('base_url', '?')}")
    print(f"{'Provider':<16} {'Model':<22} {'Status':<8} {'Latency':<10} {'Detail'}")
    print("-" * 90)

    all_ok = True
    for name, p in providers.items():
        base_url = p.get("base_url", "").rstrip("/")
        model = p.get("model_name", "")
        url = f"{base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
            "stream": False,
        }

        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=TIMEOUT)
            t = resp.elapsed.total_seconds()
            if resp.status_code == 200:
                rj = resp.json()
                finish = rj.get("choices", [{}])[0].get("finish_reason", "?")
                print(f"{name:<16} {model:<22} {'✅ OK':<8} {t*1000:>7.0f}ms  {finish}")
            else:
                all_ok = False
                err = ""
                try:
                    err = resp.json().get("error", {}).get("message", resp.text[:80])
                except Exception:
                    err = resp.text[:80]
                print(f"{name:<16} {model:<22} {'❌ FAIL':<8} {t*1000:>7.0f}ms  HTTP {resp.status_code} {err}")
        except httpx.ConnectError as e:
            all_ok = False
            print(f"{name:<16} {model:<22} {'❌ CONN':<8} {'--':>7}  {e}")
        except Exception as e:
            all_ok = False
            print(f"{name:<16} {model:<22} {'❌ ERR':<8} {'--':>7}  {type(e).__name__}: {e}")

    print("-" * 90)
    print(f"Result: {'✅ ALL PASS' if all_ok else '❌ SOME FAILED'}")

    # ── agents → provider 映射摘要 ──
    print("\nAgent → Provider 映射:")
    print(f"{'Agent':<22} {'Provider':<16} {'Model':<22} {'Temp':<6}")
    print("-" * 70)
    for agent_name, a in cfg.get("agents", {}).items():
        prov = a.get("provider", "?")
        prov_cfg = providers.get(prov, {})
        model = prov_cfg.get("model_name", "?")
        temp = a.get("temperature", "?")
        print(f"{agent_name:<22} {prov:<16} {model:<22} {temp:<6}")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
