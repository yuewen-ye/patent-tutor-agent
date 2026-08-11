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
_PROJECT_ROOT = _EVAL_DIR.parents[2]  # 项目根目录

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

def load_system_prompt(mode: str = "overall") -> str:
    """加载系统提示词。
    
    Args:
        mode: 评估模式，"overall" 或 "statement"
    """
    if mode == "statement":
        prompt_path = _THIS_DIR / "prompts" / "statement_evaluator.md"
    else:
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
    mode: str = "overall",
) -> dict[str, Any] | None:
    """评估指定画像的指定轮次。
    
    Args:
        mode: 评估模式
            - "overall": 整体评估（默认），按 ## 分块评估后汇总
            - "statement": M1/M9 陈述级评估，抽取可核验陈述后逐条判定
    """
    llm_config = config.get("llm", {})
    output_config = config.get("output", {})

    # statement 模式使用独立的 M1/M9 评估函数
    if mode == "statement":
        return evaluate_m1_m9(profile_id, round_num, config, force=force)

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
    
    # 确定评估模式
    eval_mode = getattr(args, "mode", "overall")

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

    mode_label = {
        "overall": "整体评估",
        "statement": "M1/M9 陈述级评估",
        "m7": "M7 资源形态评估",
        "m8": "M8 异议闭环率评估",
    }.get(eval_mode, eval_mode)
    print(f"\n{'='*60}")
    print(f"外部 LLM 评估器 ({mode_label})")
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
                if eval_mode == "statement":
                    # M1/M9 陈述级评估
                    result = evaluate_m1_m9(
                        profile_id, round_num, config, force=args.force
                    )
                elif eval_mode == "m7":
                    # M7 资源形态评估
                    result = evaluate_m7_resource_morphology(
                        profile_id, round_num, config, force=args.force
                    )
                elif eval_mode == "m8":
                    # M8 异议闭环率评估
                    result = evaluate_m8_objection_loop(
                        profile_id, round_num, config, force=args.force
                    )
                else:
                    # 整体评估
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


# ── M1/M9 专用接口 ──────────────────────────────────────────────────────────────

def extract_verifiable_statements(course_text: str) -> list[dict[str, Any]]:
    """从 course_package.md 中抽取可核验陈述。
    
    返回格式：
    [
        {
            "text": "专利法第 42 条规定...",
            "source_type": "legal_basis" | "time_limit" | "procedure",
            "has_source": True,
            "source_file": "中华人民共和国专利法.txt",
            "context": "法条号 42",
        },
        ...
    ]
    """
    statements = []
    
    # 1. legal_basis 中的法条引用
    # 匹配 ## legal_basis 章节下的表格内容
    legal_section = re.search(
        r"## legal_basis\s*([\s\S]*?)(?=\n##|\Z)",
        course_text
    )
    if legal_section:
        legal_text = legal_section.group(1)
        # 匹配 article 和 source 字段
        for m in re.finditer(
            r"article[:：]\s*(\d+).*?source[:：]\s*([^\n|]+)",
            legal_text
        ):
            statements.append({
                "text": m.group(0).strip(),
                "source_type": "legal_basis",
                "has_source": True,
                "source_file": m.group(2).strip(),
                "context": f"法条号 {m.group(1)}",
            })
        # 也匹配表格行中的法条引用
        for line in legal_text.splitlines():
            if "|" in line and "---" not in line:
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2 and not cells[0].startswith("法条"):
                    # 可能是表格行
                    for cell in cells:
                        article_match = re.search(r"第\s*(\d+)\s*条", cell)
                        source_match = re.search(r"source[:：]\s*(\S+)", line)
                        if article_match:
                            statements.append({
                                "text": line.strip(),
                                "source_type": "legal_basis",
                                "has_source": bool(source_match),
                                "source_file": source_match.group(1) if source_match else "",
                                "context": f"法条号 {article_match.group(1)}",
                            })
    
    # 2. 教学正文中的期限断言（如"6个月"、"12个月"）
    for m in re.finditer(
        r"(\d+)\s*(?:个月|天|日|年).*?(?:内|前|后|期限)",
        course_text
    ):
        statements.append({
            "text": m.group(0).strip(),
            "source_type": "time_limit",
            "has_source": False,
            "source_file": "",
            "context": "期限断言",
        })
    
    # 3. risks 中的程序规则
    risks_section = re.search(
        r"## risks\s*([\s\S]*?)(?=\n##|\Z)",
        course_text
    )
    if risks_section:
        for line in risks_section.group(1).splitlines():
            if line.strip() and not line.startswith("#") and not line.startswith("|"):
                # 只提取非表格、非标题的规则陈述
                if len(line.strip()) > 5:  # 过滤太短的行
                    statements.append({
                        "text": line.strip(),
                        "source_type": "procedure",
                        "has_source": False,
                        "source_file": "",
                        "context": "风险/程序规则",
                    })
    
    # 去重
    seen = set()
    unique_statements = []
    for s in statements:
        if s["text"] not in seen:
            seen.add(s["text"])
            unique_statements.append(s)
    
    return unique_statements


