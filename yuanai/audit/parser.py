import json
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class AuditResult:
    is_correct: bool
    error_type: Optional[str]
    error_count: int
    reason: str


ERROR_TYPES = [
    '格式问题较多', '举报', '文本压线', '黄框压题干',
    '最终答案', '不独立', '出框', '少答案', '字太小', '答案错'
]


def parse_audit_result(ai_response: str) -> AuditResult:
    """
    解析 AI 返回的审核结果
    :param ai_response: AI 模型返回的文本
    :return: AuditResult 对象
    """
    ai_response = ai_response.strip()

    # 尝试提取 JSON
    json_data = extract_json(ai_response)
    if json_data:
        return parse_json_result(json_data)

    # 降级：正则匹配简单判断
    return parse_text_result(ai_response)


def extract_json(text: str) -> Optional[dict]:
    """从文本中提取 JSON，支持嵌套对象"""
    # 先尝试 ```json ... ``` 代码块
    for pattern in [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```']:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    # Brace-matching: 从第一个 { 开始，计数匹配 }
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    break

    # 降级：尝试直接解析整个文本
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_json_result(data: dict) -> AuditResult:
    """解析 JSON 格式结果"""
    is_correct = data.get('is_correct', True)
    error_type = data.get('error_type')
    error_count = data.get('error_count', 0)
    reason = data.get('reason', '')

    # 校验 error_type 是否在允许列表中
    if error_type and error_type not in ERROR_TYPES:
        error_type = normalize_error_type(error_type)

    return AuditResult(
        is_correct=is_correct,
        error_type=error_type,
        error_count=error_count,
        reason=reason or 'AI 判断完成'
    )


def parse_text_result(text: str) -> AuditResult:
    """从文本中提取判断结果（降级方案）"""
    text_lower = text.lower()

    # 判断正确性
    is_correct = any(word in text_lower for word in ['正确', '通过', 'ok', 'yes', 'true'])

    # 提取错误类型
    error_type = None
    for et in ERROR_TYPES:
        if et in text:
            error_type = et
            break

    # 提取错误数量
    error_count = 0
    count_match = re.search(r'(\d+)\s*个?错误', text)
    if count_match:
        error_count = int(count_match.group(1))
    elif '错误' in text:
        error_count = 1 if error_type else 1

    return AuditResult(
        is_correct=is_correct,
        error_type=error_type,
        error_count=error_count,
        reason=text[:200]
    )


def normalize_error_type(error_type: str) -> str:
    """标准化错误类型"""
    error_type = error_type.strip()

    mapping = {
        '格式': '格式问题较多',
        '压线': '文本压线',
        '压题干': '黄框压题干',
        '遗漏': '少答案',
        '黄框内内容出界': '出框',
        '答案错误': '答案错',
    }

    for key, value in mapping.items():
        if key in error_type:
            return value

    return error_type


if __name__ == '__main__':
    # 测试用例
    test_cases = [
        '{"is_correct": true, "reason": "标注正确"}',
        '{"is_correct": false, "error_type": "文本压线", "error_count": 1}',
        '标注正确，可以提交',
        '有文本压线问题，需要修正',
    ]

    for tc in test_cases:
        result = parse_audit_result(tc)
        print(f"输入: {tc[:50]}")
        print(f"结果: {result}")
        print()