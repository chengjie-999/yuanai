# -*- coding: utf-8 -*-
"""Claude Code 桥接的实时搜索通道（用法：python -m yuanai_core.pure.cc_search "查询词"）

桥接白名单只有 Bash(python -m:*)——CC 直接执行脚本文件（python xxx.py）会被
权限表拦截，本模块提供 -m 入口。网络请求走平台内置三级兜底
（DeepSeek 官方 Search → Bing → DDG），不开新安全边界。
"""

import os
import sys


def _load_env():
    """子进程（claude -p）不保证已加载 .env——搜索需要 DEEPSEEK_API_KEY"""
    try:
        from dotenv import load_dotenv
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        load_dotenv(os.path.join(root, ".env"))
    except Exception:
        pass


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('用法: python -m yuanai_core.pure.cc_search "查询词" [最大条数 1-20，默认 8]')
        return 1
    query = sys.argv[1]
    max_results = 8
    if len(sys.argv) > 2:
        try:
            max_results = max(1, min(int(sys.argv[2]), 20))
        except ValueError:
            pass
    _load_env()
    from yuanai_core.pure.web_search import web_search
    results = web_search(query, max_results)
    if not results:
        print(f"未找到结果: {query}")
        return 0
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('title', '')}\n   {r.get('url', '')}")
        snippet = (r.get('snippet') or r.get('answer') or '').strip()
        if snippet:
            print(f"   {snippet[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
