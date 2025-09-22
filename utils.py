import pygame
import os
import config

def load_image(name, scale=1):
    """Loads an image, scales it, and converts it for performance."""
    try:
        image = pygame.image.load(name).convert_alpha()
        if scale != 1:
            size = image.get_size()
            image = pygame.transform.scale(image, (int(size[0] * scale), int(size[1] * scale)))
    except pygame.error as message:
        print(f"Cannot load image: {name}")
        raise SystemExit(message)
    return image


def draw_text(surface, text, size, x, y, color, font_path, align="center", shadow=False, shadow_color=config.BLACK, shadow_offset=(2, 2)):
    """Draws text on a surface with optional shadow and alignment."""
    try:
        # Use symbol font for special characters if the main font fails
        try:
            font = pygame.font.Font(font_path, size)
            text_surface = font.render(text, True, color)
        except pygame.error:
            font = pygame.font.Font(config.SYMBOL_FONT_PATH, size)
            text_surface = font.render(text, True, color)
    except IOError:
        font = pygame.font.Font(None, size) # Fallback to default font
        text_surface = font.render(text, True, color)

    text_rect = text_surface.get_rect()

    if align == "center":
        text_rect.center = (x, y)
    elif align == "topleft":
        text_rect.topleft = (x, y)
    elif align == "topright":
        text_rect.topright = (x, y)
    elif align == "midleft":
        text_rect.midleft = (x, y)

    if shadow:
        shadow_surface = font.render(text, True, shadow_color)
        # Position shadow relative to the final text position
        surface.blit(shadow_surface, (text_rect.x + shadow_offset[0], text_rect.y + shadow_offset[1]))

    surface.blit(text_surface, text_rect)
    return text_rect

def draw_rounded_rect(surface, rect, color, corner_radius):
    """Draws a rectangle with rounded corners."""
    if rect.width < 2 * corner_radius or rect.height < 2 * corner_radius:
        raise ValueError("Rectangle is too small for the given corner radius.")

    # Draw the main body
    pygame.draw.rect(surface, color, rect.inflate(-2 * corner_radius, 0))
    pygame.draw.rect(surface, color, rect.inflate(0, -2 * corner_radius))

    # Draw the rounded corners
    pygame.draw.circle(surface, color, (rect.left + corner_radius, rect.top + corner_radius), corner_radius)
    pygame.draw.circle(surface, color, (rect.right - corner_radius - 1, rect.top + corner_radius), corner_radius)
    pygame.draw.circle(surface, color, (rect.left + corner_radius, rect.bottom - corner_radius - 1), corner_radius)
    pygame.draw.circle(surface, color, (rect.right - corner_radius - 1, rect.bottom - corner_radius - 1), corner_radius)

class Button:
    """A clickable button with rounded corners and text."""
    def __init__(self, rect, text, on_click=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.on_click = on_click
        self.color = config.GRAY
        self.hover_color = (150, 150, 150)
        self.is_hovered = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos) and self.on_click:
                return self.on_click()
        return None

    def update(self):
        self.is_hovered = self.rect.collidepoint(pygame.mouse.get_pos())

    def draw(self, surface):
        color = self.hover_color if self.is_hovered else self.color
        draw_rounded_rect(surface, self.rect, color, 20)
        draw_text(surface, self.text, 30, self.rect.centerx, self.rect.centery, config.WHITE, config.FONT_PATH, shadow=True)


if __name__ == '__main__':
    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    pygame.display.set_caption("Utils Test")
    clock = pygame.time.Clock()

    # Load test assets
    try:
        background = load_image(config.BACKGROUND_IMG)
        background = pygame.transform.scale(background, (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        circle_light = load_image(config.CIRCLE_LIGHT_IMG, scale=0.5)
    except SystemExit as e:
        print(e)
        background = pygame.Surface(screen.get_size())
        background.fill(config.LIGHT_BLUE)
        circle_light = pygame.Surface((50, 50), pygame.SRCALPHA)
        pygame.draw.circle(circle_light, config.WHITE, (25, 25), 25)


    def test_button_click():
        print("Button clicked!")

    test_button = Button((140, 400, 200, 60), "Test Button", test_button_click)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            test_button.handle_event(event)

        test_button.update()

        screen.blit(background, (0, 0))
        screen.blit(circle_light, (50, 50))

        draw_text(screen, "Utils Test Screen", 50, config.SCREEN_WIDTH // 2, 100, config.WHITE, config.FONT_PATH, shadow=True)
        draw_text(screen, "This text has a shadow.", 30, config.SCREEN_WIDTH // 2, 200, config.CYAN, config.FONT_PATH, shadow=True)
        draw_text(screen, "This text is left-aligned.", 24, 20, 250, config.WHITE, config.FONT_PATH, align="midleft")

        draw_rounded_rect(screen, pygame.Rect(100, 300, 280, 80), (100, 100, 200), 25)
        test_button.draw(screen)

        pygame.display.flip()
        clock.tick(config.FPS)

    pygame.quit()
    print("Utils test finished.")