"""MySQL 数据导出/导入工具。

用于在不同环境之间同步学习者数据（学习者画像、会话、BKT mastery 等）。

用法：
  # 导出 multi- 开头的学习者数据（默认输出到 backend/tests/evaluation/）
  uv run python backend/tests/evaluation/mysql_export_import.py export --all

  # 导出指定学习者的数据
  uv run python backend/tests/evaluation/mysql_export_import.py export --learner-ids multi-B multi-C

  # 导出所有学习者的数据（不过滤前缀）
  uv run python backend/tests/evaluation/mysql_export_import.py export --all --no-filter

  # 导入数据
  uv run python backend/tests/evaluation/mysql_export_import.py import --input backend/tests/evaluation/export_data.sql
  
  # 预览将导出的数据（不实际执行）
  uv run python backend/tests/evaluation/mysql_export_import.py export --learner-ids multi-B --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # backend/tests/evaluation/ -> project root
EVAL_DIR = Path(__file__).resolve().parent  # backend/tests/evaluation/

# 默认过滤前缀：只导出以 multi- 开头的学习者数据
DEFAULT_FILTER_PREFIX = "multi-"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 加载 .env 文件
from dotenv import load_dotenv

ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
    print(f"已加载配置: {ENV_PATH}")
else:
    print(f"⚠️ 未找到 .env 文件: {ENV_PATH}")


def get_mysql_url() -> str:
    """获取 MySQL 连接 URL。"""
    url = os.getenv("PATENT_TUTOR_MYSQL_URL", "")
    if not url:
        try:
            from backend.app.config import load_service_settings
            url = load_service_settings().mysql_url or ""
        except Exception:
            pass
    if not url:
        raise RuntimeError("PATENT_TUTOR_MYSQL_URL 未配置，请在 .env 中设置")
    return url


def parse_mysql_url(url: str) -> dict[str, str]:
    """解析 MySQL URL，支持 mysql://、mysql+pymysql:// 格式，支持 URL 编码的凭据。"""
    m = re.match(
        r"mysql(?:\+\w+)?://(?P<u>[^:]+):(?P<p>[^@]+)@(?P<h>[^:]+):(?P<port>\d+)/(?P<db>[^/?]+)",
        url,
    )
    if not m:
        raise ValueError(f"无法解析 MySQL URL: {url}")

    return {
        "user": unquote(m.group("u")),
        "password": unquote(m.group("p")),
        "host": m.group("h"),
        "port": m.group("port"),
        "database": m.group("db"),
    }


