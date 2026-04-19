import streamlit as st
import time

from yuanai.audit import audit_question_detail, AuditDetailResult
from yuanai.tools.audit_tools import save_audit_feedback


DEFAULT_MODEL = "doubao-seed-2-0-lite-260215"
SHARED_AUDIT_KEY = "pending_audit_result"

ERROR_TYPES = [
    '格式问题较多', '举报', '文本压线', '黄框压题干',
    '最终答案', '不独立', '出框', '少答案', '字太小', '答案错', '无'
]


class AIAuditTools:
    """AI 审核工具类 - 独立模块，可手动调用"""

    def __init__(self, sa_handler, model: str = DEFAULT_MODEL):
        """
        初始化
        :param sa_handler: SingleAuditHandler 实例
        :param model: 模型名称（默认豆包 Seed 多模态）
        """
        self.sa = sa_handler
        self.model = model
        self.image_id = None

    def run_audit(self, qa_images: list = None, model: str = None) -> AuditDetailResult:
        """
        执行 AI 审核（带完整详情）
        :param qa_images: 题目图片列表，默认从 session 获取
        :param model: 模型名称（可选，默认使用实例属性）
        :return: AuditDetailResult 审核结果
        """
        if qa_images is None:
            qa_images = st.session_state.get('xiao_yuan_qa', [])

        if not qa_images:
            return AuditDetailResult(
                is_correct=False,
                error_type="答案错",
                error_count=1,
                reason="获取题目图片失败",
                images=[],
                raw_response="",
                tool_used=[]
            )

        model = model or self.model
        self.image_id = f"audit_{int(time.time() * 1000)}"
        result = audit_question_detail(qa_images, model=model)
        result.image_id = self.image_id

        return result

    def show_ai_result(self, result: AuditDetailResult):
        """显示 AI 审核结果"""
        if result.is_correct:
            st.success(f"✅ AI 判断：正确")
            st.caption(f"原因: {result.reason}")
        else:
            st.error(f"❌ AI 判断：{result.error_type}，{result.error_count}处错误")
            st.caption(f"原因: {result.reason}")

    def collect_feedback(self, result: AuditDetailResult) -> bool:
        """
        收集人工反馈（无论AI判断正确/错误都需要用户确认）
        :param result: 审核结果
        :return: 用户是否确认AI判断正确
        """
        if result.image_id is None:
            result.image_id = f"audit_{int(time.time() * 1000)}"
        
        # 检查是否已完成反馈
        feedback_key = f"feedback_done_{result.image_id}"
        if st.session_state.get(feedback_key):
            st.success("✅ 反馈已提交")
            return st.session_state.get(f"feedback_confirmed_{result.image_id}", True)
        
        # 显示 AI 判断结果
        st.write("---")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if result.is_correct:
                st.success(f"✅ AI 判断：正确")
            else:
                st.error(f"❌ AI 判断：{result.error_type}")
            st.caption(f"原因: {result.reason}")
        
        # 让用户确认/纠正（无论AI判断如何都需要）
        with col2:
            user_confirms_ai = st.radio(
                "您认为AI判断是否正确？",
                ["✅ 正确", "❌ 错误，我来纠正"],
                horizontal=True,
                key=f"confirm_{result.image_id}"
            )
        
        # 根据用户选择，显示不同的选择项
        user_error_type = None
        if user_confirms_ai == "❌ 错误，我来纠正":
            user_error_type = st.selectbox(
                "👉 选择正确类型",
                ERROR_TYPES,
                key=f"error_{result.image_id}"
            )
        
        st.write("---")
        
        # 操作按钮（横向排列）
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            btn1_clicked = st.button(
                "📝 仅提交反馈",
                key=f"btn_feedback_{result.image_id}",
                use_container_width=True
            )
        with col_btn2:
            btn2_clicked = st.button(
                "⭐ 重点参考",
                key=f"btn_important_{result.image_id}",
                use_container_width=True
            )
        with col_btn3:
            btn3_clicked = st.button(
                "⚡ 不提交",
                key=f"btn_skip_{result.image_id}",
                use_container_width=True
            )
        
        # 处理逻辑
        if btn3_clicked:
            return result.is_correct
        
        if btn1_clicked or btn2_clicked:
            is_important = btn2_clicked
            
            # 用户判断
            user_is_correct = (user_confirms_ai == "✅ 正确")
            
            # 确定用户选择的错误类型
            final_user_error_type = None
            if not user_is_correct:
                final_user_error_type = user_error_type
            else:
                final_user_error_type = result.error_type
            
            # 获取用户的额外指导
            user_instruction = st.text_area(
                "💬 给AI的指导（可选）",
                placeholder="例如：这道题正确答案应该是xxx，注意看...",
                key=f"instruction_{result.image_id}"
            )
            
            # 构建完整原因
            reason_text = f"{'用户确认' if user_is_correct else '用户纠正: '+str(user_error_type)}"
            if user_instruction:
                reason_text += f" | 指导: {user_instruction}"
            
            try:
                save_audit_feedback(
                    image_id=result.image_id,
                    ai_is_correct=result.is_correct,
                    ai_error_type=result.error_type or "",
                    user_is_correct=user_is_correct,
                    user_error_type=final_user_error_type,
                    reason=reason_text,
                    is_important=is_important,
                    user_instruction=user_instruction
                )
                
                # 同步到AI对话框
                self.sync_feedback_to_chat(
                    result=result,
                    user_confirms=("✅ 正确" == user_confirms_ai),
                    user_error_type=final_user_error_type,
                    user_instruction=user_instruction,
                    is_important=is_important
                )
                
                # 标记已完成
                st.session_state[feedback_key] = True
                st.session_state[f"feedback_confirmed_{result.image_id}"] = user_is_correct
                
                if is_important:
                    st.success("✅ 反馈已保存（⭐ 重要参考，AI将学习调整）")
                else:
                    st.success("✅ 反馈已保存")
                    
            except Exception as e:
                st.error(f"保存失败: {e}")
                print(f"保存反馈失败: {e}")
            
            return user_is_correct
        
        return result.is_correct

    def handle_result(self, result: AuditDetailResult) -> bool:
        """
        根据审核结果执行相应操作
        :param result: 审核结果
        :return: 是否需要继续人工处理
        """
        if result.is_correct:
            st.success(f"✅ AI 判断：正确 - {result.reason}")
            self.sa.quick_true_handle()
            self.sa.question_restore()
            return True
        else:
            st.error(f"❌ AI 判断：{result.error_type}，{result.error_count}处错误")
            st.caption(f"原因: {result.reason}")

            if result.error_count > 2:
                st.warning("错误标注过多，执行整题驳回...")
                go_on = self.sa.compete('整题驳回', cause=result.error_type)
                if not go_on:
                    st.session_state.xiao_yuan_step = 1
                return False
            else:
                st.info(f"点击错误标注（{result.error_count}处）+ 人工确认...")
                return False

    def sync_to_ai_chat(self, result: AuditDetailResult):
        """
        将审核结果同步到 AI 聊天记录中
        :param result: 审核结果
        """
        # 存储到共享位置，供 yuanai/ui/ai.py 读取
        st.session_state[SHARED_AUDIT_KEY] = {
            "images": result.images,
            "result": {
                "is_correct": result.is_correct,
                "error_type": result.error_type,
                "error_count": result.error_count,
                "reason": result.reason,
            },
            "raw_response": result.raw_response,
            "tool_used": result.tool_used,
            "source": "xiao_yuan"
        }

    def sync_feedback_to_chat(
            self,
            result: AuditDetailResult,
            user_confirms: bool,
            user_error_type: str = None,
            user_instruction: str = "",
            is_important: bool = False
    ):
        """
        将用户反馈同步到 AI 聊天记录中
        """
        st.session_state[SHARED_AUDIT_KEY] = {
            "images": result.images[:2],  # 只传前2张图片
            "result": {
                "is_correct": result.is_correct,
                "error_type": result.error_type,
                "error_count": result.error_count,
                "reason": result.reason,
            },
            "user_feedback": {
                "confirms_ai": user_confirms,
                "user_error_type": user_error_type or result.error_type,
                "user_instruction": user_instruction,
                "is_important": is_important,
            },
            "raw_response": result.raw_response,
            "tool_used": result.tool_used,
            "source": "xiao_yuan",
            "is_feedback": True,  # 标记为反馈消息
        }

    def full_audit_flow(self, qa_images: list = None) -> AuditDetailResult:
        """
        完整的审核流程：审核 + 执行 + 同步
        :param qa_images: 题目图片列表
        :return: 审核结果
        """
        st.info("🤖 AI 正在审核...")
        try:
            result = self.run_audit(qa_images)

            # 同步到 AI 聊天界面
            self.sync_to_ai_chat(result)

            # 执行相应操作
            self.handle_result(result)

            return result
        except Exception as e:
            st.error(f"❌ AI 审核失败: {str(e)}")
            return AuditDetailResult(
                is_correct=False,
                error_type="答案错",
                error_count=1,
                reason=f"AI 审核失败: {str(e)}",
                images=[],
                raw_response="",
                tool_used=[]
            )


def ai_do_sa(sa_handler, qa_images: list = None, model: str = DEFAULT_MODEL) -> AuditDetailResult:
    """
    便捷函数：AI 审核单题标答
    :param sa_handler: SingleAuditHandler 实例
    :param qa_images: 题目图片列表（可选）
    :param model: 模型名称（默认豆包 Seed 多模态）
    :return: AuditDetailResult 审核结果
    """
    audit_tools = AIAuditTools(sa_handler, model=model)
    return audit_tools.full_audit_flow(qa_images)


if __name__ == '__main__':
    pass
