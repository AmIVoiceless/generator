import sys
import sqlite3
from datetime import datetime
from io import BytesIO
import base64

from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *

from docx import Document
import qrcode
from jinja2 import Template

T = {
    "app_title": "Quest Master",
    "quest_title": "Quest title",
    "difficulty": "Difficulty",
    "reward": "Reward (gold)",
    "description": "Description",
    "deadline": "Deadline",
    "create_btn": "Create quest",
    "template_docx": "Export to DOCX",
    "map_editor": "Map Editor",
    "xp_label": "XP:",
    "level_label": "Level:",

    "d_easy": "Easy",
    "d_mid": "Medium",
    "d_hard": "Hard",
    "d_epic": "Epic",

    "err_title": "Title required",
    "err_desc": "Description too short",
    "create_ok": "Quest created",

    "save_map": "Save map"
}

db = sqlite3.connect("quests.db")
cur = db.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS quests(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT UNIQUE NOT NULL,
 difficulty TEXT,
 reward INTEGER,
 description TEXT,
 deadline TEXT,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS locations(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 quest_id INTEGER,
 x INTEGER,
 y INTEGER,
 type TEXT,
 FOREIGN KEY (quest_id) REFERENCES quests(id)
);
""")
db.commit()

LEVELS = {
    "Apprentice": 0,
    "Master of Scrolls": 50,
    "Archmage": 100
}
xp = 0
def add_xp(amount):
    global xp
    xp += amount

TEMPLATE_DOCX_TEXT = """Quest #{id}
Title: {title}
Difficulty: {difficulty}
Reward: {reward} gold
Description: {description}
Deadline: {deadline}
Date: {now}
"""

def highlight(widget, ok: bool):
    widget.setStyleSheet("" if ok else "border:2px solid red")

def fetch_quest(title):
    cur.execute("SELECT * FROM quests WHERE title=?", (title,))
    return cur.fetchone()

def save_docx(quest):
    now = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    filename = f"{quest[0]}_{now}.docx"
    doc = Document()
    doc.add_paragraph(TEMPLATE_DOCX_TEXT.format(
        id=quest[0],
        title=quest[1],
        difficulty=quest[2],
        reward=quest[3],
        description=quest[4],
        deadline=quest[5],
        now=now
    ))
    doc.save(filename)
    add_xp(2)
    QMessageBox.information(None, "Saved", f"Quest exported as {filename}")

class MapEditor(QWidget):
    def __init__(self, quest_id=None):
        super().__init__()
        self.setWindowTitle(T["map_editor"])
        self.setFixedSize(800, 600)
        self.image = QPixmap(800,600)
        self.image.fill(QColor("#f4e4bc"))
        self.last_point = None
        self.pen_color = Qt.GlobalColor.darkYellow
        self.pen_width = 3
        self.quest_id = quest_id
        self.markers = []
        save_btn = QPushButton(T["save_map"])
        save_btn.clicked.connect(self.save_map)
        layout = QVBoxLayout()
        layout.addWidget(save_btn)
        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_point = event.position()
            # Add marker
            self.markers.append((event.position().x(), event.position().y(), "marker"))
            if self.quest_id:
                cur.execute("INSERT INTO locations (quest_id,x,y,type) VALUES (?,?,?,?)",
                            (self.quest_id, int(event.position().x()), int(event.position().y()), "marker"))
                db.commit()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0,0,self.image)
        pen = QPen(self.pen_color, self.pen_width)
        painter.setPen(pen)
        for m in self.markers:
            painter.drawEllipse(QPoint(int(m[0]),int(m[1])), 5,5)

    def save_map(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Map", "", "PNG (*.png);;JPG (*.jpg)")
        if filename:
            self.image.save(filename)
            add_xp(5)
            QMessageBox.information(self, "Saved", f"Map saved as {filename}")

class QuestForm(QWidget):
    def __init__(self):
        super().__init__()
        layout = QFormLayout()
        self.title = QLineEdit()
        self.difficulty = QComboBox()
        self.difficulty.addItems([T["d_easy"],T["d_mid"],T["d_hard"],T["d_epic"]])
        self.reward = QSpinBox()
        self.reward.setRange(10,10000)
        self.description = QTextEdit()
        self.deadline = QDateTimeEdit()
        self.deadline.setDateTime(datetime.now())

        layout.addRow(T["quest_title"], self.title)
        layout.addRow(T["difficulty"], self.difficulty)
        layout.addRow(T["reward"], self.reward)
        layout.addRow(T["description"], self.description)
        layout.addRow(T["deadline"], self.deadline)

        self.create_btn = QPushButton(T["create_btn"])
        self.create_btn.clicked.connect(self.create_quest)
        layout.addWidget(self.create_btn)

        self.export_btn = QPushButton(T["template_docx"])
        self.export_btn.clicked.connect(self.export_quest)
        layout.addWidget(self.export_btn)

        self.setLayout(layout)
        self.last_quest_id = None

    def create_quest(self):
        title = self.title.text().strip()
        desc = self.description.toPlainText().strip()
        highlight(self.title,bool(title))
        highlight(self.description,len(desc)>10)
        if not title or len(desc)<10:
            QMessageBox.warning(self,"Error","Title or description invalid")
            return
        difficulty = self.difficulty.currentText()
        reward = self.reward.value()
        deadline = self.deadline.dateTime().toString()
        cur.execute("INSERT INTO quests(title,difficulty,reward,description,deadline) VALUES (?,?,?,?,?)",
                    (title,difficulty,reward,desc,deadline))
        db.commit()
        self.last_quest_id = cur.lastrowid
        add_xp(3)
        QMessageBox.information(self,"Success","Quest created")

    def export_quest(self):
        if not self.last_quest_id:
            QMessageBox.warning(self,"Error","No quest to export")
            return
        cur.execute("SELECT * FROM quests WHERE id=?",(self.last_quest_id,))
        quest = cur.fetchone()
        save_docx(quest)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(T["app_title"])
        self.resize(600,400)
        tabs = QTabWidget()
        self.form_tab = QuestForm()
        self.map_tab = MapEditor()
        tabs.addTab(self.form_tab,"Quest Wizard")
        tabs.addTab(self.map_tab,"Map Editor")
        self.setCentralWidget(tabs)

if __name__=="__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