def connect_mysql(url: str):
    """连接 MySQL 数据库（使用 pymysql）。"""
    import pymysql
    from pymysql.cursors import DictCursor
    
    config = parse_mysql_url(url)
    conn = pymysql.connect(
        user=config["user"],
        password=config["password"],
        host=config["host"],
        port=int(config["port"]),
        database=config["database"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False,
    )
    return conn


def list_learners(conn, prefix_filter: str | None = None) -> list[str]:
    """列出数据库中所有学习者 ID，可按前缀过滤。"""
    cursor = conn.cursor()
    if prefix_filter:
        cursor.execute("SELECT DISTINCT student_id FROM students WHERE student_id LIKE %s", 
                      (f"{prefix_filter}%",))
    else:
        cursor.execute("SELECT DISTINCT student_id FROM students")
    learners = [row["student_id"] for row in cursor.fetchall()]
    cursor.close()
    return sorted(learners)


def get_learner_data(conn, learner_id: str) -> dict[str, list[dict[str, Any]]]:
    """导出单个学习者的所有数据。"""
    cursor = conn.cursor()  # DictCursor 已在连接时设置
    data: dict[str, list[dict[str, Any]]] = {}
    
    # 1. students 表
    cursor.execute("SELECT * FROM students WHERE student_id = %s", (learner_id,))
    data["students"] = cursor.fetchall()
    
    # 2. student_profiles 表
    cursor.execute("SELECT * FROM student_profiles WHERE student_id = %s", (learner_id,))
    data["student_profiles"] = cursor.fetchall()
    
    # 3. profile_history 表
    cursor.execute("SELECT * FROM profile_history WHERE student_id = %s", (learner_id,))
    data["profile_history"] = cursor.fetchall()
    
    # 4. student_node_mastery 表
    cursor.execute("SELECT * FROM student_node_mastery WHERE student_id = %s", (learner_id,))
    data["student_node_mastery"] = cursor.fetchall()
    
    # 5. 会话相关（sessions + session_states + rounds）
    cursor.execute("SELECT * FROM sessions WHERE student_id = %s", (learner_id,))
    sessions = cursor.fetchall()
    data["sessions"] = sessions
    
    session_ids = [s["session_id"] for s in sessions]
    if session_ids:
        placeholders = ",".join(["%s"] * len(session_ids))
        
        cursor.execute(f"SELECT * FROM session_states WHERE session_id IN ({placeholders})", session_ids)
        data["session_states"] = cursor.fetchall()
        
        cursor.execute(f"SELECT * FROM rounds WHERE session_id IN ({placeholders})", session_ids)
        data["rounds"] = cursor.fetchall()
        
        # 6. 学习计划相关
        cursor.execute("SELECT * FROM learner_learning_plans WHERE student_id = %s", (learner_id,))
        plans = cursor.fetchall()
        data["learner_learning_plans"] = plans
        
        plan_ids = [p["plan_id"] for p in plans]
        if plan_ids:
            plan_placeholders = ",".join(["%s"] * len(plan_ids))
            cursor.execute(f"SELECT * FROM learner_learning_plan_nodes WHERE plan_id IN ({plan_placeholders})", plan_ids)
            data["learner_learning_plan_nodes"] = cursor.fetchall()
        
        # 7. 题目相关
        cursor.execute(f"SELECT * FROM questions WHERE session_id IN ({placeholders})", session_ids)
        data["questions"] = cursor.fetchall()
        
        # 8. 作答相关
        # 需要把 session_ids 展开，再加一个 learner_id
        params = tuple(session_ids) + (learner_id,)
        cursor.execute(f"SELECT * FROM attempts WHERE session_id IN ({placeholders}) OR student_id = %s", 
                      params)
        attempts = cursor.fetchall()
        data["attempts"] = attempts
        
        attempt_ids = [a["attempt_id"] for a in attempts]
        if attempt_ids:
            attempt_placeholders = ",".join(["%s"] * len(attempt_ids))
            cursor.execute(f"SELECT * FROM mastery_events WHERE attempt_id IN ({attempt_placeholders})", attempt_ids)
            data["mastery_events"] = cursor.fetchall()
        
        # 9. 问卷相关
        cursor.execute(f"SELECT * FROM onboarding_responses WHERE session_id IN ({placeholders})", session_ids)
        data["onboarding_responses"] = cursor.fetchall()
        
        # 10. 产物相关
        cursor.execute(f"SELECT * FROM artifacts WHERE session_id IN ({placeholders})", session_ids)
        artifacts = cursor.fetchall()
        data["artifacts"] = artifacts
        
        artifact_ids = [a["artifact_id"] for a in artifacts]
        if artifact_ids:
            artifact_placeholders = ",".join(["%s"] * len(artifact_ids))
            cursor.execute(f"SELECT * FROM artifact_citations WHERE artifact_id IN ({artifact_placeholders})", artifact_ids)
            data["artifact_citations"] = cursor.fetchall()
    
    # 11. memory_items
    cursor.execute("SELECT * FROM memory_items WHERE namespace LIKE %s", (f"{learner_id}/%",))
    data["memory_items"] = cursor.fetchall()
    
    cursor.close()
    return data


def _escape_str(s: str) -> str:
    """MySQL 字符串转义（单引号包裹场景），覆盖 \\ ' \\n \\r \\0 \\x1a。"""
    return (
        s.replace("\\", "\\\\")
         .replace("'", "\\'")
         .replace("\n", "\\n")
         .replace("\r", "\\r")
         .replace("\0", "\\0")
         .replace("\x1a", "\\Z")
    )


def _format_value(v: Any) -> str:
    """将单个 Python 值转成安全的 SQL 字面量（保持 INSERT 语句格式不变）。"""
    import json
    from decimal import Decimal

    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    if isinstance(v, (dict, list)):
        return "'" + _escape_str(json.dumps(v, ensure_ascii=False)) + "'"
    if isinstance(v, bytes):
        return "x'" + v.hex() + "'"
    return "'" + _escape_str(str(v)) + "'"


def export_to_sql(data: dict[str, list[dict[str, Any]]], learner_id: str) -> str:
    """将数据转换为 SQL INSERT 语句。"""
    lines: list[str] = []
    lines.append(f"-- 导出学习者数据: {learner_id}")
    lines.append(f"-- 导出时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    for table, rows in data.items():
        if not rows:
            continue
        
        lines.append(f"-- {table} ({len(rows)} 条记录)")
        for row in rows:
            columns = ", ".join(row.keys())
            values = [_format_value(v) for v in row.values()]
            values_str = ", ".join(values)
            lines.append(f"INSERT INTO {table} ({columns}) VALUES ({values_str});")
        
        lines.append("")
    
    return "\n".join(lines)


def _split_sql_statements(sql: str) -> list[str]:
    """按分号切分 SQL，忽略字符串字面量（含转义）与注释中的分号。"""
    out: list[str] = []
    buf: list[str] = []
    quote = None  # None / "'" / '"'
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        # 不在字符串内时识别注释，注释内的分号不切分
        if not quote:
            if c == "-" and i + 1 < n and sql[i + 1] == "-":  # 行注释 --
                while i < n and sql[i] != "\n":
                    i += 1
                continue
            if c == "/" and i + 1 < n and sql[i + 1] == "*":  # 块注释 /* */
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
                # MySQL 字符串内连续两个单引号表示一个字面量单引号
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


def import_from_sql(conn, sql_content: str, *, dry_run: bool = False) -> dict:
    """执行 SQL 导入，返回统计信息。"""
    cursor = conn.cursor()
    statements = _split_sql_statements(sql_content)
    
    stats = {
        "total": len(statements),
        "success": 0,
        "skipped": 0,  # 可能已存在
        "failed": 0,
    }
    
    if dry_run:
        print(f"[DRY RUN] 将执行 {len(statements)} 条 SQL 语句")
        for i, stmt in enumerate(statements[:5], 1):
            print(f"  {i}. {stmt[:100]}...")
        if len(statements) > 5:
            print(f"  ... 还有 {len(statements) - 5} 条")
        cursor.close()
        return stats
    
    # 禁用外键检查，避免导入顺序问题
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    print("已禁用外键检查")
    
    for stmt in statements:
        # 跳过注释
        if stmt.startswith("--"):
            continue
        try:
            cursor.execute(stmt)
            stats["success"] += 1
            conn.commit()  # 每条成功语句立即提交
        except Exception as e:
            error_msg = str(e).lower()
            # 判断是否为"已存在"类错误（pymysql 1062 = Duplicate entry）
            if any(kw in error_msg for kw in ["duplicate", "exists", "already", "1062", "errno 1062"]):
                stats["skipped"] += 1
            else:
                stats["failed"] += 1
                print(f"  ❌ 失败: {str(e)[:100]}")
            # 继续执行，不中断
            conn.rollback()
            continue
    
    # 恢复外键检查
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    print("已恢复外键检查")
    
    cursor.close()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", help="操作类型")
    
    # 导出命令
    export_parser = subparsers.add_parser("export", help="导出数据")
    export_group = export_parser.add_mutually_exclusive_group(required=True)
    export_group.add_argument("--learner-ids", nargs="+", help="要导出的学习者 ID 列表")
    export_group.add_argument("--all", action="store_true", help=f"导出所有学习者（默认只导出 {DEFAULT_FILTER_PREFIX} 开头的）")
    export_parser.add_argument("--no-filter", action="store_true", help="禁用前缀过滤，导出所有学习者")
    export_parser.add_argument("--filter-prefix", default=DEFAULT_FILTER_PREFIX, 
                               help=f"学习者 ID 前缀过滤（默认: {DEFAULT_FILTER_PREFIX}）")
    export_parser.add_argument("--output", default="export_data.sql", help="输出文件路径（默认保存到 backend/tests/evaluation/）")
    export_parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际导出")
    
    # 导入命令
    import_parser = subparsers.add_parser("import", help="导入数据")
    import_parser.add_argument("--input", required=True, help="输入 SQL 文件路径")
    import_parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际导入")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        url = get_mysql_url()
        print(f"连接数据库: {url.split('@')[-1] if '@' in url else url}")
        conn = connect_mysql(url)
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return
    
    try:
        if args.command == "export":
            if args.all:
                # 默认使用前缀过滤，除非指定 --no-filter
                filter_prefix = None if args.no_filter else args.filter_prefix
                learner_ids = list_learners(conn, prefix_filter=filter_prefix)
                if filter_prefix:
                    print(f"发现 {len(learner_ids)} 个 {filter_prefix} 开头的学习者: {', '.join(learner_ids)}")
                else:
                    print(f"发现 {len(learner_ids)} 个学习者（无过滤）: {', '.join(learner_ids)}")
            else:
                learner_ids = args.learner_ids
            
            all_sql_parts: list[str] = []
            total_tables = 0
            total_records = 0
            successful_learners = 0
            failed_learners = []
            
            for lid in learner_ids:
                print(f"\n导出学习者: {lid}")
                try:
                    data = get_learner_data(conn, lid)
                    tables = len(data)
                    records = sum(len(rows) for rows in data.values())
                    total_tables += tables
                    total_records += records
                    successful_learners += 1
                    print(f"  ✅ 成功: {tables} 张表，{records} 条记录")
                    
                    if args.dry_run:
                        for table, rows in data.items():
                            if rows:
                                print(f"    {table}: {len(rows)} 条")
                    else:
                        sql = export_to_sql(data, lid)
                        all_sql_parts.append(sql)
                except Exception as e:
                    failed_learners.append(lid)
                    print(f"  ❌ 失败: {str(e)[:100]}")
            
            # 显示汇总
            print(f"\n{'='*50}")
            print(f"导出统计")
            print(f"{'='*50}")
            print(f"  总学习者数: {len(learner_ids)}")
            print(f"  ✅ 成功:   {successful_learners}")
            if failed_learners:
                print(f"  ❌ 失败:   {len(failed_learners)} ({', '.join(failed_learners)})")
            print(f"  总表数:   {total_tables}")
            print(f"  总记录数: {total_records}")
            print(f"{'='*50}")
            
            if not args.dry_run and all_sql_parts:
                output_path = Path(args.output)
                # 如果是相对路径，默认保存到 evaluation 目录
                if not output_path.is_absolute() and output_path == Path("export_data.sql"):
                    output_path = EVAL_DIR / output_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("\n".join(all_sql_parts), encoding="utf-8")
                print(f"\n📁 导出文件: {output_path}")
        
        elif args.command == "import":
            input_path = Path(args.input)
            # 如果是相对路径且不存在，尝试从 evaluation 目录查找
            if not input_path.is_absolute() and not input_path.exists():
                eval_path = EVAL_DIR / input_path
                if eval_path.exists():
                    input_path = eval_path
            if not input_path.exists():
                print(f"❌ 文件不存在: {input_path}")
                return
            
            sql_content = input_path.read_text(encoding="utf-8")
            
            if args.dry_run:
                print(f"[DRY RUN] 将从 {input_path} 导入数据")
            
            stats = import_from_sql(conn, sql_content, dry_run=args.dry_run)
            
            total = stats["total"]
            success = stats["success"]
            skipped = stats["skipped"]
            failed = stats["failed"]
            
            print(f"\n{'='*50}")
            print(f"导入统计")
            print(f"{'='*50}")
            print(f"  总语句数: {total}")
            print(f"  ✅ 成功:   {success}")
            if skipped > 0:
                print(f"  ⚠️ 跳过:   {skipped}（可能已存在）")
            if failed > 0:
                print(f"  ❌ 失败:   {failed}")
            print(f"{'='*50}")
            
            if args.dry_run:
                print("（预览模式，未实际执行）")
    
    finally:
        conn.close()
        print("\n数据库连接已关闭")


if __name__ == "__main__":
    main()
