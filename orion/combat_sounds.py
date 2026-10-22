"""Original synthesized combat cues; no downloaded samples or new dependencies."""

from array import array
import math
import random


DURATIONS = {"beam": .20, "heavy_beam": .30, "launch": .30,
             "shield": .24, "impact": .25, "explosion": .65}


def samples(name, rate, channels):
    frames = round(DURATIONS[name]*rate)
    rng = random.Random(8041+sum(map(ord, name)))
    result = array("h")
    phase, noise = 0.0, 0.0
    for index in range(frames):
        t = index/rate
        progress = index/frames
        fade = min(1, t/.006)*(1-progress)**2
        noise = .78*noise+.22*rng.uniform(-1, 1)
        if name in ("beam", "heavy_beam"):
            base = 1600 if name == "beam" else 620
            phase += math.tau*(base*(1-progress)**2+100)/rate
            value = .65*math.sin(phase)+.12*math.sin(phase*2.01)+.20*noise
        elif name == "launch":
            value = 1.4*noise+.18*math.sin(math.tau*(85*t+45*t*t))
        elif name == "shield":
            value = .4*math.sin(math.tau*510*t)+.25*math.sin(math.tau*773*t)
            value *= .75+.25*math.sin(math.tau*24*t)
        elif name == "impact":
            value = 1.7*noise+.30*math.sin(math.tau*125*t)
        else:
            value = 1.9*noise+.38*math.sin(math.tau*(60*t-20*t*t))
        amplitude = round(max(-1, min(1, value*fade)) * 10500)
        result.extend([amplitude]*channels)
    return result
