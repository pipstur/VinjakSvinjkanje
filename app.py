import pygame
import random
import sys
import time
import pandas as pd
import os
import json

# --- CONFIG ---
WIDTH, HEIGHT = 800, 600
FPS = 60
VINJAK_FALL_SPEED = 3
POINTS_PER_VINJAK = 100
SPAWN_DELAY = 40  # frames
STAGE_PAUSE = 2  # sekunde
LEADERBOARD_FILE = "leaderboard.xlsx"

# --- INIT ---
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Vinjak Svinjkanje")
clock = pygame.time.Clock()

# --- COLORS ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
BROWN = (139, 69, 19)
YELLOW = (255, 255, 100)
GOLD = (255, 215, 0)

# --- FONTS ---
font = pygame.font.SysFont("garamond", 28)
big_font = pygame.font.SysFont("garamond", 64, bold=True)
small_font = pygame.font.SysFont("garamond", 22)

# --- SPRITES (placeholder) ---
mouth_img = pygame.Surface((100, 70))
mouth_img.fill(RED)

vinjak_folder = "slike/flase/"


cep_img = pygame.image.load("slike/vinjakceppixel2.png").convert_alpha()
cep_img = pygame.transform.scale(cep_img, (40, 40))

background_img = pygame.image.load("slike/pozadina.png").convert()
background_img = pygame.transform.scale(background_img, (WIDTH, HEIGHT))

leaderboard_img = pygame.image.load("slike/leaderboard.png").convert()
leaderboard_img = pygame.transform.scale(leaderboard_img, (WIDTH, HEIGHT))

main_img = pygame.image.load("slike/pozadina_main.png").convert()
main_img = pygame.transform.scale(main_img, (WIDTH, HEIGHT))

game_over_img = pygame.image.load("slike/game_over.png").convert()
game_over_img = pygame.transform.scale(game_over_img, (WIDTH, HEIGHT))


class Vinjak(pygame.sprite.Sprite):
    def __init__(self, speed, vinjak_images):
        super().__init__()
        self.image = random.choice(vinjak_images)  # biramo nasumičnu sliku
        self.rect = self.image.get_rect()
        self.rect.x = random.randint(0, WIDTH - self.rect.width)
        self.rect.y = -self.rect.height
        self.speed = speed

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > HEIGHT:
            self.kill()
            game.lose_life()


