"""Coach/cheat sheet page with search."""

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QTextBrowser, QPushButton, QHBoxLayout
)

from ciscoman_core import cheatsheet, actions

logger = logging.getLogger(__name__)


class CoachPage(QWidget):
    """Coach and cheat sheet."""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h1>📚 Coach & Cheat Sheet</h1>"))
        layout.addWidget(QLabel("Search network terms and tasks"))
        
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Try: VLAN, PoE, GRE tunnel, trunk, ACL, SVI...")
        self.search_input.textChanged.connect(self.perform_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        self.results_browser = QTextBrowser()
        layout.addWidget(self.results_browser)
        
        # Show all by default
        self.perform_search("")
    
    def perform_search(self, query: str):
        """Search and display results."""
        hits = cheatsheet.search(query) if query else {"glossary": cheatsheet.GLOSSARY, "actions": []}
        
        html = "<h2>Search Results</h2>"
        
        if hits["glossary"]:
            html += "<h3>Terms & Concepts</h3>"
            for entry in hits["glossary"]:
                html += f"<p><b>{entry.term}</b> ({entry.category})<br>"
                html += f"{entry.definition}</p>"
                if entry.action_ids:
                    html += "<p><i>Related tasks:</i> " + ", ".join(entry.action_ids) + "</p>"
        
        if hits["actions"]:
            html += "<h3>Runnable Tasks</h3>"
            for act in hits["actions"]:
                html += f"<p><b>{act.name}</b> — {act.category}<br>"
                html += f"{act.explanation}</p>"
        
        if not hits["glossary"] and not hits["actions"] and query:
            html += "<p><i>No matches found. Try another keyword.</i></p>"
        
        self.results_browser.setHtml(html)
