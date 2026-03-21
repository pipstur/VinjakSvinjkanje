import pygame
import random
import sys
import time
import pandas as pd
import os
import json

# --- CONFIG ---
WIDTH, HEIGHT = 1000, 600
DISPLAY_WIDTH, DISPLAY_HEIGHT = 1920, 1080  # Upscaling resolution
SIDEBAR_WIDTH = 300
GAME_WIDTH = WIDTH - SIDEBAR_WIDTH
FPS = 60
VINJAK_FALL_SPEED = 3
POINTS_PER_VINJAK = 100
SPAWN_DELAY = 40  # frames
STAGE_PAUSE = 2  # sekunde
LEADERBOARD_FILE = "leaderboard.xlsx"

# --- INIT ---
pygame.init()
# Kreiraj buffer površinu za igricu (1000x600)
screen = pygame.Surface((WIDTH, HEIGHT))
# Kreiraj pravi display na 1080p u fullscreen modu
display = pygame.display.set_mode((DISPLAY_WIDTH, DISPLAY_HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Vinjak Igrica")
clock = pygame.time.Clock()

# --- COLORS ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
BROWN = (139, 69, 19)
YELLOW = (255, 255, 100)
GOLD = (255, 215, 0)
DARK_RED = (30, 0, 0)
SIDEBAR_BG = (40, 20, 20)

# --- FONTS ---
font = pygame.font.SysFont("garamond", 28)
big_font = pygame.font.SysFont("garamond", 64, bold=True)
small_font = pygame.font.SysFont("garamond", 22)
tiny_font = pygame.font.SysFont("garamond", 18)

# --- SPRITE LOADING ---
glass_img = pygame.image.load("slike/casa_pixel.png").convert_alpha()
glass_img = pygame.transform.scale(glass_img, (100, 100))

vinjak_folder = "slike/flase/"

cep_img = pygame.image.load("slike/vinjakceppixel2.png").convert_alpha()
cep_img = pygame.transform.scale(cep_img, (40, 40))

background_img = pygame.image.load("slike/pozadina.jpeg").convert()
background_img = pygame.transform.scale(background_img, (GAME_WIDTH, HEIGHT))

leaderboard_img = pygame.image.load("slike/leaderboard.jpeg").convert()
leaderboard_img = pygame.transform.scale(leaderboard_img, (WIDTH, HEIGHT))

main_img = pygame.image.load("slike/pozadina_main.jpeg").convert()
main_img = pygame.transform.scale(main_img, (WIDTH, HEIGHT))

game_over_img = pygame.image.load("slike/game_over.jpeg").convert()
game_over_img = pygame.transform.scale(game_over_img, (WIDTH, HEIGHT))

# --- DEDA SPRITES ---
deda_sprites = {
    "default": pygame.image.load("slike/deda/Sprite-default.png").convert_alpha(),
    "malo_pijan": pygame.image.load("slike/deda/Sprite-malopopio.png").convert_alpha(),
    "vise_pijan": pygame.image.load("slike/deda/Sprite-visepopio.png").convert_alpha(),
    "olesen": pygame.image.load("slike/deda/Sprite-olesen.png").convert_alpha(),
    "urnisan": pygame.image.load("slike/deda/Sprite-SKROZpijan1.png").convert_alpha(),
    "urnisan_razmislja": pygame.image.load("slike/deda/Sprite-SKROZpijan2.png").convert_alpha(),
    "drinking_1": pygame.image.load("slike/deda/Sprite-tekkrecedapije.png").convert_alpha(),
    "drinking_2": pygame.image.load("slike/deda/Sprite-dedadokpije.png").convert_alpha(),
    "grob": pygame.image.load("slike/deda/Sprite-grobkonacni1.png").convert_alpha(),
    "grob_animacija1": pygame.image.load("slike/deda/Sprite-grobkonacni1.png").convert_alpha(),
    "grob_animacija2": pygame.image.load("slike/deda/Sprite-grobkonacni2.png").convert_alpha(),
    "grob_animacija3": pygame.image.load("slike/deda/Sprite-grobkonacni3.png").convert_alpha(),
    "grob_animacija4": pygame.image.load("slike/deda/Sprite-grobkonacni4.png").convert_alpha(),
    "grob_animacija5": pygame.image.load("slike/deda/Sprite-grobkonacni5.png").convert_alpha(),
    "grob_animacija6": pygame.image.load("slike/deda/Sprite-grobkonacni6.png").convert_alpha(),
}

# Skaliraj sve
for key in deda_sprites:
    deda_sprites[key] = pygame.transform.scale(deda_sprites[key], (280, 280))


class Vinjak(pygame.sprite.Sprite):
    def __init__(self, speed, vinjak_images):
        super().__init__()
        self.image = random.choice(vinjak_images)
        self.rect = self.image.get_rect()
        self.rect.x = random.randint(0, GAME_WIDTH - self.rect.width)
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
        self.image = glass_img
        self.rect = self.image.get_rect(midbottom=(GAME_WIDTH // 2, HEIGHT - 20))

    def update(self):
        mouse_x, _ = pygame.mouse.get_pos()
        # Skaliraj mouse poziciju sa display-a na game screen
        scaled_mouse_x = int(mouse_x * WIDTH / DISPLAY_WIDTH)
        self.rect.centerx = max(50, min(GAME_WIDTH - 50, scaled_mouse_x))
        self.rect.x = max(0, min(GAME_WIDTH - self.rect.width, self.rect.x))


class DedaAnimator:
    """Upravljač za Dedine animacije i stanja"""

    def __init__(self):
        self.level = 0  # 0=default, 1=malo, 2=više, 3=olesen, 4-6=urnisan, 7+=grob
        self.is_drinking = False
        self.drink_timer = 0
        self.drink_duration = 30  # frames
        self.current_sprite = "default"
        self.animation_timer = 0  # Za animaciju urnisan stanja

        # Grob animacija - sekvenca kada je nivo >= 7
        self.grob_animation_frames = [
            "grob_animacija1",
            "grob_animacija2",
            "grob_animacija3",
            "grob_animacija4",
            "grob_animacija5",
            "grob_animacija6",
        ]
        self.grob_animation_index = 0

    def get_deda_stage(self) -> str:
        """Koja faza je deda na osnovu level-a"""
        if self.level == 0:
            return "default"
        elif self.level == 1:
            return "malo_pijan"
        elif self.level == 2:
            return "vise_pijan"
        elif self.level == 3:
            return "olesen"
        elif self.level >= 4 and self.level < 7:  # 4, 5, 6
            return "urnisan"
        else:  # level >= 7
            return "grob"

    def start_drinking(self):
        """Počni animaciju pijenja"""
        self.is_drinking = True
        self.drink_timer = 0

    def update(self):
        """Update animaciju pijenja i stanja"""
        # Uvek povećavaj animation_timer
        self.animation_timer += 1

        if self.is_drinking:
            self.drink_timer += 1

            # Ako je na grob nivou (>=7), prikaži grob animaciju
            if self.level >= 7:
                # Grob animacija kroz sve frame-ove
                self.grob_animation_index = (self.drink_timer // 5) % len(
                    self.grob_animation_frames
                )
                self.current_sprite = self.grob_animation_frames[self.grob_animation_index]
            # Na nivou 4-6, alternira između urnisan i urnisan_razmislja
            elif self.level >= 4:
                if (self.drink_timer // 6) % 2 == 0:
                    self.current_sprite = "urnisan"
                else:
                    self.current_sprite = "urnisan_razmislja"
            else:
                # Flash između drinking spritova za ostale nivoe
                if (self.drink_timer // 6) % 2 == 0:
                    self.current_sprite = "drinking_1"
                else:
                    self.current_sprite = "drinking_2"

            # Završi animaciju pijenja
            if self.drink_timer >= self.drink_duration:
                self.is_drinking = False
                # Vrati se na osnovni sprite
                self.current_sprite = self.get_deda_stage()
        else:
            # Kada ne pije, prikaži osnovni sprite
            self.current_sprite = self.get_deda_stage()

    def get_current_image(self):
        """Trenutna Dedina slika"""
        return deda_sprites[self.current_sprite]

    def draw(self, surface, x, y):
        """Nacrtaj dedinu na određenoj poziciji"""
        img = self.get_current_image()
        surface.blit(img, (x, y))


class Game:
    def __init__(self, stories_list, vinjak_images_list):
        self.all_sprites = pygame.sprite.Group()
        self.vinjaks = pygame.sprite.Group()
        self.player = Player()
        self.all_sprites.add(self.player)
        self.score = 0
        self.lives = 3
        self.last_level = 0  # Za praćenje kad se level promeni
        self.spawn_timer = 0
        self.running = True
        self.vinjak_speed = VINJAK_FALL_SPEED
        self.showing_story = False

        # Deda animator
        self.deda = DedaAnimator()

        # Priče i slike se sada prosleđuju kao parametri (učitane kasnije)
        self.story_queue = stories_list
        self.story_index = 0
        self.vinjak_images = (
            vinjak_images_list if vinjak_images_list else [pygame.Surface((40, 120))]
        )
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

    def check_level_up(self):
        """Proveri da li je dostigao novi nivo (svakih 2000 poena)"""
        current_level = self.score // 2000

        if current_level > self.last_level and not self.showing_story:
            self.last_level = current_level
            self.deda.level = current_level  # Dozvoli neograničene nivoe
            self.deda.current_sprite = self.deda.get_deda_stage()
            self.vinjak_speed *= 1.4
            self.showing_story = True

    def draw_sidebar(self):
        """Nacrtaj desni sidebar sa dedom, životima i rezultatom"""
        # Sidebar background
        sidebar_rect = pygame.Rect(GAME_WIDTH, 0, SIDEBAR_WIDTH, HEIGHT)
        pygame.draw.rect(screen, SIDEBAR_BG, sidebar_rect)
        pygame.draw.line(screen, GOLD, (GAME_WIDTH, 0), (GAME_WIDTH, HEIGHT), 3)

        # Deda u sidebar-u (gornji deo)
        deda_x = GAME_WIDTH + (SIDEBAR_WIDTH - 280) // 2
        deda_y = 5
        self.deda.draw(screen, deda_x, deda_y)

        # Informacije (donji deo)
        info_y = 310

        # Rezultat
        score_label = tiny_font.render("REZULTAT", True, GOLD)
        screen.blit(score_label, (GAME_WIDTH + 20, info_y))
        score_text = font.render(str(self.score), True, WHITE)
        screen.blit(score_text, (GAME_WIDTH + 20, info_y + 25))

        # Životi
        lives_label = tiny_font.render("ŽIVOTI", True, GOLD)
        screen.blit(lives_label, (GAME_WIDTH + 20, info_y + 70))

        lives_y = info_y + 95
        for i in range(self.lives):
            screen.blit(cep_img, (GAME_WIDTH + 20 + i * 35, lives_y))

        # Stanje (dedina faza)
        drunken_map = {
            0: "Trezan",
            1: "Malo pijan",
            2: "Većinom pijan",
            3: "Olešen",
            4: "Urnisan",
            5: "Urnisan",
            6: "Urnisan",
            7: "Grob",
        }

        state_level = min(self.deda.level, 7)  # Max prikazivanja je 7
        state_label = tiny_font.render("STANJE", True, GOLD)
        screen.blit(state_label, (GAME_WIDTH + 20, info_y + 170))
        state_text = small_font.render(drunken_map.get(state_level, "Grob"), True, YELLOW)
        screen.blit(state_text, (GAME_WIDTH + 20, info_y + 195))

    def update(self):
        self.spawn_timer += 1
        if self.spawn_timer >= self.next_spawn_delay:
            self.spawn_vinjak()
            self.spawn_timer = 0
            self.next_spawn_delay = random.randint(SPAWN_DELAY - 10, SPAWN_DELAY + 10)

        self.all_sprites.update()
        self.deda.update()

        # Collision detection
        player_top_rect = pygame.Rect(
            self.player.rect.x,
            self.player.rect.y,
            self.player.rect.width,
            self.player.rect.height // 3,
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

                    # ANIMACIJA PIJENJA NA SVAKOM VINJAKU
                    self.deda.start_drinking()

                    # PROVERI DA LI JE NOVI LEVEL
                    self.check_level_up()

    def draw(self):
        # Game area
        screen.blit(background_img, (0, 0))
        self.all_sprites.draw(screen)

        # Sidebar
        self.draw_sidebar()

        # UPSCALE na 1080p
        scaled = pygame.transform.scale(screen, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        display.blit(scaled, (0, 0))
        pygame.display.flip()

    def game_over(self):
        show_game_over(self.score)
        self.running = False

    def show_vinjak_story(self):
        """Prikaži sledeću priču iz queue-a sa scrollingom za duge priče"""
        # Ako smo iskoristili sve priče iz queue-a, nemoj prikazivati ništa
        if self.story_index >= len(self.story_queue) or not self.story_queue:
            self.showing_story = False
            return

        story = self.story_queue[self.story_index]
        self.story_index += 1

        # Pripremi sve linije priče
        # Tekst počinje na x=280, a završava pre nego što dođe do kraja
        # Dostupna širina je: GAME_WIDTH - 280 - 20 (desni margin)
        lines = wrap_text(story["story"], font, GAME_WIDTH - 300)

        # Izračunaj ukupnu visinu teksta
        line_height = 40
        total_text_height = len(lines) * line_height

        # Area gdje se prikazuje tekst (sa marginama)
        text_area_y = 100
        text_area_height = HEIGHT - 200

        # Scroll offset
        scroll_offset = 0
        max_scroll = max(0, total_text_height - text_area_height)

        showing = True
        while showing:
            screen.fill(DARK_RED)

            # Deda sa trenutnom fazom
            deda_img = self.deda.get_current_image()
            screen.blit(deda_img, (50, 150))

            # Priča sa scrollingom - prikaži samo vidljive linije
            y = text_area_y + 10 - scroll_offset
            for line in lines:
                # Prikaži linije čiji početak je u vidljivoj zoni
                if y < text_area_y + text_area_height and y + line_height > text_area_y:
                    text = font.render(line, True, WHITE)
                    screen.blit(text, (280, y))
                y += line_height

            # Autor
            author = small_font.render(f"- {story['name']}", True, YELLOW)
            screen.blit(author, (GAME_WIDTH - author.get_width() - 50, HEIGHT - 100))

            # Hint koji se prilagođava
            if max_scroll > 0:
                hint = small_font.render("↑/↓ Skroluj | SPACE/Enter - Dalje", True, GOLD)
            else:
                hint = small_font.render("SPACE/Enter - Dalje", True, GOLD)
            screen.blit(hint, (GAME_WIDTH // 2 - hint.get_width() // 2, HEIGHT - 60))

            # UPSCALE za story screen
            scaled = pygame.transform.scale(screen, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
            display.blit(scaled, (0, 0))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        scroll_offset = max(0, scroll_offset - line_height * 2)
                    elif event.key == pygame.K_DOWN:
                        scroll_offset = min(max_scroll, scroll_offset + line_height * 2)
                    elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        showing = False
                        self.showing_story = False
                if event.type == pygame.MOUSEBUTTONDOWN:
                    # Scroll sa mouse wheel (ako je dostupno)
                    if event.button == 4:  # Scroll up
                        scroll_offset = max(0, scroll_offset - line_height * 2)
                    elif event.button == 5:  # Scroll down
                        scroll_offset = min(max_scroll, scroll_offset + line_height * 2)

            clock.tick(FPS)


def load_stories():
    """Učitaj priče iz price.json i promeša"""
    try:
        with open("price.json", "r", encoding="utf-8") as f:
            all_stories = json.load(f)
        random.shuffle(all_stories)
        return all_stories[:10]  # Maks 10 priča
    except:
        print("Greška: price.json nije pronađen!")
        return []


def load_vinjak_images():
    """Učitaj sve slike flasa iz foldera"""
    vinjak_images = []
    try:
        for filename in os.listdir(vinjak_folder):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                img = pygame.image.load(os.path.join(vinjak_folder, filename)).convert_alpha()
                img = pygame.transform.scale(img, (40, 120))
                vinjak_images.append(img)
    except:
        print("Greška: slike/flase folder nije pronađen!")

    return vinjak_images if vinjak_images else [pygame.Surface((40, 120))]


def wrap_text(text, font, max_width):
    """Razbija tekst u više redova"""
    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
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

        overlay = pygame.Surface((WIDTH - 200, HEIGHT - 100), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (100, 50))

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

        # UPSCALE
        scaled = pygame.transform.scale(screen, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        display.blit(scaled, (0, 0))
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                return


# === UI SCREENS ===


def show_start_menu():
    """Start ekran"""
    while True:
        screen.blit(main_img, (0, 0))

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        screen.blit(overlay, (0, 0))

        title = big_font.render("Vinjak Igrica", True, GOLD)
        start_btn = font.render("[A] Ajmo pit Vinjaka", True, WHITE)
        lead_btn = font.render("[R] Rezultati", True, WHITE)
        quit_btn = font.render("[Q] Gotov sam s Vinjakom", True, YELLOW)

        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 120))
        screen.blit(start_btn, (WIDTH // 2 - start_btn.get_width() // 2, HEIGHT // 2))
        screen.blit(lead_btn, (WIDTH // 2 - lead_btn.get_width() // 2, HEIGHT // 2 + 60))
        screen.blit(quit_btn, (WIDTH // 2 - quit_btn.get_width() // 2, HEIGHT // 2 + 120))

        # UPSCALE
        scaled = pygame.transform.scale(screen, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        display.blit(scaled, (0, 0))
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
    """Game over ekran"""
    name = ""

    while True:
        screen.blit(game_over_img, (0, 0))

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
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

        # UPSCALE
        scaled = pygame.transform.scale(screen, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        display.blit(scaled, (0, 0))
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
            # UČITAJ PRIČE I SLIKE SAMO SADA
            print("Učitavam priče...")
            stories = load_stories()
            print("Učitavam slike flasa...")
            vinjak_images = load_vinjak_images()
            print("Igra počinje!")

            global game
            game = Game(stories, vinjak_images)
            while game.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    # ESC za izlazak iz fullscreena
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            pygame.quit()
                            sys.exit()

                # Ako je vreme za priču, prikaži je
                if game.showing_story:
                    game.show_vinjak_story()

                game.update()
                game.draw()
                clock.tick(FPS)


if __name__ == "__main__":
    main()
