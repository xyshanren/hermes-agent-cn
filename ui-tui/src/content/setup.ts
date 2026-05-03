import type { PanelSection } from '../types.js'

export const SETUP_REQUIRED_TITLE = '需要配置'

export const buildSetupRequiredSections = (): PanelSection[] => [
  {
    text: 'Hermes 需要先配置模型提供商，TUI 才能启动会话。'
  },
  {
    rows: [
      ['/model', '在当前位置配置提供商 + 模型'],
      ['/setup', '在当前位置运行首次设置向导'],
      ['Ctrl+C', '退出并运行 `hermes setup` 手动设置']
    ],
    title: '操作'
  }
]
