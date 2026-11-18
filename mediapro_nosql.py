"""
MediaPro - Panel de administración MongoDB
Interfaz de escritorio con Tkinter + PyMongo.

Requisitos:
    pip install pymongo

Conexión predeterminada:
    mongodb://localhost:27017/
Base de datos:
    mediapro_nosql

IMPORTANTE:
- Este programa NO elimina colecciones ni reinicializa la base de datos.
- Crear, actualizar y eliminar solo afecta el documento seleccionado o creado.
- Los documentos se editan como JSON extendido de MongoDB para conservar
  tipos como ObjectId y fechas.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson import json_util


MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "mediapro_nosql"

COLLECTIONS = [
    "producciones",
    "localizaciones",
    "personal",
    "talento",
    "equipo_tecnico",
]


class JsonDocumentDialog(tk.Toplevel):
    """Ventana para crear o editar un documento completo en formato JSON."""

    def __init__(self, parent, title, initial_document=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("680x520")
        self.minsize(540, 400)
        self.configure(bg="#f3f6fb")
        self.transient(parent)
        self.grab_set()
        self.result = None

        header = tk.Frame(self, bg="#14243a", padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(
            header, text=title, bg="#14243a", fg="white",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Completa el documento en formato JSON. No elimines las llaves { }.",
            bg="#14243a", fg="#cbd5e1", font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(self, bg="#f3f6fb", padx=16, pady=14)
        body.pack(fill="both", expand=True)

        self.editor = tk.Text(
            body, wrap="none", font=("Consolas", 10),
            bg="#ffffff", fg="#172033", insertbackground="#172033",
            relief="solid", bd=1, padx=10, pady=10
        )
        self.editor.pack(side="left", fill="both", expand=True)

        scroll_y = ttk.Scrollbar(body, orient="vertical", command=self.editor.yview)
        scroll_y.pack(side="right", fill="y")
        self.editor.configure(yscrollcommand=scroll_y.set)

        if initial_document is None:
            initial_text = '{\n    "campo": "valor"\n}'
        else:
            initial_text = json_util.dumps(
                initial_document, indent=4, ensure_ascii=False
            )
        self.editor.insert("1.0", initial_text)

        footer = tk.Frame(self, bg="#f3f6fb", padx=16, pady=12)
        footer.pack(fill="x")

        tk.Button(
            footer, text="Cancelar", command=self.destroy,
            bg="#e2e8f0", fg="#1e293b", relief="flat",
            padx=18, pady=8, cursor="hand2"
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            footer, text="Guardar documento", command=self.validate_and_save,
            bg="#167d68", fg="white", relief="flat",
            padx=18, pady=8, cursor="hand2",
            font=("Segoe UI", 9, "bold")
        ).pack(side="right")

        self.editor.focus_set()

    def validate_and_save(self):
        raw = self.editor.get("1.0", "end-1c").strip()
        try:
            document = json_util.loads(raw)
            if not isinstance(document, dict):
                raise ValueError("El contenido debe ser un objeto JSON, es decir, usar { }.")
            if not document:
                raise ValueError("El documento no puede estar vacío.")
            self.result = document
            self.destroy()
        except Exception as exc:
            messagebox.showerror(
                "JSON no válido",
                f"No se pudo interpretar el documento:\n{exc}",
                parent=self
            )


class MediaProApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MediaPro | Administración de datos")
        self.root.geometry("1180x720")
        self.root.minsize(900, 580)
        self.root.configure(bg="#f3f6fb")

        self.client = None
        self.db = None
        self.collection_views = {}
        self.documents_by_iid = {}

        self._configure_styles()
        self._build_header()
        self._build_main()
        self._connect_to_mongodb()

        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    def _configure_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#f3f6fb", borderwidth=0)
        style.configure(
            "TNotebook.Tab", background="#e2e8f0", foreground="#26364a",
            padding=(16, 10), font=("Segoe UI", 9, "bold")
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#167d68")],
            foreground=[("selected", "#ffffff")]
        )
        style.configure(
            "Treeview", background="#ffffff", fieldbackground="#ffffff",
            foreground="#172033", rowheight=30, font=("Segoe UI", 9)
        )
        style.configure(
            "Treeview.Heading", background="#e8eef5",
            foreground="#24364b", font=("Segoe UI", 9, "bold"), padding=8
        )
        style.map("Treeview", background=[("selected", "#cce9e2")],
                  foreground=[("selected", "#14243a")])

    def _build_header(self):
        header = tk.Frame(self.root, bg="#14243a", padx=24, pady=17)
        header.pack(fill="x")

        left = tk.Frame(header, bg="#14243a")
        left.pack(side="left")
        tk.Label(
            left, text="MEDIAPRO", bg="#14243a", fg="#ffffff",
            font=("Segoe UI", 19, "bold")
        ).pack(anchor="w")
        tk.Label(
            left, text="Sistema de gestión audiovisual · MongoDB",
            bg="#14243a", fg="#b8c7d9", font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(3, 0))

        self.connection_label = tk.Label(
            header, text="●  Conectando...",
            bg="#14243a", fg="#f6c76b", font=("Segoe UI", 9, "bold")
        )
        self.connection_label.pack(side="right", padx=4)

    def _build_main(self):
        main = tk.Frame(self.root, bg="#f3f6fb", padx=20, pady=16)
        main.pack(fill="both", expand=True)

        toolbar = tk.Frame(main, bg="#f3f6fb")
        toolbar.pack(fill="x", pady=(0, 12))

        tk.Label(
            toolbar, text="Colecciones de la base de datos",
            bg="#f3f6fb", fg="#24364b",
            font=("Segoe UI", 12, "bold")
        ).pack(side="left")

        self.total_label = tk.Label(
            toolbar, text="Documentos: —",
            bg="#f3f6fb", fg="#64748b", font=("Segoe UI", 9)
        )
        self.total_label.pack(side="right")

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True)

        for collection_name in COLLECTIONS:
            self._create_collection_tab(collection_name)

        actions = tk.Frame(main, bg="#f3f6fb")
        actions.pack(fill="x", pady=(12, 0))

        self._action_button(actions, "＋  Nuevo documento", self.create_document,
                            "#167d68").pack(side="left", padx=(0, 8))
        self._action_button(actions, "✎  Editar seleccionado", self.edit_document,
                            "#2563a6").pack(side="left", padx=8)
        self._action_button(actions, "⌫  Eliminar seleccionado", self.delete_document,
                            "#b74444").pack(side="left", padx=8)
        self._action_button(actions, "↻  Actualizar tabla", self.refresh_current,
                            "#475569").pack(side="right")

        self.status_label = tk.Label(
            main, text="Preparado para conectar.",
            bg="#f3f6fb", fg="#64748b", anchor="w",
            font=("Segoe UI", 8)
        )
        self.status_label.pack(fill="x", pady=(10, 0))

    def _action_button(self, parent, text, command, color):
        return tk.Button(
            parent, text=text, command=command,
            bg=color, fg="white", activebackground=color,
            activeforeground="white", relief="flat", bd=0,
            padx=14, pady=9, cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )

    def _create_collection_tab(self, collection_name):
        frame = tk.Frame(self.notebook, bg="#ffffff")
        self.notebook.add(frame, text=collection_name.replace("_", " ").title())

        info = tk.Frame(frame, bg="#ffffff", padx=12, pady=10)
        info.pack(fill="x")
        tk.Label(
            info, text=f"Colección: {collection_name}",
            bg="#ffffff", fg="#334155", font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        count_label = tk.Label(
            info, text="0 documentos",
            bg="#ffffff", fg="#64748b", font=("Segoe UI", 8)
        )
        count_label.pack(side="right")

        table_frame = tk.Frame(frame, bg="#ffffff", padx=12, pady=12)
        table_frame.pack(fill="both", expand=True)

        tree = ttk.Treeview(table_frame, show="headings", selectmode="browse")
        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        tree.bind("<Double-1>", lambda _event: self.edit_document())

        self.collection_views[collection_name] = {
            "tree": tree,
            "count_label": count_label,
        }

    def _connect_to_mongodb(self):
        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.client.admin.command("ping")
            self.db = self.client[DATABASE_NAME]
            self.connection_label.config(
                text="●  MongoDB conectado", fg="#7ee0b8"
            )
            self.status_label.config(
                text=f"Conectado a {DATABASE_NAME} en {MONGO_URI}"
            )
            self.refresh_all()
        except Exception as exc:
            self.connection_label.config(
                text="●  Sin conexión", fg="#ff9b9b"
            )
            messagebox.showerror(
                "Error de conexión",
                "No fue posible conectar con MongoDB.\n\n"
                "Verifica que el servicio MongoDB esté activo.\n\n"
                f"Detalle: {exc}",
                parent=self.root
            )
            self.status_label.config(text="No hay conexión con MongoDB.")

    def _active_collection_name(self):
        selected = self.notebook.select()
        if not selected:
            return None
        tab_text = self.notebook.tab(selected, "text")
        return tab_text.lower().replace(" ", "_")

    def _selected_document(self):
        collection_name = self._active_collection_name()
        if not collection_name or self.db is None:
            return None, None

        tree = self.collection_views[collection_name]["tree"]
        selection = tree.selection()
        if not selection:
            messagebox.showwarning(
                "Selecciona un registro",
                "Primero selecciona un documento de la tabla.",
                parent=self.root
            )
            return collection_name, None

        return collection_name, self.documents_by_iid.get(selection[0])

    def _display_value(self, value):
        if isinstance(value, (dict, list)):
            return json_util.dumps(value, ensure_ascii=False)
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return str(value) if value is not None else ""

    def refresh_all(self):
        if self.db is None:
            return
        for name in COLLECTIONS:
            self._load_collection(name)
        self._update_total()

    def refresh_current(self):
        name = self._active_collection_name()
        if name and self.db is not None:
            self._load_collection(name)
            self._update_total()

    def _load_collection(self, collection_name):
        view = self.collection_views[collection_name]
        tree = view["tree"]
        collection = self.db[collection_name]

        for item in tree.get_children():
            self.documents_by_iid.pop(item, None)
            tree.delete(item)

        documents = list(collection.find().limit(500))
        keys = []
        for document in documents:
            for key in document.keys():
                if key not in keys:
                    keys.append(key)

        if not keys:
            keys = ["_id"]

        tree["columns"] = keys
        for key in keys:
            tree.heading(key, text=key)
            tree.column(key, width=170, minwidth=100, anchor="w", stretch=True)

        for index, document in enumerate(documents):
            values = [self._display_value(document.get(key, "")) for key in keys]
            iid = tree.insert("", "end", values=values)
            self.documents_by_iid[iid] = document

        count = collection.count_documents({})
        view["count_label"].config(text=f"{count} documentos")
        self.status_label.config(
            text=f"{collection_name}: {len(documents)} documentos mostrados "
                 f"(máximo 500 por vista)."
        )

    def _update_total(self):
        if self.db is None:
            return
        total = sum(self.db[name].count_documents({}) for name in COLLECTIONS)
        self.total_label.config(text=f"Documentos en las 5 colecciones: {total}")

    def create_document(self):
        if self.db is None:
            return
        collection_name = self._active_collection_name()
        dialog = JsonDocumentDialog(
            self.root, f"Nuevo documento · {collection_name}"
        )
        self.root.wait_window(dialog)
        if dialog.result is None:
            return

        try:
            self.db[collection_name].insert_one(dialog.result)
            self._load_collection(collection_name)
            self._update_total()
            messagebox.showinfo(
                "Registro creado",
                f"El documento se guardó en '{collection_name}'.",
                parent=self.root
            )
        except PyMongoError as exc:
            messagebox.showerror(
                "No se pudo crear",
                f"MongoDB rechazó el documento:\n{exc}",
                parent=self.root
            )

    def edit_document(self):
        collection_name, document = self._selected_document()
        if not collection_name or document is None:
            return

        dialog = JsonDocumentDialog(
            self.root, f"Editar documento · {collection_name}", document
        )
        self.root.wait_window(dialog)
        if dialog.result is None:
            return

        if dialog.result.get("_id") != document.get("_id"):
            messagebox.showerror(
                "ID protegido",
                "No cambies el campo _id. MongoDB utiliza ese valor como identificador.",
                parent=self.root
            )
            return

        try:
            result = self.db[collection_name].replace_one(
                {"_id": document["_id"]}, dialog.result
            )
            self._load_collection(collection_name)
            self._update_total()
            if result.matched_count:
                messagebox.showinfo(
                    "Registro actualizado",
                    "Los cambios se guardaron correctamente.",
                    parent=self.root
                )
        except PyMongoError as exc:
            messagebox.showerror(
                "No se pudo actualizar",
                f"MongoDB rechazó la actualización:\n{exc}",
                parent=self.root
            )

    def delete_document(self):
        collection_name, document = self._selected_document()
        if not collection_name or document is None:
            return

        identifier = document.get("_id")
        confirm = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Seguro que deseas eliminar este documento?\n\n"
            f"Colección: {collection_name}\nID: {identifier}\n\n"
            "Esta acción no se puede deshacer.",
            parent=self.root
        )
        if not confirm:
            return

        try:
            result = self.db[collection_name].delete_one({"_id": identifier})
            self._load_collection(collection_name)
            self._update_total()
            if result.deleted_count:
                messagebox.showinfo(
                    "Documento eliminado",
                    "El registro se eliminó correctamente.",
                    parent=self.root
                )
            else:
                messagebox.showwarning(
                    "Sin cambios",
                    "No se encontró el documento para eliminar.",
                    parent=self.root
                )
        except PyMongoError as exc:
            messagebox.showerror(
                "No se pudo eliminar",
                f"Error de MongoDB:\n{exc}",
                parent=self.root
            )

    def close_app(self):
        if self.client is not None:
            self.client.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MediaProApp(root)
    root.mainloop()
