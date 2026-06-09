# -*- coding: utf-8 -*-
"""
粘贴工具 - 在Windows上将粘贴改为模拟输入
适用于一些限制粘贴的地方
"""

import os
import json
import ctypes
import ctypes.wintypes
import time
import threading
import argparse
import keyboard
import win32api
import win32con
import win32clipboard
import win32process

# ====== ctypes 基础 ======
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_ssize_t
HWND = ctypes.c_void_p
UINT = ctypes.c_uint
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)

# 常量
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_CONTROL = 0x11
VK_V = 0x56
LLKHF_INJECTED = 0x10
WM_PAINT = 0x000F
WM_DESTROY = 0x0002
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEMOVE = 0x0200
WM_TIMER = 0x0113
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
SW_SHOWNOACTIVATE = 4
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x02

# 自定义窗口消息（跨线程控制提示窗口）
WM_TIP_SHOW = 0x0401
WM_TIP_HIDE = 0x0402
WM_TIP_UPDATE = 0x0403
WM_TIP_MOVE = 0x0404
WM_TIP_DRAGGED = 0x0405  # 用户拖动了窗口


# ====== 结构体 ======
class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", ctypes.c_wchar_p), ("lpszClassName", ctypes.c_wchar_p),
    ]

class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", ctypes.c_void_p), ("fErase", ctypes.c_int), ("rcPaint", ctypes.c_long * 4),
        ("fRestore", ctypes.c_int), ("fIncUpdate", ctypes.c_int), ("rgbReserved", ctypes.c_byte * 32),
    ]

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong), ("flags", ctypes.c_ulong), ("hwndActive", ctypes.c_void_p),
        ("hwndFocus", ctypes.c_void_p), ("hwndCapture", ctypes.c_void_p), ("hwndMenuOwner", ctypes.c_void_p),
        ("hwndMoveSize", ctypes.c_void_p), ("hwndCaret", ctypes.c_void_p), ("rcCaret", ctypes.c_long * 4),
    ]

class LOGFONTW(ctypes.Structure):
    _fields_ = [
        ("lfHeight", ctypes.c_long), ("lfWidth", ctypes.c_long), ("lfEscapement", ctypes.c_long),
        ("lfOrientation", ctypes.c_long), ("lfWeight", ctypes.c_long), ("lfItalic", ctypes.c_byte),
        ("lfUnderline", ctypes.c_byte), ("lfStrikeOut", ctypes.c_byte), ("lfCharSet", ctypes.c_byte),
        ("lfOutPrecision", ctypes.c_byte), ("lfClipPrecision", ctypes.c_byte), ("lfQuality", ctypes.c_byte),
        ("lfPitchAndFamily", ctypes.c_byte), ("lfFaceName", ctypes.c_wchar * 32),
    ]

class TEXTMETRIC(ctypes.Structure):
    _fields_ = [
        ("tmHeight", ctypes.c_long), ("tmAscent", ctypes.c_long), ("tmDescent", ctypes.c_long),
        ("tmInternalLeading", ctypes.c_long), ("tmExternalLeading", ctypes.c_long),
        ("tmAveCharWidth", ctypes.c_long), ("tmMaxCharWidth", ctypes.c_long), ("tmWeight", ctypes.c_long),
        ("tmOverhang", ctypes.c_long), ("tmDigitizedAspectX", ctypes.c_long),
        ("tmDigitizedAspectY", ctypes.c_long), ("tmFirstChar", ctypes.c_wchar),
        ("tmLastChar", ctypes.c_wchar), ("tmDefaultChar", ctypes.c_wchar),
        ("tmBreakChar", ctypes.c_wchar), ("tmItalic", ctypes.c_byte), ("tmUnderlined", ctypes.c_byte),
        ("tmStruckOut", ctypes.c_byte), ("tmPitchAndFamily", ctypes.c_byte), ("tmCharSet", ctypes.c_byte),
    ]

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", ctypes.c_ulong), ("scanCode", ctypes.c_ulong), ("flags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]

LOWLEVELKEYBOARDPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', ctypes.wintypes.WORD), ('wScan', ctypes.wintypes.WORD),
                ('dwFlags', ctypes.wintypes.DWORD), ('time', ctypes.wintypes.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', ctypes.c_long), ('dy', ctypes.c_long), ('mouseData', ctypes.wintypes.DWORD),
                ('dwFlags', ctypes.wintypes.DWORD), ('time', ctypes.wintypes.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', ctypes.wintypes.DWORD), ('wParamL', ctypes.wintypes.WORD),
                ('wParamH', ctypes.wintypes.WORD)]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [('type', ctypes.wintypes.DWORD), ('union', _INPUT_UNION)]

# 函数签名
user32.SendInput.restype = ctypes.c_uint
user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
gdi32.TextOutW.restype = ctypes.c_int
gdi32.TextOutW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p, ctypes.c_int]
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [HWND, UINT, WPARAM, LPARAM]
gdi32.GetTextExtentPoint32W.restype = ctypes.c_int
gdi32.GetTextExtentPoint32W.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int, ctypes.POINTER(ctypes.wintypes.SIZE)]
gdi32.GetTextMetricsW.restype = ctypes.c_int
gdi32.GetTextMetricsW.argtypes = [ctypes.c_void_p, ctypes.POINTER(TEXTMETRIC)]