class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = mouth_img
        self.rect = self.image.get_rect(midbottom=(WIDTH // 2, HEIGHT - 20))

    def update(self):
        mouse_x, _ = pygame.mouse.get_pos()
        self.rect.centerx = mouse_x
        self.rect.x = max(0, min(WIDTH - self.rect.width, self.rect.x))


class Game:
    def __init__(self):
        self.all_sprites = pygame.sprite.Group()
        self.vinjaks = pygame.sprite.Group()
        self.player = Player()
        self.all_sprites.add(self.player)
        self.score = 0
        self.lives = 3
        self.stage = 1
        self.drunkness = 0
        self.spawn_timer = 0
        self.running = True
        self.vinjak_speed = VINJAK_FALL_SPEED
        self.stage_paused = False
        self.stage_pause_start = None

        vinjak_images = []

        for filename in os.listdir(vinjak_folder):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                img = pygame.image.load(os.path.join(vinjak_folder, filename)).convert_alpha()
                img = pygame.transform.scale(img, (40, 120))
                vinjak_images.append(img)

        self.vinjak_images = vinjak_images
        with open("poruke.json", "r", encoding="utf-8") as f:
            self.stage_messages = json.load(f)
        self.next_spawn_delay = random.randint(SPAWN_DELAY - 10, SPAWN_DELAY + 10)

    def spawn_vinjak(self):
        speed_variation = random.uniform(-1, 1)
        vinjak_speed = max(1, self.vinjak_speed + speed_variation)
        v = Vinjak(vinjak_speed, self.vinjak_images)

        self.all_sprites.add(v)
        self.vinjaks.add(v)

    def lose_life(self):
        self.lives -= 1
        if self.lives <= 0:
            self.game_over()

    def get_stage_message(self, stage):
        for entry in self.stage_messages:
            if entry["stage"] == stage:
                return entry["message"]
        return "Bože pravde ti što spase."

    def update_stage(self):
        if self.score >= self.stage * 2000:
            self.stage += 1
            self.drunkness += 1
            self.vinjak_speed *= 1.4
            self.stage_paused = True
            self.show_vinjak_story(self.stage)
            self.stage_pause_start = time.time()

    def draw_lives(self):
        for i in range(self.lives):
            x = 20 + i * 50  # razmak između čepova
            y = 20
            screen.blit(cep_img, (x, y))

    def update(self):
        if self.stage_paused:
            if time.time() - self.stage_pause_start >= STAGE_PAUSE:
                self.stage_paused = False
            else:
                self.draw_stage_pause()
                return

        self.spawn_timer += 1
        if self.spawn_timer >= self.next_spawn_delay:
            self.spawn_vinjak()
            self.spawn_timer = 0
            # postavi sledeći spawn na random vrednost
            self.next_spawn_delay = random.randint(SPAWN_DELAY - 10, SPAWN_DELAY + 10)

        self.all_sprites.update()

        player_top_rect = pygame.Rect(
            self.player.rect.x,
            self.player.rect.y,
            self.player.rect.width,
            self.player.rect.height // 3,  # samo gornja trećina usta
        )

        for vinjak in self.vinjaks.copy():
            if vinjak.rect.colliderect(player_top_rect):

                bottom_hits_top = abs(vinjak.rect.bottom - player_top_rect.top) < 60

                center_aligned = abs(vinjak.rect.centerx - self.player.rect.centerx) < (
                    self.player.rect.width // 1.2
                )

                if bottom_hits_top and center_aligned:
                    vinjak.kill()
                    self.score += POINTS_PER_VINJAK
                    self.update_stage()

    def draw(self):
        screen.blit(background_img, (0, 0))
        self.all_sprites.draw(screen)

        score_text = font.render(f"{self.score}", True, WHITE)
        self.draw_lives()
        drunk_text = font.render(f"Deda pijan: {self.drunkness}", True, (180, 180, 255))
        screen.blit(score_text, (WIDTH - 200, 20))
        screen.blit(drunk_text, (WIDTH - 200, 60))

        pygame.display.flip()

    def draw_stage_pause(self):
        screen.fill((30, 0, 0))
        subtitle_text = self.get_stage_message(self.stage)
        subtitle = font.render(subtitle_text, True, WHITE)
        screen.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, HEIGHT // 2 + 20))
        pygame.display.flip()

    def game_over(self):
        show_game_over(self.score)
        self.running = False  # <-- Ključna promena!

    def show_vinjak_story(self, stage):
        with open("price.json", "r", encoding="utf-8") as f:
            stories = json.load(f)
        if stage <= len(stories):
            story = stories[stage - 1]
        else:
            story = random.choice(stories)

        showing = True
        while showing:
            screen.fill((40, 0, 0))
            lines = wrap_text(story["story"], font, WIDTH - 100)
            y = 150
            for line in lines:
                text = font.render(line, True, WHITE)
                screen.blit(text, (50, y))
                y += 40
            author = small_font.render(f"- {story['name']}", True, YELLOW)
            screen.blit(author, (WIDTH - author.get_width() - 50, HEIGHT - 100))
            hint = small_font.render("Pritisni bilo koji taster da nastaviš", True, GOLD)
            screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 60))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    showing = False


def wrap_text(text, font, max_width):
    """
    Razbija tekst u više redova tako da svaki red stane u zadatu širinu (max_width).
    Vraća listu stringova (linija).
    """
    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:
        # Proveri dužinu trenutne linije sa novom rečju
        test_line = current_line + word + " "
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            # Ako je linija preduga, zapamti je i započni novu
            lines.append(current_line.strip())
            current_line = word + " "
    if current_line:
        lines.append(current_line.strip())

    return lines


# === LEADERBOARD HANDLING ===


def save_score(name, score):
    data = pd.DataFrame([[name, score]], columns=["Name", "Score"])
    if os.path.exists(LEADERBOARD_FILE):
        df = pd.read_excel(LEADERBOARD_FILE)
        df = pd.concat([df, data], ignore_index=True)
    else:
        df = data
    df.sort_values("Score", ascending=False, inplace=True)
    df.to_excel(LEADERBOARD_FILE, index=False)


