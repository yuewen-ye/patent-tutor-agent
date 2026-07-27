import os
import builtins

_original_rename = os.rename
def _patched_rename(src, dst, *args, **kwargs):
    if os.path.exists(dst):
        try:
            os.remove(dst)
        except PermissionError:
            time.sleep(0.5)
            try:
                os.remove(dst)
            except:
                pass
    return _original_rename(src, dst, *args, **kwargs)
os.rename = _patched_rename

import glob
import shutil
import time
import pyarrow.parquet as pq
from pymilvus import MilvusClient, DataType

os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_TRACE'] = ''

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OLD_DB_PATH = os.path.join(BASE_DIR, "backend", "app", "rag", "data", "milvus_lite.db")
NEW_DB_PATH = os.path.join(BASE_DIR, "backend", "app", "rag", "data", "milvus_lite_rebuild.db")
COLLECTION_NAME = "law_knowledge_base"
VECTOR_DIM = 1024
BATCH_SIZE = 10000

if os.path.exists(NEW_DB_PATH):
    shutil.rmtree(NEW_DB_PATH)

print("[1] 创建新数据库...")
client = MilvusClient(NEW_DB_PATH, keepalive_time_ms=300000, keepalive_timeout_ms=60000)

schema = client.create_schema(auto_id=True, enable_dynamic_field=True)
schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=VECTOR_DIM)
schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=256)

index_params = client.prepare_index_params()
index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")

client.create_collection(collection_name=COLLECTION_NAME, schema=schema, index_params=index_params)
print("  collection创建成功")

parquet_dir = os.path.join(OLD_DB_PATH, "collections", COLLECTION_NAME, "partitions", "_default", "data")
parquet_files = sorted(glob.glob(os.path.join(parquet_dir, "*.parquet")))
print(f"[2] 找到 {len(parquet_files)} 个parquet文件，开始读取并插入...")

def clean_tmp_files(db_path):
    for tmp in glob.glob(os.path.join(db_path, "**", "*.tmp"), recursive=True):
        try:
            os.remove(tmp)
        except:
            pass

total_inserted = 0
for pf_idx, pf_path in enumerate(parquet_files, 1):
    fname = os.path.basename(pf_path)
    table = pq.read_table(pf_path, columns=["vector", "text", "source"])
    rows = []
    for i in range(table.num_rows):
        vec = table.column("vector")[i].as_py()
        text = table.column("text")[i].as_py()
        source = table.column("source")[i].as_py()
        rows.append({"vector": vec, "text": text, "source": source})

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i+BATCH_SIZE]
        for attempt in range(5):
            try:
                clean_tmp_files(NEW_DB_PATH)
                client.insert(collection_name=COLLECTION_NAME, data=batch)
                break
            except Exception as e:
                if attempt < 4:
                    clean_tmp_files(NEW_DB_PATH)
                    time.sleep(2)
                else:
                    raise

    total_inserted += len(rows)
    print(f"  [{pf_idx}/{len(parquet_files)}] {fname}: {len(rows)} 条，累计 {total_inserted}")

print(f"\n[3] 插入完成，等待数据落盘...")
clean_tmp_files(NEW_DB_PATH)
time.sleep(5)

stats = client.get_collection_stats(COLLECTION_NAME)
row_count = stats.get('row_count', 0)
print(f"  总条数: {row_count}")

client.close()
time.sleep(3)

print("[4] 替换旧数据库...")
if os.path.exists(OLD_DB_PATH):
    shutil.rmtree(OLD_DB_PATH)
os.rename(NEW_DB_PATH, OLD_DB_PATH)

print("[5] 设置parquet只读保护...")
for root, dirs, files in os.walk(OLD_DB_PATH):
    for f in files:
        fp = os.path.join(root, f)
        if f.endswith('.parquet'):
            os.chmod(fp, 0o444)
        else:
            try:
                os.chmod(fp, 0o666)
            except:
                pass

parquet_count = len(glob.glob(os.path.join(OLD_DB_PATH, "**", "*.parquet"), recursive=True))
print(f"  {parquet_count} 个parquet文件已设为只读")

print(f"\n=== 重灌完成！共 {row_count} 条数据 ===")
if row_count == 107229:
    print("数据条数正确 (107229)")
else:
    print(f"警告：期望107229条，实际{row_count}条")
