"""清理 export_data.sql，删除多余的测试数据。

用法:
  # 分析文件
  uv run python backend/tests/evaluation/clean_export_sql.py --analyze-only

  # 只保留 multi- 开头的画像
  uv run python backend/tests/evaluation/clean_export_sql.py --keep-prefix multi-

  # 保留指定 ID
  uv run python backend/tests/evaluation/clean_export_sql.py --keep-ids multi-B multi-C multi-D

  # 保留全部
  uv run python backend/tests/evaluation/clean_export_sql.py --all
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


def _split_sql(sql: str) -> list[str]:
    """按分号切分 SQL，忽略字符串中的分号。"""
    out = []
    buf = []
    quote = None
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if not quote:
            if c == "-" and i + 1 < n and sql[i + 1] == "-":
                while i < n and sql[i] != "\n":
                    i += 1
                continue
            if c == "/" and i + 1 < n and sql[i + 1] == "*":
                i += 2
                while i < n and not (sql[i] == "*" and i + 1 < n and sql[i + 1] == "/"):
                    i += 1
                if i < n:
                    i += 2
                continue
        if quote:
            buf.append(c)
            if c == "\\" and i + 1 < n:
                buf.append(sql[i + 1])
                i += 2
                continue
            if c == quote:
                if quote == "'" and i + 1 < n and sql[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if c == "'" or c == '"':
            quote = c
            buf.append(c)
        elif c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
        else:
            buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def get_table(stmt: str) -> str | None:
    m = re.match(r"INSERT INTO (\w+)", stmt)
    return m.group(1) if m else None


def extract_student_ids(stmt: str) -> list[str]:
    """从 INSERT 语句中提取所有 student_id。"""
    ids = []
    # 处理 students 表的特殊格式
    m = re.search(
        r"INSERT INTO students.*?VALUES\s*\('([^']+)'", stmt, re.DOTALL
    )
    if m:
        ids.append(m.group(1))
    # 通用：查找 student_id 字段
    for m in re.finditer(r"student_id[^']*?'([^']+)'", stmt):
        ids.append(m.group(1))
    return list(set(ids))


def extract_session_ids(stmt: str) -> list[str]:
    """从 INSERT 语句中提取所有 session_id。"""
    ids = []
    for m in re.finditer(r"session_id[^']*?'([^']+)'", stmt):
        ids.append(m.group(1))
    return list(set(ids))


def analyze(filepath: str) -> dict:
    """分析 SQL 文件。"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    statements = _split_sql(content)

    table_counter = Counter()
    student_ids = set()
    session_ids = set()
    student_sessions: dict[str, set[str]] = {}

    for stmt in statements:
        if not stmt:
            continue
        table = get_table(stmt)
        if not table:
            continue
        table_counter[table] += 1

        sids = extract_student_ids(stmt)
        for sid in sids:
            student_ids.add(sid)
            for ses_id in extract_session_ids(stmt):
                session_ids.add(ses_id)
                if sid not in student_sessions:
                    student_sessions[sid] = set()
                student_sessions[sid].add(ses_id)

    return {
        "total": len(statements),
        "table_counts": dict(table_counter),
        "student_ids": sorted(student_ids),
        "session_ids": sorted(session_ids),
        "student_sessions": {
            k: sorted(v) for k, v in student_sessions.items()
        },
        "statements": statements,
    }


