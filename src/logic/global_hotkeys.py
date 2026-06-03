import threading
import time
import unicodedata
import platform
import sys
import subprocess

# macOS compatibility and stability patch
IS_MAC = platform.system() == 'Darwin'
MAC_KEYCODE_C = 8
MAC_KEYCODE_V = 9
MAC_KEYCODE_CEDILLA_SPANISH_ISO = 42
if IS_MAC:
    try:
        import Quartz
        import HIServices
        try:
            import CoreFoundation
        except Exception:
            CoreFoundation = None
        try:
            # Force resolution of the lazy attribute
            _ = HIServices.AXIsProcessTrusted
        except (AttributeError, KeyError):
            # If resolution fails, try to import from ApplicationServices and patch it
            from ApplicationServices import AXIsProcessTrusted
            HIServices.AXIsProcessTrusted = AXIsProcessTrusted
    except Exception as e:
        print(f"GlobalHotkeyListener: macOS compatibility check skipped or failed: {e}")

from pynput import mouse, keyboard

class GlobalHotkeyListener:
    """
    Listens for global Shift + Left Click events to trigger region replacement.
    Also listens for Ctrl/Cmd + C + Ç to wrap clipboard code in #region/#endregion
    and auto-paste it into the active editor.
    On macOS, it uses Quartz for on-demand Shift state detection to avoid 
    instability with background keyboard listeners.
    """
    def __init__(self, controller):
        self.controller = controller
        self.startup_issues = []
        self._mac_permissions_checked = False
        
        # Check if hotkeys are enabled in config
        self.enabled = True
        if hasattr(self.controller, 'config_manager'):
            self.enabled = self.controller.config_manager.get_enable_hotkeys()
            
        if not self.enabled:
            print("GlobalHotkeyListener: Disabled via configuration.")
            self.kb_listener = None
            self.m_listener = None
            return

        if IS_MAC:
            self._check_macos_trust_and_warn()

        self.keyboard_controller = keyboard.Controller()
        self.shift_pressed = False
        self.ctrl_pressed = False
        self.cmd_pressed = False
        self.alt_pressed = False
        self.fn_pressed = False
        self.paste_hotkey_active = False
        self._region_wrap_hotkey_window_seconds = 1.2
        self._region_wrap_hotkey_armed_at = 0.0
        self._region_wrap_hotkey_modifier = None
        self._region_wrap_hotkey_active = False
        self._region_wrap_hotkey_lock = threading.Lock()
        self._region_wrap_hotkey_last_trigger_at = 0.0
        self._region_wrap_hotkey_debounce_seconds = 0.6
        self._suppress_paste_hotkey_until = 0.0
        self.kb_listener = None
        self.m_listener = None
        self._mac_paste_callback = None
        self._mac_paste_tap = None
        self._mac_paste_runloop = None
        self._mac_paste_thread = None
        self._mac_shift_click_callback = None
        self._mac_shift_click_tap = None
        self._mac_shift_click_runloop = None
        self._mac_shift_click_thread = None
        
        try:
            # On macOS, we don't use the keyboard listener as it causes 'trace trap' crashes
            # when certain keys like Caps Lock are pressed. Instead, we check the Shift state
            # on-demand during the mouse click event.
            if not IS_MAC:
                self.kb_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
                self.kb_listener.start()
            else:
                self._start_macos_paste_listener()
                self._start_macos_shift_click_listener()
            
            # Start mouse listener for clicks (non-macOS).
            # On macOS we use Quartz event taps for fully global behavior.
            if not IS_MAC:
                self.m_listener = mouse.Listener(on_click=self.on_click)
                self.m_listener.start()
            
            if IS_MAC:
                print("GlobalHotkeyListener: Initialized (Quartz event taps for Shift+Click, Cmd/Ctrl+V y Ctrl/Cmd+C+Ç)")
            else:
                print("GlobalHotkeyListener: Initialized and listening (Shift+Click y Ctrl/Cmd+C+Ç)")
                
        except Exception as e:
            self._record_startup_issue(f"Failed to initialize listeners: {e}")
            print("TIP: On macOS, this usually requires 'Accessibility' and 'Input Monitoring' permissions.")

    def _record_startup_issue(self, message):
        self.startup_issues.append(message)

    def has_startup_issues(self):
        return bool(self.startup_issues)

    def get_startup_issue_summary(self):
        if not self.startup_issues:
            return ""
        return "\n".join(f"- {issue}" for issue in self.startup_issues)

    def _check_macos_trust_and_warn(self):
        """Checks macOS Accessibility trust and requests it when possible."""
        if not IS_MAC:
            return
        if "HIServices" not in globals():
            print("GlobalHotkeyListener: HIServices no disponible para comprobar permisos de accesibilidad.")
            self._record_startup_issue(
                "No se pudo comprobar el permiso de Accesibilidad porque HIServices no está disponible."
            )
            return

        trusted = False
        try:
            trusted = bool(HIServices.AXIsProcessTrusted())
        except Exception:
            trusted = False

        if not trusted:
            try:
                options = {HIServices.kAXTrustedCheckOptionPrompt: True}
                trusted = bool(HIServices.AXIsProcessTrustedWithOptions(options))
            except Exception as exc:
                print(f"GlobalHotkeyListener: No se pudo solicitar permiso de accesibilidad automáticamente: {exc}")

        if trusted:
            self._mac_permissions_checked = True
            return

        print("GlobalHotkeyListener: La app no tiene permisos globales completos en macOS.")
        print(f"GlobalHotkeyListener: Ejecutable actual: {getattr(sys, 'executable', '(desconocido)')}")
        print("GlobalHotkeyListener: Abre Ajustes del Sistema > Privacidad y seguridad y concede permiso a esta app en:")
        print("GlobalHotkeyListener: 1) Accesibilidad")
        print("GlobalHotkeyListener: 2) Monitorización de entrada")
        print("GlobalHotkeyListener: Reinicia la app después de conceder permisos.")
        self._record_startup_issue(
            "La app no tiene permisos globales completos en macOS. "
            f"Ejecutable actual: {getattr(sys, 'executable', '(desconocido)')}"
        )

    def on_press(self, key):
        try:
            if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
                self.shift_pressed = True
                return
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self.ctrl_pressed = True
                return
            if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self.cmd_pressed = True
                return
            if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
                self.alt_pressed = True
                return
            fn_key = getattr(keyboard.Key, "fn", None)
            if fn_key is not None and key == fn_key:
                self.fn_pressed = True
                return
            if self._is_c_key(key) and (self.ctrl_pressed or self.cmd_pressed or self.alt_pressed or self.fn_pressed):
                self._arm_region_wrap_hotkey(
                    self._resolve_modifier_name(
                        self.ctrl_pressed,
                        self.cmd_pressed,
                        self.alt_pressed,
                        self.fn_pressed
                    )
                )
                return
            if self._is_cedilla_key(key) and (self.ctrl_pressed or self.cmd_pressed or self.alt_pressed or self.fn_pressed):
                modifier = self._resolve_modifier_name(
                    self.ctrl_pressed,
                    self.cmd_pressed,
                    self.alt_pressed,
                    self.fn_pressed
                )
                if self._can_trigger_region_wrap_hotkey(modifier):
                    self._dispatch_region_wrap_hotkey_async(modifier)
                return
            if self._is_v_key(key) and (self.ctrl_pressed or self.cmd_pressed):
                if not self.paste_hotkey_active:
                    self.paste_hotkey_active = True
                    self.handle_paste_hotkey()
        except:
            pass

    def on_release(self, key):
        try:
            if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
                self.shift_pressed = False
                return
            if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self.ctrl_pressed = False
                self.paste_hotkey_active = False
                self._clear_region_wrap_hotkey_if_no_modifier()
                return
            if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self.cmd_pressed = False
                self.paste_hotkey_active = False
                self._clear_region_wrap_hotkey_if_no_modifier()
                return
            if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
                self.alt_pressed = False
                self._clear_region_wrap_hotkey_if_no_modifier()
                return
            fn_key = getattr(keyboard.Key, "fn", None)
            if fn_key is not None and key == fn_key:
                self.fn_pressed = False
                self._clear_region_wrap_hotkey_if_no_modifier()
                return
            if self._is_v_key(key):
                self.paste_hotkey_active = False
        except:
            pass

    def _normalize_key_char(self, raw_char):
        if raw_char is None:
            return ""
        try:
            return unicodedata.normalize("NFC", str(raw_char)).lower()
        except Exception:
            return str(raw_char).lower()

    def _is_c_key(self, key):
        """Returns True when the pressed key corresponds to C/c."""
        try:
            char = getattr(key, "char", None)
            return self._normalize_key_char(char) == "c"
        except Exception:
            return False

    def _is_v_key(self, key):
        """Returns True when the pressed key corresponds to V/v."""
        try:
            char = getattr(key, "char", None)
            return self._normalize_key_char(char) == "v"
        except Exception:
            return False

    def _is_cedilla_key(self, key):
        """Returns True when the pressed key corresponds to Ç/ç."""
        try:
            char = getattr(key, "char", None)
            return self._normalize_key_char(char) == "ç"
        except Exception:
            return False

    def _resolve_modifier_name(self, has_ctrl, has_cmd, has_alt=False, has_fn=False):
        if has_ctrl:
            return "ctrl"
        if has_cmd:
            return "cmd"
        if has_alt:
            return "alt"
        if has_fn:
            return "fn"
        return "ctrl"

    def _arm_region_wrap_hotkey(self, modifier):
        self._region_wrap_hotkey_modifier = modifier
        self._region_wrap_hotkey_armed_at = time.monotonic()
        print(f"GlobalHotkeyListener: Hotkey C+Ç armado con modificador {modifier}.")

    def _clear_region_wrap_hotkey_if_no_modifier(self):
        if self.ctrl_pressed or self.cmd_pressed or self.alt_pressed or self.fn_pressed:
            return
        self._region_wrap_hotkey_modifier = None
        self._region_wrap_hotkey_armed_at = 0.0

    def _can_trigger_region_wrap_hotkey(self, modifier):
        if self._region_wrap_hotkey_active:
            return False
        if not self._region_wrap_hotkey_modifier:
            return False
        if self._region_wrap_hotkey_modifier != modifier:
            return False
        elapsed = time.monotonic() - self._region_wrap_hotkey_armed_at
        return elapsed <= self._region_wrap_hotkey_window_seconds

    def _is_shift_pressed_now(self):
        """Checks if Shift is currently pressed. Platform specific implementation."""
        if IS_MAC:
            try:
                flags = Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateCombinedSessionState)
                if flags & Quartz.kCGEventFlagMaskShift:
                    return True
                # Fallback: explicit keycodes (56 left shift, 60 right shift)
                l_shift = Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateCombinedSessionState, 56)
                r_shift = Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateCombinedSessionState, 60)
                return bool(l_shift or r_shift)
            except Exception as e:
                print(f"GlobalHotkeyListener: Quartz Shift check failed: {e}")
                return False
        return self.shift_pressed

    def _dispatch_trigger_async(self):
        threading.Thread(target=self.handle_trigger, daemon=True).start()

    def _dispatch_region_wrap_hotkey_async(self, modifier):
        threading.Thread(target=self.handle_region_wrap_hotkey, args=(modifier,), daemon=True).start()

    def on_click(self, x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            if self._is_shift_pressed_now():
                print("GlobalHotkeyListener: Shift + Left Click detected!")
                # Trigger replacement in a separate thread to avoid blocking the listener
                self._dispatch_trigger_async()

    def handle_trigger(self):
        from src.addons import Arbitrary_sus, chunk_sus, clever_sus, file_sus
        try:
            print("GlobalHotkeyListener: Shift + Left Click triggered. Running structure-aware smart paste.")
            # Schedule on main thread to be safe with UI
            if self.controller and self.controller.app and self.controller.app.root:
                def _dispatch():
                    def _log_arbitrary_skip(reason):
                        print(f"GlobalHotkeyListener: Arbitrary_sus no se disparó porque {reason}.")

                    handled = False
                    if chunk_sus._is_chunk_replace_enabled(self.controller.app):
                        handled = chunk_sus.process_chunk_replacements(self.controller.app)
                        if handled:
                            _log_arbitrary_skip("chunk_sus manejó el evento")
                    elif file_sus._is_file_replace_enabled(self.controller.app):
                        handled = file_sus.process_file_replacements(self.controller.app)
                        if handled:
                            _log_arbitrary_skip("file_sus manejó el evento")
                    if not handled:
                        if clever_sus.is_clever_injection_enabled(self.controller.app):
                            print("GlobalHotkeyListener: Inyección inteligente activa. Lanzando clever_sus.")
                            handled = clever_sus.process_smart_paste(self.controller.app)
                            if handled:
                                _log_arbitrary_skip("clever_sus manejó el evento")
                        if not handled:
                            print("GlobalHotkeyListener: Ningún manejador previo resolvió el evento. Lanzando Arbitrary_sus.")
                            Arbitrary_sus.process_smart_paste(self.controller.app)

                self.controller.app.root.after(0, _dispatch)
        except Exception as e:
            print(f"GlobalHotkeyListener: Error handling trigger: {e}")

    def handle_paste_hotkey(self):
        """Advances the dynamic clipboard flow after a real Ctrl/Cmd+V paste."""
        try:
            if time.monotonic() < self._suppress_paste_hotkey_until:
                return
            if not self.controller or not hasattr(self.controller, "has_dynamic_paste_active"):
                return
            if not self.controller.has_dynamic_paste_active():
                return
            self.controller.schedule_dynamic_paste_advance()
        except Exception as e:
            print(f"GlobalHotkeyListener: Error handling paste hotkey: {e}")

    def handle_region_wrap_hotkey(self, modifier):
        """Wraps clipboard code in #region/#endregion and pastes it automatically."""
        with self._region_wrap_hotkey_lock:
            if self._region_wrap_hotkey_active:
                return
            self._region_wrap_hotkey_active = True
        try:
            print(f"GlobalHotkeyListener: Detectado Ctrl/Cmd+C+Ç ({modifier}). Regionando y pegando.")
            # Let the real Ctrl/Cmd+C finish populating the clipboard.
            time.sleep(0.06)
            if not self.controller or not hasattr(self.controller, "wrap_clipboard_with_region_markers"):
                return
            success, message = self.controller.wrap_clipboard_with_region_markers()
            if not success:
                print(f"GlobalHotkeyListener: {message}")
                return
            self._wait_for_modifier_release(modifier, timeout_seconds=0.9)
            # Give the OS clipboard a short moment before sending paste.
            time.sleep(0.04)
            self._simulate_paste_shortcut(modifier)
        except Exception as e:
            print(f"GlobalHotkeyListener: Error handling Ctrl/Cmd+C+Ç hotkey: {e}")
        finally:
            self._region_wrap_hotkey_modifier = None
            self._region_wrap_hotkey_armed_at = 0.0
            self._region_wrap_hotkey_active = False

    def _simulate_paste_shortcut(self, modifier):
        """Sends a Ctrl/Cmd+V keystroke globally."""
        try:
            self._suppress_paste_hotkey_until = time.monotonic() + 0.5
            if IS_MAC:
                self._simulate_macos_paste_shortcut(modifier)
            else:
                modifier_key = keyboard.Key.ctrl
                if modifier == "cmd":
                    modifier_key = keyboard.Key.cmd
                elif modifier == "alt":
                    modifier_key = keyboard.Key.alt
                self.keyboard_controller.press(modifier_key)
                self.keyboard_controller.press("v")
                self.keyboard_controller.release("v")
                self.keyboard_controller.release(modifier_key)
        except Exception as e:
            print(f"GlobalHotkeyListener: Error simulando pegado automatico: {e}")

    def _wait_for_modifier_release(self, modifier, timeout_seconds=0.8):
        """Waits until the triggering modifier is released before auto-paste."""
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        while time.monotonic() < deadline:
            if IS_MAC and "Quartz" in globals():
                try:
                    flags = Quartz.CGEventSourceFlagsState(Quartz.kCGEventSourceStateCombinedSessionState)
                    if modifier == "cmd":
                        if not (flags & Quartz.kCGEventFlagMaskCommand):
                            return
                    elif modifier == "alt":
                        if not (flags & Quartz.kCGEventFlagMaskAlternate):
                            return
                    elif modifier == "fn":
                        if not (flags & Quartz.kCGEventFlagMaskSecondaryFn):
                            return
                    else:
                        if not (flags & Quartz.kCGEventFlagMaskControl):
                            return
                except Exception:
                    return
            else:
                if modifier == "cmd":
                    if not self.cmd_pressed:
                        return
                elif modifier == "alt":
                    if not self.alt_pressed:
                        return
                elif modifier == "fn":
                    if not self.fn_pressed:
                        return
                else:
                    if not self.ctrl_pressed:
                        return
            time.sleep(0.01)

    def _simulate_macos_paste_shortcut(self, modifier):
        """Sends paste on macOS using Quartz first, then osascript fallback."""
        if "Quartz" not in globals():
            raise RuntimeError("Quartz no disponible para simular Cmd/Ctrl+V.")

        # Most robust path on macOS: trigger Edit > Paste on the frontmost app.
        if self._simulate_macos_paste_via_menu():
            return

        keycode_v = MAC_KEYCODE_V
        keycode_modifier = 59  # left ctrl by default
        if modifier == "cmd":
            keycode_modifier = 55  # left cmd
        elif modifier == "alt":
            keycode_modifier = 58  # left option
        elif modifier == "fn":
            # Fn is not a reliable synthetic modifier for paste, use Ctrl as best fallback.
            keycode_modifier = 59

        event_src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        if event_src is None:
            raise RuntimeError("No se pudo crear CGEventSource para pegado automatico.")

        flag = Quartz.kCGEventFlagMaskControl
        if modifier == "cmd":
            flag = Quartz.kCGEventFlagMaskCommand
        elif modifier == "alt":
            flag = Quartz.kCGEventFlagMaskAlternate
        elif modifier == "fn":
            flag = Quartz.kCGEventFlagMaskControl

        def _post_with_tap(tap_location):
            mod_down = Quartz.CGEventCreateKeyboardEvent(event_src, keycode_modifier, True)
            v_down = Quartz.CGEventCreateKeyboardEvent(event_src, keycode_v, True)
            v_up = Quartz.CGEventCreateKeyboardEvent(event_src, keycode_v, False)
            mod_up = Quartz.CGEventCreateKeyboardEvent(event_src, keycode_modifier, False)
            Quartz.CGEventSetFlags(v_down, flag)
            Quartz.CGEventSetFlags(v_up, flag)
            for ev in (mod_down, v_down, v_up, mod_up):
                Quartz.CGEventPost(tap_location, ev)
                time.sleep(0.01)

        quartz_error = None
        for tap_location in (Quartz.kCGAnnotatedSessionEventTap, Quartz.kCGSessionEventTap, Quartz.kCGHIDEventTap):
            try:
                _post_with_tap(tap_location)
                print(f"GlobalHotkeyListener: Pegado enviado por Quartz (tap={tap_location}).")
                return
            except Exception as exc:
                quartz_error = exc

        print(f"GlobalHotkeyListener: Quartz no pudo enviar pegado ({quartz_error}). Intentando osascript.")
        self._simulate_macos_paste_with_osascript(modifier)

    def _simulate_macos_paste_via_menu(self):
        """Clicks Edit->Paste (or Editar->Pegar) in the frontmost app via System Events."""
        script = (
            'set didPaste to false\n'
            'tell application "System Events"\n'
            '  tell (first process whose frontmost is true)\n'
            '    try\n'
            '      click menu item "Paste" of menu "Edit" of menu bar 1\n'
            '      set didPaste to true\n'
            '    end try\n'
            '    if not didPaste then\n'
            '      try\n'
            '        click menu item "Pegar" of menu "Editar" of menu bar 1\n'
            '        set didPaste to true\n'
            '      end try\n'
            '    end if\n'
            '  end tell\n'
            'end tell\n'
            'return didPaste'
        )
        completed = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        if completed.returncode != 0:
            stderr_text = (completed.stderr or "").strip()
            if stderr_text:
                print(f"GlobalHotkeyListener: Pegar por menu fallo: {stderr_text}")
            return False
        result_text = (completed.stdout or "").strip().lower()
        if result_text == "true":
            print("GlobalHotkeyListener: Pegado enviado por menu (Editar > Pegar).")
            return True
        return False

    def _simulate_macos_paste_with_osascript(self, modifier):
        """Fallback paste on macOS using AppleScript System Events."""
        modifier_token = "control down"
        if modifier == "cmd":
            modifier_token = "command down"
        elif modifier == "alt":
            modifier_token = "option down"
        elif modifier == "fn":
            modifier_token = "control down"
        script = f'tell application "System Events" to keystroke "v" using {{{modifier_token}}}'
        completed = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        if completed.returncode != 0:
            stderr_text = (completed.stderr or "").strip()
            raise RuntimeError(f"osascript falló al pegar: {stderr_text}")
        print("GlobalHotkeyListener: Pegado enviado por osascript (Cmd+V).")

    def _get_macos_event_text(self, event):
        """Extracts typed text from a macOS keyboard event, when available."""
        if not IS_MAC or "Quartz" not in globals():
            return ""
        try:
            _length, text = Quartz.CGEventKeyboardGetUnicodeString(event, 8, None, None)
            return text or ""
        except Exception:
            return ""

    def _start_macos_paste_listener(self):
        """Starts a Quartz event tap to listen for Cmd/Ctrl+V on macOS."""
        if "Quartz" not in globals():
            print("GlobalHotkeyListener: Quartz no disponible para escuchar Cmd/Ctrl+V.")
            return

        self._mac_paste_thread = threading.Thread(
            target=self._run_macos_paste_listener,
            daemon=True
        )
        self._mac_paste_thread.start()

    def _start_macos_shift_click_listener(self):
        """Starts a Quartz event tap to listen for global Shift+LeftClick on macOS."""
        if "Quartz" not in globals():
            print("GlobalHotkeyListener: Quartz no disponible para escuchar Shift+Click.")
            return

        self._mac_shift_click_thread = threading.Thread(
            target=self._run_macos_shift_click_listener,
            daemon=True
        )
        self._mac_shift_click_thread.start()

    def _run_macos_paste_listener(self):
        """Runs the macOS key listener loop in a background thread."""
        try:
            event_mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)

            def _callback(_proxy, event_type, event, _refcon):
                try:
                    if event_type != Quartz.kCGEventKeyDown:
                        return event

                    is_autorepeat = Quartz.CGEventGetIntegerValueField(
                        event,
                        Quartz.kCGKeyboardEventAutorepeat
                    )
                    if is_autorepeat:
                        return event

                    keycode = Quartz.CGEventGetIntegerValueField(
                        event,
                        Quartz.kCGKeyboardEventKeycode
                    )
                    flags = Quartz.CGEventGetFlags(event)
                    has_command = bool(flags & Quartz.kCGEventFlagMaskCommand)
                    has_control = bool(flags & Quartz.kCGEventFlagMaskControl)
                    has_option = bool(flags & Quartz.kCGEventFlagMaskAlternate)
                    has_fn = bool(flags & Quartz.kCGEventFlagMaskSecondaryFn)
                    modifier_name = self._resolve_modifier_name(has_control, has_command, has_option, has_fn)

                    if keycode == MAC_KEYCODE_V and (has_command or has_control):
                        self.handle_paste_hotkey()
                        return event

                    key_text = self._get_macos_event_text(event)
                    normalized_text = self._normalize_key_char(key_text)

                    is_c = (keycode == MAC_KEYCODE_C) or (normalized_text == "c")
                    is_cedilla = (keycode == MAC_KEYCODE_CEDILLA_SPANISH_ISO) or (normalized_text == "ç")

                    if is_c and (has_command or has_control or has_option or has_fn):
                        self._arm_region_wrap_hotkey(modifier_name)
                        return event

                    if is_cedilla and (has_command or has_control or has_option or has_fn):
                        now = time.monotonic()
                        if now - self._region_wrap_hotkey_last_trigger_at < self._region_wrap_hotkey_debounce_seconds:
                            return event
                        if self._can_trigger_region_wrap_hotkey(modifier_name):
                            self._region_wrap_hotkey_last_trigger_at = now
                            self._dispatch_region_wrap_hotkey_async(modifier_name)
                            return event
                except Exception as e:
                    print(f"GlobalHotkeyListener: Error en callback de Cmd/Ctrl+V: {e}")

                return event

            self._mac_paste_callback = _callback
            self._mac_paste_tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                event_mask,
                self._mac_paste_callback,
                None
            )

            if not self._mac_paste_tap:
                print("GlobalHotkeyListener: No se pudo crear el event tap de teclado (Cmd/Ctrl+V y Ctrl/Cmd+C+Ç).")
                print("GlobalHotkeyListener: Sin ese permiso, el nuevo atajo de teclado no puede funcionar globalmente.")
                self._record_startup_issue(
                    "No se pudo crear el event tap de teclado para Cmd/Ctrl+V y Ctrl/Cmd+C+Ç."
                )
                return

            runloop_source = Quartz.CFMachPortCreateRunLoopSource(None, self._mac_paste_tap, 0)
            self._mac_paste_runloop = self._cf_call("CFRunLoopGetCurrent")
            self._cf_call(
                "CFRunLoopAddSource",
                self._mac_paste_runloop,
                runloop_source,
                self._cf_symbol("kCFRunLoopCommonModes"),
            )
            Quartz.CGEventTapEnable(self._mac_paste_tap, True)
            self._cf_call("CFRunLoopRun")
        except Exception as e:
            print(f"GlobalHotkeyListener: Error iniciando listener de Cmd/Ctrl+V en macOS: {e}")
            self._record_startup_issue(f"Error iniciando listener de Cmd/Ctrl+V en macOS: {e}")

    def _run_macos_shift_click_listener(self):
        """Runs a global Shift+LeftClick listener loop on macOS."""
        try:
            event_mask = Quartz.CGEventMaskBit(Quartz.kCGEventLeftMouseDown)

            def _callback(_proxy, event_type, event, _refcon):
                try:
                    if event_type != Quartz.kCGEventLeftMouseDown:
                        return event

                    flags = Quartz.CGEventGetFlags(event)
                    if flags & Quartz.kCGEventFlagMaskShift:
                        print("GlobalHotkeyListener: Shift + Left Click detected! (Quartz global tap)")
                        self._dispatch_trigger_async()
                except Exception as e:
                    print(f"GlobalHotkeyListener: Error en callback de Shift+Click: {e}")

                return event

            self._mac_shift_click_callback = _callback
            self._mac_shift_click_tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                event_mask,
                self._mac_shift_click_callback,
                None
            )

            if not self._mac_shift_click_tap:
                print("GlobalHotkeyListener: No se pudo crear el event tap de Shift+Click.")
                self._record_startup_issue("No se pudo crear el event tap de Shift+Click.")
                return

            runloop_source = Quartz.CFMachPortCreateRunLoopSource(None, self._mac_shift_click_tap, 0)
            self._mac_shift_click_runloop = self._cf_call("CFRunLoopGetCurrent")
            self._cf_call(
                "CFRunLoopAddSource",
                self._mac_shift_click_runloop,
                runloop_source,
                self._cf_symbol("kCFRunLoopCommonModes"),
            )
            Quartz.CGEventTapEnable(self._mac_shift_click_tap, True)
            self._cf_call("CFRunLoopRun")
        except Exception as e:
            print(f"GlobalHotkeyListener: Error iniciando listener de Shift+Click en macOS: {e}")
            self._record_startup_issue(f"Error iniciando listener de Shift+Click en macOS: {e}")

    def _cf_symbol(self, symbol_name):
        """Resolves CoreFoundation symbols from Quartz first, then CoreFoundation."""
        if not IS_MAC:
            raise AttributeError(symbol_name)

        for module_name in ("Quartz", "CoreFoundation"):
            module = globals().get(module_name)
            if module is None:
                continue
            try:
                return getattr(module, symbol_name)
            except Exception:
                continue
        raise AttributeError(symbol_name)

    def _cf_call(self, symbol_name, *args):
        """Calls a resolved CoreFoundation symbol with the provided args."""
        callable_symbol = self._cf_symbol(symbol_name)
        return callable_symbol(*args)

    def stop(self):
        if self.kb_listener:
            try:
                self.kb_listener.stop()
            except:
                pass
        if self.m_listener:
            try:
                self.m_listener.stop()
            except:
                pass
        if IS_MAC and "Quartz" in globals() and self._mac_paste_runloop is not None:
            try:
                self._cf_call("CFRunLoopStop", self._mac_paste_runloop)
            except Exception:
                pass
        if IS_MAC and "Quartz" in globals() and self._mac_shift_click_runloop is not None:
            try:
                self._cf_call("CFRunLoopStop", self._mac_shift_click_runloop)
            except Exception:
                pass
