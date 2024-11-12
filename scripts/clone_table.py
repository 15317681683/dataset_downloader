import psycopg2
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
from loguru import logger


def export_batch(db_config, table_name, batch_size, offset, column_names, output_dir):
    # 连接数据库
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()

    # 查询数据
    query = f"SELECT * FROM {table_name} OFFSET %s LIMIT %s"
    cur.execute(query, (offset, batch_size))
    rows = cur.fetchall()

    # 将数据转换为Pandas DataFrame
    df = pd.DataFrame(rows, columns=column_names)

    # 生成文件名
    file_name = os.path.join(output_dir, f'{table_name}_part_{offset // batch_size + 1}.csv')
    if Path(file_name).exists():
        print(f"{file_name} skipped.")
    else:
        # 写入CSV文件
        df.to_csv(file_name, index=False)

    # 关闭连接
    cur.close()
    conn.close()


def export_table_to_csv(db_config, table_name, batch_size=10000, max_workers=10):
    # 连接数据库
    conn = psycopg2.connect(**db_config)
    cur = conn.cursor()

    # 获取表的总行数
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = cur.fetchone()[0]
    logger.info(f"TOTAL ROW: {total_rows}")
    # 计算总的批次数量
    total_batches = (total_rows + batch_size - 1) // batch_size

    # 创建输出目录（如果不存在）
    output_dir = f'D:\database\law\output_{table_name}'
    os.makedirs(output_dir, exist_ok=True)

    # 获取列名
    query = f"SELECT * FROM {table_name} LIMIT 1"
    cur.execute(query)
    column_names = [desc[0] for desc in cur.description]

    # 关闭初始连接
    cur.close()
    conn.close()

    # 使用多线程导出数据
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for i in range(total_batches):
            offset = i * batch_size
            futures.append(
                executor.submit(export_batch, db_config, table_name, batch_size, offset, column_names, output_dir))

        # 使用 tqdm 显示进度条
        for future in tqdm(futures, desc=f"Exporting {table_name}", unit="batch"):
            future.result()


if __name__ == "__main__":
    # 数据库配置
    db_params = {
        'dbname': 'law',
        'user': 'law',
        'password': 'xQ4Us3c1wX',
        'host': '129.211.208.136',
        'port': '5432'
    }

    # 表名和批次大小
    table_name = 'public.case'
    batch_size = 10000
    max_workers = 5

    # 导出表数据
    export_table_to_csv(db_params, table_name, batch_size, max_workers)
