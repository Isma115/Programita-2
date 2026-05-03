import pyperclip
import threading
import re
import platform

# macOS compatibility and stability patch
IS_MAC = platform.system() == 'Darwin'
if IS_MAC:
    try:
        import Quartz
        import HIServices
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
        
        try:
            # On macOS, we don't use the keyboard listener as it causes 'trace trap' crashes
            # when certain keys like Caps Lock are pressed. Instead, we check the Shift state
            # on-demand during the mouse click event.
            if not IS_MAC:
                self.kb_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
                self.kb_listener.start()
            else:
                self._start_macos_paste_listener()
            
            # Start mouse listener for clicks
            self.m_listener = mouse.Listener(on_click=self.on_click)
            self.m_listener.start()
            
            if IS_MAC:
                print("GlobalHotkeyListener: Initialized (Mouse-only with Quartz-Shift check)")
            else:
                print("GlobalHotkeyListener: Initialized and listening (Global Shift + Left Click)")
                
        except Exception as e:
            print(f"GlobalHotkeyListener: Failed to initialize listeners: {e}")
            print("TIP: On macOS, this usually requires 'Accessibility' and 'Input Monitoring' permissions.")

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
                # 56: Left Shift, 60: Right Shift
                l_shift = Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateCombinedSessionState, 56)
                r_shift = Quartz.CGEventSourceKeyState(Quartz.kCGEventSourceStateCombinedSessionState, 60)
                return l_shift or r_shift
            except Exception as e:
                print(f"GlobalHotkeyListener: Quartz Shift check failed: {e}")
                return False
        return self.shift_pressed

    def on_click(self, x, y, button, pressed):
        if pressed and button == mouse.Button.left:
            if self._is_shift_pressed_now():
                print("GlobalHotkeyListener: Shift + Left Click detected!")
                # Trigger replacement in a separate thread to avoid blocking the listener
                threading.Thread(target=self.handle_trigger, daemon=True).start()

    def handle_trigger(self):
        from src.addons import Arbitrary_sus, chunk_sus, file_sus, structure_header_replace
        try:
            print("GlobalHotkeyListener: Shift + Left Click triggered. Running structure-aware smart paste.")
            # Schedule on main thread to be safe with UI
            if self.controller and self.controller.app and self.controller.app.root:
                def _dispatch():
                    def _log_arbitrary_skip(reason):
                        print(f"GlobalHotkeyListener: Arbitrary_sus no se disparó porque {reason}.")

                    handled = structure_header_replace.process_structure_header_replace(self.controller.app)
                    if handled:
                        _log_arbitrary_skip("structure_header_replace manejó el evento")
                    if not handled:
                        if chunk_sus._is_chunk_replace_enabled(self.controller.app):
                            handled = chunk_sus.process_chunk_replacements(self.controller.app)
                            if handled:
                                _log_arbitrary_skip("chunk_sus manejó el evento")
                        elif file_sus._is_file_replace_enabled(self.controller.app):
                            handled = file_sus.process_file_replacements(self.controller.app)
                            if handled:
                                _log_arbitrary_skip("file_sus manejó el evento")
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
            self._mac_paste_runloop = Quartz.CFRunLoopGetCurrent()
            Quartz.CFRunLoopAddSource(
                self._mac_paste_runloop,
                runloop_source,
                Quartz.kCFRunLoopCommonModes
            )
            Quartz.CGEventTapEnable(self._mac_paste_tap, True)
            Quartz.CFRunLoopRun()
        except Exception as e:
            print(f"GlobalHotkeyListener: Error iniciando listener de Cmd/Ctrl+V en macOS: {e}")

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
                Quartz.CFRunLoopStop(self._mac_paste_runloop)
            except Exception:
                pass