def show_leaderboard():
    """Prikazuje leaderboard ekran"""
    if os.path.exists(LEADERBOARD_FILE):
        df = pd.read_excel(LEADERBOARD_FILE)
        df.sort_values("Score", ascending=False, inplace=True)
        top = df.head(10)
    else:
        top = pd.DataFrame(columns=["Name", "Score"])

    while True:
        screen.blit(leaderboard_img, (0, 0))

        # --- Dodaj tamni overlay iza teksta ---
        overlay = pygame.Surface((WIDTH - 200, HEIGHT - 100), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # RGBA — 180 = poluprozirno
        screen.blit(overlay, (100, 50))  # centriraj okvirno, možeš po potrebi pomeriti

        # --- Tekst preko ---
        title = big_font.render("LEADERBOARD", True, GOLD)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 50))

        y = 120
        if top.empty:
            text = font.render("Nema još rezultata.", True, WHITE)
            screen.blit(text, (WIDTH // 2 - text.get_width() // 2, y))
        else:
            for i, row in top.iterrows():
                entry = font.render(f"{i+1}. {row['Name']} - {row['Score']}", True, WHITE)
                screen.blit(entry, (WIDTH // 2 - entry.get_width() // 2, y))
                y += 40

        back_text = small_font.render("Klikni bilo gde za povratak", True, YELLOW)
        screen.blit(back_text, (WIDTH // 2 - back_text.get_width() // 2, HEIGHT - 80))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                return


# === UI SCREENS ===


def show_start_menu():
    """Start ekran sa dugmadima"""
    while True:
        screen.blit(main_img, (0, 0))

        # --- Potamnjeni overlay (kao sloj ispod teksta) ---
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))  # RGBA: crno, 150 = providnost (0-255)
        screen.blit(overlay, (0, 0))
        # -----------------------------------------------

        # Tekst
        title = big_font.render("Vinjak svinjkanje", True, GOLD)
        start_btn = font.render("[A] Ajmo pit Vinjaka", True, WHITE)
        lead_btn = font.render("[R] Rezultati", True, WHITE)
        quit_btn = font.render("[Q] Gotov sam s Vinjakom", True, YELLOW)

        # Iscrtavanje teksta
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 120))
        screen.blit(start_btn, (WIDTH // 2 - start_btn.get_width() // 2, HEIGHT // 2))
        screen.blit(lead_btn, (WIDTH // 2 - lead_btn.get_width() // 2, HEIGHT // 2 + 60))
        screen.blit(quit_btn, (WIDTH // 2 - quit_btn.get_width() // 2, HEIGHT // 2 + 120))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_a:
                    return "start"
                if event.key == pygame.K_r:
                    return "leaderboard"
                if event.key == pygame.K_q:
                    pygame.quit()
                    sys.exit()


def show_game_over(score):
    """Game over ekran sa unosom imena i snimanjem rezultata"""
    name = ""

    while True:
        screen.blit(game_over_img, (0, 0))

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))  # RGBA: crno, 150 = providnost (0-255)
        screen.blit(overlay, (0, 0))

        title = big_font.render("Ti si svoje odvinjačio.", True, RED)
        score_text = font.render(f"Rezultat: {score}", True, WHITE)
        prompt = font.render("Upiši svoj nadimak:", True, YELLOW)
        name_text = big_font.render(name or "_", True, WHITE)
        save_hint = small_font.render("Enter - Sačuvaj | Backspace - Obriši", True, WHITE)

        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 150))
        screen.blit(score_text, (WIDTH // 2 - score_text.get_width() // 2, HEIGHT // 2 - 70))
        screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2))
        screen.blit(name_text, (WIDTH // 2 - name_text.get_width() // 2, HEIGHT // 2 + 60))
        screen.blit(save_hint, (WIDTH // 2 - save_hint.get_width() // 2, HEIGHT // 2 + 140))
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and name:
                    save_score(name, score)
                    return
                elif event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                elif len(name) < 16 and event.unicode.isprintable():
                    name += event.unicode


def main():
    while True:
        choice = show_start_menu()
        if choice == "leaderboard":
            show_leaderboard()
        elif choice == "start":
            global game
            game = Game()
            while game.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                game.update()
                game.draw()
                clock.tick(FPS)


if __name__ == "__main__":
    main()