# ====== 配置 ======
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DEFAULT_CONFIG = {
    "window_width": 400, "window_height": 60, "font_name": "Microsoft YaHei",
    "tip_font_size": 12, "clipboard_font_size": 14,
    "paste_tip_font_size": 12, "paste_content_font_size": 14,
    "window_opacity": 230, "window_corner_radius": 12, "line_spacing": 6,
    "show_tip_window": True,
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config.update(json.load(f))
        except Exception:
            pass
    return config

def save_config(config):
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ====== 光标追踪 ======
class CaretTracker:
    """光标位置追踪，只在焦点窗口或前台窗口变化时返回新位置"""

    def __init__(self):
        self._uia = None
        self._uia_mod = None
        self._last_pos = None
        self._last_focus_hwnd = None
        self._last_fg_hwnd = None
        self._init_done = False

    def init_uia(self):
        """在主线程预先初始化UIA，避免在钩子回调时初始化导致GIL问题"""
        if self._init_done:
            return
        self._init_done = True
        try:
            import comtypes.client
            self._uia_mod = comtypes.client.GetModule('UIAutomationCore.dll')
            self._uia = comtypes.client.CreateObject(self._uia_mod.CUIAutomation)
        except Exception:
            self._uia = None

    def get_caret_pos(self):
        """获取光标屏幕坐标，返回 (x, y) 或 None"""
        # 方法1：UI Automation TextPattern
        if self._uia:
            try:
                element = self._uia.GetFocusedElement()
                unknown = element.GetCurrentPattern(self._uia_mod.UIA_TextPatternId)
                if unknown:
                    tp = unknown.QueryInterface(self._uia_mod.IUIAutomationTextPattern)
                    selection = tp.GetSelection()
                    if selection.Length > 0:
                        rng = selection.GetElement(0)
                        rects = rng.GetBoundingRectangles()
                        if len(rects) >= 4:
                            return (int(rects[0]), int(rects[1] + rects[3]))
            except Exception:
                pass

        # 方法2：GetGUIThreadInfo
        for tid in [0, win32process.GetWindowThreadProcessId(user32.GetForegroundWindow())[1]]:
            try:
                gui_info = GUITHREADINFO()
                gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
                result = user32.GetGUIThreadInfo(tid, ctypes.byref(gui_info))
                if result and gui_info.hwndCaret:
                    point = ctypes.wintypes.POINT(gui_info.rcCaret[0], gui_info.rcCaret[1])
                    user32.ClientToScreen(gui_info.hwndCaret, ctypes.byref(point))
                    return (point.x, point.y)
            except Exception:
                pass
        return None

    def get_focus_hwnd(self):
        """获取当前焦点窗口句柄"""
        try:
            gui_info = GUITHREADINFO()
            gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
            tid = win32process.GetWindowThreadProcessId(user32.GetForegroundWindow())[1]
            result = user32.GetGUIThreadInfo(tid, ctypes.byref(gui_info))
            if result:
                return gui_info.hwndFocus or gui_info.hwndCaret
        except Exception:
            pass
        return None

    def check_changed(self):
        """焦点窗口、前台窗口、或光标位置显著变化时返回新光标位置"""
        focus_hwnd = self.get_focus_hwnd()
        fg_hwnd = user32.GetForegroundWindow()

        focus_changed = (focus_hwnd != self._last_focus_hwnd or
                         fg_hwnd != self._last_fg_hwnd)

        self._last_focus_hwnd = focus_hwnd
        self._last_fg_hwnd = fg_hwnd

        # 获取当前光标位置
        pos = self.get_caret_pos()

        # 检测光标位置是否显著变化（超过30像素，排除打字时的小幅移动）
        caret_moved = False
        if pos is not None and self._last_pos is not None:
            dx = abs(pos[0] - self._last_pos[0])
            dy = abs(pos[1] - self._last_pos[1])
            if dx > 30 or dy > 30:
                caret_moved = True
        elif pos is not None and self._last_pos is None:
            # 从无光标到有光标
            caret_moved = True
        elif pos is None and self._last_pos is not None:
            # 光标消失
            caret_moved = True

        if focus_changed or caret_moved:
            self._last_pos = pos
            return pos, focus_changed
        return None, False


# ====== 提示窗口（独立线程+消息泵） ======
class TipWindow:
    """提示窗口，运行在独立线程，有自己的消息泵"""

    CLASS_NAME = "PasteToolTipWindow"

    # 行类型
    LINE_PREVIEW = 0
    LINE_TIP = 1
    LINE_PASTE_TIP = 2
    LINE_PASTE_CONTENT = 3

    def __init__(self, config):
        self.config = config
        self.hwnd = None
        self._thread = None
        self._ready = threading.Event()
        self._wnd_proc_callback = None
        self.draw_lines = []
        self._target_x = 0
        self._target_y = 0
        self._dragging = False
        self._drag_mouse_start = (0, 0)
        self._drag_window_start = (0, 0)
        self._drag_moved = False  # 拖动过程中是否真正移动了
        self.visible = False
        self.on_dragged = None  # 回调：用户拖动了窗口

    def start(self):
        """启动窗口线程"""
        self._thread = threading.Thread(target=self._thread_func, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def _thread_func(self):
        """窗口线程：注册类、创建窗口、运行消息泵"""
        hinstance = kernel32.GetModuleHandleW(None)
        self._wnd_proc_callback = WNDPROC(self._wnd_proc)

        wc = WNDCLASSW()
        wc.style = 0x0003
        wc.lpfnWndProc = self._wnd_proc_callback
        wc.hInstance = hinstance
        wc.hCursor = user32.LoadCursorW(0, 32512)
        wc.hbrBackground = user32.GetSysColorBrush(5)
        wc.lpszClassName = self.CLASS_NAME
        user32.RegisterClassW(ctypes.byref(wc))

        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED,
            self.CLASS_NAME, "",
            0x80000000,  # WS_POPUP（无边框）
            0, 0, 100, 50, 0, 0, hinstance, None
        )
        # 设置半透明
        opacity = self.config.get("window_opacity", 230)
        user32.SetLayeredWindowAttributes(self.hwnd, 0, opacity, LWA_ALPHA)
        self._ready.set()

        # 消息泵
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    @staticmethod
    def _signed_coords(lparam):
        """从lparam提取有符号16位坐标"""
        x = lparam & 0xFFFF
        y = (lparam >> 16) & 0xFFFF
        if x > 32767: x -= 65536
        if y > 32767: y -= 65536
        return (x, y)

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        try:
            return self._wnd_proc_inner(hwnd, msg, wparam, lparam)
        except Exception:
            # 防止异常导致消息泵崩溃
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _wnd_proc_inner(self, hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            self._on_paint(hwnd)
            return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        elif msg == WM_LBUTTONDOWN:
            self._dragging = True
            self._drag_moved = False
            # 用屏幕坐标计算偏移，避免负坐标问题
            pt = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            self._drag_mouse_start = (pt.x, pt.y)
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            self._drag_window_start = (rect.left, rect.top)
            user32.SetCapture(hwnd)
            return 0
        elif msg == WM_MOUSEMOVE:
            if self._dragging:
                pt = ctypes.wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                dx = pt.x - self._drag_mouse_start[0]
                dy = pt.y - self._drag_mouse_start[1]
                if abs(dx) > 3 or abs(dy) > 3:
                    self._drag_moved = True
                if self._drag_moved:
                    nx = self._drag_window_start[0] + dx
                    ny = self._drag_window_start[1] + dy
                    user32.SetWindowPos(hwnd, 0, nx, ny, 0, 0,
                                        SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
            return 0
        elif msg == WM_LBUTTONUP:
            if self._dragging:
                self._dragging = False
                user32.ReleaseCapture()
                if self._drag_moved and self.on_dragged:
                    self.on_dragged()
            return 0
        elif msg == WM_TIP_SHOW:
            self._do_show()
            return 0
        elif msg == WM_TIP_HIDE:
            self._do_hide()
            return 0
        elif msg == WM_TIP_UPDATE:
            self._do_update_content()
            return 0
        elif msg == WM_TIP_MOVE:
            self._do_move(wparam, lparam)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # ---- 从其他线程调用的方法（通过PostMessage） ----

    def show(self, x, y, lines):
        """显示窗口在指定位置（线程安全）"""
        self._target_x = x
        self._target_y = y
        self.draw_lines = lines
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_TIP_SHOW, 0, 0)

    def hide(self):
        """隐藏窗口（线程安全）"""
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_TIP_HIDE, 0, 0)

    def update_content(self, lines):
        """更新内容（线程安全）"""
        self.draw_lines = lines
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_TIP_UPDATE, 0, 0)

    def move(self, x, y):
        """移动窗口（线程安全）"""
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_TIP_MOVE, x, y)

    # ---- 在窗口线程中执行 ----

    def _do_show(self):
        w = self.config.get("window_width", 400)
        h = self.config.get("window_height", 60)
        x, y = self._target_x, self._target_y
        # 获取光标所在显示器的工作区（支持多屏）
        monitor = user32.MonitorFromPoint(ctypes.wintypes.POINT(x, y), 0)  # MONITOR_DEFAULTTONEAREST
        if monitor:
            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(monitor, ctypes.byref(mi))
            work = mi.rcWork
        else:
            work = RECT(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
        if x + w > work.right: x = work.right - w - 5
        if y + h > work.bottom: y = self._target_y - h - 5
        if x < work.left: x = work.left + 5
        if y < work.top: y = work.top + 5
        user32.SetWindowPos(self.hwnd, 0, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE)
        # 设置圆角区域
        cr = self.config.get("window_corner_radius", 12)
        rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, cr * 2, cr * 2)
        user32.SetWindowRgn(self.hwnd, rgn, True)
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.InvalidateRect(self.hwnd, None, True)
        user32.UpdateWindow(self.hwnd)
        self.visible = True

    def _do_hide(self):
        user32.ShowWindow(self.hwnd, 0)
        self.visible = False

    def _do_update_content(self):
        user32.InvalidateRect(self.hwnd, None, True)
        user32.UpdateWindow(self.hwnd)

    def _do_move(self, x, y):
        user32.SetWindowPos(self.hwnd, 0, x, y, 0, 0,
                            SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    # ---- 绘制 ----

    def _get_font_size(self, line_type):
        sizes = {
            self.LINE_PREVIEW: "clipboard_font_size",
            self.LINE_TIP: "tip_font_size",
            self.LINE_PASTE_TIP: "paste_tip_font_size",
            self.LINE_PASTE_CONTENT: "paste_content_font_size",
        }
        return self.config.get(sizes.get(line_type, "clipboard_font_size"), 14)

    def _on_paint(self, hwnd):
        ps = PAINTSTRUCT()
        hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
        if not hdc:
            return
        try:
            rect = RECT()
            user32.GetClientRect(hwnd, ctypes.byref(rect))
            cw = rect.right - rect.left
            ch = rect.bottom - rect.top
            cr = self.config.get("window_corner_radius", 12)

            # 奶白色背景
            bg_brush = gdi32.CreateSolidBrush(0x00F5FAFC)  # BGR: RGB(252, 250, 245)
            user32.FillRect(hdc, ctypes.byref(rect), bg_brush)
            gdi32.DeleteObject(bg_brush)

            # 圆角边框
            pen = gdi32.CreatePen(0, 1, 0x00D2D2D2)  # BGR: RGB(210, 210, 210)
            old_pen = gdi32.SelectObject(hdc, pen)
            no_brush = gdi32.GetStockObject(5)  # NULL_BRUSH
            old_brush = gdi32.SelectObject(hdc, no_brush)
            gdi32.RoundRect(hdc, rect.left, rect.top, rect.right - 1, rect.bottom - 1,
                            cr * 2, cr * 2)
            gdi32.SelectObject(hdc, old_pen)
            gdi32.SelectObject(hdc, old_brush)
            gdi32.DeleteObject(pen)

            if self.draw_lines:
                y = 6
                pad = 12
                line_spacing = self.config.get("line_spacing", 6)
                for line_type, left_text, right_text in self.draw_lines:
                    fs = self._get_font_size(line_type)
                    font = LOGFONTW()
                    font.lfHeight = -fs
                    font.lfWeight = 400
                    font.lfFaceName = self.config.get("font_name", "Microsoft YaHei")
                    hfont = gdi32.CreateFontIndirectW(ctypes.byref(font))
                    old_font = gdi32.SelectObject(hdc, hfont)
                    # 提示行用浅灰色文字
                    if line_type == self.LINE_TIP:
                        gdi32.SetTextColor(hdc, 0x00999999)  # BGR: RGB(153, 153, 153)
                    else:
                        gdi32.SetTextColor(hdc, 0x003C3C3C)  # BGR: RGB(60, 60, 60)
                    gdi32.SetBkMode(hdc, 1)
                    lh = self._text_height(hdc)
                    aw = cw - pad * 2
                    if right_text:
                        rw = self._text_width(hdc, right_text)
                        lmw = aw - rw - 8
                        if lmw < 50: lmw = 50
                        dl = self._truncate(hdc, left_text, lmw)
                        gdi32.TextOutW(hdc, pad, y, dl, len(dl))
                        gdi32.TextOutW(hdc, cw - pad - rw, y, right_text, len(right_text))
                    else:
                        dt = self._truncate(hdc, left_text, aw)
                        gdi32.TextOutW(hdc, pad, y, dt, len(dt))
                    y += lh + line_spacing
                    gdi32.SelectObject(hdc, old_font)
                    gdi32.DeleteObject(hfont)
        finally:
            user32.EndPaint(hwnd, ctypes.byref(ps))

    def _text_width(self, hdc, text):
        s = ctypes.wintypes.SIZE()
        gdi32.GetTextExtentPoint32W(hdc, text, len(text), ctypes.byref(s))
        return s.cx

    def _text_height(self, hdc):
        m = TEXTMETRIC()
        gdi32.GetTextMetricsW(hdc, ctypes.byref(m))
        return m.tmHeight

    def _truncate(self, hdc, text, max_w):
        if not text: return text
        tw = self._text_width(hdc, text)
        if tw <= max_w: return text
        sw = self._text_width(hdc, "...")
        tw2 = max_w - sw
        if tw2 <= 0: return "..."
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._text_width(hdc, text[:mid]) <= tw2:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo] + "..."

    def destroy(self):
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_DESTROY, 0, 0)


