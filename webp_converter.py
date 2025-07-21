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
        self.frame_color = "#000000"
        self.frame_thickness = tk.StringVar(value="20")

        # 미리보기 이미지 객체
        self.tk_preview_img = None

        # UI 구성
        self.build_layout()

    def build_layout(self):
        # 좌우 프레임 분리
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)

        left_frame = tk.Frame(main_frame)
        left_frame.pack(side="left", padx=10, pady=10)

        preview_frame = tk.Frame(main_frame, width=400, height=400)
        preview_frame.pack(side="right", padx=10, pady=10)
        preview_frame.pack_propagate(False)

        self.preview_label = tk.Label(preview_frame)
        self.preview_label.pack()

        # 왼쪽 기능 UI
        tk.Button(left_frame, text="이미지 선택", command=self.select_files).pack(pady=5)
        tk.Button(left_frame, text="저장 폴더 선택", command=self.select_output_dir).pack(pady=5)

        self.rename_mode = tk.StringVar(value="original")
        tk.Label(left_frame, text="이름 변경 옵션:").pack()
        tk.Radiobutton(left_frame, text="원래 이름 유지", variable=self.rename_mode, value="original").pack()
        tk.Radiobutton(left_frame, text="접두사 + 번호", variable=self.rename_mode, value="custom").pack()

        self.prefix_entry = tk.Entry(left_frame)
        self.prefix_entry.insert(0, "image")
        self.prefix_entry.pack()

        # 액자 옵션
        tk.Checkbutton(left_frame, text="액자 추가", variable=self.add_frame, command=self.toggle_frame_options).pack(pady=5)

        self.color_button = tk.Button(left_frame, text="액자 색상 선택", command=self.choose_color, state="disabled")
        self.color_button.pack()

        self.thickness_label = tk.Label(left_frame, text="액자 두께(px):", state="disabled")
        self.thickness_label.pack()

        self.thickness_entry = tk.Entry(left_frame, textvariable=self.frame_thickness, state="disabled")
        self.thickness_entry.pack()

        tk.Button(left_frame, text="미리보기", command=self.preview_image).pack(pady=5)

        self.progress = ttk.Progressbar(left_frame, orient="horizontal", length=250, mode="determinate")
        self.progress.pack(pady=10)

        tk.Button(left_frame, text="변환 시작", command=self.start_conversion).pack(pady=10)

    def toggle_frame_options(self):
        state = "normal" if self.add_frame.get() else "disabled"
        self.color_button.config(state=state)
        self.thickness_entry.config(state=state)
        self.thickness_label.config(state=state)

    def choose_color(self):
        color_code = colorchooser.askcolor(title="액자 색상 선택")
        if color_code[1]:
            self.frame_color = color_code[1]

    def select_files(self):
        self.file_paths = filedialog.askopenfilenames(filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if self.file_paths:
            self.output_dir = str(Path(self.file_paths[0]).parent)
            messagebox.showinfo("파일 선택", f"{len(self.file_paths)}개의 파일을 선택했습니다.\n"
                                         f"저장 경로 자동 설정: {self.output_dir}")
            self.preview_image()  # 이미지 선택 시 미리보기도 자동 업데이트

    def select_output_dir(self):
        self.output_dir = filedialog.askdirectory()
        messagebox.showinfo("저장 경로", f"저장 경로: {self.output_dir}")

    def preview_image(self):
        if not self.file_paths:
            return

        try:
            thickness = int(self.frame_thickness.get()) if self.add_frame.get() else 0
            if thickness < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("입력 오류", "액자 두께는 양의 정수여야 합니다.")
            return

        image = Image.open(self.file_paths[0]).convert("RGB")

        if self.add_frame.get():
            image = ImageOps.expand(image, border=thickness, fill=self.frame_color)

        # 미리보기용 크기로 축소
        max_size = (400, 400)
        image.thumbnail(max_size)

        self.tk_preview_img = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.tk_preview_img)

    def start_conversion(self):
        if not self.file_paths:
            messagebox.showwarning("경고", "변환할 이미지를 선택하세요.")
            return
        if not self.output_dir:
            messagebox.showwarning("경고", "저장 경로를 선택하세요.")
            return

        try:
            thickness = int(self.frame_thickness.get()) if self.add_frame.get() else 0
            if thickness < 0:
                raise ValueError("음수는 허용되지 않습니다.")
        except ValueError:
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

        messagebox.showinfo("변환 완료", "\n".join(results[:10]) + ("\n... (생략)" if len(results) > 10 else ""))
        self.progress["value"] = 100


if __name__ == "__main__":
    root = tk.Tk()
    app = WebPConverterGUI(root)
    root.mainloop()

