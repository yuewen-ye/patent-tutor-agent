"""Download embedding and reranker models from ModelScope (fast in China)."""

import os
import shutil
from modelscope import snapshot_download

MODELS = {
    "bge-m3": "Xorbits/bge-m3",
    "bge-reranker-v2-m3": "ai-modelscope/bge-reranker-v2-m3",
}

HF_CACHE_NAMES = {
    "bge-m3": "models--BAAI--bge-m3",
    "bge-reranker-v2-m3": "models--BAAI--bge-reranker-v2-m3",
}

ENV_KEYS = {
    "bge-m3": "RAG_EMBEDDING_MODEL_PATH",
    "bge-reranker-v2-m3": "RAG_RERANKER_MODEL_PATH",
}


def cleanup_hf_cache():
    hub_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    for name, cache_name in HF_CACHE_NAMES.items():
        cache_path = os.path.join(hub_dir, cache_name)
        if os.path.exists(cache_path):
            print(f"removing HF cache for {name}...")
            shutil.rmtree(cache_path)
            print(f"removed: {cache_path}")


def update_env(base):
    env_path = os.path.join(base, ".env")
    rel_paths = {
        "bge-m3": "./models/bge-m3",
        "bge-reranker-v2-m3": "./models/bge-reranker-v2-m3",
    }
    if not os.path.exists(env_path):
        print(f"warning: .env not found at {env_path}, skip auto config")
        return
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    updated = set()
    new_lines = []
    for line in lines:
        stripped = line.lstrip("#").strip()
        for model_name, key in ENV_KEYS.items():
            if stripped.startswith(key + "="):
                line = f"{key}={rel_paths[model_name]}\n"
                updated.add(model_name)
        new_lines.append(line)
    for model_name, key in ENV_KEYS.items():
        if model_name not in updated:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{key}={rel_paths[model_name]}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f".env updated: model paths configured")


if __name__ == "__main__":
    base = os.path.join(os.path.dirname(__file__), "..", "..")
    base = os.path.abspath(base)
    models_dir = os.path.join(base, "models")
    os.makedirs(models_dir, exist_ok=True)

    for name, repo in MODELS.items():
        target = os.path.join(models_dir, name)
        print(f"downloading {name} from ModelScope...")
        snapshot_download(repo, local_dir=target)
        print(f"done: {target}")

    cleanup_hf_cache()
    update_env(base)
    print("\nall done! models downloaded, HF cache cleaned, .env configured.")
