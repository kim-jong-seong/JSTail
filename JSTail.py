import sys
import os
import ast
import codecs
import colorsys
import ctypes
import datetime
import random
import re
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, font, messagebox, colorchooser

# 파일 끌어다 놓기 - 없으면 그 기능만 빠지고 나머지는 그대로 동작합니다
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except ImportError:
    TkinterDnD, DND_FILES = None, None

initFlag = True
prev_file_size = 0
find_window = None  # 초기에는 창이 열려 있지 않음을 나타내기 위해 None으로 설정합니다.
selected_text = ""
delPop = None
about_window = None
highlight_window = None
jump_button = None  # "맨 아래로" 버튼 (스크롤을 올렸을 때만 표시)
jump_font = None     # 버튼 문구 폰트 (크기 계산에 사용)
jump_hover = False   # 버튼 위에 마우스가 올라가 있는지
has_new_log = False  # 스크롤을 올려둔 사이에 새 로그가 들어왔는지 여부

# "맨 아래로" 버튼 모양 (평상시 / 새 로그 도착 시)
JUMP_BG, JUMP_HOVER_BG = "#4A4F57", "#61686F"
NEW_LOG_BG, NEW_LOG_HOVER_BG = "#2D7FF9", "#4A93FF"
JUMP_FG = "#FFFFFF"

# 문구 좌우 여백 - 화살표가 있는 오른쪽을 조금 좁게 잡습니다.
JUMP_PAD_L, JUMP_PAD_R, JUMP_PAD_Y = 16, 10, 7

JUMP_OPACITY = 0.88   # 버튼 불투명도 (1 이면 완전 불투명)

def app_dir():
    """실행 파일(또는 스크립트)이 들어 있는 폴더."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def config_dir():
    """설정을 보관할 폴더 - %APPDATA%\\JSTail

    exe 옆에 두면 어느 폴더에서 실행하느냐(작업 디렉터리)에 따라 설정을
    못 찾는 문제가 있고 폴더도 지저분해집니다. exe 안에 넣는 것은 불가능합니다.
    실행 파일은 자기 자신을 고쳐 쓸 수 없기 때문입니다.
    """
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "JSTail")

# 설정 파일 경로
config_file = os.path.join(config_dir(), "config.ini")

def migrate_config():
    """예전 버전이 exe 옆에 만들어 둔 config.ini 를 한 번만 옮겨옵니다."""
    if os.path.exists(config_file):
        return
    old = os.path.join(app_dir(), "config.ini")
    try:
        if os.path.exists(old):
            os.makedirs(config_dir(), exist_ok=True)
            shutil.copy2(old, config_file)
    except OSError as e:
        print("Error migrating config:", e)

migrate_config()

# 한 번에 읽을 최대 바이트 - 파일이 갑자기 커졌을 때 통째로 읽지 않도록
MAX_READ_BYTES = 1024 * 1024

# 구분선(Ctrl+D) 모양
MARKER_TAG = "marker"
MARKER_MARK = "lastmarker"  # 마지막으로 이동한 구분선 위치
MARKER_BG, MARKER_FG = "#2F3A45", "#FFE9A8"

# 최근 파일 목록에 보관할 개수
RECENT_MAX = 5

# 배경색 창
bg_window = None
bg_tree = None
bg_color_entry = None
bg_color_swatch = None
bg_name_entry = None
bg_delete_button = None

# 처음 실행 시 넣어둘 기본 배경색 (전부 파스텔톤)
DEFAULT_BG_COLORS = [
    {"연하늘": "#E3F2FD"},
    {"민트": "#E0F2F1"},
    {"크림": "#FFF8E1"},
    {"연분홍": "#FCE4EC"},
    {"라벤더": "#EDE7F6"},
]

# 화면에 유지할 최대 줄 수 - 넘으면 오래된 줄부터 지웁니다.
# 위젯이 계속 커지면 메모리도 늘고 하이라이트도 느려지기 때문입니다.
# (config.ini 의 max_lines 로 바꿀 수 있습니다. 0 이면 제한 없음)
DEFAULT_MAX_LINES = 50000

# 하이라이트 목록 캐시 - 500ms 마다 config.ini 를 읽지 않도록
highlight_cache = None

# 제목 표시줄을 숨겼을 때 Alt+드래그로 창을 옮기기 위한 기준점
drag_origin = None

# 창 위치/크기를 저장하기까지 기다리는 시간(ms)
# 창을 끄는 동안 계속 저장하지 않도록 잠잠해진 뒤에 한 번만 씁니다.
GEOMETRY_SAVE_DELAY = 1000
geometry_job = None

# 구분선을 다시 그리기까지 기다리는 시간(ms)
MARKER_REDRAW_DELAY = 300
marker_redraw_job = None

# 화면 전체(모니터 여러 대 포함) 범위를 알아내는 값
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79

# 제목 표시줄 숨김에 쓰는 Windows 창 스타일 값
# overrideredirect() 를 쓰면 Windows 가 이 창을 "도구창"으로 취급해서
# 작업표시줄과 Alt+Tab 목록에서 빠져 버립니다. 그래서 스타일 비트만 벗깁니다.
GWL_STYLE = -16
WS_CAPTION = 0x00C00000     # 제목 표시줄
WS_THICKFRAME = 0x00040000  # 크기 조절 테두리
SWP_NOSIZE, SWP_NOMOVE = 0x0001, 0x0002
SWP_NOZORDER, SWP_FRAMECHANGED = 0x0004, 0x0020
window_style = None  # 원래 창 스타일 (복원용)

# 잠깐 떴다 사라지는 안내창
toast = None          # 안내창 위젯
toast_job = None      # 자동으로 닫는 예약
TOAST_BG, TOAST_FG = "#2F3A45", "#FFFFFF"
TOAST_OPACITY = 0.95
TOAST_PAD_X, TOAST_PAD_Y = 22, 12
TOAST_MS = 1600       # 떠 있는 시간(ms)

# 찾기 결과 표시 색
FOUND_ALL_BG = "#FFF3A8"   # 일치하는 것 전부
FOUND_CUR_BG = "#FF9E3D"   # 지금 보고 있는 것

# 로그 파일 인코딩
# 메뉴에 보여줄 이름 -> 실제 코덱 이름
ENCODING_AUTO = "자동"
ENCODING_CHOICES = (ENCODING_AUTO, "UTF-8", "CP949")
ENCODING_CODECS = {"UTF-8": "utf-8", "CP949": "cp949"}

log_encoding = "utf-8"  # 지금 실제로 쓰고 있는 코덱
log_decoder = None   # 글자 중간에서 잘린 바이트를 다음 조각까지 들고 있는 디코더
pending_cr = False   # 줄바꿈(\r\n)이 읽기 경계에서 잘린 경우 보관

def detect_encoding(path):
    """파일 앞뒤를 조금 읽어 인코딩을 추정합니다.

    1) BOM 이 있으면 그대로 따릅니다.
    2) UTF-8 로 읽어봅니다. UTF-8 은 바이트 배열 규칙이 엄격해서, CP949 로
       쓰인 한글이 우연히 UTF-8 로 읽히는 일은 거의 없습니다.
    3) 거의 다 깨지면 CP949(EUC-KR) 로 봅니다. 몇 바이트만 깨진 경우는
       파일 일부가 손상된 UTF-8 로 보고 CP949 로 넘기지 않습니다.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            sample = f.read(64 * 1024)
            if size > 128 * 1024:  # 앞부분이 영문뿐일 수 있어 끝부분도 봅니다
                f.seek(max(0, size - 64 * 1024))
                sample += f.read(64 * 1024)
    except OSError:
        return "utf-8"

    if sample.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if sample.startswith(codecs.BOM_UTF16_LE) or sample.startswith(codecs.BOM_UTF16_BE):
        return "utf-16"

    if not sample:
        return "utf-8"

    # 증분 디코더 + replace: 끝에서 글자가 잘린 것은 깨짐으로 세지 않습니다
    decoded = codecs.getincrementaldecoder("utf-8")("replace").decode(sample)
    broken = decoded.count("\ufffd")
    if broken and broken / len(decoded) >= 0.001:
        return "cp949"  # 한글이 통째로 깨지는 수준 -> CP949
    return "utf-8"

def resolve_log_encoding():
    """설정(자동/UTF-8/CP949)에 따라 실제로 쓸 코덱을 정합니다."""
    global log_encoding
    choice = encoding_choice.get()
    if choice in ENCODING_CODECS:
        log_encoding = ENCODING_CODECS[choice]
    elif file_path:
        log_encoding = detect_encoding(file_path)
    else:
        log_encoding = "utf-8"
    return log_encoding

def reset_decoder():
    """파일을 처음부터 읽기 시작할 때 디코더 상태를 초기화합니다."""
    global log_decoder, pending_cr
    # errors="replace" - 깨진 바이트 하나 때문에 화면 전체가 멈추지 않도록
    log_decoder = codecs.getincrementaldecoder(log_encoding)("replace")
    pending_cr = False

def decode_chunk(chunk):
    """새로 읽은 바이트를 글자로 바꾸고 줄바꿈을 정리합니다.

    파일 크기(바이트)를 기준으로 이어 읽기 때문에 한글처럼 여러 바이트를
    쓰는 글자가 조각 경계에서 잘릴 수 있습니다. 증분 디코더가 남은 바이트를
    다음 조각까지 들고 있다가 이어붙여 주므로 글자가 깨지지 않습니다.
    """
    global pending_cr
    result = log_decoder.decode(chunk)
    if pending_cr:
        result = "\r" + result
        pending_cr = False
    if result.endswith("\r"):  # \r\n 이 경계에서 잘린 경우
        result = result[:-1]
        pending_cr = True
    return result.replace("\r\n", "\n").replace("\r", "\n")

# 글꼴 후보 - 앞의 4개는 고정폭이라 로그의 열이 세로로 맞습니다.
# (나눔고딕코딩/돋움체는 한글 폭이 영문의 정확히 2배라 한글이 섞여도 안 틀어집니다)
FONT_CANDIDATES = ("나눔고딕코딩", "Consolas", "돋움체", "Courier New",
                   "맑은 고딕", "나눔고딕", "바탕", "굴림", "Arial", "Times New Roman")
DEFAULT_FONT = "맑은 고딕"
font_list_cache = None

def available_fonts():
    """후보 중 이 PC 에 실제로 설치된 글꼴만 골라냅니다.

    설치되지 않은 글꼴을 메뉴에서 고르면 Tk 가 말없이 기본 글꼴로
    바꿔버려서, 왜 안 바뀌는지 알 수 없기 때문에 미리 걸러냅니다.
    """
    global font_list_cache
    if font_list_cache is None:
        installed = set(font.families())
        font_list_cache = tuple(n for n in FONT_CANDIDATES if n in installed)
    return font_list_cache

# 예전 설정에 잘못 저장돼 있던 이름 보정 (실제 이름에는 띄어쓰기가 있음)
FONT_ALIASES = {"맑은고딕": "맑은 고딕"}

# 실행 파일의 경로와 아이콘 파일의 경로를 결합
base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
icon_path = os.path.join(base_path, "icon.ico")

def display_tail(event=None):
    selected = filedialog.askopenfilename(
        title="Select a file",
        filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
    )
    if selected:
        open_file(selected)

