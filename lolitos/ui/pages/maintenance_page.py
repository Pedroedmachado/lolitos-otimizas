"""Manutenção: ferramentas do próprio Windows para manter o sistema saudável."""
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout

from lolitos.i18n import tr
from lolitos.modules import repair, weekly
from lolitos.ui.widgets import (Card, Page, TaskDialog, Toggle, button, confirm, hrow, info, label, pill,
                                run_async)

GROUP_TITLES = {"Saúde": "Saúde do Windows", "Rede": "Rede", "Windows": "Windows e dispositivos"}


class MaintenancePage(Page):
    title = "Manutenção"
    subtitle = ("Ferramentas do próprio Windows para manter o sistema saudável e corrigir problemas. "
                "O comando exato é mostrado antes de rodar.")

    def build(self):
        self.body.addWidget(self._weekly_card())
        self.body.addWidget(label("Outras ferramentas", "h2"))
        groups: dict[str, list] = {}
        for t in repair.TOOLS:
            groups.setdefault(t.group, []).append(t)
        for g, items in groups.items():
            self.body.addWidget(label(GROUP_TITLES.get(g, g), "h2"))
            grid = QGridLayout()
            grid.setSpacing(10)
            for i, t in enumerate(items):
                c = Card()
                c.lay.addWidget(label(f"<b>{t.name}</b>" + (f" · {t.minutes}" if t.minutes else ""), rich=True))
                c.lay.addWidget(label(t.desc, "muted"))
                c.lay.addLayout(hrow(button("Executar", on_click=lambda _=False, tt=t: self.run_tool(tt)), None))
                grid.addWidget(c, i // 2, i % 2)
            self.body.addLayout(grid)

    # ---------------------------------------------------------------- revisão semanal
    def _weekly_card(self):
        c = Card(hero=True)
        top = QHBoxLayout()
        top.addWidget(label("<b>Revisão semanal</b>", "h3", rich=True))
        top.addWidget(pill("Recomendado · 1 vez por semana"), 0, Qt.AlignVCenter)
        top.addStretch()
        self.wk_toggle = Toggle(False)
        self.wk_toggle.clicked.connect(self._weekly_toggle)
        top.addWidget(label("Toda semana, sozinho", "muted", wrap=False), 0, Qt.AlignVCenter)
        top.addWidget(self.wk_toggle, 0, Qt.AlignVCenter)
        c.lay.addLayout(top)
        c.lay.addWidget(label("Confere a saúde do Windows e corrige o que estiver danificado, sem desfazer nenhum "
                              "ajuste. Leva de 10 a 30 minutos.", "muted"))
        c.lay.addWidget(label("• Verificar o disco (só leitura)<br>• Reparar a imagem do Windows (DISM)<br>"
                              "• Verificar os arquivos protegidos do sistema (SFC)", rich=True))
        c.lay.addWidget(label("Automático: todo domingo às 12h; se o PC estiver desligado, roda na próxima vez que "
                              "você entrar no Windows, escondido, e o resultado vai para Restauração › Histórico.",
                              "muted"))
        self.wk_last = label("", "muted", wrap=False)
        c.lay.addLayout(hrow(button("Rodar agora", "primary", self._weekly_now), self.wk_last, None))
        self._weekly_state()
        return c

    def _weekly_state(self):
        last = weekly.last_run()
        self.wk_last.setText(tr("Última revisão: {}").replace(
            "{}", time.strftime("%d/%m/%Y %H:%M", time.localtime(last)) if last else tr("nunca")))
        run_async(weekly.enabled, on_done=lambda on: (self.wk_toggle.blockSignals(True),
                                                      self.wk_toggle.setChecked(bool(on)),
                                                      self.wk_toggle.blockSignals(False)))

    def _weekly_toggle(self):
        want = self.wk_toggle.isChecked()

        def done(r):
            ok, msg = r
            if not ok and want:
                info(self, "Revisão semanal", tr("Não deu para criar a tarefa agendada: {}").replace("{}", msg))
            self._weekly_state()
        run_async(weekly.enable, want, on_done=done)

    def _weekly_now(self):
        if not confirm(self, "Revisão semanal", "Rodar a revisão agora? Leva de 10 a 30 minutos; dá para continuar "
                       "usando o PC (evite jogar durante).", yes="Rodar agora"):
            return

        def work(progress=None):
            ok, text = weekly.run_review(progress)
            return text + ("\n\nTudo certo." if ok else "\n\nTerminou com avisos (veja acima).")
        TaskDialog(self, "Revisão semanal", work, on_done=lambda _: self._weekly_state()).exec()

    def run_tool(self, t):
        if not confirm(self, t.name, f"<p>{t.desc}</p><p><b>O que será executado:</b><br><code>{t.cmd}</code></p>",
                       yes="Executar"):
            return

        def work(progress=None):
            progress(f"> {t.cmd}")
            ok, out = repair.run_tool(t)
            return (out or "") + ("\n\nReinicie o PC para concluir." if t.restart else "") + \
                ("" if ok else "\n\nTerminou com avisos ou erros (veja acima).")
        TaskDialog(self, t.name, work).exec()
