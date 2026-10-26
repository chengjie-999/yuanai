# 记忆存储方案对比（B2，2026-10-26 设计稿）

## 现状（为什么臃肿）

`data/.yuan/{user_id}/` 每条记忆一个 .md（自实现扁平 frontmatter：name/description/
type/created_at/source + 一行正文）+ `MEMORY.md` 索引。写路径 = `memory_store` 整目录
原子替换（tmp 目录 + os.replace），读路径 = 逐文件解析 + 索引重建。

痛点：N 个小文件（条目 100 条 = 100 文件 + 索引）；每次写全量重写目录；并发靠
per-user 锁串行；跨用户扫描/统计要遍历目录树。

## 三个候选

| 方案 | 结构 | 写 | 读 | 优点 | 缺点 |
|------|------|-----|-----|------|------|
| **A. 单文件 JSONL** | `data/.yuan/{uid}/facts.jsonl` 每行一条 + 文件头版本 | 追加一行（O(1)），定期压缩（重写去重） | 顺序读全文（≤100 条无压力） | Claude Code 同款；追加写天然崩溃安全；简单透明可 grep；迁移成本低（现有 .md 一次转换） | 并发追加需锁（已有 per-user 锁复用）；无索引（量小不需要） |
| B. SQLite | `data/.yuan/{uid}/facts.db` 单表 | SQL upsert | SQL 查询 | 事务、可索引、可扩展字段 | 运维/调试不透明（不如 md/jsonl 可看）；多进程写要 WAL 配置；收益对 100 条规模无意义 |
| C. 并入 MySQL | `user_facts` 表按 user_id 隔离 | 现有 db.session 路径 | SQL | 与云端其余数据同库同备份 | 记忆文件化的初衷（Claude Code 式、云端 Agent 只读写入方、懒迁移）被破坏；本地 Agent 离线读写路径复杂化；备份/删除权再陷 MySQL 级联问题（合规审计 C4 正为此头疼） |

## 推荐：A（单文件 JSONL + 定期压缩）

1. **迁移**：一次性把每条 .md 转成 JSONL 行（保留 created_at/type/source 字段），
   MEMORY.md 索引废弃（读取方按 created_at 排序即可）；旧目录保留 `.md.bak` 或
   直接 gitignore 数据目录不回滚（数据目录本就不入库）。
2. **写路径**：`append(line)` 原子追加（open 'a' + flush，单行写入天然原子性在本地
   文件系统足够）+ 触发阈值（如 >120 条或 >50KB）时后台压缩重写（复用 plan_organize
   去重语义，与自动整理天然配合）。
3. **接口兼容**：`memory_store` 对外 API 不变（load_entries/apply_entries/add_facts/
   delete_fact/clear/rewrite），内部实现换存储——折叠/组织工具/设置页/记忆注入
   零改动。
4. **安全**：仍只接受云端 Agent 写入（HTTP 端点），本地 Agent 走 /agent/memory；
   删除护栏、审计日志照旧。

## 实施顺序（批准后）

1. memory_store 加 JSONL 后端（读兼容旧 .md 目录，双读过渡）
2. 一次性迁移脚本 + 启动时懒迁移（首个用户访问时转换）
3. 写路径切 JSONL（追加 + 压缩阈值）
4. 全量测试（test_memory_store 系列适配）+ 真机整理回归
