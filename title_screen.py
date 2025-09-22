import pygame
import config
import utils

class TitleScreen:
    def __init__(self, surface):
        self.surface = surface
        self.font_path = config.FONT_PATH
        self.background = pygame.transform.scale(
            utils.load_image(config.BACKGROUND_IMG),
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        )
        self.buttons = []
        self.create_buttons()

    def create_buttons(self):
        """Create buttons for the title screen."""
        button_width = 200
        button_height = 60
        button_spacing = 20
        start_y = config.SCREEN_HEIGHT // 2
        self.buttons = [
            utils.Button(
                (config.SCREEN_WIDTH // 2 - button_width // 2, start_y, button_width, button_height),
                "Play", lambda: {'action': 'go_to_menu'}
            ),
            utils.Button(
                (config.SCREEN_WIDTH // 2 - button_width // 2, start_y + button_height + button_spacing, button_width, button_height),
                "Settings", lambda: {'action': 'go_to_settings'}
            ),
            utils.Button(
                (config.SCREEN_WIDTH // 2 - button_width // 2, start_y + 2 * (button_height + button_spacing), button_width, button_height),
                "Quit", lambda: {'action': 'quit'}
            )
        ]

    def handle_events(self):
        """Handle user input events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return {'action': 'quit'}
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for button in self.buttons:
                    button.handle_event(event)
        return self.check_button_actions()

    def check_button_actions(self):
        """Check if any button was clicked and return the result."""
        for button in self.buttons:
            if button.on_click and button.is_hovered and pygame.mouse.get_pressed()[0]:
                result = button.on_click()
                if result:
                    return result
        return None

    def update(self):
        """Update button states."""
        for button in self.buttons:
            button.update()

    def draw(self):
        """Draw the title screen."""
        self.surface.blit(self.background, (0, 0))
        utils.draw_text(
            self.surface, "Piano Tiles 2", 80,
            config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 4,
            config.WHITE, self.font_path, "center", shadow=True
        )
        for button in self.buttons:
            button.draw(self.surface)
        pygame.display.flip()

    def run(self, clock):
        """Main loop for the title screen."""
        running = True
        while running:
            result = self.handle_events()
            if result:
                return result
            self.update()
            self.draw()
            clock.tick(config.FPS)
        return {'action': 'quit'}

if __name__ == '__main__':
    import platform
    import asyncio

    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    pygame.display.set_caption("Title Screen Test")
    clock = pygame.time.Clock()
    title = TitleScreen(screen)

    async def main():
        result = title.run(clock)
        print(f"Action: {result}")
        pygame.quit()

    if platform.system() == "Emscripten":
        asyncio.ensure_future(main())
    else:
        asyncio.run(main())