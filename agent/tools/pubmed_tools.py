"""
PubMed 文献检索工具 — 使用 NCBI E-utilities API（免费，无需 API Key）
文档: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""
import re
import time
import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
REQUEST_DELAY = 0.34  # NCBI 限速：每秒最多 3 次请求

# 物种 → MeSH 术语映射
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

# 常见物种的生物学/医学描述
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


def _eutils_request(endpoint: str, params: dict) -> str:
    """发送 E-utilities API 请求，含限速保护"""
    params.setdefault("retmode", "xml")
    url = f"{PUBMED_BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    time.sleep(REQUEST_DELAY)  # 遵守 NCBI 限速
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "XiaoYuanAI/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        logger.warning("PubMed API 请求失败: %s", e)
        raise


def _parse_esearch(xml_str: str) -> Dict:
    """解析 esearch 返回的 XML"""
    root = ET.fromstring(xml_str)
    count = int(root.findtext(".//Count", 0))
    id_list = [e.text for e in root.findall(".//Id")]
    webenv = root.findtext(".//WebEnv", "")
    querykey = root.findtext(".//QueryKey", "")
    return {"count": count, "ids": id_list, "webenv": webenv, "querykey": querykey}


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
            "authors": authors[:5],
            "abstract": abstract[:2000] if abstract else "无摘要",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return articles


# ===================== LangChain 工具 =====================

@tool
def search_pubmed(query: str, species: str = "", max_results: int = 10) -> str:
    """Search PubMed for biomedical literature. query: keywords e.g. 'metformin diabetes', species: optional Chinese name e.g. '人类' '小鼠', max_results: 1-50."""
    try:
        max_results = min(max(max_results, 1), 50)

        # 物种过滤
        full_query = query
        if species:
            mesh = SPECIES_MESH.get(species.strip(), "")
            if mesh:
                full_query = f'({query}) AND "{mesh}"[MeSH Terms]'
            else:
                # 尝试部分匹配
                matched = [m for s, m in SPECIES_MESH.items() if species.strip() in s]
                if matched:
                    mesh_terms = " OR ".join(f'"{m}"[MeSH Terms]' for m in matched[:3])
                    full_query = f'({query}) AND ({mesh_terms})'

        # 搜索
        search_xml = _eutils_request("esearch.fcgi", {
            "db": "pubmed", "term": full_query,
            "retmax": str(max_results), "sort": "relevance",
            "usehistory": "y",
        })
        search_result = _parse_esearch(search_xml)

        if not search_result["ids"]:
            return f"未找到与 '{query}' 相关的文献" + (f" (物种: {species})" if species else "")

        # 获取详情
        fetch_xml = _eutils_request("efetch.fcgi", {
            "db": "pubmed",
            "id": ",".join(search_result["ids"]),
            "rettype": "abstract",
        })
        articles = _parse_efetch(fetch_xml)

        header = f"PubMed 检索: {query}"
        if species:
            header += f" (物种: {species})"
        header += f"\n共 {search_result['count']} 篇, 显示前 {len(articles)} 篇\n"

        lines = [header]
        for i, art in enumerate(articles, 1):
            authors_str = ", ".join(art["authors"][:3])
            if len(art["authors"]) > 3:
                authors_str += " et al."
            lines.append(
                f"\n### {i}. {art['title']}\n"
                f"**期刊**: {art['journal']} ({art['year']}) | **PMID**: {art['pmid']}\n"
                f"**作者**: {authors_str}\n"
                f"**摘要**: {art['abstract'][:400]}...\n"
                f"**链接**: {art['url']}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"PubMed 检索失败: {e}"


@tool
def get_article_detail(pmid: str) -> str:
    """Get full abstract of a PubMed article by PMID. pmid: PubMed ID e.g. '38123456'."""
    try:
        fetch_xml = _eutils_request("efetch.fcgi", {
            "db": "pubmed", "id": pmid.strip(), "rettype": "abstract",
        })
        articles = _parse_efetch(fetch_xml)
        if not articles:
            return f"未找到 PMID {pmid} 的文献"

        art = articles[0]
        authors_str = ", ".join(art["authors"])
        return (
            f"## {art['title']}\n\n"
            f"**期刊**: {art['journal']} ({art['year']})\n"
            f"**PMID**: {art['pmid']}\n"
            f"**作者**: {authors_str}\n\n"
            f"**摘要**:\n{art['abstract']}\n\n"
            f"**链接**: {art['url']}"
        )
    except Exception as e:
        return f"获取文献失败: {e}"


@tool
def search_clinical_trials(condition: str, drug: str = "") -> str:
    """Search clinical trials on ClinicalTrials.gov. condition: disease e.g. 'diabetes', drug: optional drug name."""
    try:
        query_parts = [condition]
        if drug:
            query_parts.append(drug)

        search_xml = _eutils_request("esearch.fcgi", {
            "db": "pubmed",
            "term": f'({" AND ".join(query_parts)}) AND "Clinical Trial"[Publication Type]',
            "retmax": "10", "sort": "relevance",
        })
        search_result = _parse_esearch(search_xml)

        if not search_result["ids"]:
            return f"未找到关于 {condition}" + (f" 和 {drug}" if drug else "") + " 的临床试验文献"

        fetch_xml = _eutils_request("efetch.fcgi", {
            "db": "pubmed",
            "id": ",".join(search_result["ids"]),
            "rettype": "abstract",
        })
        articles = _parse_efetch(fetch_xml)

        lines = [f"临床试验: {condition}" + (f" + {drug}" if drug else "")]
        lines.append(f"共 {search_result['count']} 篇, 显示前 {len(articles)} 篇\n")
        for i, art in enumerate(articles, 1):
            authors_str = ", ".join(art["authors"][:2])
            if len(art["authors"]) > 2:
                authors_str += " et al."
            lines.append(f"### {i}. {art['title']}\n**{art['journal']}** ({art['year']}) | {authors_str}\nPMID: {art['pmid']}\n")

        return "\n".join(lines)
    except Exception as e:
        return f"临床试验检索失败: {e}"


@tool
def assess_drug_feasibility(drug_name: str, target_species: str, indication: str = "") -> str:
    """Assess drug feasibility for a target species. drug_name: drug, target_species: species name, indication: optional disease."""
    # 查找物种信息
    species_info = ""
    for name, info in SPECIES_INFO.items():
        if name in target_species or target_species in name:
            species_info = info
            break
    if not species_info:
        species_info = f"{target_species} — 信息有限，建议优先查阅人类和小鼠相关研究"

    # 快速检索 PubMed 获取不良反应和毒性数据
    feasibility = []
    try:
        mesh = SPECIES_MESH.get(target_species.strip(), "")
        species_term = mesh if mesh else target_species

        # 检索毒性
        tox_xml = _eutils_request("esearch.fcgi", {
            "db": "pubmed",
            "term": f'"{drug_name}" AND ("toxicity" OR "adverse") AND "{species_term}"[MeSH Terms]',
            "retmax": "3", "sort": "relevance",
        })
        tox_result = _parse_esearch(tox_xml)
        tox_count = tox_result["count"]

        # 检索有效性
        eff_xml = _eutils_request("esearch.fcgi", {
            "db": "pubmed",
            "term": f'"{drug_name}" AND "{species_term}"[MeSH Terms]' + (f' AND "{indication}"' if indication else ""),
            "retmax": "3", "sort": "relevance",
        })
        eff_result = _parse_esearch(eff_xml)
        eff_count = eff_result["count"]

        # 综合评估
        if eff_count == 0 and tox_count == 0:
            level = "⚪ 未知"
            verdict = "该药物在目标物种中缺乏研究数据，建议先从人类和小鼠研究推断"
        elif eff_count > 0 and tox_count == 0:
            level = "🟡 有效但安全性未知"
            verdict = f"有 {eff_count} 篇文献支持有效性，但缺乏毒性数据，需谨慎"
        elif eff_count > 0 and tox_count <= eff_count * 0.5:
            level = "🟢 较可行"
            verdict = f"有效性文献 {eff_count} 篇, 毒性报告 {tox_count} 篇。比例较好"
        elif eff_count > 0 and tox_count > eff_count * 0.5:
            level = "🟡 有风险"
            verdict = f"有效性文献 {eff_count} 篇, 但毒性报告 {tox_count} 篇。需权衡风险收益"
        elif tox_count > eff_count * 2:
            level = "🔴 高风险"
            verdict = f"毒性报告({tox_count}篇)远超有效性文献({eff_count}篇)，不建议"
        else:
            level = "⚪ 数据不足"

    except Exception:
        level = "⚪ 无法评估"
        verdict = "数据库访问失败，请稍后重试"

    return (
        f"## {drug_name} 对 {target_species} 的可行性评估\n\n"
        f"**评估结果**: {level}\n\n"
        f"**分析**: {verdict}\n\n"
        f"**物种信息**: {species_info}\n\n"
        + (f"**适应症**: {indication}\n\n" if indication else "")
        + "**注意事项**:\n"
        "1. 本评估基于 PubMed 文献数量和毒性报告比例的粗略判断\n"
        "2. 不同给药途径(口服/注射/外用)安全性差异巨大\n"
        "3. 动物模型结果不能完全外推到人类\n"
        "4. 建议查阅完整文献和临床数据后做出决策"
    )


@tool
def get_species_info(species_name: str) -> str:
    """Get biological and medical info for a species. species_name: Chinese or English name."""
    for name, info in SPECIES_INFO.items():
        if name in species_name or species_name.lower() in name.lower():
            return f"**{name}**:\n{info}"

    # 尝试模糊匹配
    for name, info in SPECIES_INFO.items():
        if any(word in species_name for word in name.split()):
            return f"**{name}** (模糊匹配):\n{info}"

    return (
        f"物种 '{species_name}' 未在常用模型生物数据库中。\n"
        "常用物种: 人类, 小鼠, 大鼠, 斑马鱼, 果蝇, 线虫, 犬, 猫, 猪, 兔, 酵母, 大肠杆菌\n"
        f"可尝试: search_pubmed(query='{species_name}', max_results=5) 来检索相关文献"
    )
