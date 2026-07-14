# VRChat MIDI Player

（当前版本 **1.2.0**），面向 VRChat 场景设计。可本地试听，也可通过虚拟 MIDI / OSC 把音符实时送到世界或虚拟人物。

---

## 功能概览

| 模块 | 说明 |
|------|------|
| MIDI 播放 | 加载 Format 0/1，进度条拖拽定位，变速约 0.1x–4x |
| 移调 | 播放移调、MIDI 输入移调（±12 半音） |
| 本地音频 | Windows 合成器（Microsoft GS Wavetable Synth）发声 |
| 虚拟 MIDI | 输出到 LoopMIDI / LoopBe1 等端口，供支持 VRC Midi Listener 的世界使用 |
| OSC | 控制 VRChat 虚拟人物（`/PianoKeys/` 或 `/avatar/parameters/`） |
| MIDI 输入 | 外部键盘直通到已启用的输出（可与文件播放配合） |
| 轨道滤波 | 按轨静音 / 独奏 |
| 曲库 | 添加文件或文件夹、拖拽导入、双击播放 |
| 界面 | 中/英切换、窗口置顶、自定义背景图（磨砂卡片可读） |
| 设置 | 窗口几何、输出开关、音量、端口等自动保存到本地 JSON |

---

## 环境要求

- **系统**：Windows 10 / 11
- **Python**：3.9+（从源码运行时）
- **可选外部工具**
  - [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)（或 LoopBe1，Win11 可用）— 虚拟 MIDI
  - VRChat 内开启 OSC — 虚拟人物控制

---

## 快速启动（源码）

### 一键启动

双击 `start.bat`（推荐），或右键 `start.ps1` →「使用 PowerShell 运行」。

首次运行会自动创建 `.venv` 并安装依赖。

### 手动启动

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## 在 VRChat 中怎么用

### 1. 本地音频

在「输出设置」中开启本地音频，即可用电脑扬声器试听（不依赖 VRChat）。

### 2. 虚拟 MIDI → 世界钢琴

1. 安装 loopMIDI（或 LoopBe1）并创建一个虚拟端口  
2. 进入带 VRC Midi Listener 的世界（可在世界菜单搜索 `MIDI Piano`）  
3. 本工具中启用「虚拟 MIDI」，选择对应端口并「应用」  
4. **注意**：MIDI 输入与虚拟输出不要使用同一个 loopMIDI 端口，否则可能形成环路  

### 3. OSC → 虚拟人物

1. VRChat 设置中启用 OSC  
2. 本工具中启用 OSC，地址默认 `127.0.0.1:9000`  
3. 选择模式：  
   - `/PianoKeys/` — 钢琴类 Avatar（如 Kade's Piano 等）  
   - `/avatar/parameters/` — 自定义浮点参数  

虚拟人物需具备相匹配的参数才能听到/看到效果。

---

## 打包为 EXE

```bash
# 或双击 build_exe.bat
.venv\Scripts\activate
pip install pyinstaller
pyinstaller midi_show.spec --noconfirm
```

完成后生成：

```text
dist\VRChat_MIDI_Player.exe
```

可直接双击运行，无需安装 Python。配置与曲库会写在 **exe 同目录**：

- `midi_show_config.json` — 窗口、语言、输出、背景路径等  
- `midi_show_library.json` — 曲库列表  

仓库中的 `*.sample.json` 仅为示例，不要提交你本机的真实配置。

重新生成图标（可选）：

```bash
python gen_icon.py
```

---

## 项目结构

```text
midi-show-main/
├── main.py                 # 入口
├── requirements.txt        # 依赖
├── start.bat / start.ps1   # 一键启动
├── build_exe.bat           # 一键打包
├── midi_show.spec          # PyInstaller 配置
├── gen_icon.py             # 生成 app_icon.ico
├── app_icon.ico            # 应用图标
├── midi_show_*.sample.json # 配置/曲库示例
└── midi_show/              # 核心包
    ├── ui.py               # Tkinter 界面
    ├── engine.py           # 播放引擎
    ├── outputs.py          # 本地 / 虚拟 MIDI / OSC / 输入
    ├── midi_parser.py      # MIDI 解析
    ├── library.py          # 曲库
    ├── settings.py         # 设置读写
    ├── i18n.py             # 中英双语
    └── icon_art.py         # 图标绘制（与 exe/标题栏共用）
```

---

## 依赖

见 `requirements.txt`：

| 包 | 用途 |
|----|------|
| mido | MIDI 解析 |
| python-rtmidi | MIDI 端口 I/O |
| python-osc | OSC 输出 |
| Pillow | 图标、界面背景 |
| tkinterdnd2 | 曲库拖拽导入 |

GUI 使用标准库 **Tkinter**。

---

## 许可证与说明

本项目用于个人学习与 VRChat 演出辅助。使用虚拟 MIDI / OSC 时请遵守 VRChat 与世界/Avatar 作者的相关规则。
