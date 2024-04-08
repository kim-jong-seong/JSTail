import sys
import os
import tkinter as tk
from tkinter import filedialog, font, simpledialog, messagebox

global initFlag, prev_file_size, find_window, selected_text

initFlag = True
prev_file_size = 0
find_window = None  # 초기에는 창이 열려 있지 않음을 나타내기 위해 None으로 설정합니다.
selected_text = ""
delPop = None

# 설정 파일 경로
config_file = "config.ini"

# 실행 파일의 경로와 아이콘 파일의 경로를 결합
base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
icon_path = os.path.join(base_path, "icon.ico")

def tail(file_path, num_lines):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()[-num_lines:]
            return ''.join(lines)
    except Exception as e:
        print("Error reading file:", e)
        return None

def display_tail(event=None):
    global file_path, text, curr_file_size, prev_file_size

    file_path = filedialog.askopenfilename(
        title="Select a file",
        filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
    )
    if file_path:
        curr_file_size = os.path.getsize(file_path)
        prev_file_size = os.path.getsize(file_path)
        text.delete("1.0", tk.END)

        # 파일 경로를 설정 파일에 저장
        save_last_file(file_path)

        # 타이틀 업데이트
        update_title()

def update_tail():
    global file_path, text, previous_content, prev_file_size, initFlag

    if file_path:
        try:
            # 현재 파일 크기
            curr_file_size = os.path.getsize(file_path)

            if initFlag is True:
                prev_file_size = curr_file_size
                initFlag = False

            if prev_file_size != curr_file_size :
                # 파일이 이전에 읽은 부분보다 크기가 작을 경우 파일이 초기화된 것으로 간주하고 처음부터 읽어옴
                if curr_file_size < prev_file_size:
                    prev_file_size = 0

                # 변경된 부분만 읽어오기
                with open(file_path, 'r', encoding='utf-8') as file:
                    file.seek(prev_file_size)
                    current_content = file.read()

                text.insert(tk.END, current_content)
                text.see(tk.END)
                previous_content = current_content

                # 이전 파일 크기 갱신
                prev_file_size = curr_file_size

        except Exception as e:
            print("Error updating tail:", e)

    # 1초마다 파일을 확인하여 내용을 업데이트합니다.
    root.after(500, update_tail)

