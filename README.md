# 粘贴工具



适用于在Windows上将粘贴改为模拟输入的工具，适用于一些不合理限制粘贴的地方。

## 快速开始

启动程序：
```bash
python paste_tool.py
```

启动程序并保留控制台窗口：
```bash
python paste_tool.py -win
```
### 开发环境

Python 3.13.11
其他依赖请见 `requirements.txt`

## 工作原理

### 悬浮提示窗口

悬浮提示窗口用于告知用户当前服务正在工作，通知告知用户即将粘贴的内容、正在粘贴的进度。


#### 光标定位

程序使用两种方式获取输入光标位置：

1. UI Automation TextPattern（优先）
   - 适用于现代应用（UWP、WPF、Electron 等）
   - 通过 `ITextProvider.GetSelection()` 获取光标位置

2. GetGUIThreadInfo + ClientToScreen（回退）
   - 适用于 Win32 标准控件
   - 通过 `GUITHREADINFO.hwndCaret` 和 `rcCaret` 获取光标位置

当两种方式都无法获取光标位置时，悬浮窗自动隐藏。




#### 显示效果

在位置右小角（x+40，y+40）作为窗口左上角坐标，以一行的内容显示剪贴板最新一条数据的前几个字符（根据窗口宽度自动省略），然后显示一共有几段、几个字，像这样

<div style="width:360px; padding:8px 10px; border:1px solid #ddd; border-radius:10px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial; background:#fff;">
  <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
    <span style="font-size:16px; line-height:1; color:#000;">沉舟沉舟侧畔千帆过，病树前头万木...</span>
    <span style="font-size:13px; line-height:1; color:#666;">
      <span style="color:#ccc;">|</span> 2段 <span style="color:#ccc;">|</span> 400字 
    </span>
  </div>
  <div style="font-size:14px; line-height:1.8; color:#333;">
    在粘贴前请检查输入法语言是否正确，输入位置是否正确
  </div>
</div>


第二行是提醒，如果剪贴板中没有内容，则窗口只有提示一行。在程序工作期间，会跟随输入光标焦点一直显示。（输入过程中不跟随光标移动）
当按下 **CTRL+V** 时，按段显示，显示正在粘贴的，还有剩余几段，比如粘贴第一段的时候显示


<div style="width:360px; padding:8px 10px; border:1px solid #ddd; border-radius:10px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial; background:#fff;">
  
  <!-- 顶部状态 -->
  <div style="font-size:12px; line-height:1.4; color:#999; margin-bottom:6px;">
    正在输入
  </div>

  <!-- 主内容行 -->
  <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
    <span style="font-size:17px; line-height:1; color:#000;">
      沉舟侧畔千帆过，病树前头万木春。...
    </span>
    <span style="font-size:13px; line-height:1; color:#666; white-space:nowrap;">
      剩余 1 段
    </span>
  </div>
</div>

输入之后输入第二段

<div style="width:360px; padding:8px 10px; border:1px solid #ddd; border-radius:10px; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial; background:#fff;">
  
  <!-- 顶部状态 -->
  <div style="font-size:12px; line-height:1.4; color:#999; margin-bottom:6px;">
    正在输入
  </div>

  <!-- 主内容行 -->
  <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
    <span style="font-size:17px; line-height:1; color:#000;">
      国破山河在，城春草木深。感时花溅...
    </span>
    <span style="font-size:13px; line-height:1; color:#666; white-space:nowrap;">
      剩余 0 段
    </span>
  </div>
</div>

#### 其他功能

1. 窗口支持鼠标拖动；
2. 窗口大小，剪贴板内容、“在粘贴前..是否正确”提示语、“正在输入”提示语、正在输入内容的提示的字号可以通过配置文件设置；
3. 可通过托盘关闭悬浮提示窗；


### Ctrl+V 捕获

使用 `keyboard` 库的全局键盘钩子实现：

