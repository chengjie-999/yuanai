"""语音 StartVoiceChat 联调工具：本机直连火山 API 验证请求体

用法：python -m api.v1.voice.debug_start
读取 .env 凭据 → 构造与生产完全一致的请求体 → 调 StartVoiceChat →
打印响应 → 成功后立即 StopVoiceChat 清理（避免残留任务计费）。
"""

import json
import logging
import sys
import uuid

logging.basicConfig(level=logging.WARNING)  # 静默内部日志，只看结果

from api.v1.voice.router import _build_start_body, _call_rtc_api
from config.settings import VOLCANO_RTC_APP_ID


def main():
    if not VOLCANO_RTC_APP_ID:
        print("未配置 VOLCANO_RTC_APP_ID，请先填 .env")
        sys.exit(1)

    app_id = VOLCANO_RTC_APP_ID
    room_id = uuid.uuid4().hex
    task_id = uuid.uuid4().hex
    rtc_user_id = "debuguser"

    body = _build_start_body(app_id, room_id, task_id, rtc_user_id)
    print("=== 请求体 ===")
    print(json.dumps(body, ensure_ascii=False, indent=2))
    print("=== 响应 ===")
    try:
        resp = _call_rtc_api("StartVoiceChat", body)
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        print("=== StartVoiceChat 成功，清理任务 ===")
        _call_rtc_api("StopVoiceChat", {"AppId": app_id, "RoomId": room_id, "TaskId": task_id})
        print("StopVoiceChat 完成")
    except Exception as e:
        print(f"调用失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
