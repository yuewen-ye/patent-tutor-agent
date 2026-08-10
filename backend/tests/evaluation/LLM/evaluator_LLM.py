"""外部 LLM 评估器。

使用独立的外部 LLM 对评估产物进行评价，生成 JSON 格式的评估报告。

用法:
  # 评估指定画像的指定轮次
  uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --profile B --round 1

  # 评估指定画像的所有轮次
  uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --profile B --all-rounds

  # 批量评估所有画像的指定轮次
  uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --all-profiles --round 1

  # 重新评估（覆盖已有结果）
  uv run python backend/tests/evaluation/LLM/evaluator_LLM.py evaluate --profile B --round 1 --force

  # 查看可用画像
  uv run python backend/tests/evaluation/LLM/evaluator_LLM.py list-profiles
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ── 路径设置 ─────────────────────────────────────────────────────────────────

_THIS_DIR = Path(__file__).resolve().parent
_EVAL_DIR = _THIS_DIR.parent  # backend/tests/evaluation
_PROJECT_ROOT = _EVAL_DIR.parents[1]

for _p in (_THIS_DIR, _EVAL_DIR, _PROJECT_ROOT):
    _ps = str(_p)
    if _ps not in sys.path:
        sys.path.insert(0, _ps)

# ── 依赖导入 ──────────────────────────────────────────────────────────────────

try:
    import yaml
except ImportError:
    print("❌ 缺少依赖: pyyaml。请运行: uv add pyyaml")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ 缺少依赖: requests。请运行: uv add requests")
    sys.exit(1)

from dotenv import load_dotenv

ENV_PATH = _PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)


# ── 配置加载 ──────────────────────────────────────────────────────────────────

def load_config() -> dict[str, Any]:
    """加载外部 LLM 配置文件。"""
    config_path = _THIS_DIR / "config" / "external_llm.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 解析环境变量
    llm_config = config.get("llm", {})
    api_key = llm_config.get("api_key", "")
    if not api_key:
        api_key = os.getenv("EXTERNAL_LLM_API_KEY", "")
    if not api_key:
        print("⚠️  警告: 未配置 API Key，请在配置文件或环境变量 EXTERNAL_LLM_API_KEY 中设置")

    # 设置默认 base_url
    provider = llm_config.get("provider", "deepseek")
    if not llm_config.get("base_url"):
        default_urls = {
            "deepseek": "https://api.deepseek.com",
            "qwen": "https://dashscope.aliyuncs.com",
            "glm": "https://open.bigmodel.cn",
        }
        llm_config["base_url"] = default_urls.get(provider, "")

    llm_config["api_key"] = api_key
    config["llm"] = llm_config

    return config


# ── LLM 客户端 ────────────────────────────────────────────────────────────────

class LLMClient:
    """简单的 LLM API 客户端。"""

    def __init__(self, config: dict[str, Any]):
        self.base_url = config["base_url"].rstrip("/")
        self.api_key = config["api_key"]
        self.model = config["model"]
        self.temperature = config.get("temperature", 0.0)
        self.max_tokens = config.get("max_tokens", 4096)
        self.timeout = config.get("timeout", 120)
        self.retry = config.get("retry", 2)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """调用 LLM 对话接口。"""
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(self.retry + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

                # 提取 assistant 消息
                choices = data.get("choices", [])
                if choices:
                    return choices[0]["message"]["content"]
                raise ValueError("LLM 返回格式异常：无 choices")

            except requests.exceptions.Timeout as e:
                last_error = e
                if attempt < self.retry:
                    print(f"    ⏳ 超时，重试 {attempt + 1}/{self.retry}...")
                    time.sleep(2 ** attempt)

            except requests.exceptions.HTTPError as e:
                last_error = e
                status_code = e.response.status_code
                error_text = e.response.text[:200] if e.response.text else ""

                if status_code == 429:  # Rate limit
                    if attempt < self.retry:
                        print(f"    ⏳ 速率限制(429)，重试 {attempt + 1}/{self.retry}...")
                        time.sleep(2 ** attempt)
                elif status_code >= 500:
                    if attempt < self.retry:
                        print(f"    ⏳ 服务器错误({status_code})，重试 {attempt + 1}/{self.retry}...")
                        time.sleep(2 ** attempt)
                else:
                    # 非重试错误，直接显示
                    print(f"    ❌ HTTP 错误 {status_code}: {error_text}")
                    break

            except Exception as e:
                last_error = e
                print(f"    ❌ 异常: {type(e).__name__}: {str(e)[:200]}")
                break

        # 显示最终错误摘要
        if last_error:
            print(f"    ⚠️  LLM 调用最终失败: {type(last_error).__name__}")
            print(f"       URL: {url}")
            print(f"       模型: {self.model}")

        return self._generate_fallback_response(str(last_error))

    def _generate_fallback_response(self, error_msg: str) -> str:
        """生成降级响应（当 LLM 调用失败时）。"""
        return json.dumps({
            "scores": {
                "goal_coverage": {"score": 0, "max": 5, "comment": f"LLM 调用失败: {error_msg}", "matched_goals": [], "missed_goals": []},
                "factual_accuracy": {"score": 0, "max": 5, "comment": f"LLM 调用失败: {error_msg}", "correct_items": [], "errors": []},
                "case_accuracy": {"score": 0, "max": 5, "comment": f"LLM 调用失败: {error_msg}", "reliable_cases": [], "problematic_cases": []},
                "factual_consistency": {"score": 0, "max": 5, "comment": f"LLM 调用失败: {error_msg}", "consistent_points": [], "contradictions": []},
                "pedagogical_clarity": {"score": 0, "max": 5, "comment": f"LLM 调用失败: {error_msg}", "clear_points": [], "confusing_points": []},
                "difficulty_fit": {"score": 0, "max": 5, "comment": f"LLM 调用失败: {error_msg}", "matched_items": [], "mismatched_items": []},
                "learner_fit": {"score": 0, "max": 5, "comment": f"LLM 调用失败: {error_msg}", "adapted_points": [], "missing_adaptations": []},
                "knowledge_completeness": {"score": 0, "max": 5, "comment": f"LLM 调用失败: {error_msg}", "covered_points": [], "missing_points": []},
                "weakness_addressing": {"score": 0, "max": 5, "comment": f"LLM 调用失败: {error_msg}", "addressed_weaknesses": [], "untouched_weaknesses": []},
            },
            "overall_score": {"score": 0, "max": 100, "comment": f"LLM 调用失败: {error_msg}", "summary": "评估失败"},
            "highlights": [],
            "issues": [f"LLM 调用失败: {error_msg}"],
            "suggestions": [],
        }, ensure_ascii=False)


# ── 产物管理 ──────────────────────────────────────────────────────────────────

def get_artifacts_dir() -> Path:
    """获取评估产物目录。"""
    config = load_config()
    artifacts_dir = config.get("inputs", {}).get("artifacts_dir", "backend/tests/evaluation/artifacts")
    path = _PROJECT_ROOT / artifacts_dir
    return path


def get_profile_dir(profile_id: str) -> Path:
    """获取画像的产物目录。"""
    artifacts_dir = get_artifacts_dir()
    return artifacts_dir / f"multi-{profile_id}"


def get_round_dir(profile_id: str, round_num: int) -> Path:
    """获取轮次的产物目录。"""
    profile_dir = get_profile_dir(profile_id)
    # 优先 round-NN 格式，兼容 round_NN
    round_dir = profile_dir / f"round-{round_num:02d}"
    if not round_dir.exists():
        round_dir = profile_dir / f"round_{round_num:02d}"
    return round_dir


def read_file(path: Path) -> str | None:
    """读取文件内容。"""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def list_profiles() -> list[str]:
    """列出所有可用画像。"""
    artifacts_dir = get_artifacts_dir()
    if not artifacts_dir.exists():
        return []

    profiles = []
    for d in sorted(artifacts_dir.iterdir()):
        if d.is_dir() and d.name.startswith("multi-"):
            letter = d.name.replace("multi-", "")
            profiles.append(letter)
    return profiles


def list_rounds(profile_id: str) -> list[int]:
    """列出画像的所有可用轮次。"""
    profile_dir = get_profile_dir(profile_id)
    if not profile_dir.exists():
        return []

    rounds = []
    for d in profile_dir.iterdir():
        if d.is_dir():
            name = d.name
            # round-NN 或 round_NN
            m = re.match(r"round[-_](\d+)", name)
            if m:
                rounds.append(int(m.group(1)))
    return sorted(rounds)


def read_artifacts(profile_id: str, round_num: int) -> dict[str, str]:
    """读取指定画像指定轮次的所有产物。"""
    round_dir = get_round_dir(profile_id, round_num)
    if not round_dir.exists():
        raise FileNotFoundError(f"轮次目录不存在: {round_dir}")

    artifacts = {}
    required_files = ["course_package.md", "learning_path.md"]

    for filename in required_files:
        filepath = round_dir / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            artifacts[filename] = content
        else:
            print(f"  ⚠️  缺少文件: {filename}")
            artifacts[filename] = ""

    return artifacts


# ── 分块逻辑 ──────────────────────────────────────────────────────────────────

def split_by_sections(text: str) -> list[dict[str, Any]]:
    """按 ## 标题分块。"""
    chunks = []

    # 匹配所有 ## 标题
    pattern = r"(?:^|\n)(## .+?)(?=\n## |\Z)"
    matches = list(re.finditer(pattern, text, re.MULTILINE | re.DOTALL))

    if not matches:
        # 没有 ## 标题，作为一个整体
        chunks.append({
            "index": 0,
            "title": "完整内容",
            "content": text,
            "token_count": len(text) // 4,  # 粗略估算
        })
        return chunks

    for i, match in enumerate(matches):
        content = match.group(0).strip()
        # 提取标题
        title_match = re.match(r"## (.+)", match.group(1))
        title = title_match.group(1).strip() if title_match else f"分块 {i + 1}"

        chunks.append({
            "index": i,
            "title": title,
            "content": content,
            "token_count": len(content) // 4,  # 粗略估算
        })

    return chunks


