"""AI 审核模块测试 Demo"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_1_check_file_exists():
    """测试 1：检查规范文件是否存在"""
    print("\n" + "="*50)
    print("测试 1：检查规范文件")
    print("="*50)
    
    from yuanai.rag import SPEC_FILE_PATH
    print(f"规范文件路径: {SPEC_FILE_PATH}")
    print(f"文件存在: {os.path.exists(SPEC_FILE_PATH)}")
    
    if not os.path.exists(SPEC_FILE_PATH):
        print("❌ 请手动创建: data/file/annotation_spec.txt")
    else:
        print("✅ 规范文件已存在")


def test_2_read_specs():
    """测试 2：读取规范内容"""
    print("\n" + "="*50)
    print("测试 2：读取规范内容")
    print("="*50)
    
    from yuanai.rag import get_all_specs
    
    specs = get_all_specs()
    print(f"规范内容长度: {len(specs)} 字符")
    
    if specs:
        print("✅ 规范内容读取成功")
    else:
        print("❌ 规范文件为空或不存在")


def test_3_rag_tools():
    """测试 3：RAG 工具"""
    print("\n" + "="*50)
    print("测试 3：RAG 工具")
    print("="*50)
    
    from yuanai.rag import retrieve_specification
    
    result = retrieve_specification("")
    print(f"检索全部规范: {len(result)} 字符")
    
    result2 = retrieve_specification("压线")
    print(f"检索压线: {len(result2)} 字符")


def test_4_audit_tools():
    """测试 4：审核工具"""
    print("\n" + "="*50)
    print("测试 4：审核工具")
    print("="*50)
    
    from yuanai.tools.audit_tools import (
        retrieve_annotation_spec,
        save_audit_feedback,
        get_audit_feedback,
        get_recent_feedbacks,
        analyze_audit_errors
    )
    
    spec = retrieve_annotation_spec("出框")
    print(f"retrieve_annotation_spec: {len(spec)} 字符")
    
    result = save_audit_feedback(
        image_id="test_001",
        ai_is_correct=False,
        ai_error_type="出框",
        user_is_correct=True,
        user_error_type="文本压线",
        reason="用户纠正测试"
    )
    print(f"save_audit_feedback: {result}")
    
    feedback = get_audit_feedback("test_001")
    print(f"get_audit_feedback: {feedback}")
    
    stats = get_recent_feedbacks(5)
    print(f"get_recent_feedbacks: {stats}")


def test_5_audit_core():
    """测试 5：审核核心"""
    print("\n" + "="*50)
    print("测试 5：审核核心")
    print("="*50)
    print("提示：以下测试需要真实图片，请在 uixiaoyuan 页面中测试")


def test_6_check_tools_loaded():
    """测试 6：检查工具是否正确加载"""
    print("\n" + "="*50)
    print("测试 6：检查工具加载")
    print("="*50)
    
    from yuanai.tools import all_tools
    
    tool_names = [t.name for t in all_tools]
    print(f"总工具数: {len(tool_names)}")
    
    audit_tools = [t for t in tool_names if 'audit' in t.lower() or 'spec' in t.lower()]
    print(f"审核相关工具: {audit_tools}")


def run_all_tests():
    """运行所有测试"""
    print("="*50)
    print("开始运行审核模块测试...")
    print("="*50)
    
    test_1_check_file_exists()
    test_2_read_specs()
    test_3_rag_tools()
    test_4_audit_tools()
    test_6_check_tools_loaded()
    test_5_audit_core()
    
    print("\n" + "="*50)
    print("所有测试完成！")
    print("="*50)
    print("""
下一步：在 Streamlit 中测试完整流程
  1. 启动: streamlit run streamlit_app.py
  2. 进入 uixiaoyuan 页面
  3. 选择任务 -> 开始任务
  4. 点击【ai审核】
  5. 在确认框中选择正确/错误
  6. 观察反馈是否保存成功
""")


if __name__ == "__main__":
    run_all_tests()