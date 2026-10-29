"""Textual screens (import only when Textual is installed)."""

from __future__ import annotations

import os
from pathlib import Path

from textual import events, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
    TextArea,
)

from . import __version__
from .host.detect import host_os
from .host.privileges import elevation_hint_short, grant_destructive_write_in_process
from .host.runner import is_admin
from .workflows import (
    ensure_reference_mbr,
    requirements_lines,
    run_build_image,
    run_format_exfat,
    run_init_pfs,
    run_prepare_device,
    run_prepare_pfs_device,
    run_scaffold_opl,
)

MENU_ITEMS = [
    ("wizard", "Assistente — imagem híbrida completa (backup .img)"),
    ("prepare_device", "Preparar disco físico (tamanho real, in-place)"),
    ("prepare_pfs", "Atualizar só PFS (FHDB/OSD/OPL) — manter exFAT"),
    ("build", "Só criar imagem (APA + cabeçalhos)"),
    ("init_pfs", "Inicializar PFS (__system / __sysconf)"),
    ("format_exfat", "Formatar exFAT (+ pastas OPL)"),
    ("scaffold_opl", "Criar pastas OPL (pasta montada)"),
    ("list_disks", "Listar discos físicos (índice / hdl_dump)"),
    ("validate_opl", "Validar layout OPL (MBR / APAJ / exFAT)"),
    ("requirements", "Requisitos e dicas"),
]

KEYBOARD_HINT = (
    "[dim]Teclado: ↑↓ + Enter · teclas [b]1–9[/b] (0=10) · Tab/Shift+Tab · "
    "Espaço (caixas) · Ctrl+Enter executar · Esc voltar · q sair · "
    "Rato: clique[/dim]"
)


LOG_KEYBOARD_HINT = (
    "[dim]Conteúdo selecionável: arrastar o rato · Ctrl+C copiar · "
    "Ctrl+A selecionar tudo · botão Copiar tudo[/dim]"
)


def _elevation_fields() -> ComposeResult:
    if is_admin():
        yield Static(f"[dim]{elevation_hint_short()}[/dim]")
    elif host_os() == "windows":
        yield Static(
            "[yellow]Não está como Administrador — feche e abra o terminal "
            "«Executar como administrador».[/yellow]"
        )
    else:
        yield Static(
            "[dim]Sem root: informe a senha sudo (só nesta operação) "
            "ou inicie com[/dim] [b]sudo ./pfs-batchkit-ui[/b]"
        )
        yield Input(password=True, id="sudo_password", placeholder="senha sudo")


def _set_screen_operation_busy(screen: Screen, *, busy: bool) -> None:
    """Disable duplicate submits while a @work handler runs."""
    for button in screen.query(Button):
        button.disabled = busy
        if busy and button.id in {
            "run",
            "wizard_run",
            "build_run",
            "init_pfs_run",
            "format_exfat_run",
            "scaffold_run",
            "validate_run",
            "prepare_run",
        }:
            button.label = "Executando…"
        elif not busy and str(button.label) == "Executando…":
            button.label = "Executar"
    for widget in screen.query(Input):
        widget.disabled = busy
    for widget in screen.query(Checkbox):
        widget.disabled = busy
    for widget in screen.query(ListView):
        widget.disabled = busy
    screen._batchkit_busy = busy  # type: ignore[attr-defined]


