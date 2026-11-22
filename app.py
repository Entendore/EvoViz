import pygame
import random
import math
import colorsys
import json
import os

# --- Configuration ---
WIDTH, HEIGHT = 800, 600
FPS = 60
TILE_SIZE = 4

# Colors
BLACK = (15, 15, 20)
GRAPH_BG = (25, 25, 30)
UI_BG = (10, 10, 15, 200)

# Simulation Parameters
INITIAL_POPULATION = 80
MAX_POPULATION = 500
STARTING_ENERGY = 150
SPECIATION_THRESHOLD = 1.5
GRID_CELL_SIZE = 50

# Weather Regions
REGION_W, REGION_H = 200, 200
REGIONS_X, REGIONS_Y = WIDTH // REGION_W, HEIGHT // REGION_H

# Day/Night
DAY_LENGTH = 1200  # frames for full cycle

# --- Biome Definitions ---
# (color, food_mult, meta_mult, passable, water)
BIOMES = {
    'deep_water': ((20, 40, 80), 0.0, 1.0, False, True),
    'water':      ((40, 80, 120), 0.2, 1.0, True, True),
    'sand':       ((220, 200, 140), 0.1, 1.1, True, False),
    'grass':      ((60, 140, 60), 1.0, 1.0, True, False),
    'forest':     ((30, 80, 40), 0.6, 1.1, True, False),
    'desert':     ((200, 180, 80), 0.05, 1.4, True, False),
    'mountain':   ((120, 120, 120), 0.0, 1.3, True, False),
    'snow':       ((200, 220, 230), 0.1, 1.3, True, False)
}

# --- Global Lineage Tracking ---
LINEAGE_COLORS = {0: (200, 200, 200)}
LINEAGE_BIRTH_TIMES = {0: 0}
LINEAGE_PARENTS = {0: None}  # NEW: track parent lineage for tree
NEXT_LINEAGE_ID = 1
TOTAL_SPECIATION_EVENTS = 0

def get_new_lineage_color():
    h = random.random()
    s = 0.7 + random.random() * 0.3
    v = 0.7 + random.random() * 0.3
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))

def blend_color(color, bg, stealth):
    r = int(color[0] * (1 - stealth) + bg[0] * stealth)
    g = int(color[1] * (1 - stealth) + bg[1] * stealth)
    b = int(color[2] * (1 - stealth) + bg[2] * stealth)
    return (r, g, b)

def desaturate(color, amount):
    """Reduce saturation for aged creatures."""
    gray = sum(color) // 3
    return tuple(int(c * (1 - amount) + gray * amount) for c in color)

def draw_shape(surface, color, x, y, size, shape_type, angle):
    if shape_type == 1:
        pygame.draw.circle(surface, color, (int(x), int(y)), int(size))
    elif shape_type == 2:
        p1 = (x + math.cos(angle) * size * 1.5, y + math.sin(angle) * size * 1.5)
        p2 = (x + math.cos(angle + 2.5) * size, y + math.sin(angle + 2.5) * size)
        p3 = (x + math.cos(angle - 2.5) * size, y + math.sin(angle - 2.5) * size)
        pygame.draw.polygon(surface, color, [p1, p2, p3])
    elif shape_type == 3:
        rect = pygame.Rect(0, 0, size * 1.5, size * 1.5)
        rect.center = (x, y)
        pygame.draw.rect(surface, color, rect)
    elif shape_type == 4:
        points = []
        for i in range(5):
            a = angle + i * (2 * math.pi / 5)
            points.append((x + math.cos(a) * size * 1.2, y + math.sin(a) * size * 1.2))
        pygame.draw.polygon(surface, color, points)

# --- Expert Map Generation ---
def generate_fractal_noise(width, height, scale, octaves):
    noise_map = [[0.0 for _ in range(height)] for _ in range(width)]
    max_amplitude = 0.0
    amplitude = 1.0
    frequency = scale
    for _ in range(octaves):
        grid_w, grid_h = int(width / frequency) + 2, int(height / frequency) + 2
        grid = [[random.random() for _ in range(grid_h)] for _ in range(grid_w)]
        for x in range(width):
            for y in range(height):
                gx, gy = x / frequency, y / frequency
                x0, y0 = int(gx), int(gy)
                dx, dy = gx - x0, gy - y0
                sx = dx * dx * (3 - 2 * dx)
                sy = dy * dy * (3 - 2 * dy)
                top = grid[x0][y0] * (1 - sx) + grid[x0+1][y0] * sx
                bottom = grid[x0][y0+1] * (1 - sx) + grid[x0+1][y0+1] * sx
                noise_map[x][y] += (top * (1 - sy) + bottom * sy) * amplitude
        max_amplitude += amplitude
        amplitude *= 0.5
        frequency *= 2
    for x in range(width):
        for y in range(height):
            noise_map[x][y] /= max_amplitude
    return noise_map