# ====== 主程序 ======
class PasteTool:
    def __init__(self, show_console=False):
        self.show_console = show_console
        self.running = True
        self.active = True
        self.config = load_config()
        self.tip_window = TipWindow(self.config)
        self.caret_tracker = CaretTracker()
        self.waiting_for_second_v = False
        self.is_pasting = False
        self._last_clipboard = None
        self._last_caret_pos = None
        self._user_dragged = False
        self._ctrl_pressed = False
        self._simulating = False
        self.waiting_for_second_c = False
        self._v_down_intercepted = False
        self.show_tip_window = self.config.get("show_tip_window", True)
        self.tray_icon = None

    def get_clipboard_content(self):
        try:
            win32clipboard.OpenClipboard(0)
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            pass
        return None

    def split_into_segments(self, text):
        return [s for s in text.split('\n') if s]

    def _release_ctrl(self):
        """释放Ctrl键"""
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = VK_CONTROL
        inp.union.ki.dwFlags = KEYEVENTF_KEYUP
        inp.union.ki.dwExtraInfo = 0
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def simulate_input(self, text):
        """使用SendInput模拟键盘输入（KEYEVENTF_UNICODE）"""
        self._simulating = True
        try:
            for char in text:
                code = ord(char)
                if code >= 0x10000:
                    # BMP外字符使用代理对
                    code -= 0x10000
                    hi = 0xD800 + (code >> 10)
                    lo = 0xDC00 + (code & 0x3FF)
                    self._send_unicode_key(hi)
                    self._send_unicode_key(lo)
                else:
                    self._send_unicode_key(code)
                time.sleep(0.005)
        finally:
            self._simulating = False

    def _send_unicode_key(self, code):
        """发送一个Unicode按键事件"""
        # Key down
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = 0
        inp.union.ki.wScan = code
        inp.union.ki.dwFlags = KEYEVENTF_UNICODE
        inp.union.ki.dwExtraInfo = 0
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        # Key up
        inp2 = INPUT()
        inp2.type = INPUT_KEYBOARD
        inp2.union.ki.wVk = 0
        inp2.union.ki.wScan = code
        inp2.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        inp2.union.ki.dwExtraInfo = 0
        user32.SendInput(1, ctypes.byref(inp2), ctypes.sizeof(INPUT))

    def _press_enter(self):
        """模拟回车键"""
        VK_RETURN = 0x0D
        # Key down
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.union.ki.wVk = VK_RETURN
        inp.union.ki.dwFlags = 0
        inp.union.ki.dwExtraInfo = 0
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        # Key up
        inp2 = INPUT()
        inp2.type = INPUT_KEYBOARD
        inp2.union.ki.wVk = VK_RETURN
        inp2.union.ki.dwFlags = KEYEVENTF_KEYUP
        inp2.union.ki.dwExtraInfo = 0
        user32.SendInput(1, ctypes.byref(inp2), ctypes.sizeof(INPUT))

    def do_paste(self):
        text = self.get_clipboard_content()
        if not text:
            return
        segments = self.split_into_segments(text)
        if not segments:
            return

        self.is_pasting = True
        time.sleep(0.15)  # 等待用户释放按键
        self._release_ctrl()  # 显式释放Ctrl
        time.sleep(0.05)

        try:
            for i, segment in enumerate(segments):
                remaining = len(segments) - i - 1
                lines = [
                    (TipWindow.LINE_PASTE_TIP, "正在输入", None),
                    (TipWindow.LINE_PASTE_CONTENT, segment, f"剩余{remaining}段"),
                ]
                # 确保窗口可见
                if self._last_caret_pos:
                    x, y = self._last_caret_pos
                    self.tip_window.show(x, y + 20, lines)
                else:
                    self.tip_window.update_content(lines)
                self.simulate_input(segment)
                if i < len(segments) - 1:
                    self._press_enter()
                time.sleep(0.1)
        finally:
            self.is_pasting = False
            self.tip_window.hide()

    # ---- 键盘钩子（使用keyboard库） ----

    def _start_hook(self):
        """使用keyboard.hook()注册全局键盘钩子，手动拦截Ctrl+V"""
        try:
            keyboard.hook(self._on_key_event, suppress=True)
            if self.show_console:
                print("[OK] Keyboard hook installed (keyboard.hook)")
        except Exception as e:
            if self.show_console:
                print(f"[WARN] Failed to install keyboard hook: {e}")

    def _stop_hook(self):
        """注销键盘钩子"""
        try:
            keyboard.unhook_all()
        except Exception:
            pass

    def _on_key_event(self, event):
        """键盘事件回调：拦截Ctrl+V（仅文本），其余放行"""
        # 模拟输入期间不拦截
        if self._simulating:
            return True

        # 追踪Ctrl键状态
        if event.name in ('ctrl', 'left ctrl', 'right ctrl'):
            if event.event_type == 'down':
                self._ctrl_pressed = True
            elif event.event_type == 'up':
                self._ctrl_pressed = False
            return True

        # 拦截Ctrl+V（按下和释放都抑制，避免残留）
        if event.name == 'v' and (self._ctrl_pressed or keyboard.is_pressed('ctrl')):
            # 服务暂停时放行，让正常粘贴生效
            if not self.active:
                return True
            if event.event_type == 'down':
                self._v_down_intercepted = False
                if not self.is_pasting:
                    # 剪贴板非文本时不拦截，让正常粘贴生效
                    clip_text = self.get_clipboard_content()
                    if clip_text:
                        self._v_down_intercepted = True
                        self._on_hotkey_ctrl_v()
                        return False  # 抑制V键
                return True  # 粘贴中或非文本，放行
            # up事件：与down保持一致
            return not self._v_down_intercepted  # down拦截则up也拦截，否则放行

        # 监听Ctrl+C（服务暂停时双击启用，不拦截正常复制）
        if event.name == 'c' and (self._ctrl_pressed or keyboard.is_pressed('ctrl')):
            if event.event_type == 'down' and not self.active:
                self._on_hotkey_ctrl_c()

        return True

    def _on_hotkey_ctrl_v(self):
        """keyboard库检测到Ctrl+V时的回调"""
        if not self.active or self.is_pasting:
            return
        if self.waiting_for_second_v:
            # 第二次Ctrl+V，暂停服务
            self.active = False
            self.waiting_for_second_v = False
            self.tip_window.hide()
            self.update_tray_status()
            return

        self.waiting_for_second_v = True

        def wait_and_paste():
            time.sleep(1.0)
            if self.waiting_for_second_v and self.active:
                self.waiting_for_second_v = False
                self.do_paste()

        threading.Thread(target=wait_and_paste, daemon=True).start()

    def _on_hotkey_ctrl_c(self):
        """Ctrl+C双击启用服务"""
        if self.active:
            return
        if self.waiting_for_second_c:
            # 第二次Ctrl+C，启用服务
            self.active = True
            self.waiting_for_second_c = False
            # 重置追踪状态
            self.caret_tracker._last_focus_hwnd = None
            self.caret_tracker._last_fg_hwnd = None
            self.caret_tracker._last_pos = None
            self._last_clipboard = None
            self._user_dragged = False
            self.update_tray_status()
            return

        self.waiting_for_second_c = True

        def wait_timeout():
            time.sleep(1.0)
            self.waiting_for_second_c = False

        threading.Thread(target=wait_timeout, daemon=True).start()

    # ---- 定时更新 ----

    def _update_loop(self):
        """定时检查光标位置和剪贴板变化，仅在变化时更新"""
        while self.running:
            if self.active and not self.is_pasting:
                try:
                    self._check_update()
                except Exception:
                    pass
            time.sleep(0.5)

    def _check_update(self):
        # 输入过程中不更新位置
        if self.is_pasting:
            return

        # 悬浮窗关闭时，只更新剪贴板缓存，不显示窗口
        if not self.show_tip_window:
            self._last_clipboard = self.get_clipboard_content()
            self.tip_window.hide()
            return

        # 检查焦点窗口或前台窗口是否变化
        new_caret_pos, focus_changed = self.caret_tracker.check_changed()
        # 焦点切换到不同程序时，重置拖动标记，让窗口跟随到新位置
        if focus_changed:
            self._user_dragged = False
        # 检查剪贴板是否变化
        clip_text = self.get_clipboard_content()
        clip_changed = clip_text != self._last_clipboard
        self._last_clipboard = clip_text

        # 每次都检查光标是否消失（即使焦点窗口没变）
        current_pos = self.caret_tracker._last_pos
        if current_pos is None:
            self.tip_window.hide()
            return

        # 剪贴板无文本 → 隐藏悬浮窗
        if not clip_text:
            self.tip_window.hide()
            return

        # 无变化则跳过（位置和内容都没变）
        if new_caret_pos is None and not clip_changed:
            return

        # 构建显示内容
        segs = self.split_into_segments(clip_text)
        lines = [
            (TipWindow.LINE_PREVIEW, clip_text, f"{len(segs)}段 {len(clip_text)}字"),
            (TipWindow.LINE_TIP, "在粘贴前请检查输入法语言是否正确，输入位置是否正确", None),
        ]

        # 用户拖动过窗口后，不再自动跟随光标位置（只更新内容）
        if self._user_dragged:
            if clip_changed:
                self.tip_window.update_content(lines)
            return

        # 焦点变化时，移动窗口到新位置
        if new_caret_pos is not None:
            self._last_caret_pos = new_caret_pos
            x, y = new_caret_pos
            y += 20
            self.tip_window.show(x, y, lines)
        elif clip_changed:
            # 剪贴板变化但焦点没变，只更新内容
            self.tip_window.update_content(lines)

    # ---- 托盘 ----

    def update_tray_status(self):
        if self.tray_icon:
            self.tray_icon.title = "粘贴工具 - 运行中" if self.active else "粘贴工具 - 已暂停"
            self.tray_icon.icon = self._create_icon(self.active)
            self.tray_icon.update_menu()

    def _create_icon(self, active=True):
        from PIL import Image
        icon_dir = os.path.dirname(os.path.abspath(__file__))
        if active:
            icon_path = os.path.join(icon_dir, "enable.ico")
        else:
            icon_path = os.path.join(icon_dir, "disable.ico")
        if os.path.exists(icon_path):
            return Image.open(icon_path)
        # 回退：生成默认图标
        from PIL import ImageDraw
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = (0, 200, 0, 255) if active else (200, 200, 200, 255)
        d.ellipse([8, 8, 56, 56], fill=c)
        d.text((20, 14), "P", fill=(255, 255, 255, 255))
        return img

    def setup_tray(self):
        import pystray
        from pystray import MenuItem, Menu

        def on_start(icon, item):
            self.active = True
            # 重置追踪状态，确保恢复后能重新检测
            self.caret_tracker._last_focus_hwnd = None
            self.caret_tracker._last_fg_hwnd = None
            self.caret_tracker._last_pos = None
            self._last_clipboard = None
            self._user_dragged = False
            self.update_tray_status()

        def on_pause(icon, item):
            self.active = False
            self.tip_window.hide()
            self.update_tray_status()

        def on_toggle_tip(icon, item):
            self.show_tip_window = not self.show_tip_window
            self.config["show_tip_window"] = self.show_tip_window
            save_config(self.config)
            if not self.show_tip_window:
                self.tip_window.hide()
            self.update_tray_status()

        def on_exit(icon, item):
            self.running = False
            self.active = False
            icon.stop()

        menu = Menu(
            MenuItem("开始", on_start, visible=lambda i: not self.active),
            MenuItem("暂停", on_pause, visible=lambda i: self.active),
            Menu.SEPARATOR,
            MenuItem("显示悬浮窗", on_toggle_tip, checked=lambda i: self.show_tip_window),
            Menu.SEPARATOR,
            MenuItem("退出", on_exit)
        )
        self.tray_icon = pystray.Icon("PasteTool", self._create_icon(True), "粘贴工具 - 运行中", menu)

    # ---- 运行 ----

    def run(self):
        # 1. 预初始化UIA（避免在钩子回调时初始化）
        self.caret_tracker.init_uia()
        if self.show_console:
            print("[OK] UIA initialized")

        # 2. 启动提示窗口线程
        self.tip_window.on_dragged = lambda: setattr(self, '_user_dragged', True)
        self.tip_window.start()
        if self.show_console:
            print(f"[OK] Tip window created: {self.tip_window.hwnd}")

        # 3. 启动键盘钩子
        self._start_hook()

        # 4. 启动更新定时器
        threading.Thread(target=self._update_loop, daemon=True).start()

        # 5. 启动托盘（阻塞主线程）
        self.setup_tray()
        self.tray_icon.run()

        # 清理
        self.running = False
        self._stop_hook()
        self.tip_window.destroy()


def main():
    parser = argparse.ArgumentParser(description='粘贴工具 - 模拟输入替代粘贴')
    parser.add_argument('-win', action='store_true', help='保留控制台窗口（开发模式）')
    args = parser.parse_args()

    # 尝试安装键盘钩子来检测是否有管理员权限
    # 如果没有权限，申请UAC提权重启
    try:
        h = keyboard.hook(lambda e: True)
        keyboard.unhook(h)
    except Exception:
        _try_run_as_admin()
        # 如果到这里说明UAC被取消或失败，继续运行但钩子可能不工作

    if not args.win:
        user32.ShowWindow(kernel32.GetConsoleWindow(), 0)

    tool = PasteTool(show_console=args.win)
    tool.run()


def _try_run_as_admin():
    """尝试通过UAC提权重启，失败则静默忽略"""
    try:
        import sys
        script = os.path.abspath(sys.argv[0])
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]] if len(sys.argv) > 1 else [])
        # ShellExecuteW 返回值 > 32 表示成功
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}'.strip(), None, 1)
        if ret > 32:
            # UAC 成功，新进程已启动，当前进程退出
            sys.exit(0)
    except Exception:
        pass


if __name__ == '__main__':
    main()
