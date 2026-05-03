import { isMac, isRemoteShell } from '../lib/platform.js'

const action = isMac ? 'Cmd' : 'Ctrl'
const paste = isMac ? 'Cmd' : 'Alt'

const copyHotkeys: [string, string][] = isMac
  ? [
      ['Cmd+C', '复制选中内容'],
      ['Ctrl+C', '中断 / 清空草稿 / 退出']
    ]
  : isRemoteShell()
    ? [
        ['Cmd+C', '终端转发时的复制选中'],
        ['Ctrl+C', '复制选中 / 中断 / 清空草稿 / 退出']
      ]
    : [['Ctrl+C', '复制选中 / 中断 / 清空草稿 / 退出']]

export const HOTKEYS: [string, string][] = [
  ...copyHotkeys,
  [action + '+D', '退出'],
  [action + '+G / Alt+G', '打开编辑器 $EDITOR（Alt+G 作为 VSCode/Cursor 备选）'],
  [action + '+L', '重绘 / 刷新画面'],
  [paste + '+V / /paste', '粘贴文本；/paste 附带粘贴剪贴板图片'],
  ['Tab', '应用自动补全'],
  ['↑/↓', '补全 / 队列编辑 / 历史记录'],
  ['Ctrl+X', '删除正在编辑的排队消息（Esc 取消编辑）'],
  [action + '+A/E', '行首 / 行尾'],
  [action + '+Z / ' + action + '+Y', '撤销 / 重做输入编辑'],
  [action + '+W', '删除单词'],
  [action + '+U/K', '删除到行首 / 行尾'],
  [action + '+←/→', '跳跃单词'],
  ['Home/End', '行首 / 行尾'],
  ['Shift+Enter / Alt+Enter', '插入换行'],
  ['\\+Enter', '多行续写（备选）'],
  ['!<cmd>', '执行 Shell 命令（如 !ls, !git status）'],
  ['{!<cmd>}', '内联插入 Shell 输出（如 "当前分支是 {!git branch --show-current}"）']
]