def update_tail():
    global file_path, text, prev_file_size, initFlag, has_new_log

    if file_path:
        try:
            # 현재 파일 크기
            curr_file_size = os.path.getsize(file_path)

            if initFlag is True:
                prev_file_size = curr_file_size
                initFlag = False

            if prev_file_size != curr_file_size :
                # 크기가 줄었으면 로그가 초기화됐거나 다른 파일로 바뀐 것입니다.
                # 화면에 있던 내용은 지금 파일과 무관하므로 비우고 다시 시작합니다.
                restarted = curr_file_size < prev_file_size
                if restarted:
                    prev_file_size = 0
                    reset_decoder()
                    erase_text()

                # 한 번에 읽을 양을 제한합니다. 로그가 수백 MB 인 상태에서
                # 처음부터 읽으면 메모리를 통째로 먹고 죽기 때문입니다.
                start = prev_file_size
                skipped = curr_file_size - start > MAX_READ_BYTES
                if skipped:
                    start = curr_file_size - MAX_READ_BYTES

                # 변경된 부분만 읽어오기
                # 텍스트 모드에서 바이트 위치로 seek 하면 글자 중간에 걸려
                # 깨질 수 있으므로 바이트로 읽고 직접 디코드합니다.
                with open(file_path, 'rb') as file:
                    file.seek(start)
                    chunk = file.read()

                if skipped:
                    # 중간부터 읽으므로 디코더를 초기화하고, 잘린 첫 줄은 버립니다
                    reset_decoder()
                    cut = chunk.find(b"\n")
                    if cut >= 0:
                        chunk = chunk[cut + 1:]

                current_content = decode_chunk(chunk)
                if restarted:
                    current_content = "──── 로그 파일이 새로 시작되었습니다 ────\n" + current_content
                elif skipped:
                    current_content = "──── 오래된 로그를 건너뛰었습니다 ────\n" + current_content

                # "자동" 인데 글자가 깨졌다면, 파일을 열 때는 내용이 없거나
                # 영문뿐이라 잘못 판단한 것입니다. 지금 다시 보고 고쳐 읽습니다.
                if "\ufffd" in current_content and encoding_choice.get() == ENCODING_AUTO:
                    previous = log_encoding
                    if resolve_log_encoding() != previous:
                        reset_decoder()
                        current_content = decode_chunk(chunk)

                # 스크롤이 맨 아래에 있을 때만 새 내용을 따라갑니다.
                # 위로 올려둔 상태면 읽던 위치를 그대로 유지합니다.
                was_at_bottom = at_bottom()
                mark = text.index("end-1c")  # 붙이기 전의 끝 위치
                append_text(current_content)
                if was_at_bottom:
                    text.see(tk.END)
                else:
                    # 위로 올려둔 상태에서 새 로그가 도착하면 버튼에 알립니다.
                    has_new_log = True
                    update_follow_state()
                # 이전 파일 크기 갱신
                prev_file_size = curr_file_size

                # 새로 붙은 구간만 강조합니다.
                # 키워드가 조각 경계에 걸쳐 있을 수 있어 조금 앞에서부터 봅니다.
                highlights = get_highlights()
                back = max([len(k) for k, _ in highlights] or [1]) - 1
                highlight_keyword(highlights,
                                  "%s-%dc" % (mark, back) if back else mark)

                # 찾아둔 검색어도 새 구간까지 이어서 표시합니다.
                find_in_new_text(mark)

                # 너무 길어지면 오래된 줄부터 잘라냅니다.
                trim_buffer()

        except Exception as e:
            print("Error updating tail:", e)

    # 1초마다 파일을 확인하여 내용을 업데이트합니다.
    root.after(500, update_tail)

def save_config_values(values):
    """config.ini 에 여러 항목을 한 번에 저장합니다.

    항목이 없으면 새로 추가하고, 파일 자체가 없으면 새로 만듭니다.
    (이전에는 항목이 없으면 조용히 저장되지 않고, 파일이 없으면 오류가 났습니다.)
    """
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        lines = []

    for key, value in values.items():
        new_line = f"{key} = {value}\n"
        for index, line in enumerate(lines):
            if line.split("=", 1)[0].strip() == key:
                lines[index] = new_line  # 기존 항목 갱신
                break
        else:
            lines.append(new_line)  # 없으면 새로 추가

    try:
        folder = os.path.dirname(config_file)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except OSError as e:
        print("Error writing config file:", e)

def save_last_file(file_path):
    # 설정 파일에 파일 경로 저장
    save_config_values({"last_file_path": file_path})

def load_last_file():
    # 설정 파일에서 마지막으로 선택한 파일의 경로 읽어오기
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("last_file_path"):
                    last_file_path = line.split("=")[1].strip()
                    if last_file_path and os.path.exists(last_file_path):
                        return last_file_path
    return ""

def save_last_font(selected_font, selected_size):
    # 설정 파일에 폰트 정보 저장
    save_config_values({"last_font": selected_font, "last_size": selected_size})

def resolve_font(name):
    """설정에 저장된 글꼴 이름을 실제 설치된 이름으로 보정합니다.

    "맑은고딕"(띄어쓰기 없음)처럼 실제로 없는 이름이 저장돼 있으면 Tk 가
    말없이 기본 글꼴로 대체해 버려서 글꼴 설정이 먹지 않습니다.
    """
    name = FONT_ALIASES.get(name, name)
    try:
        return name if name in font.families() else DEFAULT_FONT
    except tk.TclError:
        # 아직 Tk 가 준비되기 전이면 이름을 그대로 돌려줍니다.
        return name or DEFAULT_FONT

def load_last_font():
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("last_font"):
                    last_font = line.split("=")[1].strip()
                    if last_font:
                        return resolve_font(last_font)
    return DEFAULT_FONT  # 설정 파일에 저장된 폰트가 없는 경우 기본 폰트를 반환합니다.

def load_last_size():
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("last_size"):
                    last_size = line.split("=")[1].strip()
                    if last_size:
                        return int(last_size)
    return 10  # 설정 파일에 저장된 크기가 없는 경우 기본 크기를 반환합니다.

def change_font(font_name):
    global text
    size = load_last_size()
    text.config(font=(font_name, size))
    save_last_font(font_name, size)
    schedule_marker_redraw()  # 글자 폭이 바뀌면 구분선 길이도 달라집니다

def change_size(size):
    global text
    font_name = load_last_font()
    text.config(font=(font_name, size))
    save_last_font(font_name, size)
    schedule_marker_redraw()

def update_title():
    global file_path, root
    if file_path:
        root.title("JS Tail : " + file_path)
    else:
        root.title("JS Tail")

def popup_menu(event):
    popup_menu = tk.Menu(root, tearoff=0)
    popup_menu.add_command(label="파일 열기 ...", command=display_tail, accelerator="        Ctrl+O")

    # 최근 파일 - 하위 메뉴로 펼쳐서 고릅니다.
    recent_menu = tk.Menu(popup_menu, tearoff=0)
    popup_menu.add_cascade(label="최근 파일", menu=recent_menu)
    recent = load_recent_files()
    if recent:
        for path in recent:
            recent_menu.add_command(label=path,
                                    command=lambda p=path: open_file(p))
    else:
        recent_menu.add_command(label="(없음)", state="disabled")

    popup_menu.add_separator()

    # 구분선 - 넣기와 앞뒤 이동을 한 묶음으로 봅니다.
    popup_menu.add_command(label="구분선 추가", command=insert_marker, accelerator="        Ctrl+D")
    popup_menu.add_command(label="이전 구분선", command=prev_marker, accelerator="        Shift+F2")
    popup_menu.add_command(label="다음 구분선", command=next_marker, accelerator="        F2")

    popup_menu.add_separator()

    popup_menu.add_command(label="찾기", command=open_find_window, accelerator="        Ctrl+F")
    popup_menu.add_command(label="지우기", command=clear_text, accelerator="        Ctrl+L")
    popup_menu.add_command(label="빈줄 지우기", command=del_pop, accelerator="        Ctrl+Q")
    popup_menu.add_command(label="하이라이트", command=highlight_pop, accelerator="        Ctrl+H")
    popup_menu.add_command(label="배경색", command=change_bg_color, accelerator="        Ctrl+B")
    popup_menu.add_checkbutton(label="항상 위", variable=always_on_top,
                               command=apply_topmost, accelerator="        Ctrl+T")
    popup_menu.add_checkbutton(label="제목 표시줄 숨기기", variable=title_hidden,
                               command=apply_title_bar, accelerator="        Ctrl+E")

    popup_menu.add_separator()

    font_menu = tk.Menu(popup_menu, tearoff=0)
    popup_menu.add_cascade(label="글꼴", menu=font_menu)
    selected_font.set(load_last_font())  # 이전에 선택된 폰트에 체크 표시
    for font_name in available_fonts():
        font_menu.add_radiobutton(label=font_name, variable=selected_font, value=font_name, command=lambda f=font_name: change_font(f))

    size_menu = tk.Menu(popup_menu, tearoff=0)
    popup_menu.add_cascade(label="크기", menu=size_menu)
    selected_size.set(str(load_last_size()))  # 이전에 선택된 크기에 체크 표시
    for size in range(8, 16):
        size_menu.add_radiobutton(label=str(size), variable=selected_size, value=str(size), command=lambda s=size: change_size(s))

    encoding_menu = tk.Menu(popup_menu, tearoff=0)
    popup_menu.add_cascade(label="인코딩", menu=encoding_menu)
    for name in ENCODING_CHOICES:
        label = name
        if name == ENCODING_AUTO:
            label = "%s  (현재 %s)" % (ENCODING_AUTO, log_encoding)
        encoding_menu.add_radiobutton(label=label, variable=encoding_choice,
                                      value=name, command=change_encoding)

    settings_menu = tk.Menu(popup_menu, tearoff=0)
    popup_menu.add_cascade(label="설정", menu=settings_menu)
    settings_menu.add_command(label="설정 내보내기 ...", command=export_settings)
    settings_menu.add_command(label="설정 가져오기 ...", command=import_settings)
    settings_menu.add_separator()
    settings_menu.add_command(label="설정 폴더 열기", command=open_config_folder)

    popup_menu.add_separator()
    
    popup_menu.add_command(label="정보", command=aboutInfo)
    popup_menu.add_command(label="끝내기", command=root.quit)
    popup_menu.post(event.x_root, event.y_root)

def delPop_menu(event):
    delPop_menu = tk.Menu(root, tearoff=0)
    delPop_menu.add_command(label="빈줄 지우기", command=del_pop_bindQ, accelerator="        Ctrl+Q")

    # 오른쪽 클릭 이벤트 발생 시 메뉴를 표시합니다.
    delPop_menu.post(event.x_root, event.y_root)

def del_pop(event=None):
    global selected_text, delPop, del_text_widget

    if delPop is None:  # delPop가 존재하지 않을 때만 새로운 창을 엽니다.
        delPop = tk.Toplevel(root)
        delPop.title("빈줄 지우기")
        delPop.focus_force()

        # 아이콘 설정
        delPop.iconbitmap(icon_path)

        popupWidth = 700
        popupHeight = 600

        x_coord = root.winfo_x()
        y_coord = root.winfo_y()

        root_width = root.winfo_width()
        root_height = root.winfo_height()

        resize = str(popupWidth) + "x" + str(popupHeight) + "+" + str(round(x_coord + (root_width / 2) - (popupWidth / 2))) + "+" + str(round(y_coord + (root_height / 2) - (popupHeight / 2)))

        delPop.geometry(resize)
        delPop.protocol("WM_DELETE_WINDOW", on_del_pop_close)  # Find 창이 닫힐 때 호출할 함수 설정

        # 텍스트 영역 생성
        delPop_text_frame = tk.Frame(delPop)
        delPop_text_frame.pack(expand=True, fill=tk.BOTH)

        del_text_scrollbar_y = tk.Scrollbar(delPop_text_frame)
        del_text_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        del_text_scrollbar_x = tk.Scrollbar(delPop_text_frame, orient=tk.HORIZONTAL)
        del_text_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        del_text_widget = tk.Text(delPop_text_frame, yscrollcommand=del_text_scrollbar_y.set, xscrollcommand=del_text_scrollbar_x.set, wrap="none")
        del_text_widget.pack(fill=tk.BOTH, expand=True)

        del_text_scrollbar_y.config(command=del_text_widget.yview)
        del_text_scrollbar_x.config(command=del_text_widget.xview)

        # 오른쪽 클릭 이벤트 바인딩
        del_text_widget.bind("<Button-3>", delPop_menu)

        # Ctrl+Q 단축키 바인딩
        delPop.bind("<Control-q>", del_pop_bindQ)
        delPop.bind("<Escape>", on_del_pop_close)

        if selected_text != "":
            del_text_widget.insert(tk.END, selected_text)
            
            # 텍스트 위젯 내용 가져오기
            content = del_text_widget.get("1.0", "end-1c")
            
            # 빈 줄 제거
            lines = content.split("\n")
            non_empty_lines = [line for line in lines if line.strip()]
            new_content = "\n".join(non_empty_lines)

            # 기존 내용 삭제 후 새로운 내용 삽입
            del_text_widget.delete("1.0", "end")
            del_text_widget.insert("1.0", new_content)

    else:
        delPop.lift()  # 이미 열려 있는 경우에는 해당 창을 화면 제일 앞으로 이동시킵니다.
        delPop.focus_force()  # Find 창에 포커스를 줍니다.

