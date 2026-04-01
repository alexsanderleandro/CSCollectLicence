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
    QLineEdit,
    QDateEdit,
    QCheckBox,
    QLabel,
    QFileDialog,
    QMessageBox,
    QInputDialog,
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import QDate

from licenca import (
    gerar_licenca,
    salvar_licenca,
    carregar_licenca_de_arquivo,
)
from version import VERSION


class LicencaWindow(QMainWindow):
    """Janela principal da aplicação de gerenciamento de licenças.

    Fornece UI para adicionar múltiplos CNPJs e IDs de celular, definir validade,
    gerar tokens assinados e salvar/carregar o arquivo `licenca.key`.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Gerenciador de Licença')
        base = os.path.dirname(__file__)
        # prefere o arquivo .ico para o ícone da janela
        icon_ico = os.path.join(base, 'assets', 'logo.ico')
        icon_svg = os.path.join(base, 'assets', 'logo.svg')
        icon_png = os.path.join(base, 'assets', 'logo.png')
        icon_path = (
            icon_ico
            if os.path.exists(icon_ico)
            else (icon_svg if os.path.exists(icon_svg) else (icon_png if os.path.exists(icon_png) else None))
        )
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

        # cabeçalho com o logo (usa o mesmo .ico gerado para o executável quando disponível)
        self.header_label = QLabel()
        logo_path = icon_ico if os.path.exists(icon_ico) else (icon_png if os.path.exists(icon_png) else None)
        if logo_path:
            self.header_label.setPixmap(QIcon(logo_path).pixmap(48, 48))
            self.header_label.setFixedHeight(56)
            layout.addWidget(self.header_label)

        # CNPJs list
        self.cnpj_list = QListWidget()
        layout.addWidget(QLabel('CNPJs liberados (mínimo 1):'))
        layout.addWidget(self.cnpj_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton('Adicionar CNPJ')
        btn_add.clicked.connect(self.add_cnpj)
        btn_remove = QPushButton('Remover CNPJ')
        btn_remove.clicked.connect(self.remove_cnpj)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        layout.addLayout(btn_row)

        # IDs de celular
        self.id_celular_list = QListWidget()
        layout.addWidget(QLabel('IDs de celular liberados (mínimo 1):'))
        layout.addWidget(self.id_celular_list)

        btn_row2 = QHBoxLayout()
        btn_add_cel = QPushButton('Adicionar ID Celular')
        btn_add_cel.clicked.connect(self.add_id_celular)
        btn_remove_cel = QPushButton('Remover ID Celular')
        btn_remove_cel.clicked.connect(self.remove_id_celular)
        btn_row2.addWidget(btn_add_cel)
        btn_row2.addWidget(btn_remove_cel)
        layout.addLayout(btn_row2)

        # validade (date picker) + opção 'sem validade'
        hd2 = QHBoxLayout()
        hd2.addWidget(QLabel('Validade:'))
        self.validade = QDateEdit()
        self.validade.setCalendarPopup(True)
        self.validade.setDisplayFormat('yyyy-MM-dd')
        # default to today
        self.validade.setDate(QDate.currentDate())
        hd2.addWidget(self.validade)
        self.sem_validade_cb = QCheckBox('Sem validade')
        self.sem_validade_cb.toggled.connect(lambda checked: self.validade.setEnabled(not checked))
        hd2.addWidget(self.sem_validade_cb)
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
        actions.addWidget(btn_load)
        actions.addWidget(btn_save)
        layout.addLayout(actions)

        # mostrado quando carregado
        self.gerado_em_label = QLabel('')
        layout.addWidget(self.gerado_em_label)

        # versão do app
        self.version_label = QLabel(f'Versão: {VERSION}')
        layout.addWidget(self.version_label)

        self.current_path = None

    def add_cnpj(self):
        """Abre diálogo para inserir um CNPJ, normaliza (apenas dígitos) e adiciona à lista.

        Evita duplicatas.
        """
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
        """Remove o CNPJ selecionado na lista (se houver seleção)."""
        sel = self.cnpj_list.currentRow()
        if sel >= 0:
            self.cnpj_list.takeItem(sel)

    def add_id_celular(self):
        """Abre diálogo para inserir um ID de celular e adiciona à lista, evitando duplicatas."""
        text, ok = QInputDialog.getText(self, 'Adicionar ID de Celular', 'ID do celular:')
        if ok and text:
            clean = text.strip()
            if clean:
                items = [self.id_celular_list.item(i).text() for i in range(self.id_celular_list.count())]
                if clean in items:
                    QMessageBox.information(self, 'Info', 'ID de celular já presente.')
                    return
                self.id_celular_list.addItem(clean)

    def remove_id_celular(self):
        """Remove o ID de celular selecionado na lista (se houver seleção)."""
        sel = self.id_celular_list.currentRow()
        if sel >= 0:
            self.id_celular_list.takeItem(sel)

    def load_license(self):
        """Carrega um arquivo de licença (`.key`), valida e popula os campos da GUI.

        Em caso de erro exibe uma mensagem para o usuário.
        """
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
        self.id_celular_list.clear()
        for ic in payload.get('ids_celular', []):
            self.id_celular_list.addItem(ic)
        vt = payload.get('validade', '')
        if not vt:
            self.sem_validade_cb.setChecked(True)
            self.validade.setEnabled(False)
        else:
            self.sem_validade_cb.setChecked(False)
            # parse expected format YYYY-MM-DD
            try:
                d = QDate.fromString(str(vt), 'yyyy-MM-dd')
                if d.isValid():
                    self.validade.setDate(d)
                else:
                    # fallback: set text as is by attempting parse with Qt
                    self.validade.setDate(QDate.currentDate())
            except Exception:
                self.validade.setDate(QDate.currentDate())
        # mostra gerado_em se presente
        ge = payload.get('gerado_em')
        if ge:
            self.gerado_em_label.setText(f'Gerado em: {ge}')
        else:
            self.gerado_em_label.setText('')
        self.current_path = path
        QMessageBox.information(self, 'OK', 'Licença carregada com sucesso.')

    def save_license(self):
        """Gera o token de licença a partir dos campos e salva em arquivo.

        Valida que exista pelo menos um CNPJ e um ID de celular antes de gerar.
        """
        # collect
        cnpjs = [self.cnpj_list.item(i).text() for i in range(self.cnpj_list.count())]
        ids_celular = [self.id_celular_list.item(i).text() for i in range(self.id_celular_list.count())]
        if getattr(self, 'sem_validade_cb', None) and self.sem_validade_cb.isChecked():
            validade = ''
        else:
            # QDateEdit -> string in yyyy-MM-dd
            validade = self.validade.date().toString('yyyy-MM-dd')

        if not cnpjs:
            QMessageBox.warning(self, 'Atenção', 'É obrigatório informar pelo menos um CNPJ.')
            return
        if not ids_celular:
            QMessageBox.warning(self, 'Atenção', 'É obrigatório informar pelo menos um ID de celular.')
            return

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
            # Gera o token (string assinada) a partir de todos os CNPJs e IDs de celular.
            # O token contém o payload JSON e a assinatura HMAC; o mesmo token é salvo
            # em disco no arquivo `path` para distribuição/instalação.
            token = gerar_licenca(cnpjs, ids_celular, validade)
            # Salva o token no arquivo de licença (por padrão: licenca.key)
            salvar_licenca(token, path)
            self.current_path = path
            QMessageBox.information(self, 'OK', f'Licença salva em: {path}')
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao salvar: {e}')

    def generate_token_only(self):
        """Gera o token e o exibe em um diálogo para cópia/colagem.

        Não salva o arquivo; útil para enviar o token por outros canais.
        """
        # removido: geração direta de token via botão (fluxo mantido no salvar)
        return

    def new_license(self):
        """Limpa todos os campos da GUI para criar uma nova licença do zero."""
        # limpa campos para criar nova licença
        self.cnpj_list.clear()
        self.id_celular_list.clear()
        self.sem_validade_cb.setChecked(False)
        self.validade.setEnabled(True)
        self.validade.setDate(QDate.currentDate())
        self.gerado_em_label.setText('')
        self.current_path = None
        QMessageBox.information(self, 'Novo', 'Criando nova licença — preencha os campos e clique em Salvar.')


def main():
    """Inicializa a aplicação Qt e exibe a janela principal.

    Uso: executar este módulo para abrir a interface gráfica.
    """
    app = QApplication(sys.argv)
    w = LicencaWindow()
    w.resize(700, 400)
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