def evaluate_statements(
    statements: list[dict[str, Any]],
    system_prompt: str,
    config: dict[str, Any],
    batch_size: int = 50,
) -> list[dict[str, Any]]:
    """批量评估陈述正确性（含 M1 谬误判定 + M9 内容相关性判定）。
    
    返回格式：
    [
        {
            "text": "...",
            "verdict": "correct" | "incorrect" | "uncertain",
            "reasoning": "...",
            "source_verifiable": True/False,
            "source_check_result": "verified" | "unverified" | "mismatch",
            "content_relevance": True/False,
            "relevance_check_result": "relevant" | "irrelevant" | "partially_relevant",
            "relevance_reasoning": "..."
        },
        ...
    ]
    """
    results = []
    llm_config = config.get("llm", {})
    client = LLMClient(llm_config)
    
    # 分批处理
    for i in range(0, len(statements), batch_size):
        batch = statements[i:i + batch_size]
        
        user_prompt = f"""请评估以下 {len(batch)} 条陈述的正确性和溯源有效性：

{json.dumps(batch, ensure_ascii=False, indent=2)}

对每条陈述，请判断：
1. 是否正确 (correct) / 错误 (incorrect) / 存疑 (uncertain)
2. 是否带来源 (has_source)
3. 来源是否可验证 (source_check_result)：verified/unverified/mismatch
4. 【M9 增强】内容相关性判断：
   - content_relevance：该陈述引用的法条/来源内容是否**直接支撑**该陈述的核心断言（true=支撑，false=不支撑）
   - relevance_check_result：relevant（完全支撑）/ partially_relevant（部分支撑）/ irrelevant（不支撑）
   - relevance_reasoning：简要说明相关性判定理由
   
   示例：
   - 陈述"专利法第42条规定发明专利权期限为20年" → 引用第42条内容确有20年期限 → relevant
   - 陈述"专利法第42条规定了侵权赔偿" → 第42条实际是关于期限而非赔偿 → irrelevant

请严格按照以下 JSON 格式输出：
{{
    "evaluations": [
        {{
            "text": "原文陈述",
            "verdict": "correct/incorrect/uncertain",
            "reasoning": "判定理由",
            "source_verifiable": true/false,
            "source_check_result": "verified/unverified/mismatch",
            "content_relevance": true/false,
            "relevance_check_result": "relevant/partially_relevant/irrelevant",
            "relevance_reasoning": "相关性判定理由"
        }}
    ]
}}
"""
        
        response = client.chat(system_prompt, user_prompt)
        parsed = parse_llm_response(response)
        
        # 解析结果
        if "evaluations" in parsed:
            batch_results = parsed["evaluations"]
        else:
            # 如果没有 evaluations 字段，尝试从顶层获取
            batch_results = [parsed] if isinstance(parsed, dict) and "verdict" in parsed else []
        
        if not batch_results:
            # 尝试直接解析为列表
            if isinstance(parsed, list):
                batch_results = parsed
        
        # 处理结果，确保格式统一
        for j, statement in enumerate(batch):
            if j < len(batch_results):
                result = batch_results[j]
                results.append({
                    "text": statement["text"],
                    "verdict": result.get("verdict", "uncertain"),
                    "reasoning": result.get("reasoning", ""),
                    "source_verifiable": result.get("source_verifiable", statement.get("has_source", False)),
                    "source_check_result": result.get("source_check_result", "unverified"),
                    "content_relevance": result.get("content_relevance", statement.get("has_source", False)),
                    "relevance_check_result": result.get("relevance_check_result", "irrelevant"),
                    "relevance_reasoning": result.get("relevance_reasoning", ""),
                })
            else:
                # 如果 LLM 没有返回足够的结果，使用默认值
                results.append({
                    "text": statement["text"],
                    "verdict": "uncertain",
                    "reasoning": "LLM 未返回评估结果",
                    "source_verifiable": statement.get("has_source", False),
                    "source_check_result": "unverified",
                    "content_relevance": False,
                    "relevance_check_result": "irrelevant",
                    "relevance_reasoning": "",
                })
    
    return results


