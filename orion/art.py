"""A lightweight animated backdrop and original code-drawn spacecraft."""

import math
import random
import pygame as pg
from .ui import ASSETS, CYAN, GOLD, LINE

SIZE=(1440,900)


def ship(surface, x, y, scale=1.0, angle=-.26):
    def pt(a,b):
        return (x+scale*(a*math.cos(angle)-b*math.sin(angle)),
                y+scale*(a*math.sin(angle)+b*math.cos(angle)))
    hull=[(-40,-9),(-14,-12),(4,-8),(43,0),(4,8),(-14,12),(-40,9),(-33,0)]
    wing=[(-28,-11),(-39,-28),(-8,-17),(14,0),(-8,17),(-39,28),(-28,11)]
    pg.draw.polygon(surface,(41,63,73),[pt(*p) for p in wing])
    pg.draw.polygon(surface,(75,98,107),[pt(*p) for p in hull])
    pg.draw.lines(surface,(140,159,163),False,[pt(-38,-8),pt(-14,-11),pt(4,-7),pt(40,0)],1)
    pg.draw.lines(surface,(36,51,63),False,[pt(-30,0),pt(24,0)],max(1,int(scale*3)))
    pg.draw.line(surface,GOLD,pt(0,-3),pt(17,-1),max(1,int(scale*2)))
    for dy in (-7,7):
        pg.draw.line(surface,(20,77,96),pt(-42,dy),pt(-58,dy),max(1,int(scale*5)))
        pg.draw.line(surface,CYAN,pt(-42,dy),pt(-49,dy),max(1,int(scale*2)))


class Backdrop:
    def __init__(self):
        self.space=pg.image.load(str(ASSETS/"space.png")).convert()
        self.planet=pg.image.load(str(ASSETS/"planet.png")).convert_alpha()
        rng=random.Random(24)
        self.stars=[(rng.randrange(1440),rng.randrange(900),rng.uniform(.1,1),rng.uniform(0,6.3)) for _ in range(290)]
        self.shade=pg.Surface(SIZE,pg.SRCALPHA)
        self.shade.fill((3,8,14,193))
        self.moon=pg.transform.smoothscale(self.planet,(104,104))
        self.moon.set_alpha(150)

    def draw(self,surface,time,animated=True,full=True):
        t=time if animated else 3.0
        surface.blit(self.space,(0,0))
        for x,y,brightness,phase in self.stars:
            value=int((55+125*brightness)*(.83+.17*math.sin(t*.6+phase)))
            color=(int(value*.8),int(value*.92),value)
            pg.draw.circle(surface,color,(x,y),1 if brightness<.94 else 2)
            if brightness>.985:
                pg.draw.line(surface,(value//3,value//3,value//2),(x-5,y),(x+5,y))
                pg.draw.line(surface,(value//3,value//3,value//2),(x,y-5),(x,y+5))
        if full:
            # Technical orbital guides sit behind the planet.
            pg.draw.ellipse(surface,(42,57,63),(656,194,738,466),1)
            pg.draw.ellipse(surface,(30,48,59),(619,160,812,534),1)
            surface.blit(self.moon,(1180,110))
            surface.blit(self.planet,(637,139))
            for a in (2.15,2.42,2.67):
                x=1025+376*math.cos(a)
                y=430+237*math.sin(a)
                pg.draw.circle(surface,GOLD,(int(x),int(y)),2)
            drift=math.sin(t*.13)*10
            ship(surface,945+drift,708+math.cos(t*.17)*5,1.05,-.34)
            ship(surface,1117+drift*.6,760+math.cos(t*.13)*4,.44,-.34)
            ship(surface,869+drift*.8,773+math.cos(t*.15)*3,.36,-.34)

    def dim(self,surface):
        surface.blit(self.shade,(0,0))