def del_pop_bindQ(event=None):
    # 텍스트 위젯 내용 가져오기
    content = del_text_widget.get("1.0", "end-1c")
    
    # 빈 줄 제거
    lines = content.split("\n")
    non_empty_lines = [line for line in lines if line.strip()]
    new_content = "\n".join(non_empty_lines)

    # 기존 내용 삭제 후 새로운 내용 삽입
    del_text_widget.delete("1.0", "end")
    del_text_widget.insert("1.0", new_content)

def on_del_pop_close(event=None):
    global delPop
    delPop.destroy()
    delPop = None  # 창이 닫힐 때 참조를 제거하여 다시 열 수 있도록 설정합니다.

def open_find_window():
    global find_window, direction, match, find_entry, find_button, find_status

    if not find_window:  # find_window가 존재하지 않을 때만 새로운 창을 엽니다.
        find_window = tk.Toplevel(root)
        find_window.title("찾기")
        find_window.lift()

        # 아이콘 설정
        find_window.iconbitmap(icon_path)

        popupWidth = 235
        popupHeight = 95

        x_coord = root.winfo_x()
        y_coord = root.winfo_y()

        root_width = root.winfo_width()
        root_height = root.winfo_height()

        resize = str(popupWidth) + "x" + str(popupHeight) + "+" + str(round(x_coord + (root_width / 2) - (popupWidth / 2))) + "+" + str(round(y_coord + (root_height / 2) - (popupHeight / 2)))

        find_window.geometry(resize)
        find_window.protocol("WM_DELETE_WINDOW", on_find_window_close)  # Find 창이 닫힐 때 호출할 함수 설정
        find_window.bind("<Escape>", on_find_window_close)
        find_window.resizable(False, False)
        
        find_label = tk.Label(find_window, text="내용 :")
        find_label.place(x=10, y=10)
        
        find_entry = tk.Entry(find_window)
        find_entry.place(x=45, y=12)
        find_entry.focus_force()

        find_entry.bind("<Return>", run_find)
        find_entry.bind("<Shift-Return>", find_prev)

        find_button = tk.Button(find_window, text="검색", command=run_find)
        find_button.place(x=191, y=8)
        find_button.config(state='disabled')
        find_entry.bind("<KeyRelease>", on_entry_changed)

        direction = tk.IntVar()
        match = tk.IntVar()

        # 바꾸면 바로 다시 찾습니다. command 가 없으면 검색을 다시 누를 때까지
        # 예전 조건으로 모아둔 결과 위에서 F3 이 움직이게 됩니다.
        find_radio_up = tk.Radiobutton(find_window, text="위로", variable=direction,
                                       value=0, command=on_find_option_changed)
        find_radio_up.place(x=25, y=40)

        find_radio_down = tk.Radiobutton(find_window, text="아래로", variable=direction,
                                         value=1, command=on_find_option_changed)
        find_radio_down.place(x=75, y=40)

        find_checkbox_match = tk.Checkbutton(find_window, text="매치", variable=match,
                                             command=on_find_option_changed)
        find_checkbox_match.place(x=150, y=40)

        # 결과 개수 + 다음/이전 안내
        find_status = tk.Label(find_window, text="", anchor="w")
        find_status.place(x=12, y=68, width=90)
        tk.Label(find_window, text="F3 다음 / Shift+F3 이전",
                 foreground="#777777").place(x=100, y=68)

        find_window.bind("<F3>", find_next)
        find_window.bind("<Shift-F3>", find_prev)

        prefill_find_entry()  # 로그창에서 드래그해 둔 문자열을 검색어로 채웁니다
    else:
        find_window.lift()  # 이미 열려 있는 경우에는 해당 창을 화면 제일 앞으로 이동시킵니다.
        find_window.focus_force()  # Find 창에 포커스를 줍니다.
        find_entry.focus_force()
        prefill_find_entry()  # 새로 드래그한 문자열로 다시 채웁니다.

def on_find_window_close(event=None):
    global find_window, find_term, find_case, find_status, find_entry
    find_term = ""
    find_case = False
    find_status = None
    find_entry = None
    text.tag_remove("found", "1.0", tk.END)
    text.tag_remove("found_all", "1.0", tk.END)

    find_window.destroy()
    find_window = None  # 창이 닫힐 때 참조를 제거하여 다시 열 수 있도록 설정합니다.

# 일치 위치를 줄 번호로 들고 있으면 오래된 줄이 잘려나갈 때(trim_buffer)
# 아래쪽 줄 번호가 전부 밀려서 엉뚱한 곳을 가리키게 됩니다. 그래서 위치는
# 따로 저장하지 않고, 글자를 따라 움직이는 태그에서 그때그때 읽어옵니다.
find_term = ""         # 마지막으로 검색한 문자열
find_case = False      # 그때 "매치"(대소문자 구분)가 켜져 있었는지
find_status = None     # "3 / 27" 을 보여주는 라벨
find_entry = None      # 검색어 입력칸 (창을 연 적이 없으면 None)

def on_entry_changed(event):
    global find_entry, find_button

    if find_entry.get() != "":
        find_button.config(state='normal')
    else:
        find_button.config(state='disabled')

def index_key(index):
    """'12.5' 같은 위치를 (줄, 칸) 숫자로 바꿉니다.

    text.compare() 는 한 번 부를 때마다 Tcl 을 거치므로 일치 항목이 많으면
    비교만으로도 느려집니다. 숫자로 바꿔 파이썬에서 비교합니다.
    """
    line, _, column = str(index).partition(".")
    try:
        return int(line), int(column)
    except ValueError:
        return 0, 0

def match_list():
    """지금 남아 있는 일치 항목을 [(시작, 끝), ...] 로 돌려줍니다.

    found_all 태그는 글자를 따라 움직이므로, 로그가 쌓여 위쪽이 잘려나가도
    남은 항목들은 항상 제자리를 가리킵니다.
    """
    ranges = text.tag_ranges("found_all")
    return [(str(ranges[i]), str(ranges[i + 1]))
            for i in range(0, len(ranges), 2)]

def current_match_index(matches):
    """지금 보고 있는 항목이 목록에서 몇 번째인지 돌려줍니다. 없으면 -1."""
    current = text.tag_ranges("found")
    if not current:
        return -1
    key = index_key(current[0])
    for i, (start, _) in enumerate(matches):
        if index_key(start) == key:
            return i
    return -1  # 보고 있던 항목이 잘려나간 경우

def nearest_match_index(matches, forward):
    """화면 맨 위를 기준으로 다음(또는 이전) 항목의 번호를 고릅니다.

    기준을 커서(INSERT)로 잡으면 안 됩니다. 커서는 로그가 붙을 때마다 끝으로
    따라가 버려서 "위로" 가 언제나 마지막 항목만 가리키게 됩니다.
    구분선 이동(goto_marker)과 같은 기준(화면 맨 위)을 씁니다.
    """
    here = index_key(text.index("@0,0"))
    if forward:
        return next((i for i, (start, _) in enumerate(matches)
                     if index_key(start) >= here), 0)  # 없으면 처음으로
    earlier = [i for i, (start, _) in enumerate(matches)
               if index_key(start) < here]
    return earlier[-1] if earlier else len(matches) - 1  # 없으면 마지막으로

def collect_matches(search_term):
    """검색어와 일치하는 위치를 모두 찾아 전부 연하게 표시합니다."""
    global find_term, find_case

    text.tag_remove("found_all", "1.0", tk.END)
    text.tag_remove("found", "1.0", tk.END)
    find_term = search_term
    find_case = bool(match.get())
    if not search_term:
        update_find_status()
        return

    nocase = not find_case  # "매치" 를 끄면 대소문자를 무시합니다.
    index = "1.0"
    while True:
        index = text.search(search_term, index, stopindex=tk.END, nocase=nocase)
        if not index:
            break
        end = f"{index}+{len(search_term)}c"
        text.tag_add("found_all", index, end)
        index = end

    text.tag_configure("found_all", background=FOUND_ALL_BG)
    text.tag_configure("found", background=FOUND_CUR_BG)
    # 하이라이트 태그보다 위에 있어야 검색 표시가 가려지지 않습니다.
    # (하이라이트를 추가/삭제하면 그 태그들이 나중에 다시 만들어져 위로 올라갑니다)
    text.tag_raise("found_all")
    text.tag_raise("found")  # 현재 항목이 항상 위에 보이도록

def find_in_new_text(mark):
    """새로 붙은 구간에서도 검색어를 찾아 표시합니다.

    한 번 찾아둔 뒤에 들어온 로그가 빠지면 개수(3 / 27)가 실제와 달라지고
    F3 으로도 갈 수 없습니다.
    """
    if not find_term:
        return

    # 검색어가 조각 경계에 걸쳐 있을 수 있어 조금 앞에서부터 봅니다.
    back = len(find_term) - 1
    index = "%s-%dc" % (mark, back) if back else mark
    nocase = not find_case
    found = False
    while True:
        index = text.search(find_term, index, stopindex=tk.END, nocase=nocase)
        if not index:
            break
        end = "%s+%dc" % (index, len(find_term))
        text.tag_add("found_all", index, end)
        index = end
        found = True
    if found:
        update_find_status()

def show_match(position):
    """position 번째 일치 항목으로 이동해 진하게 표시합니다."""
    matches = match_list()
    text.tag_remove("found", "1.0", tk.END)
    if not matches:
        update_find_status()
        return

    start, end = matches[position % len(matches)]  # 끝까지 가면 처음으로
    text.tag_add("found", start, end)
    text.see(start)
    update_find_status()

def update_find_status():
    """"3 / 27" 처럼 몇 번째인지 표시합니다."""
    if find_status is None or not find_status.winfo_exists():
        return
    if not find_term:
        find_status.config(text="")
        return

    matches = match_list()
    if not matches:
        find_status.config(text="없음", foreground="#C0392B")
        return

    here = current_match_index(matches)
    if here < 0:  # 보고 있던 항목이 잘려나갔으면 개수만 보여줍니다
        find_status.config(text="%d 개" % len(matches), foreground="#333333")
    else:
        find_status.config(text="%d / %d" % (here + 1, len(matches)),
                           foreground="#333333")

def step_match(step):
    """다음(step=1) 또는 이전(step=-1) 일치 항목으로 갑니다."""
    matches = match_list()
    if not matches:
        # 아직 찾은 것이 없으면 입력칸에 적힌 내용으로 한 번 찾아봅니다.
        if find_entry is not None and find_entry.winfo_exists() and find_entry.get():
            run_find()
        return "break"

    here = current_match_index(matches)
    if here < 0:
        # 보고 있던 항목이 잘려나갔으면 화면 위치를 기준으로 다시 잡습니다.
        show_match(nearest_match_index(matches, step > 0))
    else:
        show_match(here + step)
    return "break"

def run_find(event=None):
    """검색 버튼 / Enter - 방향에 맞는 항목으로 갑니다.

    조건이 그대로면 다시 모으지 않고 다음 항목으로 넘어갑니다. 누를 때마다
    처음부터 다시 모으면 몇 번을 눌러도 같은 자리에 머물기 때문입니다.
    """
    if find_entry is None or not find_entry.winfo_exists():
        return "break"

    search_term = find_entry.get()
    forward = direction.get() == 1
    same = (search_term and search_term == find_term
            and bool(match.get()) == find_case and match_list())
    if same:
        return step_match(1 if forward else -1)

    collect_matches(search_term)
    matches = match_list()
    if matches:
        show_match(nearest_match_index(matches, forward))
    else:
        update_find_status()
    return "break"

def on_find_option_changed(event=None):
    """위로/아래로/매치를 바꾸면 그 자리에서 바로 반영합니다.

    보고 있던 자리가 새 조건에서도 일치하면 그대로 지키고,
    아니면 화면 위치를 기준으로 다시 잡습니다.
    """
    if find_entry is None or not find_entry.winfo_exists() or not find_entry.get():
        return

    current = text.tag_ranges("found")
    anchor = index_key(current[0]) if current else None

    collect_matches(find_entry.get())
    matches = match_list()
    if not matches:
        update_find_status()
        return

    target = None
    if anchor is not None:
        target = next((i for i, (start, _) in enumerate(matches)
                       if index_key(start) == anchor), None)
    if target is None:
        target = nearest_match_index(matches, direction.get() == 1)
    show_match(target)

