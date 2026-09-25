import sys
import tkinter as tk
import analyzer
from tkinter import messagebox, filedialog
from contextlib import redirect_stdout
import io

def show_error(error):
    messagebox.showinfo('Error', error)


def show_save_file_message(file_path):
    messagebox.showinfo('Information', 'Report was successfully saved in file: \n' + file_path)


class MainAnalyzerWindow(tk.Frame):
    global_filename = ''

    def __init__(self, *args, **kwargs):
        tk.Frame.__init__(self, *args, **kwargs)
        self.code_text_label = tk.Label(self, text='Исходный код:')
        self.code_text_label.grid(row=0, column=0)
        self.ok_button = tk.Button(self, text="Выберите файл для анализа", command=self._get_file)
        self.ok_button.grid(row=0, column=1)
        self.code_text = tk.Text(self)
        self.code_text.grid(row=1, column=0)
        self.review_text_label = tk.Label(self, text='Результат анализа:')
        self.review_text_label.grid(row=0, column=2)
        self.review_text = tk.Text(self)
        self.review_text.grid(row=1, column=2)
        self.analyze_button = tk.Button(self, text="Анализировать", command=self._send_analyze_command)
        self.analyze_button.grid(row=6, column=0)
        self.save_report_button = tk.Button(self, text="Сохранить отчёт", command=self._send_save_report_command)
        self.save_report_button.grid(row=6, column=2)

    def _send_analyze_command(self):
        self._on_analyze_code()

    def _get_file(self):
        code = ""
        file = filedialog.askopenfilename()
        self.global_filename = file
        if file:
            with open(file, "r", encoding="utf-8") as file:
                code = file.read()
            self.code_text.insert(tk.END, code)

    def _on_analyze_code(self):
        try:
            result = "Ошибка при анализе файла"
            with io.StringIO() as stdout_buf, redirect_stdout(stdout_buf):
                result = analyzer.analyze(self.global_filename)
                result = stdout_buf.getvalue()
            self.review_text.delete(1.0, tk.END)
            self.review_text.update()
            self.review_text.insert(tk.END, result)
            self.review_text.update()
        except Exception as e:
            show_error(str(e))

    def _send_save_report_command(self):
        self.review_text.update()
        filename = filedialog.asksaveasfile(defaultextension='.txt')
        file = open(filename.name, "w")
        file.write(self.review_text.get("1.0", tk.END))
        if file:
            show_save_file_message(filename.name)
            file.close()


if __name__ == "__main__":
    root = tk.Tk()
    root.title('Дипломная работа. Статический анализатор.')
    root.geometry('1310x500')
    main = MainAnalyzerWindow(root)
    main.pack(side="top", fill="both", padx=10, expand=True)
    root.mainloop()
