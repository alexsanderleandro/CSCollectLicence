"""
styles.py
=========
Tema visual do CSCollectLicence — claro, com identidade própria
(não herda o tema escuro do CSCollectManager).
"""


class LightTheme:
    """Tema claro para a aplicação."""

    BG = "#fbfaf6"
    SURFACE = "#ffffff"
    BORDER = "#e1ded4"
    BORDER_HOVER = "#c7c2b3"
    BORDER_FOCUS = "#33518a"

    TEXT = "#26241d"
    TEXT_MUTED = "#726d5f"
    TEXT_DISABLED = "#a6a196"

    # Ações de arquivo (Novo/Carregar/Salvar)
    ACCENT = "#33518a"
    ACCENT_HOVER = "#3d5fa0"
    ACCENT_PRESSED = "#25406f"

    # Ações administrativas (Config API/Gerar token) — emitem credenciais
    ADMIN = "#b3822f"
    ADMIN_HOVER = "#fbf3e4"
    ADMIN_PRESSED = "#f5e6c8"

    SUCCESS = "#2f8f5b"
    WARNING = "#b3822f"
    ERROR = "#b3453c"

    STYLESHEET = """
    QWidget {
        background-color: #fbfaf6;
        color: #26241d;
        font-family: "Segoe UI", "Segoe UI Variable", Arial, sans-serif;
        font-size: 10pt;
        selection-background-color: #33518a;
        selection-color: #ffffff;
    }

    QMainWindow, QDialog {
        background-color: #fbfaf6;
    }

    QLabel[role="caption"] {
        color: #726d5f;
        font-size: 8pt;
        font-weight: 600;
    }

    /* ===== INPUTS ===== */
    QLineEdit, QDateEdit, QSpinBox {
        background-color: #ffffff;
        border: 1px solid #e1ded4;
        border-radius: 7px;
        padding: 6px 8px;
        selection-background-color: #33518a;
        selection-color: #ffffff;
    }
    QLineEdit:hover, QDateEdit:hover, QSpinBox:hover {
        border-color: #c7c2b3;
    }
    QLineEdit:focus, QDateEdit:focus, QSpinBox:focus {
        border-color: #33518a;
    }
    QLineEdit:disabled {
        background-color: #f2f0ea;
        color: #a6a196;
    }

    /* ===== LISTS ===== */
    QListWidget {
        background-color: #ffffff;
        border: 1px solid #e1ded4;
        border-radius: 7px;
        padding: 2px;
        outline: none;
    }
    QListWidget::item {
        padding: 4px 6px;
        border-radius: 5px;
    }
    QListWidget::item:selected {
        background-color: #eef1f7;
        color: #26241d;
    }

    /* ===== CHECKBOX ===== */
    QCheckBox {
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #c7c2b3;
        border-radius: 4px;
        background-color: #ffffff;
    }
    QCheckBox::indicator:checked {
        background-color: #33518a;
        border-color: #33518a;
    }

    /* ===== RADIO BUTTON ===== */
    QRadioButton {
        spacing: 8px;
    }
    QRadioButton::indicator {
        width: 16px;
        height: 16px;
        border: 1px solid #c7c2b3;
        border-radius: 8px;
        background-color: #ffffff;
    }
    QRadioButton::indicator:hover {
        border-color: #33518a;
    }
    QRadioButton::indicator:checked {
        background-color: #33518a;
        border-color: #33518a;
    }

    /* ===== BUTTONS ===== */
    QPushButton {
        background-color: #ffffff;
        color: #26241d;
        border: 1px solid #e1ded4;
        border-radius: 7px;
        padding: 7px 16px;
        min-height: 18px;
    }
    QPushButton:hover {
        border-color: #c7c2b3;
        background-color: #f5f4ef;
    }
    QPushButton:pressed {
        background-color: #eeece4;
    }
    QPushButton:disabled {
        color: #a6a196;
        background-color: #f5f4ef;
    }

    QPushButton#primary {
        background-color: #33518a;
        border-color: #33518a;
        color: #ffffff;
        font-weight: 600;
    }
    QPushButton#primary:hover {
        background-color: #3d5fa0;
        border-color: #3d5fa0;
    }
    QPushButton#primary:pressed {
        background-color: #25406f;
        border-color: #25406f;
    }

    QPushButton#admin {
        border-color: #b3822f;
        color: #b3822f;
        background-color: #ffffff;
    }
    QPushButton#admin:hover {
        background-color: #fbf3e4;
    }
    QPushButton#admin:pressed {
        background-color: #f5e6c8;
    }

    QDialogButtonBox QPushButton {
        min-width: 84px;
    }

    /* ===== TABS ===== */
    QTabWidget::pane {
        border: 1px solid #e1ded4;
        border-radius: 7px;
        top: -1px;
    }
    QTabBar::tab {
        background-color: #f5f4ef;
        color: #726d5f;
        border: 1px solid #e1ded4;
        border-bottom: none;
        border-top-left-radius: 7px;
        border-top-right-radius: 7px;
        padding: 7px 16px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background-color: #ffffff;
        color: #26241d;
        font-weight: 600;
    }
    QTabBar::tab:hover:!selected {
        background-color: #eeece4;
    }

    /* ===== TABLES ===== */
    QTableWidget {
        background-color: #ffffff;
        alternate-background-color: #f8f7f2;
        border: 1px solid #e1ded4;
        border-radius: 7px;
        gridline-color: #e1ded4;
        outline: none;
    }
    QTableWidget::item {
        padding: 4px 6px;
    }
    QTableWidget::item:selected {
        background-color: #eef1f7;
        color: #26241d;
    }
    QHeaderView::section {
        background-color: #f5f4ef;
        color: #726d5f;
        padding: 6px 8px;
        border: none;
        border-bottom: 1px solid #e1ded4;
        border-right: 1px solid #e1ded4;
        font-weight: 600;
    }

    /* ===== SCROLLBARS ===== */
    QScrollBar:vertical {
        background-color: #fbfaf6;
        width: 10px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background-color: #d8d4c8;
        min-height: 24px;
        border-radius: 5px;
        margin: 1px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #c7c2b3;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    """


def apply_theme(app) -> None:
    """Aplica o tema claro à aplicação."""
    app.setStyleSheet(LightTheme.STYLESHEET)