def prefill_find_entry():
    """로그창에서 드래그한 문자열을 검색어 칸에 미리 채웁니다. (Ctrl+F)

    여러 줄을 드래그했으면 검색어로 쓸 수 있는 첫 줄만 씁니다.
    바로 덮어쓸 수 있도록 채운 내용을 선택해 둡니다.
    """
    keyword = ""
    for line in selected_text.splitlines():
        if line.strip():
            keyword = line.strip()
            break

    if keyword:
        find_entry.delete(0, "end")
        find_entry.insert(0, keyword)
        find_entry.select_range(0, "end")
        find_entry.icursor("end")
    find_button.config(state="normal" if find_entry.get() else "disabled")

def find_next(event=None):
    """F3 - 다음 항목"""
    return step_match(1)

def find_prev(event=None):
    """Shift+F3 - 이전 항목"""
    return step_match(-1)

# ------------------------- 안내창 -------------------------

def build_toast(parent):
    """화면 가운데에 잠깐 떴다 사라지는 안내창을 만듭니다.

    확인을 눌러야 닫히는 대화상자는 단축키로 자주 누를 때 거슬리므로,
    "맨 아래로" 버튼과 같은 모양으로 그려서 스스로 사라지게 합니다.
    """
    canvas = tk.Canvas(parent, highlightthickness=0, bd=0,
                       background=parent.cget("background"))
    canvas.pill = canvas.create_polygon(0, 0, 0, 0, 0, 0,
                                        fill=TOAST_BG, outline="", smooth=True)
    canvas.label = canvas.create_text(0, 0, text="", fill=TOAST_FG, font=jump_font)
    return canvas

def show_toast(message):
    """안내 문구를 화면 가운데에 잠깐 띄웁니다."""
    global toast_job
    if toast is None or jump_font is None:
        return

    back = text.cget("background")
    label_w = jump_font.measure(message)
    w = label_w + TOAST_PAD_X * 2
    h = jump_font.metrics("linespace") + TOAST_PAD_Y * 2

    toast.configure(width=w, height=h, background=back)
    toast.coords(toast.pill, pill_points(w, h))
    toast.itemconfigure(toast.pill,
                        fill=blend_color(toast, TOAST_BG, back, TOAST_OPACITY))
    toast.coords(toast.label, w / 2, h / 2)
    toast.itemconfigure(toast.label, text=message,
                        fill=blend_color(toast, TOAST_FG, back, TOAST_OPACITY))
    toast.place(relx=0.5, rely=0.5, anchor="center")
    tk.Misc.lift(toast)  # Canvas 의 lift() 는 도형용이라 위젯용을 직접 호출합니다

    if toast_job is not None:  # 연달아 누르면 시간을 다시 셉니다
        root.after_cancel(toast_job)
    toast_job = root.after(TOAST_MS, hide_toast)

def hide_toast():
    """안내창을 감춥니다."""
    global toast_job
    toast_job = None
    if toast is not None:
        toast.place_forget()

# ------------------------- 구분선 -------------------------

