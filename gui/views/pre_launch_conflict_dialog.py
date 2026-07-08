# -*- coding: utf-8 -*-
"""
gui/views/pre_launch_conflict_dialog.py

Diálogo que se muestra antes de lanzar el juego si se detectan mods
instalados que son incompatibles entre sí. Por cada conflicto, ofrece:
  - Buscar versión compatible del mod A
  - Desactivar el mod A
  - Ignorar y continuar
"""
import os
import threading
import flet as ft

from gui.theme import CARD_BG, CARD2_BG, INPUT_BG, BORDER, GREEN, TEXT_PRI, TEXT_SEC, TEXT_DIM, TEXT_INV, ACCENT_RED


def _mini_icon(url: str, title: str, size: int = 36) -> ft.Control:
    fallback = ft.Container(
        width=size, height=size, border_radius=8,
        bgcolor=CARD2_BG, alignment=ft.alignment.center,
        content=ft.Text(
            (title[0] if title else "?").upper(),
            color=TEXT_DIM, size=13, weight=ft.FontWeight.BOLD,
        ),
    )
    if not url:
        return fallback
    return ft.Image(
        src=url, width=size, height=size,
        border_radius=8, fit=ft.ImageFit.COVER,
        error_content=fallback,
    )

def show_pre_launch_conflict_dialog(
    page: ft.Page,
    app,
    profile,
    conflicts: list[dict],
    mods_dir: str,
    on_resolved,
    on_ignore,
    missing_deps: list[dict] = None,
    loader: str = None,
    natives_status: dict = None,
):
    missing_deps = missing_deps or []
    natives_status = natives_status or {"ok": True, "missing_jars": []}
    """
    conflicts: salida de ModrinthService.check_installed_conflicts()
    on_resolved: callback llamado cuando el usuario resuelve TODOS los
                 conflictos (desactivando o actualizando) y quiere reintentar.
    on_ignore: callback llamado si el usuario elige lanzar igual, ignorando
               los conflictos restantes.
    """
    from managers.mod_manager import ModManager

    mod_manager = ModManager(profile)
    conflict_rows = ft.Column(spacing=10)

    def _rebuild_conflict_rows():
        conflict_rows.controls.clear()
        for conflict in conflicts:
            mod_a = conflict["mod_a"]
            mod_b = conflict["mod_b"]
            if not mod_a or not mod_b:
                continue

            status_txt = ft.Text("", color=TEXT_DIM, size=10)

            def _make_handlers(c=conflict, status=status_txt):
                mod_a_obj = c["mod_a"]

                def _disable(e):
                    try:
                        for filename in os.listdir(mods_dir):
                            full = os.path.join(mods_dir, filename)
                            if not os.path.isfile(full):
                                continue
                            proj = app.modrinth_service.get_project_by_file_hash(full)
                            if proj and proj.project_id == mod_a_obj.project_id:
                                if not full.endswith(".disabled"):
                                    os.rename(full, full + ".disabled")
                                status.value = "✓ Desactivado"
                                status.color = GREEN
                                try: status.update()
                                except Exception: pass
                                return
                    except Exception as ex:
                        status.value = f"Error: {ex}"
                        try: status.update()
                        except Exception: pass

                def _find_update(e):
                    status.value = "Buscando versión compatible…"
                    try: status.update()
                    except Exception: pass

                    def do():
                        try:
                            other_ids = [
                                cc["mod_b"].project_id for cc in conflicts
                                if cc["mod_a"] and cc["mod_a"].project_id == mod_a_obj.project_id
                                and cc["mod_b"]
                            ]
                            installed_projects = app.modrinth_service.get_installed_projects(mods_dir)
                            version, remaining_conflicts = app.modrinth_service.find_compatible_version(
                                mod_a_obj.project_id,
                                installed_projects,
                                mc_version=getattr(profile, "version_id", None),
                            )
                            def update():
                                if version:
                                    status.value = "✓ Versión compatible encontrada, instalando…"
                                    try: status.update()
                                    except Exception: pass
                                    threading.Thread(
                                        target=lambda: _install_and_report(version, status),
                                        daemon=True,
                                    ).start()
                                else:
                                    status.value = "✗ No hay versión compatible disponible"
                                    status.color = ACCENT_RED
                                    try: status.update()
                                    except Exception: pass
                            page.run_thread(update)
                        except Exception as ex:
                            def err():
                                status.value = f"Error: {ex}"
                                try: status.update()
                                except Exception: pass
                            page.run_thread(err)

                    threading.Thread(target=do, daemon=True).start()

                def _install_and_report(version, status):
                    try:
                        # Borrar la versión vieja del mod antes de instalar la nueva
                        for filename in os.listdir(mods_dir):
                            full = os.path.join(mods_dir, filename)
                            if not os.path.isfile(full):
                                continue
                            proj = app.modrinth_service.get_project_by_file_hash(full)
                            if proj and proj.project_id == mod_a_obj.project_id:
                                os.remove(full)
                        app.modrinth_service.download_mod_version(version, mods_dir)
                        def done():
                            status.value = "✓ Actualizado correctamente"
                            status.color = GREEN
                            try: status.update()
                            except Exception: pass
                        page.run_thread(done)
                    except Exception as ex:
                        def err():
                            status.value = f"Error al instalar: {ex}"
                            status.color = ACCENT_RED
                            try: status.update()
                            except Exception: pass
                        page.run_thread(err)

                return _disable, _find_update

            disable_fn, update_fn = _make_handlers()

            row = ft.Container(
                bgcolor=CARD2_BG, border_radius=10,
                padding=ft.padding.all(12),
                content=ft.Column([
                    ft.Row([
                        _mini_icon(mod_a.icon_url, mod_a.title),
                        ft.Container(width=8),
                        ft.Icon(ft.icons.CLOSE_ROUNDED, size=14, color=ACCENT_RED),
                        ft.Container(width=8),
                        _mini_icon(mod_b.icon_url, mod_b.title),
                        ft.Container(width=10),
                        ft.Column([
                            ft.Text(f"{mod_a.title}  vs  {mod_b.title}",
                                    color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
                            ft.Text("Estos mods son incompatibles entre sí",
                                    color=TEXT_DIM, size=10),
                        ], spacing=2, expand=True),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=8),
                    ft.Row([
                        ft.OutlinedButton(
                            "Buscar actualización",
                            icon=ft.icons.SYSTEM_UPDATE_ROUNDED,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8),
                                side=ft.BorderSide(1, GREEN), color=GREEN,
                            ),
                            on_click=update_fn,
                        ),
                        ft.Container(width=8),
                        ft.OutlinedButton(
                            f"Desactivar {mod_a.title}",
                            icon=ft.icons.TOGGLE_OFF_ROUNDED,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8),
                                side=ft.BorderSide(1, ACCENT_RED), color=ACCENT_RED,
                            ),
                            on_click=disable_fn,
                        ),
                    ]),
                    ft.Container(height=4),
                    status_txt,
                ], spacing=0),
            )
            conflict_rows.controls.append(row)

        try: conflict_rows.update()
        except Exception: pass

    _rebuild_conflict_rows()

    missing_rows = ft.Column(spacing=10)

    def _rebuild_missing_rows():
        missing_rows.controls.clear()
        for item in missing_deps:
            mod = item["mod"]
            dep_project = item["missing_project"]
            if not mod or not dep_project:
                continue

            status_txt = ft.Text("", color=TEXT_DIM, size=10)

            def _install(e, dep=dep_project, status=status_txt, entry=item):
                status.value = "Instalando…"
                status.color = TEXT_DIM
                try: status.update()
                except Exception: pass

                def do():
                    try:
                        required_version_id = entry.get("required_version_id")

                        # 1) Si Modrinth pide un version_id EXACTO, usar ese
                        if required_version_id:
                            version = app.modrinth_service.get_version_by_id(
                                required_version_id
                            )
                        else:
                            version = None

                        # 2) Si no hay version_id exacto (o falló), buscar
                        #    la más reciente compatible con MC + loader
                        if not version:
                            version = app.modrinth_service.get_latest_version(
                                dep.project_id,
                                mc_version=getattr(profile, "version_id", None),
                                loader=loader,
                            )
                        if not version:
                            version = app.modrinth_service.get_latest_version(
                                dep.project_id,
                                mc_version=getattr(profile, "version_id", None),
                                loader=None,
                            )

                        if not version:
                            def notfound():
                                status.value = "✗ No se encontró versión compatible"
                                status.color = ACCENT_RED
                                try: status.update()
                                except Exception: pass
                            page.run_thread(notfound)
                            return

                        if loader and version.loaders and loader not in version.loaders:
                            def wrongloader():
                                status.value = (
                                    f"✗ La versión encontrada es para "
                                    f"{', '.join(version.loaders)}, no {loader}"
                                )
                                status.color = ACCENT_RED
                                try: status.update()
                                except Exception: pass
                            page.run_thread(wrongloader)
                            return

                        # 3) Si YA había una versión distinta instalada de
                        #    este mismo mod, borrarla antes de instalar la nueva
                        try:
                            for filename in os.listdir(mods_dir):
                                full = os.path.join(mods_dir, filename)
                                if not os.path.isfile(full):
                                    continue
                                existing_proj = app.modrinth_service.get_project_by_file_hash(full)
                                if existing_proj and existing_proj.project_id == dep.project_id:
                                    os.remove(full)
                        except Exception:
                            pass

                        app.modrinth_service.download_mod_version(version, mods_dir)

                        def done():
                            status.value = f"✓ Instalado ({version.version_number})"
                            status.color = GREEN
                            try: status.update()
                            except Exception: pass
                        page.run_thread(done)
                    except Exception as ex:
                        def err(ex=ex):
                            status.value = f"Error: {ex}"
                            status.color = ACCENT_RED
                            try: status.update()
                            except Exception: pass
                        page.run_thread(err)

                threading.Thread(target=do, daemon=True).start()

            parent_wrong = item.get("parent_wrong_loader", False)

            if parent_wrong:
                # El problema real es que el mod PADRE (mod_a) no es la
                # versión correcta para este loader — no tiene sentido
                # ofrecer instalar la dependencia, hay que arreglar el padre.
                def _fix_parent(e, mod_ref=mod, status=status_txt):
                    status.value = "Buscando versión correcta…"
                    status.color = TEXT_DIM
                    try: status.update()
                    except Exception: pass

                    def do():
                        try:
                            version = app.modrinth_service.get_latest_version(
                                mod_ref.project_id,
                                mc_version=getattr(profile, "version_id", None),
                                loader=loader,
                            )
                            if not version:
                                def notfound():
                                    status.value = f"✗ No hay versión de {loader} para {mod_ref.title}"
                                    status.color = ACCENT_RED
                                    try: status.update()
                                    except Exception: pass
                                page.run_thread(notfound)
                                return

                            # Borrar la versión incorrecta antes de instalar la nueva
                            for filename in os.listdir(mods_dir):
                                full = os.path.join(mods_dir, filename)
                                if not os.path.isfile(full):
                                    continue
                                existing = app.modrinth_service.get_project_by_file_hash(full)
                                if existing and existing.project_id == mod_ref.project_id:
                                    os.remove(full)

                            app.modrinth_service.download_mod_version(version, mods_dir)

                            def done():
                                status.value = f"✓ {mod_ref.title} corregido ({version.version_number})"
                                status.color = GREEN
                                try: status.update()
                                except Exception: pass
                            page.run_thread(done)
                        except Exception as ex:
                            def err(ex=ex):
                                status.value = f"Error: {ex}"
                                status.color = ACCENT_RED
                                try: status.update()
                                except Exception: pass
                            page.run_thread(err)

                    threading.Thread(target=do, daemon=True).start()

                row = ft.Container(
                    bgcolor=CARD2_BG, border_radius=10,
                    padding=ft.padding.all(12),
                    content=ft.Column([
                        ft.Row([
                            _mini_icon(mod.icon_url, mod.title),
                            ft.Container(width=10),
                            ft.Column([
                                ft.Text(f"{mod.title} no es la versión de {loader}",
                                        color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
                                ft.Text(
                                    f"El {mod.title} instalado es para otro loader. "
                                    f"Por eso arrastra dependencias incorrectas.",
                                    color=TEXT_DIM, size=10,
                                ),
                            ], spacing=2, expand=True),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Container(height=8),
                        ft.Row([
                            ft.ElevatedButton(
                                f"Corregir {mod.title}",
                                icon=ft.icons.BUILD_ROUNDED,
                                bgcolor=GREEN, color=TEXT_INV,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=_fix_parent,
                            ),
                        ]),
                        ft.Container(height=4),
                        status_txt,
                    ], spacing=0),
                )
                missing_rows.controls.append(row)
                continue

            row = ft.Container(
                bgcolor=CARD2_BG, border_radius=10,
                padding=ft.padding.all(12),
                content=ft.Column([
                    ft.Row([
                        _mini_icon(mod.icon_url, mod.title),
                        ft.Container(width=8),
                        ft.Icon(ft.icons.ARROW_FORWARD_ROUNDED, size=14, color=TEXT_DIM),
                        ft.Container(width=8),
                        _mini_icon(dep_project.icon_url, dep_project.title),
                        ft.Container(width=10),
                        ft.Column([
                            ft.Text(f"{mod.title} necesita {dep_project.title}",
                                    color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
                            ft.Text(
                                "Versión instalada incorrecta"
                                if item.get("wrong_version")
                                else "Esta dependencia no está instalada",
                                color=TEXT_DIM, size=10,
                            ),
                        ], spacing=2, expand=True),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=8),
                    ft.Row([
                        ft.ElevatedButton(
                            f"Instalar {dep_project.title}",
                            icon=ft.icons.DOWNLOAD_ROUNDED,
                            bgcolor=GREEN, color=TEXT_INV,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=_install,
                        ),
                    ]),
                    ft.Container(height=4),
                    status_txt,
                ], spacing=0),
            )
            missing_rows.controls.append(row)

        try: missing_rows.update()
        except Exception: pass

    _rebuild_missing_rows()

    natives_rows = ft.Column(spacing=10)

    def _rebuild_natives_rows():
        natives_rows.controls.clear()
        if natives_status.get("ok", True):
            return

        missing_jars = natives_status.get("missing_jars", [])
        status_txt = ft.Text("", color=TEXT_DIM, size=10)

        def _repair(e, status=status_txt):
            status.value = "Reparando…"
            status.color = TEXT_DIM
            try: status.update()
            except Exception: pass

            def do():
                try:
                    count = app.version_manager.repair_natives(profile.version_id)
                    def done():
                        status.value = f"✓ {count} archivo(s) nativo(s) reparados"
                        status.color = GREEN
                        try: status.update()
                        except Exception: pass
                    page.run_thread(done)
                except Exception as ex:
                    def err(ex=ex):
                        status.value = f"Error: {ex}"
                        status.color = ACCENT_RED
                        try: status.update()
                        except Exception: pass
                    page.run_thread(err)

            threading.Thread(target=do, daemon=True).start()

        row = ft.Container(
            bgcolor=CARD2_BG, border_radius=10,
            padding=ft.padding.all(12),
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=36, height=36, border_radius=8,
                        bgcolor="#2d1a1a", alignment=ft.alignment.center,
                        content=ft.Icon(ft.icons.MEMORY_ROUNDED, size=18, color=ACCENT_RED),
                    ),
                    ft.Container(width=10),
                    ft.Column([
                        ft.Text("Archivos nativos incompletos",
                                color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
                        ft.Text(
                            f"Faltan {len(missing_jars)} librería(s) nativa(s) sin "
                            f"extraer: {', '.join(missing_jars[:3])}"
                            + ("…" if len(missing_jars) > 3 else "")
                            + ". Esto puede hacer que mods como Sodium crasheen al iniciar.",
                            color=TEXT_DIM, size=10,
                        ),
                    ], spacing=2, expand=True),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=8),
                ft.Row([
                    ft.ElevatedButton(
                        "Reparar instalación",
                        icon=ft.icons.BUILD_ROUNDED,
                        bgcolor=GREEN, color=TEXT_INV,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=_repair,
                    ),
                ]),
                ft.Container(height=4),
                status_txt,
            ], spacing=0),
        )
        natives_rows.controls.append(row)

        try: natives_rows.update()
        except Exception: pass

    _rebuild_natives_rows()

    def _retry(e):
        page.close(dlg)
        on_resolved()

    def _ignore(e):
        page.close(dlg)
        on_ignore()

    dlg = ft.AlertDialog(
        bgcolor=CARD_BG,
        shape=ft.RoundedRectangleBorder(radius=14),
        title=ft.Row([
            ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=ACCENT_RED, size=20),
            ft.Container(width=8),
            ft.Text("Mods incompatibles detectados", color=TEXT_PRI, size=15,
                    weight=ft.FontWeight.W_700),
        ], spacing=0, tight=True),
        content=ft.Container(
            width=460,
            content=ft.Column([
                ft.Text(
                    "Se encontraron problemas con tus mods instalados que "
                    "podrían impedir que el juego inicie.",
                    color=TEXT_SEC, size=12,
                ),
                ft.Container(height=12),
                ft.Column(
                    [
                        *([natives_rows] if not natives_status.get("ok", True) else []),
                        *([missing_rows] if missing_deps else []),
                        *([conflict_rows] if conflicts else []),
                    ],
                    scroll=ft.ScrollMode.AUTO, height=320, spacing=14,
                ),
            ], spacing=0, tight=True),
        ),
        actions=[
            ft.TextButton(
                "Lanzar de todas formas",
                style=ft.ButtonStyle(color=TEXT_DIM),
                on_click=_ignore,
            ),
            ft.ElevatedButton(
                "Volver a comprobar",
                bgcolor=GREEN, color=TEXT_INV,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                on_click=_retry,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )
    page.open(dlg)