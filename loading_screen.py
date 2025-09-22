import pygame
import config
import utils
import os
from main_menu import MainMenuScreen

class LoadingScreen:
    def __init__(self, surface):
        self.surface = surface
        self.font_path = config.FONT_PATH
        self.background = pygame.transform.scale(
            utils.load_image(config.BACKGROUND_IMG),
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        )
        self.loading_progress = 0
        self.total_files = len([f for f in os.listdir(config.SONGS_DIR) if f.endswith('.json')])
        self.menu_screen = None

    def load_songs(self):
        """Simulate loading songs by initializing MainMenuScreen."""
        self.menu_screen = MainMenuScreen(self.surface)
        self.loading_progress = 1.0

    def handle_events(self):
        """Handle user input events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return {'action': 'quit'}
        return None

    def update(self, dt):
        """Update loading progress."""
        if self.loading_progress < 1.0:
            self.loading_progress += dt * 0.5  # Simulate loading
        if self.loading_progress >= 1.0 and self.menu_screen:
            return {'action': 'go_to_menu', 'menu_screen': self.menu_screen}
        return None

    def draw(self):
        """Draw the loading screen."""
        self.surface.blit(self.background, (0, 0))
        utils.draw_text(
            self.surface, "Loading Songs...", 60,
            config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 - 50,
            config.WHITE, self.font_path, "center", shadow=True
        )
        progress_rect = pygame.Rect(50, config.SCREEN_HEIGHT // 2, config.SCREEN_WIDTH - 100, 40)
        utils.draw_rounded_rect(self.surface, progress_rect, config.GRAY, 10)
        filled_rect = progress_rect.copy()
        filled_rect.width = int(progress_rect.width * self.loading_progress)
        utils.draw_rounded_rect(self.surface, filled_rect, config.CYAN, 10)
        pygame.display.flip()

    def run(self, clock):
        """Main loop for the loading screen."""
        self.load_songs()  # Start loading
        running = True
        while running:
            dt = clock.tick(config.FPS) / 1000.0
            result = self.handle_events()
            if result:
                return result
            result = self.update(dt)
            if result:
                return result
            self.draw()
        return {'action': 'quit'}

if __name__ == '__main__':
    import platform
    import asyncio

    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    pygame.display.set_caption("Loading Screen Test")
    clock = pygame.time.Clock()
    loading = LoadingScreen(screen)

    async def main():
        result = loading.run(clock)
        print(f"Action: {result}")
        pygame.quit()

    if platform.system() == "Emscripten":
        asyncio.ensure_future(main())
    else:
        asyncio.run(main())