def marker_line(stamp):
    """창 폭에 맞춘 구분선 문자열을 만듭니다.

    글자 "개수" 가 아니라 "픽셀" 로 계산해야 합니다. 고정폭 글꼴이라도 ━ 는
    한글처럼 두 칸을 차지해서 시각 글자와 폭이 다르기 때문입니다.
    (개수로 빼면 그 차이만큼 오른쪽이 비어 보입니다)
    """
    label = "  %s  " % stamp
    try:
        metric = font.Font(font=text.cget("font"))
        bar_w = metric.measure("━") or 8
        label_w = metric.measure(label)
        # 테두리(borderwidth)와 좌우 여백(padx)을 양쪽에서 뺀 값이 실제 폭입니다
        inset = 2 * (int(text.cget("borderwidth")) + int(text.cget("padx")))
        usable = text.winfo_width() - inset
    except tk.TclError:
        metric = None
        bar_w, label_w, usable = 8, len(label) * 8, 480

    if usable < 100:  # 아직 창이 그려지기 전이면 적당한 기본값
        usable = 480

    count = max(4, int((usable - label_w) // bar_w))
    left = count // 2
    line = "━" * left + label + "━" * (count - left)

    # ━ 를 하나 더 넣기엔 모자란 자투리는 빈칸으로 채웁니다.
    # 글자는 보이지 않지만 배경색이 이어져서 막대가 오른쪽 끝까지 닿습니다.
    space_w = metric.measure(" ") if metric is not None else 0
    if space_w:
        leftover = usable - (label_w + count * bar_w)
        line += " " * int(max(0, leftover) // space_w)
    return line

def marker_stamp(start, end):
    """구분선 줄에서 시각 부분만 뽑아냅니다."""
    # 끝쪽 빈칸 때문에 ━ 가 양끝에 오지 않을 수 있어 둘을 함께 떼어냅니다
    return text.get(start, end).strip("━ 	")

def redraw_markers():
    """창 크기나 글꼴이 바뀌었을 때 구분선 길이를 다시 맞춥니다.

    구분선은 넣는 순간 그냥 글자로 굳기 때문에, 나중에 창을 넓히면
    오른쪽이 비어 보입니다. 그래서 다시 그려 줍니다.

    줄바꿈 문자는 건드리지 않고 줄 안쪽 내용만 교체하므로 줄 수가 그대로입니다.
    (줄 수가 바뀌면 다른 구분선 위치와 태그가 모두 어긋납니다)
    """
    global marker_redraw_job
    marker_redraw_job = None
    positions = marker_positions()
    if not positions:
        return

    was_bottom = at_bottom()
    first = text.yview()[0]  # 보던 위치

    text.config(state=tk.NORMAL)
    for pos in positions:
        start = text.index("%s linestart" % pos)
        end = text.index("%s lineend" % pos)
        stamp = marker_stamp(start, end)
        if not stamp:
            continue
        text.delete(start, end)
        text.insert(start, marker_line(stamp), MARKER_TAG)
    text.config(state=tk.DISABLED)

    if was_bottom:
        text.see(tk.END)
    else:
        text.yview_moveto(first)

def schedule_marker_redraw():
    """잠잠해진 뒤에 한 번만 다시 그리도록 예약합니다."""
    global marker_redraw_job
    if marker_redraw_job is not None:
        root.after_cancel(marker_redraw_job)
    marker_redraw_job = root.after(MARKER_REDRAW_DELAY, redraw_markers)

def insert_marker(event=None):
    """지금 위치에 시각이 찍힌 구분선을 넣습니다. (Ctrl+D)

    배포하고 기능을 눌러보기 직전에 선을 하나 그어두면,
    그 아래부터가 방금 발생한 로그입니다.
    """
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = marker_line(stamp)

    text.config(state=tk.NORMAL)
    if text.index("end-1c") != "1.0":
        text.insert(tk.END, "\n")  # 앞 줄에 붙지 않도록
    start = text.index("end-1c")
    text.insert(tk.END, line)
    text.tag_add(MARKER_TAG, start, text.index("end-1c"))
    text.insert(tk.END, "\n")
    text.config(state=tk.DISABLED)

    # 위아래로 여백을 줘서 로그 사이에서 확실히 눈에 띄게 합니다.
    text.tag_configure(MARKER_TAG, background=MARKER_BG, foreground=MARKER_FG,
                       spacing1=6, spacing3=6)
    jump_to_bottom()
    show_toast("구분선을 넣었습니다.   F2 다음 / Shift+F2 이전")
    return "break"

def marker_positions():
    """화면에 있는 구분선들의 위치를 위에서부터 차례로 돌려줍니다."""
    ranges = text.tag_ranges(MARKER_TAG)
    return [str(ranges[i]) for i in range(0, len(ranges), 2)]

def goto_marker(forward=True):
    """다음/이전 구분선으로 갑니다.

    번호를 따로 세지 않고 매번 위치로 찾기 때문에, 구분선을 더 넣거나
    오래된 줄이 잘려나가도 항상 맞습니다.
    """
    markers = marker_positions()
    if not markers:
        show_toast("구분선이 없습니다.   Ctrl+D 로 넣을 수 있습니다")
        return "break"

    # 기준점 정하기
    # 직전에 이동한 구분선이 아직 화면에 보이면 그 구분선을 기준으로 삼습니다.
    # (맨 아래쪽 구분선은 화면 맨 위로 올릴 수 없어서 화면 위치만으로는 어긋납니다)
    # 사용자가 다른 곳으로 스크롤했으면 화면 맨 위를 기준으로 삼습니다.
    here = None
    if MARKER_MARK in text.mark_names():
        spot = text.index(MARKER_MARK)
        if text.bbox(spot):  # 그 구분선이 아직 화면에 보이는가
            here = spot
    if here is None:
        here = text.index("@0,0")

    if forward:
        target = next((i for i, m in enumerate(markers)
                       if text.compare(m, ">", here)), 0)  # 없으면 처음으로
    else:
        earlier = [i for i, m in enumerate(markers) if text.compare(m, "<", here)]
        target = earlier[-1] if earlier else len(markers) - 1  # 없으면 마지막으로

    text.mark_set(MARKER_MARK, markers[target])  # 글이 밀려도 따라다닙니다
    text.mark_gravity(MARKER_MARK, "left")
    text.see(markers[target])
    text.yview(markers[target])  # 구분선을 화면 맨 위에 둡니다
    update_follow_state()
    show_toast("구분선  %d / %d" % (target + 1, len(markers)))
    return "break"

def next_marker(event=None):
    """F2 - 다음 구분선"""
    return goto_marker(True)

def prev_marker(event=None):
    """Shift+F2 - 이전 구분선"""
    return goto_marker(False)

# ------------------------- 항상 위 -------------------------

def apply_topmost():
    """현재 설정을 창에 적용하고 config.ini 에 저장합니다."""
    root.attributes("-topmost", bool(always_on_top.get()))
    save_config_values({"always_on_top": 1 if always_on_top.get() else 0})

def toggle_topmost(event=None):
    """항상 위 켜기/끄기. (Ctrl+T)

    메뉴에서 바꿀 때는 체크 표시로 알 수 있지만 단축키는 티가 나지 않아서,
    지금 어느 쪽으로 바뀌었는지 안내를 잠깐 띄웁니다.
    """
    always_on_top.set(not always_on_top.get())
    apply_topmost()
    show_toast("창이 항상 위에 고정됩니다." if always_on_top.get()
               else "창 고정이 해제되었습니다.")
    return "break"

def load_topmost():
    """config.ini 에 저장된 항상 위 설정을 읽어옵니다."""
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.split("=", 1)[0].strip() == "always_on_top":
                    return line.split("=", 1)[1].strip() in ("1", "True", "true")
    return False

def ensure_config():
    """설정 파일에서 빠진 항목을 기본값으로 채웁니다.

    파일이 아예 없으면 새로 만들고, 예전 버전에서 쓰던 파일이라 나중에 생긴
    항목이 빠져 있으면 그것만 더합니다. 이미 있는 값은 건드리지 않습니다.
    """
    defaults = {
        "last_file_path": "",
        "last_font": DEFAULT_FONT,
        "last_size": 10,
        "highlight": [],
        "background_color": "#FFFFFF",
        "always_on_top": 0,
        "recent_files": [],
        "encoding": ENCODING_AUTO,
        "max_lines": DEFAULT_MAX_LINES,
        "bg_colors": str(DEFAULT_BG_COLORS).replace("}, ", "},"),
        "geometry": "1000x400+500+500",
        "maximized": 0,
    }

    existing = set()
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                existing.add(line.split("=", 1)[0].strip())
    except OSError:
        pass  # 파일이 없으면 전부 새로 넣습니다

    missing = {key: value for key, value in defaults.items() if key not in existing}
    if missing:
        save_config_values(missing)

# ------------------------- 설정 내보내기/가져오기 -------------------------

# 가져온 파일이 JSTail 설정이 맞는지 확인할 때 쓰는 항목들
KNOWN_KEYS = ("last_file_path", "last_font", "last_size", "highlight",
              "background_color", "always_on_top", "recent_files",
              "encoding", "max_lines", "bg_colors", "geometry", "maximized")

def export_settings():
    """지금 설정을 파일 하나로 저장합니다."""
    path = filedialog.asksaveasfilename(
        title="설정 내보내기", defaultextension=".ini",
        initialfile="JSTail_config.ini",
        filetypes=(("설정 파일", "*.ini"), ("모든 파일", "*.*")))
    if not path:
        return
    try:
        if not os.path.exists(config_file):
            save_config_values({})  # 아직 없으면 만들어 둡니다
        shutil.copy2(config_file, path)
        show_toast("설정을 내보냈습니다")
    except OSError as e:
        messagebox.showwarning("알림", "설정을 내보내지 못했습니다.\n%s" % e)

def import_settings():
    """설정 파일을 불러와 지금 창에 바로 적용합니다."""
    path = filedialog.askopenfilename(
        title="설정 가져오기",
        filetypes=(("설정 파일", "*.ini"), ("모든 파일", "*.*")))
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        messagebox.showwarning("알림", "설정을 읽지 못했습니다.\n%s" % e)
        return

    if not any(line.split("=", 1)[0].strip() in KNOWN_KEYS for line in lines):
        messagebox.showwarning("알림", "JSTail 설정 파일이 아닌 것 같습니다.")
        return

    try:
        os.makedirs(config_dir(), exist_ok=True)
        shutil.copy2(path, config_file)
    except OSError as e:
        messagebox.showwarning("알림", "설정을 저장하지 못했습니다.\n%s" % e)
        return

    apply_all_settings()
    show_toast("설정을 가져왔습니다")

def apply_all_settings():
    """설정 파일 내용을 지금 창에 반영합니다. (가져오기 직후)"""
    global max_lines
    text.config(font=(load_last_font(), load_last_size()),
                background=load_background_color())
    selected_font.set(load_last_font())
    selected_size.set(str(load_last_size()))

    always_on_top.set(load_topmost())
    root.attributes("-topmost", bool(always_on_top.get()))

    encoding_choice.set(load_encoding_choice())
    resolve_log_encoding()
    reset_decoder()

    max_lines = load_max_lines()
    invalidate_highlights()
    clear_all_tags()
    highlight_keyword(get_highlights())
    trim_buffer()
    paint_jump_button()

def open_config_folder():
    """설정 파일이 있는 폴더를 탐색기로 엽니다."""
    try:
        os.makedirs(config_dir(), exist_ok=True)
        os.startfile(config_dir())
    except (OSError, AttributeError) as e:
        messagebox.showwarning("알림", "폴더를 열지 못했습니다.\n%s" % e)

# ------------------------- 인코딩 -------------------------

def load_encoding_choice():
    """config.ini 에 저장된 인코딩 설정을 읽어옵니다."""
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.split("=", 1)[0].strip() == "encoding":
                    value = line.split("=", 1)[1].strip()
                    if value in ENCODING_CHOICES:
                        return value
    return ENCODING_AUTO

def change_encoding():
    """인코딩을 바꾸고 지금 시점부터 다시 읽습니다.

    이미 화면에 있는 글자는 예전 인코딩으로 읽힌 것이라 되돌릴 수 없어서,
    화면을 비우고 새로 들어오는 로그부터 적용합니다.
    """
    global prev_file_size
    save_config_values({"encoding": encoding_choice.get()})
    resolve_log_encoding()
    reset_decoder()
    erase_text()
    if file_path and os.path.exists(file_path):
        prev_file_size = os.path.getsize(file_path)
    name = encoding_choice.get()
    if name == ENCODING_AUTO:
        name = "%s (%s)" % (ENCODING_AUTO, log_encoding)
    show_toast("인코딩: %s   지금부터 다시 읽습니다" % name)

# ------------------------- 창 위치/크기 -------------------------

def load_geometry():
    """저장해둔 창 위치/크기를 읽어옵니다. 없으면 빈 문자열."""
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.split("=", 1)[0].strip() == "geometry":
                    return line.split("=", 1)[1].strip()
    return ""

def load_maximized():
    """최대화된 상태로 껐는지 읽어옵니다."""
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.split("=", 1)[0].strip() == "maximized":
                    return line.split("=", 1)[1].strip() in ("1", "True", "true")
    return False

def geometry_on_screen(geometry):
    """저장된 위치가 지금 화면 안에 있는지 확인합니다.

    모니터를 빼거나 배치를 바꾸면 예전 위치가 화면 밖일 수 있습니다.
    그대로 띄우면 창을 찾을 수 없으므로 미리 걸러냅니다.
    """
    match = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", geometry or "")
    if not match:
        return False
    width, height, x, y = (int(v) for v in match.groups())
    if width < 200 or height < 100:
        return False
    try:
        metrics = ctypes.windll.user32.GetSystemMetrics
        left, top = metrics(SM_XVIRTUALSCREEN), metrics(SM_YVIRTUALSCREEN)
        right = left + metrics(SM_CXVIRTUALSCREEN)
        bottom = top + metrics(SM_CYVIRTUALSCREEN)
    except (AttributeError, OSError):
        left, top = 0, 0
        right, bottom = root.winfo_screenwidth(), root.winfo_screenheight()

    # 제목 표시줄을 잡을 수 있을 만큼은 화면 안에 들어와 있어야 합니다
    return (x + width - 80 > left and x + 80 < right
            and y + 40 > top and y + 40 < bottom)

def save_geometry():
    """지금 창 위치/크기를 저장합니다."""
    global geometry_job
    geometry_job = None
    try:
        maximized = root.state() == "zoomed"
    except tk.TclError:
        return

    values = {"maximized": 1 if maximized else 0}
    if not maximized:  # 최대화 상태의 크기는 저장하지 않습니다
        values["geometry"] = root.winfo_geometry()
    save_config_values(values)

def on_window_configure(event):
    """창을 옮기거나 크기를 바꾸면 잠시 뒤에 저장합니다."""
    global geometry_job, marker_redraw_job
    if event.widget is not root:
        return  # 안에 든 위젯들의 변화는 무시합니다
    if geometry_job is not None:
        root.after_cancel(geometry_job)
    geometry_job = root.after(GEOMETRY_SAVE_DELAY, save_geometry)
    schedule_marker_redraw()  # 넓어진 만큼 구분선도 다시 그립니다

def restore_geometry():
    """저장해둔 위치/크기로 창을 되돌립니다."""
    saved = load_geometry()
    if saved and geometry_on_screen(saved):
        root.geometry(saved)
    else:
        root.geometry("1000x400+500+500")  # 처음이거나 화면 밖이면 기본 위치
    if load_maximized():
        try:
            root.state("zoomed")
        except tk.TclError:
            pass

# ------------------------- 제목 표시줄 -------------------------

def window_handle():
    """이 창의 실제 Windows 핸들을 얻습니다."""
    user32 = ctypes.windll.user32
    child = root.winfo_id()
    return user32.GetParent(child) or child

def apply_title_bar():
    """제목 표시줄 표시 여부를 창에 적용합니다.

    제목 표시줄과 크기 조절 테두리 비트만 벗겨서, 작업표시줄과 Alt+Tab
    목록에는 그대로 남아 있도록 합니다. 대신 창을 잡고 옮길 곳이 없어지므로
    Alt+드래그로 옮기는 법을 함께 안내합니다.
    """
    global window_style
    try:
        user32 = ctypes.windll.user32
        hwnd = window_handle()
        if window_style is None:  # 처음 한 번 원래 스타일을 기억해 둡니다
            window_style = user32.GetWindowLongW(hwnd, GWL_STYLE)

        if title_hidden.get():
            style = window_style & ~(WS_CAPTION | WS_THICKFRAME)
        else:
            style = window_style

        user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        # 테두리가 바뀐 것을 창에 알려 다시 그리게 합니다
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except (AttributeError, OSError) as e:
        # Windows 가 아니거나 실패하면 Tk 기본 방식으로 대체합니다
        print("Error changing window style:", e)
        root.overrideredirect(bool(title_hidden.get()))

    root.focus_force()  # 숨긴 뒤에도 단축키가 먹도록 포커스를 되돌립니다
    if title_hidden.get():
        show_toast("제목 표시줄을 숨겼습니다.   Alt+드래그로 창 이동")

def toggle_title_bar(event=None):
    """제목 표시줄 숨기기/보이기. (Ctrl+E)"""
    title_hidden.set(not title_hidden.get())
    apply_title_bar()
    return "break"

def start_window_drag(event):
    """Alt+드래그 시작. 제목 표시줄을 숨겼을 때만 동작합니다."""
    global drag_origin
    if not title_hidden.get():
        return None  # 제목 표시줄이 있으면 평소대로 두고 봅니다
    drag_origin = (event.x_root - root.winfo_x(), event.y_root - root.winfo_y())
    return "break"  # 글자가 같이 선택되지 않도록 막습니다

def do_window_drag(event):
    """Alt+드래그 중 - 창을 따라 옮깁니다."""
    if drag_origin is None:
        return None
    root.geometry("+%d+%d" % (event.x_root - drag_origin[0],
                              event.y_root - drag_origin[1]))
    return "break"

def end_window_drag(event):
    """Alt+드래그 끝."""
    global drag_origin
    if drag_origin is None:
        return None
    drag_origin = None
    return "break"

# ------------------------- 최근 파일 -------------------------

def load_recent_files():
    """최근에 연 파일 목록을 읽어옵니다. (없어진 파일은 걸러냅니다)"""
    value = ""
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.split("=", 1)[0].strip() == "recent_files":
                    value = line.split("=", 1)[1]
                    break
    except OSError:
        return []

    try:
        items = ast.literal_eval(value.strip()) if value.strip() else []
    except (ValueError, SyntaxError):
        return []
    if not isinstance(items, list):
        return []
    return [path for path in items
            if isinstance(path, str) and os.path.exists(path)]

def push_recent_file(path):
    """방금 연 파일을 목록 맨 앞으로 올립니다."""
    items = [p for p in load_recent_files() if p != path]
    items.insert(0, path)
    save_config_values({"recent_files": items[:RECENT_MAX]})

def open_file(path):
    """파일을 열어 화면을 비우고 그 시점부터 따라갑니다."""
    global file_path, prev_file_size
    if not os.path.exists(path):
        messagebox.showwarning("알림", "파일을 찾을 수 없습니다.\n" + path)
        return
    file_path = path
    prev_file_size = os.path.getsize(path)
    resolve_log_encoding()  # "자동" 이면 파일마다 다시 판단합니다
    reset_decoder()
    erase_text()
    save_last_file(path)
    push_recent_file(path)
    update_title()

# ------------------------- 자동 스크롤 -------------------------

def at_bottom():
    """세로 스크롤이 맨 아래에 있는지 확인합니다."""
    try:
        return text.yview()[1] >= 0.9999
    except tk.TclError:
        return True

def jump_to_bottom(event=None):
    """맨 아래로 이동합니다. (Ctrl+Space 또는 버튼 클릭)"""
    text.yview_moveto(1.0)
    text.see(tk.END)
    update_follow_state()
    return "break"

def pill_points(w, h):
    """양 끝이 둥근 알약 모양의 좌표를 만듭니다. (smooth=True 로 그림)"""
    r = h / 2
    return [r, 0, w - r, 0, w, 0, w, r,
            w, h - r, w, h, w - r, h, r, h,
            0, h, 0, h - r, 0, r, 0, 0]

def build_jump_button(parent):
    """하단 중앙에 띄울 알약 모양 버튼을 만듭니다.

    tk.Button 은 사각 테두리라 로그 화면 위에서 튀기 때문에,
    Canvas 에 직접 그려서 테두리 없는 납작한 모양으로 만듭니다.
    """
    global jump_font
    jump_font = font.Font(family=DEFAULT_FONT, size=9)
    canvas = tk.Canvas(parent, highlightthickness=0, bd=0, cursor="hand2",
                       background=parent.cget("background"))
    canvas.pill = canvas.create_polygon(0, 0, 0, 0, 0, 0,
                                        fill=JUMP_BG, outline="", smooth=True)
    canvas.label = canvas.create_text(0, 0, text="", fill=JUMP_FG, font=jump_font)
    canvas.bind("<Button-1>", jump_to_bottom)
    canvas.bind("<Enter>", lambda e: paint_jump_button(hover=True))
    canvas.bind("<Leave>", lambda e: paint_jump_button(hover=False))
    return canvas

def blend_color(widget, fore, back, alpha):
    """fore 를 back 위에 alpha(0~1) 만큼 얹은 색을 계산합니다.

    Tk 캔버스는 항목별 투명도를 지원하지 않아서, 배경색과 직접 섞은 색을
    만들어 반투명하게 보이도록 합니다.
    """
    fr, fg, fb = widget.winfo_rgb(fore)
    br, bg, bb = widget.winfo_rgb(back)
    mix = lambda f, b: int((f * alpha + b * (1 - alpha)) / 256)
    return "#%02x%02x%02x" % (mix(fr, br), mix(fg, bg), mix(fb, bb))

def paint_jump_button(hover=None):
    """현재 상태(새 로그 여부 / 마우스 오버)에 맞춰 버튼을 다시 그립니다."""
    global jump_hover
    if jump_button is None:
        return
    if hover is not None:
        jump_hover = hover

    if has_new_log:
        label = "새로운 로그 (Ctrl+Space) ↓"
        color = NEW_LOG_HOVER_BG if jump_hover else NEW_LOG_BG
    else:
        label = "맨 아래로 (Ctrl+Space) ↓"
        color = JUMP_HOVER_BG if jump_hover else JUMP_BG

    # 배경색을 바꿔도(Ctrl+B) 버튼 주변이 사각형으로 남지 않도록 맞춰줍니다.
    back = text.cget("background")
    label_w = jump_font.measure(label)
    w = JUMP_PAD_L + label_w + JUMP_PAD_R
    h = jump_font.metrics("linespace") + JUMP_PAD_Y * 2
    opacity = JUMP_OPACITY

    jump_button.configure(width=w, height=h, background=back)
    jump_button.coords(jump_button.pill, pill_points(w, h))
    jump_button.itemconfigure(jump_button.pill,
                              fill=blend_color(jump_button, color, back, opacity))
    # 좌우 여백이 다르므로 문구를 여백 기준으로 배치합니다.
    jump_button.coords(jump_button.label, JUMP_PAD_L + label_w / 2, h / 2)
    jump_button.itemconfigure(jump_button.label, text=label,
                              fill=blend_color(jump_button, JUMP_FG, back, opacity))

def update_follow_state(*args):
    """맨 아래가 아니면 버튼을 하단 중앙에 띄우고, 맨 아래면 숨깁니다.

    스크롤을 올려둔 사이에 새 로그가 들어왔으면 문구를 "새로운 로그"로 바꿉니다.
    """
    global has_new_log
    if jump_button is None:
        return
    if at_bottom():
        has_new_log = False  # 맨 아래로 돌아왔으므로 알림 해제
        jump_button.place_forget()
    else:
        paint_jump_button()
        jump_button.place(relx=0.5, rely=1.0, y=-12, anchor="s")

def on_text_scroll(first, last):
    """Text 세로 스크롤 콜백: 스크롤바와 버튼 상태를 함께 갱신합니다."""
    text_scrollbar_y.set(first, last)
    update_follow_state()

def append_text(content):
    """읽기 전용 상태를 잠깐 풀고 새 로그를 덧붙입니다.

    로그 창은 실수로 타이핑되지 않도록 state=DISABLED 로 두는데,
    그 상태에서는 프로그램의 insert 도 막히므로 쓸 때만 잠시 풀어줍니다.
    """
    text.config(state=tk.NORMAL)
    text.insert(tk.END, content)
    text.config(state=tk.DISABLED)

def erase_text():
    """읽기 전용 상태를 잠깐 풀고 화면 내용을 비웁니다."""
    text.config(state=tk.NORMAL)
    text.delete("1.0", tk.END)
    text.config(state=tk.DISABLED)

def clear_text(event=None):
    erase_text()
    update_follow_state()

def on_selection_changed(event):
    global selected_text

    selected_range = text.tag_ranges(tk.SEL)
    if selected_range:
        selected_text = text.get(selected_range[0], selected_range[1])
    else:
        selected_text = ""  # 선택된 텍스트가 없으면 비웁니다.

def bring_find_window_to_front(event):
    global find_window
    if find_window and find_window.winfo_exists():  # 서브 창이 존재하는지 확인합니다.
        find_window.lift()

highlight_window = None  # 하이라이트 창 변수
tree = None  # Treeview 변수
keyword_entry = None  # 키워드 입력 변수
color_entry = None  # 색상 입력 변수
color_swatch = None  # 입력한 색을 보여주는 칸 (클릭하면 색상 선택창)
item_counter = 0  # 각 행의 고유 태그용 카운터

def highlight_window_close(event=None):
    global highlight_window
    highlight_window.destroy()
    highlight_window = None

def add_item():
    global keyword_entry, color_entry, tree, item_counter

    keyword = keyword_entry.get().strip()
    color = color_entry.get().strip()

    if keyword and color:
        # 기존 키워드 목록 읽기
        current_keywords = load_highlight_items()

        # 중복 키워드 체크
        if any(keyword in item for item in current_keywords):
            tk.messagebox.showwarning("입력 오류", "이미 존재하는 키워드입니다.")
            highlight_window.lift()  # 색상 선택 전 창을 최상위로
            return  # 함수 종료

        # 새로운 태그 생성
        tag_name = f"row_{item_counter}"
        tree.insert('', 'end', values=(keyword, color), tags=(tag_name,))

        # 태그에 색상 적용
        tree.tag_configure(tag_name, background=color)

        # 새로운 키워드 추가
        current_keywords.append({keyword: color})

        save_highlight_items(current_keywords)

        # 입력 필드 초기화 (다음에 쓸 색상은 미리 채워둡니다)
        keyword_entry.delete(0, 'end')
        current_colors = [list(i.values())[0] for i in current_keywords
                          if isinstance(i, dict) and i]
        set_color_value(pick_pastel_color(current_colors))

        item_counter += 1

        # 키워드가 바뀌었으니 캐시를 버리고 전체를 다시 강조합니다.
        invalidate_highlights()
        highlight_keyword(get_highlights())
    else:
        # 에러 처리: 키워드와 색상을 모두 입력해야 함
        tk.messagebox.showwarning("입력 오류", "키워드와 색상을 모두 입력하세요.")
        highlight_window.lift()  # 색상 선택 전 창을 최상위로

def delete_item():
    global tree
    selected_item = tree.selection()

    if selected_item:
        # 태그 모두 지우기
        clear_all_tags()

        # 선택된 항목의 값 가져오기
        item_values = tree.item(selected_item, 'values')
        if item_values:
            keyword_to_delete = item_values[0]  # 키워드 값

            # Treeview에서 항목 삭제
            tree.delete(selected_item)

            # 선택된 키워드 삭제
            current_keywords = [item for item in load_highlight_items()
                                if keyword_to_delete not in item]
            save_highlight_items(current_keywords)

        # 키워드가 바뀌었으니 캐시를 버리고 전체를 다시 강조합니다.
        invalidate_highlights()
        highlight_keyword(get_highlights())

def set_color_value(color):
    """색상 입력란에 값을 넣고 옆 미리보기 칸도 함께 갱신합니다."""
    color_entry.delete(0, "end")
    if color:
        color_entry.insert(0, color)
    update_color_swatch()

def update_color_swatch(event=None):
    """입력된 색상 코드를 오른쪽 미리보기 칸에 칠합니다.

    아직 다 입력하지 않았거나 잘못된 코드면 빈 칸으로 둡니다.
    """
    if color_swatch is None:
        return
    try:
        color_swatch.configure(background=color_entry.get().strip())
    except tk.TclError:
        color_swatch.configure(background=EMPTY_SWATCH_BG)

def choose_color(event=None):
    """색상 선택창을 엽니다. (미리보기 칸을 누르면 호출됩니다)"""
    color_code = colorchooser.askcolor(title="색상 선택",
                                       parent=highlight_window)[1]
    highlight_window.lift()
    if color_code:
        set_color_value(color_code)
        highlight_window.lift()

def auto_color(event=None):
    """등록된 색과 겹치지 않는 파스텔 색을 무작위로 골라 넣습니다."""
    used = [list(item.values())[0] for item in load_highlight_items()
            if isinstance(item, dict) and item]
    set_color_value(pick_pastel_color(used))

def on_highlight_click(event):
    """하이라이트 창의 빈 곳을 누르면 목록 선택과 입력 포커스를 해제합니다."""
    global tree, delete_button
    widget = event.widget

    if widget is tree:
        # 목록 안이라도 항목이 없는 빈 줄을 눌렀으면 선택을 해제합니다.
        if not tree.identify_row(event.y):
            tree.selection_remove(tree.selection())
    elif widget is not delete_button:  # Treeview 또는 삭제 버튼 외부 클릭 시
        tree.selection_remove(tree.selection())

    # 입력칸 밖을 눌렀으면 커서를 놓아 어디에 입력되는지 헷갈리지 않게 합니다.
    if widget is not color_entry and widget is not keyword_entry:
        highlight_window.focus_set()

def highlight_pop(event=None):
    global highlight_window, tree, keyword_entry, color_entry, color_swatch, delete_button

    if highlight_window is None:  # highlight_window가 존재하지 않을 때만 새로운 창을 엽니다.
        highlight_window = tk.Toplevel(root)
        highlight_window.title("하이라이트")
        highlight_window.focus_force()

        # 아이콘 설정 (필요시)
        highlight_window.iconbitmap(icon_path)

        popupWidth = 267
        popupHeight = 400

        x_coord = root.winfo_x()
        y_coord = root.winfo_y()

        root_width = root.winfo_width()
        root_height = root.winfo_height()

        resize = str(popupWidth) + "x" + str(popupHeight) + "+" + str(round(x_coord + (root_width / 2) - (popupWidth / 2))) + "+" + str(round(y_coord + (root_height / 2) - (popupHeight / 2)))
        highlight_window.geometry(resize)
        highlight_window.protocol("WM_DELETE_WINDOW", highlight_window_close)  # 창이 닫힐 때 호출할 함수 설정
        highlight_window.bind("<Escape>", highlight_window_close)
        highlight_window.resizable(False, False)

        # 표를 표시할 Treeview 생성
        columns = ('키워드')
        tree = ttk.Treeview(highlight_window, columns=columns, show='headings')
        tree.heading('키워드', text='키워드')
        tree.pack(fill='both', expand=True, padx=10, pady=10)

        # 추가 및 삭제 버튼
        button_frame = tk.Frame(highlight_window)
        button_frame.pack(fill='x', pady=1, padx=5)

        # Treeview 외부 클릭 시 선택 해제
        highlight_window.bind("<Button-1>", on_highlight_click)

        add_button = tk.Button(button_frame, text="추가", command=add_item)
        add_button.grid(row=0, column=0, sticky='ew', padx=5)  # 같은 비율로 채우기 위해 grid 사용

        delete_button = tk.Button(button_frame, text="삭제", command=delete_item)
        delete_button.grid(row=0, column=1, sticky='ew', padx=5)  # 같은 비율로 채우기 위해 grid 사용

        # 버튼의 비율을 맞추기 위해 column weight 설정
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)


        # 색상과 키워드 입력란
        input_frame = tk.Frame(highlight_window)
        input_frame.pack(fill='x', pady=5, padx=5)

        # 색상 줄 - [코드 입력] [색 미리보기] [자동] 세 칸을 같은 폭으로 나눕니다.
        for column in (1, 2, 3):
            input_frame.grid_columnconfigure(column, weight=1, uniform="cell")
        tk.Label(input_frame, text="색상:").grid(row=0, column=0, sticky='e', padx=5, pady=5)

        color_entry = tk.Entry(input_frame, width=6)
        color_entry.grid(row=0, column=1, sticky='nsew', padx=3, pady=5)  # 높이도 옆 칸과 맞춤
        color_entry.bind("<KeyRelease>", update_color_swatch)

        # 미리보기 칸 - 누르면 예전 "선택" 버튼과 똑같이 색상 선택창이 열립니다.
        color_swatch = tk.Frame(input_frame, background=EMPTY_SWATCH_BG,
                                relief="sunken", bd=1, cursor="hand2")
        color_swatch.grid(row=0, column=2, sticky='nsew', padx=3, pady=5)
        color_swatch.bind("<Button-1>", choose_color)

        # 자동 색상 버튼 (예전 "선택" 버튼 자리)
        auto_button = tk.Button(input_frame, text="자동", command=auto_color)
        auto_button.grid(row=0, column=3, sticky='ew', padx=3, pady=5)

        # 키워드 입력 필드
        tk.Label(input_frame, text="키워드:").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        keyword_entry = tk.Entry(input_frame)
        keyword_entry.grid(row=1, column=1, columnspan=3, padx=3, pady=5, sticky='ew')

        # config.ini의 highlight 값 읽기 및 Treeview에 추가
        try:
            with open(config_file, 'r', encoding='utf-8') as configfile:
                lines = configfile.readlines()
                for line in lines:
                    if line.startswith('highlight ='):
                        highlight_values = parse_highlights(line.split('=', 1)[1])
                        for item in highlight_values:
                            keyword = list(item.keys())[0]
                            color = item[keyword]
                            tree.insert('', 'end', values=(keyword, color))  # Treeview에 추가
                            # 태그 생성 및 색상 적용
                            tag_name = f"tag_{keyword}"
                            tree.tag_configure(tag_name, background=color)
                            tree.item(tree.get_children()[-1], tags=(tag_name,))  # 마지막 추가한 항목에 태그 적용
        except (FileNotFoundError, SyntaxError, NameError) as e:
            print("Error reading config file:", e)

        # 드래그한 문자열과 겹치지 않는 색을 미리 채워둡니다.
        prefill_highlight_inputs()

    else:
        highlight_window.lift()  # 이미 열려 있는 경우에는 해당 창을 화면 제일 앞으로 이동시킵니다.
        highlight_window.focus_force()  # 창에 포커스를 줍니다.
        prefill_highlight_inputs()  # 새로 드래그한 문자열로 다시 채웁니다.

EMPTY_SWATCH_BG = "#F0F0F0"  # 색상 코드가 비었거나 잘못됐을 때 미리보기 칸 색

# 파스텔 색상 선택에 쓰는 값
HUE_SLOTS = 12          # 색상환을 12칸(30도)으로 나눠 서로 구분되게 고릅니다
PASTEL_SAT = (0.20, 0.34)   # 채도 범위 (낮을수록 연함)
PASTEL_VAL = (0.95, 1.00)   # 명도 범위 (높을수록 밝음)

def hue_of(color):
    """#rrggbb 색의 색상(hue)을 0~1 로 돌려줍니다. 회색 계열이면 None."""
    try:
        r = int(color[1:3], 16) / 255
        g = int(color[3:5], 16) / 255
        b = int(color[5:7], 16) / 255
    except (ValueError, IndexError):
        return None
    h, sat, _ = colorsys.rgb_to_hsv(r, g, b)
    return h if sat > 0.05 else None

def pick_pastel_color(used_colors):
    """이미 등록된 색과 겹치지 않는 파스텔 색을 하나 고릅니다.

    색상환을 12칸으로 나눠 아직 쓰지 않은 칸에서 고르므로 서로 구분이 됩니다.
    빈 칸이 없으면(12개를 다 쓰면) 전체에서 고릅니다.
    """
    used = set()
    for color in used_colors:
        h = hue_of(color)
        if h is not None:
            used.add(int(round(h * HUE_SLOTS)) % HUE_SLOTS)

    free = [i for i in range(HUE_SLOTS) if i not in used]
    slot = random.choice(free or list(range(HUE_SLOTS)))
    # 같은 칸 안에서도 조금씩 흔들어 매번 똑같은 색이 나오지 않게 합니다.
    hue = ((slot + random.uniform(-0.35, 0.35)) / HUE_SLOTS) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue,
                                  random.uniform(*PASTEL_SAT),
                                  random.uniform(*PASTEL_VAL))
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))

