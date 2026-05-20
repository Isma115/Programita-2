import pyperclip
import threading
import re
import platform
import sys

# macOS compatibility and stability patch
IS_MAC = platform.system() == 'Darwin'
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
    On macOS, it uses Quartz for on-demand Shift state detection to avoid 
    instability with background keyboard listeners.
    """
    def __init__(self, controller):
        self.controller = controller
        
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
        self.paste_hotkey_active = False
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
                print("GlobalHotkeyListener: Initialized (Quartz event taps for global Shift+Click and Cmd/Ctrl+V)")
            else:
                print("GlobalHotkeyListener: Initialized and listening (Global Shift + Left Click)")
                
        except Exception as e:
            print(f"GlobalHotkeyListener: Failed to initialize listeners: {e}")
            print("TIP: On macOS, this usually requires 'Accessibility' and 'Input Monitoring' permissions.")

    def _check_macos_trust_and_warn(self):
        """Checks macOS Accessibility trust and requests it when possible."""
        if not IS_MAC:
            return
        if "HIServices" not in globals():
            print("GlobalHotkeyListener: HIServices no disponible para comprobar permisos de accesibilidad.")
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
            return

        print("GlobalHotkeyListener: La app no tiene permisos globales completos en macOS.")
        print(f"GlobalHotkeyListener: Ejecutable actual: {getattr(sys, 'executable', '(desconocido)')}")
        print("GlobalHotkeyListener: Abre Ajustes del Sistema > Privacidad y seguridad y concede permiso a esta app en:")
        print("GlobalHotkeyListener: 1) Accesibilidad")
        print("GlobalHotkeyListener: 2) Monitorización de entrada")
        print("GlobalHotkeyListener: Reinicia la app después de conceder permisos.")

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
                return
            if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                self.cmd_pressed = False
                self.paste_hotkey_active = False
                return
            if self._is_v_key(key):
                self.paste_hotkey_active = False
        except:
            pass

    def _is_v_key(self, key):
        """Returns True when the pressed key corresponds to V/v."""
        try:
            char = getattr(key, "char", None)
            return bool(char) and char.lower() == "v"
        except Exception:
            return False

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
            if not self.controller or not hasattr(self.controller, "has_dynamic_paste_active"):
                return
            if not self.controller.has_dynamic_paste_active():
                return
            self.controller.schedule_dynamic_paste_advance()
        except Exception as e:
            print(f"GlobalHotkeyListener: Error handling paste hotkey: {e}")

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

                    if keycode == 9 and (has_command or has_control):
                        self.handle_paste_hotkey()
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
                print("GlobalHotkeyListener: No se pudo crear el event tap de Cmd/Ctrl+V.")
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
