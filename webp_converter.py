import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser
from PIL import Image, ImageOps, ImageTk
from pathlib import Path
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing


def convert_image(input_path, output_dir, rename_mode, prefix=None, index=None, frame=False, frame_color="#000000", frame_thickness=20):
    try:
        image = Image.open(input_path).convert("RGB")

        if frame:
            image = ImageOps.expand(image, border=frame_thickness, fill=frame_color)

        if rename_mode == "original":
            output_name = Path(input_path).stem + ".webp"
        else:
            output_name = f"{prefix}_{index}.webp"
        output_path = os.path.join(output_dir, output_name)
        image.save(output_path, "WEBP")
        return f"완료: {output_path}"
    except Exception as e:
        return f"실패: {input_path} - {str(e)}"


class WebPConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("WebP 변환기")
        self.file_paths = []
        self.output_dir = ""

        # 액자 옵션
        self.add_frame = tk.BooleanVar()
        self.frame_color = "#ffffff"
        self.frame_thickness = tk.StringVar(value="100")

        # 미리보기 이미지 객체
        self.tk_preview_img = None
        self._resize_after_id = None  # 디바운스용

        # UI 구성
        self.build_layout()

    def build_layout(self):
        # 좌우 프레임 grid 배치
        main_frame = tk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=0)
        main_frame.grid_columnconfigure(1, weight=1)

        left_frame = tk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky="ns", padx=10, pady=10)

        self.selected_output_label = tk.Label(left_frame, text="저장 경로: 없음", anchor="w", justify="left", wraplength=250)
        self.selected_output_label.pack(pady=(0, 10), fill="x")

        # 파일 선택/리스트 영역 그룹화
        file_frame = tk.LabelFrame(left_frame, text="파일 선택", padx=5, pady=5)
        file_frame.pack(fill="x", pady=(0, 10))
        tk.Button(file_frame, text="이미지 선택", command=self.select_files).pack(fill="x", pady=2)
        self.files_listbox = tk.Listbox(file_frame, height=5, width=35)
        self.files_listbox.pack(fill="x", pady=2)
        self.files_listbox.bind("<<ListboxSelect>>", self.on_file_select)

        # 저장 경로 영역 그룹화
        output_frame = tk.LabelFrame(left_frame, text="저장 경로", padx=5, pady=5)
        output_frame.pack(fill="x", pady=(0, 10))
        tk.Button(output_frame, text="저장 폴더 선택", command=self.select_output_dir).pack(fill="x", pady=2)
        self.selected_output_label = tk.Label(output_frame, text="저장 경로: 없음", anchor="w", justify="left", wraplength=250)
        self.selected_output_label.pack(fill="x", pady=2)

        # 이름 변경 옵션 그룹화
        rename_frame = tk.LabelFrame(left_frame, text="이름 변경 옵션", padx=5, pady=5)
        rename_frame.pack(fill="x", pady=(0, 10))
        self.rename_mode = tk.StringVar(value="original")
        tk.Radiobutton(rename_frame, text="원래 이름 유지", variable=self.rename_mode, value="original", command=self.toggle_prefix_entry).pack(anchor="w")
        tk.Radiobutton(rename_frame, text="접두사 + 번호", variable=self.rename_mode, value="custom", command=self.toggle_prefix_entry).pack(anchor="w")
        self.prefix_entry = tk.Entry(rename_frame)
        self.prefix_entry.insert(0, "image")
        self.prefix_entry.pack(fill="x", pady=2)
        self.prefix_entry.config(state="disabled")

        # 액자 옵션 그룹화
        frame_option_frame = tk.LabelFrame(left_frame, text="액자 옵션", padx=5, pady=5)
        frame_option_frame.pack(fill="x", pady=(0, 10))
        tk.Checkbutton(frame_option_frame, text="액자 추가", variable=self.add_frame, command=lambda: [self.toggle_frame_options(), self.preview_image(self._last_preview_idx)]).pack(anchor="w", pady=2)
        self.color_button = tk.Button(frame_option_frame, text="액자 색상 선택", command=lambda: [self.choose_color(), self.preview_image(self._last_preview_idx)], state="disabled")
        self.color_button.pack(fill="x", pady=2)
        self.thickness_label = tk.Label(frame_option_frame, text="액자 두께(px):", state="disabled")
        self.thickness_label.pack(anchor="w")
        self.thickness_entry = tk.Entry(frame_option_frame, textvariable=self.frame_thickness, state="disabled")
        self.thickness_entry.pack(fill="x", pady=2)
        self.thickness_entry.bind('<KeyRelease>', lambda e: self.preview_image(self._last_preview_idx))

        # 진행/실행 버튼 그룹화 (미리보기 버튼 삭제)
        action_frame = tk.Frame(left_frame)
        action_frame.pack(fill="x", pady=(0, 10))
        self.progress = ttk.Progressbar(action_frame, orient="horizontal", length=250, mode="determinate")
        self.progress.pack(fill="x", pady=5)
        self.convert_button = tk.Button(action_frame, text="변환 시작", command=self.start_conversion)
        self.convert_button.pack(fill="x", pady=2)

        preview_frame = tk.Frame(main_frame, width=400, height=400)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1, minsize=400)
        preview_frame.grid_propagate(False)
        preview_frame.config(width=400, height=400)

        self.preview_label = tk.Label(preview_frame, bg=None)
        self.preview_label.pack(fill="both", expand=True)
        preview_frame.bind("<Configure>", self.on_preview_resize)
        self.preview_frame = preview_frame
        self._last_preview_idx = 0  # 마지막 미리보기 인덱스 기억
        self._last_preview_size = (0, 0)  # 마지막 프레임 크기 기억

    def toggle_frame_options(self):
        state = "normal" if self.add_frame.get() else "disabled"
        self.color_button.config(state=state)
        self.thickness_entry.config(state=state)
        self.thickness_label.config(state=state)

    def toggle_prefix_entry(self):
        if self.rename_mode.get() == "custom":
            self.prefix_entry.config(state="normal")
        else:
            self.prefix_entry.config(state="disabled")

    def choose_color(self):
        color_code = colorchooser.askcolor(title="액자 색상 선택")
        if color_code[1]:
            self.frame_color = color_code[1]

    def update_selected_files_label(self):
        # self.selected_files_label 제거, 리스트박스만 갱신
        if not self.file_paths:
            self.files_listbox.delete(0, tk.END)
        else:
            self.files_listbox.delete(0, tk.END)
            for f in self.file_paths:
                self.files_listbox.insert(tk.END, Path(f).name)

    def update_selected_output_label(self):
        if not self.output_dir:
            self.selected_output_label.config(text="저장 경로: 없음")
        else:
            self.selected_output_label.config(text=f"저장 경로: {self.output_dir}")

    def on_file_select(self, event=None):
        # 리스트에서 선택된 파일로 미리보기 갱신
        if not self.file_paths:
            return
        selection = self.files_listbox.curselection()
        if selection:
            idx = selection[0]
        else:
            idx = 0
        self.preview_image(idx)

    def select_files(self):
        self.file_paths = filedialog.askopenfilenames(filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if self.file_paths:
            self.output_dir = str(Path(self.file_paths[0]).parent)
            self.update_selected_files_label()
            self.update_selected_output_label()
            self.files_listbox.selection_clear(0, tk.END)
            self.files_listbox.selection_set(0)
            self.files_listbox.activate(0)
            self.preview_image(0)  # 첫 번째 파일로 미리보기
        else:
            self.update_selected_files_label()

    def select_output_dir(self):
        self.output_dir = filedialog.askdirectory()
        self.update_selected_output_label()
        self.preview_image(self._last_preview_idx)

    def preview_image(self, idx=0):
        self._last_preview_idx = idx
        if not self.file_paths:
            # 파일 없을 때 미리보기 영역 비우기
            self.preview_label.config(image='', text='미리보기 없음', bg=None)
            return

        if self.add_frame.get():
            try:
                thickness = int(self.frame_thickness.get())
            except Exception:
                thickness = 0
        else:
            thickness = 0

        # idx가 범위 벗어나면 0으로
        if idx < 0 or idx >= len(self.file_paths):
            idx = 0
        image = Image.open(self.file_paths[idx]).convert("RGB")

        if self.add_frame.get():
            image = ImageOps.expand(image, border=thickness, fill=self.frame_color)

        # 프레임 크기를 고정값(400, 400)으로 사용
        frame_w, frame_h = 400, 400
        max_size = (frame_w, frame_h)
        image.thumbnail(max_size, Image.LANCZOS)

        # 배경 이미지를 만들고 중앙에 합성 (비율 유지)
        bg = Image.new("RGBA", max_size, (255, 255, 255, 0))
        img_w, img_h = image.size
        offset = ((frame_w - img_w) // 2, (frame_h - img_h) // 2)
        bg.paste(image, offset)

        self.tk_preview_img = ImageTk.PhotoImage(bg)
        self.preview_label.configure(image=self.tk_preview_img, text='')

    def on_preview_resize(self, event):
        # 디바운스: 여러 번 이벤트가 발생해도 마지막에 한 번만 preview_image 호출
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)
        def do_resize():
            w, h = self.preview_frame.winfo_width(), self.preview_frame.winfo_height()
            if (w, h) != getattr(self, '_last_preview_size', (None, None)):
                self._last_preview_size = (w, h)
                self.preview_image(self._last_preview_idx)
        self._resize_after_id = self.root.after(50, do_resize)

    def start_conversion(self):
        if not self.file_paths:
            messagebox.showwarning("경고", "변환할 이미지를 선택하세요.")
            return
        if not self.output_dir:
            messagebox.showwarning("경고", "저장 경로를 선택하세요.")
            return

        # 변환 시작 버튼 비활성화 및 텍스트 변경
        self.convert_button.config(state="disabled", text="변환 중...")
        self.root.update_idletasks()

        try:
            thickness = int(self.frame_thickness.get()) if self.add_frame.get() else 0
            if thickness < 0:
                raise ValueError
        except Exception:
            messagebox.showerror("입력 오류", "액자 두께는 양의 정수여야 합니다.")
            return

        self.progress["value"] = 0
        self.root.update_idletasks()

        rename_mode = self.rename_mode.get()
        prefix = self.prefix_entry.get() if rename_mode == "custom" else None

        num_files = len(self.file_paths)
        results = []

        with ProcessPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            futures = []
            for i, file in enumerate(self.file_paths):
                futures.append(
                    executor.submit(
                        convert_image, file, self.output_dir,
                        rename_mode, prefix, i + 1,
                        self.add_frame.get(), self.frame_color, thickness
                    )
                )

            for i, f in enumerate(as_completed(futures), 1):
                results.append(f.result())
                percent = (i / num_files) * 100
                self.progress["value"] = percent
                self.root.update_idletasks()

        self.progress["value"] = 100
        # 변환 시작 버튼 다시 활성화 및 텍스트 복구
        self.convert_button.config(state="normal", text="변환 시작")


if __name__ == "__main__":
    root = tk.Tk()
    app = WebPConverterGUI(root)
    root.mainloop()

