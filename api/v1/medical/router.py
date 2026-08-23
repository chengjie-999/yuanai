"""
医学与生命科学 API — 物种导航 / PubMed 文献检索 / 药物可行性评估

数据与 NCBI 调用逻辑复用自 agent/tools/pubmed_tools.py（LangChain 工具版），
但不在 api 进程 import agent.tools：agent/tools/__init__.py 在模块级会扫描全部
38 个专用工具（含 selenium 等重依赖），云端 API 进程不应加载。
故此处按原样保留物种映射表与 eutils 调用实现，来源：agent/tools/pubmed_tools.py
"""
import logging
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/medical", tags=["medical"])

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
REQUEST_DELAY = 0.34  # NCBI 限速：每秒最多 3 次请求
EUTILS_TIMEOUT = 10  # 单次 NCBI 请求超时（秒）

# ===================== 物种 → MeSH 术语映射 =====================
# 来源: agent/tools/pubmed_tools.py SPECIES_MESH（原样保留）
SPECIES_MESH: Dict[str, str] = {
    "人类": "humans", "人": "humans", "human": "humans",
    "小鼠": "mice", "mouse": "mice", "mice": "mice",
    "大鼠": "rats", "rat": "rats", "rats": "rats",
    "非人灵长类": "primates", "灵长类": "primates", "猴子": "primates",
    "犬": "dogs", "狗": "dogs", "dog": "dogs", "dogs": "dogs",
    "猫": "cats", "cat": "cats", "cats": "cats",
    "猪": "swine", "pig": "swine", "swine": "swine",
    "牛": "cattle", "cow": "cattle", "cattle": "cattle",
    "羊": "sheep", "sheep": "sheep",
    "兔": "rabbits", "rabbit": "rabbits", "rabbits": "rabbits",
    "斑马鱼": "zebrafish", "zebrafish": "zebrafish",
    "果蝇": "drosophila", "drosophila": "drosophila",
    "线虫": "caenorhabditis elegans", "c elegans": "caenorhabditis elegans",
    "酵母": "saccharomyces cerevisiae", "yeast": "saccharomyces cerevisiae",
    "大肠杆菌": "escherichia coli", "e coli": "escherichia coli",
    "拟南芥": "arabidopsis", "arabidopsis": "arabidopsis",
    "斑胸草雀": "taeniopygia guttata",
}

# 常见物种的生物学/医学描述（来源同上 SPECIES_INFO，仅用于可行性评估 prompt 补充）
SPECIES_INFO: Dict[str, str] = {
    "人类": "Homo sapiens — 哺乳纲灵长目。基因组约3.2Gb，~20000个蛋白编码基因。模式生物，所有临床研究最终指向人类。常用细胞系：HeLa、HEK293、HUVEC。",
    "小鼠": "Mus musculus — 啮齿目。最常用的哺乳动物模型。生命周期短(2-3年)，基因编辑成熟(CRISPR/Cas9)。常用品系：C57BL/6、BALB/c。免疫系统与人存在差异。",
    "大鼠": "Rattus norvegicus — 啮齿目。体型大于小鼠，适合手术操作和生理学研究。常用品系：Sprague-Dawley、Wistar。心血管和神经科学研究首选。",
    "斑马鱼": "Danio rerio — 鲤科。胚胎透明，适合发育生物学研究。高通量药物筛选模型。再生能力强(心脏、鳍)。",
    "果蝇": "Drosophila melanogaster — 双翅目。经典遗传学模型。生命周期极短(~10天)。约75%人类疾病基因有果蝇同源基因。",
    "线虫": "Caenorhabditis elegans — 线虫动物门。959个细胞，完整的细胞谱系图。RNAi筛选。寿命研究模型。",
    "犬": "Canis lupus familiaris — 食肉目。与人类共享环境，自发疾病模型。常用于：肿瘤学、心脏病学。",
    "猪": "Sus scrofa domesticus — 偶蹄目。器官大小和解剖结构接近人类。异种移植供体候选。常用：小型猪。",
    "非人灵长类": "猕猴(Macaca mulatta)等 — 灵长目。最接近人类的模型。用于：神经科学、疫苗开发、药物安全性评价。伦理要求严格。",
}