def auto_select_eval_mode(text: str, config: dict[str, Any]) -> str:
    """自动选择评估模式。"""
    chunking_config = config.get("chunking", {})
    threshold = chunking_config.get("auto_whole_threshold", 4000)
    token_count = len(text) // 4  # 粗略估算

    if token_count < threshold:
        return "whole"
    return "chunked"


# ── Prompt 构造 ───────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    """加载系统提示词。"""
    prompt_path = _THIS_DIR / "prompts" / "evaluator_system.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"系统提示词文件不存在: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def build_chunk_prompt(
    chunk: dict[str, Any],
    learning_path: str,
    chunk_index: int,
    total_chunks: int,
) -> str:
    """构造分块评估的用户提示词。"""
    return f"""
## 当前任务

你正在评估一个专利教学课程的**分块内容**。

## 分块信息
- 序号：{chunk_index + 1} / {total_chunks}
- 标题：{chunk['title']}

## 学习路径（评估标准）
{learning_path}

## 待评估内容
{chunk['content']}

## 注意
- 请仅评估此分块涉及的学习目标，不需要评估整个学习路径
- 如果此分块不涉及某个评估维度，请给出该维度的满分并注明"本分块不涉及此维度"
- 请严格按照 JSON 格式输出评估结果
"""


def build_whole_prompt(
    course_content: str,
    learning_path: str,
) -> str:
    """构造整体评估的用户提示词。"""
    return f"""
## 当前任务

你正在评估一个专利教学课程的**完整内容**。

## 学习路径（评估标准）
{learning_path}

## 待评估内容（完整课程）
{course_content}

## 注意
- 请综合评估整个课程，不要仅看单个分块
- 重点关注课程的整体连贯性、完整性和实用性
- 请严格按照 JSON 格式输出评估结果
"""


