import pygame as pg
import random, math, os, sys

WIDTH, HEIGHT = 800, 600
FPS = 60
TITLE = "Space Blaster — Pygame"

# -------------------- Helpers --------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# -------------------- Game Objects --------------------
class Bullet(pg.sprite.Sprite):
    def __init__(self, x, y, vy=-10, color=(255, 240, 200), radius=4):
        super().__init__()
        self.vy = vy
        self.color = color
        self.radius = radius
        self.image = pg.Surface((radius*2, radius*2), pg.SRCALPHA)
        pg.draw.circle(self.image, color, (radius, radius), radius)
        self.rect = self.image.get_rect(center=(x, y))

    def update(self):
        self.rect.y += self.vy
        if self.rect.bottom < 0 or self.rect.top > HEIGHT:
            self.kill()

class Enemy(pg.sprite.Sprite):
    def __init__(self, x=None, y=None, speed=None, hp=1, score=10):
        super().__init__()
        self.w = random.randint(24, 40)
        self.h = self.w
        self.image = pg.Surface((self.w, self.h), pg.SRCALPHA)
        # draw a simple diamond-shaped alien
        pts = [(self.w//2, 0), (self.w, self.h//2), (self.w//2, self.h), (0, self.h//2)]
        pg.draw.polygon(self.image, (200, 80, 200), pts)
        pg.draw.polygon(self.image, (255, 180, 255), pts, 2)
        x = x if x is not None else random.randint(20, WIDTH-20)
        y = y if y is not None else -random.randint(40, 120)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = speed if speed is not None else random.uniform(2, 4)
        self.hp = hp
        self.score = score
        self.timer = 0

    def update(self):
        self.timer += 1
        sway = math.sin(self.timer * 0.05) * 2
        self.rect.y += self.speed
        self.rect.x += sway
        if self.rect.top > HEIGHT + 40:
            self.kill()

class PowerUp(pg.sprite.Sprite):
    TYPES = ["heal", "shield", "rapid"]
    COLORS = {"heal": (80, 220, 120), "shield": (80, 180, 255), "rapid": (255, 200, 80)}

    def __init__(self, x, y, kind=None):
        super().__init__()
        self.kind = kind or random.choice(PowerUp.TYPES)
        self.image = pg.Surface((22, 22), pg.SRCALPHA)
        pg.draw.circle(self.image, PowerUp.COLORS[self.kind], (11, 11), 10)
        pg.draw.circle(self.image, (255, 255, 255), (11, 11), 10, 2)
        self.rect = self.image.get_rect(center=(x, y))
        self.vy = 2.5

    def update(self):
        self.rect.y += self.vy
        if self.rect.top > HEIGHT:
            self.kill()

class Particle(pg.sprite.Sprite):
    def __init__(self, pos, vel, life, color):
        super().__init__()
        self.image = pg.Surface((3, 3), pg.SRCALPHA)
        self.color = color
        self.image.fill(color)
        self.rect = self.image.get_rect(center=pos)
        self.vx, self.vy = vel
        self.life = life

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        self.life -= 1
        if self.life <= 0:
            self.kill()

class Player(pg.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pg.Surface((40, 46), pg.SRCALPHA)
        # draw a triangle ship
        pts = [(20, 0), (0, 46), (40, 46)]
        pg.draw.polygon(self.image, (120, 200, 255), pts)
        pg.draw.polygon(self.image, (255, 255, 255), pts, 2)
        self.rect = self.image.get_rect(center=(WIDTH//2, HEIGHT-70))
        self.speed = 6
        self.hp = 3
        self.shield = 0
        self.shoot_cd_default = 240  # ms
        self.shoot_cd = self.shoot_cd_default
        self.last_shot = 0

    def update(self, keys):
        dx = (keys[pg.K_RIGHT] or keys[pg.K_d]) - (keys[pg.K_LEFT] or keys[pg.K_a])
        dy = (keys[pg.K_DOWN] or keys[pg.K_s]) - (keys[pg.K_UP] or keys[pg.K_w])
        self.rect.x += int(dx * self.speed)
        self.rect.y += int(dy * (self.speed - 2))
        self.rect.clamp_ip(pg.Rect(0, 0, WIDTH, HEIGHT))

    def can_shoot(self):
        return pg.time.get_ticks() - self.last_shot >= self.shoot_cd

    def shoot(self, bullets):
        self.last_shot = pg.time.get_ticks()
        # two bullets slight spread
        bullets.add(Bullet(self.rect.centerx - 8, self.rect.top, vy=-11))
        bullets.add(Bullet(self.rect.centerx + 8, self.rect.top, vy=-11))

# -------------------- Game --------------------
class Game:
    def __init__(self):
        pg.init()
        pg.display.set_caption(TITLE)
        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        self.clock = pg.time.Clock()
        self.font = pg.font.SysFont("consolas", 22)
        self.bigfont = pg.font.SysFont("consolas", 44, bold=True)
        self.running = True
        self.reset()
        self.load_highscore()

    def load_highscore(self):
        self.highscore = 0
        try:
            with open("highscore.txt", "r", encoding="utf-8") as f:
                self.highscore = int(f.read().strip() or 0)
        except Exception:
            self.highscore = 0

    def save_highscore(self):
        try:
            with open("highscore.txt", "w", encoding="utf-8") as f:
                f.write(str(self.highscore))
        except Exception:
            pass

    def reset(self):
        self.player = Player()
        self.all = pg.sprite.Group(self.player)
        self.bullets = pg.sprite.Group()
        self.enemies = pg.sprite.Group()
        self.powerups = pg.sprite.Group()
        self.fx = pg.sprite.Group()
        self.score = 0
        self.level = 1
        self.spawn_timer = 0
        self.spawn_delay = 900  # ms
        self.paused = False
        self.state = "menu"  # menu, playing, gameover
        self.flash_timer = 0

    def spawn_enemy_wave(self):
        # difficulty scales with level
        count = clamp(2 + self.level // 2, 2, 8)
        for i in range(count):
            e = Enemy(speed=2 + self.level*0.15, hp=1 + self.level // 4, score=10 + 2*self.level)
            # jitter x
            e.rect.centerx += random.randint(-60, 60)
            self.enemies.add(e)
            self.all.add(e)

    def spawn_powerup(self, x, y):
        if random.random() < 0.18:  # 18% drop chance
            p = PowerUp(x, y)
            self.powerups.add(p)
            self.all.add(p)

    def explode(self, pos, color=(255, 200, 50), amount=18):
        for _ in range(amount):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(1, 4)
            vx, vy = math.cos(ang)*spd, math.sin(ang)*spd
            self.fx.add(Particle(pos, (vx, vy), life=random.randint(20, 40), color=color))

    def handle_powerup(self, kind):
        if kind == "heal":
            self.player.hp = clamp(self.player.hp + 1, 0, 5)
        elif kind == "shield":
            self.player.shield = clamp(self.player.shield + 2, 0, 6)
        elif kind == "rapid":
            self.player.shoot_cd = max(90, int(self.player.shoot_cd * 0.6))
            self.flash_timer = pg.time.get_ticks()

    def draw_hud(self):
        # hearts
        for i in range(self.player.hp):
            pg.draw.circle(self.screen, (255, 90, 110), (20 + i*20, 20), 8)
        # shield pips
        for i in range(self.player.shield):
            pg.draw.rect(self.screen, (120, 200, 255), (20 + i*12, 34, 10, 6))
        # score/level
        txt = self.font.render(f"Score {self.score}  |  Lvl {self.level}  |  Best {self.highscore}", True, (230,230,230))
        self.screen.blit(txt, (WIDTH - txt.get_width() - 12, 10))

    def draw_center_text(self, text, sub=None):
        t = self.bigfont.render(text, True, (255,255,255))
        self.screen.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT//2 - 60))
        if sub:
            s = self.font.render(sub, True, (220,220,220))
            self.screen.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT//2 + 4))

    def mainloop(self):
        while self.running:
            dt = self.clock.tick(FPS)
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.running = False
                if event.type == pg.KEYDOWN:
                    if self.state == "menu" and event.key in (pg.K_SPACE, pg.K_RETURN):
                        self.state = "playing"
                    elif self.state == "gameover" and event.key == pg.K_r:
                        self.reset(); self.state = "playing"
                    elif event.key == pg.K_p and self.state == "playing":
                        self.paused = not self.paused

            self.screen.fill((10, 12, 18))

            if self.state == "menu":
                self.draw_center_text("SPACE BLASTER", "Enter/Space: Start  |  ESC: Quit  |  Pfeile/WASD + SPACE")
                pg.display.flip()
                if pg.key.get_pressed()[pg.K_ESCAPE]:
                    self.running = False
                continue

            if self.state == "playing":
                if self.paused:
                    self.draw_center_text("PAUSE", "P: Weiter")
                    pg.display.flip()
                    continue

                keys = pg.key.get_pressed()
                self.player.update(keys)

                if (keys[pg.K_SPACE] or keys[pg.K_RETURN]) and self.player.can_shoot():
                    self.player.shoot(self.bullets)
                    self.all.add(self.bullets)

                # Spawning
                now = pg.time.get_ticks()
                if now - self.spawn_timer > self.spawn_delay:
                    self.spawn_enemy_wave()
                    self.spawn_timer = now
                    # speed up over time
                    self.level += 1
                    self.spawn_delay = max(400, int(self.spawn_delay * 0.96))

                # Updates
                self.enemies.update()
                self.bullets.update()
                self.powerups.update()
                self.fx.update()

                # Collisions: bullets ↔ enemies
                hits = pg.sprite.groupcollide(self.enemies, self.bullets, False, True)
                for enemy, bullets in hits.items():
                    for _ in bullets:
                        enemy.hp -= 1
                        self.explode(enemy.rect.center, (255, 220, 120), amount=6)
                        if enemy.hp <= 0:
                            self.score += enemy.score
                            self.spawn_powerup(enemy.rect.centerx, enemy.rect.centery)
                            self.explode(enemy.rect.center, (255, 140, 220), amount=18)
                            enemy.kill()

                # Collisions: player ↔ enemies
                pe = pg.sprite.spritecollide(self.player, self.enemies, True, pg.sprite.collide_rect)
                for _ in pe:
                    if self.player.shield > 0:
                        self.player.shield -= 1
                    else:
                        self.player.hp -= 1
                    self.explode(self.player.rect.center, (120, 200, 255), amount=14)
                    if self.player.hp <= 0:
                        self.state = "gameover"
                        self.highscore = max(self.highscore, self.score)
                        self.save_highscore()

                # Collisions: player ↔ powerups
                pp = pg.sprite.spritecollide(self.player, self.powerups, True, pg.sprite.collide_rect)
                for p in pp:
                    self.handle_powerup(p.kind)

                # Draw all
                # subtle rapid-fire flash
                if pg.time.get_ticks() - self.flash_timer < 300:
                    self.screen.fill((30,30,15))
                self.all.draw(self.screen)
                self.fx.draw(self.screen)
                self.draw_hud()

            elif self.state == "gameover":
                self.draw_center_text("GAME OVER", f"Score: {self.score}  |  Best: {self.highscore}  —  R: Restart  ESC: Quit")
                if pg.key.get_pressed()[pg.K_ESCAPE]:
                    self.running = False

            pg.display.flip()

        pg.quit()

if __name__ == "__main__":
    Game().mainloop()