1. **注册钩子**：调用 `keyboard.hook(callback, suppress=True)` 注册全局键盘事件回调，`suppress=True` 允许回调返回 `False` 时抑制按键事件。

2. **事件回调**：每次按键都会触发回调，回调接收一个 `event` 对象，包含 `name`（按键名）、`event_type`（down/up）。

3. **追踪 Ctrl 状态**：在回调中监听 Ctrl 键的 down/up 事件，维护 `_ctrl_pressed` 标记，因为单独的 V 键事件无法知道 Ctrl 是否按下。

4. **检测 Ctrl+V**：当 `event.name == 'v'` 且 Ctrl 处于按下状态时，判定为 Ctrl+V。

5. **抑制按键**：回调返回 `False` 时，该按键事件被抑制（不会传递给目标窗口）。V 键的 down 和 up 事件都需要抑制，避免残留。

6. **放行条件**：
   - 剪贴板非文本时返回 `True` 放行，让正常粘贴生效
   - 服务暂停时放行
   - 模拟输入期间放行（避免自己的模拟输入被拦截）


### 输入逻辑


使用 Windows API SendInput + KEYEVENTF_UNICODE 实现：

1. SendInput 函数：Windows 提供的模拟输入 API，可以发送键盘、鼠标等输入事件。
2. KEYEVENTF_UNICODE 标志：表示输入的是 Unicode 字符码，而非虚拟键码。这样可以直接输入任意字符（包括中文），无需关心键盘布局。
3. 逐字符发送：遍历文本的每个字符，获取其 Unicode 码点（ord(char)），然后发送一个 key down + key up 事件对。
4. 代理对处理：对于 U+10000 以上的字符（如 emoji），需要拆分成 UTF-16 代理对（高代理 + 低代理），分别发送两个事件。
5. 间隔延时：每字符间隔 5ms，避免输入过快导致目标应用丢失字符。
6. 结构体定义：INPUT 结构体包含 type（输入类型）和嵌套的 KEYBDINPUT 结构体（包含 wVk、wScan、dwFlags 等字段）。

> 并不是像上一个版本那样完全模拟键盘按键输入，因此也不受输入法影响。

### 托盘

程序启动后以托盘运行（开发过程中添加 -win 参数保留控制台），托盘可以设置服务的暂停、开始（启动时默认开启）、程序的退出。

工作时图标 `enabe.ico` ，暂停时图标 `disabe.ico` （图标由 *豆包* 生成）

### 配置文件

程序通过 `config.json` 配置，首次运行自动生成默认配置：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `window_width` | int | 400 | 悬浮窗宽度（像素） |
| `window_height` | int | 60 | 悬浮窗高度（像素） |
| `font_name` | string | "Microsoft YaHei" | 字体名称 |
| `tip_font_size` | int | 12 | 提示语字号 |
| `clipboard_font_size` | int | 14 | 剪贴板内容字号 |
| `paste_tip_font_size` | int | 12 | "正在输入"提示字号 |
| `paste_content_font_size` | int | 14 | 粘贴时内容字号 |
| `window_opacity` | int | 230 | 窗口透明度（0-255，越大越不透明） |
| `window_corner_radius` | int | 12 | 窗口圆角半径（像素） |
| `line_spacing` | int | 6 | 行间距（像素） |
| `show_tip_window` | bool | true | 是否显示悬浮窗 |

### 快捷键

| 快捷键 | 条件 | 功能 |
|--------|------|------|
| Ctrl+V | 服务运行中 + 剪贴板有文本 | 模拟键盘输入（逐字符） |
| Ctrl+V → V | 服务工作时，1秒内再次按 V （不松 Ctrl）| 暂停服务 |
| Ctrl+C → C | 服务暂停时，1秒内再次按 C（不松 Ctrl） | 启用服务 |

## 实际效果

![演示](/attachment/demonstration.gif)

## 提示

请不要在 VS Code 等编辑器中使用，因为这些编辑器在换行的时候一般会自动调整行缩进。

## 开源许可

GPL v3
