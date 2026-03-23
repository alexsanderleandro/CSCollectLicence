import sys
import os
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QSpinBox,
    QLineEdit,
    QLabel,
    QFileDialog,
    QMessageBox,
    QInputDialog,
)
from PySide6.QtGui import QIcon

from licenca import (
    gerar_licenca,
    salvar_licenca,
    carregar_licenca_de_arquivo,
)


class LicencaWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Gerenciador de Licença')
        # tenta carregar ícone da pasta assets (svg ou png)
        base = os.path.dirname(__file__)
        icon_svg = os.path.join(base, 'assets', 'logo.svg')
        icon_png = os.path.join(base, 'assets', 'logo.png')
        icon_path = icon_svg if os.path.exists(icon_svg) else (icon_png if os.path.exists(icon_png) else None)
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # CNPJs list
        self.cnpj_list = QListWidget()
        layout.addWidget(QLabel('CNPJs liberados:'))
        layout.addWidget(self.cnpj_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton('Adicionar')
        btn_add.clicked.connect(self.add_cnpj)
        btn_remove = QPushButton('Remover')
        btn_remove.clicked.connect(self.remove_cnpj)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        layout.addLayout(btn_row)

        # max devices
        hd = QHBoxLayout()
        hd.addWidget(QLabel('Max devices:'))
        self.max_devices = QSpinBox()
        self.max_devices.setMinimum(1)
        self.max_devices.setMaximum(9999)
        self.max_devices.setValue(1)
        hd.addWidget(self.max_devices)
        hd.addStretch()
        layout.addLayout(hd)

        # validade
        hd2 = QHBoxLayout()
        hd2.addWidget(QLabel('Validade (YYYY-MM-DD ou ISO, vazio = sem validade):'))
        self.validade = QLineEdit()
        hd2.addWidget(self.validade)
        layout.addLayout(hd2)

        # actions
        actions = QHBoxLayout()
        btn_new = QPushButton('Novo')
        btn_new.clicked.connect(self.new_license)
        actions.addWidget(btn_new)
        btn_load = QPushButton('Carregar')
        btn_load.clicked.connect(self.load_license)
        btn_save = QPushButton('Salvar')
        btn_save.clicked.connect(self.save_license)
        btn_generate = QPushButton('Gerar e Mostrar Token')
        btn_generate.clicked.connect(self.generate_token_only)
        actions.addWidget(btn_load)
        actions.addWidget(btn_save)
        actions.addWidget(btn_generate)
        layout.addLayout(actions)

        # mostrado quando carregado
        self.gerado_em_label = QLabel('')
        layout.addWidget(self.gerado_em_label)

        self.current_path = None

    def add_cnpj(self):
        text, ok = QInputDialog.getText(self, 'Adicionar CNPJ', 'CNPJ (apenas dígitos):')
        if ok and text:
            clean = ''.join(ch for ch in text if ch.isdigit())
            if clean:
                # avoid duplicates
                items = [self.cnpj_list.item(i).text() for i in range(self.cnpj_list.count())]
                if clean in items:
                    QMessageBox.information(self, 'Info', 'CNPJ já presente.')
                    return
                self.cnpj_list.addItem(clean)

    def remove_cnpj(self):
        sel = self.cnpj_list.currentRow()
        if sel >= 0:
            self.cnpj_list.takeItem(sel)

    def load_license(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Abrir licença', '', 'License files (*.key);;All files (*)')
        if not path:
            return
        try:
            payload, token = carregar_licenca_de_arquivo(path)
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao carregar: {e}')
            return
        # populate fields
        self.cnpj_list.clear()
        for c in payload.get('cnpjs', []):
            self.cnpj_list.addItem(c)
        self.max_devices.setValue(int(payload.get('max_devices', 1)))
        self.validade.setText(str(payload.get('validade', '')))
        # mostra gerado_em se presente
        ge = payload.get('gerado_em')
        if ge:
            self.gerado_em_label.setText(f'Gerado em: {ge}')
        else:
            self.gerado_em_label.setText('')
        self.current_path = path
        QMessageBox.information(self, 'OK', 'Licença carregada com sucesso.')

    def save_license(self):
        # collect
        cnpjs = [self.cnpj_list.item(i).text() for i in range(self.cnpj_list.count())]
        max_dev = self.max_devices.value()
        validade = self.validade.text().strip()

        path = self.current_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, 'Salvar licença', 'licenca.key', 'License files (*.key);;All files (*)')
            if not path:
                return
        # confirmação antes de sobrescrever
        if os.path.exists(path):
            resp = QMessageBox.question(self, 'Confirmar', f'O arquivo {path} já existe. Sobrescrever?')
            if resp != QMessageBox.Yes:
                return

        try:
            token = gerar_licenca(cnpjs, max_dev, validade)
            salvar_licenca(token, path)
            self.current_path = path
            QMessageBox.information(self, 'OK', f'Licença salva em: {path}')
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao salvar: {e}')

    def generate_token_only(self):
        cnpjs = [self.cnpj_list.item(i).text() for i in range(self.cnpj_list.count())]
        max_dev = self.max_devices.value()
        validade = self.validade.text().strip()
        try:
            token = gerar_licenca(cnpjs, max_dev, validade)
            dlg = QMessageBox(self)
            dlg.setWindowTitle('Token gerado')
            dlg.setText('Token:')
            dlg.setDetailedText(token)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao gerar token: {e}')

    def new_license(self):
        # limpa campos para criar nova licença
        self.cnpj_list.clear()
        self.max_devices.setValue(1)
        self.validade.setText('')
        self.gerado_em_label.setText('')
        self.current_path = None
        QMessageBox.information(self, 'Novo', 'Criando nova licença — preencha os campos e clique em Salvar.')


def main():
    app = QApplication(sys.argv)
    w = LicencaWindow()
    w.resize(700, 400)
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