class GameMap:
    def __init__(self, w, h, tile_size):
        self.w = w
        self.h = h
        self.tile_size = tile_size
        self.tiles_w = w // tile_size
        self.tiles_h = h // tile_size
        self.elevation = generate_fractal_noise(self.tiles_w, self.tiles_h, 8, 4)
        self.moisture = generate_fractal_noise(self.tiles_w, self.tiles_h, 6, 4)
        self.biome_grid = [[None for _ in range(self.tiles_h)] for _ in range(self.tiles_w)]
        self.surface = pygame.Surface((w, h))
        self.generate_biomes()

    def generate_biomes(self):
        for x in range(self.tiles_w):
            for y in range(self.tiles_h):
                e = self.elevation[x][y]
                m = self.moisture[x][y]
                if e < 0.3: biome = 'deep_water'
                elif e < 0.4: biome = 'water'
                elif e < 0.45: biome = 'sand'
                elif e < 0.75:
                    if m < 0.2: biome = 'desert'
                    elif m < 0.5: biome = 'grass'
                    elif m < 0.8: biome = 'forest'
                    else: biome = 'grass'
                else:
                    if m < 0.5: biome = 'mountain'
                    else: biome = 'snow'
                self.biome_grid[x][y] = biome
                color = BIOMES[biome][0]
                rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
                pygame.draw.rect(self.surface, color, rect)

    def get_biome_at(self, x, y):
        tx, ty = int(x // self.tile_size), int(y // self.tile_size)
        if 0 <= tx < self.tiles_w and 0 <= ty < self.tiles_h:
            return self.biome_grid[tx][ty]
        return 'water'

    def is_water_at(self, x, y):
        return BIOMES[self.get_biome_at(x, y)][4]

    def draw(self, surface):
        surface.blit(self.surface, (0, 0))

class WeatherRegion:
    def __init__(self, x, y, w, h):
        self.rect = pygame.Rect(x, y, w, h)
        self.weather_type = 'Clear'
        self.timer = random.randint(100, 500)

        self.effects = {
            'Clear':   {'food_mult': 1.0, 'meta_mult': 1.0, 'vision_mult': 1.0, 'color': (0,0,0,0)},
            'Rain':    {'food_mult': 1.8, 'meta_mult': 0.9, 'vision_mult': 1.0, 'color': (20,40,80,50)},
            'Snow':    {'food_mult': 0.3, 'meta_mult': 1.3, 'vision_mult': 0.8, 'color': (200,220,230,60)},
            'Drought': {'food_mult': 0.1, 'meta_mult': 1.4, 'vision_mult': 1.0, 'color': (100,50,20,60)},
            'Fog':     {'food_mult': 0.8, 'meta_mult': 1.0, 'vision_mult': 0.5, 'color': (150,150,150,70)}
        }
        self.particles = []

    def update(self, season_name):
        self.timer -= 1
        if self.timer <= 0:
            self.timer = random.randint(300, 800)
            choices = ['Clear']
            if season_name == 'Winter': choices = ['Clear', 'Snow', 'Snow', 'Fog']
            elif season_name == 'Summer': choices = ['Clear', 'Drought', 'Drought', 'Clear']
            elif season_name == 'Spring': choices = ['Clear', 'Rain', 'Rain']
            else: choices = ['Clear', 'Rain', 'Fog']
            self.weather_type = random.choice(choices)

        if self.weather_type in ['Rain', 'Snow'] and len(self.particles) < 30:
            self.particles.append([
                random.uniform(self.rect.x, self.rect.right),
                random.uniform(self.rect.y, self.rect.y + 10),
                random.uniform(-1, 1), random.uniform(2, 5)
            ])
        elif self.weather_type in ['Clear', 'Drought', 'Fog'] and self.particles:
            self.particles.pop()

        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            if p[1] > self.rect.bottom:
                p[1] = self.rect.y
                p[0] = random.uniform(self.rect.x, self.rect.right)

    def draw_tint(self, surface):
        if self.weather_type != 'Clear':
            tint = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
            tint.fill(self.effects[self.weather_type]['color'])
            surface.blit(tint, self.rect.topleft)

    def draw_particles(self, surface):
        if self.weather_type == 'Rain':
            for p in self.particles:
                pygame.draw.line(surface, (100, 150, 200), (p[0], p[1]), (p[0]+p[2], p[1]+p[3]), 1)
        elif self.weather_type == 'Snow':
            for p in self.particles:
                pygame.draw.circle(surface, (255, 255, 255), (int(p[0]), int(p[1])), 2)

class SpatialGrid:
    def __init__(self, cell_size):
        self.cell_size = cell_size
        self.grid = {}
    def clear(self): self.grid.clear()
    def add(self, obj, x=None, y=None):
        if x is None: x = obj.x
        if y is None: y = obj.y
        cx, cy = int(x // self.cell_size), int(y // self.cell_size)
        if (cx, cy) not in self.grid: self.grid[(cx, cy)] = []
        self.grid[(cx, cy)].append(obj)
    def get_nearby(self, x, y, radius):
        nearby = []
        cx, cy = int(x // self.cell_size), int(y // self.cell_size)
        r = int(radius // self.cell_size) + 1
        for i in range(-r, r + 1):
            for j in range(-r, r + 1):
                if (cx + i, cy + j) in self.grid:
                    nearby.extend(self.grid[(cx + i, cy + j)])
        return nearby

class FoodItem:
    """Food with decay, nutrition, and position."""
    __slots__ = ('x', 'y', 'nutrition', 'age', 'max_age', 'is_corpse')
    def __init__(self, x, y, nutrition=40, is_corpse=False):
        self.x = x
        self.y = y
        self.nutrition = nutrition
        self.age = 0
        self.max_age = 600 if is_corpse else 1500
        self.is_corpse = is_corpse

    def update(self):
        self.age += 1
        if self.is_corpse:
            # Corpses decay, losing nutrition over time
            self.nutrition = max(0, self.nutrition - 0.05)
        return self.age < self.max_age and self.nutrition > 0.5

class Creature:
    def __init__(self, x, y, size=5.0, speed=2.0, vision=80.0,
                 energy=STARTING_ENERGY, repro_thresh=150.0, max_age=2000,
                 spikes=0.0, clutch_size=1, agility=0.3, max_energy=250.0,
                 stealth=0.0, toxicity=0.0, digest_eff=1.0, mut_rate=0.15, intelligence=0.0,
                 lineage_id=0, body_type=1, diet_type=0, aquatic=False):
        self.x = x
        self.y = y
        self.size = size
        self.current_size = size * 0.3
        self.speed = speed
        self.vision = vision
        self.color = LINEAGE_COLORS.get(lineage_id, (200, 200, 200))
        self.energy = energy
        self.repro_thresh = repro_thresh
        self.max_age = max_age
        self.spikes = spikes
        self.clutch_size = int(clutch_size)
        self.agility = agility
        self.max_energy = max_energy
        self.stealth = stealth
        self.toxicity = toxicity
        self.digest_eff = digest_eff
        self.mut_rate = mut_rate
        self.intelligence = intelligence
        self.lineage_id = lineage_id
        self.body_type = body_type
        self.diet_type = diet_type
        self.aquatic = aquatic  # NEW: can swim in water
        self.age = 0
        self.angle = random.uniform(0, math.pi * 2)
        self.brain_timer = random.randint(10, 30)
        self.target_pos = None
        self.poison_timer = 0
        self.mating_cooldown = 0
        self.infected = False
        self.infection_timer = 0  # NEW: how long infected
        self.kills = 0  # NEW: tracking for stats
        self.memory = {}  # NEW: remembers dangerous locations

    def update(self, grid, food_grid, foods, game_map, region_grid, season_meta, day_factor, all_creatures):
        self.age += 1
        if self.mating_cooldown > 0: self.mating_cooldown -= 1
        if self.infection_timer > 0:
            self.infection_timer -= 1
            if self.infection_timer <= 0:
                # Chance to recover
                if random.random() < 0.3:
                    self.infected = False
                else:
                    self.infection_timer = 100  # continue infection

        growth_cost = 0
        if self.current_size < self.size:
            self.current_size += 0.02
            growth_cost = 0.3

        base_cost = math.pow(self.current_size, 1.5) * 0.02
        trait_cost = (self.vision * 0.003) + (self.spikes * 0.05) + (self.agility * 0.1) \
                   + (self.max_energy * 0.001) + (self.stealth * 0.1) + (self.toxicity * 0.1) \
                   + (self.digest_eff * 0.2) + (self.intelligence * 0.5)
        move_cost = (self.current_size * self.speed * 0.015)
        total_cost = base_cost + trait_cost + move_cost + growth_cost

        current_biome = game_map.get_biome_at(self.x, self.y)
        _, _, biome_meta_mult, _, is_water = BIOMES[current_biome]
        total_cost *= biome_meta_mult
        total_cost *= season_meta['meta_mult']

        # Day/night: night increases metabolism slightly, reduces effective vision
        night_factor = 1.0 - day_factor  # 0 at day, 1 at night
        total_cost *= (1.0 + night_factor * 0.1)

        # Regional Weather Effect
        rx = max(0, min(REGIONS_X - 1, int(self.x // REGION_W)))
        ry = max(0, min(REGIONS_Y - 1, int(self.y // REGION_H)))
        current_region = region_grid[rx][ry]
        total_cost *= current_region.effects[current_region.weather_type]['meta_mult']

        # Water penalty for non-aquatic creatures
        if is_water and not self.aquatic:
            total_cost *= 1.5
            # Also slow down
            effective_speed = self.speed * 0.5
        else:
            effective_speed = self.speed

        if self.infected: total_cost += 0.5

        if self.age > self.max_age * 0.7:
            aging_factor = 1.0 + ((self.age - self.max_age * 0.7) / (self.max_age * 0.3)) * 2.0
            total_cost *= aging_factor

        self.energy -= total_cost

        if self.poison_timer > 0:
            self.energy -= 0.25
            self.poison_timer -= 1

        self.energy = min(self.energy, self.max_energy)
        if self.age > self.max_age:
            self.energy = 0
            return

        self.brain_timer -= 1
        if self.brain_timer <= 0:
            self.angle += random.uniform(-0.5, 0.5)
            self.brain_timer = random.randint(10, 30)

        closest_target = None
        closest_dist = float('inf')
        flee_pos = None

        # Adjust vision based on local weather (Fog/night reduces it)
        effective_vision = self.vision * current_region.effects[current_region.weather_type]['vision_mult']
        effective_vision *= (0.4 + 0.6 * day_factor)  # Night reduces vision

        nearby_creatures = grid.get_nearby(self.x, self.y, effective_vision)

        # Flee from predators
        if self.intelligence > 0.3 or True:  # All creatures can flee
            for c in nearby_creatures:
                if c == self or c.energy <= 0: continue
                if c.diet_type == self.body_type:
                    dist = math.hypot(self.x - c.x, self.y - c.y)
                    threat_vision = effective_vision * (1 + self.intelligence)
                    if dist < threat_vision and dist < closest_dist:
                        flee_pos = (c.x, c.y)
                        closest_dist = dist

        closest_dist = float('inf')

        # Migration: weak attraction to same lineage (herding)
        if random.random() < 0.3 and self.intelligence > 0.2:
            same_lin_count = 0
            avg_x, avg_y = 0, 0
            for c in nearby_creatures:
                if c == self: continue
                if c.lineage_id == self.lineage_id:
                    avg_x += c.x
                    avg_y += c.y
                    same_lin_count += 1
            if same_lin_count > 0 and same_lin_count < 5:  # Herding but not overcrowding
                avg_x /= same_lin_count
                avg_y /= same_lin_count
                # Slight pull toward group
                herd_angle = math.atan2(avg_y - self.y, avg_x - self.x)
                angle_diff = (herd_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
                self.angle += angle_diff * 0.1

        if self.diet_type == 0:
            # Use food grid for performance
            nearby_foods = food_grid.get_nearby(self.x, self.y, effective_vision)
            for food in nearby_foods:
                dist = math.hypot(self.x - food.x, self.y - food.y)
                if dist < closest_dist:
                    closest_dist = dist
                    closest_target = food
        else:
            for c in nearby_creatures:
                if c == self or c.energy <= 0: continue
                if c.body_type == self.diet_type:
                    dist = math.hypot(self.x - c.x, c.y - c.y)
                    eff_v = effective_vision * (1 - c.stealth)
                    if dist < eff_v and dist < closest_dist:
                        if self.intelligence > 0.5 and c.toxicity > 0.3 and self.energy > 40: continue
                        closest_dist = dist
                        closest_target = (c.x, c.y)

        if flee_pos:
            dx, dy = self.x - flee_pos[0], self.y - flee_pos[1]
            self.angle = math.atan2(dy, dx)
            self.target_pos = None
        elif closest_target and closest_dist < effective_vision:
            if isinstance(closest_target, tuple):
                tx, ty = closest_target
            else:
                tx, ty = closest_target.x, closest_target.y
            self.target_pos = (tx, ty)
            dx, dy = tx - self.x, ty - self.y
            target_angle = math.atan2(dy, dx)
            angle_diff = (target_angle - self.angle + math.pi) % (2 * math.pi) - math.pi
            max_turn = self.agility
            if abs(angle_diff) < max_turn: self.angle = target_angle
            else: self.angle += max_turn if angle_diff > 0 else -max_turn
        else:
            self.target_pos = None

        next_x = self.x + math.cos(self.angle) * effective_speed
        next_y = self.y + math.sin(self.angle) * effective_speed
        next_biome = game_map.get_biome_at(next_x, next_y)
        _, _, _, passable, _ = BIOMES[next_biome]

        if not passable:
            self.angle += math.pi
            next_x = self.x + math.cos(self.angle) * effective_speed
            next_y = self.y + math.sin(self.angle) * effective_speed

        self.x = max(self.current_size, min(WIDTH - self.current_size, next_x))
        self.y = max(self.current_size, min(HEIGHT - self.current_size, next_y))

    def can_reproduce(self):
        return self.energy > self.repro_thresh and self.age > self.max_age * 0.2 and self.mating_cooldown <= 0

    def mutate_and_track(self, val, min_val, max_val, scale):
        original_val = val
        mutation = random.gauss(0, 1) * self.mut_rate * scale
        if random.random() < 0.005: mutation = val
        elif random.random() < 0.005: mutation = -val * 0.5
        new_val = max(min_val, min(max_val, val + mutation))
        val_range = max_val - min_val
        distance = abs(new_val - original_val) / val_range if val_range > 0 else 0
        return new_val, distance

    def create_child_genome(self, global_frame):
        global NEXT_LINEAGE_ID, TOTAL_SPECIATION_EVENTS
        total_distance = 0
        new_size, d1 = self.mutate_and_track(self.size, 2.0, 15.0, 2.0)
        new_speed, d2 = self.mutate_and_track(self.speed, 0.5, 6.0, 1.0)
        new_vision, d3 = self.mutate_and_track(self.vision, 20.0, 250.0, 20.0)
        new_max_energy, d4 = self.mutate_and_track(self.max_energy, 150.0, 500.0, 40.0)
        new_repro, d5 = self.mutate_and_track(self.repro_thresh, 80.0, self.max_energy * 0.8, 20.0)
        new_age, d6 = self.mutate_and_track(self.max_age, 500, 4000, 200.0)
        new_spikes, d7 = self.mutate_and_track(self.spikes, 0.0, 8.0, 1.0)
        new_agility, d8 = self.mutate_and_track(self.agility, 0.05, 1.0, 0.1)
        new_stealth, d9 = self.mutate_and_track(self.stealth, 0.0, 0.8, 0.1)
        new_toxicity, d10 = self.mutate_and_track(self.toxicity, 0.0, 1.0, 0.1)
        new_digest, d11 = self.mutate_and_track(self.digest_eff, 0.5, 1.5, 0.2)
        new_mut_rate, d12 = self.mutate_and_track(self.mut_rate, 0.02, 0.4, 0.03)
        new_intel, d13 = self.mutate_and_track(self.intelligence, 0.0, 1.0, 0.1)
        total_distance = d1+d2+d3+d4+d5+d6+d7+d8+d9+d10+d11+d12+d13

        new_clutch = self.clutch_size
        if random.random() < 0.1 * self.mut_rate:
            new_clutch = max(1, min(4, self.clutch_size + random.choice([-1, 1])))
            total_distance += 0.2

        new_body = self.body_type
        if random.random() < 0.02 * self.mut_rate:
            new_body = random.randint(1, 4)
            total_distance += 2.0

        new_diet = self.diet_type
        if random.random() < 0.05 * self.mut_rate:
            new_diet = random.randint(0, 4)
            new_spikes = 0.0
            new_toxicity = 0.0
            total_distance += 2.0

        new_aquatic = self.aquatic
        if random.random() < 0.03 * self.mut_rate:
            new_aquatic = not new_aquatic
            total_distance += 1.0

        new_lineage_id = self.lineage_id
        if total_distance > SPECIATION_THRESHOLD:
            new_lineage_id = NEXT_LINEAGE_ID
            LINEAGE_COLORS[new_lineage_id] = get_new_lineage_color()
            LINEAGE_BIRTH_TIMES[new_lineage_id] = global_frame
            LINEAGE_PARENTS[new_lineage_id] = self.lineage_id  # NEW
            NEXT_LINEAGE_ID += 1
            TOTAL_SPECIATION_EVENTS += 1
            founder_trait = random.choice(['size', 'speed', 'digest', 'max_en'])
            if founder_trait == 'size': new_size *= random.uniform(0.85, 1.15)
            elif founder_trait == 'speed': new_speed *= random.uniform(0.85, 1.15)
            elif founder_trait == 'digest': new_digest *= random.uniform(0.85, 1.15)
            elif founder_trait == 'max_en': new_max_energy *= random.uniform(0.85, 1.15)

        return {
            'size': new_size, 'speed': new_speed, 'vision': new_vision,
            'max_energy': new_max_energy, 'repro_thresh': new_repro, 'max_age': new_age,
            'spikes': new_spikes, 'agility': new_agility, 'stealth': new_stealth,
            'toxicity': new_toxicity, 'digest_eff': new_digest, 'mut_rate': new_mut_rate,
            'intelligence': new_intel, 'clutch_size': new_clutch,
            'body_type': new_body, 'diet_type': new_diet, 'lineage_id': new_lineage_id,
            'aquatic': new_aquatic
        }

    def get_offspring_asexual(self, global_frame):
        offspring = []
        offspring_energy = (self.energy / 2) / self.clutch_size
        self.energy /= 2
        self.mating_cooldown = 100
        for _ in range(self.clutch_size):
            g = self.create_child_genome(global_frame)
            offspring.append(Creature(self.x, self.y, g['size'], g['speed'], g['vision'],
                                      offspring_energy, g['repro_thresh'], g['max_age'],
                                      g['spikes'], g['clutch_size'], g['agility'], g['max_energy'],
                                      g['stealth'], g['toxicity'], g['digest_eff'], g['mut_rate'],
                                      g['intelligence'], g['lineage_id'], g['body_type'], g['diet_type'],
                                      g['aquatic']))
        return offspring

    def get_offspring_sexual(self, partner, global_frame):
        offspring = []
        offspring_energy = ((self.energy + partner.energy) / 4) / self.clutch_size
        self.energy /= 2
        partner.energy /= 2
        self.mating_cooldown = 150
        partner.mating_cooldown = 150
        for _ in range(self.clutch_size):
            base_genome = self.create_child_genome(global_frame)
            if random.random() < 0.5: base_genome['size'] = partner.size
            if random.random() < 0.5: base_genome['speed'] = partner.speed
            if random.random() < 0.5: base_genome['vision'] = partner.vision
            if random.random() < 0.5: base_genome['intelligence'] = partner.intelligence
            if random.random() < 0.5: base_genome['aquatic'] = partner.aquatic
            offspring.append(Creature(self.x, self.y, base_genome['size'], base_genome['speed'], base_genome['vision'],
                                      offspring_energy, base_genome['repro_thresh'],
                                      base_genome['max_age'], base_genome['spikes'], base_genome['clutch_size'], base_genome['agility'],
                                      base_genome['max_energy'], base_genome['stealth'], base_genome['toxicity'], base_genome['digest_eff'],
                                      base_genome['mut_rate'], base_genome['intelligence'], base_genome['lineage_id'],
                                      base_genome['body_type'], base_genome['diet_type'], base_genome['aquatic']))
        return offspring

    def draw(self, surface, is_apex, day_factor):
        if self.target_pos is not None:
            pygame.draw.line(surface, (40, 40, 40), (self.x, self.y), self.target_pos, 1)

        # Age-based desaturation
        age_pct = self.age / self.max_age
        display_color = blend_color(self.color, BLACK, self.stealth)
        if age_pct > 0.5:
            display_color = desaturate(display_color, (age_pct - 0.5) * 0.6)

        # Night darkening
        if day_factor < 0.5:
            display_color = tuple(int(c * (0.5 + 0.5 * day_factor)) for c in display_color)

        if self.spikes > 0:
            num_spikes = 8
            for i in range(num_spikes):
                angle = self.angle + (i * 2 * math.pi / num_spikes)
                p1 = (self.x + math.cos(angle) * self.current_size, self.y + math.sin(angle) * self.current_size)
                p2 = (self.x + math.cos(angle) * (self.current_size + self.spikes), self.y + math.sin(angle) * (self.current_size + self.spikes))
                pygame.draw.line(surface, (200, 200, 0), p1, p2, 2)

        draw_shape(surface, display_color, self.x, self.y, self.current_size, self.body_type, self.angle)

        outline_color = (200, 200, 200)
        if is_apex: outline_color = (255, 255, 255)
        elif self.infected: outline_color = (255, 0, 0)
        elif self.poison_timer > 0: outline_color = (255, 255, 0)
        elif self.toxicity > 0.1: outline_color = (50, 255, 50)
        elif self.intelligence > 0.6: outline_color = (100, 150, 255)
        elif self.aquatic: outline_color = (100, 200, 255)

        if self.body_type == 1:
            pygame.draw.circle(surface, outline_color, (int(self.x), int(self.y)), int(self.current_size), 2 if is_apex else 1)
        else:
            draw_shape(surface, outline_color, self.x, self.y, self.current_size, self.body_type, self.angle)

        bar_width = self.current_size * 2
        bar_height = 2
        bar_x = self.x - self.current_size
        bar_y = self.y + self.current_size + 3
        pygame.draw.rect(surface, (50, 0, 0), (bar_x, bar_y, bar_width, bar_height))
        health_pct = max(0, self.energy / self.max_energy)
        pygame.draw.rect(surface, (0, 200, 0), (bar_x, bar_y, bar_width * health_pct, bar_height))

    def get_stats_dict(self):
        return {
            'Position': f"({int(self.x)}, {int(self.y)})",
            'Lineage': self.lineage_id,
            'Age': f"{self.age}/{self.max_age}",
            'Energy': f"{int(self.energy)}/{int(self.max_energy)}",
            'Size': f"{self.current_size:.1f}/{self.size:.1f}",
            'Speed': f"{self.speed:.2f}",
            'Vision': f"{self.vision:.0f}",
            'Intelligence': f"{self.intelligence:.2f}",
            'Diet': ['Herbivore', 'Carn-Circle', 'Carn-Tri', 'Carn-Sq', 'Carn-Pent'][self.diet_type],
            'Body': ['Circle', 'Triangle', 'Square', 'Pentagon'][self.body_type - 1],
            'Toxicity': f"{self.toxicity:.2f}",
            'Stealth': f"{self.stealth:.2f}",
            'Spikes': f"{self.spikes:.1f}",
            'Agility': f"{self.agility:.2f}",
            'Digest': f"{self.digest_eff:.2f}",
            'MutRate': f"{self.mut_rate:.3f}",
            'Aquatic': self.aquatic,
            'Infected': self.infected,
            'Kills': self.kills
        }

def draw_graph(surface, history, font):
    graph_w, graph_h = 250, 100
    graph_x = WIDTH - graph_w - 10
    graph_y = HEIGHT - graph_h - 10
    pygame.draw.rect(surface, GRAPH_BG, (graph_x, graph_y, graph_w, graph_h))
    pygame.draw.rect(surface, (100, 100, 100), (graph_x, graph_y, graph_w, graph_h), 1)
    title = font.render("Lineage Population History", True, (180, 180, 180))
    surface.blit(title, (graph_x + 5, graph_y - 18))
    if not history: return
    max_pop = max([max(frame.values()) for frame in history] + [10])
    current_counts = history[-1]
    top_lineages = sorted(current_counts.keys(), key=lambda k: current_counts[k], reverse=True)[:4]
    for lin_id in top_lineages:
        color = LINEAGE_COLORS.get(lin_id, (255, 255, 255))
        points = []
        for i, frame in enumerate(history):
            count = frame.get(lin_id, 0)
            px = graph_x + (i / (len(history)-1 if len(history) > 1 else 1)) * graph_w
            py = graph_y + graph_h - (count / max_pop) * graph_h
            points.append((px, py))
        if len(points) > 1:
            pygame.draw.lines(surface, color, False, points, 2)

def draw_lineage_tree(surface, font, x, y, w, h):
    """Draw a small tree of lineage relationships."""
    pygame.draw.rect(surface, GRAPH_BG, (x, y, w, h))
    pygame.draw.rect(surface, (100, 100, 100), (x, y, w, h), 1)
    title = font.render("Lineage Tree", True, (180, 180, 180))
    surface.blit(title, (x + 5, y - 18))

    if not LINEAGE_PARENTS: return

    # Build tree levels
    levels = {}
    for lin_id in LINEAGE_PARENTS:
        # Walk up to root to find depth
        depth = 0
        cur = lin_id
        while LINEAGE_PARENTS.get(cur) is not None:
            cur = LINEAGE_PARENTS[cur]
            depth += 1
        levels.setdefault(depth, []).append(lin_id)

    max_depth = max(levels.keys()) + 1 if levels else 1
    if max_depth == 0: max_depth = 1

    # Draw nodes
    for depth, lins in levels.items():
        node_y = y + 15 + depth * (h - 30) / max(1, max_depth - 1) if max_depth > 1 else y + h // 2
        for i, lin_id in enumerate(lins):
            node_x = x + 15 + (i + 0.5) * (w - 30) / max(1, len(lins))
            color = LINEAGE_COLORS.get(lin_id, (200, 200, 200))
            pygame.draw.circle(surface, color, (int(node_x), int(node_y)), 4)
            # Draw line to parent
            parent = LINEAGE_PARENTS.get(lin_id)
            if parent is not None and parent in [l for ls in list(levels.values())[:depth] for l in ls]:
                # Find parent position (simple: search previous levels)
                for d2 in range(depth):
                    if parent in levels.get(d2, []):
                        p_idx = levels[d2].index(parent)
                        p_x = x + 15 + (p_idx + 0.5) * (w - 30) / max(1, len(levels[d2]))
                        p_y = y + 15 + d2 * (h - 30) / max(1, max_depth - 1) if max_depth > 1 else y + h // 2
                        pygame.draw.line(surface, (80, 80, 80), (p_x, p_y), (node_x, node_y), 1)
                        break

def draw_inspection_panel(surface, creature, font, small_font, x, y):
    """Draw an inspection panel for a clicked creature."""
    if not creature: return
    panel_w, panel_h = 220, 280
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill(UI_BG)
    pygame.draw.rect(panel, (100, 100, 100), (0, 0, panel_w, panel_h), 1)

    title_color = LINEAGE_COLORS.get(creature.lineage_id, (255, 255, 255))
    title = font.render(f"Creature Inspector", True, title_color)
    panel.blit(title, (10, 5))

    stats = creature.get_stats_dict()
    for i, (k, v) in enumerate(stats.items()):
        text = f"{k}: {v}"
        render = small_font.render(text, True, (200, 200, 200))
        panel.blit(render, (10, 30 + i * 16))

    surface.blit(panel, (x, y))

def trigger_natural_event(event_type, game_map, creatures, foods, region_grid):
    """Trigger a random natural event."""
    if event_type == 'meteor':
        # Meteor strike: kills creatures in radius, creates food
        mx, my = random.randint(50, WIDTH - 50), random.randint(50, HEIGHT - 50)
        radius = 80
        for c in creatures:
            if math.hypot(c.x - mx, c.y - my) < radius:
                c.energy = 0
                # Leave corpse food
                foods.append(FoodItem(c.x, c.y, nutrition=80, is_corpse=True))
        return f"Meteor at ({int(mx)},{int(my)})!"
    elif event_type == 'bloom':
        # Food bloom
        for _ in range(80):
            x, y = random.randint(0, WIDTH), random.randint(0, HEIGHT)
            b = game_map.get_biome_at(x, y)
            if BIOMES[b][1] > 0:
                foods.append(FoodItem(x, y, nutrition=60))
        return "Food Bloom!"
    elif event_type == 'cold_snap':
        # All regions become snow briefly
        for row in region_grid:
            for r in row:
                r.weather_type = 'Snow'
                r.timer = 200
        return "Cold Snap!"
    return ""

def save_simulation(creatures, foods, global_frame, filename='evo_save.json'):
    """Save simulation state to JSON."""
    data = {
        'global_frame': global_frame,
        'creatures': [{
            'x': c.x, 'y': c.y, 'size': c.size, 'speed': c.speed, 'vision': c.vision,
            'energy': c.energy, 'repro_thresh': c.repro_thresh, 'max_age': c.max_age,
            'spikes': c.spikes, 'clutch_size': c.clutch_size, 'agility': c.agility,
            'max_energy': c.max_energy, 'stealth': c.stealth, 'toxicity': c.toxicity,
            'digest_eff': c.digest_eff, 'mut_rate': c.mut_rate, 'intelligence': c.intelligence,
            'lineage_id': c.lineage_id, 'body_type': c.body_type, 'diet_type': c.diet_type,
            'aquatic': c.aquatic, 'age': c.age, 'angle': c.angle
        } for c in creatures],
        'foods': [{'x': f.x, 'y': f.y, 'nutrition': f.nutrition, 'is_corpse': f.is_corpse} for f in foods],
        'lineage_colors': {str(k): v for k, v in LINEAGE_COLORS.items()},
        'lineage_birth_times': {str(k): v for k, v in LINEAGE_BIRTH_TIMES.items()},
        'lineage_parents': {str(k): v for k, v in LINEAGE_PARENTS.items()},
        'next_lineage_id': NEXT_LINEAGE_ID,
        'total_speciation_events': TOTAL_SPECIATION_EVENTS
    }
    with open(filename, 'w') as f:
        json.dump(data, f)
    return True

def load_simulation(filename='evo_save.json'):
    """Load simulation state from JSON."""
    global NEXT_LINEAGE_ID, TOTAL_SPECIATION_EVENTS
    global LINEAGE_COLORS, LINEAGE_BIRTH_TIMES, LINEAGE_PARENTS
    if not os.path.exists(filename):
        return None
    with open(filename, 'r') as f:
        data = json.load(f)

    LINEAGE_COLORS = {int(k): tuple(v) for k, v in data['lineage_colors'].items()}
    LINEAGE_BIRTH_TIMES = {int(k): v for k, v in data['lineage_birth_times'].items()}
    LINEAGE_PARENTS = {int(k): v for k, v in data['lineage_parents'].items()}
    NEXT_LINEAGE_ID = data['next_lineage_id']
    TOTAL_SPECIATION_EVENTS = data['total_speciation_events']

    creatures = []
    for cd in data['creatures']:
        c = Creature(cd['x'], cd['y'], cd['size'], cd['speed'], cd['vision'],
                     cd['energy'], cd['repro_thresh'], cd['max_age'],
                     cd['spikes'], cd['clutch_size'], cd['agility'], cd['max_energy'],
                     cd['stealth'], cd['toxicity'], cd['digest_eff'], cd['mut_rate'],
                     cd['intelligence'], cd['lineage_id'], cd['body_type'], cd['diet_type'],
                     cd.get('aquatic', False))
        c.age = cd['age']
        c.angle = cd['angle']
        c.current_size = c.size  # Skip growth animation
        creatures.append(c)

    foods = [FoodItem(f['x'], f['y'], f['nutrition'], f['is_corpse']) for f in data['foods']]
    return creatures, foods, data['global_frame']

def main():
    global NEXT_LINEAGE_ID, LINEAGE_COLORS, LINEAGE_BIRTH_TIMES, LINEAGE_PARENTS, TOTAL_SPECIATION_EVENTS
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Evolution Simulation - Enhanced Edition")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("Consolas", 16, bold=True)
    small_font = pygame.font.SysFont("Consolas", 12, bold=True)
    big_font = pygame.font.SysFont("Consolas", 20, bold=True)

    game_map = GameMap(WIDTH, HEIGHT, TILE_SIZE)

    region_grid = [[WeatherRegion(x * REGION_W, y * REGION_H, REGION_W, REGION_H)
                    for y in range(REGIONS_Y)] for x in range(REGIONS_X)]

    def reset_sim():
        global NEXT_LINEAGE_ID, LINEAGE_COLORS, LINEAGE_BIRTH_TIMES, LINEAGE_PARENTS, TOTAL_SPECIATION_EVENTS
        NEXT_LINEAGE_ID = 1
        TOTAL_SPECIATION_EVENTS = 0
        LINEAGE_COLORS = {0: (200, 200, 200)}
        LINEAGE_BIRTH_TIMES = {0: 0}
        LINEAGE_PARENTS = {0: None}
        creatures = []
        while len(creatures) < INITIAL_POPULATION:
            x, y = random.randint(0, WIDTH), random.randint(0, HEIGHT)
            b = game_map.get_biome_at(x, y)
            if BIOMES[b][3]:
                creatures.append(Creature(x, y, random.uniform(3, 8), random.uniform(1, 3),
                                          random.uniform(40, 120), lineage_id=0, body_type=1, diet_type=0))
        return creatures

    creatures = reset_sim()
    foods = []
    food_timer = 0
    global_frame = 0
    graph_history = []
    GRAPH_UPDATE_RATE = 15
    grid = SpatialGrid(GRID_CELL_SIZE)
    food_grid = SpatialGrid(GRID_CELL_SIZE)  # NEW: separate grid for food

    season_index = 0
    seasons = [
        {'name': 'Spring', 'food_mult': 1.5, 'meta_mult': 1.0, 'color': (50, 100, 50)},
        {'name': 'Summer', 'food_mult': 1.0, 'meta_mult': 1.0, 'color': (100, 100, 50)},
        {'name': 'Autumn', 'food_mult': 0.6, 'meta_mult': 1.1, 'color': (100, 50, 50)},
        {'name': 'Winter', 'food_mult': 0.2, 'meta_mult': 1.2, 'color': (50, 50, 100)}
    ]
    season_timer = 0
    SEASON_DURATION = 1500

    plague_timer = 1500
    plague_active_lineage = -1
    plague_duration_timer = 0

    # NEW: UI state
    paused = False
    sim_speed = 1  # 1, 2, 4, 8
    selected_creature = None
    hovered_creature = None
    event_message = ""
    event_message_timer = 0
    natural_event_timer = random.randint(2000, 4000)
    show_inspect = False
    mouse_pos = (0, 0)

    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0

        global_frame += 1
        season_timer += 1
        plague_timer -= 1
        natural_event_timer -= 1

        # Day/night cycle
        day_factor = (math.sin(global_frame * 2 * math.pi / DAY_LENGTH - math.pi / 2) + 1) / 2

        if season_timer > SEASON_DURATION:
            season_index = (season_index + 1) % 4
            season_timer = 0
        current_season = seasons[season_index]

        for row in region_grid:
            for region in row:
                region.update(current_season['name'])

        # Plague logic
        if plague_timer <= 0 and plague_active_lineage == -1:
            lineage_counts_temp = {}
            for c in creatures:
                lineage_counts_temp[c.lineage_id] = lineage_counts_temp.get(c.lineage_id, 0) + 1
            if lineage_counts_temp and max(lineage_counts_temp.values()) > 20:
                plague_active_lineage = max(lineage_counts_temp, key=lineage_counts_temp.get)
                plague_duration_timer = 600
                plague_timer = 2500
        if plague_duration_timer > 0:
            plague_duration_timer -= 1
            if plague_duration_timer <= 0:
                plague_active_lineage = -1
                # Cure all
                for c in creatures:
                    c.infected = False
                    c.infection_timer = 0

        # Natural events
        if natural_event_timer <= 0:
            event_type = random.choice(['meteor', 'bloom', 'cold_snap'])
            event_message = trigger_natural_event(event_type, game_map, creatures, foods, region_grid)
            event_message_timer = 180
            natural_event_timer = random.randint(3000, 6000)
        if event_message_timer > 0:
            event_message_timer -= 1

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE: paused = not paused
                elif event.key == pygame.K_r:
                    creatures = reset_sim()
                    foods = []
                    graph_history = []
                    selected_creature = None
                elif event.key == pygame.K_1: sim_speed = 1
                elif event.key == pygame.K_2: sim_speed = 2
                elif event.key == pygame.K_3: sim_speed = 4
                elif event.key == pygame.K_4: sim_speed = 8
                elif event.key == pygame.K_s:
                    if save_simulation(creatures, foods, global_frame):
                        event_message = "Saved!"
                        event_message_timer = 120
                elif event.key == pygame.K_l:
                    result = load_simulation()
                    if result:
                        creatures, foods, global_frame = result
                        event_message = "Loaded!"
                        event_message_timer = 120
                        selected_creature = None
                elif event.key == pygame.K_i:
                    show_inspect = not show_inspect
                elif event.key == pygame.K_e:
                    # Trigger event manually
                    event_type = random.choice(['meteor', 'bloom', 'cold_snap'])
                    event_message = trigger_natural_event(event_type, game_map, creatures, foods, region_grid)
                    event_message_timer = 180
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    mx, my = event.pos
                    # Find closest creature within radius
                    closest = None
                    closest_dist = 25  # max click distance
                    for c in creatures:
                        d = math.hypot(c.x - mx, c.y - my)
                        if d < closest_dist:
                            closest_dist = d
                            closest = c
                    selected_creature = closest
                    show_inspect = closest is not None
            elif event.type == pygame.MOUSEMOTION:
                mouse_pos = event.pos

        if not paused:
            for _ in range(sim_speed):
                global_frame += 1

                # Spawn Food based on Season, Biome, and LOCAL Weather
                food_timer += 1
                base_spawn_rate = 8
                effective_spawn_rate = max(1, int(base_spawn_rate / current_season['food_mult']))

                # Day factor affects food spawn (more during day)
                day_spawn_bonus = 0.5 + day_factor * 0.5
                effective_spawn_rate = max(1, int(effective_spawn_rate / day_spawn_bonus))

                if food_timer >= effective_spawn_rate and len(foods) < 600:
                    food_timer = 0
                    for _ in range(3):
                        x, y = random.randint(0, WIDTH), random.randint(0, HEIGHT)
                        b = game_map.get_biome_at(x, y)
                        if BIOMES[b][1] > 0:
                            rx = max(0, min(REGIONS_X - 1, int(x // REGION_W)))
                            ry = max(0, min(REGIONS_Y - 1, int(y // REGION_H)))
                            local_weather = region_grid[rx][ry]
                            local_food_mult = local_weather.effects[local_weather.weather_type]['food_mult']

                            if random.random() < (BIOMES[b][1] * local_food_mult):
                                # Forest food has slightly more nutrition
                                nutrition = 40 if b != 'forest' else 50
                                foods.append(FoodItem(x, y, nutrition=nutrition))
                                break

                # Update food (decay)
                foods = [f for f in foods if f.update()]

                # Rebuild grids
                grid.clear()
                food_grid.clear()
                for c in creatures: grid.add(c)
                for f in foods: food_grid.add(f, f.x, f.y)

                new_creatures = []
                mated_this_frame = set()
                lineage_counts = {}
                for c in creatures: lineage_counts[c.lineage_id] = lineage_counts.get(c.lineage_id, 0) + 1
                apex_id = max(lineage_counts, key=lineage_counts.get) if lineage_counts else -1

                creatures_to_update = list(creatures)
                for c in creatures_to_update:
                    if c.energy <= 0: continue
                    c.update(grid, food_grid, foods, game_map, region_grid, current_season, day_factor, creatures)

                    if c.diet_type == 0 and c.energy > 0:
                        # Herbivore eating - use food grid
                        nearby_foods = food_grid.get_nearby(c.x, c.y, c.current_size + 5)
                        for food in nearby_foods:
                            if food not in foods: continue  # Already eaten
                            dist = math.hypot(c.x - food.x, c.y - food.y)
                            if dist < c.current_size + 3:
                                c.energy += food.nutrition * c.digest_eff
                                if food in foods:
                                    foods.remove(food)
                                break
                    elif c.energy > 0:
                        nearby_prey = grid.get_nearby(c.x, c.y, c.current_size * 2)
                        for prey in nearby_prey:
                            if prey == c or prey.energy <= 0: continue
                            if c.diet_type == prey.body_type:
                                dist = math.hypot(c.x - prey.x, c.y - prey.y)
                                if dist < c.current_size + prey.current_size:
                                    c.energy -= prey.spikes * 25
                                    if prey.toxicity > 0: c.poison_timer = max(c.poison_timer, int(prey.toxicity * 300))
                                    # Plague spread by contact (not just same lineage)
                                    if plague_active_lineage != -1:
                                        if (c.lineage_id == plague_active_lineage or prey.lineage_id == plague_active_lineage):
                                            c.infected = True
                                            prey.infected = True
                                            c.infection_timer = max(c.infection_timer, 100)
                                            prey.infection_timer = max(prey.infection_timer, 100)
                                    if c.energy > 0:
                                        base_gain = (prey.energy + 20) * c.digest_eff
                                        if c.lineage_id == prey.lineage_id: base_gain *= 0.7
                                        else: base_gain *= 1.2
                                        c.energy += base_gain
                                        c.kills += 1
                                    # Leave corpse food
                                    foods.append(FoodItem(prey.x, prey.y, nutrition=40 + prey.current_size * 5, is_corpse=True))
                                    prey.energy = 0
                                    break
                    if c.energy <= 0: continue
                    if c.can_reproduce() and len(creatures) + len(new_creatures) < MAX_POPULATION:
                        mated = False
                        nearby_mates = grid.get_nearby(c.x, c.y, c.current_size * 2.5)
                        for partner in nearby_mates:
                            if partner == c or partner.mating_cooldown > 0: continue
                            if partner.body_type == c.body_type and partner.lineage_id == c.lineage_id and partner.energy > partner.repro_thresh and partner.age > partner.max_age * 0.2:
                                dist = math.hypot(c.x - partner.x, c.y - partner.y)
                                if dist < c.current_size + partner.current_size + 2:
                                    new_creatures.extend(c.get_offspring_sexual(partner, global_frame))
                                    mated = True
                                    mated_this_frame.add(c)
                                    mated_this_frame.add(partner)
                                    break
                        if not mated and c not in mated_this_frame:
                            new_creatures.extend(c.get_offspring_asexual(global_frame))

                creatures.extend(new_creatures)
                if plague_active_lineage == -1:
                    for c in creatures:
                        c.infected = False
                        c.infection_timer = 0

                # Remove dead creatures (already converted to corpses above)
                creatures = [c for c in creatures if c.energy > 0]

                if global_frame % GRAPH_UPDATE_RATE == 0:
                    current_frame_counts = {}
                    for c in creatures: current_frame_counts[c.lineage_id] = current_frame_counts.get(c.lineage_id, 0) + 1
                    graph_history.append(current_frame_counts)
                    if len(graph_history) > 100: graph_history.pop(0)

                if sim_speed > 1 and global_frame % (sim_speed * 5) == 0:
                    break  # Allow events to process between fast ticks

        # Find hovered creature
        hovered_creature = None
        if not show_inspect:
            closest_d = 20
            for c in creatures:
                d = math.hypot(c.x - mouse_pos[0], c.y - mouse_pos[1])
                if d < closest_d:
                    closest_d = d
                    hovered_creature = c

        # --- DRAWING ---
        game_map.draw(screen)

        # Day/night overlay
        night_alpha = int((1 - day_factor) * 80)
        if night_alpha > 0:
            night_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            night_surface.fill((10, 10, 40, night_alpha))
            screen.blit(night_surface, (0, 0))

        # Seasonal Tint
        tint_surface = pygame.Surface((WIDTH, HEIGHT))
        tint_surface.fill(current_season['color'])
        tint_surface.set_alpha(30)
        screen.blit(tint_surface, (0, 0))

        # Food
        for food in foods:
            color = (100, 150, 80) if food.is_corpse else (50, 200, 50)
            size = 4 if food.is_corpse else 3
            pygame.draw.circle(screen, color, (int(food.x), int(food.y)), size)

        # Regional Weather Tints & Particles
        for row in region_grid:
            for region in row:
                region.draw_tint(screen)
        for row in region_grid:
            for region in row:
                region.draw_particles(screen)

        # Draw creatures
        for c in creatures:
            is_apex = (lineage_counts.get(c.lineage_id, 0) == max(lineage_counts.values()) if lineage_counts else False)
            c.draw(screen, is_apex, day_factor)

        # Highlight selected/hovered
        if selected_creature and selected_creature in creatures:
            pygame.draw.circle(screen, (255, 255, 0), (int(selected_creature.x), int(selected_creature.y)),
                             int(selected_creature.current_size) + 5, 2)
        elif hovered_creature:
            pygame.draw.circle(screen, (200, 200, 200), (int(hovered_creature.x), int(hovered_creature.y)),
                             int(hovered_creature.current_size) + 4, 1)

        # --- UI / Stats ---
        t1 = sum(1 for c in creatures if c.body_type == 1)
        t2 = sum(1 for c in creatures if c.body_type == 2)
        t3 = sum(1 for c in creatures if c.body_type == 3)
        t4 = sum(1 for c in creatures if c.body_type == 4)
        d0 = sum(1 for c in creatures if c.diet_type == 0)
        d1 = sum(1 for c in creatures if c.diet_type == 1)
        d2 = sum(1 for c in creatures if c.diet_type == 2)
        d3 = sum(1 for c in creatures if c.diet_type == 3)
        d4 = sum(1 for c in creatures if c.diet_type == 4)
        infected_count = sum(1 for c in creatures if c.infected)
        aquatic_count = sum(1 for c in creatures if c.aquatic)
        plague_text = f"Plague on Lin {plague_active_lineage} ({infected_count} inf)" if plague_active_lineage != -1 else "No Plague"

        time_of_day = "Day" if day_factor > 0.5 else "Night" if day_factor < 0.2 else "Dusk/Dawn"

        stats_text = [
            f"Pop: {len(creatures)}/{MAX_POPULATION} | Food: {len(foods)} | Lines: {len(lineage_counts)} | Sp: {TOTAL_SPECIATION_EVENTS}",
            f"Bodies -> Circ:{t1} Tri:{t2} Sq:{t3} Pent:{t4} | Aquatic: {aquatic_count}",
            f"Diet -> Herb:{d0} Carn1:{d1} Carn2:{d2} Carn3:{d3} Carn4:{d4}",
            f"Season: {current_season['name']} | Time: {time_of_day} | {plague_text}",
            f"Speed: {sim_speed}x | [SPACE]Pause [R]Reset [1-4]Speed [S]Save [L]Load [I]Inspect [E]Event",
        ]

        for i, text in enumerate(stats_text):
            color = (200, 200, 200)
            if i == 3: color = current_season['color']
            color = tuple(min(255, c + 80) for c in color)
            render = font.render(text, True, color)
            screen.blit(render, (10, 10 + i * 20))

        # Top lineages
        sorted_lineages = sorted(lineage_counts.items(), key=lambda item: item[1], reverse=True)
        for i in range(min(4, len(sorted_lineages))):
            lin_id, count = sorted_lineages[i]
            age = global_frame - LINEAGE_BIRTH_TIMES.get(lin_id, 0)
            text = f"  - Lin {lin_id}: {count} (Age {age})"
            render = small_font.render(text, True, LINEAGE_COLORS.get(lin_id, (255,255,255)))
            screen.blit(render, (10, 115 + i * 16))

        # Hover tooltip
        if hovered_creature and not show_inspect:
            tooltip_lines = [
                f"Lin {hovered_creature.lineage_id} | {hovered_creature.get_stats_dict()['Body']}",
                f"E: {int(hovered_creature.energy)} | Age: {hovered_creature.age}",
                f"Diet: {hovered_creature.get_stats_dict()['Diet']}",
            ]
            tx, ty = mouse_pos[0] + 15, mouse_pos[1] + 15
            for j, line in enumerate(tooltip_lines):
                r = small_font.render(line, True, (255, 255, 255))
                bg = pygame.Surface((r.get_width() + 6, r.get_height() + 2), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 180))
                screen.blit(bg, (tx - 3, ty + j * 16 - 1))
                screen.blit(r, (tx, ty + j * 16))

        # Event message
        if event_message_timer > 0:
            alpha = min(255, event_message_timer * 3)
            msg_surf = big_font.render(event_message, True, (255, 200, 100))
            msg_rect = msg_surf.get_rect(center=(WIDTH // 2, 60))
            bg = pygame.Surface((msg_rect.w + 20, msg_rect.h + 10), pygame.SRCALPHA)
            bg.fill((0, 0, 0, alpha // 2))
            screen.blit(bg, (msg_rect.x - 10, msg_rect.y - 5))
            msg_surf.set_alpha(alpha)
            screen.blit(msg_surf, msg_rect)

        # Graphs
        draw_graph(screen, graph_history, small_font)
        draw_lineage_tree(screen, small_font, WIDTH - 270, 80, 260, 100)

        # Inspection panel
        if show_inspect and selected_creature and selected_creature in creatures:
            draw_inspection_panel(screen, selected_creature, font, small_font, WIDTH - 240, 200)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()