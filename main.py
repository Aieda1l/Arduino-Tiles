import pygame
import config
import utils
from game import GameScreen
from title_screen import TitleScreen
from main_menu import MainMenuScreen
from settings_screen import SettingsScreen
from loading_screen import LoadingScreen
from arduino_handler import ArduinoHandler

class GameApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption(config.GAME_NAME)
        self.clock = pygame.time.Clock()
        self.arduino = ArduinoHandler()
        self.state = 'loading'
        self.loading_screen = LoadingScreen(self.screen)
        self.title_screen = TitleScreen(self.screen)
        self.menu_screen = None
        self.game_screen = GameScreen(self.screen)
        self.settings_screen = SettingsScreen(self.screen, self.arduino)

    def run(self):
        """Main application loop."""
        running = True
        while running:
            if self.state == 'loading':
                result = self.loading_screen.run(self.clock)
                if result:
                    if result['action'] == 'quit':
                        running = False
                    elif result['action'] == 'go_to_menu':
                        self.menu_screen = result['menu_screen']
                        self.state = 'title'
            elif self.state == 'title':
                result = self.title_screen.run(self.clock)
                if result:
                    if result['action'] == 'quit':
                        running = False
                    elif result['action'] == 'go_to_menu':
                        self.state = 'menu'
                    elif result['action'] == 'go_to_settings':
                        self.state = 'settings'
            elif self.state == 'menu':
                result = self.menu_screen.run(self.clock)
                if result:
                    if result['action'] == 'quit':
                        running = False
                    elif result['action'] == 'back':
                        self.state = 'title'
                    elif result['action'] == 'play_song':
                        self.game_screen.load_song(result['filename'])
                        self.state = 'game'
            elif self.state == 'game':
                self.game_screen.run(self.clock)
                self.state = 'menu'
            elif self.state == 'settings':
                result = self.settings_screen.run(self.clock)
                if result:
                    if result['action'] == 'quit':
                        running = False
                    elif result['action'] == 'back':
                        self.state = 'title'
                        config.KEYBINDS.update(self.settings_screen.keybinds)
                        if config.SERIAL_PORT != self.settings_screen.com_port_text:
                            config.SERIAL_PORT = self.settings_screen.com_port_text
                            self.arduino.close()
                            self.arduino = ArduinoHandler(port=config.SERIAL_PORT)

        self.arduino.close()
        pygame.quit()

if __name__ == '__main__':
    import platform
    import asyncio

    async def main():
        app = GameApp()
        app.run()

    if platform.system() == "Emscripten":
        asyncio.ensure_future(main())
    else:
        asyncio.run(main())