"""Short presentation-only effects. Damage and orders are never applied here."""

from dataclasses import dataclass
import math

import pygame as pg

from .combat import BEAMS
from .ui import INK, text


@dataclass
class CombatAnimation:
    kind: str
    ship_id: int
    path: tuple
    target_id: int | None = None
    weapon: str = "none"
    damage: int = 0
    destroyed: bool = False
    elapsed: float = 0.0
    weapons: tuple[str, ...] = ()
    missed: bool = False
    escorts: tuple = ()

    @classmethod
    def from_action(cls, battle, action):
        if action["kind"] == "move":
            return cls("move", action["ship_id"], tuple(action["path"]))
        if action["kind"] == "fire":
            ship, target = battle.ship(action["ship_id"]), battle.ship(action["target_id"])
            result = cls("fire", ship.id, (ship.position, target.position), target.id,
                       ship.weapon, action["damage"], target.hull == 0,
                       weapons=tuple(action.get("weapons", dict.fromkeys(w for w, _ in ship.volley(target)))), missed=action.get("missed", False))
            if any(BEAMS[w].projectile or BEAMS[w].drone for w in result.weapons or (result.weapon,)):
                result.escorts = tuple(battle.ship(i).position for i in action.get("support_ids", ()) if battle.ship(i))
            return result
        return None

    @property
    def duration(self):
        if self.kind == "move":
            return .12+.16*(len(self.path)-1)
        return 1.3 if self.destroyed else .75

    @property
    def finished(self):
        return self.elapsed >= self.duration

    def moving_position(self):
        fraction = min(1.0, self.elapsed/self.duration)
        step = fraction*(len(self.path)-1)
        index = min(int(step), len(self.path)-2)
        a, b = self.path[index:index+2]
        return a[0]+(b[0]-a[0])*(step-index), a[1]+(b[1]-a[1])*(step-index)

    def draw(self, surface, project, *, origin=None, target=None, explosion_scale=1.0):
        if self.kind == "move":
            points = [project(p) for p in self.path]
            if len(points) > 1:
                pg.draw.lines(surface, (51, 91, 112), False, points, 2)
            return
        origin = project(self.path[0]) if origin is None else origin
        target = project(self.path[1]) if target is None else target
        if self.missed:
            target = (target[0]+18, target[1]-25)
        color = BEAMS[(self.weapons or (self.weapon,))[0]].color
        age = self.elapsed
        if self.escorts and .06 <= age < .3:
            # Short defensive bursts converge on the approaching salvo. Visual only.
            for index, escort in enumerate(self.escorts):
                point = (round(origin[0]+(target[0]-origin[0])*.82),
                         round(origin[1]+(target[1]-origin[1])*.82)+(index%3-1)*7)
                pg.draw.line(surface, (95, 236, 205), project(escort), point, 1)
                pg.draw.circle(surface, (206, 255, 235), point, 3, 1)
        for index, weapon in enumerate(self.weapons or (self.weapon,)):
            shade = BEAMS[weapon].color
            if age < .34:
                spec = BEAMS[weapon]
                reach = min(1, age/(.18 if spec.projectile else .1))
                start = (origin[0], origin[1]+index*4)
                tip = (round(start[0]+(target[0]-start[0])*reach),
                       round(start[1]+(target[1]-start[1])*reach))
                if spec.projectile:
                    for warhead in range(spec.shots):
                        spread = (warhead-(spec.shots-1)/2)*14*math.sin(reach*math.pi)
                        head = (tip[0], round(tip[1]+spread))
                        tail = (round(head[0]+(start[0]-head[0])*.08), round(head[1]+(start[1]-head[1])*.08))
                        pg.draw.line(surface, shade, tail, head, 4)
                        pg.draw.circle(surface, INK, head, 4)
                else:
                    self.draw_beam(surface, weapon, start, tip, shade, age)
        if age >= .18:
            impact = age-.18
            if self.destroyed:
                self.draw_explosion(surface, target, impact, explosion_scale)
            elif not self.missed and impact < .4:
                radius = max(2, round(5+impact*43))
                pg.draw.circle(surface, color, target, radius, max(1, round(4*(1-impact/.4))))
                if impact < .15:
                    pg.draw.circle(surface, (255, 226, 164), target, max(2, round(12*(1-impact/.15))))
            text(surface, "MISS" if self.missed else f"−{self.damage}" if self.damage else "SHIELD", (target[0]+22, target[1]-22-round(impact*22)), 19, color, "mono")

    @staticmethod
    def draw_beam(surface, weapon, start, tip, shade, age):
        """Distinct procedural silhouettes, readable even at battlefield scale."""
        point = lambda fraction: (round(start[0]+(tip[0]-start[0])*fraction),
                                  round(start[1]+(tip[1]-start[1])*fraction))
        if weapon == "ion":
            points = [point(i/14) for i in range(15)]
            points = [(x, y+round(math.sin(i*2.4+age*45)*7) if 0 < i < 14 else y)
                      for i, (x, y) in enumerate(points)]
            pg.draw.lines(surface, (20, 63, 106), False, points, 10)
            pg.draw.lines(surface, shade, False, points, 3)
            pg.draw.lines(surface, INK, False, points, 1)
        elif weapon in ("pulse", "phased"):
            segments = 8 if weapon == "pulse" else 17
            for i in range(segments):
                a = min(1, (i+age*5 % 1)/segments)
                b = min(1, a+.6/segments)
                pg.draw.line(surface, shade, point(a), point(b), 5 if weapon == "pulse" else 2)
        else:
            width = 10 if weapon in ("plasma", "heavy_beam", "disruptor") else 2 if weapon == "particle" else 5
            pg.draw.line(surface, tuple(round(c*.22) for c in shade), start, tip, width+7)
            pg.draw.line(surface, shade, start, tip, width)
            pg.draw.line(surface, (255, 245, 232), start, tip, 1 if weapon == "particle" else 2)
        if weapon in ("graviton", "disruptor"):
            for i in range(1, 8):
                center = point((i/8+age*.9) % 1)
                radius = 5+round(4*math.sin(i+age*20)**2)
                pg.draw.ellipse(surface, shade, (center[0]-radius//2, center[1]-radius, radius, radius*2), 2)
        pg.draw.circle(surface, shade, start, 7)
        pg.draw.circle(surface, INK, start, 3)

    def draw_explosion(self, surface, center, age, scale=1.0):
        """Flash, fireball, shock ring and deterministic drifting debris."""
        x, y = center
        progress = min(1, age/1.12)
        layer = pg.Surface((180, 180), pg.SRCALPHA)
        alpha = round(220*(1-progress))
        if progress < .75:
            radius = max(1, round(10+42*progress))
            pg.draw.circle(layer, (250, 100, 37, alpha//3), (90, 90), radius+12)
            pg.draw.circle(layer, (255, 140, 47, alpha), (90, 90), radius)
            pg.draw.circle(layer, (255, 215, 126, alpha), (90, 90), max(1, round(radius*.62)))
            pg.draw.circle(layer, (255, 250, 221, alpha), (90, 90), max(1, round(radius*.3)))
        ring = max(2, round(12+65*progress))
        pg.draw.circle(layer, (255, 185, 97, alpha), (90, 90), ring, max(1, round(3*(1-progress))))
        for i in range(14):
            angle = i*math.tau/14+self.target_id*.31
            travel = 9+(43+(i*13)%28)*progress
            dx, dy = math.cos(angle), math.sin(angle)
            head = (round(90+dx*travel), round(90+dy*travel))
            tail = (round(90+dx*(travel-4-7*(1-progress))), round(90+dy*(travel-4-7*(1-progress))))
            pg.draw.line(layer, (255, 180+(i%3)*25, 92, alpha), tail, head, 2)
        if scale != 1.0:
            size = max(1, round(180*scale))
            layer = pg.transform.smoothscale(layer, (size, size))
        surface.blit(layer, layer.get_rect(center=(x, y)))
