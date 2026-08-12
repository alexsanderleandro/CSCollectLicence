import sys
import os
from typing import Optional, List, Dict, Any, Callable, Tuple
# pyrefly: ignore [missing-import]
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLineEdit,
    QDateEdit,
    QSpinBox,
    QCheckBox,
    QRadioButton,
    QButtonGroup,
    QLabel,
    QFileDialog,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QMenu,
)
# pyrefly: ignore [missing-import]
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor
# pyrefly: ignore [missing-import]
from PySide6.QtCore import QDate, Qt, QPointF

from licenca import (
    gerar_licenca,
    salvar_licenca,
    carregar_licenca_de_arquivo,
    carregar_licenca_de_conteudo,
    registrar_tokens_por_cnpjs_single,
    gerar_activation_token,
    listar_clientes,
    listar_activation_tokens,
)
try:
    from config import configure_database_interactive, get_database_config, get_config_path, load_config, get_api_config, save_api_config
except ImportError:
    configure_database_interactive = None
    get_database_config = None
    get_config_path = None
    load_config = None
    get_api_config = None
    save_api_config = None
from version import VERSION
from styles import LightTheme, apply_theme


def _make_icon(kind: str, color: str, size: int = 16) -> QIcon:
    """Desenha um ícone vetorial simples (evita depender de arquivos de asset)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if kind == 'gear':
        cx, cy, r = size / 2, size / 2, size * 0.22
        painter.drawEllipse(QPointF(cx, cy), r, r)
        for i in range(8):
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(i * 45)
            painter.drawLine(QPointF(0, -size * 0.32), QPointF(0, -size * 0.44))
            painter.restore()
    elif kind == 'key':
        r = size * 0.2
        painter.drawEllipse(QPointF(size * 0.32, size * 0.32), r, r)
        painter.drawLine(QPointF(size * 0.46, size * 0.46), QPointF(size * 0.84, size * 0.84))
        painter.drawLine(QPointF(size * 0.68, size * 0.68), QPointF(size * 0.8, size * 0.56))

    painter.end()
    return QIcon(pixmap)


class LicencaWindow(QMainWindow):
    """Janela principal da aplicação de gerenciamento de licenças.

    Fornece UI para adicionar múltiplos CNPJs e IDs de celular, definir validade,
    gerar tokens assinados e salvar/carregar o arquivo `licenca.key`.
    """
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Gerenciador de Licença')
        self._setup_layout()
        self.current_path = None
        self.original_cnpjs_str = None  # Armazena a string original de CNPJs para detectar mudanças

    def _find_asset(self, *names: str) -> Optional[str]:
        """Busca por um asset entre os nomes fornecidos na pasta assets."""
        base = os.path.dirname(__file__)
        for name in names:
            path = os.path.join(base, 'assets', name)
            if os.path.exists(path):
                return path
        return None

    def _setup_layout(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self._setup_licenca_tab(), 'Gerenciar Licença')
        self.tabs.addTab(self._setup_painel_tab(), 'Painel de Licenças')

    def _setup_licenca_tab(self) -> QWidget:
        central = QWidget()

        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Configuração de Ícone e Cabeçalho
        self.header_label = QLabel()
        logo_path = self._find_asset('logo.ico', 'logo.png')
        icon_path = self._find_asset('logo.ico', 'logo.svg', 'logo.png')
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        if logo_path:
            self.header_label.setPixmap(QIcon(logo_path).pixmap(48, 48))
            self.header_label.setFixedHeight(56)
            layout.addWidget(self.header_label)

        # O nome do cliente é informado por CNPJ, na seção de CNPJs (lista pareada).

        # Linhas de entrada modularizadas
        self._setup_sql_section(layout)
        self._setup_api_section(layout)
        self._setup_cnpj_section(layout)
        self._setup_celular_section(layout)
        self._setup_tipo_licenca_section(layout)
        self._setup_validade_section(layout)
        self._setup_actions_section(layout)

        # Rodapé / Versão
        self.gerado_em_label = QLabel('')
        layout.addWidget(self.gerado_em_label)

        self.version_label = QLabel(f'Versão: {VERSION}')
        layout.addWidget(self.version_label)

        return central

    def _setup_sql_section(self, layout: QVBoxLayout) -> None:
        row_sql = QHBoxLayout()

        col_servidor = QVBoxLayout()
        col_servidor.addWidget(QLabel('Servidor SQL:'))
        self.sql_servidor_edit = QLineEdit()
        self.sql_servidor_edit.setMaxLength(30)
        self.sql_servidor_edit.setPlaceholderText('Nome do servidor SQL')
        col_servidor.addWidget(self.sql_servidor_edit)
        row_sql.addLayout(col_servidor)

        col_banco = QVBoxLayout()
        col_banco.addWidget(QLabel('Banco de dados:'))
        self.sql_banco_edit = QLineEdit()
        self.sql_banco_edit.setMaxLength(30)
        self.sql_banco_edit.setPlaceholderText('Nome do banco de dados')
        col_banco.addWidget(self.sql_banco_edit)
        row_sql.addLayout(col_banco)

        layout.addLayout(row_sql)

    def _setup_api_section(self, layout: QVBoxLayout) -> None:
        row_api = QHBoxLayout()

        col_api_auth = QVBoxLayout()
        col_api_auth.addWidget(QLabel('API Authorization Token (máx 1000 caracteres):'))
        self.api_authorization_edit = QLineEdit()
        self.api_authorization_edit.setMaxLength(1000)  # Aumentado de 100 para suportar tokens JWT longos
        self.api_authorization_edit.setPlaceholderText('Token de autenticação da API')
        col_api_auth.addWidget(self.api_authorization_edit)
        row_api.addLayout(col_api_auth)

        col_api_db = QVBoxLayout()
        col_api_db.addWidget(QLabel('API Database URL (máx 100 caracteres):'))
        self.api_database_url_edit = QLineEdit()
        self.api_database_url_edit.setMaxLength(100)
        self.api_database_url_edit.setPlaceholderText('URL da base de dados da API')
        col_api_db.addWidget(self.api_database_url_edit)
        row_api.addLayout(col_api_db)

        layout.addLayout(row_api)

    def _build_list_editor(
        self,
        layout: QVBoxLayout,
        titulo: str,
        placeholder: str,
        on_validate: Optional[Callable[[str], str]] = None,
        placeholder_nome: Optional[str] = None,
        max_nome: int = 30,
    ) -> QListWidget:
        """Cria uma seção de lista com adição inline (sem popup) e remoção por seleção.

        Usado tanto para CNPJs quanto para IDs de celular — antes eram dois
        métodos quase-duplicados, um por seção.

        Com `placeholder_nome`, a lista vira **pareada**: cada item guarda um
        valor e um nome associado (usado pelos CNPJs, um nome de empresa por
        CNPJ). O texto do item é só exibição — os valores reais ficam em
        `Qt.UserRole` como `{'valor': ..., 'nome': ...}`, evitando parsing do
        rótulo. Use `_itens_pareados()` para ler de volta.
        """
        pareado = placeholder_nome is not None

        layout.addWidget(QLabel(titulo))
        list_widget = QListWidget()
        layout.addWidget(list_widget)

        row = QHBoxLayout()
        add_edit = QLineEdit()
        add_edit.setPlaceholderText(placeholder)
        row.addWidget(add_edit)
        nome_edit = None
        if pareado:
            nome_edit = QLineEdit()
            nome_edit.setMaxLength(max_nome)
            nome_edit.setPlaceholderText(placeholder_nome)
            row.addWidget(nome_edit)
        btn_add = QPushButton('+ Adicionar')
        row.addWidget(btn_add)
        btn_remove = QPushButton('Remover selecionado')
        row.addWidget(btn_remove)
        layout.addLayout(row)

        # Índice do item em edição (duplo clique), ou None se for uma adição nova.
        # Usa dict como "célula mutável" para poder ser lido/alterado pelas
        # closures abaixo sem precisar de `nonlocal` espalhado.
        editing_index = {'value': None}

        def _add():
            raw = add_edit.text().strip()
            if not raw:
                return
            clean = on_validate(raw) if on_validate else raw
            if not clean:
                return
            nome = nome_edit.text().strip() if nome_edit is not None else ''
            if pareado and not nome:
                QMessageBox.information(self, 'Info', 'Informe o nome da empresa deste CNPJ.')
                return
            idx_editando = editing_index['value']
            valores = [
                (list_widget.item(i).data(Qt.UserRole) or {}).get('valor')
                for i in range(list_widget.count())
                if i != idx_editando
            ]
            if clean in valores:
                QMessageBox.information(self, 'Info', 'Item já presente na lista.')
                add_edit.clear()
                return
            label = f'{clean} — {nome}' if pareado else clean
            if idx_editando is not None and 0 <= idx_editando < list_widget.count():
                item = list_widget.item(idx_editando)
                item.setText(label)
                item.setData(Qt.UserRole, {'valor': clean, 'nome': nome})
            else:
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, {'valor': clean, 'nome': nome})
                list_widget.addItem(item)
            editing_index['value'] = None
            add_edit.clear()
            if nome_edit is not None:
                nome_edit.clear()

        def _remove():
            row_idx = list_widget.currentRow()
            if row_idx >= 0:
                list_widget.takeItem(row_idx)
                # Qualquer remoção cancela uma edição em andamento, evitando
                # que `editing_index` fique apontando para a linha errada
                # depois que os índices da lista mudam de tamanho.
                editing_index['value'] = None

        def _start_edit(item: QListWidgetItem):
            dados = item.data(Qt.UserRole) or {}
            add_edit.setText(dados.get('valor') or item.text())
            if nome_edit is not None:
                nome_edit.setText(dados.get('nome') or '')
            editing_index['value'] = list_widget.row(item)
            add_edit.setFocus()
            add_edit.selectAll()

        btn_add.clicked.connect(_add)
        add_edit.returnPressed.connect(_add)
        if nome_edit is not None:
            nome_edit.returnPressed.connect(_add)
        btn_remove.clicked.connect(_remove)
        list_widget.itemDoubleClicked.connect(_start_edit)

        return list_widget

    @staticmethod
    def _itens_pareados(list_widget: QListWidget) -> Tuple[List[str], List[str]]:
        """Lê uma lista construída por `_build_list_editor`, devolvendo (valores, nomes).

        Aceita itens antigos sem `UserRole` (fallback para o texto do item).
        """
        valores: List[str] = []
        nomes: List[str] = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            dados = item.data(Qt.UserRole) or {}
            valores.append(dados.get('valor') or item.text())
            nomes.append(dados.get('nome') or '')
        return valores, nomes

    @staticmethod
    def _preencher_lista_pareada(list_widget: QListWidget, valores: List[str], nomes: List[str]) -> None:
        """Repovoa uma lista pareada a partir de duas listas alinhadas por posição."""
        list_widget.clear()
        for i, valor in enumerate(valores):
            nome = nomes[i] if i < len(nomes) else ''
            item = QListWidgetItem(f'{valor} — {nome}')
            item.setData(Qt.UserRole, {'valor': valor, 'nome': nome})
            list_widget.addItem(item)

    def _setup_cnpj_section(self, layout: QVBoxLayout) -> None:
        row_qtde = QHBoxLayout()
        row_qtde.addWidget(QLabel('Quantidade de CNPJs contratados:'))
        self.qtde_cnpj_spin = QSpinBox()
        self.qtde_cnpj_spin.setMinimum(1)
        self.qtde_cnpj_spin.setMaximum(999)
        self.qtde_cnpj_spin.setValue(1)
        row_qtde.addWidget(self.qtde_cnpj_spin)
        row_qtde.addStretch(1)
        layout.addLayout(row_qtde)

        self.cnpj_list = self._build_list_editor(
            layout,
            'CNPJs e nomes das empresas liberadas (deve bater com a quantidade acima):',
            'CNPJ (apenas dígitos)',
            on_validate=lambda raw: ''.join(ch for ch in raw if ch.isdigit()),
            placeholder_nome='Nome da empresa (máx 30)',
        )

    def _setup_celular_section(self, layout: QVBoxLayout) -> None:
        row_qtde = QHBoxLayout()
        row_qtde.addWidget(QLabel('Quantidade de devices contratados:'))
        self.qtde_device_spin = QSpinBox()
        self.qtde_device_spin.setMinimum(1)
        self.qtde_device_spin.setMaximum(999)
        self.qtde_device_spin.setValue(1)
        row_qtde.addWidget(self.qtde_device_spin)
        row_qtde.addStretch(1)
        layout.addLayout(row_qtde)

        self.id_celular_list = self._build_list_editor(
            layout,
            'IDs de celular liberados (deve bater com a quantidade acima):',
            'ID do celular',
        )

    def _setup_tipo_licenca_section(self, layout: QVBoxLayout) -> None:
        row = QHBoxLayout()
        row.addWidget(QLabel('Tipo de licença:'))
        self.tipo_licenca_group = QButtonGroup(self)
        self.tipo_licenca_lite_rb = QRadioButton('Lite')
        self.tipo_licenca_lite_rb.setChecked(True)
        self.tipo_licenca_pro_rb = QRadioButton('Pro')
        self.tipo_licenca_group.addButton(self.tipo_licenca_lite_rb)
        self.tipo_licenca_group.addButton(self.tipo_licenca_pro_rb)
        row.addWidget(self.tipo_licenca_lite_rb)
        row.addWidget(self.tipo_licenca_pro_rb)
        row.addStretch(1)
        layout.addLayout(row)

    def _get_tipo_licenca(self) -> str:
        return 'Pro' if self.tipo_licenca_pro_rb.isChecked() else 'Lite'

    def _setup_validade_section(self, layout: QVBoxLayout) -> None:
        hd2 = QHBoxLayout()
        hd2.addWidget(QLabel('Validade:'))
        self.validade = QDateEdit()
        self.validade.setCalendarPopup(True)
        self.validade.setDisplayFormat('yyyy-MM-dd')
        self.validade.setDate(QDate.currentDate())
        hd2.addWidget(self.validade)
        self.sem_validade_cb = QCheckBox('Sem validade')
        self.sem_validade_cb.toggled.connect(lambda checked: self.validade.setEnabled(not checked))
        hd2.addWidget(self.sem_validade_cb)
        layout.addLayout(hd2)

        self.ativa_cb = QCheckBox('Ativa (salvar como ativa no banco de dados)')
        self.ativa_cb.setChecked(True)
        layout.addWidget(self.ativa_cb)

    def _section_caption(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setProperty('role', 'caption')
        return label

    def _setup_actions_section(self, layout: QVBoxLayout) -> None:
        actions = QHBoxLayout()
        actions.setSpacing(20)

        file_group = QVBoxLayout()
        file_group.addWidget(self._section_caption('Arquivo'))
        file_row = QHBoxLayout()
        btn_new = QPushButton('Novo')
        btn_new.clicked.connect(self.new_license)
        file_row.addWidget(btn_new)
        btn_load = QPushButton('Carregar')
        btn_load.clicked.connect(self.load_license)
        file_row.addWidget(btn_load)
        btn_save = QPushButton('Salvar licença')
        btn_save.setObjectName('primary')
        btn_save.clicked.connect(self.save_license)
        file_row.addWidget(btn_save)
        file_group.addLayout(file_row)
        actions.addLayout(file_group)

        admin_group = QVBoxLayout()
        admin_group.addWidget(self._section_caption('Administrativo'))
        admin_row = QHBoxLayout()
        btn_config_db = QPushButton(' Config API')
        btn_config_db.setObjectName('admin')
        btn_config_db.setIcon(_make_icon('gear', LightTheme.ADMIN))
        btn_config_db.clicked.connect(self.configure_api)
        admin_row.addWidget(btn_config_db)

        btn_gen_token = QPushButton(' Gerar token')
        btn_gen_token.setObjectName('admin')
        btn_gen_token.setIcon(_make_icon('key', LightTheme.ADMIN))
        btn_gen_token.setToolTip('Gera token de ativação de uso único para o cliente ativar sem arquivo .key')
        btn_gen_token.clicked.connect(self.gerar_token_ativacao)
        admin_row.addWidget(btn_gen_token)
        admin_group.addLayout(admin_row)
        actions.addLayout(admin_group)

        actions.addStretch(1)
        layout.addLayout(actions)

    def configure_api(self) -> None:
        """Abre diálogo para configurar a URL da API, token de autorização e URL do banco."""
        if not get_api_config:
            QMessageBox.warning(self, 'Erro', 'Módulo config.py não disponível.')
            return

        current = get_api_config()

        dlg = QDialog(self)
        dlg.setWindowTitle('Configuração da API')
        dlg.setMinimumWidth(500)

        form = QFormLayout()

        api_url_edit = QLineEdit()
        api_url_edit.setText(current.get('api_url', ''))
        api_url_edit.setPlaceholderText('https://api.exemplo.com')
        form.addRow('URL da API:', api_url_edit)

        api_token_edit = QLineEdit()
        api_token_edit.setText(current.get('api_token', ''))
        api_token_edit.setPlaceholderText('Token de autorização Bearer')
        api_token_edit.setEchoMode(QLineEdit.Password)
        form.addRow('Token de autorização:', api_token_edit)

        db_url_edit = QLineEdit()
        db_url_edit.setText(current.get('database_url', ''))
        db_url_edit.setPlaceholderText('postgresql://user:pass@host:5432/db')
        form.addRow('URL do banco:', db_url_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        main_layout = QVBoxLayout(dlg)
        main_layout.addLayout(form)
        main_layout.addWidget(buttons)

        if dlg.exec() == QDialog.Accepted:
            api_url = api_url_edit.text().strip()
            api_token = api_token_edit.text().strip()
            db_url = db_url_edit.text().strip()

            if not api_url:
                QMessageBox.warning(self, 'Atenção', 'A URL da API não pode ser vazia.')
                return
            if not api_url.startswith(('http://', 'https://')):
                QMessageBox.warning(self, 'Atenção', 'A URL da API deve começar com http:// ou https://')
                return

            if not api_token:
                QMessageBox.warning(self, 'Atenção', 'O token de autorização não pode ser vazio.')
                return

            if save_api_config:
                save_api_config(api_url, api_token, db_url)
                QMessageBox.information(self, 'Sucesso', f'Configurações salvas em:\n{get_config_path()}')

    def load_license(self) -> None:
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

        self._popular_campos_de_payload(payload)
        self.current_path = path
        QMessageBox.information(self, 'OK', 'Licença carregada com sucesso.')

    def _popular_campos_de_payload(self, payload: dict) -> None:
        """Preenche os campos da aba 'Gerenciar Licença' a partir de um payload já obtido.

        Compartilhado por `load_license` (arquivo `.key`) e por
        `_carregar_cliente_do_painel` (registro do banco, via `arq_licenca`).
        """
        # popular campos de forma direta, removendo getattr redundantes
        self.sql_servidor_edit.setText(payload.get('sql_servidor', ''))
        self.sql_banco_edit.setText(payload.get('sql_banco', ''))
        self.api_authorization_edit.setText(payload.get('api_authorization', ''))
        self.api_database_url_edit.setText(payload.get('api_database_url', ''))

        cnpjs_carregados = payload.get('cnpjs', [])
        # `carregar_licenca_de_arquivo` já devolve `nomes` pareado com `cnpjs`,
        # aplicando a retrocompatibilidade de licenças com um único nome.
        self._preencher_lista_pareada(
            self.cnpj_list,
            cnpjs_carregados,
            payload.get('nomes', []),
        )
        # Armazena a string original de CNPJs para deletar registro antigo se modificar
        self.original_cnpjs_str = ','.join(cnpjs_carregados) if cnpjs_carregados else None
        self.id_celular_list.clear()
        for ic in payload.get('ids_celular', []):
            self.id_celular_list.addItem(ic)

        qtde_cnpjs = payload.get('qtde_cnpjs')
        if qtde_cnpjs is None:
            qtde_cnpjs = self.cnpj_list.count()
        self.qtde_cnpj_spin.setValue(max(1, qtde_cnpjs))

        qtde_devices = payload.get('qtde_devices')
        if qtde_devices is None:
            qtde_devices = self.id_celular_list.count()
        self.qtde_device_spin.setValue(max(1, qtde_devices))

        tipo_licenca = payload.get('tipo_licenca') or 'Lite'
        if tipo_licenca == 'Pro':
            self.tipo_licenca_pro_rb.setChecked(True)
        else:
            self.tipo_licenca_lite_rb.setChecked(True)

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
                    self.validade.setDate(QDate.currentDate())
            except Exception:
                self.validade.setDate(QDate.currentDate())
        # mostra gerado_em se presente
        ge = payload.get('gerado_em')
        if ge:
            self.gerado_em_label.setText(f'Gerado em: {ge}')
        else:
            self.gerado_em_label.setText('')

    def save_license(self) -> None:
        """Gera o token de licença a partir dos campos e salva em arquivo.

        Valida que exista pelo menos um CNPJ e um ID de celular antes de gerar.
        """
        # Valida quantidades informadas x quantidade real de itens nas listas
        qtde_cnpjs = self.qtde_cnpj_spin.value()
        qtde_devices = self.qtde_device_spin.value()

        if self.cnpj_list.count() != qtde_cnpjs:
            QMessageBox.warning(
                self, 'Quantidade de CNPJs inválida',
                f'A quantidade informada ({qtde_cnpjs}) não corresponde ao número de CNPJs '
                f'cadastrados na lista ({self.cnpj_list.count()}).'
            )
            return

        if self.id_celular_list.count() != qtde_devices:
            QMessageBox.warning(
                self, 'Quantidade de devices inválida',
                f'A quantidade informada ({qtde_devices}) não corresponde ao número de devices '
                f'cadastrados na lista ({self.id_celular_list.count()}).'
            )
            return

        # collect
        cnpjs, nomes = self._itens_pareados(self.cnpj_list)
        ids_celular = [self.id_celular_list.item(i).text() for i in range(self.id_celular_list.count())]
        validade = '' if self.sem_validade_cb.isChecked() else self.validade.date().toString('yyyy-MM-dd')
        tipo_licenca = self._get_tipo_licenca()

        # O banco e o envelope do .key recebem a string completa, separada por vírgula
        nome_cliente = ','.join(nomes)
        sql_servidor = self.sql_servidor_edit.text().strip()
        sql_banco = self.sql_banco_edit.text().strip()
        api_authorization = self.api_authorization_edit.text().strip()
        api_database_url = self.api_database_url_edit.text().strip()

        # Valida os dados gerando a licença antes de solicitar o caminho do arquivo (Item 18)
        try:
            lic_token = gerar_licenca(
                cnpjs, ids_celular, validade or '9999-12-31',
                nomes, sql_servidor, sql_banco,
                api_authorization=api_authorization,
                api_database_url=api_database_url,
                tipo_licenca=tipo_licenca,
            )
        except ValueError as e:
            QMessageBox.warning(self, 'Dados inválidos', str(e))
            return

        path = self.current_path
        if not path:
            # nome do arquivo: primeira empresa da licença
            _nome_arq = nomes[0] if nomes else ''
            safe = ''.join(ch for ch in _nome_arq if (ch.isalnum() or ch in (' ', '_', '-'))).strip().replace(' ', '_')
            if not safe:
                safe = 'cliente'
            default_name = f'Licenca_CSCollectManager_{safe}.key'
            path, _ = QFileDialog.getSaveFileName(self, 'Salvar licença', default_name, 'License files (*.key);;All files (*)')
            if not path:
                return

        if os.path.exists(path):
            resp = QMessageBox.question(self, 'Confirmar', f'O arquivo {path} já existe. Sobrescrever?')
            if resp != QMessageBox.Yes:
                return

        try:
            # Obtém token de autorização e database_url da configuração da API
            api_cfg = get_api_config() if get_api_config else {}
            api_token = api_cfg.get('api_token', '').strip()
            if not api_token:
                QMessageBox.warning(
                    self, 'Atenção',
                    'Token de autorização não configurado.\nClique em "Config API" para configurar.'
                )
                return

            api_url = api_cfg.get('api_url', '').strip() or None
            api_database_url_cfg = api_cfg.get('database_url', '').strip() or None
            
            # Validação automática de DSN Neon (Item 18)
            if api_database_url_cfg and 'neon.tech' in api_database_url_cfg:
                from urllib.parse import urlparse, urlunparse
                try:
                    p = urlparse(api_database_url_cfg)
                    if not p.path or p.path == '/':
                        api_database_url_cfg = urlunparse(p._replace(path='/neondb'))
                except Exception:
                    pass

            # Fallback: variável de ambiente DATABASE_URL
            if not api_database_url_cfg and get_database_config:
                db_config = get_database_config()
                if db_config and db_config.get('type') == 'sql':
                    api_database_url_cfg = db_config.get('url')

            meta = {
                'cnpjs': cnpjs,
                'nomes': nomes,
                'ids_celular': ids_celular,
                'validade': validade,
                'api_url': api_url,
                'nome_cliente': nome_cliente,
                'sql_servidor': sql_servidor,
                'sql_banco': sql_banco,
                'api_authorization': api_authorization,
                'api_database_url': api_database_url,
                'tipo_licenca': tipo_licenca,
            }
            conteudo_licenca = salvar_licenca(
                lic_token, path, payload_meta=meta,
                qtde_cnpjs=qtde_cnpjs, qtde_devices=qtde_devices,
            )
            
            # Registra no banco de dados (se configurado)
            try:
                # Cria registro único com CNPJs e IDs separados por vírgula
                cnpjs_str = ','.join(cnpjs)
                ids_str = ','.join(ids_celular)
                ativa = self.ativa_cb.isChecked()
                
                # Se a string de CNPJs mudou, deleta o registro antigo primeiro (Item 17)
                if self.original_cnpjs_str and self.original_cnpjs_str != cnpjs_str:
                    from licenca import deletar_registro_por_cnpjs
                    try:
                        deletar_registro_por_cnpjs(self.original_cnpjs_str)
                    except Exception as e:
                        import logging
                        logging.warning(f"[GUI] Falha ao deletar registro antigo ({self.original_cnpjs_str}): {e}")
                
                registrar_tokens_por_cnpjs_single(
                    cnpjs_str, ids_str, lic_token, validade, ativa,
                    nome_cliente, sql_servidor, sql_banco,
                    api_authorization=api_token,
                    api_database_url=api_database_url or '',
                    arq_licenca=conteudo_licenca,
                    qtde_cnpjs=qtde_cnpjs, qtde_devices=qtde_devices,
                    tipo_licenca=tipo_licenca,
                )
                
                self.original_cnpjs_str = cnpjs_str
                msg = f'Licença salva em: {path}\n\n✓ CNPJs registrados no banco com sucesso.'
            except Exception as e:
                msg = f'Licença salva em: {path}\n\n⚠ Aviso: falha ao registrar no banco: {e}'
            
            self.current_path = path
            QMessageBox.information(self, 'OK', msg)
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao salvar: {e}')

    def gerar_token_ativacao(self) -> None:
        """Gera token avulso de ativação para o cliente usar o fluxo 'Ativar Online'.

        Coleta Device ID, validade (horas) e operador em um único diálogo
        (antes eram 3 popups nativos encadeados).
        """
        cnpjs, _ = self._itens_pareados(self.cnpj_list)
        if not cnpjs:
            QMessageBox.warning(self, 'CNPJs obrigatórios', 'Adicione pelo menos um CNPJ antes de gerar o token.')
            return

        dlg = QDialog(self)
        dlg.setWindowTitle('Gerar token de ativação')
        dlg.setMinimumWidth(420)

        form = QFormLayout()

        device_id_edit = QLineEdit()
        device_id_edit.setPlaceholderText('Device ID exibido na tela de ativação do cliente')
        form.addRow('Device ID do cliente:', device_id_edit)

        ttl_spin = QSpinBox()
        ttl_spin.setRange(1, 720)
        ttl_spin.setValue(24)
        ttl_spin.setSuffix(' horas')
        form.addRow('Validade do token:', ttl_spin)

        operador_edit = QLineEdit()
        operador_edit.setPlaceholderText('Seu nome (para auditoria)')
        form.addRow('Operador:', operador_edit)

        tipo_licenca_row = QHBoxLayout()
        tipo_licenca_group = QButtonGroup(dlg)
        tipo_licenca_lite_rb = QRadioButton('Lite')
        tipo_licenca_lite_rb.setChecked(True)
        tipo_licenca_pro_rb = QRadioButton('Pro')
        tipo_licenca_group.addButton(tipo_licenca_lite_rb)
        tipo_licenca_group.addButton(tipo_licenca_pro_rb)
        tipo_licenca_row.addWidget(tipo_licenca_lite_rb)
        tipo_licenca_row.addWidget(tipo_licenca_pro_rb)
        tipo_licenca_row.addStretch(1)
        form.addRow('Tipo de licença:', tipo_licenca_row)

        cnpjs_label = QLabel(', '.join(cnpjs))
        cnpjs_label.setWordWrap(True)
        form.addRow('CNPJs incluídos:', cnpjs_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('Gerar token')
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        main_layout = QVBoxLayout(dlg)
        main_layout.addLayout(form)
        main_layout.addWidget(buttons)

        if dlg.exec() != QDialog.Accepted:
            return

        device_id_str = device_id_edit.text().strip()
        if not device_id_str:
            QMessageBox.warning(self, 'Device ID obrigatório',
                                'O Device ID é necessário para vincular o token ao celular do cliente.')
            return

        ttl_horas = ttl_spin.value()
        gerado_por_str = operador_edit.text().strip()
        tipo_licenca_str = 'Pro' if tipo_licenca_pro_rb.isChecked() else 'Lite'

        try:
            raw_token, expira_em = gerar_activation_token(
                cnpjs, device_id=device_id_str,
                ttl_horas=ttl_horas, gerado_por=gerado_por_str,
                tipo_licenca=tipo_licenca_str,
            )
        except Exception as e:
            QMessageBox.critical(self, 'Erro ao gerar token', str(e))
            return

        expira_str = expira_em.strftime('%d/%m/%Y %H:%M UTC')
        msg = (
            f'Token gerado com sucesso!\n\n'
            f'Token (copie e envie ao cliente):\n\n'
            f'{raw_token}\n\n'
            f'CNPJs: {", ".join(cnpjs)}\n'
            f'Device ID: {device_id_str}\n'
            f'Tipo de licença: {tipo_licenca_str}\n'
            f'Expira em: {expira_str}\n\n'
            f'⚠ Este token é exibido apenas uma vez e não pode ser recuperado.'
        )
        
        # Copiar para clipboard automaticamente com aviso de falha (Item 24)
        try:
            # pyrefly: ignore [missing-import]
            from PySide6.QtGui import QClipboard
            # pyrefly: ignore [missing-import]
            from PySide6.QtWidgets import QApplication as _QApp
            _QApp.clipboard().setText(raw_token)
            msg += '\n\n✓ Copiado para a área de transferência'
        except Exception as e:
            import logging
            logging.warning(f"[GUI] Falha ao copiar para o clipboard: {e}")
            msg += '\n\n⚠ Não foi possível copiar automaticamente — copie manualmente.'
        QMessageBox.information(self, 'Token de Ativação', msg)

    def new_license(self) -> None:
        """Limpa os campos da GUI para criar uma nova licença do zero.

        API Authorization Token e API Database URL vêm pré-preenchidos com os
        valores já salvos em "Config API", para não precisar copiar manualmente.
        """
        self.cnpj_list.clear()
        self.id_celular_list.clear()
        self.qtde_cnpj_spin.setValue(1)
        self.qtde_device_spin.setValue(1)
        self.tipo_licenca_lite_rb.setChecked(True)
        self.sem_validade_cb.setChecked(False)
        self.validade.setEnabled(True)
        self.validade.setDate(QDate.currentDate())
        self.ativa_cb.setChecked(True)
        self.gerado_em_label.setText('')
        self.sql_servidor_edit.setText('')
        self.sql_banco_edit.setText('')

        api_cfg = get_api_config() if get_api_config else {}
        self.api_authorization_edit.setText(api_cfg.get('api_token', ''))
        self.api_database_url_edit.setText(api_cfg.get('database_url', ''))

        self.current_path = None
        self.original_cnpjs_str = None
        QMessageBox.information(self, 'Novo', 'Criando nova licença — preencha os campos e clique em Salvar.')

    def _setup_painel_tab(self) -> QWidget:
        """Aba somente leitura com os dados já gravados no banco Neon.

        Sub-abas separadas para `clientes` (licenças) e `activation_tokens`
        (tokens avulsos), cada uma em uma tabela ordenável por coluna.
        """
        painel_page = QWidget()
        outer = QVBoxLayout(painel_page)
        self.painel_subtabs = QTabWidget()
        outer.addWidget(self.painel_subtabs)

        self.painel_subtabs.addTab(self._build_clientes_subtab(), 'Clientes')
        self.painel_subtabs.addTab(self._build_tokens_subtab(), 'Tokens de Ativação')
        return painel_page

    def _build_readonly_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSortingEnabled(True)
        table.setAlternatingRowColors(True)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(lambda pos, t=table: self._show_table_context_menu(t, pos))
        return table

    def _show_table_context_menu(self, table: QTableWidget, pos) -> None:
        item = table.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        copiar = menu.addAction('Copiar valor')
        action = menu.exec(table.viewport().mapToGlobal(pos))
        if action == copiar:
            QApplication.clipboard().setText(item.text())

    def _build_clientes_subtab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        btn_refresh = QPushButton('Atualizar')
        btn_refresh.clicked.connect(self._reload_clientes_table)
        row.addWidget(btn_refresh)
        row.addStretch(1)
        layout.addLayout(row)

        self.clientes_table = self._build_readonly_table()
        self.clientes_table.cellDoubleClicked.connect(self._carregar_cliente_do_painel)
        layout.addWidget(self.clientes_table)

        self._reload_clientes_table()
        return page

    def _build_tokens_subtab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        btn_refresh = QPushButton('Atualizar')
        btn_refresh.clicked.connect(self._reload_tokens_table)
        row.addWidget(btn_refresh)
        row.addStretch(1)
        layout.addLayout(row)

        self.tokens_table = self._build_readonly_table()
        layout.addWidget(self.tokens_table)

        self._reload_tokens_table()
        return page

    # Rótulos amigáveis para colunas do banco (painel somente leitura). Colunas
    # sem entrada aqui caem no fallback de `_friendly_columns` (nome original).
    COLUMN_LABELS = {
        'id': 'ID',
        'cnpj': 'CNPJ(s)',
        'idcelular': 'Devices',
        'token': 'Token',
        'token_hash': 'Hash do Token',
        'nome_cliente': 'Cliente',
        'validade': 'Validade',
        'ativo': 'Ativo',
        'sql_servidor': 'Servidor SQL',
        'sql_banco': 'Banco de Dados',
        'api_authorization': 'API Token',
        'api_database_url': 'API Database URL',
        'arq_licenca': 'Arquivo de Licença',
        'qtde_cnpjs': 'Qtde. CNPJs',
        'qtde_devices': 'Qtde. Devices',
        'tipo_licenca': 'Tipo de Licença',
        'reginclusao': 'Criado em',
        'dataalteracao': 'Atualizado em',
        'criado_em': 'Criado em',
        'expira_em': 'Expira em',
        'usado_em': 'Usado em',
        'device_id_usado': 'Device Usado',
        'device_id_autorizado': 'Device Autorizado',
        'gerado_por': 'Gerado por',
    }

    @classmethod
    def _friendly_columns(cls, columns: list) -> list:
        return [cls.COLUMN_LABELS.get(c, c) for c in columns]

    def _populate_table(self, table: QTableWidget, columns: list, rows: list) -> None:
        table.setSortingEnabled(False)
        table.clear()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(self._friendly_columns(columns))
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            # Guarda os valores brutos da linha (não o `str()` de exibição) para
            # permitir reaproveitar o registro depois (ex.: duplo clique em
            # "Clientes" carregando a licença sem precisar do arquivo .key).
            dados_linha = {'columns': columns, 'row': row}
            for c, value in enumerate(row):
                display = '' if value is None else str(value)
                item = QTableWidgetItem(display)
                item.setToolTip(display)
                item.setData(Qt.UserRole, dados_linha)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        for c in range(len(columns)):
            if table.columnWidth(c) > 320:
                table.setColumnWidth(c, 320)
        table.setSortingEnabled(True)

    def _reload_clientes_table(self) -> None:
        try:
            colunas, linhas = listar_clientes()
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao consultar clientes: {e}')
            return
        self._populate_table(self.clientes_table, colunas, linhas)

    def _carregar_cliente_do_painel(self, row: int, column: int) -> None:
        """Duplo clique num registro de 'Clientes' carrega a licença na aba de gerenciamento.

        Reaproveita o conteúdo completo do `.key` já salvo em `clientes.arq_licenca`
        (gravado por `save_license` a cada salvamento), sem precisar do arquivo em disco.
        """
        item = self.clientes_table.item(row, 0)
        dados = item.data(Qt.UserRole) if item else None
        if not dados:
            return
        registro = dict(zip(dados['columns'], dados['row']))

        arq_licenca = registro.get('arq_licenca')
        if not arq_licenca:
            QMessageBox.warning(
                self, 'Licença não disponível',
                'Este registro não tem o conteúdo da licença salvo no banco '
                '(campo arq_licenca vazio) e não pode ser carregado por aqui.\n\n'
                'Carregue o arquivo .key correspondente manualmente em "Carregar".'
            )
            return

        try:
            payload, token = carregar_licenca_de_conteudo(arq_licenca)
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao carregar licença do banco: {e}')
            return

        self._popular_campos_de_payload(payload)
        # 'ativo' só existe na tabela do banco, não no envelope .key.
        self.ativa_cb.setChecked(bool(registro.get('ativo', True)))
        # Não veio de um arquivo local — "Salvar licença" deve pedir um caminho novo.
        self.current_path = None

        self.tabs.setCurrentIndex(0)
        nome = payload.get('nome_cliente') or registro.get('nome_cliente') or ''
        QMessageBox.information(self, 'OK', f'Licença de "{nome}" carregada do banco com sucesso.')

    def _reload_tokens_table(self) -> None:
        try:
            colunas, linhas = listar_activation_tokens()
        except Exception as e:
            QMessageBox.critical(self, 'Erro', f'Falha ao consultar tokens de ativação: {e}')
            return
        self._populate_table(self.tokens_table, colunas, linhas)


def main():
    """Inicializa a aplicação Qt e exibe a janela principal.

    Uso: executar este módulo para abrir a interface gráfica.
    """
    app = QApplication(sys.argv)
    apply_theme(app)
    w = LicencaWindow()
    w.setMinimumSize(880, 560)
    w.showMaximized()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

