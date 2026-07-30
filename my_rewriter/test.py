import logging
import sys
import os
import argparse
import re
import json

sys.path.append('..')
from my_rewriter.config import init_llms, init_db_config

parser = argparse.ArgumentParser()
parser.add_argument('--database', type=str, required=True)
parser.add_argument('--logdir', type=str, default='logs')
parser.add_argument('--index', type=str, default='hybrid')
parser.add_argument('--topk', type=int, default=10)
args = parser.parse_args()

model_args = init_llms('open')
pg_config = init_db_config(args.database)

from my_rewriter.database import DBArgs, Database
from my_rewriter.test_utils import test
from my_rewriter.rag_retrieve import init_docstore

RETRIEVER_TOP_K = args.topk
CASE_BATCH = 5
RULE_BATCH = 10
REWRITE_ROUNDS = 1
DATABASE = args.database

if 'calcite' in DATABASE:
    DATASET = 'calcite'
elif 'tpch' in DATABASE:
    DATASET = 'tpch'
elif 'dsb' in DATABASE:
    DATASET = 'dsb'
elif 'hbom' in DATABASE:
    DATASET = 'hbom'
else:
    DATASET = DATABASE

LOG_DIR = os.path.join(args.logdir, DATASET)

pg_args = DBArgs(pg_config)

schema_path = os.path.join('..', DATASET, 'create_tables.sql')
schema = open(schema_path, 'r').read()

docstore = init_docstore()

if DATASET == 'calcite':
    queries_path = os.path.join('..', DATASET, f'{DATASET}.jsonl')
    with open(queries_path, 'r') as fin:
        for line in fin.readlines():
            obj = json.loads(line)
            query = obj['input_sql']
            name = sorted([x['name'] for x in obj['rewrites']])[0]
            test(name, query, schema, pg_args, model_args, docstore, LOG_DIR, RETRIEVER_TOP_K=RETRIEVER_TOP_K, CASE_BATCH=CASE_BATCH, RULE_BATCH=RULE_BATCH, REWRITE_ROUNDS=REWRITE_ROUNDS, index=args.index)
elif DATASET == 'hbom':
    queries_filename = os.path.join('..', DATASET, 'queries.sql')
    content = open(queries_filename, 'r').read()
    queries = [q.strip() + ';' for q in content.split(';') if q.strip()]
    for j, query in enumerate(queries):
        name = f'query{j}'
        test(name, query, schema, pg_args, model_args, docstore, LOG_DIR, RETRIEVER_TOP_K=RETRIEVER_TOP_K, CASE_BATCH=CASE_BATCH, RULE_BATCH=RULE_BATCH, REWRITE_ROUNDS=REWRITE_ROUNDS, index=args.index)
else:
    queries_path = os.path.join('..', DATASET)

    for template in sorted(os.listdir(queries_path)):
        template_path = os.path.join(queries_path, template)

        # Skip create_tables.sql, fkindexes.sql, and other files.
        if not os.path.isdir(template_path):
            continue

        query_files = sorted(
            os.path.join(template_path, filename)
            for filename in os.listdir(template_path)
            if filename.endswith('.sql')
        )

        for query_filename in query_files:
            with open(query_filename, 'r', encoding='utf-8') as file:
                content = file.read()

            # Remove SQL line comments.
            content = re.sub(r'--.*(?:\n|$)', '\n', content)

            queries = [
                statement.strip() + ';'
                for statement in content.split(';')
                if statement.strip()
            ]

            # query1a_0.sql -> query1a_0
            query_stem = os.path.splitext(
                os.path.basename(query_filename)
            )[0]

            for j, query in enumerate(queries):
                name = (
                    query_stem
                    if len(queries) == 1
                    else f'{query_stem}_{j}'
                )

                test(
                    name,
                    query,
                    schema,
                    pg_args,
                    model_args,
                    docstore,
                    LOG_DIR,
                    RETRIEVER_TOP_K=RETRIEVER_TOP_K,
                    CASE_BATCH=CASE_BATCH,
                    RULE_BATCH=RULE_BATCH,
                    REWRITE_ROUNDS=REWRITE_ROUNDS,
                    index=args.index,
                )