def prefill_highlight_inputs():
    """하이라이트 창의 입력값을 미리 채웁니다. (추가 버튼은 사용자가 누름)

    로그창에서 드래그한 문자열이 있으면 키워드에 넣고,
    색상은 이미 등록된 것과 겹치지 않는 파스텔 색으로 채웁니다.
    """
    items = load_highlight_items()

    # 드래그한 문자열 - 여러 줄이면 첫 번째 줄만 씁니다.
    keyword = ""
    for line in selected_text.splitlines():
        if line.strip():
            keyword = line.strip()
            break

    keyword_entry.delete(0, "end")
    if keyword and not any(keyword in item for item in items):
        keyword_entry.insert(0, keyword)

    used = [list(item.values())[0] for item in items if isinstance(item, dict) and item]
    set_color_value(pick_pastel_color(used))

def load_highlight_items(): 
    """config.ini 의 highlight 항목을 [{키워드: 색상}, ...] 형태로 읽어옵니다."""
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.split("=", 1)[0].strip() == "highlight":
                    return parse_highlights(line.split("=", 1)[1])
    except OSError as e:
        print("Error reading config file:", e)
    return []

def save_highlight_items(items):
    """하이라이트 목록을 config.ini 에 한 줄로 저장합니다."""
    save_config_values({"highlight": str(items).replace("}, ", "},")})

