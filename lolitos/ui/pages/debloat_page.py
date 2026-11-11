"""Debloat: tudo que dá para tirar do Windows numa tela só.

- Essencial e Recomendado: seguro em qualquer PC; vem marcado o que ainda não está aplicado.
- Avançados: com contrapartida visível; nada vem marcado e cada item mostra o que se perde.
- Apps pré-instalados: só os que existem nesta conta; os marcados com ⚠ começam desmarcados.
Cada item aplicado tem o próprio Desfazer (menos apps removidos, que voltam pela Microsoft Store)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QGridLayout, QWidget

from lolitos.catalog.debloat import DEBLOAT_TWEAKS, ONEDRIVE
from lolitos.catalog.sem_ia import CAPABILITY_TWEAKS
from lolitos.core.actions import APPX
from lolitos.core.tweaks import ADVANCED, CATALOG
from lolitos.i18n import tr
from lolitos.ui.theme import C
from lolitos.ui.tweaklist import TweakList, bulk_apply
from lolitos.ui.widgets import Card, Page, TaskDialog, button, confirm, hrow, info, label, run_async, status_pool

# Ordem pensada para quem lê de cima para baixo: o que mais pesa e mais incomoda primeiro.
ESSENTIAL_IDS = [
    "edge_background_off", "widgets_off", "chat_meetnow_off", "consumer_features_off", "telemetry_min",
    "diagtrack_manual", "telemetry_tasks", "data_collect_tasks", "appcompat_telemetry_off", "copilot_off",
    "recall_off", "clicktodo_off", "delivery_p2p_off", "search_local", "speech_models_off", "explorer_cloud_off",
    "settings_agent_off", "push_install_off", "motion_bg_off", "ad_id_off", "no_outlook_devhome", "ads_start",
    "spotlight_off", "notepad_no_ad", "scoobe_off", "track_progs_off",
    # recomendados
    "background_apps_off", "game_dvr_off", "remove_copilot_apps", "services_manual", "diag_collector_manual",
    "clipboard_cloud_off", "pca_off", "wer_off",
]
ADVANCED_IDS = [
    "sysmain_off", "search_index_off", "spooler_manual", "hibernation_off", "reserved_storage_off",
    "driver_software_off", "device_metadata_off", "onedrive_remove", "remove_recall_feature",
    "cap_mathrecognizer", "cap_language_handwriting", "cap_app_support_quickassist", "cap_app_stepsrecorder",
    "cap_language_speech", "cap_language_texttospeech", "cap_hello_face", "cap_onesync", "rdp_client_remove",
    "cap_microsoft_windows_wordpad", "cap_print_fax_scan", "appcompat_engine_off", "findmydevice_off",
    "store_autoupdate_off", "wu_notifs_off", "wer_logging_off", "bg_apps_policy",
]


def _pick(ids):
    out, seen = [], set()
    for i in ids:
        t = CATALOG.get(i)
        if t and t.id not in seen:
            out.append(t)
            seen.add(t.id)
    return out


def _app_states(tweaks):
    APPX.invalidate()
    return {t.id: t.status() for t in tweaks}


class DebloatPage(Page):
    title = "Debloat"
    subtitle = ("Marque o que você quer tirar do Windows e clique em Aplicar selecionados. O Essencial e o "
                "Recomendado também entram no Boost do Painel. Cada item aplicado tem o próprio Desfazer.")

    def build(self):
        ess = _pick(ESSENTIAL_IDS)
        adv = _pick([*ADVANCED_IDS, *(t.id for t in CAPABILITY_TWEAKS), ONEDRIVE.id])
        self.counter = label("", "muted", wrap=False)
        self.actions.addWidget(self.counter)

        # ------------------------------------------------ essencial e recomendado
        c1 = Card()
        c1.lay.addLayout(hrow(label("Essencial e Recomendado", "h2"), None,
                              button("Marcar todos", on_click=lambda: self.ess.set_all(True)),
                              button("Desmarcar todos", on_click=lambda: self.ess.set_all(False))))
        c1.lay.addWidget(label("Seguro em qualquer PC. O Recomendado deixa o PC mais leve, mas avisa em amarelo o "
                               "que se perde. Os dois vêm marcados quando ainda não estão aplicados.", "muted"))
        self.ess = TweakList(ess, self, search=False, bar=False, on_selection=self._count,
                             on_states=self._first_mark, table=True)
        c1.lay.addWidget(self.ess)
        self.body.addWidget(c1)

        # ------------------------------------------------ avançados
        c2 = Card()
        self.adv_btn = button("Esconder avançados", on_click=self._toggle_adv)
        c2.lay.addLayout(hrow(label("Avançados", "h2"), None, self.adv_btn))
        c2.lay.addWidget(label("Mais leveza com contrapartidas visíveis. Ao marcar um item, o app mostra os prós e "
                               "contras e pede confirmação. Nenhum vem marcado.", "muted"))
        self.adv = TweakList(adv, self, search=False, bar=False, on_selection=self._count,
                             on_states=self._adv_label, table=True)
        c2.lay.addWidget(self.adv)
        self.body.addWidget(c2)

        # ------------------------------------------------ aplicar
        c3 = Card(hero=True)
        self.sel_txt = label("", "muted")
        self.apply_btn = button("Aplicar selecionados", "primary", self._apply)
        c3.lay.addLayout(hrow(self.sel_txt, self.apply_btn, stretch_first=True))
        self.body.addWidget(c3)

        # ------------------------------------------------ apps pré-instalados
        c4 = Card()
        self.rm_btn = button("Remover selecionados", on_click=self._remove_apps)
        c4.lay.addLayout(hrow(label("Apps pré-instalados", "h2"), None,
                              button("Atualizar lista", on_click=self._load_apps), self.rm_btn))
        c4.lay.addWidget(label("Apps que vêm com o Windows e quase ninguém usa. Os marcados com ⚠ começam "
                               "desmarcados. Sem Desfazer: se precisar de algum, reinstale pela Microsoft Store.",
                               "muted"))
        self.apps_w = QWidget()
        self.apps_grid = QGridLayout(self.apps_w)
        self.apps_grid.setContentsMargins(0, 4, 0, 0)
        self.apps_grid.setHorizontalSpacing(18)
        self.apps_grid.setVerticalSpacing(8)
        c4.lay.addWidget(self.apps_w)
        self.apps_txt = label("Procurando os apps desta conta…", "muted")
        c4.lay.addWidget(self.apps_txt)
        self.body.addWidget(c4)
        self.app_checks: dict[str, QCheckBox] = {}
        self._marked_once = False
        self._adv_hidden = False
        self._load_apps()
        self._count()

    # ---------------------------------------------------------------- seleção
    def _first_mark(self):
        if not self._marked_once:
            self._marked_once = True
            self.ess.mark_defaults()
        self._count()

    def _adv_label(self):
        n = self.adv.pending()
        self.adv_btn.setText(tr("Mostrar avançados ({} não aplicados)" if self._adv_hidden else
                                "Esconder avançados ({} não aplicados)").replace("{}", str(n)))
        self._count()

    def _toggle_adv(self):
        self._adv_hidden = not self._adv_hidden
        self.adv.setVisible(not self._adv_hidden)
        self._adv_label()

    def _count(self):
        n = len(self.ess.selected()) + len(self.adv.selected())
        on = sum(1 for lst in (self.ess, self.adv) for s in lst.states.values() if s == "on")
        tot = sum(1 for lst in (self.ess, self.adv) for s in lst.states.values() if s != "na")
        self.counter.setText(tr("{} de {} aplicados").replace("{}", str(on), 1).replace("{}", str(tot), 1))
        self.sel_txt.setText(tr("{} item(ns) selecionado(s). Um ponto de restauração é criado antes. Alguns só "
                                "valem depois de reiniciar.").replace("{}", str(n)))
        self.apply_btn.setText(tr("Aplicar selecionados ({})").replace("{}", str(n)))
        self.apply_btn.setEnabled(n > 0)

    def _apply(self):
        sel = self.ess.selected() + self.adv.selected()
        if not sel:
            return
        adv = [t for t in sel if t.level == ADVANCED or not t.reversible]
        if adv:
            txt = "".join(f"<p><b>{tr(t.title)}</b><br><span style='color:{C['warn']}'>{tr(t.loss) or tr(t.desc)}"
                          "</span></p>" for t in adv)
            if not confirm(self, "Itens avançados", tr("Você marcou itens com contrapartida:") + txt +
                           tr("Continuar?"), yes="Aplicar"):
                return
        TaskDialog(self, tr("Aplicando {} ajuste(s)").replace("{}", str(len(sel))), bulk_apply, sel,
                   on_done=lambda _: self._after()).exec()

    def _after(self):
        self.ess.refresh()
        self.adv.refresh()
        if self.main:
            self.main.changed()

    # ---------------------------------------------------------------- apps
    def _load_apps(self):
        self.apps_txt.setText(tr("Procurando os apps desta conta…"))
        run_async(_app_states, DEBLOAT_TWEAKS, on_done=self._show_apps, _pool=status_pool())

    def _show_apps(self, st: dict):
        while self.apps_grid.count():
            w = self.apps_grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.app_checks = {}
        present = [t for t in DEBLOAT_TWEAKS if st.get(t.id) in ("off", "partial")]
        cols = 4
        for i, t in enumerate(present):
            warn = t.level == ADVANCED
            cb = QCheckBox(tr(t.title.split(" (")[0] if len(t.title) > 34 else t.title) + ("  ⚠" if warn else ""))
            cb.setChecked(not warn)
            tip = tr(t.loss) if t.loss else tr(t.desc)
            cb.setToolTip(tip)
            cb.setCursor(Qt.PointingHandCursor)
            cb.toggled.connect(lambda _=False: self._apps_count())
            self.app_checks[t.id] = cb
            self.apps_grid.addWidget(cb, i // cols, i % cols)
        gone = sum(1 for t in DEBLOAT_TWEAKS if st.get(t.id) == "on")
        self.apps_txt.setText(
            tr("{} app(s) deste catálogo instalados nesta conta · {} já removido(s).")
            .replace("{}", str(len(present)), 1).replace("{}", str(gone), 1) if present else
            tr("Nenhum app deste catálogo está instalado nesta conta."))
        self._apps_count()

    def _apps_count(self):
        n = sum(1 for cb in self.app_checks.values() if cb.isChecked())
        self.rm_btn.setText(tr("Remover selecionados ({})").replace("{}", str(n)))
        self.rm_btn.setEnabled(n > 0)

    def _remove_apps(self):
        sel = [CATALOG[k] for k, cb in self.app_checks.items() if cb.isChecked()]
        if not sel:
            info(self, "Nada selecionado", "Marque os apps que você quer remover.")
            return
        if not confirm(self, "Remover apps", tr("Remover {} app(s)? Eles não têm Desfazer: se precisar de algum, "
                                                "reinstale pela Microsoft Store.").replace("{}", str(len(sel))) +
                       "<br><br>• " + "<br>• ".join(tr(t.title) for t in sel), yes="Remover"):
            return
        TaskDialog(self, tr("Removendo {} app(s)").replace("{}", str(len(sel))), bulk_apply, sel,
                   on_done=lambda _: self._load_apps()).exec()

    def on_show(self):
        APPX.invalidate()
