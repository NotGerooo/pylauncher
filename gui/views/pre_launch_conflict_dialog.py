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
):
    missing_deps = missing_deps or []

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

            def _install(e, dep=dep_project, status=status_txt, btn_ref=None):
                status.value = "Instalando…"
                status.color = TEXT_DIM
                try: status.update()
                except Exception: pass

                def do():
                    try:
                        # 1er intento: con el loader detectado de la instancia
                        version = app.modrinth_service.get_latest_version(
                            dep.project_id,
                            mc_version=getattr(profile, "version_id", None),
                            loader=loader,
                        )
                        # Fallback: sin filtro de loader, por si el mod no
                        # etiqueta bien sus versiones en Modrinth
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

                        # Verificar que la versión realmente sirva para
                        # este loader (si loader es conocido)
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
                            ft.Text("Esta dependencia no está instalada",
                                    color=TEXT_DIM, size=10),
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