# ── 评估流程 ──────────────────────────────────────────────────────────────────

def evaluate_profile_round(
    profile_id: str,
    round_num: int,
    config: dict[str, Any],
    force: bool = False,
) -> dict[str, Any] | None:
    """评估指定画像的指定轮次。"""
    llm_config = config.get("llm", {})
    output_config = config.get("output", {})

    # 1. 检查输出文件
    model_name = llm_config.get("model", "unknown")
    output_name = output_config.get("naming", "judge_{model}_{profile}_{round:02d}.json")
    output_name = output_name.format(
        model=model_name,
        profile=profile_id,
        round=round_num,
    )
    output_dir = _PROJECT_ROOT / output_config.get("dir", "backend/tests/evaluation/LLM/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name

    if output_path.exists() and not force:
        print(f"  ⏭️  跳过：{output_name} 已存在")
        return None

    # 2. 读取产物
    print(f"  📖 读取产物...")
    artifacts = read_artifacts(profile_id, round_num)
    course_content = artifacts.get("course_package.md", "")
    learning_path = artifacts.get("learning_path.md", "")

    if not course_content:
        print(f"  ❌ course_package.md 为空，跳过")
        return None

    # 3. 初始化 LLM 客户端
    llm_client = LLMClient(llm_config)
    system_prompt = load_system_prompt()

    # 4. 选择评估模式
    eval_mode = auto_select_eval_mode(course_content, config)
    print(f"  📏 评估模式: {eval_mode}")

    result: dict[str, Any] = {
        "metadata": {
            "profile_id": profile_id,
            "round": round_num,
            "evaluator": "external_llm",
            "model": model_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "eval_mode": eval_mode,
        },
    }

    if eval_mode == "whole":
        # 整体评估
        print(f"  🔍 整体评估...")
        user_prompt = build_whole_prompt(course_content, learning_path)
        llm_response = llm_client.chat(system_prompt, user_prompt)
        parsed = parse_llm_response(llm_response)
        result["overall_evaluation"] = parsed
        result["chunk_evaluations"] = []

    else:
        # 分块评估
        chunks = split_by_sections(course_content)
        print(f"  🔍 分块评估: {len(chunks)} 个分块")

        chunk_results = []
        for i, chunk in enumerate(chunks):
            print(f"    📄 块 {i + 1}/{len(chunks)}: {chunk['title']}")
            user_prompt = build_chunk_prompt(
                chunk, learning_path, i, len(chunks)
            )
            llm_response = llm_client.chat(system_prompt, user_prompt)
            parsed = parse_llm_response(llm_response)
            chunk_results.append({
                "chunk_index": i,
                "chunk_title": chunk["title"],
                "token_count": chunk["token_count"],
                "evaluation": parsed,
            })

        result["chunk_evaluations"] = chunk_results

        # 整体评估（基于分块摘要）
        print(f"  🔍 整体评估（基于分块结果）...")
        summary_text = generate_summary_from_chunks(chunk_results)
        user_prompt = build_whole_prompt(
            f"## 分块摘要\n{summary_text}",
            learning_path,
        )
        llm_response = llm_client.chat(system_prompt, user_prompt)
        parsed = parse_llm_response(llm_response)
        result["overall_evaluation"] = parsed

    # 5. 保存结果
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 评估完成: {output_name}")
    return result


def parse_llm_response(response: str) -> dict[str, Any]:
    """解析 LLM 返回的 JSON 响应。"""
    try:
        # 尝试直接解析
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 块
    pattern = r"```json\s*(.*?)\s*```"
    json_match = re.search(pattern, response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试直接找第一个 { 到最后一个 }
    start = response.find("{")
    end = response.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(response[start:end + 1])
        except json.JSONDecodeError:
            pass

    # 解析失败，返回原始文本
    return {
        "parse_error": True,
        "raw_response": response,
        "scores": {},
        "overall_score": {"score": 0, "max": 100, "comment": "JSON 解析失败", "summary": ""},
        "highlights": [],
        "issues": ["JSON 解析失败"],
        "suggestions": [],
    }


def generate_summary_from_chunks(chunk_results: list[dict[str, Any]]) -> str:
    """从分块结果生成摘要文本。"""
    lines = []
    for chunk in chunk_results:
        title = chunk.get("chunk_title", f"分块 {chunk['chunk_index']}")
        eval_data = chunk.get("evaluation", {})
        scores = eval_data.get("scores", {})

        lines.append(f"### {title}")
        for dim_name, dim_data in scores.items():
            score = dim_data.get("score", 0)
            max_score = dim_data.get("max", 5)
            comment = dim_data.get("comment", "")
            lines.append(f"- {dim_name}: {score}/{max_score} - {comment[:100]}")
        lines.append("")

    return "\n".join(lines)


# ── 主入口 ────────────────────────────────────────────────────────────────────

def cmd_list_profiles() -> None:
    """列出所有可用画像。"""
    profiles = list_profiles()
    if not profiles:
        print("❌ 未找到任何画像")
        return

    print(f"\n可用画像 ({len(profiles)} 个):")
    for p in profiles:
        rounds = list_rounds(p)
        rounds_str = ", ".join(f"R{r:02d}" for r in rounds) or "无"
        print(f"  multi-{p}: {rounds_str}")


def cmd_evaluate(args) -> None:
    """执行评估。"""
    config = load_config()
    profiles_config = config.get("llm", {})
    model = profiles_config.get("model", "unknown")

    # 确定要评估的画像
    if args.all_profiles:
        profiles = list_profiles()
    elif args.profile:
        profiles = [args.profile]
    else:
        print("❌ 请指定 --profile 或 --all-profiles")
        return

    if not profiles:
        print("❌ 未找到任何画像")
        return

    # 确定要评估的轮次
    if args.all_rounds:
        rounds_set: set[int] = set()
        for p in profiles:
            rounds_set.update(list_rounds(p))
        rounds = sorted(rounds_set)
    elif args.round is not None:
        rounds = [args.round]
    else:
        print("❌ 请指定 --round 或 --all-rounds")
        return

    if not rounds:
        print("❌ 未找到任何轮次")
        return

    print(f"\n{'='*60}")
    print(f"外部 LLM 评估器")
    print(f"{'='*60}")
    print(f"  模型: {model}")
    print(f"  画像: {len(profiles)} 个")
    print(f"  轮次: {rounds}")
    print(f"  强制重跑: {args.force}")
    print(f"{'='*60}\n")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for profile_id in profiles:
        available_rounds = set(list_rounds(profile_id))
        for round_num in rounds:
            if round_num not in available_rounds:
                print(f"\n📋 multi-{profile_id} R{round_num:02d}: 产物不存在，跳过")
                skip_count += 1
                continue

            print(f"\n📋 评估 multi-{profile_id} R{round_num:02d}...")
            try:
                result = evaluate_profile_round(
                    profile_id, round_num, config, force=args.force
                )
                if result is None:
                    skip_count += 1
                else:
                    success_count += 1
            except Exception as e:
                print(f"  ❌ 异常: {type(e).__name__}: {e}")
                fail_count += 1

    print(f"\n{'='*60}")
    print(f"评估完成")
    print(f"{'='*60}")
    print(f"  ✅ 成功: {success_count}")
    print(f"  ⏭️  跳过: {skip_count}")
    print(f"  ❌ 失败: {fail_count}")
    print(f"{'='*60}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="外部 LLM 评估器 - 使用独立 LLM 对评估产物进行评价",
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list-profiles 命令
    subparsers.add_parser("list-profiles", help="列出所有可用画像")

    # evaluate 命令
    eval_parser = subparsers.add_parser("evaluate", help="执行评估")
    eval_parser.add_argument("--profile", help="指定画像字母（如 B）")
    eval_parser.add_argument("--all-profiles", action="store_true", help="评估所有画像")
    eval_parser.add_argument("--round", type=int, help="指定轮次（如 1）")
    eval_parser.add_argument("--all-rounds", action="store_true", help="评估所有轮次")
    eval_parser.add_argument("--force", action="store_true", help="强制重跑（覆盖已有结果）")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "list-profiles":
        cmd_list_profiles()
    elif args.command == "evaluate":
        cmd_evaluate(args)


if __name__ == "__main__":
    main()
