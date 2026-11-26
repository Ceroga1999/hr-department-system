import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import psycopg2
import csv
import os
import platform
import subprocess
from reportlab.lib.pagesizes import A2
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.lib.colors import HexColor

# === НАСТРОЙКИ ПОДКЛЮЧЕНИЯ К БД ===
DB_CONFIG = {
    "dbname": "HR",
    "user": "postgres",
    "password": "",  # Укажите ваш пароль
    "host": "localhost",
    "port": "5432"
}

TABLES = [
    "roles", "users", "departments", "positions", "employees",
    "employee_events", "documents", "absences", "notifications",
    "audit_log", "integration_queue"
]

class HRApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("ИС «Отдел кадров» - Панель управления")
        self.root.geometry("1200x700")
        
        self.current_table = None
        self.conn = None
        self.connect_db()
        self.setup_ui()

    def connect_db(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = True
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось подключиться к базе данных:\n{e}")
            self.root.destroy()

    def setup_ui(self):
        left_frame = tk.Frame(self.root, width=200, bg="#f0f0f0")
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(left_frame, text="Таблицы:", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=10)
        
        self.table_listbox = tk.Listbox(left_frame, font=("Arial", 11))
        self.table_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        for t in TABLES:
            self.table_listbox.insert(tk.END, t)
        self.table_listbox.bind("<<ListboxSelect>>", self.on_table_select)

        right_frame = tk.Frame(self.root)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        toolbar = tk.Frame(right_frame)
        toolbar.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(toolbar, text="🔄 Обновить", command=self.load_data).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="➕ Добавить", command=self.add_record).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="✏️ Изменить", command=self.edit_record).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="❌ Удалить", command=self.delete_record).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="📥 Экспорт CSV", command=self.export_csv).pack(side=tk.LEFT, padx=15)
        tk.Button(toolbar, text="📤 Импорт CSV", command=self.import_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="📄 ER Диаграмма (PDF)", command=self.show_er_diagram, bg="#f0ad4e", fg="white").pack(side=tk.RIGHT, padx=5)

        self.tree = ttk.Treeview(right_frame, show="headings")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        vsb = ttk.Scrollbar(right_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(right_frame, orient="horizontal", command=self.tree.xview)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    def on_table_select(self, event):
        selection = self.table_listbox.curselection()
        if selection:
            self.current_table = self.table_listbox.get(selection[0])
            self.load_data()

    def load_data(self):
        if not self.current_table: return
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        cur = self.conn.cursor()
        try:
            cur.execute(f"SELECT * FROM {self.current_table} ORDER BY id LIMIT 1000;")
            colnames = [desc[0] for desc in cur.description]
            
            self.tree["columns"] = colnames
            for col in colnames:
                self.tree.heading(col, text=col, anchor=tk.W)
                self.tree.column(col, width=100, anchor=tk.W)
                
            for row in cur.fetchall():
                self.tree.insert("", tk.END, values=row)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить данные:\n{e}")
        finally:
            cur.close()

    def get_columns(self):
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM {self.current_table} LIMIT 0")
        cols = [desc[0] for desc in cur.description]
        cur.close()
        return cols

    def add_record(self):
        if not self.current_table: return
        cols = self.get_columns()
        self.open_edit_window(cols, mode="add")

    def edit_record(self):
        if not self.current_table: return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите строку для редактирования.")
            return
        row_values = self.tree.item(selected[0])['values']
        cols = self.get_columns()
        self.open_edit_window(cols, mode="edit", values=row_values)

    def open_edit_window(self, cols, mode, values=None):
        win = tk.Toplevel(self.root)
        win.title("Добавление записи" if mode == "add" else "Редактирование записи")
        win.geometry("400x600")
        
        entries = {}
        frame = tk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for i, col in enumerate(cols):
            tk.Label(scrollable_frame, text=col).grid(row=i, column=0, sticky="w", pady=5, padx=5)
            ent = tk.Entry(scrollable_frame, width=30)
            ent.grid(row=i, column=1, pady=5, padx=5)
            if mode == "edit":
                val = values[i] if i < len(values) else ""
                ent.insert(0, str(val) if val is not None else "")
                if col == "id":
                    ent.config(state="disabled")
            entries[col] = ent

        def save():
            data = {col: entries[col].get() for col in cols if entries[col].cget("state") != "disabled"}
            if not data: return
            
            vals = [None if v == "" else v for v in data.values()]
            keys = list(data.keys())
            
            cur = self.conn.cursor()
            try:
                if mode == "add":
                    query = f"INSERT INTO {self.current_table} ({', '.join(keys)}) VALUES ({', '.join(['%s']*len(keys))})"
                    cur.execute(query, vals)
                else:
                    id_val = values[0]
                    set_clause = ", ".join([f"{k} = %s" for k in keys])
                    query = f"UPDATE {self.current_table} SET {set_clause} WHERE id = %s"
                    cur.execute(query, vals + [id_val])
                
                self.load_data()
                win.destroy()
            except Exception as e:
                messagebox.showerror("Ошибка SQL", str(e), parent=win)
            finally:
                cur.close()

        tk.Button(scrollable_frame, text="Сохранить", command=save, bg="#5cb85c", fg="white", font=("Arial", 10, "bold")).grid(row=len(cols), column=0, columnspan=2, pady=20, sticky="we")

    def delete_record(self):
        if not self.current_table: return
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите строку для удаления.")
            return
            
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите удалить эту запись?"):
            row_values = self.tree.item(selected[0])['values']
            id_val = row_values[0]
            cur = self.conn.cursor()
            try:
                cur.execute(f"DELETE FROM {self.current_table} WHERE id = %s", (id_val,))
                self.load_data()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить запись:\n{e}")
            finally:
                cur.close()

    def export_csv(self):
        if not self.current_table: return
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV файлы", "*.csv")])
        if not filepath: return
        
        try:
            cur = self.conn.cursor()
            cur.execute(f"SELECT * FROM {self.current_table}")
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(colnames)
                writer.writerows(rows)
            messagebox.showinfo("Успех", "Данные успешно экспортированы в CSV.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка экспорта:\n{e}")
        finally:
            cur.close()

    def import_csv(self):
        if not self.current_table: return
        filepath = filedialog.askopenfilename(filetypes=[("CSV файлы", "*.csv")])
        if not filepath: return
        
        try:
            cur = self.conn.cursor()
            cur.execute(f"SELECT * FROM {self.current_table} LIMIT 0")
            db_cols = [desc[0] for desc in cur.description]
            
            with open(filepath, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f, delimiter=";")
                header = next(reader)
                
                if header != db_cols:
                    messagebox.showerror("Ошибка", "Столбцы в CSV файле не совпадают с таблицей БД.")
                    return

                count = 0
                for row in reader:
                    placeholders = ', '.join(['%s'] * len(row))
                    query = f"INSERT INTO {self.current_table} VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"
                    cur.execute(query, row)
                    count += 1
                    
            self.load_data()
            messagebox.showinfo("Успех", f"Импортировано строк: {count}.")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка импорта:\n{e}")
        finally:
            cur.close()

    def show_er_diagram(self):
        cur = self.conn.cursor()
        try:
            # 1. Получаем таблицы
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]

            # 2. Получаем поля
            schema = {}
            for table in tables:
                cur.execute(f"""
                    SELECT column_name, data_type FROM information_schema.columns 
                    WHERE table_name = '{table}' AND table_schema = 'public' ORDER BY ordinal_position
                """)
                schema[table] = cur.fetchall()

            # 3. Получаем связи (внешние ключи) с указанием конкретных колонок
            cur.execute("""
                SELECT
                    tc.table_name AS from_table,
                    kcu.column_name AS from_column,
                    ccu.table_name AS to_table,
                    ccu.column_name AS to_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
            """)
            fks = cur.fetchall()
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            return
        finally:
            cur.close()

        # 4. Настройка холста
        page_width, page_height = A2
        d = Drawing(page_width, page_height)
        
        cols_grid = 4
        padding = 50
        table_w = 250
        header_h = 30
        row_h = 20
        
        # Вычисляем высоту каждой таблицы
        table_heights = {t: header_h + len(cols_list) * row_h for t, cols_list in schema.items()}
        max_h = max(table_heights.values())
        
        spacing_x = (page_width - 2 * padding - cols_grid * table_w) / (cols_grid - 1)
        rows = (len(tables) + cols_grid - 1) // cols_grid
        spacing_y = (page_height - 2 * padding - rows * max_h) / max(1, (rows - 1))

        # Словари для хранения координат
        table_positions = {}
        attr_coords = {} # attr_coords[table][col] = {'left': (x,y), 'right': (x,y)}

        # 5. Рассчитываем координаты всех таблиц и их полей
        for i, table in enumerate(tables):
            col = i % cols_grid
            row = i // cols_grid
            
            x = padding + col * (table_w + spacing_x)
            y = page_height - padding - (row + 1) * max_h - row * spacing_y
            h = table_heights[table]
            
            table_positions[table] = (x, y, table_w, h)
            attr_coords[table] = {}
            
            for j, (col_name, _) in enumerate(schema[table]):
                # Вычисляем Y-координату центра строки с атрибутом
                y_center = y + h - header_h - (j * row_h) - (row_h / 2)
                attr_coords[table][col_name] = {
                    'left': (x, y_center),
                    'right': (x + table_w, y_center)
                }

        # 6. Рисуем связи (до отрисовки таблиц, чтобы они были на заднем плане)
        for from_table, from_col, to_table, to_col in fks:
            if from_table in attr_coords and from_col in attr_coords[from_table] and \
               to_table in attr_coords and to_col in attr_coords[to_table]:
                
                p_from = attr_coords[from_table][from_col]
                p_to = attr_coords[to_table][to_col]
                
                # Определяем, с каких краев соединять
                if table_positions[from_table][0] < table_positions[to_table][0]:
                    pt1 = p_from['right']
                    pt2 = p_to['left']
                else:
                    pt1 = p_from['left']
                    pt2 = p_to['right']
                
                # Рисуем линию
                line = Line(pt1[0], pt1[1], pt2[0], pt2[1])
                line.strokeColor = HexColor("#ff7f0e")
                line.strokeWidth = 1.5
                d.add(line)
                
                # Рисуем точки на концах линий (маркеры)
                d.add(Circle(pt1[0], pt1[1], 3, fillColor=HexColor("#ff7f0e"), strokeColor=None))
                d.add(Circle(pt2[0], pt2[1], 3, fillColor=HexColor("#ff7f0e"), strokeColor=None))

        # 7. Рисуем сами таблицы поверх линий
        for table in tables:
            x, y, w, h = table_positions[table]
            
            # Белый фон таблицы (перекрывает линии)
            rect = Rect(x, y, w, h, fillColor=HexColor("#ffffff"), strokeColor=HexColor("#4A90E2"))
            rect.strokeWidth = 2
            d.add(rect)
            
            # Синий заголовок
            d.add(Rect(x, y + h - header_h, w, header_h, fillColor=HexColor("#4A90E2"), strokeColor=HexColor("#4A90E2")))
            d.add(String(x + 10, y + h - 20, table, fontName="Helvetica-Bold", fontSize=12, fillColor=HexColor("#ffffff")))
            
            # Поля
            for j, (col_name, col_type) in enumerate(schema[table]):
                text_y = y + h - header_h - (j * row_h) - 14
                
                d.add(String(x + 10, text_y, col_name, fontName="Helvetica-Bold", fontSize=10, fillColor=HexColor("#333333")))
                # Ограничиваем длину типа данных
                type_str = str(col_type)[:15].split('(')[0] 
                d.add(String(x + 130, text_y, type_str, fontName="Helvetica", fontSize=9, fillColor=HexColor("#888888")))

        # 8. Сохранение и открытие
        pdf_filename = "er_diagram.pdf"
        try:
            d.save(formats=['pdf'], outDir='.', fnRoot='er_diagram')
            filepath = os.path.abspath(pdf_filename)
            
            if platform.system() == 'Windows':
                os.startfile(filepath)
            elif platform.system() == 'Darwin':
                subprocess.call(('open', filepath))
            else:
                subprocess.call(('xdg-open', filepath))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить PDF:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = HRApplication(root)
    root.mainloop()