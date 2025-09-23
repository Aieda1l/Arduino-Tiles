import pygame
import config
import utils
from arduino_handler import ArduinoHandler
import serial.tools.list_ports

class SettingsScreen:
    def __init__(self, surface, arduino_handler):
        pygame.mixer.init()
        self.surface = surface
        self.font_path = config.FONT_PATH
        self.background = pygame.transform.scale(
            utils.load_image(config.BACKGROUND_IMG),
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        )
        self.arduino_handler = arduino_handler
        self.buttons = []
        self.keybind_input = None
        self.com_port_text = config.SERIAL_PORT
        self.com_port_active = False
        self.feedback_message = ""
        self.feedback_timer = 0
        self.keybinds = config.KEYBINDS.copy()
        self.create_buttons()

    def create_buttons(self):
        """Create buttons for the settings screen."""
        button_width = 200
        button_height = 40
        start_y = 150
        spacing = 10
        self.buttons = []
        # Keybind buttons
        for i in range(4):
            lane = f"lane_{i}"
            def set_keybind(l=lane):
                self.keybind_input = l
                self.com_port_active = False
                self.feedback_message = f"Press a key for {l.replace('_', ' ')}..."
                self.feedback_timer = 3.0
            key_name = "None"
            for key, lane_idx in self.keybinds.items():
                if lane_idx == i:
                    key_name = pygame.key.name(key)
                    break
            self.buttons.append(utils.Button(
                (config.SCREEN_WIDTH // 2 - button_width // 2, start_y + i * (button_height + spacing), button_width, button_height),
                f"{lane.replace('_', ' ')}: {key_name}", set_keybind
            ))
        # Rescan Arduino button
        def rescan_arduino():
            self.arduino_handler.close()
            config.SERIAL_PORT = self.com_port_text  # Update config.SERIAL_PORT
            self.arduino_handler = ArduinoHandler(port=self.com_port_text)
            self.feedback_message = "Arduino rescanned." if self.arduino_handler.connected else "Arduino not found."
            self.feedback_timer = 3.0
        self.buttons.append(utils.Button(
            (config.SCREEN_WIDTH // 2 - button_width // 2, start_y + 4 * (button_height + spacing), button_width, button_height),
            "Rescan Arduino", rescan_arduino
        ))
        # Back button
        self.buttons.append(utils.Button(
            (config.SCREEN_WIDTH - 120, config.SCREEN_HEIGHT - 80, 100, 50),
            "Back", lambda: {'action': 'back', 'arduino_handler': self.arduino_handler, 'keybinds': self.keybinds}
        ))

    def handle_events(self):
        """Handle user input events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return {'action': 'quit', 'arduino_handler': self.arduino_handler, 'keybinds': self.keybinds}
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for button in self.buttons:
                    result = button.handle_event(event)
                    if result:
                        return result
                com_rect = pygame.Rect(50, 400, config.SCREEN_WIDTH - 100, 40)
                if com_rect.collidepoint(event.pos):
                    self.com_port_active = True
                    self.keybind_input = None
                else:
                    self.com_port_active = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return {'action': 'back', 'arduino_handler': self.arduino_handler, 'keybinds': self.keybinds}
                if self.keybind_input:
                    lane_idx = int(self.keybind_input[-1])
                    self.keybinds = {k: v for k, v in self.keybinds.items() if v != lane_idx}
                    self.keybinds[event.key] = lane_idx
                    self.feedback_message = f"{self.keybind_input.replace('_', ' ')} set to {pygame.key.name(event.key)}"
                    self.feedback_timer = 3.0
                    self.keybind_input = None
                    self.update_buttons()
                elif self.com_port_active:
                    if event.key == pygame.K_BACKSPACE:
                        self.com_port_text = self.com_port_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        config.SERIAL_PORT = self.com_port_text  # Update config.SERIAL_PORT on Enter
                        self.arduino_handler.close()
                        self.arduino_handler = ArduinoHandler(port=self.com_port_text)
                        self.feedback_message = "COM port updated." if self.arduino_handler.connected else "Arduino not found."
                        self.feedback_timer = 3.0
                        self.com_port_active = False
                    else:
                        char = event.unicode
                        if char.isprintable():
                            self.com_port_text += char
        return self.check_button_actions()

    def update_buttons(self):
        """Update button text for keybinds."""
        for i in range(4):
            lane = f"lane_{i}"
            key_name = "None"
            for key, lane_idx in self.keybinds.items():
                if lane_idx == i:
                    key_name = pygame.key.name(key)
                    break
            self.buttons[i].text = f"{lane.replace('_', ' ')}: {key_name}"

    def check_button_actions(self):
        """Check if any button was clicked and return the result."""
        for button in self.buttons:
            if button.on_click and button.is_hovered and pygame.mouse.get_pressed()[0]:
                result = button.on_click()
                if result:
                    return result
        return None

    def update(self, dt):
        """Update button states and feedback timer."""
        for button in self.buttons:
            button.update()
        if self.feedback_timer > 0:
            self.feedback_timer -= dt
            if self.feedback_timer <= 0:
                self.feedback_message = ""

    def draw(self):
        """Draw the settings screen."""
        self.surface.blit(self.background, (0, 0))
        utils.draw_text(
            self.surface, "Settings", 60,
            config.SCREEN_WIDTH // 2, 50,
            config.WHITE, self.font_path, "center", shadow=True
        )
        com_rect = pygame.Rect(50, 400, config.SCREEN_WIDTH - 100, 40)
        utils.draw_rounded_rect(self.surface, com_rect, config.LIGHT_BLUE if self.com_port_active else config.GRAY, 10)
        com_text = self.com_port_text if self.com_port_text else ("Enter COM port..." if not self.com_port_active else "")
        utils.draw_text(
            self.surface, com_text, 24,
            com_rect.left + 10, com_rect.centery,
            config.WHITE if self.com_port_text else (180, 180, 180) if not self.com_port_active else config.WHITE,
            self.font_path, "midleft"
        )
        if self.feedback_message:
            utils.draw_text(
                self.surface, self.feedback_message, 24,
                config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT - 120,
                config.CYAN, self.font_path, "center", shadow=True
            )
        for button in self.buttons:
            button.draw(self.surface)
        pygame.display.flip()

    def run(self, clock):
        """Main loop for the settings screen."""
        running = True
        while running:
            dt = clock.tick(config.FPS) / 1000.0
            result = self.handle_events()
            if result:
                return result
            self.update(dt)
            self.draw()
        return {'action': 'quit', 'arduino_handler': self.arduino_handler, 'keybinds': self.keybinds}