def save_last_file(file_path):
    # 설정 파일에 파일 경로 저장
    with open(config_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    with open(config_file, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip().startswith("last_file_path"):
                f.write(f"last_file_path = {file_path}\n")
            else:
                f.write(line)

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
    with open(config_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    with open(config_file, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip().startswith("last_font"):
                f.write(f"last_font = {selected_font}\n")
            elif line.strip().startswith("last_size"):
                f.write(f"last_size = {selected_size}\n")
            else:
                f.write(line)

def load_last_font():
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("last_font"):
                    last_font = line.split("=")[1].strip()
                    if last_font:
                        return last_font
    return "맑은고딕"  # 설정 파일에 저장된 폰트가 없는 경우 기본 폰트를 반환합니다.

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

def change_size(size):
    global text
    font_name = load_last_font()
    text.config(font=(font_name, size))
    save_last_font(font_name, size)

def update_title():
    global file_path, root
    if file_path:
        root.title("JS Tail : " + file_path)
    else:
        root.title("JS Tail")

def popup_menu(event):
    popup_menu = tk.Menu(root, tearoff=0)
    popup_menu.add_command(label="파일 열기 ...", command=display_tail, accelerator="        Ctrl+O")
    popup_menu.add_separator()

    popup_menu.add_command(label="찾기", command=open_find_window, accelerator="        Ctrl+F")
    popup_menu.add_command(label="지우기", command=clear_text, accelerator="        Ctrl+L")
    popup_menu.add_command(label="빈줄 지우기 툴", command=del_pop, accelerator="        Ctrl+Q")
    
    font_menu = tk.Menu(popup_menu, tearoff=0)
    popup_menu.add_cascade(label="글꼴", menu=font_menu)
    for font_name in ("Arial", "Times New Roman", "Courier New", "맑은고딕", "나눔고딕", "바탕", "굴림"):
        font_menu.add_radiobutton(label=font_name, variable=selected_font, value=font_name, command=lambda f=font_name: change_font(f))
        if font_name == load_last_font():
            font_menu.invoke(font_name)  # 이전에 선택된 폰트에 체크 표시

    size_menu = tk.Menu(popup_menu, tearoff=0)
    popup_menu.add_cascade(label="크기", menu=size_menu)
    for size in range(8, 16):
        size_menu.add_radiobutton(label=str(size), variable=selected_size, value=size, command=lambda s=size: change_size(s))
        if size == load_last_size():
            size_menu.invoke(str(size))  # 이전에 선택된 크기에 체크 표시

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
        delPop.title("빈줄 지우기 툴")
        delPop.focus_force()

        # 아이콘 설정
        delPop.iconbitmap(icon_path)

        x_coord = root.winfo_x()
        y_coord = root.winfo_y()

        resize = "700x600+" + str(x_coord + 150) + "+" + str(y_coord - 100)

        delPop.geometry(resize)
        delPop.protocol("WM_DELETE_WINDOW", on_del_pop_close)  # Find 창이 닫힐 때 호출할 함수 설정

        # 텍스트 영역 생성
        delPop_text_frame = tk.Frame(delPop)
        delPop_text_frame.pack(expand=True, fill=tk.BOTH)

        del_text_scrollbar_y = tk.Scrollbar(delPop_text_frame)
        del_text_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        del_text_scrollbar_x = tk.Scrollbar(delPop_text_frame, orient=tk.HORIZONTAL)
        del_text_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        del_text_widget = del_text_widget = tk.Text(delPop_text_frame, yscrollcommand=del_text_scrollbar_y.set, xscrollcommand=del_text_scrollbar_x.set, wrap="none")
        del_text_widget.pack(fill=tk.BOTH, expand=True)

        del_text_scrollbar_y.config(command=del_text_widget.yview)
        del_text_scrollbar_x.config(command=del_text_widget.xview)

        # 오른쪽 클릭 이벤트 바인딩
        del_text_widget.bind("<Button-3>", delPop_menu)

        # Ctrl+Q 단축키 바인딩
        delPop.bind("<Control-q>", del_pop_bindQ)

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

def on_del_pop_close():
    global delPop
    delPop.destroy()
    delPop = None  # 창이 닫힐 때 참조를 제거하여 다시 열 수 있도록 설정합니다.

def find_text():
    global text
    search_term = simpledialog.askstring("Find", "Find :", parent=root)
    if search_term:
        start_pos = text.search(search_term, "1.0", tk.END)
        if start_pos:
            text.tag_remove("found", "1.0", tk.END)
            while start_pos:
                end_pos = f"{start_pos}+{len(search_term)}c"
                text.tag_add("found", start_pos, end_pos)
                start_pos = text.search(search_term, end_pos, tk.END)
            text.tag_config("found", background="yellow")

def open_find_window():
    global find_window, direction, match, find_entry, find_button

    if not find_window:  # find_window가 존재하지 않을 때만 새로운 창을 엽니다.
        find_window = tk.Toplevel(root)
        find_window.title("찾기")
        find_window.lift()

        # 아이콘 설정
        find_window.iconbitmap(icon_path)

        x_coord = root.winfo_x()
        y_coord = root.winfo_y()

        resize = "235x75+" + str(x_coord + 218) + "+" + str(y_coord + 108)

        find_window.geometry(resize)
        find_window.protocol("WM_DELETE_WINDOW", on_find_window_close)  # Find 창이 닫힐 때 호출할 함수 설정
        
        find_label = tk.Label(find_window, text="내용 :")
        find_label.place(x=10, y=10)
        
        find_entry = tk.Entry(find_window)
        find_entry.place(x=45, y=12)
        find_entry.focus_force()

        find_entry.bind("<Return>", lambda event: find_text_external(find_entry.get()))
        
        find_button = tk.Button(find_window, text="검색", command=lambda: find_text_external(find_entry.get()))
        find_button.place(x=191, y=8)
        find_button.config(state='disabled')
        find_entry.bind("<KeyRelease>", on_entry_changed)

        direction = tk.IntVar()
        match = tk.IntVar()

        find_radio_up = tk.Radiobutton(find_window, text="위로", variable=direction, value=0)
        find_radio_up.place(x=25, y=40)

        find_radio_down = tk.Radiobutton(find_window, text="아래로", variable=direction, value=1)
        find_radio_down.place(x=75, y=40)

        find_checkbox_match = tk.Checkbutton(find_window, text="매치", variable=match)
        find_checkbox_match.place(x=150, y=40)
    else:
        find_window.lift()  # 이미 열려 있는 경우에는 해당 창을 화면 제일 앞으로 이동시킵니다.
        find_window.focus_force()  # Find 창에 포커스를 줍니다.
        find_entry.focus_force()

def on_find_window_close():
    global find_window, last_search_pos
    last_search_pos = None 
    text.tag_remove("found", "1.0", tk.END)

    find_window.destroy()
    find_window = None  # 창이 닫힐 때 참조를 제거하여 다시 열 수 있도록 설정합니다.

last_search_pos = None  # 마지막으로 찾은 위치를 저장할 변수

def on_entry_changed(event):
    global find_entry, find_button

    if find_entry.get() != "":
        find_button.config(state='normal')
    else:
        find_button.config(state='disabled')


def find_text_external(search_term):
    global find_window, text, direction, last_search_pos, match
    
    # Convert search term to lowercase if case-insensitive search is requested
    if not match.get():
        search_term = search_term.lower()

    # 모든 하이라이트 초기화
    text.tag_remove("found", "1.0", tk.END)

    if search_term:
        if direction.get() == 0:    # Up
            startLoc = tk.INSERT
            endLoc = "1.0"
        else:   # Down
            startLoc = "1.0"
            endLoc = tk.END

        # 대소문자 일치 여부 결정
        if match.get() == 0:
            case_sensitive = True
        else:
            case_sensitive = False

        start_pos = None
        if last_search_pos:
            if direction.get() == 0:  # Up 방향 검색
                start_pos = text.search(search_term, last_search_pos, endLoc, nocase=case_sensitive, backwards=True)
            else:  # Down 방향 검색
                start_pos = text.search(search_term, last_search_pos, endLoc, nocase=case_sensitive)
        
        if start_pos == "":
            messagebox.showinfo("알림", "\"" + search_term + "\"을(를) 찾을 수 없습니다.")
            find_window.lift()
            find_window.focus_force()  # Find 창에 포커스를 줍니다.
            find_entry.focus_force()
            return
            
        if not start_pos:
            # 이전 위치에서 검색어를 찾을 수 없는 경우 처음부터 다시 검색
            if direction.get() == 0:  # Up 방향 검색
                start_pos = text.search(search_term, startLoc, endLoc, nocase=case_sensitive, backwards=True)
            else:  # Down 방향 검색
                start_pos = text.search(search_term, startLoc, endLoc, nocase=case_sensitive)

        if start_pos:
            end_pos = f"{start_pos}+{len(search_term)}c"
            text.tag_add("found", start_pos, end_pos)
            text.see(start_pos)
            text.tag_config("found", background="yellow")
            if direction.get() == 0:  # Up 방향 검색일 때
                last_search_pos = f"{start_pos}-{len(search_term)-1}c"  # 이전에 찾은 위치에서 검색한 단어의 길이를 뺍니다.
            else:  # Down 방향 검색일 때
                last_search_pos = f"{start_pos}+{len(search_term)}c"  # 검색어의 길이만큼 앞으로 이동하여 다음 검색을 시작합니다.
                
def clear_text(event=None):
    text.delete("1.0", tk.END)

def on_selection_changed(event):
    global selected_text

    selected_range = text.tag_ranges(tk.SEL)
    if selected_range:
        selected_text = text.get(selected_range[0], selected_range[1])
        print("Selected Text:", selected_text)
    else:
        selected_text = ""  # 선택된 텍스트가 없으면 비웁니다.
        print("No text selected.")

def bring_find_window_to_front(event):
    global find_window
    if find_window and find_window.winfo_exists():  # 서브 창이 존재하는지 확인합니다.
        find_window.lift()

def aboutInfo():
    x_coord = root.winfo_x()
    y_coord = root.winfo_y()

    resize = "300x45+" + str(x_coord + 350) + "+" + str(y_coord + 180)

    about_window = tk.Toplevel(root)
    about_window.title("정보")
    about_window.focus_force()

    # 아이콘 설정
    about_window.iconbitmap(icon_path)
    about_window.geometry(resize)

    about_label = tk.Label(about_window, text="ⓒ 2024. JongSeong. All Rights Reserved.\nIcon created by Smashicons.", justify="center")
    about_label.pack(pady=7)

# Tkinter 애플리케이션 생성
root = tk.Tk()
root.title("JS Tail")
root.geometry("1000x400+500+500")  # 창 크기 설정

# 아이콘 설정
root.iconbitmap(icon_path)

# StringVar 생성
selected_font = tk.StringVar()  # 선택된 폰트를 저장하는 변수
selected_size = tk.StringVar()  # 선택된 크기를 저장하는 변수

# 텍스트 영역 생성
text_frame = tk.Frame(root)
text_frame.pack(expand=True, fill=tk.BOTH)

text_scrollbar_y = tk.Scrollbar(text_frame)
text_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

text_scrollbar_x = tk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
text_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

text = tk.Text(text_frame, yscrollcommand=text_scrollbar_y.set, xscrollcommand=text_scrollbar_x.set, wrap="none")
text.pack(expand=True, fill=tk.BOTH)

text_scrollbar_y.config(command=text.yview)
text_scrollbar_x.config(command=text.xview)

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

# 텍스트에서 드래그 인식 이벤트
text.bind("<<Selection>>", on_selection_changed)

root.bind("<Button-1>", bring_find_window_to_front)

# 초기 파일 경로
file_path = load_last_file()

# 초기 내용
previous_content = ""

# 애플리케이션 실행
update_title()  # 초기 타이틀 설정
root.after(1000, update_tail)
root.mainloop()