# M1 错误类型权重（可通过 config 覆盖）
M1_ERROR_WEIGHTS: dict[str, float] = {
    "legal_scope": 1.0,       # 法律适用错误（原则性错误）
    "time_limit": 0.8,        # 期限/时间错误
    "procedure": 0.7,         # 程序步骤错误
    "amount": 0.5,            # 数量/金额错误
    "terminology": 0.3,       # 术语使用错误
    "other": 0.5,             # 其他错误
}


def _classify_error_type(statement_text: str, reasoning: str) -> str:
    """将错误分类为权重不同的类型。

    基于陈述文本和判定理由中的关键词进行启发式分类。
    """
    combined = (statement_text + " " + reasoning).lower()

    if any(kw in combined for kw in ["期限", "时间", "年", "月", "日", "时效"]):
        return "time_limit"
    if any(kw in combined for kw in ["程序", "步骤", "流程", "申请", "审查"]):
        return "procedure"
    if any(kw in combined for kw in ["法律", "法条", "适用", "依据", "条例"]):
        return "legal_scope"
    if any(kw in combined for kw in ["金额", "费用", "罚款", "赔偿", "数额"]):
        return "amount"
    if any(kw in combined for kw in ["术语", "定义", "概念", "含义"]):
        return "terminology"
    return "other"


