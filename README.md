# MIDI Show — VRChat MIDI Player

一款 Windows 桌面 MIDI 播放器，专为 VRChat 场景设计。支持本地音频播放、虚拟 MIDI 端口输出（VRChat 世界）和 OSC 协议（VRChat 虚拟人物控制）。

---

## 启动方式

### 一键启动

双击 `start.bat`（推荐）或右键 `start.ps1` → "使用 PowerShell 运行"。首次运行会自动创建虚拟环境并安装依赖。

### 手动启动

```bash
# 创建并激活虚拟环境（可选）
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动
python main.py
```

---

## 功能

- MIDI 文件播放（格式 0/1，支持实时调速 0.25x – 4x）
- **本地音频**：通过 Microsoft GS Wavetable Synth 发声
- **虚拟 MIDI 端口**：将音符事件发送到 VRChat 世界（需安装 LoopMIDI）
- **OSC 输出**：将音符发送到 VRChat 虚拟人物（支持 /PianoKeys/ 和 /avatar/parameters/ 两种模式）
- **MIDI 输入直通**：实时转发外部 MIDI 输入到所有输出
- **曲库管理**：添加/移除/浏览 MIDI 文件，双击播放
- **中/英双语界面**
- 进度条拖拽寻求、设置自动保存

---

## 项目结构

```
midi show/
├── main.py                         # 应用入口
├── requirements.txt                # Python 依赖
├── start.bat / start.ps1           # 一键启动脚本
├── midi_show/                      # 核心代码包
│   ├── engine.py                   # 播放引擎
│   ├── outputs.py                  # 输出模块 (Local/Virtual/OSC/Input)
│   ├── midi_parser.py              # MIDI 文件解析
│   ├── ui.py                       # Tkinter 用户界面
│   ├── settings.py                 # 设置持久化
│   ├── library.py                  # 曲库管理
│   └── i18n.py                     # 中/英双语
├── database/                       # 数据库脚本（预留）
├── doc/                            # 文档（预留）
├── prototype/                      # 产品原型（预留）
├── project/frontend/               # 前端（预留）
├── project/backend/                # 后端（预留）
└── utils/                          # 工具包（预留）
```

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| GUI | Tkinter (标准库) |
| MIDI 解析 | mido |
| MIDI 端口 | python-rtmidi |
| OSC 协议 | python-osc |

---

## 依赖

```bash
pip install mido python-rtmidi python-osc
```