def _canonical_species() -> List[Dict[str, str]]:
    """从映射表提取去重后的规范物种列表（每个 MeSH 术语取第一个中文名）"""
    seen: Dict[str, str] = {}
    for name, mesh in SPECIES_MESH.items():
        if mesh not in seen:
            seen[mesh] = name
    return [{"name": name, "mesh": mesh} for mesh, name in seen.items()]


# ===================== NCBI E-utilities =====================
# 实现逻辑复用 agent/tools/pubmed_tools.py（_eutils_request / _parse_esearch / _parse_efetch）


def _eutils_request(endpoint: str, params: dict) -> str:
    """发送 E-utilities API 请求，含限速保护与 10s 超时"""
    params.setdefault("retmode", "xml")
    url = f"{PUBMED_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    time.sleep(REQUEST_DELAY)  # 遵守 NCBI 限速
    req = urllib.request.Request(url, headers={"User-Agent": "XiaoYuanAI/1.0"})
    with urllib.request.urlopen(req, timeout=EUTILS_TIMEOUT) as resp:
        return resp.read().decode("utf-8")


def _parse_esearch(xml_str: str) -> Dict:
    """解析 esearch 返回的 XML"""
    root = ET.fromstring(xml_str)
    count = int(root.findtext(".//Count", 0))
    id_list = [e.text for e in root.findall(".//Id")]
    return {"count": count, "ids": id_list}