def filter_statements(
    statements: list[str],
    keep_student_ids: set[str],
) -> tuple[list[str], set[str]]:
    """过滤 SQL 语句，返回 (保留的语句, 保留的session_id)。"""
    # 第一遍：收集要保留的 session_id
    keep_sessions: set[str] = set()
    for stmt in statements:
        if not stmt:
            continue
        sids = extract_student_ids(stmt)
        if any(sid in keep_student_ids for sid in sids):
            for ses_id in extract_session_ids(stmt):
                keep_sessions.add(ses_id)

    # 第二遍：过滤
    result = []
    for stmt in statements:
        if not stmt:
            continue
        sids = extract_student_ids(stmt)
        ses_ids = extract_session_ids(stmt)

        keep = False
        if any(sid in keep_student_ids for sid in sids):
            keep = True
        elif any(ses_id in keep_sessions for ses_id in ses_ids):
            keep = True

        if keep:
            result.append(stmt)

    return result, keep_sessions


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 export_data.sql")
    parser.add_argument(
        "--input",
        default="backend/tests/evaluation/export_data.sql",
    )
    parser.add_argument(
        "--output",
        default="backend/tests/evaluation/export_data_clean.sql",
    )
    parser.add_argument(
        "--keep-ids",
        nargs="+",
        help="要保留的 student_id 列表",
    )
    parser.add_argument(
        "--keep-prefix",
        help="保留所有以此前缀开头的学生（如 multi-）",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="保留全部数据",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
    )

    args = parser.parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"❌ 文件不存在: {input_path}")
        sys.exit(1)

    print(f"正在分析: {input_path}")
    info = analyze(str(input_path))

    print(f"\n{'='*50}")
    print(f"分析结果")
    print(f"{'='*50}")
    print(f"总语句数: {info['total']}")
    print(f"\n各表统计:")
    for table, count in sorted(
        info["table_counts"].items(), key=lambda x: -x[1]
    ):
        print(f"  {table}: {count}")

    print(f"\n学生 ID ({len(info['student_ids'])} 个):")
    by_prefix = {}
    for sid in info["student_ids"]:
        sessions = info["student_sessions"].get(sid, [])
        prefix = sid.split("-")[0] if "-" in sid else sid[:8]
        by_prefix.setdefault(prefix, []).append((sid, len(sessions)))

    for prefix, items in sorted(by_prefix.items()):
        print(f"\n  [{prefix}] ({len(items)} 个):")
        for sid, ses_count in sorted(items):
            print(f"    {sid}: {ses_count} 个会话")

    if args.analyze_only:
        return

    # 确定要保留的学生
    if args.all:
        print("\n保留全部数据")
        return

    keep_ids = set()
    if args.keep_prefix:
        prefix = args.keep_prefix
        keep_ids = {
            sid for sid in info["student_ids"] if sid.startswith(prefix)
        }
        print(f"\n保留所有以 '{prefix}' 开头的学生: {len(keep_ids)} 个")

    if args.keep_ids:
        keep_ids.update(args.keep_ids)

    if not keep_ids:
        print("\n请选择要保留的学生类型:")
        print("  1) multi- 开头 (评估用画像)")
        print("  2) profile_ 开头 (旧画像)")
        print("  3) 全部")
        print("  4) 自定义 (输入 ID)")
        raw = input("> ").strip()

        if raw == "1":
            keep_ids = {
                sid for sid in info["student_ids"] if sid.startswith("multi-")
            }
        elif raw == "2":
            keep_ids = {
                sid for sid in info["student_ids"] if sid.startswith("profile_")
            }
        elif raw == "3":
            print("保留全部")
            return
        elif raw == "4":
            print("输入学生 ID（逗号分隔）:")
            ids_str = input("> ").strip()
            keep_ids = set(id.strip() for id in ids_str.split(","))
        else:
            print("已取消")
            return

    if not keep_ids:
        print("未选择任何学生，退出")
        return

    # 预览
    filtered, keep_sessions = filter_statements(
        info["statements"], keep_ids
    )
    print(f"\n过滤预览:")
    print(f"  保留学生: {len(keep_ids)} 个")
    print(f"  保留会话: {len(keep_sessions)} 个")
    print(f"  原语句数: {len(info['statements'])}")
    print(f"  保留语句数: {len(filtered)}")

    if not args.yes:
        print("\n确认保存？(y/N)")
        if input("> ").strip().lower() != "y":
            print("已取消")
            return

    # 写入
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for stmt in filtered:
            f.write(stmt)
            f.write(";\n\n" if not stmt.endswith(";") else "\n\n")

    print(f"\n✅ 清理完成: {output_path}")


if __name__ == "__main__":
    main()