def calc_hallucination_rate(
    eval_results: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """计算 M1 专业知识谬误率（支持加权计算）。

    加权方案：不同类型的错误具有不同权重。
    - 默认权重在 M1_ERROR_WEIGHTS 中定义
    - 可通过 config["m1_weights"] 覆盖
    - 加权谬误率 = Σ(错误_i × weight_i) / Σ(陈述_j × max_weight)

    注：当前实现同时返回简单谬误率和加权谬误率，
    具体使用哪个数值由上层消费方（如 report.py）决定。
    """
    total = len(eval_results)
    incorrect = sum(1 for r in eval_results if r.get("verdict") == "incorrect")
    uncertain = sum(1 for r in eval_results if r.get("verdict") == "uncertain")
    correct = sum(1 for r in eval_results if r.get("verdict") == "correct")

    rate = incorrect / total * 100 if total > 0 else 0

    # 加权计算
    weights = M1_ERROR_WEIGHTS.copy()
    if config and "m1_weights" in config:
        weights.update(config["m1_weights"])

    weighted_error_sum = 0.0
    max_weight_sum = total * max(weights.values()) if total > 0 else 0

    error_type_details: dict[str, int] = {}
    for r in eval_results:
        if r.get("verdict") == "incorrect":
            error_type = _classify_error_type(
                r.get("text", ""), r.get("reasoning", "")
            )
            w = weights.get(error_type, 0.5)
            weighted_error_sum += w
            error_type_details[error_type] = error_type_details.get(error_type, 0) + 1

    weighted_rate = (
        round(weighted_error_sum / max_weight_sum * 100, 1)
        if max_weight_sum > 0
        else 0.0
    )

    return {
        "name": "专业知识谬误率",
        "value": round(rate, 1),
        "unit": "%",
        "total": total,
        "incorrect": incorrect,
        "correct": correct,
        "uncertain": uncertain,
        # 加权相关
        "weighted_value": weighted_rate,
        "weighted_error_sum": round(weighted_error_sum, 2),
        "max_weight_sum": round(max_weight_sum, 2),
        "error_type_distribution": error_type_details,
        "weights_used": weights,
        "note": "value 为简单谬误率，weighted_value 为加权谬误率",
    }


def calc_source_verifiable_rate(eval_results: list[dict[str, Any]]) -> dict[str, Any]:
    """计算 M9 知识溯源可验证率。

    增强版：同时考虑「来源可验证」和「内容相关性」两个维度。
    只有当来源可验证 AND 内容相关时，才算有效溯源。
    """
    source_with = [r for r in eval_results if r.get("source_verifiable")]
    
    if not source_with:
        return {
            "name": "知识溯源可验证率",
            "value": 0,
            "unit": "%",
            "note": "无带来源的陈述",
            "total_with_source": 0,
            "verified": 0,
            "content_relevant": 0,
            "fully_verified": 0,
        }
    
    verified = sum(1 for r in source_with 
                   if r.get("source_check_result") == "verified")
    content_relevant = sum(1 for r in source_with
                          if r.get("content_relevance") and r.get("relevance_check_result") == "relevant")
    # 完全验证：来源可验证 AND 内容相关
    fully_verified = sum(1 for r in source_with
                        if r.get("source_check_result") == "verified"
                        and r.get("content_relevance")
                        and r.get("relevance_check_result") == "relevant")

    rate = fully_verified / len(source_with) * 100 if source_with else 0
    
    return {
        "name": "知识溯源可验证率",
        "value": round(rate, 1),
        "unit": "%",
        "total_with_source": len(source_with),
        "verified": verified,
        "content_relevant": content_relevant,
        "fully_verified": fully_verified,
        "unverified": len(source_with) - fully_verified,
        "note": "完全验证 = 来源可验证 AND 内容支撑陈述",
    }


def evaluate_m1_m9(
    profile_id: str,
    round_num: int,
    config: dict[str, Any],
    force: bool = False,
) -> dict[str, Any] | None:
    """执行 M1（幻觉率）和 M9（溯源可验证率）评估。"""
    llm_config = config.get("llm", {})
    output_config = config.get("output", {})

    # 1. 检查输出文件
    model_name = llm_config.get("model", "unknown")
    output_name = f"statement_judge_{model_name}_{profile_id}_{round_num:02d}.json"
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

    if not course_content:
        print(f"  ❌ course_package.md 为空，跳过")
        return None

    # 3. 抽取可核验陈述
    print(f"  🔍 抽取可核验陈述...")
    statements = extract_verifiable_statements(course_content)
    print(f"    找到 {len(statements)} 条可核验陈述")
    
    if not statements:
        print(f"  ⚠️  未找到可核验陈述，跳过")
        # 仍然生成空结果文件
        result = {
            "metadata": {
                "profile_id": profile_id,
                "round": round_num,
                "eval_type": "statement_evaluation",
                "model": model_name,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            "statements_count": 0,
            "evaluations": [],
            "m1_hallucination_rate": calc_hallucination_rate([]),
            "m9_source_verifiable_rate": calc_source_verifiable_rate([]),
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  ✅ 评估完成（无陈述）: {output_name}")
        return result

    # 4. 加载系统提示词（statement evaluator 专用）
    print(f"  🤖 调用外部 LLM 评估...")
    system_prompt = load_system_prompt(mode="statement")

    # 5. 评估陈述
    evaluations = evaluate_statements(statements, system_prompt, config)
    print(f"    完成 {len(evaluations)} 条陈述的评估")

    # 6. 计算指标
    m1_result = calc_hallucination_rate(evaluations, config)
    m9_result = calc_source_verifiable_rate(evaluations)

    # 7. 保存结果
    result = {
        "metadata": {
            "profile_id": profile_id,
            "round": round_num,
            "eval_type": "statement_evaluation",
            "model": model_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "statements_count": len(statements),
        "evaluations": evaluations,
        "m1_hallucination_rate": m1_result,
        "m9_source_verifiable_rate": m9_result,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 评估完成: {output_name}")
    print(f"     M1 幻觉率: {m1_result['value']}{m1_result['unit']} ({m1_result['incorrect']}/{m1_result['total']})")
    print(f"     M9 溯源可验证率: {m9_result['value']}{m9_result['unit']} ({m9_result['verified']}/{m9_result['total_with_source']})")
    
    return result


# ── M8 异议闭环率（外部 LLM 评估） ────────────────────────────────────────────

def evaluate_m8_objection_loop(
    profile_id: str,
    round_num: int,
    config: dict[str, Any],
    force: bool = False,
) -> dict[str, Any] | None:
    """执行 M8 异议闭环率评估。

    通过外部 LLM 判定「🔴 异议 → 裁判采纳 → 修订修正 → 复核通过」链路。
    读取 cross_review、judge_report、revision 等产物进行综合判断。
    """
    llm_config = config.get("llm", {})
    output_config = config.get("output", {})

    # 1. 检查输出文件
    model_name = llm_config.get("model", "unknown")
    output_name = f"objection_loop_{model_name}_{profile_id}_{round_num:02d}.json"
    output_dir = _PROJECT_ROOT / output_config.get("dir", "backend/tests/evaluation/LLM/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name

    if output_path.exists() and not force:
        print(f"  ⏭️  跳过：{output_name} 已存在")
        return None

    # 2. 读取所需产物
    print(f"  📖 读取 M8 评估所需产物...")
    round_dir = get_round_dir(profile_id, round_num)

    required_files = {
        "cross_review_a": "expert_a_cross_review.md",
        "cross_review_b": "expert_b_cross_review.md",
        "judge_report": "judge_report.md",
        "revision_a": "expert_a_revision.md",
        "revision_b": "expert_b_revision.md",
    }

    artifact_contents: dict[str, str] = {}
    for key, filename in required_files.items():
        content = read_file(round_dir / filename)
        if content is None:
            print(f"  ⚠️  缺少文件: {filename}")
            artifact_contents[key] = ""
        else:
            artifact_contents[key] = content

    # 3. 加载 M8 专用提示词（占位，待补充）
    m8_prompt_path = _THIS_DIR / "prompts" / "objection_loop_evaluator.md"
    if m8_prompt_path.exists():
        system_prompt = m8_prompt_path.read_text(encoding="utf-8")
    else:
        # 占位提示词：待产品/教研补充
        system_prompt = (
            "你是一个专利教学课程的质量评审专家。\n"
            "请评估以下课程产出中的「异议闭环率」。\n"
            "异议闭环率 = 闭环的 🔴 异议数 / 总 🔴 异议数 × 100%\n"
            "闭环链路：🔴 异议 → 裁判采纳 → 修订修正 → 复核通过\n\n"
            "请输出 JSON 格式：\n"
            "{\n"
            '  "total_objections": 0,\n'
            '  "adopted_count": 0,\n'
            '  "closed_loop_count": 0,\n'
            '  "objections_detail": [],\n'
            '  "overall_score": 0-100,\n'
            '  "reasoning": "..."\n'
            "}"
        )

    # 4. 构造用户提示词
    user_prompt = f"""请评估 multi-{profile_id} round-{round_num:02d} 的异议闭环情况。

## 专家 A 交叉评审（含 🔴 异议）
{artifact_contents.get("cross_review_a", "(无)")}

## 专家 B 交叉评审（含 🔴 异议）
{artifact_contents.get("cross_review_b", "(无)")}

## 裁判报告
{artifact_contents.get("judge_report", "(无)")}

## 专家 A 修订稿
{artifact_contents.get("revision_a", "(无)")}

## 专家 B 修订稿
{artifact_contents.get("revision_b", "(无)")}

请按照系统提示中的 JSON 格式输出评估结果。"""

    # 5. 调用 LLM
    print(f"  🤖 调用外部 LLM 评估异议闭环率...")
    llm_client = LLMClient(llm_config)
    llm_response = llm_client.chat(system_prompt, user_prompt)
    parsed = parse_llm_response(llm_response)

    # 6. 解析结果并计算指标
    total_objections = parsed.get("total_objections", 0)
    closed_loop_count = parsed.get("closed_loop_count", 0)
    adopted_count = parsed.get("adopted_count", 0)
    overall_score = parsed.get("overall_score", 0)

    if total_objections > 0:
        loop_rate = round(closed_loop_count / total_objections * 100, 1)
    else:
        loop_rate = 100.0  # 无异议视为满分

    result = {
        "metadata": {
            "profile_id": profile_id,
            "round": round_num,
            "eval_type": "objection_loop_evaluation",
            "model": model_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "raw_llm_response": parsed,
        "metrics": {
            "value": loop_rate,
            "unit": "%",
            "detail": {
                "总🔴异议数": total_objections,
                "裁判采纳数": adopted_count,
                "闭环数（采纳+修正）": closed_loop_count,
                "未闭环数": max(0, total_objections - closed_loop_count),
                "闭环详情": parsed.get("objections_detail", []),
                "LLM评分": overall_score,
                "LLM理由": parsed.get("reasoning", ""),
                "评估方式": "外部 LLM 判定（objection_loop_evaluator 提示词）",
            },
        },
    }

    # 7. 保存结果
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  ✅ M8 评估完成: {output_name}")
    print(f"     异议闭环率: {loop_rate}% ({closed_loop_count}/{total_objections})")

    return result


# ── M7 资源形态（外部 LLM 评估） ────────────────────────────────────────────

def evaluate_m7_resource_morphology(
    profile_id: str,
    round_num: int,
    config: dict[str, Any],
    force: bool = False,
) -> dict[str, Any] | None:
    """执行 M7 资源形态外部评估。

    通过外部 LLM 判断课程中资源形态的覆盖度及与学员画像的匹配度。
    """
    llm_config = config.get("llm", {})
    output_config = config.get("output", {})

    # 1. 检查输出文件
    model_name = llm_config.get("model", "unknown")
    output_name = f"resource_morphology_{model_name}_{profile_id}_{round_num:02d}.json"
    output_dir = _PROJECT_ROOT / output_config.get("dir", "backend/tests/evaluation/LLM/results")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_name

    if output_path.exists() and not force:
        print(f"  ⏭️  跳过：{output_name} 已存在")
        return None

    # 2. 读取课程内容和画像
    print(f"  📖 读取课程内容和画像...")
    course_artifacts = read_artifacts(profile_id, round_num)
    course_content = course_artifacts.get("course_package.md", "")

    # 读取学员画像（用于适配度评估）
    profile_data = {}
    profile_dir = get_profile_dir(profile_id)
    profile_files = sorted(profile_dir.glob("profile_B.json")) # 假设画像文件
    if profile_files:
        try:
            profile_data = json.loads(profile_files[0].read_text(encoding="utf-8"))
        except Exception:
            pass
    # 如果 round_num > 1，尝试读取 feedback 目录中的画像更新
    if round_num > 1:
        prev_round_dir = get_round_dir(profile_id, round_num - 1)
        feedback_update = prev_round_dir / "feedback" / "learner_profile_update.md"
        if feedback_update.exists():
            profile_data["profile_update"] = feedback_update.read_text(encoding="utf-8")

    if not course_content:
        print(f"  ❌ course_package.md 为空，跳过")
        return None

    # 3. 加载 M7 专用提示词
    m7_prompt_path = _THIS_DIR / "prompts" / "resource_morphology_evaluator.md"
    if m7_prompt_path.exists():
        system_prompt = m7_prompt_path.read_text(encoding="utf-8")
    else:
        system_prompt = "提示词文件 resource_morphology_evaluator.md 缺失，请创建。"

    # 4. 构造用户提示词
    user_prompt = f"""请评估以下课程内容的资源形态使用情况。

## 学员画像
{json.dumps(profile_data, ensure_ascii=False, indent=2)[:1000]}

## 课程内容
{course_content[:8000]}  # 限制 token，超出截断

请按照系统提示中的 JSON 格式输出评估结果。"""

    # 5. 调用 LLM
    print(f"  🤖 调用外部 LLM 评估资源形态...")
    llm_client = LLMClient(llm_config)
    llm_response = llm_client.chat(system_prompt, user_prompt)
    parsed = parse_llm_response(llm_response)

    # 6. 解析结果
    coverage_rate = parsed.get("coverage_rate", 0)
    fit_score = parsed.get("fit_score", 0)
    core_shapes = parsed.get("core_shapes_status", {})

    # 核心形态检查
    core_coverage = sum(1 for v in core_shapes.values() if v)
    if coverage_rate == 0 and parsed.get("matched_types"):
        # 提示词未返回覆盖率时，自行计算
        matched = len(parsed.get("matched_types", []))
        coverage_rate = round(matched / 13 * 100, 1)  # 假设总类型13种

    # 综合分：简单加权 (覆盖率 * 0.4 + 适配分 * 0.6)
    overall_score = round(coverage_rate * 0.4 + fit_score * 0.6, 1)

    result = {
        "metadata": {
            "profile_id": profile_id,
            "round": round_num,
            "eval_type": "resource_morphology_evaluation",
            "model": model_name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "raw_llm_response": parsed,
        "metrics": {
            "value": overall_score,
            "unit": "分",
            "detail": {
                "资源形态覆盖率": coverage_rate,
                "学员画像适配度": fit_score,
                "核心形态（讲义/实操/分阶题）": f"{core_coverage}/3",
                "已识别形态": parsed.get("matched_types", []),
                "缺失形态": parsed.get("missing_types", []),
                "LLM理由": parsed.get("reasoning", ""),
                "评估方式": "外部 LLM 判定（resource_morphology_evaluator 提示词）",
            },
        },
    }

    # 7. 保存结果
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  ✅ M7 评估完成: {output_name}")
    print(f"     综合得分: {overall_score} (覆盖率 {coverage_rate}%, 适配度 {fit_score})")

    return result


# ── 主入口 ────────────────────────────────────────────────────────────────────

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
    eval_parser.add_argument("--mode", choices=["overall", "statement", "m7", "m8"], default="overall", 
                           help="评估模式：overall=整体评价（默认），statement=M1/M9 陈述级评估，m7=资源形态评估，m8=异议闭环率评估")

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
