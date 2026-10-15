// 计划面板窗口协议 — 父子窗共用常量（防两侧漂移）

export const PLAN_PATH = '/chat/plan'
export const PLAN_WIN_NAME = 'yuanai_plan_panel'
export const PLAN_WIN_FEATURES = 'popup=1,width=1080,height=760,left=120,top=80'
export const PLAN_MSG = 'yuanai:plan'  // message 体 {type: PLAN_MSG, action: ...}

// 父窗 → 子窗：refresh（刷新列表并自动选中最新）；子窗 → 父窗：hello（握手）/ autoclose（终态自关预告）
export const isPlanLink = (p?: string) => !!p && p.split('?')[0] === PLAN_PATH