def _parse_efetch(xml_str: str) -> List[Dict]:
    """解析 efetch 返回的 XML，提取文章信息"""
    root = ET.fromstring(xml_str)
    articles = []
    for article_elem in root.findall(".//PubmedArticle"):
        art = article_elem.find(".//Article")
        if art is None:
            continue
        title = art.findtext(".//ArticleTitle", "")
        abstract_elem = art.find(".//Abstract")
        abstract = ""
        if abstract_elem is not None:
            parts = abstract_elem.findall(".//AbstractText")
            abstract = " ".join(p.text or "" for p in parts)

        pmid = article_elem.findtext(".//PMID", "")
        journal = art.findtext(".//Journal/Title", "")
        pub_date_elem = art.find(".//Journal/JournalIssue/PubDate")
        year = pub_date_elem.findtext("Year", "") if pub_date_elem is not None else ""

        authors = []
        for au in art.findall(".//Author"):
            last = au.findtext("LastName", "")
            fore = au.findtext("ForeName", "")
            if last:
                authors.append(f"{last} {fore}".strip())

        articles.append({
            "pmid": pmid,
            "title": title,
            "journal": journal,
            "year": year,
            "authors": authors[:10],
            "abstract": abstract[:2000] if abstract else "无摘要",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return articles


# ===================== 端点 =====================


@router.get("/species")
def get_species() -> Dict:
    """物种导航：返回 {species: [{name, mesh}]}，name 为中文规范名，mesh 为 MeSH 术语"""
    return {"species": _canonical_species()}


@router.get("/search")
def search_pubmed(q: str, max_results: int = Query(10, alias="max")) -> Dict:
    """PubMed 文献检索：esearch 取 ID 列表 + efetch 取标题/作者/期刊/摘要

    - q: 检索关键词（如 'metformin diabetes'）
    - max: 返回条数，1-50，默认 10
    - 成功返回 {total, articles: [{pmid, title, authors, journal, year, abstract, url}]}
    - NCBI 不可达 / 解析失败时返回 502，不抛 500
    """
    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="检索关键词不能为空")
    max_results = min(max(max_results, 1), 50)

    try:
        # 第一步：esearch 按相关性取 PMID 列表
        search_xml = _eutils_request("esearch.fcgi", {
            "db": "pubmed", "term": q,
            "retmax": str(max_results), "sort": "relevance",
        })
        search_result = _parse_esearch(search_xml)

        if not search_result["ids"]:
            return {"total": 0, "articles": []}

        # 第二步：efetch 取文章详情（含摘要）
        fetch_xml = _eutils_request("efetch.fcgi", {
            "db": "pubmed",
            "id": ",".join(search_result["ids"]),
            "rettype": "abstract",
        })
        articles = _parse_efetch(fetch_xml)
        return {"total": search_result["count"], "articles": articles}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("PubMed 检索失败 q=%s: %s", q, e)
        raise HTTPException(
            status_code=502,
            detail="PubMed 检索失败，请稍后重试（可到对话中委派生命科学 Agent 检索）",
        )


class FeasibilityRequest(BaseModel):
    drug: str = Field(..., min_length=1, max_length=100, description="药物名称")
    disease: str = Field(..., min_length=1, max_length=100, description="疾病/适应症")


@router.post("/feasibility")
def assess_drug_feasibility(body: FeasibilityRequest) -> Dict:
    """药物可行性评估：LLM 综合判断 → {verdict: '高'|'中'|'低', reason, confidence}

    思路参考 agent/tools/pubmed_tools.py 的 assess_drug_feasibility：
    从证据充分度、安全性、机制合理性三个维度打分。
    """
    drug = body.drug.strip()
    disease = body.disease.strip()
    if not drug or not disease:
        raise HTTPException(status_code=400, detail="药物名称和疾病不能为空")

    prompt = (
        "你是医学与生命科学专家，请评估药物对疾病的可行性。\n\n"
        f"药物: {drug}\n"
        f"疾病/适应症: {disease}\n\n"
        "评估维度（综合 PubMed 临床证据、药理学机制、安全性信号）:\n"
        "1. 证据充分度：有无获批/临床试验/高质量研究支持\n"
        "2. 安全性：已知不良反应、毒性、禁忌症\n"
        "3. 机制合理性：作用靶点与疾病通路是否相关\n\n"
        "只返回 JSON（不要其他文字），格式: {\"verdict\": \"高\"|\"中\"|\"低\", "
        "\"confidence\": 0到1之间的小数, \"reason\": \"一段中文分析(2-4句话，说明依据)\"}\n"
        "verdict 含义: 高=证据充分可行性高, 中=证据有限需谨慎, 低=证据不足或风险高"
    )

    try:
        from yuanai_core.core.lc import call_llm
        from langchain_core.messages import HumanMessage

        result = call_llm(
            [HumanMessage(content=prompt)],
            model_name="deepseek-v4-pro",
            temperature=0.1,
        )
    except Exception as e:
        logger.warning("药物可行性评估 LLM 初始化失败: %s", e)
        raise HTTPException(status_code=502, detail="评估服务暂不可用（LLM 未配置），请稍后重试")

    if not result:
        raise HTTPException(status_code=502, detail="评估服务暂不可用（模型调用失败），请稍后重试")

    parsed = _parse_feasibility_json(result)
    verdict = parsed.get("verdict", "")
    if verdict not in ("高", "中", "低"):
        # 兜底：从文本中匹配
        for v in ("高", "中", "低"):
            if v in verdict:
                verdict = v
                break
        else:
            verdict = "中"
    try:
        confidence = float(parsed.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = min(max(confidence, 0.0), 1.0)
    reason = parsed.get("reason", "") or result[:500]

    return {"verdict": verdict, "reason": reason, "confidence": round(confidence, 2)}


def _parse_feasibility_json(text: str) -> Dict:
    """从 LLM 输出中稳健提取 JSON（容忍 markdown 代码块/前后缀文字）"""
    import json as _json
    import re

    text = text.strip()
    # 去掉 ```json ... ``` 代码块
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    else:
        # 提取第一个 { ... } 块
        brace = re.search(r"\{.*\}", text, re.S)
        if brace:
            text = brace.group(0)
    try:
        data = _json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        # 无法解析时从文本中抓取 verdict / confidence
        v = re.search(r"[\"']verdict[\"']\s*[:：]\s*[\"']([高中低])[\"']", text)
        c = re.search(r"[\"']confidence[\"']\s*[:：]\s*([0-9.]+)", text)
        return {
            "verdict": v.group(1) if v else "",
            "confidence": float(c.group(1)) if c else 0.5,
            "reason": text[:500],
        }
