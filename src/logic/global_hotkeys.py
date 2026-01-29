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
        self.kb_listener = None
        self.m_listener = None
        
        try:
            # On macOS, we don't use the keyboard listener as it causes 'trace trap' crashes
            # when certain keys like Caps Lock are pressed. Instead, we check the Shift state
            # on-demand during the mouse click event.
            if not IS_MAC:
                self.kb_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
                self.kb_listener.start()
            
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
        except:
            pass

    def on_release(self, key):
        try:
            if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
                self.shift_pressed = False
        except:
            pass

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
        from src.addons import Arbitrary_sus
        try:
            print("GlobalHotkeyListener: Shift + Left Click triggered. Delegating to Smart Paste.")
            # Schedule on main thread to be safe with UI
            if self.controller and self.controller.app and self.controller.app.root:
                 self.controller.app.root.after(0, lambda: Arbitrary_sus.process_smart_paste(self.controller.app))
        except Exception as e:
            print(f"GlobalHotkeyListener: Error handling trigger: {e}")

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