def parse_highlights(value):
    """config.ini 의 highlight 값을 안전하게 파싱합니다.

    eval() 대신 ast.literal_eval() 을 사용하며, 값이 비었거나 깨져 있으면
    예외를 던지지 않고 빈 목록을 돌려줍니다.
    """
    value = (value or "").strip()
    if not value:
        return []
    try:
        items = ast.literal_eval(value)
    except (ValueError, SyntaxError) as e:
        print("Invalid highlight config:", e)
        return []
    return items if isinstance(items, list) else []

def load_highlights():
    """highlight 설정을 (키워드, 색상) 목록으로 읽어옵니다."""
    highlights_str = ""
    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith("highlight"):
                    highlights_str = line.split('=', 1)[1]
                    break
    except OSError as e:
        # config.ini 가 없거나 읽을 수 없어도 프로그램은 계속 동작해야 합니다.
        print("Error reading config file:", e)
        return []

    # 키워드와 색상으로 변환 (형식이 어긋난 항목은 건너뜁니다)
    result = []
    for item in parse_highlights(highlights_str):
        if isinstance(item, dict) and item:
            keyword, color = next(iter(item.items()))
            result.append((keyword, color))
    return result

def get_highlights():
    """하이라이트 목록을 돌려줍니다. 한 번 읽어두고 재사용합니다."""
    global highlight_cache
    if highlight_cache is None:
        highlight_cache = load_highlights()
    return highlight_cache

def invalidate_highlights():
    """키워드를 추가/삭제했을 때 캐시를 버립니다."""
    global highlight_cache
    highlight_cache = None

def load_max_lines():
    """config.ini 의 max_lines 를 읽어옵니다. (없으면 기본값)"""
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.split("=", 1)[0].strip() == "max_lines":
                    try:
                        return max(0, int(line.split("=", 1)[1].strip()))
                    except ValueError:
                        break
    return DEFAULT_MAX_LINES

def trim_buffer():
    """줄 수가 상한을 넘으면 위(오래된 쪽)에서부터 잘라냅니다."""
    if max_lines <= 0:
        return
    total = int(text.index("end-1c").split(".")[0])
    excess = total - max_lines
    if excess > 0:
        text.config(state=tk.NORMAL)
        text.delete("1.0", "%d.0" % (excess + 1))
        text.config(state=tk.DISABLED)

# 하이라이트 태그만 초기화하는 함수
def clear_all_tags():
    """하이라이트 태그만 삭제합니다.

    드래그 선택(sel)과 검색 결과(found) 태그까지 지우면 선택/검색 표시가
    깨지므로 highlight_ 로 시작하는 태그만 대상으로 합니다.
    """
    global text
    for tag in text.tag_names():
        if tag.startswith("highlight_"):
            text.tag_delete(tag)

def highlight_keyword(keywords, start="1.0"):
    """start 위치부터 끝까지 키워드를 찾아 강조합니다.

    갱신할 때마다 문서 전체를 다시 훑으면 줄 수에 비례해 느려지므로,
    평소에는 새로 붙은 구간만 검사합니다. (start 를 넘겨줌)
    """
    for keyword, color in keywords:
        # 태그 설정
        tag_name = f"highlight_{keyword}"
        text.tag_configure(tag_name, background=color)

        # 텍스트에서 키워드를 찾고 강조
        start_index = start
        while True:
            start_index = text.search(keyword, start_index, stopindex=tk.END)
            if not start_index:
                break
            end_index = f"{start_index}+{len(keyword)}c"
            text.tag_add(tag_name, start_index, end_index)
            start_index = end_index  # 다음 검색을 위해 인덱스 이동

    # 태그는 나중에 만들어진 것이 위에 그려집니다. 하이라이트를 추가/삭제하면
    # highlight_ 태그들이 다시 만들어지면서 검색 표시를 덮어버리므로,
    # 찾는 중이라면 검색 표시를 다시 맨 위로 올려줍니다.
    if find_term:
        text.tag_raise("found_all")
        text.tag_raise("found")

def load_bg_colors():
    """저장해둔 배경색 목록을 [{이름: 색상}, ...] 으로 읽어옵니다."""
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.split("=", 1)[0].strip() == "bg_colors":
                    # 하이라이트와 같은 형식이라 같은 파서를 씁니다
                    return parse_highlights(line.split("=", 1)[1])
    except OSError as e:
        print("Error reading config file:", e)
    return []

def save_bg_colors(items):
    """배경색 목록을 config.ini 에 한 줄로 저장합니다."""
    save_config_values({"bg_colors": str(items).replace("}, ", "},")})

def bg_set_color_value(color):
    """색상 입력칸에 값을 넣고 옆 미리보기 칸도 함께 갱신합니다."""
    bg_color_entry.delete(0, "end")
    if color:
        bg_color_entry.insert(0, color)
    bg_update_swatch()

def bg_update_swatch(event=None):
    """입력된 색상 코드를 오른쪽 미리보기 칸에 칠합니다."""
    if bg_color_swatch is None:
        return
    try:
        bg_color_swatch.configure(background=bg_color_entry.get().strip())
    except tk.TclError:
        bg_color_swatch.configure(background=EMPTY_SWATCH_BG)

def bg_choose_color(event=None):
    """미리보기 칸을 누르면 Windows 색 선택 창을 엽니다."""
    current = bg_color_entry.get().strip() or load_background_color()
    try:
        picked = colorchooser.askcolor(initialcolor=current, title="배경색 선택",
                                       parent=bg_window)[1]
    except tk.TclError:
        picked = colorchooser.askcolor(title="배경색 선택", parent=bg_window)[1]
    bg_window.lift()
    if picked:
        bg_set_color_value(picked)

def bg_apply():
    """입력칸에 있는 색을 배경색으로 적용합니다."""
    color = bg_color_entry.get().strip()
    if not color:
        messagebox.showwarning("입력 오류", "색상을 입력하거나 목록에서 고르세요.")
        bg_window.lift()
        return
    try:
        text.configure(background=color)
    except tk.TclError:
        messagebox.showwarning("입력 오류", "색상 코드가 올바르지 않습니다.")
        bg_window.lift()
        return
    save_background_color(color)
    paint_jump_button()  # 버튼/안내창 배경도 새 색에 맞춥니다

def bg_add_item():
    """입력칸의 이름과 색상을 목록에 저장합니다."""
    name = bg_name_entry.get().strip()
    color = bg_color_entry.get().strip()
    if not name or not color:
        messagebox.showwarning("입력 오류", "이름과 색상을 모두 입력하세요.")
        bg_window.lift()
        return
    try:
        bg_color_swatch.configure(background=color)
    except tk.TclError:
        messagebox.showwarning("입력 오류", "색상 코드가 올바르지 않습니다.")
        bg_window.lift()
        return

    items = load_bg_colors()
    if any(name in item for item in items):
        messagebox.showwarning("입력 오류", "이미 존재하는 이름입니다.")
        bg_window.lift()
        return

    items.append({name: color})
    save_bg_colors(items)
    fill_bg_tree()
    bg_name_entry.delete(0, "end")

def bg_delete_item():
    """목록에서 선택한 색을 지웁니다."""
    selected = bg_tree.selection()
    if not selected:
        return
    values = bg_tree.item(selected, "values")
    if not values:
        return
    name = values[0]
    save_bg_colors([item for item in load_bg_colors() if name not in item])
    fill_bg_tree()

def fill_bg_tree():
    """목록을 다시 채웁니다. 각 행의 배경을 그 색으로 칠합니다."""
    bg_tree.delete(*bg_tree.get_children())
    for item in load_bg_colors():
        if not isinstance(item, dict) or not item:
            continue
        name, color = next(iter(item.items()))
        tag = "bg_%s" % name
        bg_tree.insert("", "end", values=(name, color), tags=(tag,))
        try:
            bg_tree.tag_configure(tag, background=color)
        except tk.TclError:
            pass  # 색상 코드가 깨져 있으면 기본 배경으로 둡니다

def on_bg_tree_select(event=None):
    """목록에서 고른 색을 색상 입력칸으로 옮겨옵니다. (이름은 건드리지 않습니다)"""
    selected = bg_tree.selection()
    if not selected:
        return
    values = bg_tree.item(selected, "values")
    if len(values) >= 2:
        bg_set_color_value(values[1])

