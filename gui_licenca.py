import sys
import os
from typing import Optional, List, Dict, Any
# pyrefly: ignore [missing-import]
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
    QDialog,
    QDialogButtonBox,
    QFormLayout,
)
# pyrefly: ignore [missing-import]
from PySide6.QtGui import QIcon
# pyrefly: ignore [missing-import]
from PySide6.QtCore import QDate

from licenca import (
    gerar_licenca,
    salvar_licenca,
    carregar_licenca_de_arquivo,
    registrar_tokens_por_cnpjs_single,
    gerar_activation_token,
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
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)

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

        # Nome do cliente (obrigatório, max 30)
        layout.addWidget(QLabel('Nome do cliente (máx 30 caracteres):'))
        self.nome_cliente_edit = QLineEdit()
        self.nome_cliente_edit.setMaxLength(30)
        self.nome_cliente_edit.setPlaceholderText('Nome do cliente vinculado à licença')
        layout.addWidget(self.nome_cliente_edit)

        # Linhas de entrada modularizadas
        self._setup_sql_section(layout)
        self._setup_api_section(layout)
        self._setup_cnpj_section(layout)
        self._setup_celular_section(layout)
        self._setup_validade_section(layout)
        self._setup_actions_section(layout)

        # Rodapé / Versão
        self.gerado_em_label = QLabel('')
        layout.addWidget(self.gerado_em_label)

        self.version_label = QLabel(f'Versão: {VERSION}')
        layout.addWidget(self.version_label)

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

    def _setup_cnpj_section(self, layout: QVBoxLayout) -> None:
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

    def _setup_celular_section(self, layout: QVBoxLayout) -> None:
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

    def _setup_actions_section(self, layout: QVBoxLayout) -> None:
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
        
        btn_config_db = QPushButton('⚙ Config API')
        btn_config_db.clicked.connect(self.configure_api)
        actions.addWidget(btn_config_db)

        btn_gen_token = QPushButton('🔑 Gerar Token')
        btn_gen_token.setToolTip('Gera token de ativação de uso único para o cliente ativar sem arquivo .key')
        btn_gen_token.clicked.connect(self.gerar_token_ativacao)
        actions.addWidget(btn_gen_token)
        
        layout.addLayout(actions)

        # mostrado quando carregado
        self.gerado_em_label = QLabel('')
        layout.addWidget(self.gerado_em_label)

        # versão do app
        #self.version_label = QLabel(f'Versão: {VERSION}')
        #layout.addWidget(self.version_label)

        self.current_path = None
        self.original_cnpjs_str = None  # Armazena a string original de CNPJs para detectar mudanças

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
        
        # popular campos de forma direta, removendo getattr redundantes
        self.nome_cliente_edit.setText(payload.get('nome_cliente', ''))
        self.sql_servidor_edit.setText(payload.get('sql_servidor', ''))
        self.sql_banco_edit.setText(payload.get('sql_banco', ''))
        self.api_authorization_edit.setText(payload.get('api_authorization', ''))
        self.api_database_url_edit.setText(payload.get('api_database_url', ''))

        self.cnpj_list.clear()
        cnpjs_carregados = payload.get('cnpjs', [])
        for c in cnpjs_carregados:
            self.cnpj_list.addItem(c)
        # Armazena a string original de CNPJs para deletar registro antigo se modificar
        self.original_cnpjs_str = ','.join(cnpjs_carregados) if cnpjs_carregados else None
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

    def save_license(self) -> None:
        """Gera o token de licença a partir dos campos e salva em arquivo.

        Valida que exista pelo menos um CNPJ e um ID de celular antes de gerar.
        """
        # collect
        cnpjs = [self.cnpj_list.item(i).text() for i in range(self.cnpj_list.count())]
        ids_celular = [self.id_celular_list.item(i).text() for i in range(self.id_celular_list.count())]
        validade = '' if self.sem_validade_cb.isChecked() else self.validade.date().toString('yyyy-MM-dd')

        nome_cliente = self.nome_cliente_edit.text().strip()
        sql_servidor = self.sql_servidor_edit.text().strip()
        sql_banco = self.sql_banco_edit.text().strip()
        api_authorization = self.api_authorization_edit.text().strip()
        api_database_url = self.api_database_url_edit.text().strip()

        # Valida os dados gerando a licença antes de solicitar o caminho do arquivo (Item 18)
        try:
            lic_token = gerar_licenca(
                cnpjs, ids_celular, validade or '9999-12-31',
                nome_cliente, sql_servidor, sql_banco,
                api_authorization=api_authorization,
                api_database_url=api_database_url
            )
        except ValueError as e:
            QMessageBox.warning(self, 'Dados inválidos', str(e))
            return

        path = self.current_path
        if not path:
            safe = ''.join(ch for ch in nome_cliente if (ch.isalnum() or ch in (' ', '_', '-'))).strip().replace(' ', '_')
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
                    'Token de autorização não configurado.\nClique em "⚙ Config API" para configurar.'
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
                'ids_celular': ids_celular,
                'validade': validade,
                'api_url': api_url,
                'nome_cliente': nome_cliente,
                'sql_servidor': sql_servidor,
                'sql_banco': sql_banco,
                'api_authorization': api_authorization,
                'api_database_url': api_database_url,
            }
            conteudo_licenca = salvar_licenca(lic_token, path, payload_meta=meta)
            
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
        """Gera token avulso de ativação para o cliente usar o fluxo 'Ativar Online'."""
        # Coletar CNPJs da lista
        cnpjs = [self.cnpj_list.item(i).text() for i in range(self.cnpj_list.count())]
        if not cnpjs:
            QMessageBox.warning(self, 'CNPJs obrigatórios', 'Adicione pelo menos um CNPJ antes de gerar o token.')
            return

        device_id_str, ok0 = QInputDialog.getText(
            self, 'Device ID do cliente',
            'Cole o Device ID exibido no app do cliente\n(tela de ativação → campo DEVICE ID):',
            text=''
        )
        if not ok0:
            return
        device_id_str = device_id_str.strip()
        if not device_id_str:
            QMessageBox.warning(self, 'Device ID obrigatório',
                                'O Device ID é necessário para vincular o token ao celular do cliente.')
            return

        ttl_str, ok = QInputDialog.getText(
            self, 'Validade do token', 'Duração em horas (padrão: 24):', text='24'
        )
        if not ok:
            return
        try:
            ttl_horas = int(ttl_str.strip() or '24')
            if ttl_horas < 1:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, 'Valor inválido', 'Informe um número inteiro de horas (ex.: 24).')
            return

        gerado_por_str, ok2 = QInputDialog.getText(
            self, 'Operador', 'Seu nome (para auditoria):', text=''
        )
        if not ok2:
            return

        try:
            raw_token, expira_em = gerar_activation_token(
                cnpjs, device_id=device_id_str,
                ttl_horas=ttl_horas, gerado_por=gerado_por_str.strip()
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
        """Limpa todos os campos da GUI para criar uma nova licença do zero."""
        self.cnpj_list.clear()
        self.id_celular_list.clear()
        self.sem_validade_cb.setChecked(False)
        self.validade.setEnabled(True)
        self.validade.setDate(QDate.currentDate())
        self.ativa_cb.setChecked(True)
        self.gerado_em_label.setText('')
        self.nome_cliente_edit.setText('')
        self.sql_servidor_edit.setText('')
        self.sql_banco_edit.setText('')
        self.api_authorization_edit.setText('')
        self.api_database_url_edit.setText('')
        self.current_path = None
        self.original_cnpjs_str = None
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

