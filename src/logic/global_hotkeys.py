import pyperclip
from pynput import mouse, keyboard
import threading
import re

class GlobalHotkeyListener:
    """
    Listens for global Shift + Left Click events to trigger region replacement.
    """
    def __init__(self, controller):
        self.controller = controller
        self.keyboard_controller = keyboard.Controller()
        self.shift_pressed = False
        
        # Start keyboard listener to track shift key
        self.kb_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.kb_listener.start()
        
        # Start mouse listener for clicks
        self.m_listener = mouse.Listener(on_click=self.on_click)
        self.m_listener.start()
        
        print("GlobalHotkeyListener: Initialized and listening (Shift + Left Click)")

    def on_press(self, key):
        if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
            self.shift_pressed = True

    def on_release(self, key):
        if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
            self.shift_pressed = False

    def on_click(self, x, y, button, pressed):
        if pressed and button == mouse.Button.left and self.shift_pressed:
            print("GlobalHotkeyListener: Shift + Left Click detected!")
            # Trigger replacement in a separate thread to avoid blocking the listener
            threading.Thread(target=self.handle_trigger, daemon=True).start()

    def handle_trigger(self):
        try:
            content = pyperclip.paste()
            if not content:
                print("GlobalHotkeyListener: Clipboard is empty.")
                return

            # Search for #region "name" in the clipboard content
            # It expects the clipboard content itself to contain the region definition
            # or at least the header to identify the name.
            match = re.search(r'#region\s+["\']?([^"\']+)["\']?', content)
            if match:
                region_name = match.group(1)
                print(f"GlobalHotkeyListener: Found region '{region_name}' in clipboard.")
                self.controller.replace_region_from_clipboard(region_name, content)
            else:
                print("GlobalHotkeyListener: No #region tag found in clipboard content.")
        except Exception as e:
            print(f"GlobalHotkeyListener: Error handling trigger: {e}")

    def stop(self):
        self.kb_listener.stop()
        self.m_listener.stop()