class LogScreen(Screen):
    BINDINGS = [
        ("escape", "pop_screen", "Voltar"),
    ]

    def __init__(self, title: str, lines: list[str], exit_code: int) -> None:
        super().__init__()
        self._title = title
        self._lines = lines
        self._exit_code = exit_code
        self._body = "\n".join(lines)

    def compose(self) -> ComposeResult:
        status = "OK" if self._exit_code == 0 else f"Erro (código {self._exit_code})"
        yield Header()
        yield Static(f"[bold]{self._title}[/bold] — {status}")
        yield TextArea(
            self._body,
            id="log",
            read_only=True,
            show_cursor=True,
            show_line_numbers=False,
            soft_wrap=True,
            highlight_cursor_line=False,
        )
        yield Static(LOG_KEYBOARD_HINT)
        with Horizontal(id="log_actions"):
            yield Button("Copiar tudo", id="copy_all", variant="default")
            yield Button("Voltar ao menu", id="back", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#log", TextArea).focus()

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "copy_all":
            self.app.copy_to_clipboard(self._body)
            self.notify("Texto copiado (Ctrl+Shift+V para colar no terminal).", timeout=4)


class FormScreen(Screen):
    BINDINGS = [
        ("escape", "pop_screen", "Voltar"),
        ("ctrl+enter", "submit_form", "Executar"),
        ("f10", "submit_form", "Executar"),
    ]

    def __init__(
        self,
        title: str,
        fields: list[tuple[str, str, str]],
        *,
        checkboxes: list[tuple[str, str, bool]] | None = None,
        action_id: str = "run",
    ) -> None:
        super().__init__()
        self._title = title
        self._fields = fields
        self._checkboxes = checkboxes or []
        self._action_id = action_id

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"[bold]{self._title}[/bold]")
        with VerticalScroll():
            with Vertical(id="form"):
                for fid, label, default in self._fields:
                    yield Label(label)
                    yield Input(value=default, id=fid)
                for cid, clabel, checked in self._checkboxes:
                    yield Checkbox(clabel, id=cid, value=checked)
        with Horizontal(id="form_actions"):
            yield Button("Executar", id=self._action_id, variant="success")
            yield Button("Cancelar", id="cancel")
        yield Static(KEYBOARD_HINT)

    def on_mount(self) -> None:
        inputs = self.query(Input)
        if inputs:
            inputs[0].focus()

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_submit_form(self) -> None:
        self.app.run_form_action(self)  # type: ignore[attr-defined]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.pop_screen()
            return
        if event.button.id == self._action_id:
            self.app.run_form_action(self)  # type: ignore[attr-defined]

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter no último campo avança para Executar; nos outros, Tab implícito."""
        inputs = list(self.query(Input))
        if not inputs:
            return
        if event.input == inputs[-1]:
            self.query_one(f"#{self._action_id}", Button).focus()
        else:
            idx = inputs.index(event.input)
            if idx + 1 < len(inputs):
                inputs[idx + 1].focus()
            else:
                boxes = list(self.query(Checkbox))
                if boxes:
                    boxes[0].focus()
                else:
                    self.query_one(f"#{self._action_id}", Button).focus()


class DiskPickerMixin:
    _disks: list

    def _refresh_disks(self) -> None:
        from .disks import list_physical_disks

        self._disks = list_physical_disks()
        lv = self.query_one("#disk_list", ListView)
        lv.clear()
        if not self._disks:
            lv.mount(
                ListItem(Label("[dim]Nenhum disco detectado — use caminho manual[/dim]"))
            )
            return
        for d in self._disks:
            lv.mount(ListItem(Label(d.summary_line()), id=f"disk-{d.index}"))

    def selected_device_path(self) -> Path | None:
        manual = self.query_one("#manual_device", Input).value.strip()
        if manual:
            return Path(manual)
        lv = self.query_one("#disk_list", ListView)
        if lv.index is None or not self._disks:
            return None
        highlighted = lv.highlighted_child
        if highlighted is None:
            return None
        item_id = highlighted.id or ""
        if not item_id.startswith("disk-"):
            return None
        try:
            index = int(item_id.removeprefix("disk-"))
        except ValueError:
            return None
        for d in self._disks:
            if d.index == index:
                return d.path
        return None


class PrepareDeviceScreen(DiskPickerMixin, Screen):
    BINDINGS = [
        ("escape", "pop_screen", "Voltar"),
        ("ctrl+enter", "submit_prepare", "Executar"),
        ("f10", "submit_prepare", "Executar"),
    ]

    def __init__(self, *, pfs_only: bool = False) -> None:
        super().__init__()
        self._disks = []
        self._pfs_only = pfs_only

    def compose(self) -> ComposeResult:
        yield Header()
        if self._pfs_only:
            yield Static(
                "[bold]Atualizar só PFS[/bold] [red]DESTRUTIVO em __system/__sysconf[/red] — "
                "FHDB/OSD/OPL/ATA-Assault; exFAT e jogos intactos"
            )
        else:
            yield Static(
                "[bold]Preparar disco[/bold] [red]DESTRUTIVO[/red] — "
                "lê o tamanho real, grava APA (384 MiB), opcional PFS + exFAT no restante"
            )
        yield ListView(id="disk_list")
        yield Label("Ou caminho manual (opcional):")
        yield Input(placeholder="/dev/sdb ou \\\\.\\PhysicalDrive2", id="manual_device")
        if not self._pfs_only:
            yield Label("Referência mbr.img (BAT):")
            yield Input(value="/tmp/pfs-batchkit/mbr.img", id="reference_mbr")
            yield Checkbox("Inicializar PFS (__system, __sysconf)", id="init_pfs", value=True)
            yield Checkbox(
                "Formatar exFAT + pastas OPL (root/sudo)",
                id="format_exfat",
                value=True,
            )
        yield from _elevation_fields()
        yield Checkbox(
            "Confirmo operação destrutiva no disco selecionado",
            id="force",
            value=False,
        )
        with Horizontal(id="form_actions"):
            yield Button("Atualizar lista", id="refresh_disks", variant="default")
            yield Button("Executar", id="prepare_run", variant="success")
            yield Button("Cancelar", id="cancel")
        yield Static(KEYBOARD_HINT)

    def on_mount(self) -> None:
        self._refresh_disks()
        lv = self.query_one("#disk_list", ListView)
        if lv.children:
            lv.focus()

    def action_pop_screen(self) -> None:
        self.app.pop_screen()

    def action_submit_prepare(self) -> None:
        self.app.run_prepare_action(self)  # type: ignore[attr-defined]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.app.pop_screen()
            return
        if event.button.id == "refresh_disks":
            self._refresh_disks()
            return
        if event.button.id == "prepare_run":
            self.app.run_prepare_action(self)  # type: ignore[attr-defined]


class BatchKitApp(App):
    TITLE = "PFS BatchKit"
    SUB_TITLE = f"v{__version__} — APA-Jail + exFAT OPL"

    def __init__(self) -> None:
        super().__init__()
        self._operation_screen: Screen | None = None

    CSS = """
    Screen { layout: vertical; }
    #form { padding: 1 2; height: auto; }
    #menu {
        height: 1fr;
        margin: 1 2;
        border: solid $accent;
        scrollbar-size: 1 1;
    }
    ListView:focus {
        border: solid $primary;
    }
    ListView > ListItem.-highlight {
        background: $accent 40%;
    }
    ListView:focus > ListItem.-highlight {
        background: $accent;
        color: $text;
    }
    TextArea#log {
        height: 1fr;
        margin: 1 2;
        border: solid $primary;
    }
    #log_actions { height: auto; align: center middle; padding: 0 1 1 1; }
    #log_actions Button { margin: 0 1; }
    #form_actions { height: auto; align: center middle; padding: 1; }
    #form_actions Button { margin: 0 1; }
    #hints_line { padding: 0 2 1 2; }
    """

    BINDINGS = [
        ("q", "quit", "Sair"),
        ("escape", "back_or_quit", "Voltar"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(
            "[bold]PFS BatchKit[/bold] — preparar HDD PS2\n"
            'Inspirado no fluxo do '
            '[link="https://github.com/GDX-X/PFS-BatchKit-Manager"]'
            "PFS-BatchKit-Manager[/link] (menu simplificado).\n"
            f"[dim]{elevation_hint_short()}[/dim]"
        )
        items = [
            ListItem(Label(f"[b]{i}[/b]  {label}"), id=key)
            for i, (key, label) in enumerate(MENU_ITEMS, start=1)
        ]
        yield ListView(*items, id="menu")
        yield Static(KEYBOARD_HINT, id="hints_line")
        yield Footer()

    def on_mount(self) -> None:
        menu = self.query_one("#menu", ListView)
        menu.focus()
        if menu.children:
            menu.index = 0

    def action_back_or_quit(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()
            if len(self.screen_stack) == 1:
                self.call_after_refresh(self._focus_main_menu)
        # No menu principal, Esc não fecha (use q) — evita sair acidentalmente.

    def _focus_main_menu(self) -> None:
        if self.query("#menu"):
            self.query_one("#menu", ListView).focus()

    def on_key(self, event: events.Key) -> None:
        if len(self.screen_stack) > 1:
            return
        char = event.character
        if not char or not char.isdigit():
            return
        n = int(char)
        if 1 <= n <= len(MENU_ITEMS):
            self.open_menu_item(MENU_ITEMS[n - 1][0])
            event.prevent_default()
            event.stop()
        elif char == "0" and len(MENU_ITEMS) >= 10:
            self.open_menu_item(MENU_ITEMS[9][0])
            event.prevent_default()
            event.stop()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.open_menu_item(event.item.id)

    def open_menu_item(self, item_id: str | None) -> None:
        if not item_id:
            return
        if item_id == "wizard":
            self.push_screen(
                FormScreen(
                    "Assistente completo",
                    [
                        ("size_gib", "Tamanho total do disco (GiB):", "500"),
                        (
                            "output",
                            "Arquivo de saída (.img):",
                            str(Path.home() / "ps2-hdd.img"),
                        ),
                        (
                            "reference_mbr",
                            "Referência mbr.img (BAT):",
                            "/tmp/pfs-batchkit/mbr.img",
                        ),
                    ],
                    checkboxes=[
                        ("init_pfs", "Inicializar PFS (__system, __sysconf)", True),
                        (
                            "format_exfat",
                            "Formatar exFAT no restante do disco (precisa root/sudo)",
                            True,
                        ),
                        ("scaffold_opl", "Criar pastas OPL após formatar exFAT", True),
                    ],
                    action_id="wizard_run",
                )
            )
        elif item_id == "prepare_device":
            self.push_screen(PrepareDeviceScreen())
        elif item_id == "prepare_pfs":
            self.push_screen(PrepareDeviceScreen(pfs_only=True))
        elif item_id == "build":
            self.push_screen(
                FormScreen(
                    "Criar imagem",
                    [
                        ("size_gib", "Tamanho total (GiB):", "500"),
                        ("output", "Arquivo .img:", str(Path.home() / "ps2-hdd.img")),
                        (
                            "reference_mbr",
                            "mbr.img:",
                            "/tmp/pfs-batchkit/mbr.img",
                        ),
                    ],
                    action_id="build_run",
                )
            )
        elif item_id == "init_pfs":
            self.push_screen(
                FormScreen(
                    "Inicializar PFS",
                    [("image", "Imagem híbrida:", str(Path.home() / "ps2-hdd.img"))],
                    action_id="init_pfs_run",
                )
            )
        elif item_id == "format_exfat":
            self.push_screen(
                FormScreen(
                    "Formatar exFAT",
                    [("image", "Imagem híbrida:", str(Path.home() / "ps2-hdd.img"))],
                    checkboxes=[("scaffold_opl", "Criar pastas OPL", True)],
                    action_id="format_exfat_run",
                )
            )
        elif item_id == "scaffold_opl":
            self.push_screen(
                FormScreen(
                    "Pastas OPL",
                    [("mount", "Pasta montada (exFAT):", "/mnt/PS2OPL")],
                    action_id="scaffold_run",
                )
            )
        elif item_id == "list_disks":
            from .disks import format_disk_listing, list_physical_disks

            self.push_screen(
                LogScreen(
                    "Discos físicos",
                    format_disk_listing(list_physical_disks()),
                    0,
                )
            )
        elif item_id == "validate_opl":
            self.push_screen(
                FormScreen(
                    "Validar layout OPL",
                    [("image", "Imagem híbrida:", str(Path.home() / "ps2-hdd.img"))],
                    checkboxes=[
                        ("require_exfat", "Exigir superblock exFAT formatado", False),
                        ("strict", "Strict (aviso = erro)", False),
                    ],
                    action_id="validate_run",
                )
            )
        elif item_id == "requirements":
            self.push_screen(LogScreen("Requisitos", requirements_lines(), 0))

    def _begin_operation(self, screen: Screen) -> bool:
        if getattr(screen, "_batchkit_busy", False):
            return False
        self._operation_screen = screen
        _set_screen_operation_busy(screen, busy=True)
        return True

    def _end_operation(self) -> None:
        screen = self._operation_screen
        if screen is not None:
            _set_screen_operation_busy(screen, busy=False)
        self._operation_screen = None

    def run_form_action(self, screen: FormScreen) -> None:
        if not self._begin_operation(screen):
            return
        action = screen._action_id  # noqa: SLF001
        if action == "wizard_run":
            self._run_wizard(screen)
        elif action == "build_run":
            self._run_build_only(screen)
        elif action == "init_pfs_run":
            self._run_init_pfs(screen)
        elif action == "format_exfat_run":
            self._run_format_exfat(screen)
        elif action == "scaffold_run":
            self._run_scaffold(screen)
        elif action == "validate_run":
            self._run_validate(screen)

    def run_prepare_action(self, screen: PrepareDeviceScreen) -> None:
        if not self._begin_operation(screen):
            return
        self._run_prepare_device(screen)

    @work(thread=True)
    def _run_validate(self, screen: FormScreen) -> None:
        from .opl_validate import format_report, validate_opl_layout

        image = Path(screen.query_one("#image", Input).value.strip()).expanduser()
        require_exfat = screen.query_one("#require_exfat", Checkbox).value
        strict = screen.query_one("#strict", Checkbox).value
        report = validate_opl_layout(image, require_exfat=require_exfat)
        lines = format_report(report)
        code = report.exit_code(strict=strict)
        self.call_from_thread(self._show_result, "Validar OPL", lines, code)

    @work(thread=True)
    def _run_wizard(self, screen: FormScreen) -> None:
        size = float(screen.query_one("#size_gib", Input).value.strip())
        output = Path(screen.query_one("#output", Input).value.strip()).expanduser()
        ref = Path(screen.query_one("#reference_mbr", Input).value.strip()).expanduser()
        init_pfs = screen.query_one("#init_pfs", Checkbox).value
        format_exfat = screen.query_one("#format_exfat", Checkbox).value
        scaffold = screen.query_one("#scaffold_opl", Checkbox).value
        try:
            ensure_reference_mbr(ref)
        except OSError as exc:
            self.call_from_thread(
                self._show_result,
                "Assistente",
                [f"Não foi possível obter mbr.img: {exc}"],
                2,
            )
            return
        outcome = run_build_image(
            output,
            size,
            reference_mbr=ref,
            init_pfs=init_pfs,
            format_exfat=format_exfat,
            scaffold_opl=scaffold,
        )
        if format_exfat and outcome.exit_code != 0:
            outcome.messages.append(
                "Se exFAT falhou por sudo: rode a TUI com sudo ou use format-exfat depois."
            )
        self.call_from_thread(
            self._show_result, "Assistente completo", outcome.messages, outcome.exit_code
        )

    @work(thread=True)
    def _run_build_only(self, screen: FormScreen) -> None:
        size = float(screen.query_one("#size_gib", Input).value.strip())
        output = Path(screen.query_one("#output", Input).value.strip()).expanduser()
        ref = Path(screen.query_one("#reference_mbr", Input).value.strip()).expanduser()
        try:
            ensure_reference_mbr(ref)
        except OSError as exc:
            self.call_from_thread(
                self._show_result, "Criar imagem", [f"mbr.img: {exc}"], 2
            )
            return
        outcome = run_build_image(output, size, reference_mbr=ref)
        self.call_from_thread(
            self._show_result, "Criar imagem", outcome.messages, outcome.exit_code
        )

    @work(thread=True)
    def _run_init_pfs(self, screen: FormScreen) -> None:
        image = Path(screen.query_one("#image", Input).value.strip()).expanduser()
        code, lines = run_init_pfs(image)
        self.call_from_thread(self._show_result, "Init PFS", lines, code)

    @work(thread=True)
    def _run_format_exfat(self, screen: FormScreen) -> None:
        image = Path(screen.query_one("#image", Input).value.strip()).expanduser()
        scaffold = screen.query_one("#scaffold_opl", Checkbox).value
        code, lines = run_format_exfat(image, scaffold_opl=scaffold)
        self.call_from_thread(self._show_result, "Format exFAT", lines, code)

    @work(thread=True)
    def _run_scaffold(self, screen: FormScreen) -> None:
        mount = Path(screen.query_one("#mount", Input).value.strip()).expanduser()
        code, lines = run_scaffold_opl(mount)
        self.call_from_thread(self._show_result, "OPL scaffold", lines, code)

    @work(thread=True)
    def _run_prepare_device(self, screen: PrepareDeviceScreen) -> None:
        device = screen.selected_device_path()
        force = screen.query_one("#force", Checkbox).value
        pfs_only = getattr(screen, "_pfs_only", False)
        init_pfs = True
        format_exfat = False
        ref = Path("/tmp/pfs-batchkit/mbr.img")
        if not pfs_only:
            init_pfs = screen.query_one("#init_pfs", Checkbox).value
            format_exfat = screen.query_one("#format_exfat", Checkbox).value
            ref = Path(screen.query_one("#reference_mbr", Input).value.strip()).expanduser()

        title = "Atualizar PFS" if pfs_only else "Preparar disco"

        if device is None:
            self.call_from_thread(
                self._show_result,
                title,
                [
                    "Selecione um disco na lista ou informe o caminho manual.",
                    "Dica: menu «Listar discos» ou `pfs-batchkit list-disks`.",
                ],
                2,
            )
            return
        if not force:
            self.call_from_thread(
                self._show_result,
                title,
                ["Marque a confirmação para continuar."],
                2,
            )
            return
        grant_destructive_write_in_process()
        sudo_pw: str | None = None
        if not is_admin():
            if host_os() == "windows":
                self.call_from_thread(
                    self._show_result,
                    title,
                    [
                        "Abra o PowerShell ou CMD como Administrador ",
                        "e execute pfs-batchkit-ui novamente.",
                    ],
                    2,
                )
                return
            sudo_pw = screen.query_one("#sudo_password", Input).value.strip()
            if not sudo_pw:
                self.call_from_thread(
                    self._show_result,
                    title,
                    [
                        "Informe a senha sudo nesta tela ",
                        "ou inicie o app com: sudo ./pfs-batchkit-ui",
                    ],
                    2,
                )
                return
        if not pfs_only:
            try:
                ensure_reference_mbr(ref)
            except OSError as exc:
                self.call_from_thread(
                    self._show_result,
                    title,
                    [f"Não foi possível obter mbr.img: {exc}"],
                    2,
                )
                return

        if pfs_only:
            outcome = run_prepare_pfs_device(
                device,
                force=True,
                sudo_password=sudo_pw,
            )
        else:
            outcome = run_prepare_device(
                device,
                reference_mbr=ref,
                init_pfs=init_pfs,
                format_exfat=format_exfat,
                force=True,
                sudo_password=sudo_pw,
            )
        self.call_from_thread(
            self._show_result,
            title,
            outcome.messages,
            outcome.exit_code,
        )

    def _show_result(self, title: str, lines: list[str], exit_code: int) -> None:
        self._end_operation()
        self.push_screen(LogScreen(title, lines, exit_code))


def run_app() -> None:
    BatchKitApp().run()
