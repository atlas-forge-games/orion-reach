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

    @classmethod
    def from_action(cls, battle, action):
        if action["kind"] == "move":
            return cls("move", action["ship_id"], tuple(action["path"]))
        if action["kind"] == "fire":
            ship, target = battle.ship(action["ship_id"]), battle.ship(action["target_id"])
            return cls("fire", ship.id, (ship.position, target.position), target.id,
                       ship.weapon, action["damage"], target.hull == 0,
                       weapons=tuple(dict.fromkeys(w for w, _ in ship.volley(target))), missed=action.get("missed", False))
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

    def draw(self, surface, project):
        if self.kind == "move":
            points = [project(p) for p in self.path]
            if len(points) > 1:
                pg.draw.lines(surface, (51, 91, 112), False, points, 2)
            return
        origin, target = (project(p) for p in self.path)
        if self.missed:
            target = (target[0]+18, target[1]-25)
        color = BEAMS[self.weapon].color
        age = self.elapsed
        for index, weapon in enumerate(self.weapons or (self.weapon,)):
            shade = BEAMS[weapon].color
            if age < .34:
                reach = min(1, age/(.18 if weapon in ("torpedo", "missile") else .1))
                start = (origin[0], origin[1]+index*4)
                tip = (round(start[0]+(target[0]-start[0])*reach),
                       round(start[1]+(target[1]-start[1])*reach))
                if weapon in ("torpedo", "missile"):
                    tail = (round(tip[0]+(start[0]-tip[0])*.08), round(tip[1]+(start[1]-tip[1])*.08))
                    pg.draw.line(surface, shade, tail, tip, 4)
                    pg.draw.circle(surface, INK, tip, 4)
                else:
                    pg.draw.line(surface, tuple(round(c*.22) for c in shade), start, tip, 11)
                    pg.draw.line(surface, shade, start, tip, 5)
                    pg.draw.line(surface, (255, 245, 232), start, tip, 2)
                    pg.draw.circle(surface, shade, start, 7)
                    pg.draw.circle(surface, INK, start, 3)
        if age >= .18:
            impact = age-.18
            if self.destroyed:
                self.draw_explosion(surface, target, impact)
            elif not self.missed and impact < .4:
                radius = max(2, round(5+impact*43))
                pg.draw.circle(surface, color, target, radius, max(1, round(4*(1-impact/.4))))
                if impact < .15:
                    pg.draw.circle(surface, (255, 226, 164), target, max(2, round(12*(1-impact/.15))))
            text(surface, "MISS" if self.missed else f"−{self.damage}" if self.damage else "SHIELD", (target[0]+22, target[1]-22-round(impact*22)), 19, color, "mono")

    def draw_explosion(self, surface, center, age):
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
        surface.blit(layer, (x-90, y-90))