def on_bg_click(event):
    """빈 곳을 누르면 목록 선택과 입력 포커스를 해제합니다."""
    widget = event.widget
    if widget is bg_tree:
        if not bg_tree.identify_row(event.y):
            bg_tree.selection_remove(bg_tree.selection())
    elif widget is not bg_delete_button:
        bg_tree.selection_remove(bg_tree.selection())

    if widget is not bg_color_entry and widget is not bg_name_entry:
        bg_window.focus_set()

def bg_window_close(event=None):
    global bg_window
    bg_window.destroy()
    bg_window = None

def change_bg_color(event=None):
    """배경색 창을 엽니다. (Ctrl+B)"""
    global bg_window, bg_tree, bg_color_entry, bg_color_swatch
    global bg_name_entry, bg_delete_button

    if bg_window is not None:
        bg_window.lift()
        bg_window.focus_force()
        return

    bg_window = tk.Toplevel(root)
    bg_window.title("배경색")
    bg_window.focus_force()
    bg_window.iconbitmap(icon_path)

    popupWidth, popupHeight = 267, 400
    x_coord, y_coord = root.winfo_x(), root.winfo_y()
    root_width, root_height = root.winfo_width(), root.winfo_height()
    bg_window.geometry("%dx%d+%d+%d" % (
        popupWidth, popupHeight,
        round(x_coord + (root_width / 2) - (popupWidth / 2)),
        round(y_coord + (root_height / 2) - (popupHeight / 2))))
    bg_window.protocol("WM_DELETE_WINDOW", bg_window_close)
    bg_window.bind("<Escape>", bg_window_close)
    bg_window.resizable(False, False)

    # 저장해둔 색 목록
    columns = ("이름", "색상")
    bg_tree = ttk.Treeview(bg_window, columns=columns, show="headings")
    bg_tree.heading("이름", text="이름")
    bg_tree.heading("색상", text="색상")
    bg_tree.column("이름", width=140)
    bg_tree.column("색상", width=90)
    bg_tree.pack(fill="both", expand=True, padx=10, pady=10)
    bg_tree.bind("<<TreeviewSelect>>", on_bg_tree_select)

    bg_window.bind("<Button-1>", on_bg_click)

    # 적용 버튼 - 추가/삭제 두 버튼을 합친 너비로 윗줄에 놓습니다
    apply_frame = tk.Frame(bg_window)
    apply_frame.pack(fill="x", pady=(0, 2), padx=5)
    apply_button = tk.Button(apply_frame, text="적용", command=bg_apply)
    apply_button.pack(fill="x", padx=5)

    button_frame = tk.Frame(bg_window)
    button_frame.pack(fill="x", pady=1, padx=5)
    tk.Button(button_frame, text="추가", command=bg_add_item).grid(
        row=0, column=0, sticky="ew", padx=5)
    bg_delete_button = tk.Button(button_frame, text="삭제", command=bg_delete_item)
    bg_delete_button.grid(row=0, column=1, sticky="ew", padx=5)
    button_frame.grid_columnconfigure(0, weight=1)
    button_frame.grid_columnconfigure(1, weight=1)

    # 색상 / 이름 입력란
    input_frame = tk.Frame(bg_window)
    input_frame.pack(fill="x", pady=5, padx=5)
    input_frame.grid_columnconfigure(1, weight=1, uniform="cell")
    input_frame.grid_columnconfigure(2, weight=1, uniform="cell")

    tk.Label(input_frame, text="색상:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    bg_color_entry = tk.Entry(input_frame, width=6)
    bg_color_entry.grid(row=0, column=1, sticky="nsew", padx=3, pady=5)
    bg_color_entry.bind("<KeyRelease>", bg_update_swatch)
    bg_color_entry.bind("<Return>", lambda e: bg_apply())

    # 미리보기 칸 - 누르면 Windows 색 선택 창이 열립니다
    bg_color_swatch = tk.Frame(input_frame, background=EMPTY_SWATCH_BG,
                               relief="sunken", bd=1, cursor="hand2")
    bg_color_swatch.grid(row=0, column=2, sticky="nsew", padx=3, pady=5)
    bg_color_swatch.bind("<Button-1>", bg_choose_color)

    tk.Label(input_frame, text="이름:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
    bg_name_entry = tk.Entry(input_frame)
    bg_name_entry.grid(row=1, column=1, columnspan=2, padx=3, pady=5, sticky="ew")

    fill_bg_tree()
    bg_set_color_value(load_background_color())  # 지금 배경색을 채워둡니다

# 설정을 저장하는 함수 (섹션 없이 background_color 만 저장)
def save_background_color(color):
    save_config_values({"background_color": color})

# 설정된 배경색을 로드하는 함수
def load_background_color():
    """저장된 배경색을 읽어옵니다. 없으면 흰색.

    항목이 없을 때 None 이 나오면 배경색이 엉뚱하게 잡히므로
    어떤 경우에도 실제 색을 돌려줍니다.
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith('background_color'):
                    value = line.split('=', 1)[1].strip()
                    if value:
                        return value
    except OSError:
        pass
    return '#FFFFFF'

def aboutInfo():
    global about_window

    if about_window is None:  # about_window가 존재하지 않을 때만 새로운 창을 엽니다.

        popupWidth = 300
        popupHeight = 45

        x_coord = root.winfo_x()
        y_coord = root.winfo_y()

        root_width = root.winfo_width()
        root_height = root.winfo_height()

        resize = str(popupWidth) + "x" + str(popupHeight) + "+" + str(round(x_coord + (root_width / 2) - (popupWidth / 2))) + "+" + str(round(y_coord + (root_height / 2) - (popupHeight / 2)))

        about_window = tk.Toplevel(root)
        about_window.title("정보")
        about_window.focus_force()
        about_window.protocol("WM_DELETE_WINDOW", aboutInfo_close)  # about_window 창이 닫힐 때 호출할 함수 설정
        about_window.bind("<Escape>", aboutInfo_close)  # Find 창이 닫힐 때 호출할 함수 설정
        about_window.resizable(False, False)

        # 아이콘 설정
        about_window.iconbitmap(icon_path)
        about_window.geometry(resize)

        about_label = tk.Label(about_window, text="ⓒ 2024. JongSeong. All Rights Reserved.\nIcon created by Smashicons.", justify="center")
        about_label.pack(pady=7)
    else:
        about_window.lift() # 이미 열려 있는 경우에는 해당 창을 화면 제일 앞으로 이동시킵니다.
        about_window.focus_force()  # 창에 포커스를 줍니다.

def aboutInfo_close(event=None):
    global about_window

    about_window.destroy()
    about_window = None

def on_drop_files(event):
    """파일을 창에 끌어다 놓으면 엽니다."""
    # 경로에 공백이 있으면 {} 로 묶여 오므로 Tcl 목록으로 풀어야 합니다
    for path in root.tk.splitlist(event.data):
        if os.path.isfile(path):
            open_file(path)
            return
    messagebox.showwarning("알림", "파일만 열 수 있습니다.")

# Tkinter 애플리케이션 생성
# tkinterdnd2 가 있으면 파일 끌어다 놓기를 쓸 수 있는 창으로 만듭니다.
try:
    root = TkinterDnD.Tk() if TkinterDnD is not None else tk.Tk()
except Exception as e:
    print("Drag and drop unavailable:", e)
    root = tk.Tk()
root.title("JS Tail")
restore_geometry()  # 지난번에 쓰던 위치/크기로

# 처음 실행이면 설정 파일을 기본값으로 만들어 둡니다.
ensure_config()

# 아이콘 설정
root.iconbitmap(icon_path)

# StringVar 생성
selected_font = tk.StringVar()  # 선택된 폰트를 저장하는 변수
selected_size = tk.StringVar()  # 선택된 크기를 저장하는 변수

# 항상 위 설정 (우클릭 메뉴의 체크 표시와 연결됩니다)
always_on_top = tk.BooleanVar(value=load_topmost())
root.attributes("-topmost", bool(always_on_top.get()))

# 제목 표시줄 숨김 여부 - 시작할 때는 항상 보이는 상태로 둡니다.
# (숨긴 채로 시작하면 작업표시줄에 없어서 창을 찾기 어렵습니다)
title_hidden = tk.BooleanVar(value=False)

# 로그 파일 인코딩 설정 (우클릭 메뉴에서 고릅니다)
encoding_choice = tk.StringVar(value=load_encoding_choice())

# 텍스트 영역 생성
text_frame = tk.Frame(root)
text_frame.pack(expand=True, fill=tk.BOTH)

text_scrollbar_y = tk.Scrollbar(text_frame)
text_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

text_scrollbar_x = tk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
text_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

text = tk.Text(text_frame, yscrollcommand=on_text_scroll, xscrollcommand=text_scrollbar_x.set,
               wrap="none", background=load_background_color(),
               font=(load_last_font(), load_last_size()),
               state=tk.DISABLED)  # 실수로 타이핑되지 않도록 읽기 전용
text.pack(expand=True, fill=tk.BOTH)

# "맨 아래로" 버튼 - 스크롤을 위로 올렸을 때만 하단 중앙에 표시됩니다.
jump_button = build_jump_button(text)

# 안내창 - 필요할 때만 화면 가운데에 잠깐 나타납니다.
toast = build_toast(text)

text_scrollbar_y.config(command=text.yview)
text_scrollbar_x.config(command=text.xview)

# 파일 끌어다 놓기
if DND_FILES is not None and hasattr(text, "drop_target_register"):
    try:
        text.drop_target_register(DND_FILES)
        text.dnd_bind("<<Drop>>", on_drop_files)
    except tk.TclError as e:
        print("Drag and drop unavailable:", e)

# 오른쪽 클릭 이벤트 바인딩
text.bind("<Button-3>", popup_menu)

# 파일열기 단축키 바인딩
root.bind("<Control-o>", display_tail)

# 검색 단축키 바인딩
root.bind("<Control-f>", lambda event: open_find_window())

# Ctrl+L 단축키 바인딩
root.bind("<Control-l>", clear_text)

# Ctrl+Q 단축키 바인딩
root.bind("<Control-q>", del_pop)

# Ctrl+H 단축키 바인딩
root.bind("<Control-h>", highlight_pop)

# Ctrl+B 단축키 바인딩
root.bind("<Control-b>", change_bg_color)

# Ctrl+Space 단축키 바인딩 (맨 아래로)
root.bind("<Control-space>", jump_to_bottom)

# Ctrl+D 단축키 바인딩 (구분선 넣기)
root.bind("<Control-d>", insert_marker)

# Ctrl+T 단축키 바인딩 (항상 위)
root.bind("<Control-t>", toggle_topmost)

# Ctrl+E 단축키 바인딩 (제목 표시줄 숨기기)
root.bind("<Control-e>", toggle_title_bar)

# Alt+드래그로 창 이동 (제목 표시줄을 숨겼을 때)
# text 에 걸어야 글자 선택보다 먼저 잡아서 막을 수 있습니다.
text.bind("<Alt-Button-1>", start_window_drag)
text.bind("<Alt-B1-Motion>", do_window_drag)
text.bind("<Alt-ButtonRelease-1>", end_window_drag)
root.bind("<Alt-Button-1>", start_window_drag)
root.bind("<Alt-B1-Motion>", do_window_drag)
root.bind("<Alt-ButtonRelease-1>", end_window_drag)

# F3 / Shift+F3 (찾기 다음/이전)
root.bind("<F3>", find_next)
root.bind("<Shift-F3>", find_prev)

# F2 / Shift+F2 (구분선 다음/이전)
root.bind("<F2>", next_marker)
root.bind("<Shift-F2>", prev_marker)

# 텍스트에서 드래그 인식 이벤트
text.bind("<<Selection>>", on_selection_changed)

root.bind("<Button-1>", bring_find_window_to_front)

# 화면에 유지할 최대 줄 수
max_lines = load_max_lines()

# 창을 옮기거나 크기를 바꾸면 저장해 둡니다
root.bind("<Configure>", on_window_configure)

# 초기 파일 경로
file_path = load_last_file()
resolve_log_encoding()
reset_decoder()

# 애플리케이션 실행
update_title()  # 초기 타이틀 설정
root.after(100, update_follow_state)  # 버튼 초기 상태
root.after(1000, update_tail)
root.mainloop()
